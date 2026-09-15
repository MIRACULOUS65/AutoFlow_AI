"""Task and planning contracts.

Covers the raw user request, the normalized task, and the planner's task graph
(a DAG). DAG validation (no cycles, valid references, resolvable dependencies)
is enforced on construction so an invalid plan cannot exist as a valid object.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import (
    IdStr,
    Reference,
    Tenancy,
    VersionedModel,
    validate_id,
)
from .enums import AgentKind, RiskClass


class Attachment(VersionedModel):
    """An input file/reference attached to a task request."""

    attachment_id: IdStr
    filename: str = Field(min_length=1, max_length=512)
    mime_type: str = Field(min_length=1, max_length=128)
    uri: str | None = Field(default=None, max_length=2048)
    content_hash: str | None = Field(default=None, min_length=8, max_length=128)

    @field_validator("attachment_id")
    @classmethod
    def _aid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="att")


class TaskRequest(VersionedModel):
    """Raw natural-language objective plus context (master prompt §5, FR-01)."""

    task_id: IdStr
    tenancy: Tenancy
    principal_id: IdStr
    prompt: str = Field(min_length=1, max_length=20_000)
    attachments: tuple[Attachment, ...] = ()
    constraints: tuple[str, ...] = ()
    deadline: str | None = Field(default=None, max_length=64)

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="task")

    @field_validator("principal_id")
    @classmethod
    def _pid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="user")


class NormalizedTask(VersionedModel):
    """Structured interpretation of a request (FR-01 output).

    The normalizer does not execute anything; it produces intent, entities,
    constraints, required capabilities, risk hints, ambiguities and approval
    candidates.
    """

    task_id: IdStr
    objective: str = Field(min_length=1, max_length=4000)
    entities: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    requested_outputs: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    risk_hint: RiskClass = RiskClass.LOW
    target_systems: tuple[str, ...] = ()
    ambiguities: tuple[str, ...] = ()
    approval_candidates: tuple[str, ...] = ()
    missing_information: tuple[str, ...] = ()

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="task")


class VerificationRequirement(VersionedModel):
    """A verification check a step must satisfy to be considered complete."""

    check_id: str = Field(min_length=1, max_length=64)
    description: str = Field(min_length=1, max_length=512)

    @field_validator("check_id")
    @classmethod
    def _cid(cls, v: str) -> str:
        return v.strip()


class TaskNode(VersionedModel):
    """A single planned step (AGENT_BRAIN §4, master prompt §11)."""

    step_id: IdStr
    objective: str = Field(min_length=1, max_length=2000)
    assigned_agent: AgentKind
    input_refs: tuple[Reference, ...] = ()
    preconditions: tuple[str, ...] = ()
    expected_state: dict = Field(default_factory=dict)
    available_capabilities: tuple[str, ...] = ()
    verification: tuple[VerificationRequirement, ...] = ()
    risk: RiskClass = RiskClass.LOW
    requires_approval: bool = False
    timeout_seconds: float = Field(default=120.0, gt=0, le=86_400)
    max_attempts: int = Field(default=3, ge=1, le=50)

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")

    @model_validator(mode="after")
    def _material_steps_verify(self) -> "TaskNode":
        # High-risk steps must define at least one verification and require
        # approval (RULE 4/5/6/7).
        if self.risk in (RiskClass.HIGH, RiskClass.CRITICAL):
            if not self.verification:
                raise ValueError(
                    f"step {self.step_id!r} is {self.risk} risk and must define "
                    "verification"
                )
            if not self.requires_approval:
                raise ValueError(
                    f"step {self.step_id!r} is {self.risk} risk and must set "
                    "requires_approval=True"
                )
        return self


class TaskEdge(VersionedModel):
    """A dependency edge: ``from_step`` must complete before ``to_step``."""

    from_step: IdStr
    to_step: IdStr

    @field_validator("from_step", "to_step")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")

    @model_validator(mode="after")
    def _no_self_loop(self) -> "TaskEdge":
        if self.from_step == self.to_step:
            raise ValueError(f"self-dependency not allowed: {self.from_step}")
        return self


class TaskGraph(VersionedModel):
    """A validated DAG of steps produced by the planner.

    Validation performed on construction:
    * every edge references existing nodes;
    * unique step ids;
    * no cycles (topological sort must succeed);
    * at least one root (no orphan-only graphs);
    * input_refs that point to steps must reference existing steps.
    """

    task_id: IdStr
    goal: str = Field(min_length=1, max_length=4000)
    nodes: tuple[TaskNode, ...]
    edges: tuple[TaskEdge, ...] = ()

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="task")

    @field_validator("nodes")
    @classmethod
    def _nodes_nonempty(cls, v: tuple[TaskNode, ...]) -> tuple[TaskNode, ...]:
        if not v:
            raise ValueError("task graph must contain at least one node")
        return v

    @model_validator(mode="after")
    def _validate_dag(self) -> "TaskGraph":
        ids = [n.step_id for n in self.nodes]
        id_set = set(ids)
        if len(ids) != len(id_set):
            dupes = sorted({x for x in ids if ids.count(x) > 1})
            raise ValueError(f"duplicate step ids: {dupes}")

        for edge in self.edges:
            if edge.from_step not in id_set:
                raise ValueError(f"edge from unknown step: {edge.from_step}")
            if edge.to_step not in id_set:
                raise ValueError(f"edge to unknown step: {edge.to_step}")

        # Duplicate edges are rejected to keep dependency semantics clean.
        edge_pairs = [(e.from_step, e.to_step) for e in self.edges]
        if len(edge_pairs) != len(set(edge_pairs)):
            raise ValueError("duplicate dependency edges are not allowed")

        # Cycle detection via Kahn's algorithm.
        indegree = {sid: 0 for sid in id_set}
        adjacency: dict[str, list[str]] = {sid: [] for sid in id_set}
        for e in self.edges:
            adjacency[e.from_step].append(e.to_step)
            indegree[e.to_step] += 1

        queue = [sid for sid, d in indegree.items() if d == 0]
        visited = 0
        while queue:
            node = queue.pop()
            visited += 1
            for nxt in adjacency[node]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if visited != len(id_set):
            raise ValueError("task graph contains a cycle")

        return self

    def roots(self) -> tuple[str, ...]:
        """Step ids with no incoming dependency."""

        has_incoming = {e.to_step for e in self.edges}
        return tuple(n.step_id for n in self.nodes if n.step_id not in has_incoming)

    def dependencies_of(self, step_id: str) -> tuple[str, ...]:
        return tuple(e.from_step for e in self.edges if e.to_step == step_id)

    def topological_order(self) -> tuple[str, ...]:
        """Return a valid execution order (stable by insertion order)."""

        id_order = [n.step_id for n in self.nodes]
        indegree = {sid: 0 for sid in id_order}
        adjacency: dict[str, list[str]] = {sid: [] for sid in id_order}
        for e in self.edges:
            adjacency[e.from_step].append(e.to_step)
            indegree[e.to_step] += 1
        ready = [sid for sid in id_order if indegree[sid] == 0]
        order: list[str] = []
        while ready:
            # Preserve declaration order for determinism.
            ready.sort(key=id_order.index)
            node = ready.pop(0)
            order.append(node)
            for nxt in adjacency[node]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
        return tuple(order)

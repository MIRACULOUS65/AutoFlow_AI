"""Planning models: typed task graph, node state machine, planner output."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from ..schemas.common import AutoFlowModel, VersionedModel, utcnow
from ..schemas.enums import RiskClass, StrEnum


class AgentType(StrEnum):
    """Specialist agent types (Phase 6)."""

    PLANNER = "planner"
    RESEARCH = "research"
    DOCUMENT = "document"
    SPREADSHEET = "spreadsheet"
    PRESENTATION = "presentation"
    CODING = "coding"
    COMMUNICATION = "communication"
    BROWSER = "browser"
    COMPUTER = "computer"
    QA = "qa"


class NodeStatus(StrEnum):
    """Runtime task-graph node states."""

    PENDING = "pending"
    READY = "ready"
    BLOCKED = "blocked"
    RUNNING = "running"
    WAITING = "waiting"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    NEEDS_REPLAN = "needs_replan"


TERMINAL_NODE_STATES = frozenset(
    {NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.SKIPPED, NodeStatus.CANCELLED}
)


_NODE_TRANSITIONS: dict[NodeStatus, frozenset[NodeStatus]] = {
    NodeStatus.PENDING: frozenset({NodeStatus.READY, NodeStatus.BLOCKED, NodeStatus.SKIPPED, NodeStatus.CANCELLED}),
    NodeStatus.BLOCKED: frozenset({NodeStatus.READY, NodeStatus.SKIPPED, NodeStatus.CANCELLED}),
    NodeStatus.READY: frozenset({NodeStatus.RUNNING, NodeStatus.CANCELLED, NodeStatus.SKIPPED}),
    NodeStatus.RUNNING: frozenset(
        {NodeStatus.SUCCEEDED, NodeStatus.FAILED, NodeStatus.WAITING, NodeStatus.CANCELLED}
    ),
    NodeStatus.WAITING: frozenset({NodeStatus.READY, NodeStatus.RUNNING, NodeStatus.CANCELLED}),
    NodeStatus.FAILED: frozenset({NodeStatus.NEEDS_REPLAN, NodeStatus.CANCELLED}),
    NodeStatus.NEEDS_REPLAN: frozenset({NodeStatus.READY, NodeStatus.SKIPPED, NodeStatus.CANCELLED, NodeStatus.FAILED}),
    NodeStatus.SUCCEEDED: frozenset(),
    NodeStatus.SKIPPED: frozenset(),
    NodeStatus.CANCELLED: frozenset(),
}


def is_valid_node_transition(current: NodeStatus, nxt: NodeStatus) -> bool:
    if current == nxt:
        return True
    return nxt in _NODE_TRANSITIONS.get(current, frozenset())


class ReuseMode(StrEnum):
    REUSE_EXACT = "reuse_exact"
    ADAPT_PARAMETERS = "adapt_parameters"
    ADAPT_PLAN = "adapt_plan"
    IGNORE_MEMORY = "ignore_memory"


class PlanNode(AutoFlowModel):
    """A typed task-graph node (mutable runtime status)."""

    task_id: str = Field(min_length=1, max_length=128)
    objective: str = Field(min_length=1, max_length=2000)
    description: str = Field(default="", max_length=2000)
    agent_type: AgentType
    required_capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    tool_requirements: tuple[str, ...] = ()
    permission_requirements: tuple[str, ...] = ()
    expected_outputs: tuple[str, ...] = ()
    verification_requirements: tuple[str, ...] = ()
    parameters: dict = Field(default_factory=dict)
    risk_level: RiskClass = RiskClass.LOW
    approval_required: bool = False
    status: NodeStatus = NodeStatus.PENDING
    retry_count: int = Field(default=0, ge=0)
    max_retries: int = Field(default=2, ge=0, le=50)
    failure_reason: str | None = None
    output: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("dependencies")
    @classmethod
    def _no_self_dep(cls, v, info):
        return v

    def can_transition_to(self, nxt: NodeStatus) -> bool:
        return is_valid_node_transition(self.status, nxt)


class RuntimeGraph(AutoFlowModel):
    """A validated, mutable task graph for one execution."""

    execution_id: str = Field(min_length=1, max_length=128)
    task_id: str = Field(min_length=1, max_length=128)
    goal: str = Field(min_length=1, max_length=4000)
    nodes: list[PlanNode]
    created_at: datetime = Field(default_factory=utcnow)

    @field_validator("nodes")
    @classmethod
    def _nonempty(cls, v):
        if not v:
            raise ValueError("graph must contain at least one node")
        return v

    def node(self, task_id: str) -> PlanNode | None:
        for n in self.nodes:
            if n.task_id == task_id:
                return n
        return None

    def dependents_of(self, task_id: str) -> list[PlanNode]:
        return [n for n in self.nodes if task_id in n.dependencies]

    def ready_nodes(self) -> list[PlanNode]:
        """Nodes whose dependencies have all succeeded and are not started."""

        ready = []
        for n in self.nodes:
            if n.status not in (NodeStatus.PENDING, NodeStatus.READY, NodeStatus.WAITING):
                continue
            deps = [self.node(d) for d in n.dependencies]
            if all(d is not None and d.status == NodeStatus.SUCCEEDED for d in deps):
                ready.append(n)
        return ready

    def is_complete(self) -> bool:
        return all(n.status in TERMINAL_NODE_STATES for n in self.nodes)

    def has_failure(self) -> bool:
        return any(n.status == NodeStatus.FAILED for n in self.nodes)

    def succeeded_ids(self) -> tuple[str, ...]:
        return tuple(n.task_id for n in self.nodes if n.status == NodeStatus.SUCCEEDED)


class AgentAssignment(AutoFlowModel):
    task_id: str
    agent_type: AgentType


class PlannerOutput(VersionedModel):
    """Strict planner output contract. Free-form prose is never authoritative."""

    normalized_goal: str = Field(min_length=1, max_length=4000)
    assumptions: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ()
    nodes: list[PlanNode]
    agent_assignments: tuple[AgentAssignment, ...] = ()
    required_tools: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    verification_plan: tuple[str, ...] = ()
    approval_points: tuple[str, ...] = ()
    risk_summary: str = ""
    unresolved_questions: tuple[str, ...] = ()
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    planner_version: str = "planner_v1"
    reuse_mode: ReuseMode = ReuseMode.IGNORE_MEMORY
    source_workflow_id: str | None = None

    @field_validator("nodes")
    @classmethod
    def _nonempty(cls, v):
        if not v:
            raise ValueError("planner output must contain at least one node")
        return v

    def to_runtime_graph(self, *, execution_id: str, task_id: str) -> RuntimeGraph:
        return RuntimeGraph(
            execution_id=execution_id,
            task_id=task_id,
            goal=self.normalized_goal,
            nodes=[n.model_copy(deep=True) for n in self.nodes],
        )

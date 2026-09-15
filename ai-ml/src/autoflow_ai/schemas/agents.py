"""Agent contracts.

Agents are profiles over a shared runtime. They receive a typed input bundle
and return typed output — never uncontrolled prose that drives side effects.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import IdStr, Reference, VersionedModel, validate_id
from .enums import ActionType, AgentKind


class AgentDefinition(VersionedModel):
    """A registered specialist agent profile."""

    agent_id: IdStr
    kind: AgentKind
    display_name: str = Field(min_length=1, max_length=128)
    description: str = Field(min_length=1, max_length=1024)
    allowed_tools: frozenset[str] = frozenset()
    default_role_capabilities: tuple[str, ...] = ()

    @field_validator("agent_id")
    @classmethod
    def _aid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="agent")


class AgentRunInput(VersionedModel):
    """Typed input to an agent run (AGENT_BRAIN §3).

    An agent must never operate from the original prompt alone; it receives
    the current step, expected/observed state, authorized context, permitted
    tools, recovery history and an output contract.
    """

    task_id: IdStr
    step_id: IdStr
    objective: str = Field(min_length=1, max_length=2000)
    context_ref: Reference | None = None
    permissions: frozenset[str] = frozenset()
    allowed_tools: frozenset[str] = frozenset()
    observation_ref: Reference | None = None
    recovery_history: tuple[Reference, ...] = ()
    output_contract_ref: Reference | None = None

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="task")

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")


class ProposedAction(VersionedModel):
    """A structured action proposed by an execution agent (PROMPTS §4).

    ``reason`` is concise operational rationale, never hidden chain-of-thought.
    """

    action_type: ActionType
    tool: str | None = Field(default=None, min_length=3, max_length=128)
    arguments: dict = Field(default_factory=dict)
    reason: str = Field(min_length=1, max_length=1024)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _tool_required_for_tool_call(self) -> "ProposedAction":
        if self.action_type == ActionType.TOOL_CALL and not self.tool:
            raise ValueError("tool_call action must name a tool")
        if self.action_type != ActionType.TOOL_CALL and self.tool:
            raise ValueError(f"{self.action_type} action must not name a tool")
        return self


class AgentRun(VersionedModel):
    """The record of a single agent invocation and its typed output."""

    agent_run_id: IdStr
    agent_id: IdStr
    kind: AgentKind
    task_id: IdStr
    step_id: IdStr
    proposed_action: ProposedAction | None = None
    output_refs: tuple[Reference, ...] = ()
    notes: tuple[str, ...] = ()

    @field_validator("agent_run_id")
    @classmethod
    def _arid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="arun")

    @field_validator("agent_id")
    @classmethod
    def _aid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="agent")

    @field_validator("task_id")
    @classmethod
    def _tid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="task")

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")

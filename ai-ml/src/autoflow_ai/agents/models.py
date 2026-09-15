"""Agent context and structured agent outputs."""

from __future__ import annotations

from pydantic import Field

from ..schemas.common import AutoFlowModel
from ..schemas.enums import StrEnum


class AgentStatus(StrEnum):
    OK = "ok"
    NEEDS_TOOL = "needs_tool"
    NEEDS_APPROVAL = "needs_approval"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    NOOP = "noop"


class AgentContext(AutoFlowModel):
    """Bounded, explicit context handed to a specialist agent.

    The agent must not obtain global context out-of-band; everything it may use
    is here. This mirrors the Phase 3 trust boundaries (retrieved content is
    data, permissions are explicit).
    """

    execution_id: str
    task_id: str
    tenant_id: str
    workspace_id: str
    actor: str
    objective: str
    parameters: dict = Field(default_factory=dict)
    available_tools: frozenset[str] = frozenset()
    permissions: frozenset[str] = frozenset()
    constraints: tuple[str, ...] = ()
    prior_outputs: dict = Field(default_factory=dict)      # task_id -> output
    observations: tuple[str, ...] = ()
    context_summary: str = ""  # concise, trust-separated context (no CoT)


class AgentActionProposal(AutoFlowModel):
    """A single proposed tool action (validated + executed by the runtime)."""

    tool_name: str = Field(min_length=1, max_length=128)
    tool_args: dict = Field(default_factory=dict)
    expected_outputs: tuple[str, ...] = ()
    verification_needed: bool = False


class AgentResult(AutoFlowModel):
    """Structured agent output. No raw chain-of-thought is persisted."""

    status: AgentStatus
    reasoning_summary: str = Field(default="", max_length=1024)
    proposed_action: AgentActionProposal | None = None
    expected_state: dict = Field(default_factory=dict)
    observations_needed: tuple[str, ...] = ()
    verification_needed: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    warnings: tuple[str, ...] = ()
    output: dict = Field(default_factory=dict)

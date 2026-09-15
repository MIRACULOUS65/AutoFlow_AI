"""Real-model reasoning path per agent role (fail-closed, deterministic fallback).

Each collaborating agent can reason with a real model to choose its next action.
The model is asked (through the existing ModelRouter — no new gateway) for a
STRUCTURED decision matching :class:`ModelDecision`. Its output is:

* parsed defensively (StructuredOutputError -> fallback);
* validated against the role's tool allowlist (a hallucinated or off-role tool
  is rejected -> fallback);
* bounded (empty/none -> fallback).

If the model is unavailable, times out, errors, or produces anything malformed
or unsafe, the agent FAILS CLOSED to the deterministic specialist proposal.
The model can only ever *propose*; it never executes, and every proposed tool
still passes the full authority chain. So enabling the model never weakens the
safety envelope or the false-success guarantees.
"""

from __future__ import annotations

from pydantic import Field

from ..agents.models import AgentContext, AgentActionProposal, AgentResult, AgentStatus
from ..schemas.common import AutoFlowModel
from ..schemas.enums import ModelRole
from .roles import AgentRole


class ModelDecision(AutoFlowModel):
    """Structured decision we require the model to emit (no chain-of-thought)."""

    action: str = Field(default="produce_output")  # propose_action|produce_output|handoff|blocked
    tool: str | None = None
    tool_args: dict = Field(default_factory=dict)
    reasoning_summary: str = Field(default="", max_length=1024)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


_ROLE_TO_MODEL_ROLE = {
    "supervisor": ModelRole.PLANNER,
    "research": ModelRole.EXECUTOR,
    "document": ModelRole.EXECUTOR,
    "computer": ModelRole.TOOL_CALLER,
    "browser": ModelRole.TOOL_CALLER,
    "qa": ModelRole.EXECUTOR,
}


class ReasoningPolicy:
    """Model-backed decision policy with deterministic fallback.

    ``router`` is any object exposing ``generate(request, prompt=...)`` (the
    real :class:`ModelRouter`). ``deterministic`` is the specialist whose
    ``propose`` provides the safe fallback decision.
    """

    def __init__(self, *, router, role: AgentRole, deterministic) -> None:
        self._router = router
        self._role = role
        self._fallback = deterministic

    def decide(self, context: AgentContext) -> AgentResult:
        """Return an AgentResult; model-derived when valid, else deterministic."""

        fallback = self._fallback.propose(context)
        if self._router is None:
            return fallback
        try:
            decision = self._ask_model(context)
        except Exception:  # noqa: BLE001 - any model failure fails closed
            return fallback
        if decision is None:
            return fallback

        # validate against the role's allowlist + registered/available tools.
        result = self._to_result(decision, context, fallback)
        return result or fallback

    # -- model call ------------------------------------------------------
    def _ask_model(self, context: AgentContext) -> ModelDecision | None:
        from ..model_gateway.structured import parse_into, StructuredOutputError
        from ..schemas.models import ModelRequest

        model_role = _ROLE_TO_MODEL_ROLE.get(self._role.name, ModelRole.EXECUTOR)
        request = ModelRequest(
            request_id="mreq_society",
            required_role=model_role,
            required_capabilities={"structured_output": True},
            require_structured_output=True,
            max_output_tokens=384,
            timeout_seconds=min(context.parameters.get("timeout", 30.0), 60.0)
            if isinstance(context.parameters.get("timeout"), (int, float)) else 30.0,
        )
        response = self._router.generate(request, prompt=self._prompt(context))
        if response.structured_output is not None:
            try:
                return ModelDecision.model_validate(response.structured_output)
            except Exception:  # noqa: BLE001
                return None
        if response.text:
            try:
                return parse_into(response.text, ModelDecision)
            except StructuredOutputError:
                return None
        return None

    def _prompt(self, context: AgentContext) -> str:
        tools = sorted(t for t in context.available_tools if self._role.may_use_tool(t))
        return (
            f"{self._role.system_prompt}\n\n"
            f"Objective: {context.objective}\n"
            f"Allowed tools: {tools or 'none'}\n"
            f"Context: {context.context_summary[:500]}\n\n"
            "Respond ONLY with a JSON object: "
            '{"action": "propose_action|produce_output|handoff|blocked", '
            '"tool": <one allowed tool or null>, "tool_args": {}, '
            '"reasoning_summary": <short>, "confidence": <0..1>}'
        )

    # -- validation ------------------------------------------------------
    def _to_result(self, decision: ModelDecision, context: AgentContext,
                   fallback: AgentResult) -> AgentResult | None:
        if decision.action == "blocked":
            return AgentResult(
                status=AgentStatus.FAILED,
                reasoning_summary=decision.reasoning_summary or "model reported blocked",
                confidence=decision.confidence,
            )
        if decision.action == "handoff":
            return AgentResult(
                status=AgentStatus.NEEDS_TOOL,
                reasoning_summary=decision.reasoning_summary or "model requested handoff",
                confidence=decision.confidence,
            )
        if decision.action == "propose_action":
            tool = decision.tool
            # hallucination guards: tool must exist, be available, and be on-role.
            if not tool:
                return None
            if tool not in context.available_tools:
                return None
            if not self._role.may_use_tool(tool):
                return None
            return AgentResult(
                status=AgentStatus.OK,
                reasoning_summary=decision.reasoning_summary or f"model proposes {tool}",
                proposed_action=AgentActionProposal(tool_name=tool, tool_args=decision.tool_args),
                confidence=min(decision.confidence, 0.95),
            )
        # produce_output: only accept if the fallback also produced output
        # (prevents the model from claiming done with no substance).
        if fallback.output:
            return AgentResult(
                status=AgentStatus.OK,
                reasoning_summary=decision.reasoning_summary or "model produced output",
                output=fallback.output,
                confidence=min(decision.confidence, fallback.confidence + 0.1),
            )
        return None


class ReasoningSpecialist:
    """Adapts a ReasoningPolicy to the SpecialistAgent.propose() interface.

    This lets a CollaborativeAgent use the model path transparently: the
    collaborator calls ``propose(context)`` exactly as before, but the decision
    now comes from the model when available and valid, else deterministically.
    """

    def __init__(self, *, agent_type, capabilities, policy: ReasoningPolicy) -> None:
        self.agent_type = agent_type
        self.capabilities = tuple(capabilities)
        self._policy = policy

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def propose(self, context: AgentContext) -> AgentResult:
        return self._policy.decide(context)

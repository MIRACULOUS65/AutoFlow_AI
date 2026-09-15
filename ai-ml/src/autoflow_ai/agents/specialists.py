"""Specialist agent implementations.

Executable now: Planner (handled separately), Document, Research, Spreadsheet,
QA, and a generic Execution agent. Basic: Presentation, Coding, Communication
(propose a registered tool if one is provided, else NOOP). Honest stubs:
Browser, Computer — real agent types with a real interface that return
UNSUPPORTED rather than faking automation.

Every agent maps its node's ``parameters['tool']`` (or an inferred tool) into a
structured AgentActionProposal. The runtime validates + executes it.
"""

from __future__ import annotations

from ..planning.models import AgentType
from .base import SpecialistAgent
from .models import AgentActionProposal, AgentContext, AgentResult, AgentStatus


def _tool_from_context(context: AgentContext) -> str | None:
    tool = context.parameters.get("tool")
    if tool and tool in context.available_tools:
        return tool
    return tool  # may be validated/rejected by the runtime


class DocumentAgent(SpecialistAgent):
    agent_type = AgentType.DOCUMENT
    capabilities = ("document_editing", "document_inspection")

    def propose(self, context: AgentContext) -> AgentResult:
        tool = _tool_from_context(context)
        if not tool:
            return AgentResult(status=AgentStatus.NOOP, reasoning_summary="no document tool specified")
        args = {k: v for k, v in context.parameters.items() if k != "tool"}

        # For document.edit, translate the natural-language prompt into
        # structured edit operations (the agent's real job). The deterministic
        # runtime then applies them.
        if tool == "document.edit":
            from ..editing.operations import detect_operations_from_prompt

            prompt = args.pop("prompt", "") or context.objective
            ops = detect_operations_from_prompt(prompt)
            args["operations"] = [op.model_dump(mode="json") for op in ops]

        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary=f"document agent will run {tool}",
            proposed_action=AgentActionProposal(tool_name=tool, tool_args=args),
            verification_needed=tool.endswith(".save"),
            confidence=0.9,
        )


class ResearchAgent(SpecialistAgent):
    agent_type = AgentType.RESEARCH
    capabilities = ("research", "knowledge_retrieval")

    def propose(self, context: AgentContext) -> AgentResult:
        # Research is grounded in the provided context summary (retrieved
        # evidence). It produces a structured finding, not a side effect.
        finding = context.context_summary or "no authorized evidence available"
        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary="research agent synthesized authorized evidence",
            output={"finding": finding[:1000], "objective": context.objective},
            confidence=0.7 if context.context_summary else 0.3,
        )


class SpreadsheetAgent(SpecialistAgent):
    agent_type = AgentType.SPREADSHEET
    capabilities = ("data_analysis", "spreadsheet")

    def propose(self, context: AgentContext) -> AgentResult:
        tool = _tool_from_context(context)
        if tool:
            args = {k: v for k, v in context.parameters.items() if k != "tool"}
            return AgentResult(
                status=AgentStatus.OK,
                reasoning_summary=f"spreadsheet agent will run {tool}",
                proposed_action=AgentActionProposal(tool_name=tool, tool_args=args),
                confidence=0.8,
            )
        # no tool -> structured data transformation of prior outputs
        rows = context.prior_outputs
        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary="spreadsheet agent structured prior outputs",
            output={"rows": list(rows.keys()), "count": len(rows)},
            confidence=0.6,
        )


class QAAgent(SpecialistAgent):
    agent_type = AgentType.QA
    capabilities = ("verification", "qa")

    def propose(self, context: AgentContext) -> AgentResult:
        # QA proposes the verification tool when one is provided; otherwise it
        # performs a structural check over prior outputs.
        tool = _tool_from_context(context)
        if tool:
            args = {k: v for k, v in context.parameters.items() if k != "tool"}
            return AgentResult(
                status=AgentStatus.OK,
                reasoning_summary=f"QA agent will verify via {tool}",
                proposed_action=AgentActionProposal(tool_name=tool, tool_args=args, verification_needed=True),
                verification_needed=True,
                confidence=0.9,
            )
        expected = context.parameters.get("expect_outputs", [])
        present = [k for k in expected if k in context.prior_outputs]
        passed = len(present) == len(expected)
        return AgentResult(
            status=AgentStatus.OK if passed else AgentStatus.FAILED,
            reasoning_summary=f"QA checked {len(present)}/{len(expected)} expected outputs",
            output={"passed": passed, "present": present},
            verification_needed=True,
            confidence=1.0 if passed else 0.0,
        )


class GenericExecutionAgent(SpecialistAgent):
    agent_type = AgentType.DOCUMENT  # default fallback maps to a benign type
    capabilities = ("generic",)

    def propose(self, context: AgentContext) -> AgentResult:
        tool = _tool_from_context(context)
        if not tool:
            return AgentResult(status=AgentStatus.NOOP, reasoning_summary="no tool to execute")
        args = {k: v for k, v in context.parameters.items() if k != "tool"}
        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary=f"execution agent will run {tool}",
            proposed_action=AgentActionProposal(tool_name=tool, tool_args=args),
            confidence=0.7,
        )


class _BasicToolAgent(SpecialistAgent):
    """Presentation/Coding/Communication: propose a registered tool or NOOP."""

    def propose(self, context: AgentContext) -> AgentResult:
        tool = _tool_from_context(context)
        if not tool:
            return AgentResult(
                status=AgentStatus.NOOP,
                reasoning_summary=f"{self.agent_type} has no registered tool for this step",
            )
        args = {k: v for k, v in context.parameters.items() if k != "tool"}
        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary=f"{self.agent_type} will run {tool}",
            proposed_action=AgentActionProposal(tool_name=tool, tool_args=args),
            confidence=0.6,
        )


class PresentationAgent(_BasicToolAgent):
    agent_type = AgentType.PRESENTATION
    capabilities = ("presentation",)


class CodingAgent(_BasicToolAgent):
    agent_type = AgentType.CODING
    capabilities = ("coding",)


class CommunicationAgent(SpecialistAgent):
    """Composes email/messaging actions.

    It proposes a communication tool (``gmail.*`` / ``email.*`` / a registered
    ``communication`` tool). It refuses to act outside its capability: a tool
    that is not a communication tool yields UNSUPPORTED rather than a blind
    passthrough. Sending is never proposed directly — the Gmail workflow's
    approval gate owns that side effect.
    """

    agent_type = AgentType.COMMUNICATION
    capabilities = ("communication", "email")

    _COMM_PREFIXES = ("gmail.", "email.", "communication.")

    def propose(self, context: AgentContext) -> AgentResult:
        tool = context.parameters.get("tool")
        if not tool:
            return AgentResult(
                status=AgentStatus.NOOP,
                reasoning_summary="communication agent has no tool for this step",
            )
        if not any(tool.startswith(p) for p in self._COMM_PREFIXES):
            # capability guard: refuse to act on a non-communication tool
            return AgentResult(
                status=AgentStatus.UNSUPPORTED,
                reasoning_summary=f"{tool} is outside the communication agent's capability",
                warnings=(f"{tool} is not a communication tool",),
            )
        if tool not in context.available_tools:
            return AgentResult(
                status=AgentStatus.UNSUPPORTED,
                reasoning_summary=f"communication tool {tool} is not registered/available",
                warnings=(f"{tool} unavailable",),
            )
        args = {k: v for k, v in context.parameters.items() if k != "tool"}
        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary=f"communication agent will run {tool}",
            proposed_action=AgentActionProposal(tool_name=tool, tool_args=args),
            # a send is high-consequence; require verification downstream
            verification_needed=tool.endswith(".send"),
            confidence=0.8,
        )


class _UnsupportedAgent(SpecialistAgent):
    """Real agent interface whose advanced execution is not implemented yet.

    Returns UNSUPPORTED — it never fakes automation."""

    def propose(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            status=AgentStatus.UNSUPPORTED,
            reasoning_summary=f"{self.agent_type} automation requires a future adapter and registered tools",
            warnings=(f"{self.agent_type} not implemented in this phase",),
            confidence=0.0,
        )


class BrowserAutomationAgent(SpecialistAgent):
    """Real browser specialist.

    Proposes ONE semantic ``browser.*`` action per node (navigate/find/read/
    fill/click/wait/close) from the node's parameters. The runtime's
    tool-calling controller executes it through the same authority chain, and
    the BrowserAdapter enforces the local/allowlisted-URL policy. It refuses to
    act outside its capability (non-browser tool -> UNSUPPORTED) and NOOPs when
    no browser tool is specified — it never fakes navigation.
    """

    agent_type = AgentType.BROWSER
    capabilities = ("browser_automation", "web_navigation")

    def propose(self, context: AgentContext) -> AgentResult:
        tool = context.parameters.get("tool")
        if not tool:
            return AgentResult(
                status=AgentStatus.NOOP,
                reasoning_summary="no browser tool specified for this step",
            )
        if not tool.startswith("browser."):
            return AgentResult(
                status=AgentStatus.UNSUPPORTED,
                reasoning_summary=f"{tool} is outside the browser agent's capability",
                warnings=(f"{tool} is not a browser tool",),
            )
        if tool not in context.available_tools:
            return AgentResult(
                status=AgentStatus.UNSUPPORTED,
                reasoning_summary=f"browser tool {tool} is not registered/available",
                warnings=(f"{tool} unavailable",),
            )
        args = {k: v for k, v in context.parameters.items() if k != "tool"}
        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary=f"browser agent will run {tool}",
            proposed_action=AgentActionProposal(tool_name=tool, tool_args=args),
            verification_needed=tool in ("browser.click", "browser.fill", "browser.navigate"),
            confidence=0.85,
        )


class ComputerAutomationAgent(SpecialistAgent):
    """Real Windows computer agent (Phase 7).

    Proposes ONE semantic computer tool action per node from the node's
    ``parameters`` (the deterministic desktop planner emits explicit per-step
    computer tool calls). It never invokes the adapter directly — the runtime's
    tool-calling controller executes the proposal. When no computer tool is
    specified it is a NOOP (honest), not a fake action.
    """

    agent_type = AgentType.COMPUTER
    capabilities = ("computer_use", "desktop_automation")

    def propose(self, context: AgentContext) -> AgentResult:
        tool = context.parameters.get("tool")
        if not tool or not tool.startswith("computer."):
            return AgentResult(
                status=AgentStatus.NOOP,
                reasoning_summary="no computer tool specified for this step",
            )
        if tool not in context.available_tools:
            return AgentResult(
                status=AgentStatus.UNSUPPORTED,
                reasoning_summary=f"computer tool {tool} is not registered/available",
                warnings=(f"{tool} unavailable",),
            )
        args = {k: v for k, v in context.parameters.items() if k != "tool"}
        return AgentResult(
            status=AgentStatus.OK,
            reasoning_summary=f"computer agent will run {tool}",
            proposed_action=AgentActionProposal(tool_name=tool, tool_args=args),
            verification_needed=tool in ("computer.hotkey", "computer.click"),
            confidence=0.85,
        )

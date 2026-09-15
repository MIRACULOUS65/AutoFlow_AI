"""Dynamic planners.

* ``DeterministicPlanner`` — rule-based decomposition into a validated graph.
  It is memory-aware: it can reuse/adapt a compatible verified workflow.
* ``ModelPlanner`` — asks the model gateway for a structured PlannerOutput,
  validates it, and FAILS CLOSED on malformed output (falling back to the
  deterministic planner so the system always produces a valid plan).
"""

from __future__ import annotations

import re

from ..schemas.enums import RiskClass
from .models import AgentType, PlanNode, PlannerOutput, ReuseMode


def _slug(text: str, n: int = 4) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())[:n]
    return "_".join(words) or "task"


class DeterministicPlanner:
    """Rule-based decomposition. Always produces a schema-valid PlannerOutput."""

    planner_version = "deterministic_v1"

    def plan(
        self,
        prompt: str,
        *,
        target_path: str | None = None,
        available_tools: set[str] | None = None,
    ) -> PlannerOutput:
        p = prompt.lower()
        tools = available_tools or set()

        # Desktop / computer-use family (Phase 7): open an app, type, save.
        if "notepad" in p or ("open" in p and ("type" in p or "desktop" in p)):
            if any(t.startswith("computer.") for t in tools):
                return self._desktop_plan(prompt, tools)

        # Document-edit family (Golden 01 shape) -> inspect/edit/save/verify.
        if target_path and any(
            k in p for k in ("edit", "fix", "clean", "normalize", "wording", "save", "document", "word", "file")
        ):
            return self._document_plan(prompt, target_path, tools)

        # Research -> structure -> summarize family.
        if "research" in p or "competitor" in p or "summar" in p:
            return self._research_plan(prompt)

        # Fallback: single research/QA node so the graph is always valid.
        return self._fallback_plan(prompt)

    def _document_plan(self, prompt: str, path: str, tools: set[str]) -> PlannerOutput:
        nodes = [
            PlanNode(
                task_id="t_inspect",
                objective="Inspect the target document",
                agent_type=AgentType.DOCUMENT,
                required_capabilities=("document_editing",),
                tool_requirements=("document.inspect",),
                permission_requirements=("files:read",),
                parameters={"tool": "document.inspect", "path": path},
                expected_outputs=("document_inspected",),
            ),
            PlanNode(
                task_id="t_edit",
                objective="Apply the requested edits",
                agent_type=AgentType.DOCUMENT,
                required_capabilities=("document_editing",),
                tool_requirements=("document.edit",),
                permission_requirements=("files:write",),
                dependencies=("t_inspect",),
                parameters={"tool": "document.edit", "prompt": prompt},
                expected_outputs=("document_edited",),
            ),
            PlanNode(
                task_id="t_save",
                objective="Save to the same file",
                agent_type=AgentType.DOCUMENT,
                required_capabilities=("document_editing",),
                tool_requirements=("document.save",),
                permission_requirements=("files:write",),
                dependencies=("t_edit",),
                parameters={"tool": "document.save", "target_path": path},
                expected_outputs=("document_saved",),
            ),
            PlanNode(
                task_id="t_verify",
                objective="Verify edits present and file valid",
                agent_type=AgentType.QA,
                required_capabilities=("verification",),
                tool_requirements=("document.verify",),
                dependencies=("t_save",),
                verification_requirements=("edits_present", "file_reopens"),
                parameters={"tool": "document.verify", "path": path},
            ),
        ]
        return PlannerOutput(
            normalized_goal=f"Edit '{path}' and save the result",
            nodes=nodes,
            required_tools=("document.inspect", "document.edit", "document.save", "document.verify"),
            required_capabilities=("document_editing", "verification"),
            expected_artifacts=("edited_document",),
            verification_plan=("verify saved document",),
            confidence=0.9,
            planner_version=self.planner_version,
        )

    def _desktop_plan(self, prompt: str, tools: set[str]) -> PlannerOutput:
        """Notepad-style desktop workflow: launch -> type -> save (Ctrl+S)."""

        import re as _re

        m = _re.search(r'type\s+"([^"]+)"', prompt, _re.IGNORECASE)
        if not m:
            m = _re.search(r"type\s+(.+?)(?:\s+and\b|,|\.|$)", prompt, _re.IGNORECASE)
        text = m.group(1).strip() if m else "HELLO AUTOFLOW"

        nodes = [
            PlanNode(
                task_id="t_launch", objective="Launch Notepad",
                agent_type=AgentType.COMPUTER, required_capabilities=("computer_use",),
                tool_requirements=("computer.launch_application",),
                permission_requirements=("computer:launch",),
                parameters={"tool": "computer.launch_application", "executable": "notepad.exe"},
                expected_outputs=("app_launched",),
            ),
            PlanNode(
                task_id="t_type", objective="Type the text",
                agent_type=AgentType.COMPUTER, required_capabilities=("computer_use",),
                tool_requirements=("computer.type",),
                permission_requirements=("computer:interact",),
                dependencies=("t_launch",),
                parameters={"tool": "computer.type", "text": text},
                expected_outputs=("text_typed",),
            ),
        ]
        return PlannerOutput(
            normalized_goal=f"Open Notepad and type '{text}'",
            nodes=nodes,
            required_tools=("computer.launch_application", "computer.type"),
            required_capabilities=("computer_use",),
            confidence=0.8,
            planner_version=self.planner_version,
        )

    def _research_plan(self, prompt: str) -> PlannerOutput:
        # Independent research nodes fan into a synthesis + verify (parallelizable).
        research_a = PlanNode(
            task_id="t_research_a",
            objective="Research part A",
            agent_type=AgentType.RESEARCH,
            required_capabilities=("research",),
        )
        research_b = PlanNode(
            task_id="t_research_b",
            objective="Research part B",
            agent_type=AgentType.RESEARCH,
            required_capabilities=("research",),
        )
        synth = PlanNode(
            task_id="t_synthesize",
            objective="Combine findings",
            agent_type=AgentType.SPREADSHEET,
            required_capabilities=("data_analysis",),
            dependencies=("t_research_a", "t_research_b"),
            expected_outputs=("combined_findings",),
        )
        verify = PlanNode(
            task_id="t_verify",
            objective="Verify combined findings",
            agent_type=AgentType.QA,
            required_capabilities=("verification",),
            dependencies=("t_synthesize",),
            verification_requirements=("findings_present",),
            parameters={"expect_outputs": ["t_synthesize"]},
        )
        return PlannerOutput(
            normalized_goal=prompt.strip()[:200] or "Research and synthesize",
            nodes=[research_a, research_b, synth, verify],
            required_capabilities=("research", "data_analysis", "verification"),
            confidence=0.7,
            planner_version=self.planner_version,
        )

    def _fallback_plan(self, prompt: str) -> PlannerOutput:
        node = PlanNode(
            task_id="t_research",
            objective=prompt.strip()[:200] or "Handle request",
            agent_type=AgentType.RESEARCH,
            required_capabilities=("research",),
        )
        return PlannerOutput(
            normalized_goal=prompt.strip()[:200] or "Handle request",
            nodes=[node],
            required_capabilities=("research",),
            confidence=0.4,
            planner_version=self.planner_version,
        )


class ModelPlanner:
    """Model-backed planner that fails closed to the deterministic planner.

    It renders a planning request through the gateway. If the model returns
    valid structured PlannerOutput it is used; otherwise the deterministic
    planner is used so the runtime always receives a valid graph. This keeps
    the "malformed planner output must fail closed" invariant.
    """

    planner_version = "model_v1"

    def __init__(self, router, *, deterministic: DeterministicPlanner | None = None) -> None:
        self._router = router
        self._fallback = deterministic or DeterministicPlanner()

    def plan(self, prompt: str, *, target_path: str | None = None, available_tools: set[str] | None = None) -> PlannerOutput:
        from ..model_gateway.structured import StructuredOutputError, parse_into
        from ..schemas.enums import ModelRole
        from ..schemas.models import ModelRequest

        try:
            request = ModelRequest(
                request_id="mreq_planner",
                required_role=ModelRole.PLANNER,
                required_capabilities={"structured_output": True, "reasoning": True},
                require_structured_output=True,
                max_output_tokens=512,
            )
            response = self._router.generate(request, prompt=self._planning_prompt(prompt))
            if response.structured_output:
                # The model may return a plan-shaped dict; validate strictly.
                out = PlannerOutput.model_validate(response.structured_output)
                return out
        except (StructuredOutputError, Exception):  # noqa: BLE001 - fail closed
            pass
        # fail closed: deterministic plan (always valid)
        return self._fallback.plan(prompt, target_path=target_path, available_tools=available_tools)

    @staticmethod
    def _planning_prompt(prompt: str) -> str:
        return (
            "Decompose the objective into a task graph. Objective: " + prompt
        )

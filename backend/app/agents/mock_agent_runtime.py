"""Deterministic mock agent runtime.

Each agent produces predictable structured output for integration testing. It is
intentionally not "smart" — it maps the step's allowed tools into proposed
actions and returns a plausible observation.
"""

from __future__ import annotations

from app.db.base import new_id
from app.domain.enums import RiskClass
from app.schemas.agents import (
    AgentObservation,
    AgentRunRequest,
    AgentRunResult,
    ProposedAction,
)

# Tools that constitute a material (side-effecting/external) action.
_MATERIAL_TOOLS = {"email.send", "email.send.mock", "message.send"}


class MockAgentRuntime:
    async def run_step(self, request: AgentRunRequest) -> AgentRunResult:
        actions: list[ProposedAction] = []
        for tool in request.allowed_tools:
            material = tool in _MATERIAL_TOOLS
            actions.append(
                ProposedAction(
                    tool=tool,
                    arguments=_arguments_for(tool, request),
                    recipient=("finance@example.com" if material else None),
                    resource=request.inputs.get("resource"),
                    risk_class=(RiskClass.HIGH if material else RiskClass.LOW),
                    material=material,
                )
            )

        observation = AgentObservation(
            summary=f"{request.objective}",
            data={"step_id": request.step_id, "expected_state": request.expected_state},
        )
        return AgentRunResult(
            agent_run_id=new_id("arun"),
            status="completed",
            proposed_actions=actions,
            observations=[observation],
            output={"note": "mock output", "step_id": request.step_id},
            telemetry={"mock": True, "tool_count": len(actions)},
        )


def _arguments_for(tool: str, request: AgentRunRequest) -> dict:
    if tool in {"spreadsheet.create", "document.create", "filesystem.create"}:
        return {"name": _artifact_name_for(request), "template": "approved"}
    if tool in {"email.prepare", "email.send", "email.send.mock"}:
        return {"subject": "Weekly Operations Report", "attachment": "report.xlsx"}
    if tool == "knowledge.retrieve.mock":
        return {"query": request.objective, "limit": 3}
    return {}


def _artifact_name_for(request: AgentRunRequest) -> str:
    obj = request.objective.lower()
    if "report" in obj:
        return "report.xlsx"
    if "document" in obj:
        return "document.docx"
    return "deliverable.bin"

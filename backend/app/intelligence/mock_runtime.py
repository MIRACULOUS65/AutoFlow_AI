"""Mock IntelligenceRuntime.

Delegates to the existing mock orchestrator so the current mock execution path
is available through the same coarse interface. NOTE: the primary mock execution
path in this codebase remains the per-step controller in
`app/services/execution_service.py`; this class exists so the intelligence seam
is uniform (mock and integration implement the same Protocol) and so contract
tests can exercise it without the AI/ML server.
"""

from __future__ import annotations

from app.intelligence.interfaces import (
    MissionOutcome,
    MissionRequest,
    PlanResult,
)
from app.orchestration.mock_orchestrator import MockOrchestrator
from app.schemas.task import TaskRequest


class MockIntelligenceRuntime:
    def __init__(self) -> None:
        self._orchestrator = MockOrchestrator()

    async def available(self) -> bool:
        return True

    async def create_plan(self, request: MissionRequest) -> PlanResult:
        plan = await self._orchestrator.create_plan(
            TaskRequest(workspace_id=request.workspace_id, goal=request.goal)
        )
        return PlanResult(plan=plan, external_ref=None, raw={})

    async def run_mission(self, request: MissionRequest) -> MissionOutcome:
        # The mock per-step controller owns real mock execution; this coarse
        # path simply reports a verified completion for interface parity.
        return MissionOutcome(
            status="COMPLETE",
            verified=True,
            outcome="mock_complete",
            reason=None,
            external_ref=None,
            artifacts=[],
            evidence=[],
            events=[],
            raw={},
        )

"""Deterministic mock recovery manager.

Progression: first failure -> REOBSERVE, second -> ALTERNATE_PATH (which the
controller applies and then succeeds), budget exhausted -> FAIL. This drives the
documented recovery fixture (PRD §74).
"""

from __future__ import annotations

from app.domain.enums import RecoveryDecision
from app.schemas.agents import RecoveryOutcome, RecoveryRequest


class MockRecoveryManager:
    async def recover(self, request: RecoveryRequest) -> RecoveryOutcome:
        if request.budget_remaining <= 0:
            return RecoveryOutcome(
                decision=RecoveryDecision.FAIL.value,
                reason="Recovery budget exhausted.",
            )
        if request.attempt <= 1:
            return RecoveryOutcome(
                decision=RecoveryDecision.REOBSERVE.value,
                reason="Re-checking the target state.",
            )
        return RecoveryOutcome(
            decision=RecoveryDecision.ALTERNATE_PATH.value,
            reason="Retrying via an alternate path.",
            detail={"clear_force_fail": True},
        )

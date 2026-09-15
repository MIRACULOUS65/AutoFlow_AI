"""Recovery manager interface. Recovery must be bounded (PRD §42, §80)."""

from __future__ import annotations

from typing import Protocol

from app.schemas.agents import RecoveryOutcome, RecoveryRequest


class RecoveryManager(Protocol):
    async def recover(self, request: RecoveryRequest) -> RecoveryOutcome: ...

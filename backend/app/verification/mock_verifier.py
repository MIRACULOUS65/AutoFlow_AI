"""Deterministic mock verifier.

Returns PASSED for the requested checks by default. A step whose context carries
`force_fail=True` returns FAILED — used to drive the recovery scenario.
"""

from __future__ import annotations

from app.db.base import new_id
from app.domain.enums import VerificationStatus
from app.schemas.agents import (
    VerificationCheck,
    VerificationRequest,
    VerificationResult,
)


class MockVerifier:
    async def verify(self, request: VerificationRequest) -> VerificationResult:
        force_fail = bool(request.context.get("force_fail"))
        checks = [
            VerificationCheck(
                id=check_id,
                passed=not force_fail,
                detail=None if not force_fail else "Target could not be verified.",
            )
            for check_id in (request.checks or ["artifact_exists"])
        ]
        status = VerificationStatus.FAILED if force_fail else VerificationStatus.PASSED
        evidence = [] if force_fail else [f"artifact://{request.step_id}"]
        return VerificationResult(
            verification_id=new_id("ver"),
            status=status,
            checks=checks,
            evidence=evidence,
            confidence=0.4 if force_fail else 0.98,
        )

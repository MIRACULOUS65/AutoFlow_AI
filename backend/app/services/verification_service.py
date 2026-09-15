"""Verification service — persists authoritative verification results.

The Control Plane records verification as a durable, queryable
``VerificationRun`` (+ per-check rows), not just as an event. This is the
honest record of whether the *business outcome* was verified — tool success is
never treated as business success (PRD §41, §79).

In integration mode the verification truth comes only from the AI/ML mission
report (``document_verified`` / independent QA / ``all_verified``); the Control
Plane persists it and gates COMPLETE on it. It is never inferred or faked.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import new_id
from app.domain.enums import VerificationStatus
from app.intelligence.interfaces import MissionOutcome
from app.models.verification import VerificationCheckModel, VerificationRun


# The verification-bearing signals the AI/ML mission report can carry. Each maps
# to a named CP check so the record is explicit about *what* was verified.
_MISSION_CHECK_FIELDS: list[tuple[str, str]] = [
    ("document_verified", "document_verified"),
    ("draft_verified", "draft_verified"),
    ("sent_verified", "sent_verified"),
    ("complete", "mission_complete"),
]


def _mission_checks(result: dict[str, Any]) -> list[tuple[str, bool, str | None]]:
    """Extract the (check_id, passed, detail) rows present in a mission result."""
    rows: list[tuple[str, bool, str | None]] = []
    for field, check_id in _MISSION_CHECK_FIELDS:
        if field in result:
            passed = bool(result.get(field))
            detail = None if passed else f"{check_id} not satisfied"
            rows.append((check_id, passed, detail))

    # Independent-QA / true-agenticity signal, when present.
    agenticity = result.get("agenticity")
    if isinstance(agenticity, dict):
        for flag in ("independent_qa", "success_evidence_gated"):
            if flag in agenticity:
                passed = bool(agenticity.get(flag))
                rows.append((flag, passed, None if passed else f"{flag} not satisfied"))

    if not rows:
        # No explicit signals: fall back to the single boolean verdict so the
        # record is never empty (still honest — mirrors outcome.verified).
        rows.append(("mission_verified", False, "no verification signals present"))
    return rows


async def record_mission_verification(
    session: AsyncSession,
    *,
    execution_id: str,
    outcome: MissionOutcome,
    step_id: str | None = None,
) -> VerificationRun:
    """Persist a VerificationRun (+ checks) from an AI/ML mission outcome.

    Returns the run. The run's status reflects the honest verified truth:
    PASSED only when the mission report says the outcome was verified.
    """
    result = outcome.raw.get("result") if isinstance(outcome.raw, dict) else None
    result = result or {}

    check_rows = _mission_checks(result)
    # The run passes only if the mission was verified AND no explicit check
    # failed. This is stricter than any single flag and never fakes success.
    all_checks_pass = all(passed for _cid, passed, _d in check_rows)
    status = (
        VerificationStatus.PASSED
        if (outcome.verified and all_checks_pass)
        else VerificationStatus.FAILED
    )

    run = VerificationRun(
        id=new_id("ver"),
        execution_id=execution_id,
        step_id=step_id,
        status=status.value,
        confidence=1.0 if status == VerificationStatus.PASSED else 0.0,
        evidence=list(outcome.evidence or []),
    )
    session.add(run)
    await session.flush()

    for check_id, passed, detail in check_rows:
        session.add(
            VerificationCheckModel(
                id=new_id("vchk"),
                verification_run_id=run.id,
                check_id=check_id,
                passed=passed,
                detail=detail,
            )
        )
    await session.flush()
    return run

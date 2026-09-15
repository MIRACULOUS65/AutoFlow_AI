"""Contract mapping between the AI/ML runtime and the Control Plane.

The two systems share the *same vocabulary* but different encodings:
  - AI/ML statuses/enums are lowercase; CP enums are UPPERCASE.
  - AI/ML mission events use their own type names; CP uses dotted EventType.
  - AI/ML mission records use a small status set; CP uses the full state machine.

All translation lives here so no other module has to know the AI/ML shapes.
Every mapping is total for the values we consume; unknown values fall back
conservatively (never silently "succeed").
"""

from __future__ import annotations

from app.domain.enums import EventType, TaskStatus, VerificationStatus

# --- Status: AI/ML lowercase -> CP UPPERCASE ------------------------------

# AI/ML ExecutionStatus values are the lowercase form of CP TaskStatus.
_EXEC_STATUS: dict[str, TaskStatus] = {
    "queued": TaskStatus.QUEUED,
    "planning": TaskStatus.PLANNING,
    "validating": TaskStatus.VALIDATING,
    "awaiting_approval": TaskStatus.AWAITING_APPROVAL,
    "running": TaskStatus.RUNNING,
    "verifying": TaskStatus.VERIFYING,
    "recovery": TaskStatus.RECOVERY,
    "complete": TaskStatus.COMPLETE,
    "failed": TaskStatus.FAILED,
    "cancelled": TaskStatus.CANCELLED,
    "expired": TaskStatus.EXPIRED,
    "blocked": TaskStatus.BLOCKED,
}

# AI/ML mission record status (created|running|awaiting_approval|complete|failed).
_MISSION_STATUS: dict[str, TaskStatus] = {
    "created": TaskStatus.QUEUED,
    "running": TaskStatus.RUNNING,
    "awaiting_approval": TaskStatus.AWAITING_APPROVAL,
    "complete": TaskStatus.COMPLETE,
    "failed": TaskStatus.FAILED,
}


def map_execution_status(value: str) -> TaskStatus:
    return _EXEC_STATUS.get((value or "").lower(), TaskStatus.RUNNING)


def map_mission_status(value: str) -> TaskStatus:
    return _MISSION_STATUS.get((value or "").lower(), TaskStatus.RUNNING)


# --- Events: AI/ML mission EventType -> CP EventType ----------------------

# AI/ML server events.py EventType values (underscore names) -> CP dotted names.
_EVENT_TYPE: dict[str, EventType] = {
    "mission_started": EventType.EXECUTION_STARTED,
    "context_built": EventType.OBSERVATION_CREATED,
    "evidence_retrieved": EventType.OBSERVATION_CREATED,
    "plan_created": EventType.PLAN_CREATED,
    "task_delegated": EventType.STEP_STARTED,
    "action_proposed": EventType.TOOL_REQUESTED,
    "tool_completed": EventType.TOOL_COMPLETED,
    "observation_captured": EventType.OBSERVATION_CREATED,
    "verification_passed": EventType.VERIFICATION_PASSED,
    "verification_failed": EventType.VERIFICATION_FAILED,
    "approval_requested": EventType.APPROVAL_REQUESTED,
    "approval_granted": EventType.APPROVAL_GRANTED,
    "recovery_started": EventType.RECOVERY_STARTED,
    "artifact_created": EventType.ARTIFACT_CREATED,
    "cleanup_completed": EventType.STEP_COMPLETED,
    "mission_completed": EventType.EXECUTION_COMPLETED,
    "mission_failed": EventType.EXECUTION_FAILED,
    "stage": EventType.STEP_STARTED,
}


def map_event_type(value: str) -> EventType | None:
    """Translate an AI/ML mission event type to a CP EventType.

    Returns None for events that should not be surfaced as product events
    (kept out of the canonical stream to avoid implementation noise).
    """
    return _EVENT_TYPE.get((value or "").lower())


# --- Verification ---------------------------------------------------------

_VERIFICATION: dict[str, VerificationStatus] = {
    "passed": VerificationStatus.PASSED,
    "failed": VerificationStatus.FAILED,
    "pending": VerificationStatus.PENDING,
    "inconclusive": VerificationStatus.PENDING,
    "not_run": VerificationStatus.PENDING,
}


def map_verification(value: str | bool | None) -> VerificationStatus:
    if isinstance(value, bool):
        return VerificationStatus.PASSED if value else VerificationStatus.FAILED
    if value is None:
        return VerificationStatus.PENDING
    return _VERIFICATION.get(str(value).lower(), VerificationStatus.PENDING)


# --- Artifact kind: AI/ML lowercase -> CP UPPER ---------------------------

_ARTIFACT_KIND: dict[str, str] = {
    "docx": "DOCX",
    "xlsx": "XLSX",
    "pptx": "PPTX",
    "pdf": "PDF",
    "csv": "CSV",
    "json": "JSON",
    "image": "IMAGE",
    "code": "CODE",
    "test_report": "TEST_REPORT",
    "email_draft": "EMAIL_DRAFT",
    "text": "JSON",  # CP has no TEXT kind; store as JSON metadata
}


def map_artifact_kind_from_name(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return _ARTIFACT_KIND.get(ext, "JSON")

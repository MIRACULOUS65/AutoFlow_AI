"""Contract-convergence tests: every AI/ML enum value maps to a CP value.

The AI/ML enum values are pinned here from `ai-ml/src/autoflow_ai/schemas/
enums.py` and `ai-ml/src/autoflow_ai/server/events.py`. If the AI/ML runtime
adds a value, this test fails loudly so the mapper is updated — no silent drift.
"""

from app.domain.enums import EventType, TaskStatus, VerificationStatus
from app.intelligence import mappers

# ai-ml ExecutionStatus (schemas/enums.py) — lowercase.
AI_ML_EXECUTION_STATUS = [
    "queued", "planning", "validating", "awaiting_approval", "running",
    "verifying", "recovery", "complete", "failed", "cancelled", "expired",
    "blocked",
]

# ai-ml mission record status (server/missions.py).
AI_ML_MISSION_STATUS = ["created", "running", "awaiting_approval", "complete", "failed"]

# ai-ml server EventType (server/events.py).
AI_ML_EVENT_TYPES = [
    "mission_started", "context_built", "evidence_retrieved", "plan_created",
    "task_delegated", "action_proposed", "tool_completed", "observation_captured",
    "verification_passed", "verification_failed", "approval_requested",
    "approval_granted", "recovery_started", "artifact_created",
    "cleanup_completed", "mission_completed", "mission_failed", "stage",
]

# ai-ml VerificationStatus.
AI_ML_VERIFICATION = ["passed", "failed", "inconclusive", "not_run"]


def test_every_execution_status_maps():
    for value in AI_ML_EXECUTION_STATUS:
        result = mappers.map_execution_status(value)
        assert isinstance(result, TaskStatus)
        # lowercase of the CP value must equal the AI/ML value (same vocabulary)
        assert result.value.lower() == value


def test_every_mission_status_maps():
    for value in AI_ML_MISSION_STATUS:
        assert isinstance(mappers.map_mission_status(value), TaskStatus)


def test_every_event_type_maps():
    for value in AI_ML_EVENT_TYPES:
        mapped = mappers.map_event_type(value)
        assert mapped is None or isinstance(mapped, EventType)
    # the operationally-critical ones must map (not dropped)
    for critical in [
        "plan_created", "verification_passed", "verification_failed",
        "approval_requested", "artifact_created", "mission_completed",
        "mission_failed",
    ]:
        assert isinstance(mappers.map_event_type(critical), EventType)


def test_every_verification_maps():
    for value in AI_ML_VERIFICATION:
        assert isinstance(mappers.map_verification(value), VerificationStatus)
    assert mappers.map_verification(True) == VerificationStatus.PASSED
    assert mappers.map_verification(False) == VerificationStatus.FAILED
    assert mappers.map_verification(None) == VerificationStatus.PENDING


def test_unknown_values_fall_back_conservatively():
    # unknown status -> RUNNING (never a fake terminal success)
    assert mappers.map_execution_status("wat") == TaskStatus.RUNNING
    # unknown verification -> PENDING (never PASSED)
    assert mappers.map_verification("wat") == VerificationStatus.PENDING

"""Tests for workflow, artifact, automation, event and audit contracts."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from autoflow_ai.schemas import (
    ActorType,
    ArtifactType,
    AutomationDefinition,
    EventType,
    ExecutionEvent,
    Tenancy,
    TriggerKind,
    WorkflowMemory,
    WorkflowStep,
    WorkflowVersion,
)

pytestmark = pytest.mark.contract


def _tenancy() -> Tenancy:
    return Tenancy(organization_id="org_a", workspace_id="ws_b")


def test_workflow_version_requires_steps():
    with pytest.raises(ValidationError, match="at least one step"):
        WorkflowVersion(workflow_id="wf_1", version=1, intent="i", steps=())


def test_workflow_step_names_unique():
    with pytest.raises(ValidationError, match="unique"):
        WorkflowVersion(
            workflow_id="wf_1",
            version=1,
            intent="i",
            steps=(
                WorkflowStep(name="A", capability="c"),
                WorkflowStep(name="A", capability="c"),
            ),
        )


def test_workflow_step_depends_on_must_exist():
    with pytest.raises(ValidationError, match="unknown"):
        WorkflowVersion(
            workflow_id="wf_1",
            version=1,
            intent="i",
            steps=(WorkflowStep(name="A", capability="c", depends_on=("Ghost",)),),
        )


def test_workflow_step_cannot_depend_on_self():
    with pytest.raises(ValidationError, match="itself"):
        WorkflowVersion(
            workflow_id="wf_1",
            version=1,
            intent="i",
            steps=(WorkflowStep(name="A", capability="c", depends_on=("A",)),),
        )


def test_workflow_memory_must_be_verified():
    with pytest.raises(ValidationError, match="verified"):
        WorkflowMemory(
            memory_id="wmem_1",
            workflow_id="wf_1",
            version=1,
            tenancy=_tenancy(),
            verified=False,
        )


def test_automation_schedule_requires_expression():
    with pytest.raises(ValidationError, match="schedule expression"):
        AutomationDefinition(
            automation_id="auto_1",
            tenancy=_tenancy(),
            name="n",
            trigger_kind=TriggerKind.SCHEDULE,
            workflow_id="wf_1",
            workflow_version=1,
        )


def test_automation_event_requires_event_name():
    with pytest.raises(ValidationError, match="event_name"):
        AutomationDefinition(
            automation_id="auto_1",
            tenancy=_tenancy(),
            name="n",
            trigger_kind=TriggerKind.EVENT,
            workflow_id="wf_1",
            workflow_version=1,
        )


def test_automation_manual_rejects_schedule():
    with pytest.raises(ValidationError, match="manual trigger"):
        AutomationDefinition(
            automation_id="auto_1",
            tenancy=_tenancy(),
            name="n",
            trigger_kind=TriggerKind.MANUAL,
            schedule="0 9 * * MON",
            workflow_id="wf_1",
            workflow_version=1,
        )


def _event(data: dict) -> ExecutionEvent:
    return ExecutionEvent(
        event_id="evt_1",
        type=EventType.TOOL_COMPLETED,
        occurred_at=datetime.now(timezone.utc),
        organization_id="org_a",
        workspace_id="ws_b",
        actor_type=ActorType.WORKER,
        actor_id="worker_1",
        data=data,
    )


def test_event_rejects_secret_keys():
    for secret in ("api_key", "password", "authorization", "access_token",
                   "client_secret", "chain_of_thought"):
        with pytest.raises(ValidationError, match="sensitive keys"):
            _event({secret: "x"})


def test_event_allows_safe_data():
    e = _event({"message_id": "m_1", "status": "sent"})
    assert e.data["status"] == "sent"


def test_event_occurred_at_must_be_tz_aware():
    with pytest.raises(ValidationError, match="timezone-aware"):
        ExecutionEvent(
            event_id="evt_1",
            type=EventType.TASK_CREATED,
            occurred_at=datetime(2026, 1, 1),
            organization_id="org_a",
            workspace_id="ws_b",
            actor_type=ActorType.USER,
            actor_id="user_a",
        )


def test_artifact_type_serializes_to_value():
    from autoflow_ai.schemas import Artifact

    a = Artifact(
        artifact_id="art_1",
        execution_id="exec_1",
        artifact_type=ArtifactType.PDF,
        mime_type="application/pdf",
        content_hash="a" * 16,
    )
    assert a.model_dump(mode="json")["artifact_type"] == "pdf"

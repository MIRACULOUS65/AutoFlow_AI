"""Tests for execution state machine, verification, recovery and approvals."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from autoflow_ai.schemas import (
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    ContextBundle,
    ContextItem,
    Execution,
    ExecutionStatus,
    MemoryItem,
    MemoryKind,
    Reference,
    RiskClass,
    Tenancy,
    TrustLevel,
    VerificationCheck,
    VerificationKind,
    VerificationResult,
    VerificationStatus,
    is_valid_transition,
)

pytestmark = pytest.mark.contract


# ---- execution state machine ------------------------------------------------


@pytest.mark.parametrize(
    "src,dst,ok",
    [
        (ExecutionStatus.QUEUED, ExecutionStatus.PLANNING, True),
        (ExecutionStatus.PLANNING, ExecutionStatus.VALIDATING, True),
        (ExecutionStatus.VALIDATING, ExecutionStatus.AWAITING_APPROVAL, True),
        (ExecutionStatus.AWAITING_APPROVAL, ExecutionStatus.RUNNING, True),
        (ExecutionStatus.RUNNING, ExecutionStatus.VERIFYING, True),
        (ExecutionStatus.VERIFYING, ExecutionStatus.COMPLETE, True),
        (ExecutionStatus.VERIFYING, ExecutionStatus.RECOVERY, True),
        (ExecutionStatus.RECOVERY, ExecutionStatus.RUNNING, True),
        # illegal
        (ExecutionStatus.COMPLETE, ExecutionStatus.RUNNING, False),
        (ExecutionStatus.QUEUED, ExecutionStatus.COMPLETE, False),
        (ExecutionStatus.VERIFYING, ExecutionStatus.PLANNING, False),
        (ExecutionStatus.FAILED, ExecutionStatus.RUNNING, False),
    ],
)
def test_execution_transitions(src, dst, ok):
    assert is_valid_transition(src, dst) is ok


def test_terminal_states_have_no_exits():
    for terminal in (
        ExecutionStatus.COMPLETE,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
        ExecutionStatus.EXPIRED,
        ExecutionStatus.BLOCKED,
    ):
        for target in ExecutionStatus:
            assert not is_valid_transition(terminal, target)


def test_execution_is_terminal_property():
    e = Execution(execution_id="exec_1", task_id="task_1", plan_version=1,
                  status=ExecutionStatus.COMPLETE)
    assert e.is_terminal
    e2 = Execution(execution_id="exec_2", task_id="task_1", plan_version=1)
    assert not e2.is_terminal


# ---- verification -----------------------------------------------------------


def test_passed_verification_requires_passing_checks():
    with pytest.raises(ValidationError, match="at least one check"):
        VerificationResult(
            verification_id="ver_1",
            execution_id="exec_1",
            step_id="step_1",
            status=VerificationStatus.PASSED,
            checks=(),
        )
    with pytest.raises(ValidationError, match="cannot contain a failed check"):
        VerificationResult(
            verification_id="ver_1",
            execution_id="exec_1",
            step_id="step_1",
            status=VerificationStatus.PASSED,
            checks=(
                VerificationCheck(check_id="a", kind=VerificationKind.STRUCTURAL, passed=True),
                VerificationCheck(check_id="b", kind=VerificationKind.SEMANTIC, passed=False),
            ),
        )


def test_failed_verification_cannot_have_all_passing():
    with pytest.raises(ValidationError, match="all checks passing"):
        VerificationResult(
            verification_id="ver_1",
            execution_id="exec_1",
            step_id="step_1",
            status=VerificationStatus.FAILED,
            checks=(
                VerificationCheck(check_id="a", kind=VerificationKind.STRUCTURAL, passed=True),
            ),
        )


# ---- approvals --------------------------------------------------------------


def _approval(**o) -> ApprovalRequest:
    base = dict(
        approval_id="appr_1",
        execution_id="exec_1",
        step_id="step_1",
        plan_version=1,
        action_hash="a" * 16,
        risk=RiskClass.HIGH,
        summary="send email",
        requested_by="user_a",
    )
    base.update(o)
    return ApprovalRequest(**base)


def test_low_risk_cannot_require_approval():
    with pytest.raises(ValidationError, match="medium\\+ risk"):
        _approval(risk=RiskClass.LOW)


def test_approval_binding_matches_exact_plan_and_action():
    appr = _approval(plan_version=3, action_hash="b" * 16)
    assert appr.binds_to(plan_version=3, action_hash="b" * 16)
    # mutated action -> new approval needed
    assert not appr.binds_to(plan_version=3, action_hash="c" * 16)
    # new plan version -> new approval needed
    assert not appr.binds_to(plan_version=4, action_hash="b" * 16)


def test_approval_decision_cannot_be_pending():
    with pytest.raises(ValidationError, match="cannot be PENDING"):
        ApprovalDecision(
            approval_id="appr_1",
            decision=ApprovalStatus.PENDING,
            approver="user_b",
            plan_version=1,
            action_hash="a" * 16,
        )


def test_approval_expiry_must_be_tz_aware():
    with pytest.raises(ValidationError, match="timezone-aware"):
        _approval(expires_at=datetime(2026, 1, 1))
    _approval(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))


# ---- memory promotion -------------------------------------------------------


def test_workflow_memory_must_be_verified():
    tenancy = Tenancy(organization_id="org_a", workspace_id="ws_b")
    ref = Reference(kind="workflow", ref_id="wf_1")
    with pytest.raises(ValidationError, match="verified"):
        MemoryItem(
            memory_id="mem_1",
            kind=MemoryKind.WORKFLOW,
            tenancy=tenancy,
            content_ref=ref,
            verified=False,
        )
    # session memory can be unverified
    MemoryItem(
        memory_id="mem_2",
        kind=MemoryKind.SESSION,
        tenancy=tenancy,
        content_ref=ref,
        verified=False,
    )


# ---- context budget ---------------------------------------------------------


def test_context_bundle_enforces_token_budget():
    item = ContextItem(
        item_ref=Reference(kind="knowledge", ref_id="chunk_1"),
        trust_level=TrustLevel.UNTRUSTED,
        tokens=900,
        section="retrieved_knowledge",
    )
    # 900 used + 200 reserved <= 1200 ok
    ContextBundle(
        bundle_id="ctx_1", task_id="task_1", items=(item,),
        token_budget=1200, reserved_output_tokens=200,
    )
    # 900 used + 400 reserved > 1200 -> reject
    with pytest.raises(ValidationError, match="exceeds token budget"):
        ContextBundle(
            bundle_id="ctx_1", task_id="task_1", items=(item,),
            token_budget=1200, reserved_output_tokens=400,
        )

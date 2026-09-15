"""Canonical valid sample instances for every contract.

Used by the CLI (`autoflow contracts check`, `autoflow eval smoke`) and by the
test suite. Keeping the samples in one place guarantees the CLI self-check and
the tests exercise identical, known-valid shapes.
"""

from __future__ import annotations

from datetime import timezone

from . import schemas as S
from .schemas.common import utcnow


def _dt():
    return utcnow().replace(tzinfo=timezone.utc)


def sample_tenancy() -> S.Tenancy:
    return S.Tenancy(organization_id="org_acme", workspace_id="ws_finance")


def sample_principal() -> S.Principal:
    return S.Principal(
        principal_id="user_alice",
        organization_id="org_acme",
        workspace_id="ws_finance",
        roles=("analyst",),
        permissions=frozenset({"tasks:create", "communication:send"}),
        tool_grants=frozenset({"email.send", "files.write"}),
    )


def sample_task_request() -> S.TaskRequest:
    return S.TaskRequest(
        task_id="task_report01",
        tenancy=sample_tenancy(),
        principal_id="user_alice",
        prompt="Prepare the weekly report and email it to finance after I approve.",
        attachments=(
            S.Attachment(
                attachment_id="att_data01",
                filename="data.xlsx",
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                content_hash="a" * 16,
            ),
        ),
        constraints=("do not send before approval",),
    )


def sample_normalized_task() -> S.NormalizedTask:
    return S.NormalizedTask(
        task_id="task_report01",
        objective="Generate a weekly finance report and email it after approval.",
        entities=("weekly report", "finance team"),
        requested_outputs=("report.xlsx", "email draft"),
        required_capabilities=("spreadsheet", "communication"),
        risk_hint=S.RiskClass.MEDIUM,
        approval_candidates=("send email",),
    )


def sample_task_graph() -> S.TaskGraph:
    nodes = (
        S.TaskNode(
            step_id="step_extract",
            objective="Extract data from the attached spreadsheet.",
            assigned_agent=S.AgentKind.SPREADSHEET,
        ),
        S.TaskNode(
            step_id="step_report",
            objective="Generate the report artifact.",
            assigned_agent=S.AgentKind.DOCUMENT,
        ),
        S.TaskNode(
            step_id="step_verify",
            objective="Verify the report totals reconcile.",
            assigned_agent=S.AgentKind.QA,
            verification=(
                S.VerificationRequirement(
                    check_id="totals", description="totals reconcile"
                ),
            ),
        ),
        S.TaskNode(
            step_id="step_send",
            objective="Send the approved email to finance.",
            assigned_agent=S.AgentKind.COMMUNICATION,
            risk=S.RiskClass.HIGH,
            requires_approval=True,
            verification=(
                S.VerificationRequirement(
                    check_id="sent", description="message exists in sent state"
                ),
            ),
        ),
    )
    edges = (
        S.TaskEdge(from_step="step_extract", to_step="step_report"),
        S.TaskEdge(from_step="step_report", to_step="step_verify"),
        S.TaskEdge(from_step="step_verify", to_step="step_send"),
    )
    return S.TaskGraph(
        task_id="task_report01",
        goal="Weekly finance report + approved email.",
        nodes=nodes,
        edges=edges,
    )


def sample_model_capability() -> S.ModelCapability:
    return S.ModelCapability(
        text=True,
        tool_calling=True,
        structured_output=True,
        reasoning=True,
    )


def sample_model_definition() -> S.ModelDefinition:
    return S.ModelDefinition(
        model_id="model_planner01",
        provider="example",
        provider_model_name="example-large",
        display_name="Example Large",
        roles=(S.ModelRole.PLANNER, S.ModelRole.EXECUTOR),
        capabilities=sample_model_capability(),
        context_window=128_000,
        max_output_tokens=8_192,
    )


def sample_model_request() -> S.ModelRequest:
    return S.ModelRequest(
        request_id="mreq_001",
        required_role=S.ModelRole.PLANNER,
        required_capabilities={"structured_output": True},
        require_structured_output=True,
    )


def sample_model_response() -> S.ModelResponse:
    return S.ModelResponse(
        request_id="mreq_001",
        model_id="model_planner01",
        provider="example",
        finish_reason="stop",
        structured_output={"goal": "ok"},
        usage=S.ModelUsage(input_tokens=100, output_tokens=50),
    )


def sample_tool_definition() -> S.ToolDefinition:
    return S.ToolDefinition(
        name="email.send",
        description="Send an email to approved recipients.",
        input_schema={
            "type": "object",
            "properties": {
                "recipient_group": {"type": "string"},
                "artifact_id": {"type": "string"},
            },
            "required": ["recipient_group"],
            "additionalProperties": False,
        },
        risk_class=S.RiskClass.HIGH,
        permission_scope="communication:send",
        requires_approval=True,
        idempotent=True,
        verifier="email.sent",
    )


def sample_tool_call_request() -> S.ToolCallRequest:
    return S.ToolCallRequest(
        tool_call_id="tcall_001",
        tool_name="email.send",
        arguments={"recipient_group": "finance", "artifact_id": "art_report01"},
        execution_id="exec_001",
        step_id="step_send",
        confidence=0.95,
        reason="Send control is the next required action.",
    )


def sample_tool_call_result() -> S.ToolCallResult:
    return S.ToolCallResult(
        tool_call_id="tcall_001",
        tool_name="email.send",
        ok=True,
        output={"message_id": "m_123"},
        latency_ms=420,
    )


def sample_agent_definition() -> S.AgentDefinition:
    return S.AgentDefinition(
        agent_id="agent_comm01",
        kind=S.AgentKind.COMMUNICATION,
        display_name="Communication Agent",
        description="Drafts and sends messages via approved tools.",
        allowed_tools=frozenset({"email.create_draft", "email.attach", "email.send"}),
    )


def sample_proposed_action() -> S.ProposedAction:
    return S.ProposedAction(
        action_type=S.ActionType.TOOL_CALL,
        tool="email.send",
        arguments={"recipient_group": "finance"},
        reason="Send the approved email.",
        confidence=0.94,
    )


def sample_agent_run_input() -> S.AgentRunInput:
    return S.AgentRunInput(
        task_id="task_report01",
        step_id="step_send",
        objective="Send the approved email.",
        permissions=frozenset({"communication:send"}),
        allowed_tools=frozenset({"email.send"}),
    )


def sample_agent_run() -> S.AgentRun:
    return S.AgentRun(
        agent_run_id="arun_001",
        agent_id="agent_comm01",
        kind=S.AgentKind.COMMUNICATION,
        task_id="task_report01",
        step_id="step_send",
        proposed_action=sample_proposed_action(),
    )


def sample_knowledge_chunk() -> S.KnowledgeChunk:
    return S.KnowledgeChunk(
        chunk_id="chunk_001",
        document_id="doc_sop01",
        source_id="src_drive01",
        tenancy=sample_tenancy(),
        text="Weekly reports use the approved finance template.",
        source_type="pdf",
        trust_level=S.TrustLevel.UNTRUSTED,
        content_hash="b" * 16,
    )


def sample_context_bundle() -> S.ContextBundle:
    return S.ContextBundle(
        bundle_id="ctx_001",
        task_id="task_report01",
        items=(
            S.ContextItem(
                item_ref=S.Reference(kind="knowledge", ref_id="chunk_001"),
                trust_level=S.TrustLevel.UNTRUSTED,
                tokens=120,
                relevance=0.8,
                section="retrieved_knowledge",
            ),
        ),
        token_budget=4000,
        reserved_output_tokens=512,
    )


def sample_memory_item() -> S.MemoryItem:
    return S.MemoryItem(
        memory_id="mem_001",
        kind=S.MemoryKind.WORKFLOW,
        tenancy=sample_tenancy(),
        content_ref=S.Reference(kind="workflow", ref_id="wf_report01"),
        verified=True,
        score=0.9,
    )


def sample_observation() -> S.Observation:
    return S.Observation(
        observation_id="obs_001",
        execution_id="exec_001",
        step_id="step_send",
        summary="Email created and message present in sent folder.",
        data={"message_id": "m_123", "state": "sent"},
    )


def sample_verification_result() -> S.VerificationResult:
    return S.VerificationResult(
        verification_id="ver_001",
        execution_id="exec_001",
        step_id="step_send",
        status=S.VerificationStatus.PASSED,
        checks=(
            S.VerificationCheck(
                check_id="sent", kind=S.VerificationKind.EXTERNAL, passed=True
            ),
        ),
        confidence=0.98,
    )


def sample_recovery_decision() -> S.RecoveryDecision:
    return S.RecoveryDecision(
        decision_id="rec_001",
        execution_id="exec_001",
        step_id="step_send",
        strategy=S.RecoveryStrategy.RETRY,
        attempt_number=1,
        failure_type="transient_timeout",
        remaining_attempts=2,
        reason="Provider timed out; retry is safe and idempotent.",
    )


def sample_execution() -> S.Execution:
    return S.Execution(
        execution_id="exec_001",
        task_id="task_report01",
        plan_version=1,
        status=S.ExecutionStatus.QUEUED,
        steps=(
            S.ExecutionStep(step_id="step_send", status=S.StepStatus.PENDING),
        ),
    )


def sample_approval_request() -> S.ApprovalRequest:
    return S.ApprovalRequest(
        approval_id="appr_001",
        execution_id="exec_001",
        step_id="step_send",
        plan_version=1,
        action_hash="c" * 16,
        risk=S.RiskClass.HIGH,
        summary="Send weekly report email to finance.",
        requested_by="user_alice",
    )


def sample_approval_decision() -> S.ApprovalDecision:
    return S.ApprovalDecision(
        approval_id="appr_001",
        decision=S.ApprovalStatus.APPROVED,
        approver="user_bob",
        plan_version=1,
        action_hash="c" * 16,
    )


def sample_workflow_version() -> S.WorkflowVersion:
    return S.WorkflowVersion(
        workflow_id="wf_report01",
        version=1,
        intent="Weekly finance report + approved email.",
        capabilities=("spreadsheet", "communication"),
        steps=(
            S.WorkflowStep(name="OpenReport", capability="document"),
            S.WorkflowStep(
                name="CreateDraft", capability="communication", depends_on=("OpenReport",)
            ),
            S.WorkflowStep(
                name="RequestApproval",
                capability="approval",
                depends_on=("CreateDraft",),
                requires_approval=True,
            ),
        ),
        verified=True,
    )


def sample_workflow() -> S.Workflow:
    return S.Workflow(
        workflow_id="wf_report01",
        tenancy=sample_tenancy(),
        name="Weekly finance report",
        current_version=1,
    )


def sample_workflow_memory() -> S.WorkflowMemory:
    return S.WorkflowMemory(
        memory_id="wmem_001",
        workflow_id="wf_report01",
        version=1,
        tenancy=sample_tenancy(),
        verified=True,
        score=0.92,
    )


def sample_artifact() -> S.Artifact:
    return S.Artifact(
        artifact_id="art_report01",
        execution_id="exec_001",
        artifact_type=S.ArtifactType.XLSX,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_hash="d" * 16,
        verified=True,
    )


def sample_automation_definition() -> S.AutomationDefinition:
    return S.AutomationDefinition(
        automation_id="auto_weekly01",
        tenancy=sample_tenancy(),
        name="Weekly report",
        trigger_kind=S.TriggerKind.SCHEDULE,
        schedule="0 9 * * MON",
        workflow_id="wf_report01",
        workflow_version=1,
        approval_required=True,
    )


def sample_automation_run() -> S.AutomationRun:
    return S.AutomationRun(
        run_id="arun_auto01",
        automation_id="auto_weekly01",
        status=S.AutomationRunStatus.SCHEDULED,
    )


def sample_execution_event() -> S.ExecutionEvent:
    return S.ExecutionEvent(
        event_id="evt_001",
        type=S.EventType.TASK_CREATED,
        occurred_at=_dt(),
        organization_id="org_acme",
        workspace_id="ws_finance",
        task_id="task_report01",
        actor_type=S.ActorType.USER,
        actor_id="user_alice",
    )


def sample_audit_event() -> S.AuditEvent:
    return S.AuditEvent(
        audit_id="audit_001",
        organization_id="org_acme",
        workspace_id="ws_finance",
        action="email.send",
        actor_type=S.ActorType.WORKER,
        actor_id="worker_7",
        occurred_at=_dt(),
        outcome="verified",
        risk=S.RiskClass.HIGH,
    )


def build_sample_registry() -> dict[str, S.AutoFlowModel]:
    """Return one valid instance of every contract, keyed by class name."""

    instances = [
        sample_tenancy(),
        sample_principal(),
        sample_task_request(),
        sample_normalized_task(),
        sample_task_graph(),
        sample_model_capability(),
        sample_model_definition(),
        sample_model_request(),
        sample_model_response(),
        sample_tool_definition(),
        sample_tool_call_request(),
        sample_tool_call_result(),
        sample_agent_definition(),
        sample_proposed_action(),
        sample_agent_run_input(),
        sample_agent_run(),
        sample_knowledge_chunk(),
        sample_context_bundle(),
        sample_memory_item(),
        sample_observation(),
        sample_verification_result(),
        sample_recovery_decision(),
        sample_execution(),
        sample_approval_request(),
        sample_approval_decision(),
        sample_workflow_version(),
        sample_workflow(),
        sample_workflow_memory(),
        sample_artifact(),
        sample_automation_definition(),
        sample_automation_run(),
        sample_execution_event(),
        sample_audit_event(),
    ]
    return {type(i).__name__: i for i in instances}


def smoke_flow() -> dict:
    """Exercise the primary contract flow and report structured results.

    normalize -> plan (validated DAG) -> tool definition + call (validated
    args) -> observation -> verification -> approval binding check.
    """

    checks: list[dict] = []

    def check(name: str, passed: bool, detail: str = "") -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    # 1. Normalization + planning
    graph = sample_task_graph()
    order = graph.topological_order()
    check(
        "plan_dag_topo_order",
        order == ("step_extract", "step_report", "step_verify", "step_send"),
        detail=str(order),
    )
    check("plan_roots", graph.roots() == ("step_extract",), detail=str(graph.roots()))

    # 2. Tool definition + validated arguments
    tool = sample_tool_definition()
    call = sample_tool_call_request()
    from .schemas.tools import validate_tool_arguments

    try:
        validate_tool_arguments(tool, call.arguments)
        check("tool_arguments_valid", True)
    except ValueError as exc:
        check("tool_arguments_valid", False, detail=str(exc))

    # 3. Observation + verification
    verification = sample_verification_result()
    check(
        "verification_passed",
        verification.status == S.VerificationStatus.PASSED,
    )

    # 4. Approval binding to plan/action version
    approval = sample_approval_request()
    check(
        "approval_binds_matching",
        approval.binds_to(plan_version=1, action_hash="c" * 16),
    )
    check(
        "approval_rejects_mutated_action",
        not approval.binds_to(plan_version=1, action_hash="e" * 16),
    )
    check(
        "approval_rejects_new_plan_version",
        not approval.binds_to(plan_version=2, action_hash="c" * 16),
    )

    # 5. Execution state machine sanity
    from .schemas.execution import is_valid_transition

    check(
        "valid_transition_queued_planning",
        is_valid_transition(S.ExecutionStatus.QUEUED, S.ExecutionStatus.PLANNING),
    )
    check(
        "invalid_transition_complete_running",
        not is_valid_transition(S.ExecutionStatus.COMPLETE, S.ExecutionStatus.RUNNING),
    )

    ok = all(c["passed"] for c in checks)
    return {"ok": ok, "checks": checks, "total": len(checks)}

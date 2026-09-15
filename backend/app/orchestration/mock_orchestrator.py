"""Deterministic mock orchestrator.

Produces a fixed, plausible plan graph. This is a FIXTURE, not business logic —
the real orchestrator (ML #2) will decide plans dynamically. The flagship goal
("weekly operations report") yields the documented 9-step plan; anything else
gets a generic 5-step plan.
"""

from __future__ import annotations

from app.core.security import compute_action_hash
from app.db.base import new_id
from app.domain.enums import PlanValidationStatus, RiskClass
from app.schemas.approval import CanonicalAction
from app.schemas.plan import (
    Plan,
    PlanFragment,
    PlanGraph,
    PlanStepSpec,
    ReplanRequest,
    VerificationCheckSpec,
)
from app.schemas.task import TaskRequest


def _step(
    step_id: str,
    index: int,
    title: str,
    objective: str,
    agent: str,
    *,
    depends_on: list[str] | None = None,
    tools: list[str] | None = None,
    expected: str,
    checks: list[str] | None = None,
    risk: RiskClass = RiskClass.LOW,
    requires_approval: bool = False,
) -> PlanStepSpec:
    return PlanStepSpec(
        step_id=step_id,
        index=index,
        title=title,
        objective=objective,
        agent_profile=agent,
        dependencies=depends_on or [],
        allowed_tools=tools or [],
        expected_state=expected,
        verification_checks=[VerificationCheckSpec(id=c) for c in (checks or [])],
        risk_class=risk,
        requires_approval=requires_approval,
    )


def _flagship_plan(prefix: str) -> list[PlanStepSpec]:
    def sid(n: int) -> str:
        return f"{prefix}_s{n}"

    return [
        _step(sid(1), 1, "Resolve approved template", "Resolve the approved operations report template.",
              "agent_research", tools=["knowledge.retrieve.mock"],
              expected="Approved template resolved.", checks=["template_resolved"]),
        _step(sid(2), 2, "Retrieve operational data", "Retrieve approved operational data for the period.",
              "agent_research", depends_on=[sid(1)], tools=["knowledge.retrieve.mock"],
              expected="Authorized data retrieved.", checks=["data_retrieved"]),
        _step(sid(3), 3, "Analyze data", "Aggregate and reconcile the operational figures.",
              "agent_data", depends_on=[sid(2)], tools=["spreadsheet.create"],
              expected="Figures reconciled.", checks=["totals_reconcile"]),
        _step(sid(4), 4, "Generate report", "Generate report.xlsx from the template and data.",
              "agent_spreadsheet", depends_on=[sid(3)], tools=["spreadsheet.create", "filesystem.create"],
              expected="report.xlsx generated.", checks=["artifact_exists"]),
        _step(sid(5), 5, "Verify report", "Independently verify the report totals and structure.",
              "agent_verification", depends_on=[sid(4)],
              expected="Report verified.", checks=["artifact_exists", "content_valid", "totals_reconcile"]),
        _step(sid(6), 6, "Prepare email draft", "Draft an email to finance with the report attached.",
              "agent_communication", depends_on=[sid(5)], tools=["email.prepare"],
              expected="Email drafted with verified report.", checks=["draft_ready"], risk=RiskClass.MEDIUM),
        _step(sid(7), 7, "Request approval", "Request human approval before sending externally.",
              "agent_communication", depends_on=[sid(6)],
              expected="Human approval recorded.", risk=RiskClass.HIGH, requires_approval=True),
        _step(sid(8), 8, "Send", "Send the approved email to finance (mock send).",
              "agent_communication", depends_on=[sid(7)], tools=["email.send.mock"],
              expected="Email delivered to finance.", risk=RiskClass.HIGH),
        _step(sid(9), 9, "Verify outcome", "Verify the final outcome and record artifacts.",
              "agent_verification", depends_on=[sid(8)],
              expected="Outcome verified.", checks=["outcome_verified"]),
    ]


def _generic_plan(prefix: str) -> list[PlanStepSpec]:
    def sid(n: int) -> str:
        return f"{prefix}_s{n}"

    return [
        _step(sid(1), 1, "Understand goal", "Interpret the goal and scope the work.",
              "agent_planner", expected="Goal understood."),
        _step(sid(2), 2, "Retrieve data", "Retrieve the information required.",
              "agent_research", depends_on=[sid(1)], tools=["knowledge.retrieve.mock"],
              expected="Sources retrieved.", checks=["data_retrieved"]),
        _step(sid(3), 3, "Produce deliverable", "Generate the primary deliverable.",
              "agent_document", depends_on=[sid(2)], tools=["document.create", "filesystem.create"],
              expected="Deliverable generated.", checks=["artifact_exists"]),
        _step(sid(4), 4, "Verify", "Independently verify the deliverable.",
              "agent_verification", depends_on=[sid(3)],
              expected="Deliverable verified.", checks=["artifact_exists", "content_valid"]),
        _step(sid(5), 5, "Approval", "Request approval before any external action.",
              "agent_communication", depends_on=[sid(4)],
              expected="Human approval recorded.", risk=RiskClass.HIGH, requires_approval=True),
    ]


class MockOrchestrator:
    """Deterministic fixture orchestrator."""

    async def create_plan(self, request: TaskRequest) -> Plan:
        goal = request.resolved_goal.lower()
        prefix = new_id("pstep")
        if "report" in goal or "operations" in goal:
            steps = _flagship_plan(prefix)
        else:
            steps = _generic_plan(prefix)

        required_approvals = sum(1 for s in steps if s.requires_approval)
        plan = Plan(
            plan_id=new_id("plan"),
            task_id="",  # filled in by the service when persisting
            version=1,
            graph=PlanGraph(steps=steps),
            generated_by="mock-orchestrator",
            validation_status=PlanValidationStatus.DRAFT,
            risk_summary={
                "max_risk": max((s.risk_class for s in steps), default=RiskClass.LOW).value,
                "material_steps": [s.step_id for s in steps if s.risk_class in (RiskClass.HIGH, RiskClass.CRITICAL)],
            },
            required_approvals=required_approvals,
        )
        # A stable plan hash over the step structure.
        plan.plan_hash = compute_action_hash(
            CanonicalAction(
                tool="plan",
                arguments={"steps": [s.step_id for s in steps]},
                plan_version=1,
            )
        )
        return plan

    async def replan(self, request: ReplanRequest) -> PlanFragment:
        # Deterministic recovery fragment: replace the failed step with an
        # alternate-path step that succeeds.
        alt = _step(
            new_id("pstep"),
            index=0,
            title="Alternate path",
            objective="Retry the failed step via an alternate path.",
            agent="agent_verification",
            expected="Alternate path completed.",
            checks=["artifact_exists"],
        )
        return PlanFragment(steps=[alt], replaces_step_ids=[request.failed_step_id])

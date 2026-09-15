"""Development seed data — essential registry only.

Seeds the minimal registry the app needs to function: organization, workspaces,
the dev user + memberships, and the agent catalog. It deliberately does NOT
seed demo workflows, knowledge sources, tasks, executions, approvals or
artifacts — those surfaces show only real data produced by real runs, so the
UI never displays placeholder/bluff fixtures. Idempotent: re-running is a no-op
once the organization exists.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import session_scope
from app.domain.enums import Role
from app.models.agent import Agent
from app.models.membership import OrganizationMembership, WorkspaceMembership
from app.models.organization import Organization
from app.models.user import User
from app.models.workspace import Workspace
from app.repositories import organizations as orgs_repo

ORG_ID = "org_autoflow"

WORKSPACES = [
    ("ws_operations", "Operations", "Reporting, reconciliation and internal operations."),
    ("ws_finance", "Finance", "Invoice processing, compliance and financial reporting."),
    ("ws_engineering", "Engineering", "Repository QA, release verification and data analysis."),
]

AGENTS = [
    ("agent_planner", "Planner Agent", "planner", "Plans multi-step work and sequences dependencies.",
     ["Goal decomposition", "Dependency resolution", "Plan validation"], ["plan.create", "plan.validate"]),
    ("agent_research", "Research Agent", "research", "Finds and synthesizes evidence from authorized sources.",
     ["Source retrieval", "Provenance checks", "Synthesis"], ["knowledge.retrieve.mock"]),
    ("agent_document", "Document Agent", "document", "Creates and validates documents.",
     ["Document generation", "Template validation"], ["document.create", "filesystem.create"]),
    ("agent_spreadsheet", "Spreadsheet Agent", "spreadsheet", "Analyzes, transforms and generates spreadsheets.",
     ["Analysis", "Transformation", "Spreadsheet generation"], ["spreadsheet.create", "filesystem.create"]),
    ("agent_presentation", "Presentation Agent", "presentation", "Creates presentation artifacts.",
     ["Deck generation", "Layout"], ["document.create"]),
    ("agent_coding", "Coding Agent", "coding", "Writes and tests code.",
     ["Implementation", "Testing", "Code review"], ["filesystem.create"]),
    ("agent_data", "Data Analysis Agent", "data", "Analyzes structured data.",
     ["Analysis", "Validation", "Aggregation"], ["spreadsheet.create"]),
    ("agent_communication", "Communication Agent", "communication", "Creates communications and prepares external actions.",
     ["Drafting", "Recipient resolution", "Approval routing"], ["email.prepare", "email.send.mock"]),
    ("agent_automation", "Computer Automation Agent", "automation", "Operates supported applications.",
     ["Application control", "State observation"], ["filesystem.create"]),
    ("agent_verification", "Verification Agent", "verification", "Validates outputs and outcomes.",
     ["Outcome verification", "Field checks", "Reconciliation"], ["knowledge.retrieve.mock"]),
]

async def _seed_registry(session: AsyncSession) -> None:
    session.add(Organization(id=ORG_ID, name="AutoFlow", status="ACTIVE"))
    for ws_id, name, desc in WORKSPACES:
        session.add(
            Workspace(
                id=ws_id,
                organization_id=ORG_ID,
                name=name,
                slug=name.lower(),
                description=desc,
                policy_profile="standard",
                capabilities=["documents", "spreadsheets", "email"],
                members=0,
            )
        )
    session.add(
        User(id="usr_001", email="ava.mercer@example.com", display_name="Ava Mercer")
    )
    session.add(
        OrganizationMembership(
            user_id="usr_001", organization_id=ORG_ID, role=Role.OPERATOR.value
        )
    )
    for ws_id, _, _ in WORKSPACES:
        session.add(
            WorkspaceMembership(
                user_id="usr_001",
                organization_id=ORG_ID,
                workspace_id=ws_id,
                role=Role.OPERATOR.value,
            )
        )

    for agent_id, name, kind, desc, caps, tools in AGENTS:
        session.add(
            Agent(
                id=agent_id,
                name=name,
                kind=kind,
                description=desc,
                summary=desc,
                capabilities=caps,
                supported_tools=tools,
                tools=[{"id": t, "name": t, "description": f"{t} tool"} for t in tools],
                status="AVAILABLE",
                version="1.0",
            )
        )

    # NOTE: Workflows and knowledge sources are intentionally NOT seeded as
    # demo fixtures — those surfaces show real data only (real verified
    # workflows learned from runs, real ingested knowledge). This keeps the
    # product honest: nothing appears in the UI that wasn't really produced.


async def seed(*, force: bool = False) -> dict:
    """Seed the database. No-op if already seeded (unless force=True)."""
    async with session_scope() as session:
        existing = await orgs_repo.get_organization(session, ORG_ID)
        if existing is not None and not force:
            return {"seeded": False, "reason": "already seeded"}

    if not (await _org_missing()):
        return {"seeded": False, "reason": "already seeded"}

    async with session_scope() as session:
        await _seed_registry(session)

    # Only the essential registry is seeded (org, workspaces, user, agents).
    # No demo tasks/executions/approvals are created — the UI shows real data
    # produced by real runs, never placeholder fixtures.
    return {
        "seeded": True,
        "organization": ORG_ID,
        "tasks": {},
    }


async def _org_missing() -> bool:
    async with session_scope() as session:
        return (await orgs_repo.get_organization(session, ORG_ID)) is None

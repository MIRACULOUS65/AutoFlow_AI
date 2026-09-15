"""Approval endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import DbDep, PrincipalDep
from app.api.serializers import approval_detail, approval_summary
from app.core.errors import forbidden, not_found
from app.domain.enums import Role
from app.repositories import approvals as approvals_repo
from app.schemas.approval import ApprovalDecisionRequest, ApprovalDetail, ApprovalSummary
from app.schemas.common import Page
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=Page[ApprovalSummary])
async def list_approvals(
    session: DbDep,
    principal: PrincipalDep,
    workspace_id: str | None = None,
    status: str | None = None,
    risk_class: str | None = None,
    task_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> Page[ApprovalSummary]:
    rows, total = await approvals_repo.list_approvals(
        session,
        organization_id=principal.organization_id,
        workspace_id=workspace_id,
        status=status,
        risk_class=risk_class,
        task_id=task_id,
        limit=page_size,
        offset=(page - 1) * page_size,
    )
    return Page[ApprovalSummary](
        items=[approval_summary(a) for a in rows], page=page, page_size=page_size, total=total
    )


async def _load(session, approval_id: str, principal):
    ap = await approvals_repo.get_approval(
        session, approval_id, organization_id=principal.organization_id
    )
    if ap is None:
        raise not_found("Approval", approval_id)
    return ap


@router.get("/{approval_id}", response_model=ApprovalDetail)
async def get_approval(
    approval_id: str, session: DbDep, principal: PrincipalDep
) -> ApprovalDetail:
    ap = await _load(session, approval_id, principal)
    return await approval_detail(session, ap)


def _require_approver(principal) -> None:
    if not principal.has_role(Role.OPERATOR, Role.ADMIN, Role.OWNER):
        raise forbidden("You are not permitted to decide approvals.")


@router.post("/{approval_id}/approve", response_model=ApprovalDetail)
async def approve(
    approval_id: str,
    session: DbDep,
    principal: PrincipalDep,
    body: ApprovalDecisionRequest | None = None,
) -> ApprovalDetail:
    _require_approver(principal)
    ap = await _load(session, approval_id, principal)
    ap = await approval_service.approve(
        session, ap, principal=principal, reason=(body.reason if body else None)
    )
    return await approval_detail(session, ap)


@router.post("/{approval_id}/reject", response_model=ApprovalDetail)
async def reject(
    approval_id: str,
    session: DbDep,
    principal: PrincipalDep,
    body: ApprovalDecisionRequest | None = None,
) -> ApprovalDetail:
    _require_approver(principal)
    ap = await _load(session, approval_id, principal)
    ap = await approval_service.reject(
        session, ap, principal=principal, reason=(body.reason if body else None)
    )
    return await approval_detail(session, ap)

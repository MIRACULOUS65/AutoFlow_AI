"""Auth endpoints (mock).

Login returns a mock bearer token for the dev principal. /me resolves the
current principal from the bearer token.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import PrincipalDep
from app.core.security import DEV_PRINCIPAL, issue_mock_token
from app.schemas.auth import CurrentUser, LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(_body: LoginRequest) -> TokenResponse:
    # Mock: any credentials resolve to the dev principal's token.
    return TokenResponse(access_token=issue_mock_token(DEV_PRINCIPAL.user_id))


@router.post("/logout")
async def logout() -> dict:
    return {"ok": True}


@router.get("/me", response_model=CurrentUser)
async def me(principal: PrincipalDep) -> CurrentUser:
    return CurrentUser(
        user_id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        organization_id=principal.organization_id,
        workspace_id=principal.workspace_id,
        roles=list(principal.roles),
    )

"""Auth schemas."""

from __future__ import annotations

from app.domain.enums import Role
from app.schemas.common import Schema


class LoginRequest(Schema):
    email: str
    password: str | None = None


class TokenResponse(Schema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class CurrentUser(Schema):
    user_id: str
    email: str
    display_name: str
    organization_id: str
    workspace_id: str
    roles: list[Role]

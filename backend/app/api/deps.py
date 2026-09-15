"""API dependencies: request context, authentication, authorization, DB session.

Auth is mock in this phase (bearer token -> Principal). Swapping in a real
identity provider only touches `resolve_token`; routes are unchanged.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import forbidden, unauthenticated
from app.core.security import Principal, resolve_token
from app.db.session import get_session
from app.domain.enums import Role


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


def get_request_id(request: Request) -> str:
    existing = request.headers.get("x-request-id")
    return existing or f"req_{uuid.uuid4().hex[:16]}"


async def get_principal(
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization:
        raise unauthenticated("Missing Authorization header.")
    token = authorization
    if authorization.lower().startswith("bearer "):
        token = authorization[7:]
    principal = resolve_token(token)
    if principal is None:
        raise unauthenticated("Invalid or expired token.")
    return principal


def require_roles(*roles: Role):
    """Dependency factory enforcing that the principal has one of the roles."""

    async def _dep(principal: Annotated[Principal, Depends(get_principal)]) -> Principal:
        if roles and not principal.has_role(*roles):
            raise forbidden(
                f"Requires one of roles: {', '.join(r.value for r in roles)}."
            )
        return principal

    return _dep


DbDep = Annotated[AsyncSession, Depends(get_db)]
PrincipalDep = Annotated[Principal, Depends(get_principal)]
RequestIdDep = Annotated[str, Depends(get_request_id)]

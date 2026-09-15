"""Security primitives: action hashing and mock authentication.

The action hash binds an approval to an exact material action. If the material
action changes after approval, the recomputed hash differs and the approval is
invalidated (PRD §16, §23–24).

Mock authentication resolves a bearer token into an identity/context. A real
identity provider can replace `resolve_token` without changing callers.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.domain.enums import Role
from app.schemas.approval import CanonicalAction


def compute_action_hash(action: CanonicalAction) -> str:
    """Deterministic SHA-256 over a canonical action representation.

    Keys are sorted and JSON is emitted without whitespace so semantically
    identical actions always hash identically.
    """
    canonical = {
        "tool": action.tool,
        "arguments": action.arguments,
        "target": action.target,
        "recipient": action.recipient,
        "resource": action.resource,
        "plan_version": action.plan_version,
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def content_hash(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def request_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


# --- Mock authentication --------------------------------------------------


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str
    display_name: str
    organization_id: str
    workspace_id: str
    roles: tuple[Role, ...]

    def has_role(self, *roles: Role) -> bool:
        return any(r in self.roles for r in roles)


# Default development identity, aligned with the frontend's seeded user.
DEV_PRINCIPAL = Principal(
    user_id="usr_001",
    email="ava.mercer@example.com",
    display_name="Ava Mercer",
    organization_id="org_autoflow",
    workspace_id="ws_operations",
    roles=(Role.OPERATOR,),
)

# Tokens recognized in mock auth mode. Format: "mock:<user_id>" or "dev".
_MOCK_TOKENS: dict[str, Principal] = {
    "dev": DEV_PRINCIPAL,
    "mock:usr_001": DEV_PRINCIPAL,
    "mock:usr_admin": Principal(
        user_id="usr_admin",
        email="admin@example.com",
        display_name="Admin",
        organization_id="org_autoflow",
        workspace_id="ws_operations",
        roles=(Role.OWNER, Role.ADMIN),
    ),
    "mock:usr_viewer": Principal(
        user_id="usr_viewer",
        email="viewer@example.com",
        display_name="Viewer",
        organization_id="org_autoflow",
        workspace_id="ws_operations",
        roles=(Role.VIEWER,),
    ),
}


def resolve_token(token: str | None) -> Principal | None:
    """Resolve a bearer token to a principal (mock implementation).

    In mock mode any non-empty token maps to the dev principal unless it matches
    a specific known token. Returns None when no token is supplied.
    """
    if not token:
        return None
    token = token.strip()
    if token in _MOCK_TOKENS:
        return _MOCK_TOKENS[token]
    # Any other non-empty token authenticates as the dev operator in mock mode.
    return DEV_PRINCIPAL


def issue_mock_token(user_id: str = "usr_001") -> str:
    return f"mock:{user_id}"

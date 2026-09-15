"""Authorization filtering seam.

Authorization happens BEFORE model context assembly — never by asking the model
what the user may see. Items in protected sections must match the caller's
tenant/workspace and (if the item declares a permission scope) the caller must
hold at least one matching permission.

Phase 4 (RAG) will feed candidate chunks through this same seam before ranking.
"""

from __future__ import annotations

from dataclasses import dataclass

from .items import ContextItem, PROTECTED_SECTIONS


@dataclass
class AuthorizationContext:
    tenant_id: str
    workspace_id: str
    permissions: frozenset[str] = frozenset()


@dataclass
class AuthorizationResult:
    authorized: list[ContextItem]
    excluded: list[tuple[ContextItem, str]]  # (item, reason)


class AuthorizationFilter:
    def filter(
        self, items: list[ContextItem], auth: AuthorizationContext
    ) -> AuthorizationResult:
        authorized: list[ContextItem] = []
        excluded: list[tuple[ContextItem, str]] = []

        for item in items:
            # Non-protected sections (system/task/identity/etc.) are not tenant
            # scoped and pass through.
            if item.section not in PROTECTED_SECTIONS:
                authorized.append(item)
                continue

            reason = self._exclude_reason(item, auth)
            if reason:
                excluded.append((item, reason))
            else:
                authorized.append(item)

        return AuthorizationResult(authorized=authorized, excluded=excluded)

    @staticmethod
    def _exclude_reason(item: ContextItem, auth: AuthorizationContext) -> str | None:
        if not item.has_authorization_metadata:
            return "missing tenant/workspace metadata"
        if item.tenant_id != auth.tenant_id:
            return "cross-tenant content excluded"
        if item.workspace_id != auth.workspace_id:
            return "cross-workspace content excluded"
        if item.permission_scope:
            if not (item.permission_scope & auth.permissions):
                return "caller lacks required permission scope"
        return None

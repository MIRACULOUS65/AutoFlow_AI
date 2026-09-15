"""Knowledge authorization filter.

Produces the physical Chroma ``where`` filter that PHYSICALLY excludes
unauthorized records before similarity is even considered. This is the RAG
counterpart to the Phase 3 authorization seam: similarity is never permission.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class KnowledgeIdentity:
    tenant_id: str
    workspace_id: str
    permissions: frozenset[str] = frozenset()


class KnowledgeAuthorizationFilter:
    def where_clause(self, identity: KnowledgeIdentity) -> dict:
        """A Chroma ``where`` clause restricting to the caller's scope.

        Tenant + workspace are always enforced physically. Permission-scope is
        additionally checked in Python after retrieval (Chroma cannot match a
        set-membership against a comma-joined string reliably), so this returns
        the tenant/workspace hard filter.
        """

        return {
            "$and": [
                {"tenant_id": identity.tenant_id},
                {"workspace_id": identity.workspace_id},
            ]
        }

    def permitted(self, metadata: dict, identity: KnowledgeIdentity) -> bool:
        """Final Python-side authorization check on a candidate record."""

        if metadata.get("tenant_id") != identity.tenant_id:
            return False
        if metadata.get("workspace_id") != identity.workspace_id:
            return False
        scope_raw = metadata.get("permission_scope", "")
        required = {s for s in scope_raw.split(",") if s}
        if required and not (required & set(identity.permissions)):
            return False
        return True

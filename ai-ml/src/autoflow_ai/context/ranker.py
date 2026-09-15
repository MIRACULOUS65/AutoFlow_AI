"""Deterministic multi-factor context ranking.

No model call is used to rank. Score combines relevance, importance, trust,
freshness and provenance quality. Phase 4 can inject a semantic similarity
score into ``relevance`` without changing this interface.
"""

from __future__ import annotations

from .items import ContextItem
from .trust import TRUST_ORDER


class ContextRanker:
    def __init__(
        self,
        *,
        w_relevance: float = 0.40,
        w_importance: float = 0.25,
        w_trust: float = 0.20,
        w_freshness: float = 0.10,
        w_provenance: float = 0.05,
    ) -> None:
        self._w_rel = w_relevance
        self._w_imp = w_importance
        self._w_trust = w_trust
        self._w_fresh = w_freshness
        self._w_prov = w_provenance

    def score(self, item: ContextItem) -> float:
        trust_norm = TRUST_ORDER.get(item.trust_level, 0) / 100.0
        provenance_quality = 1.0 if (item.source_id and item.provenance) else (
            0.5 if item.source_id else 0.0
        )
        return (
            self._w_rel * item.relevance
            + self._w_imp * item.importance
            + self._w_trust * trust_norm
            + self._w_fresh * item.freshness
            + self._w_prov * provenance_quality
        )

    def rank(self, items: list[ContextItem]) -> list[ContextItem]:
        """Return items sorted best-first. Deterministic: ties broken by id."""

        return sorted(items, key=lambda it: (-self.score(it), it.id))

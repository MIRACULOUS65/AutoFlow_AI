"""ContextAssembler: candidate items -> authorized, sanitized, deduped, ranked,
budgeted ContextBundle.

Pipeline (order matters):
    authorization filter  (exclude unauthorized BEFORE anything else)
      -> sanitize          (quarantine malformed / trust-mismatched)
      -> dedupe            (deterministic, keep highest-ranked source)
      -> estimate tokens
      -> rank              (deterministic multi-factor)
      -> budget            (reserve output first, then fill per-section,
                            drop lowest-value on overflow)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from .authorization import AuthorizationContext, AuthorizationFilter
from .budget import ContextBudgetPolicy
from .bundle import CompressionEvent, ContextBundle, DroppedItem
from .items import ContextItem, ContextSection, SECTION_ORDER
from .ranker import ContextRanker
from .sanitizer import ContextSanitizer
from .tokens import DEFAULT_ESTIMATOR, TokenEstimator


@dataclass
class ContextInput:
    """Everything the assembler needs to build a bundle."""

    request_id: str
    task_id: str
    model_id: str
    context_window: int
    auth: AuthorizationContext
    items: list[ContextItem] = field(default_factory=list)
    execution_id: str | None = None


@dataclass
class AssemblyMetrics:
    assembly_ms: float = 0.0
    items_considered: int = 0
    items_retained: int = 0
    items_dropped: int = 0
    estimated_tokens: int = 0


class ContextAssembler:
    def __init__(
        self,
        *,
        estimator: TokenEstimator | None = None,
        ranker: ContextRanker | None = None,
        sanitizer: ContextSanitizer | None = None,
        authorizer: AuthorizationFilter | None = None,
        budget_policy: ContextBudgetPolicy | None = None,
    ) -> None:
        self._estimator = estimator or DEFAULT_ESTIMATOR
        self._ranker = ranker or ContextRanker()
        self._sanitizer = sanitizer or ContextSanitizer()
        self._authorizer = authorizer or AuthorizationFilter()
        self._budget_policy = budget_policy or ContextBudgetPolicy()
        self.last_metrics = AssemblyMetrics()

    def assemble(self, ctx: ContextInput) -> ContextBundle:
        start = time.perf_counter()
        considered = len(ctx.items)
        dropped: list[DroppedItem] = []
        compression: list[CompressionEvent] = []

        # 1. authorization (before anything else)
        auth_result = self._authorizer.filter(ctx.items, ctx.auth)
        for item, reason in auth_result.excluded:
            dropped.append(
                DroppedItem(id=item.id, section=item.section, reason=reason)
            )

        # 2. sanitize
        sanit = self._sanitizer.sanitize(auth_result.authorized)
        for item, reason in sanit.quarantined:
            dropped.append(
                DroppedItem(id=item.id, section=item.section, reason=f"quarantined: {reason}")
            )
        items = sanit.accepted

        # 3. token estimate (fill token_estimate on each item)
        items = [
            it.model_copy(update={"token_estimate": self._estimator.estimate_text(it.content)})
            for it in items
        ]

        # 4. dedupe (deterministic; keep the higher-ranked item)
        items, dedupe_dropped = self._dedupe(items)
        dropped.extend(dedupe_dropped)

        # 5. rank
        ranked = self._ranker.rank(items)

        # 6. budget
        budget = self._budget_policy.allocate(ctx.context_window)
        kept, budget_dropped, compressed = self._apply_budget(ranked, budget)
        dropped.extend(budget_dropped)
        compression.extend(compressed)

        # order kept items by canonical section order, preserving rank within
        section_index = {s: i for i, s in enumerate(SECTION_ORDER)}
        kept.sort(key=lambda it: (section_index.get(it.section, 999), -self._ranker.score(it), it.id))

        estimated = sum(it.token_estimate for it in kept)

        bundle = ContextBundle(
            request_id=ctx.request_id,
            task_id=ctx.task_id,
            execution_id=ctx.execution_id,
            model_id=ctx.model_id,
            items=tuple(kept),
            token_budget=budget.input_budget,
            reserved_output_tokens=budget.reserved_output_tokens,
            estimated_tokens=estimated,
            dropped_items=tuple(dropped),
            compression_events=tuple(compression),
        )

        self.last_metrics = AssemblyMetrics(
            assembly_ms=(time.perf_counter() - start) * 1000,
            items_considered=considered,
            items_retained=len(kept),
            items_dropped=len(dropped),
            estimated_tokens=estimated,
        )
        return bundle

    # -- helpers -------------------------------------------------------------

    def _dedupe(self, items: list[ContextItem]) -> tuple[list[ContextItem], list[DroppedItem]]:
        seen: dict[str, ContextItem] = {}
        dropped: list[DroppedItem] = []
        # Rank first so the kept duplicate is the higher-value one.
        for item in self._ranker.rank(items):
            key = item.dedupe_key()
            if key in seen:
                dropped.append(
                    DroppedItem(
                        id=item.id,
                        section=item.section,
                        reason=f"duplicate of {seen[key].id}",
                        token_estimate=item.token_estimate,
                    )
                )
            else:
                seen[key] = item
        return list(seen.values()), dropped

    def _apply_budget(self, ranked: list[ContextItem], budget):
        kept: list[ContextItem] = []
        dropped: list[DroppedItem] = []
        compression: list[CompressionEvent] = []
        used_per_section: dict[ContextSection, int] = {}
        total_used = 0

        for item in ranked:
            section_budget = budget.budget_for(item.section)
            used = used_per_section.get(item.section, 0)
            tokens = item.token_estimate

            fits_section = used + tokens <= section_budget or section_budget == 0
            fits_total = total_used + tokens <= budget.input_budget

            if fits_section and fits_total:
                kept.append(item)
                used_per_section[item.section] = used + tokens
                total_used += tokens
            else:
                reason = (
                    "section budget exceeded"
                    if not fits_section
                    else "total input budget exceeded"
                )
                dropped.append(
                    DroppedItem(
                        id=item.id,
                        section=item.section,
                        reason=reason,
                        token_estimate=tokens,
                    )
                )
                compression.append(
                    CompressionEvent(
                        section=item.section,
                        action="drop",
                        detail=f"{item.id}: {reason}",
                    )
                )
        return kept, dropped, compression

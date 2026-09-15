"""Context Engine (Phase 3).

Builds high-quality, bounded, permission-aware, provenance-aware model context
*before* the model gateway is called. It never concatenates raw strings into a
giant prompt: it assembles typed, trust-classified, ranked, budgeted sections
and produces a deterministic, inspectable :class:`ContextBundle`.

    candidate items
       → authorization filter
       → sanitize (trust enforcement, no instruction promotion)
       → dedupe
       → rank (deterministic, semantic scores pluggable in Phase 4)
       → budget (token-aware, output reserved first)
       → sectioned prompt + manifest + deterministic hash
"""

from __future__ import annotations

from .trust import TrustLevel, TRUST_ORDER, is_trusted_instruction_source
from .items import ContextItem, ContextSection, SECTION_ORDER
from .bundle import ContextBundle, DroppedItem, CompressionEvent
from .tokens import TokenEstimator, DEFAULT_ESTIMATOR
from .budget import ContextBudget, ContextBudgetPolicy
from .ranker import ContextRanker
from .sanitizer import ContextSanitizer
from .authorization import AuthorizationFilter
from .assembler import ContextAssembler, ContextInput

__all__ = [
    "TrustLevel",
    "TRUST_ORDER",
    "is_trusted_instruction_source",
    "ContextItem",
    "ContextSection",
    "SECTION_ORDER",
    "ContextBundle",
    "DroppedItem",
    "CompressionEvent",
    "TokenEstimator",
    "DEFAULT_ESTIMATOR",
    "ContextBudget",
    "ContextBudgetPolicy",
    "ContextRanker",
    "ContextSanitizer",
    "AuthorizationFilter",
    "ContextAssembler",
    "ContextInput",
]

"""Token estimation.

The default estimator is a deterministic approximation (NOT an exact tokenizer).
It is explicitly marked as an estimate. A provider-specific tokenizer can be
swapped in later by implementing the same interface.
"""

from __future__ import annotations

from typing import Iterable


class TokenEstimator:
    """Deterministic, provider-agnostic token *estimate*.

    Approximation: ~4 characters per token plus a small per-word component,
    which tracks real BPE tokenizers closely enough for budgeting. This is an
    estimate, never presented as exact.
    """

    is_estimate: bool = True

    def __init__(self, chars_per_token: float = 4.0) -> None:
        if chars_per_token <= 0:
            raise ValueError("chars_per_token must be > 0")
        self._cpt = chars_per_token

    def estimate_text(self, text: str) -> int:
        if not text:
            return 0
        char_based = len(text) / self._cpt
        word_based = len(text.split())
        # Blend: characters dominate, words add a floor for short/dense text.
        return max(1, int(round(max(char_based, word_based * 0.75))))

    def estimate_items(self, items: Iterable) -> int:
        total = 0
        for item in items:
            # item may be a ContextItem or a raw string
            content = getattr(item, "content", item)
            total += self.estimate_text(content)
        return total

    def estimate_bundle(self, bundle) -> int:
        return self.estimate_items(bundle.items)


DEFAULT_ESTIMATOR = TokenEstimator()

"""On-device tool-calling agent (Cactus Needle 2).

Opt-in. Importing this package does NOT import the ``needle`` runtime; that
happens lazily on first use so the base package stays dependency-light.
"""

from __future__ import annotations

from .agent import BUNDLED_WEIGHTS, NeedleAgent, NeedleResult, available, default_weights

__all__ = [
    "NeedleAgent", "NeedleResult", "available", "default_weights", "BUNDLED_WEIGHTS",
]

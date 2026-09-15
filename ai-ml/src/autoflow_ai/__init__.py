"""AutoFlow AI — intelligence and execution core.

This package is the headless, API-first brain of AutoFlow AI. It must be
usable and testable without the desktop client (Electron).

Phase 1 delivers the typed contract layer: all cross-subsystem data shapes
are defined as versioned Pydantic models under :mod:`autoflow_ai.schemas`.
"""

from __future__ import annotations

__version__ = "0.1.0"

# Contract schema version. Bumped when a breaking change is made to any of the
# core contracts. Individual models also carry their own ``schema_version``.
CONTRACTS_VERSION = "1"

"""Intelligence integration boundary.

The single seam between the Control Plane and the real AI/ML runtime. The
control plane depends only on `IntelligenceRuntime`; the concrete implementation
is either the built-in mock or the real AI/ML runtime reached out-of-process
over its HTTP server. Flipping mock -> integration is config-only.
"""

from app.intelligence.interfaces import (
    IntelligenceRuntime,
    MissionOutcome,
    PlanResult,
)

__all__ = ["IntelligenceRuntime", "MissionOutcome", "PlanResult"]

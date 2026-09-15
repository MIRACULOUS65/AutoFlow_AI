"""Computer use (Phase 7): safe, semantic Windows desktop control.

The system reasons about windows, controls, roles, names and states — NOT raw
screen coordinates. Agents propose semantic actions; the ToolCallingController
validates them against the registry/policy/permission/approval chain; only then
does a ComputerAdapter perform the real UI Automation action.

Nothing here grants unrestricted OS authority: destructive/shell tools are not
registered, application launch is allowlisted, and every action returns a
structured observation for verification.
"""

from __future__ import annotations

from .errors import (
    AdapterUnavailable,
    AmbiguousTarget,
    ComputerUseError,
    ElementNotFound,
    UnsafeOperation,
)
from .models import (
    ActionResult,
    ActionStatus,
    ComputerRisk,
    DesktopObservation,
    ElementQuery,
    UIElement,
    WindowInfo,
    desktop_state_hash,
)
from .adapter import ComputerAdapter
from .fake_adapter import FakeDesktopAdapter
from .env import desktop_available
from .observation import (
    FusedObservation,
    ObservationFusion,
    Resolution,
    ResolutionStatus,
    TargetResolver,
)
from .browser import (
    BrowserAdapter,
    BrowserRisk,
    FakeBrowserAdapter,
    PlaywrightBrowserAdapter,
)
from .cv import CVUnavailable, cv_available, image_diff, image_hash, perceptual_hash
from .verification import Check, SignalKind, VerificationEngine, VerificationOutcome
from .autonomy import (
    ApprovalLedger,
    ApprovalRequest,
    RateLimits,
    RecoveryEngine,
    RecoveryStep,
    ResourceLocks,
    StuckDetector,
)
from .workflow import AutonomyLoop, WFStatus, WFStep, WorkflowExecution
from .vision import (
    FakeVisionProvider,
    RateLimitedVision,
    VisionBudget,
    VisionCandidate,
    VisionProvider,
    VisionResult,
)

__all__ = [
    "ComputerUseError",
    "AdapterUnavailable",
    "AmbiguousTarget",
    "ElementNotFound",
    "UnsafeOperation",
    "ActionResult",
    "ActionStatus",
    "ComputerRisk",
    "DesktopObservation",
    "ElementQuery",
    "UIElement",
    "WindowInfo",
    "desktop_state_hash",
    "ComputerAdapter",
    "FakeDesktopAdapter",
    "desktop_available",
    "FusedObservation",
    "ObservationFusion",
    "Resolution",
    "ResolutionStatus",
    "TargetResolver",
    "BrowserAdapter",
    "BrowserRisk",
    "FakeBrowserAdapter",
    "PlaywrightBrowserAdapter",
    "CVUnavailable",
    "cv_available",
    "image_diff",
    "image_hash",
    "perceptual_hash",
    "FakeVisionProvider",
    "RateLimitedVision",
    "VisionBudget",
    "VisionCandidate",
    "VisionProvider",
    "VisionResult",
    "Check",
    "SignalKind",
    "VerificationEngine",
    "VerificationOutcome",
    "ApprovalLedger",
    "ApprovalRequest",
    "RateLimits",
    "RecoveryEngine",
    "RecoveryStep",
    "ResourceLocks",
    "StuckDetector",
    "AutonomyLoop",
    "WFStatus",
    "WFStep",
    "WorkflowExecution",
]

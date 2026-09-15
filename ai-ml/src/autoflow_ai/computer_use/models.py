"""Semantic desktop models: elements, windows, observations, action results."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

from pydantic import Field

from ..schemas.common import AutoFlowModel, utcnow
from ..schemas.enums import StrEnum


class ComputerRisk(StrEnum):
    """Risk class for a computer action."""

    LOW = "low"        # inspect/screenshot/focus/find/wait/read
    MEDIUM = "medium"  # type/click/select/open local file
    HIGH = "high"      # delete/overwrite external/send/purchase/settings


class ActionStatus(StrEnum):
    OK = "ok"
    FAILED = "failed"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"
    UNSAFE = "unsafe"
    TIMEOUT = "timeout"


class UIElement(AutoFlowModel):
    """A semantic UI element. Coordinates are fallback metadata, not identity."""

    element_id: str
    role: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=512)
    automation_id: str = ""
    enabled: bool = True
    visible: bool = True
    focused: bool = False
    value: str | None = None
    # bounding rect kept only as execution fallback metadata
    rect: tuple[int, int, int, int] | None = None

    def matches(self, *, role: str | None = None, name: str | None = None,
                automation_id: str | None = None) -> bool:
        if role is not None and self.role.lower() != role.lower():
            return False
        if automation_id is not None and self.automation_id != automation_id:
            return False
        if name is not None and name.lower() not in self.name.lower():
            return False
        return True


class WindowInfo(AutoFlowModel):
    window_id: str
    title: str = Field(default="", max_length=512)
    process: str = ""
    active: bool = False


class ElementQuery(AutoFlowModel):
    """A semantic query for a UI element (never coordinates)."""

    role: str | None = None
    name: str | None = None
    automation_id: str | None = None
    window: str | None = None

    def describe(self) -> str:
        parts = []
        if self.role:
            parts.append(f"role={self.role}")
        if self.name:
            parts.append(f"name={self.name}")
        if self.automation_id:
            parts.append(f"aid={self.automation_id}")
        if self.window:
            parts.append(f"window={self.window}")
        return "{" + ", ".join(parts) + "}"


class DesktopObservation(AutoFlowModel):
    """Structured, bounded snapshot of desktop state (no huge raw trees)."""

    observation_id: str
    timestamp: datetime = Field(default_factory=utcnow)
    active_window: str | None = None
    windows: tuple[WindowInfo, ...] = ()
    focused_element: UIElement | None = None
    visible_elements: tuple[UIElement, ...] = ()
    application: str | None = None
    screenshot_ref: str | None = None
    state_hash: str = ""

    def summary(self, *, max_elements: int = 20) -> str:
        """Bounded text summary for a model prompt (never the full raw tree)."""

        lines = [f"active_window={self.active_window or 'none'}"]
        for e in self.visible_elements[:max_elements]:
            state = "enabled" if e.enabled else "disabled"
            lines.append(f"- {e.role} '{e.name}' ({state})")
        if len(self.visible_elements) > max_elements:
            lines.append(f"... (+{len(self.visible_elements) - max_elements} more)")
        return "\n".join(lines)


class ActionResult(AutoFlowModel):
    """Result of a computer action. Secrets are never persisted here."""

    action_id: str
    tool: str
    arguments: dict = Field(default_factory=dict)  # sanitized
    status: ActionStatus
    changed_state: bool = False
    duration_ms: int | None = None
    error: str | None = None
    detail: str = ""
    before_hash: str | None = None
    after_hash: str | None = None


def desktop_state_hash(obs: DesktopObservation) -> str:
    """Deterministic fingerprint from SEMANTIC state (not raw pixels).

    Uses active window + visible control roles/names/states + focused element.
    Used for change detection, verification and loop detection.
    """

    payload = {
        "active_window": obs.active_window,
        "application": obs.application,
        "focused": obs.focused_element.name if obs.focused_element else None,
        "elements": sorted(
            f"{e.role}|{e.name}|{int(e.enabled)}|{int(e.visible)}|{e.value or ''}"
            for e in obs.visible_elements
        ),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

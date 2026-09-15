"""Windows UI Automation adapter (real desktop control).

Uses the `uiautomation` package (Windows UIA via comtypes). Resolves elements
semantically (role/name/automation_id) and detects ambiguity rather than
guessing. Application launch is restricted to an allowlist. Coordinates are
never the primary identity; UIA controls are invoked via their native patterns.

Import is guarded so the module loads on any platform; ``available()`` returns
False when UIA cannot be used.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .errors import AdapterUnavailable, UnsafeOperation
from .models import (
    ActionResult,
    ActionStatus,
    DesktopObservation,
    ElementQuery,
    UIElement,
    WindowInfo,
    desktop_state_hash,
)

# Allowlisted executables (safe apps only). No arbitrary launch.
_ALLOWED_APPS = {
    "notepad.exe": "notepad.exe",
    "notepad": "notepad.exe",
    "winword.exe": "winword.exe",
    "calc.exe": "calc.exe",
    "calc": "calc.exe",
}

_MAX_ELEMENTS = 60


def _load_uia():
    try:
        import uiautomation as auto
    except Exception as exc:  # noqa: BLE001
        raise AdapterUnavailable(f"uiautomation not available: {exc}") from exc
    return auto


class WindowsUIAutomationAdapter:
    name = "windows-uia"

    def __init__(self) -> None:
        self._auto = None

    def _uia(self):
        if self._auto is None:
            self._auto = _load_uia()
        return self._auto

    def available(self) -> bool:
        from .env import desktop_available

        return desktop_available()

    # -- observation ---------------------------------------------------------

    def list_windows(self) -> list[WindowInfo]:
        auto = self._uia()
        root = auto.GetRootControl()
        wins = []
        for i, w in enumerate(root.GetChildren()):
            try:
                wins.append(
                    WindowInfo(
                        window_id=f"w{i}",
                        title=w.Name or "",
                        process=str(getattr(w, "ProcessId", "")),
                        active=False,
                    )
                )
            except Exception:  # noqa: BLE001
                continue
        return wins

    def get_active_window(self) -> WindowInfo | None:
        auto = self._uia()
        try:
            fw = auto.GetForegroundControl()
            top = fw.GetTopLevelControl() if fw else None
            if top:
                return WindowInfo(window_id="active", title=top.Name or "", active=True)
        except Exception:  # noqa: BLE001
            return None
        return None

    def _top_level(self, title: str | None):
        auto = self._uia()
        root = auto.GetRootControl()
        for w in root.GetChildren():
            if title is None or (title.lower() in (w.Name or "").lower()):
                return w
        return None

    def _collect_elements(self, control, *, limit: int = _MAX_ELEMENTS) -> list[UIElement]:
        out: list[UIElement] = []

        def walk(node, depth: int):
            if len(out) >= limit or depth > 6:
                return
            for child in node.GetChildren():
                try:
                    name = child.Name or ""
                    role = child.ControlTypeName.replace("Control", "").lower()
                    enabled = bool(getattr(child, "IsEnabled", True))
                    aid = getattr(child, "AutomationId", "") or ""
                    value = None
                    # read editable content via Value or Text pattern where present
                    try:
                        if child.IsValuePatternAvailable():
                            value = child.GetValuePattern().Value
                        elif child.IsTextPatternAvailable():
                            value = child.GetTextPattern().DocumentRange.GetText(4096)
                    except Exception:  # noqa: BLE001
                        value = None
                    out.append(
                        UIElement(
                            element_id=f"{role}:{aid or name}:{len(out)}",
                            role=role,
                            name=name[:512],
                            automation_id=aid,
                            enabled=enabled,
                            value=(value[:512] if isinstance(value, str) else None),
                        )
                    )
                except Exception:  # noqa: BLE001
                    pass
                if len(out) >= limit:
                    return
                walk(child, depth + 1)

        walk(control, 0)
        return out

    def inspect_desktop(self) -> DesktopObservation:
        active = self.get_active_window()
        elements: list[UIElement] = []
        if active:
            top = self._top_level(active.title)
            if top:
                elements = self._collect_elements(top)
        obs = DesktopObservation(
            observation_id=f"obs_{int(time.time()*1000)}",
            active_window=active.title if active else None,
            windows=tuple(self.list_windows()),
            visible_elements=tuple(elements),
            application=active.title if active else None,
        )
        return obs.model_copy(update={"state_hash": desktop_state_hash(obs)})

    # -- windows / apps ------------------------------------------------------

    def find_window(self, title: str) -> WindowInfo | None:
        w = self._top_level(title)
        return WindowInfo(window_id="w", title=w.Name or "", active=False) if w else None

    def focus_window(self, title: str) -> ActionResult:
        w = self._top_level(title)
        if w is None:
            return ActionResult(action_id="a", tool="computer.focus_window",
                                arguments={"title": title}, status=ActionStatus.NOT_FOUND)
        try:
            w.SetActive()
            w.SetTopmost(True)
            w.SetTopmost(False)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="a", tool="computer.focus_window",
                                arguments={"title": title}, status=ActionStatus.FAILED, error=str(exc))
        return ActionResult(action_id="a", tool="computer.focus_window",
                            arguments={"title": title}, status=ActionStatus.OK, changed_state=True)

    def launch_application(self, executable: str) -> ActionResult:
        key = Path(executable).name.lower()
        if key not in _ALLOWED_APPS:
            raise UnsafeOperation(f"application not on allowlist: {executable}")
        try:
            subprocess.Popen([_ALLOWED_APPS[key]])  # noqa: S603 - allowlisted only
            time.sleep(1.0)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="a", tool="computer.launch_application",
                                arguments={"executable": key}, status=ActionStatus.FAILED, error=str(exc))
        return ActionResult(action_id="a", tool="computer.launch_application",
                            arguments={"executable": key}, status=ActionStatus.OK, changed_state=True)

    # -- elements ------------------------------------------------------------

    def find_elements(self, query: ElementQuery) -> list[UIElement]:
        top = self._top_level(query.window) if query.window else self._top_level(
            self.get_active_window().title if self.get_active_window() else None
        )
        if top is None:
            return []
        elements = self._collect_elements(top)
        return [e for e in elements if e.matches(role=query.role, name=query.name,
                                                 automation_id=query.automation_id)]

    def inspect_element(self, query: ElementQuery) -> UIElement | None:
        matches = self.find_elements(query)
        return matches[0] if len(matches) == 1 else None

    def _resolve_control(self, query: ElementQuery):
        """Resolve a live UIA control for a query. Returns (control, count)."""

        auto = self._uia()
        top = self._top_level(query.window) if query.window else auto.GetForegroundControl().GetTopLevelControl()
        if top is None:
            return None, 0
        candidates = []

        def walk(node, depth):
            if depth > 6 or len(candidates) > 200:
                return
            for child in node.GetChildren():
                try:
                    role = child.ControlTypeName.replace("Control", "").lower()
                    name = child.Name or ""
                    aid = getattr(child, "AutomationId", "") or ""
                    ok = True
                    if query.role and role != query.role.lower():
                        ok = False
                    if query.automation_id and aid != query.automation_id:
                        ok = False
                    if query.name and query.name.lower() not in name.lower():
                        ok = False
                    if ok:
                        candidates.append(child)
                except Exception:  # noqa: BLE001
                    pass
                walk(child, depth + 1)

        walk(top, 0)
        if len(candidates) == 1:
            return candidates[0], 1
        return None, len(candidates)

    # -- actions -------------------------------------------------------------

    def click(self, query: ElementQuery) -> ActionResult:
        before = self.inspect_desktop().state_hash
        control, count = self._resolve_control(query)
        if count == 0:
            return ActionResult(action_id="a", tool="computer.click",
                                arguments=query.model_dump(mode="json"), status=ActionStatus.NOT_FOUND)
        if count > 1:
            return ActionResult(action_id="a", tool="computer.click",
                                arguments=query.model_dump(mode="json"), status=ActionStatus.AMBIGUOUS,
                                detail=f"{count} matches")
        try:
            control.Click(simulateMove=False)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="a", tool="computer.click",
                                arguments=query.model_dump(mode="json"), status=ActionStatus.FAILED, error=str(exc))
        after = self.inspect_desktop().state_hash
        return ActionResult(action_id="a", tool="computer.click",
                            arguments=query.model_dump(mode="json"), status=ActionStatus.OK,
                            changed_state=before != after, before_hash=before, after_hash=after)

    def type_text(self, text: str, query: ElementQuery | None = None) -> ActionResult:
        auto = self._uia()
        before = self.inspect_desktop().state_hash
        try:
            if query is not None:
                control, count = self._resolve_control(query)
                if count == 1:
                    control.SetFocus()
            auto.SendKeys(text, waitTime=0.02)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="a", tool="computer.type",
                                arguments={"length": len(text)}, status=ActionStatus.FAILED, error=str(exc))
        after = self.inspect_desktop().state_hash
        # sanitized: only length recorded, never the typed text
        return ActionResult(action_id="a", tool="computer.type",
                            arguments={"length": len(text)}, status=ActionStatus.OK,
                            changed_state=before != after, before_hash=before, after_hash=after)

    def press_key(self, key: str) -> ActionResult:
        auto = self._uia()
        try:
            auto.SendKeys("{" + key + "}")
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="a", tool="computer.press_key",
                                arguments={"key": key}, status=ActionStatus.FAILED, error=str(exc))
        return ActionResult(action_id="a", tool="computer.press_key",
                            arguments={"key": key}, status=ActionStatus.OK)

    def hotkey(self, *keys: str) -> ActionResult:
        auto = self._uia()
        mapping = {"ctrl": "{Ctrl}", "alt": "{Alt}", "shift": "{Shift}"}
        seq = "".join(mapping.get(k.lower(), k) for k in keys)
        try:
            auto.SendKeys(seq)
        except Exception as exc:  # noqa: BLE001
            return ActionResult(action_id="a", tool="computer.hotkey",
                                arguments={"keys": list(keys)}, status=ActionStatus.FAILED, error=str(exc))
        return ActionResult(action_id="a", tool="computer.hotkey",
                            arguments={"keys": list(keys)}, status=ActionStatus.OK, changed_state=True)

    def wait_for(self, query: ElementQuery, *, timeout: float = 5.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.find_elements(query):
                return True
            time.sleep(0.2)
        return False

    def screenshot(self) -> str | None:
        # interface present; screenshot capture deferred (vision fallback phase)
        return None

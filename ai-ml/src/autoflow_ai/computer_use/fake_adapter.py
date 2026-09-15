"""Deterministic in-memory desktop adapter for hermetic tests.

Simulates a simple Notepad-like application: a window with an editable text
area and a Save button. It lets the full tool-calling + agent + verification
path be tested offline without a real desktop, and supports injecting failure
modes (ambiguity, missing element, stuck state).
"""

from __future__ import annotations

import time

from .models import (
    ActionResult,
    ActionStatus,
    DesktopObservation,
    ElementQuery,
    UIElement,
    WindowInfo,
    desktop_state_hash,
)


class FakeDesktopAdapter:
    name = "fake"

    def __init__(self, *, ambiguous_save: bool = False, missing_editor: bool = False) -> None:
        self._launched = False
        self._text = ""
        self._saved = False
        self._ambiguous_save = ambiguous_save
        self._missing_editor = missing_editor
        self._counter = 0
        self._focused = "document"

    def available(self) -> bool:
        return True

    def _elements(self) -> list[UIElement]:
        if not self._launched:
            return []
        els = []
        if not self._missing_editor:
            els.append(UIElement(element_id="e_edit", role="edit", name="Document",
                                 value=self._text, focused=self._focused == "document"))
        els.append(UIElement(element_id="e_save", role="button", name="Save", enabled=bool(self._text)))
        if self._ambiguous_save:
            els.append(UIElement(element_id="e_save2", role="button", name="Save As", enabled=True))
            els.append(UIElement(element_id="e_save3", role="button", name="Save", enabled=True))
        return els

    def _obs(self) -> DesktopObservation:
        self._counter += 1
        win = "Untitled - Notepad" if self._launched else None
        obs = DesktopObservation(
            observation_id=f"obs_fake{self._counter}",
            active_window=win,
            application="notepad" if self._launched else None,
            windows=(WindowInfo(window_id="w1", title=win or "", active=True),) if win else (),
            visible_elements=tuple(self._elements()),
            focused_element=next((e for e in self._elements() if e.focused), None),
        )
        return obs.model_copy(update={"state_hash": desktop_state_hash(obs)})

    def inspect_desktop(self) -> DesktopObservation:
        return self._obs()

    def list_windows(self) -> list[WindowInfo]:
        return list(self._obs().windows)

    def get_active_window(self) -> WindowInfo | None:
        wins = self._obs().windows
        return wins[0] if wins else None

    def find_window(self, title: str) -> WindowInfo | None:
        for w in self._obs().windows:
            if title.lower() in w.title.lower():
                return w
        return None

    def focus_window(self, title: str) -> ActionResult:
        found = self.find_window(title)
        return ActionResult(
            action_id="a_focus", tool="computer.focus_window",
            arguments={"title": title},
            status=ActionStatus.OK if found else ActionStatus.NOT_FOUND,
        )

    def launch_application(self, executable: str) -> ActionResult:
        self._launched = True
        return ActionResult(action_id="a_launch", tool="computer.launch_application",
                            arguments={"executable": executable}, status=ActionStatus.OK,
                            changed_state=True)

    def find_elements(self, query: ElementQuery) -> list[UIElement]:
        return [e for e in self._elements() if e.matches(role=query.role, name=query.name,
                                                          automation_id=query.automation_id)]

    def inspect_element(self, query: ElementQuery) -> UIElement | None:
        matches = self.find_elements(query)
        return matches[0] if len(matches) == 1 else None

    def click(self, query: ElementQuery) -> ActionResult:
        before = self._obs().state_hash
        matches = self.find_elements(query)
        if len(matches) == 0:
            return ActionResult(action_id="a_click", tool="computer.click",
                                arguments=query.model_dump(mode="json"), status=ActionStatus.NOT_FOUND)
        if len(matches) > 1:
            return ActionResult(action_id="a_click", tool="computer.click",
                                arguments=query.model_dump(mode="json"), status=ActionStatus.AMBIGUOUS,
                                detail=f"{len(matches)} matches")
        el = matches[0]
        if el.role == "button" and "save" in el.name.lower():
            self._saved = True
        after = self._obs().state_hash
        return ActionResult(action_id="a_click", tool="computer.click",
                            arguments=query.model_dump(mode="json"), status=ActionStatus.OK,
                            changed_state=before != after, before_hash=before, after_hash=after)

    def type_text(self, text: str, query: ElementQuery | None = None) -> ActionResult:
        before = self._obs().state_hash
        if self._missing_editor:
            return ActionResult(action_id="a_type", tool="computer.type", arguments={"len": len(text)},
                                status=ActionStatus.NOT_FOUND)
        self._text += text
        after = self._obs().state_hash
        # arguments are sanitized: we record length, never the raw text
        return ActionResult(action_id="a_type", tool="computer.type",
                            arguments={"length": len(text)}, status=ActionStatus.OK,
                            changed_state=before != after, before_hash=before, after_hash=after)

    def press_key(self, key: str) -> ActionResult:
        return ActionResult(action_id="a_key", tool="computer.press_key",
                            arguments={"key": key}, status=ActionStatus.OK)

    def hotkey(self, *keys: str) -> ActionResult:
        if [k.lower() for k in keys] == ["ctrl", "s"]:
            self._saved = True
            return ActionResult(action_id="a_hotkey", tool="computer.hotkey",
                                arguments={"keys": list(keys)}, status=ActionStatus.OK, changed_state=True)
        return ActionResult(action_id="a_hotkey", tool="computer.hotkey",
                            arguments={"keys": list(keys)}, status=ActionStatus.OK)

    def wait_for(self, query: ElementQuery, *, timeout: float = 5.0) -> bool:
        return bool(self.find_elements(query))

    def screenshot(self) -> str | None:
        return None

    # test helpers
    @property
    def text(self) -> str:
        return self._text

    @property
    def saved(self) -> bool:
        return self._saved

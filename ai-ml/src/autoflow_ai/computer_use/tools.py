"""Register safe computer tools into the EXISTING ToolRegistry.

Only low/medium-risk semantic tools are registered. Destructive/shell tools
(close_window/delete/shutdown/execute_shell/...) are deliberately NOT registered
so they can never be called. Each tool delegates to a ComputerAdapter and
returns a structured, secret-sanitized result.
"""

from __future__ import annotations

from typing import Any

from ..runtime.registry import ToolExecutionError, ToolRegistry
from ..schemas.enums import RiskClass
from ..schemas.tools import ToolDefinition
from .adapter import ComputerAdapter
from .errors import AmbiguousTarget, UnsafeOperation
from .models import ActionStatus, ElementQuery

# Tools that must never be registered/available in this phase.
BLOCKED_TOOLS = frozenset(
    {
        "computer.close_window",
        "computer.delete",
        "computer.shutdown",
        "computer.restart",
        "computer.install",
        "computer.execute_shell",
    }
)


def _q(args: dict) -> ElementQuery:
    return ElementQuery(
        role=args.get("role"),
        name=args.get("name"),
        automation_id=args.get("automation_id"),
        window=args.get("window"),
    )


def register_computer_tools(registry: ToolRegistry, adapter: ComputerAdapter) -> None:
    """Register the safe computer tool set backed by ``adapter``."""

    def _obj(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}

    # -- inspect_desktop (LOW) ----------------------------------------------
    def _inspect(_args: dict) -> dict:
        obs = adapter.inspect_desktop()
        return {
            "active_window": obs.active_window,
            "window_count": len(obs.windows),
            "element_count": len(obs.visible_elements),
            "state_hash": obs.state_hash,
            "summary": obs.summary(),
        }

    registry.register(
        ToolDefinition(name="computer.inspect_desktop", description="Inspect desktop state (semantic).",
                       input_schema=_obj({}), risk_class=RiskClass.LOW,
                       permission_scope="computer:read", idempotent=True),
        _inspect,
    )

    # -- list_windows (LOW) --------------------------------------------------
    def _windows(_args: dict) -> dict:
        return {"windows": [w.model_dump(mode="json") for w in adapter.list_windows()]}

    registry.register(
        ToolDefinition(name="computer.list_windows", description="List open windows.",
                       input_schema=_obj({}), risk_class=RiskClass.LOW,
                       permission_scope="computer:read", idempotent=True),
        _windows,
    )

    # -- focus_window (LOW) --------------------------------------------------
    def _focus(args: dict) -> dict:
        res = adapter.focus_window(args["title"])
        if res.status != ActionStatus.OK:
            raise ToolExecutionError("focus_failed", res.error or res.status.value)
        return res.model_dump(mode="json")

    registry.register(
        ToolDefinition(name="computer.focus_window", description="Focus a window by title.",
                       input_schema=_obj({"title": {"type": "string"}}, ["title"]),
                       risk_class=RiskClass.LOW, permission_scope="computer:read"),
        _focus,
    )

    # -- find_element (LOW) --------------------------------------------------
    def _find(args: dict) -> dict:
        els = adapter.find_elements(_q(args))
        return {"count": len(els), "elements": [e.model_dump(mode="json") for e in els[:20]]}

    registry.register(
        ToolDefinition(name="computer.find_element", description="Find semantic UI elements.",
                       input_schema=_obj({"role": {"type": "string"}, "name": {"type": "string"},
                                          "automation_id": {"type": "string"}, "window": {"type": "string"}}),
                       risk_class=RiskClass.LOW, permission_scope="computer:read", idempotent=True),
        _find,
    )

    # -- launch_application (MEDIUM, allowlisted) ---------------------------
    # Allowlist is enforced HERE (tool layer) so the safety property holds for
    # every adapter, not only the real Windows one.
    _ALLOWED_APPS = {"notepad.exe", "notepad", "winword.exe", "calc.exe", "calc"}

    def _launch(args: dict) -> dict:
        from pathlib import Path as _Path

        key = _Path(args["executable"]).name.lower()
        if key not in _ALLOWED_APPS:
            raise ToolExecutionError("unsafe_operation", f"application not on allowlist: {args['executable']}")
        try:
            res = adapter.launch_application(args["executable"])
        except UnsafeOperation as exc:
            raise ToolExecutionError("unsafe_operation", str(exc)) from exc
        if res.status != ActionStatus.OK:
            raise ToolExecutionError("launch_failed", res.error or res.status.value)
        return res.model_dump(mode="json")

    registry.register(
        ToolDefinition(name="computer.launch_application", description="Launch an allowlisted application.",
                       input_schema=_obj({"executable": {"type": "string"}}, ["executable"]),
                       risk_class=RiskClass.MEDIUM, permission_scope="computer:launch"),
        _launch,
    )

    # -- click (MEDIUM) ------------------------------------------------------
    def _click(args: dict) -> dict:
        res = adapter.click(_q(args))
        if res.status == ActionStatus.AMBIGUOUS:
            raise ToolExecutionError("ambiguous_target", res.detail or "multiple matches")
        if res.status == ActionStatus.NOT_FOUND:
            raise ToolExecutionError("element_not_found", "no matching element")
        if res.status != ActionStatus.OK:
            raise ToolExecutionError("click_failed", res.error or res.status.value)
        return res.model_dump(mode="json")

    registry.register(
        ToolDefinition(name="computer.click", description="Click a semantic control.",
                       input_schema=_obj({"role": {"type": "string"}, "name": {"type": "string"},
                                          "automation_id": {"type": "string"}, "window": {"type": "string"}}),
                       risk_class=RiskClass.MEDIUM, permission_scope="computer:interact"),
        _click,
    )

    # -- type (MEDIUM) -------------------------------------------------------
    def _type(args: dict) -> dict:
        text = args["text"]
        query = _q(args) if (args.get("role") or args.get("name")) else None
        res = adapter.type_text(text, query)
        if res.status == ActionStatus.NOT_FOUND:
            raise ToolExecutionError("element_not_found", "no editable target")
        if res.status != ActionStatus.OK:
            raise ToolExecutionError("type_failed", res.error or res.status.value)
        # result already sanitized (length only); never echo the text
        return res.model_dump(mode="json")

    registry.register(
        ToolDefinition(name="computer.type", description="Type text into the focused/target control.",
                       input_schema=_obj({"text": {"type": "string"}, "role": {"type": "string"},
                                          "name": {"type": "string"}, "window": {"type": "string"}}, ["text"]),
                       risk_class=RiskClass.MEDIUM, permission_scope="computer:interact"),
        _type,
    )

    # -- press_key (MEDIUM) --------------------------------------------------
    def _press(args: dict) -> dict:
        return adapter.press_key(args["key"]).model_dump(mode="json")

    registry.register(
        ToolDefinition(name="computer.press_key", description="Press a single key.",
                       input_schema=_obj({"key": {"type": "string"}}, ["key"]),
                       risk_class=RiskClass.MEDIUM, permission_scope="computer:interact"),
        _press,
    )

    # -- hotkey (MEDIUM) -----------------------------------------------------
    def _hotkey(args: dict) -> dict:
        keys = args["keys"]
        if not isinstance(keys, list):
            raise ToolExecutionError("invalid_arguments", "keys must be a list")
        return adapter.hotkey(*keys).model_dump(mode="json")

    registry.register(
        ToolDefinition(name="computer.hotkey", description="Send a hotkey combination.",
                       input_schema=_obj({"keys": {"type": "array"}}, ["keys"]),
                       risk_class=RiskClass.MEDIUM, permission_scope="computer:interact"),
        _hotkey,
    )

    # -- wait_for (LOW) ------------------------------------------------------
    def _wait(args: dict) -> dict:
        ok = adapter.wait_for(_q(args), timeout=float(args.get("timeout", 5.0)))
        return {"found": ok}

    registry.register(
        ToolDefinition(name="computer.wait_for", description="Wait (bounded) for an element.",
                       input_schema=_obj({"role": {"type": "string"}, "name": {"type": "string"},
                                          "window": {"type": "string"}, "timeout": {"type": "number"}}),
                       risk_class=RiskClass.LOW, permission_scope="computer:read", idempotent=True),
        _wait,
    )

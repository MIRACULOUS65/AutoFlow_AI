"""Register safe browser tools into the EXISTING ToolRegistry.

Read + mutation tools are registered; high-risk browser actions (purchase,
financial, security settings) are NOT registered. Navigation is restricted to
local URLs by the adapter. Fill values are sanitized (length only) in results.
"""

from __future__ import annotations

from ..runtime.registry import ToolExecutionError, ToolRegistry
from ..schemas.enums import RiskClass
from ..schemas.tools import ToolDefinition
from .browser import BrowserAdapter
from .models import ActionStatus


def register_browser_tools(registry: ToolRegistry, adapter: BrowserAdapter) -> None:
    def _obj(props, required=()):
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}

    def _launch(_a):
        r = adapter.launch()
        if r.status != ActionStatus.OK:
            raise ToolExecutionError("launch_failed", r.error or r.status.value)
        return r.model_dump(mode="json")

    registry.register(
        ToolDefinition(name="browser.launch", description="Launch a headless browser.",
                       input_schema=_obj({}), risk_class=RiskClass.LOW,
                       permission_scope="browser:read"),
        _launch,
    )

    def _navigate(a):
        r = adapter.navigate(a["url"])
        if r.status == ActionStatus.UNSAFE:
            raise ToolExecutionError("unsafe_operation", r.error or "non-local navigation blocked")
        if r.status != ActionStatus.OK:
            raise ToolExecutionError("navigate_failed", r.error or r.status.value)
        return r.model_dump(mode="json")

    registry.register(
        ToolDefinition(name="browser.navigate", description="Navigate to a LOCAL url.",
                       input_schema=_obj({"url": {"type": "string"}}, ["url"]),
                       risk_class=RiskClass.LOW, permission_scope="browser:read"),
        _navigate,
    )

    def _set_content(a):
        return adapter.set_content(a["html"]).model_dump(mode="json")

    registry.register(
        ToolDefinition(name="browser.set_content", description="Set local page HTML (test lab).",
                       input_schema=_obj({"html": {"type": "string"}}, ["html"]),
                       risk_class=RiskClass.LOW, permission_scope="browser:read"),
        _set_content,
    )

    def _find(a):
        return {"count": adapter.find(a["selector"])}

    registry.register(
        ToolDefinition(name="browser.find", description="Count matching elements.",
                       input_schema=_obj({"selector": {"type": "string"}}, ["selector"]),
                       risk_class=RiskClass.LOW, permission_scope="browser:read", idempotent=True),
        _find,
    )

    def _read(a):
        return {"text": adapter.read_text(a["selector"])}

    registry.register(
        ToolDefinition(name="browser.read_text", description="Read element text.",
                       input_schema=_obj({"selector": {"type": "string"}}, ["selector"]),
                       risk_class=RiskClass.LOW, permission_scope="browser:read", idempotent=True),
        _read,
    )

    def _fill(a):
        r = adapter.fill(a["selector"], a["value"])
        if r.status == ActionStatus.NOT_FOUND:
            raise ToolExecutionError("element_not_found", a["selector"])
        if r.status != ActionStatus.OK:
            raise ToolExecutionError("fill_failed", r.error or r.status.value)
        return r.model_dump(mode="json")  # value already sanitized to length

    registry.register(
        ToolDefinition(name="browser.fill", description="Fill a form field (mutation).",
                       input_schema=_obj({"selector": {"type": "string"}, "value": {"type": "string"}},
                                         ["selector", "value"]),
                       risk_class=RiskClass.MEDIUM, permission_scope="browser:interact"),
        _fill,
    )

    def _click(a):
        r = adapter.click(a["selector"])
        if r.status == ActionStatus.AMBIGUOUS:
            raise ToolExecutionError("ambiguous_target", r.detail or "multiple matches")
        if r.status == ActionStatus.NOT_FOUND:
            raise ToolExecutionError("element_not_found", a["selector"])
        if r.status != ActionStatus.OK:
            raise ToolExecutionError("click_failed", r.error or r.status.value)
        return r.model_dump(mode="json")

    registry.register(
        ToolDefinition(name="browser.click", description="Click an element (mutation).",
                       input_schema=_obj({"selector": {"type": "string"}}, ["selector"]),
                       risk_class=RiskClass.MEDIUM, permission_scope="browser:interact"),
        _click,
    )

    def _wait(a):
        return {"found": adapter.wait_for(a["selector"], timeout=float(a.get("timeout", 5.0)))}

    registry.register(
        ToolDefinition(name="browser.wait_for", description="Wait (bounded) for a selector.",
                       input_schema=_obj({"selector": {"type": "string"}, "timeout": {"type": "number"}},
                                         ["selector"]),
                       risk_class=RiskClass.LOW, permission_scope="browser:read", idempotent=True),
        _wait,
    )

    def _close(_a):
        return adapter.close().model_dump(mode="json")

    registry.register(
        ToolDefinition(name="browser.close", description="Close the browser.",
                       input_schema=_obj({}), risk_class=RiskClass.LOW, permission_scope="browser:read"),
        _close,
    )

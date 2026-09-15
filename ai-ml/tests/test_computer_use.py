"""Phase 7 computer-use unit + adversarial tests (hermetic, FakeDesktopAdapter)."""

from __future__ import annotations

import pytest

from autoflow_ai.computer_use import (
    ActionStatus,
    ElementQuery,
    FakeDesktopAdapter,
    UIElement,
    desktop_state_hash,
)
from autoflow_ai.computer_use.tools import BLOCKED_TOOLS, register_computer_tools
from autoflow_ai.computer_use.errors import UnsafeOperation
from autoflow_ai.computer_use.windows_adapter import WindowsUIAutomationAdapter
from autoflow_ai.runtime.registry import ToolRegistry
from autoflow_ai.runtime.tool_calling import ToolCallingController
from autoflow_ai.schemas.tools import ToolCallRequest

pytestmark = pytest.mark.integration

COMPUTER_PERMS = frozenset({"computer:read", "computer:launch", "computer:interact"})


@pytest.fixture
def wired():
    adapter = FakeDesktopAdapter()
    reg = ToolRegistry()
    register_computer_tools(reg, adapter)
    return adapter, reg


def _call(reg, tool, args):
    return reg.execute(
        ToolCallRequest(tool_call_id="tcall_x", tool_name=tool, arguments=args,
                        execution_id="exec_x", step_id="step_x")
    )


# ---- tool registration -----------------------------------------------------


def test_safe_tools_registered(wired):
    _adapter, reg = wired
    for t in ("computer.inspect_desktop", "computer.list_windows", "computer.focus_window",
              "computer.find_element", "computer.launch_application", "computer.click",
              "computer.type", "computer.press_key", "computer.hotkey", "computer.wait_for"):
        assert reg.has(t), t


def test_destructive_tools_not_registered(wired):
    _adapter, reg = wired
    for t in BLOCKED_TOOLS:
        assert not reg.has(t), f"{t} must not be registered"


# ---- UI discovery ----------------------------------------------------------


def test_launch_then_find_button(wired):
    adapter, reg = wired
    _call(reg, "computer.launch_application", {"executable": "notepad.exe"})
    _call(reg, "computer.type", {"text": "hi"})
    r = _call(reg, "computer.find_element", {"role": "button", "name": "Save"})
    assert r.ok
    assert r.output["count"] >= 1


def test_type_then_click_save_changes_state(wired):
    adapter, reg = wired
    _call(reg, "computer.launch_application", {"executable": "notepad.exe"})
    _call(reg, "computer.type", {"text": "hello"})
    r = _call(reg, "computer.click", {"role": "button", "name": "Save"})
    assert r.ok
    assert adapter.saved is True


def test_ambiguous_target_not_guessed():
    adapter = FakeDesktopAdapter(ambiguous_save=True)
    reg = ToolRegistry()
    register_computer_tools(reg, adapter)
    _call(reg, "computer.launch_application", {"executable": "notepad.exe"})
    _call(reg, "computer.type", {"text": "x"})
    r = _call(reg, "computer.click", {"name": "Save"})
    assert not r.ok
    assert r.error_type == "ambiguous_target"


def test_missing_element_not_found():
    adapter = FakeDesktopAdapter()
    reg = ToolRegistry()
    register_computer_tools(reg, adapter)
    _call(reg, "computer.launch_application", {"executable": "notepad.exe"})
    r = _call(reg, "computer.click", {"role": "button", "name": "DoesNotExist"})
    assert not r.ok
    assert r.error_type == "element_not_found"


def test_type_into_missing_editor_fails():
    adapter = FakeDesktopAdapter(missing_editor=True)
    reg = ToolRegistry()
    register_computer_tools(reg, adapter)
    _call(reg, "computer.launch_application", {"executable": "notepad.exe"})
    r = _call(reg, "computer.type", {"text": "x"})
    assert not r.ok
    assert r.error_type == "element_not_found"


# ---- state / hash ----------------------------------------------------------


def test_observation_serializable(wired):
    adapter, _reg = wired
    obs = adapter.inspect_desktop()
    import json

    json.dumps(obs.model_dump(mode="json"))


def test_state_hash_changes_on_change(wired):
    adapter, reg = wired
    _call(reg, "computer.launch_application", {"executable": "notepad.exe"})
    h1 = adapter.inspect_desktop().state_hash
    _call(reg, "computer.type", {"text": "abc"})
    h2 = adapter.inspect_desktop().state_hash
    assert h1 != h2


def test_state_hash_stable_when_unchanged(wired):
    adapter, _reg = wired
    a = desktop_state_hash(adapter.inspect_desktop())
    b = desktop_state_hash(adapter.inspect_desktop())
    assert a == b


# ---- element model ---------------------------------------------------------


def test_element_matches_semantic():
    el = UIElement(element_id="e1", role="button", name="Save Document")
    assert el.matches(role="button", name="save")
    assert not el.matches(role="edit")


# ---- launch allowlist (real adapter, no launch performed) ------------------


def test_windows_adapter_launch_allowlist_rejects_arbitrary():
    adapter = WindowsUIAutomationAdapter()
    with pytest.raises(UnsafeOperation):
        adapter.launch_application("evil.exe")
    with pytest.raises(UnsafeOperation):
        adapter.launch_application("C:/Windows/System32/cmd.exe")


# ============================ ToolCallingController =========================


def _controller(reg, perms=COMPUTER_PERMS, approvals=frozenset()):
    return ToolCallingController(registry=reg, permissions=perms, approvals=approvals)


def test_controller_executes_authorized(wired):
    _adapter, reg = wired
    ctrl = _controller(reg)
    result, trace = ctrl.call(tool_name="computer.inspect_desktop", arguments={},
                              execution_id="exec_x", step_id="step_x")
    assert result.ok
    assert trace["ok"]


def test_controller_rejects_unknown_tool(wired):
    _adapter, reg = wired
    ctrl = _controller(reg)
    result, _ = ctrl.call(tool_name="computer.telekinesis", arguments={},
                          execution_id="exec_x", step_id="step_x")
    assert not result.ok
    assert result.error_type == "unauthorized"


def test_controller_rejects_blocked_tool(wired):
    _adapter, reg = wired
    ctrl = _controller(reg)
    result, _ = ctrl.call(tool_name="computer.execute_shell", arguments={"cmd": "rm -rf /"},
                          execution_id="exec_x", step_id="step_x")
    assert not result.ok


def test_controller_permission_denied(wired):
    _adapter, reg = wired
    ctrl = _controller(reg, perms=frozenset())  # no computer perms
    result, _ = ctrl.call(tool_name="computer.click", arguments={"name": "Save"},
                          execution_id="exec_x", step_id="step_x")
    assert not result.ok
    assert result.error_type == "unauthorized"


def test_controller_redacts_secrets_in_trace(wired):
    _adapter, reg = wired
    ctrl = _controller(reg)
    _result, trace = ctrl.call(
        tool_name="computer.type",
        arguments={"text": "my password is nvapi-abcdef1234567890", "api_key": "sk-secret1234567890"},
        execution_id="exec_x", step_id="step_x",
    )
    s = str(trace)
    assert "nvapi-abcdef1234567890" not in s
    assert "sk-secret1234567890" not in s
    assert "***redacted***" in s or "<text len=" in s


def test_controller_high_risk_requires_approval():
    from autoflow_ai.schemas.tools import ToolDefinition
    from autoflow_ai.schemas.enums import RiskClass

    reg = ToolRegistry()
    reg.register(
        ToolDefinition(name="computer.send", description="send", risk_class=RiskClass.HIGH,
                       permission_scope="computer:interact", requires_approval=True,
                       input_schema={"type": "object", "properties": {}, "required": []}),
        lambda a: {"sent": True},
    )
    ctrl = ToolCallingController(registry=reg, permissions=frozenset({"computer:interact"}))
    result, _ = ctrl.call(tool_name="computer.send", arguments={}, execution_id="exec_hr", step_id="step_x")
    assert not result.ok
    assert result.error_type == "approval_required"
    # with approval granted -> allowed
    ctrl2 = ToolCallingController(registry=reg, permissions=frozenset({"computer:interact"}),
                                  approvals=frozenset({"computer.send"}))
    result2, _ = ctrl2.call(tool_name="computer.send", arguments={}, execution_id="exec_hr", step_id="step_x")
    assert result2.ok


# ---- adversarial -----------------------------------------------------------


def test_adversarial_arbitrary_executable_via_tool(wired):
    _adapter, reg = wired
    # launch tool exists but adapter allowlist blocks arbitrary exe
    r = _call(reg, "computer.launch_application", {"executable": "cmd.exe"})
    assert not r.ok
    assert r.error_type == "unsafe_operation"


def test_adversarial_type_secret_not_persisted(wired):
    adapter, reg = wired
    _call(reg, "computer.launch_application", {"executable": "notepad.exe"})
    r = _call(reg, "computer.type", {"text": "password=hunter2 nvapi-secretkey123456"})
    assert r.ok
    # result records only length, never the secret text
    assert "hunter2" not in str(r.output)
    assert "nvapi-secretkey123456" not in str(r.output)
    assert r.output["arguments"]["length"] == len("password=hunter2 nvapi-secretkey123456")


def test_adversarial_malformed_click_args(wired):
    _adapter, reg = wired
    # unknown argument -> schema rejection
    r = _call(reg, "computer.click", {"bogus": 1})
    assert not r.ok
    assert r.error_type == "invalid_arguments"

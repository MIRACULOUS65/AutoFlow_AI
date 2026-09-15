"""CP7/CP8: stress (deterministic), false-success tracking, and real-model path."""

from __future__ import annotations

import pytest

from autoflow_ai.computer_use import (
    FakeBrowserAdapter,
    WFStatus,
    WFStep,
    WorkflowExecution,
    AutonomyLoop,
)
from autoflow_ai.computer_use.browser_tools import register_browser_tools
from autoflow_ai.runtime.registry import ToolRegistry
from autoflow_ai.runtime.tool_calling import ToolCallingController

pytestmark = pytest.mark.integration

BROWSER_PERMS = frozenset({"browser:read", "browser:interact"})


def _run_one() -> WorkflowExecution:
    b = FakeBrowserAdapter()
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    ctrl = ToolCallingController(registry=reg, permissions=BROWSER_PERMS)
    wf = WorkflowExecution(execution_id="exec_s", goal="submit", steps=[
        WFStep("browser.launch", {}),
        WFStep("browser.fill", {"selector": "#name", "value": "X"}),
        WFStep("browser.click", {"selector": "#submit"}),
    ])
    AutonomyLoop(controller=ctrl, observe=lambda: b.name + ("|s" if b.submitted else "|o")).run(wf)
    wf.final_result["submitted"] = b.submitted
    return wf


def test_stress_100_deterministic_runs():
    """100 deterministic workflow runs; track success + FALSE success.

    False success = workflow reported SUCCESS but the real side effect
    (submitted) did not happen. This must be zero.
    """

    success = 0
    false_success = 0
    for _ in range(100):
        wf = _run_one()
        if wf.status == WFStatus.SUCCESS:
            success += 1
            if not wf.final_result.get("submitted"):
                false_success += 1
    assert success == 100
    assert false_success == 0  # never claim success without the real effect


def test_stress_failure_injection_runs():
    """Runs where submit is missing must fail safely every time (no false success)."""

    false_success = 0
    for _ in range(30):
        b = FakeBrowserAdapter(missing_submit=True)
        reg = ToolRegistry()
        register_browser_tools(reg, b)
        ctrl = ToolCallingController(registry=reg, permissions=BROWSER_PERMS)
        wf = WorkflowExecution(execution_id="exec_f", goal="submit", steps=[
            WFStep("browser.launch", {}),
            WFStep("browser.click", {"selector": "#submit"}),
        ])
        AutonomyLoop(controller=ctrl, observe=lambda: "same").run(wf)
        if wf.status == WFStatus.SUCCESS and not b.submitted:
            false_success += 1
    assert false_success == 0


# ---- CP8: real-model reasoning path (fail-closed) --------------------------


def test_real_model_action_reasoning_fail_closed():
    """The model path must fail closed: malformed/unavailable model output never
    becomes an executable action. We exercise the gateway seam with the local
    deterministic provider (hermetic) and confirm a structured response or a
    safe fallback — never a raw executable command."""

    from autoflow_ai.model_gateway import build_gateway
    from autoflow_ai.model_gateway.config import GatewayConfig
    from autoflow_ai.schemas.enums import ModelRole
    from autoflow_ai.schemas.models import ModelRequest

    _reg, router = build_gateway(GatewayConfig(providers=[], timeout_seconds=10, max_retries=1))
    req = ModelRequest(request_id="mreq_cu", required_role=ModelRole.EXECUTOR,
                       required_capabilities={"reasoning": True})
    resp = router.generate(req, prompt="What is the next safe UI action?")
    # structured output present and no raw shell/command leaked
    assert resp.text is not None or resp.structured_output is not None
    payload = (resp.text or "") + str(resp.structured_output or {})
    assert "rm -rf" not in payload and "subprocess" not in payload

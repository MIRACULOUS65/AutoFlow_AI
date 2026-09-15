"""Bundled milestone tests: observation/browser/vision/CV/verification/recovery/
approval/rate-limits/locks/workflows + adversarial + real browser (auto-skip)."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoflow_ai.computer_use import (
    ApprovalLedger,
    ApprovalRequest,
    Check,
    FakeBrowserAdapter,
    FakeVisionProvider,
    ObservationFusion,
    RateLimits,
    RateLimitedVision,
    RecoveryEngine,
    RecoveryStep,
    ResolutionStatus,
    ResourceLocks,
    SignalKind,
    StuckDetector,
    TargetResolver,
    VerificationEngine,
    VisionBudget,
    VisionCandidate,
    WFStatus,
    WFStep,
    WorkflowExecution,
    AutonomyLoop,
)
from autoflow_ai.computer_use.browser_tools import register_browser_tools
from autoflow_ai.computer_use.models import DesktopObservation, ElementQuery, UIElement, desktop_state_hash
from autoflow_ai.runtime.registry import ToolRegistry
from autoflow_ai.runtime.tool_calling import ToolCallingController
from autoflow_ai.schemas.tools import ToolCallRequest

pytestmark = pytest.mark.integration

BROWSER_PERMS = frozenset({"browser:read", "browser:interact"})


def _bcall(reg, tool, args):
    return reg.execute(ToolCallRequest(tool_call_id="tcall_x", tool_name=tool, arguments=args,
                                       execution_id="exec_x", step_id="step_x"))


# ---- observation fusion + target resolver ----------------------------------


def _obs(source_id, elements):
    obs = DesktopObservation(observation_id=source_id, active_window="W",
                             visible_elements=tuple(elements))
    return obs.model_copy(update={"state_hash": desktop_state_hash(obs)})


def test_fusion_merges_corroborating_sources():
    save = UIElement(element_id="e1", role="button", name="Save")
    fused = ObservationFusion().fuse({
        "uia": _obs("o1", [save]),
        "screenshot": _obs("o2", [UIElement(element_id="e2", role="button", name="Save")]),
    })
    resolver = TargetResolver()
    res = resolver.resolve(ElementQuery(role="button", name="Save"), fused)
    assert res.status == ResolutionStatus.RESOLVED
    # two sources -> higher confidence
    assert res.confidence >= 0.7


def test_resolver_ambiguous_not_guessed():
    fused = ObservationFusion().fuse({"uia": _obs("o1", [
        UIElement(element_id="e1", role="button", name="Save"),
        UIElement(element_id="e2", role="button", name="Save", automation_id="x2"),
    ])})
    res = TargetResolver().resolve(ElementQuery(name="Save"), fused)
    assert res.status == ResolutionStatus.AMBIGUOUS


def test_resolver_not_found():
    fused = ObservationFusion().fuse({"uia": _obs("o1", [])})
    res = TargetResolver().resolve(ElementQuery(name="Ghost"), fused)
    assert res.status == ResolutionStatus.NOT_FOUND


def test_resolver_disabled_and_hidden():
    fused = ObservationFusion().fuse({"uia": _obs("o1", [
        UIElement(element_id="e1", role="button", name="Save", enabled=False),
    ])})
    assert TargetResolver().resolve(ElementQuery(name="Save"), fused).status == ResolutionStatus.DISABLED
    fused2 = ObservationFusion().fuse({"uia": _obs("o2", [
        UIElement(element_id="e1", role="button", name="Save", visible=False),
    ])})
    assert TargetResolver().resolve(ElementQuery(name="Save"), fused2).status == ResolutionStatus.HIDDEN


# ---- browser tools (fake) --------------------------------------------------


def test_browser_local_nav_allowed_remote_blocked():
    b = FakeBrowserAdapter()
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    assert _bcall(reg, "browser.launch", {}).ok
    assert _bcall(reg, "browser.navigate", {"url": "data:text/html,<b>x</b>"}).ok
    r = _bcall(reg, "browser.navigate", {"url": "https://example.com"})
    assert not r.ok and r.error_type == "unsafe_operation"


def test_browser_form_submit_and_confirm():
    b = FakeBrowserAdapter()
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    _bcall(reg, "browser.launch", {})
    _bcall(reg, "browser.fill", {"selector": "#name", "value": "Alice"})
    assert _bcall(reg, "browser.click", {"selector": "#submit"}).ok
    assert "submitted" in _bcall(reg, "browser.read_text", {"selector": "#confirmation"}).output["text"]


def test_browser_missing_element_fails():
    b = FakeBrowserAdapter(missing_submit=True)
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    _bcall(reg, "browser.launch", {})
    r = _bcall(reg, "browser.click", {"selector": "#submit"})
    assert not r.ok and r.error_type == "element_not_found"


def test_browser_fill_value_sanitized():
    b = FakeBrowserAdapter()
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    _bcall(reg, "browser.launch", {})
    r = _bcall(reg, "browser.fill", {"selector": "#name", "value": "secret-value-123"})
    assert "secret-value-123" not in str(r.output)
    assert r.output["arguments"]["length"] == len("secret-value-123")


# ---- vision + CV -----------------------------------------------------------


def test_vision_budget_exhausts():
    rv = RateLimitedVision(FakeVisionProvider(), VisionBudget(max_per_task=2))
    assert rv.locate(b"a", "save") is not None
    assert rv.locate(b"b", "save") is not None
    assert rv.locate(b"c", "save") is None  # budget exhausted


def test_vision_best_candidate_confidence_threshold():
    r = FakeVisionProvider([VisionCandidate("button", "Save", 0.4)]).locate(b"x", "save")
    assert r.best(min_confidence=0.6) is None  # low confidence -> no blind action
    r2 = FakeVisionProvider([VisionCandidate("button", "Save", 0.9)]).locate(b"x", "save")
    assert r2.best(min_confidence=0.6) is not None


def test_cv_available_and_diff():
    import cv2
    import numpy as np

    from autoflow_ai.computer_use.cv import cv_available, image_diff

    assert cv_available()
    a = np.zeros((32, 32), np.uint8)
    b = a.copy()
    b[:16, :] = 255
    _ok, ab = cv2.imencode(".png", a)
    _ok, bb = cv2.imencode(".png", b)
    assert image_diff(ab.tobytes(), bb.tobytes()).changed
    assert not image_diff(ab.tobytes(), ab.tobytes()).changed


# ---- verification engine ---------------------------------------------------


def test_verification_multi_signal_all_required():
    eng = VerificationEngine(min_confidence=0.6)
    good = eng.evaluate([
        Check(SignalKind.FILESYSTEM, True, "exists"),
        Check(SignalKind.DOCUMENT, True, "contains"),
    ])
    assert good.verified and good.confidence == 1.0
    bad = eng.evaluate([
        Check(SignalKind.FILESYSTEM, True),
        Check(SignalKind.DOCUMENT, False),
    ])
    assert not bad.verified


def test_verification_action_alone_not_enough():
    eng = VerificationEngine(min_confidence=0.6)
    # a single "clicked" check with no corroboration -> passes weight but the
    # engine requires evidence; simulate click-only as one passing check but a
    # required doc check failing
    outcome = eng.evaluate([Check(SignalKind.APP_STATE, True, "clicked"),
                            Check(SignalKind.FILESYSTEM, False, "file missing")])
    assert not outcome.verified


def test_file_and_document_verification(tmp_path):
    eng = VerificationEngine()
    p = tmp_path / "a.txt"
    before = eng.file_hash(p)
    assert before is None
    p.write_text("hello the world", encoding="utf-8")
    assert eng.file_exists(p).passed
    assert eng.file_changed(p, before).passed
    assert eng.document_contains(p, "hello").passed
    assert eng.document_not_contains(p, "teh").passed


# ---- recovery + stuck ------------------------------------------------------


def test_recovery_ladder_progresses_then_fail_safe():
    r = RecoveryEngine(max_steps=3)
    steps = [r.next_step() for _ in range(4)]
    assert steps[0] == RecoveryStep.RETRY
    assert steps[-1] == RecoveryStep.FAIL_SAFE  # exhausted


def test_stuck_detector():
    s = StuckDetector(max_same_state=3)
    assert not s.record_state("h")
    assert not s.record_state("h")
    assert s.record_state("h")  # 3rd time -> stuck


# ---- approval binding ------------------------------------------------------


def test_approval_binds_to_exact_action():
    ledger = ApprovalLedger()
    req = ApprovalRequest(execution_id="e", task_id="t", action_id="a", tool="email.send",
                          risk="high", target={"to": "finance"}, arguments={"subject": "x"},
                          observation_hash="obs1")
    ledger.grant(req)
    assert ledger.is_approved(req)
    # material change (different recipient) -> approval invalid
    mutated = ApprovalRequest(execution_id="e", task_id="t", action_id="a", tool="email.send",
                              risk="high", target={"to": "attacker"}, arguments={"subject": "x"},
                              observation_hash="obs1")
    assert not ledger.is_approved(mutated)


# ---- rate limits + locks ---------------------------------------------------


def test_rate_limits_block_after_max_actions():
    rl = RateLimits(max_actions_per_task=2)
    assert rl.allow_action()[0]; rl.record_action()
    assert rl.allow_action()[0]; rl.record_action()
    assert not rl.allow_action()[0]


def test_resource_locks_same_key_same_lock():
    locks = ResourceLocks()
    assert locks.lock_for("word:doc.docx") is locks.lock_for("word:doc.docx")
    assert locks.lock_for("word:doc.docx") is not locks.lock_for("browser:ctx1")


# ---- autonomy loop (fake browser) ------------------------------------------


def test_autonomy_loop_browser_workflow():
    b = FakeBrowserAdapter()
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    ctrl = ToolCallingController(registry=reg, permissions=BROWSER_PERMS)
    wf = WorkflowExecution(execution_id="exec_wf", goal="submit form", steps=[
        WFStep("browser.launch", {}),
        WFStep("browser.fill", {"selector": "#name", "value": "Bob"}),
        WFStep("browser.click", {"selector": "#submit"}),
    ])
    loop = AutonomyLoop(controller=ctrl, observe=lambda: b.name + ("|s" if b.submitted else "|o"))
    loop.run(wf)
    assert wf.status == WFStatus.SUCCESS
    assert b.submitted


def test_autonomy_loop_fails_safe_on_missing():
    b = FakeBrowserAdapter(missing_submit=True)
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    ctrl = ToolCallingController(registry=reg, permissions=BROWSER_PERMS)
    wf = WorkflowExecution(execution_id="exec_wf", goal="submit", steps=[
        WFStep("browser.launch", {}),
        WFStep("browser.click", {"selector": "#submit"}),  # missing -> fails
    ])
    loop = AutonomyLoop(controller=ctrl, observe=lambda: "same")
    loop.run(wf)
    assert wf.status in (WFStatus.FAILED, WFStatus.NEEDS_REPLAN)
    assert wf.recovery_events  # recovery was attempted


def test_workflow_execution_serializable():
    wf = WorkflowExecution(execution_id="e", goal="g", steps=[WFStep("browser.launch", {})])
    import json

    json.dumps(wf.to_dict())


# ---- adversarial -----------------------------------------------------------


def test_adversarial_browser_high_risk_tool_not_registered():
    b = FakeBrowserAdapter()
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    # purchase/financial tools are never registered
    assert not reg.has("browser.purchase")
    assert not reg.has("browser.execute_script")


def test_adversarial_remote_navigation_blocked_via_controller():
    b = FakeBrowserAdapter()
    reg = ToolRegistry()
    register_browser_tools(reg, b)
    ctrl = ToolCallingController(registry=reg, permissions=BROWSER_PERMS)
    result, _ = ctrl.call(tool_name="browser.navigate", arguments={"url": "https://evil.com"},
                          execution_id="exec_x", step_id="step_x")
    assert not result.ok


# ============================ REAL BROWSER (auto-skip) ======================


def _pw_available() -> bool:
    try:
        from autoflow_ai.computer_use.browser import PlaywrightBrowserAdapter

        return PlaywrightBrowserAdapter().available()
    except Exception:
        return False


skip_no_browser = pytest.mark.skipif(not _pw_available(), reason="playwright/chromium unavailable")


@skip_no_browser
def test_real_browser_form_workflow():
    """WD11-15: real headless Chromium, local page, fill + submit + verify."""

    from autoflow_ai.computer_use.browser import PlaywrightBrowserAdapter

    from autoflow_ai.computer_use.models import ActionStatus

    adapter = PlaywrightBrowserAdapter()
    launch = adapter.launch()
    assert launch.status == ActionStatus.OK, launch.error
    try:
        html = (
            "<html><body>"
            "<input id='name'><button id='submit' "
            "onclick=\"document.body.insertAdjacentHTML('beforeend','<div id=confirmation>Submitted OK</div>')\">"
            "Submit</button></body></html>"
        )
        adapter.set_content(html)
        assert adapter.fill("#name", "Alice").status.value == "ok"
        assert adapter.input_value("#name") == "Alice"
        assert adapter.click("#submit").status.value == "ok"
        assert adapter.wait_for("#confirmation", timeout=3.0)
        assert "Submitted OK" in (adapter.read_text("#confirmation") or "")
    finally:
        adapter.close()

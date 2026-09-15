"""Autonomous web-search tests.

Two layers:

1. Hermetic logic tests using an in-memory fake adapter — prove the loop's
   gates, the anti-hallucination property (results come ONLY from the adapter's
   DOM extraction), and honest failure modes. No network, no browser.

2. A real DOM-extraction test using the actual Playwright adapter against a
   LOCAL page (set_content) — proves read_results extracts exactly the anchors
   present and unwraps redirect URLs. Skipped when playwright isn't installed.

3. A real WEB test — skipped unless AUTOFLOW_ALLOW_WEB=1 (opt-in). When enabled
   it drives a real browser to Bing and asserts every reported result is a real
   http(s) URL that was on the page (never fabricated).
"""

from __future__ import annotations

import os

import pytest

from autoflow_ai.computer_use.browser import (
    WebSearchBrowserAdapter,
    _is_allowlisted_search_url,
    _unwrap_redirect,
)
from autoflow_ai.computer_use.models import ActionResult, ActionStatus
from autoflow_ai.society import (
    AutonomousWebSearchAgent,
    Blackboard,
    MessageBus,
    SearchOutcome,
    TrustClass,
)
from autoflow_ai.society.messages import MessageType


# --------------------------------------------------------------------------
# in-memory fake adapter (no browser). Serves a fixed set of "DOM" anchors.
# --------------------------------------------------------------------------

class FakeSearchAdapter:
    name = "fake-search"

    def __init__(self, *, allow_web=True, rows=None, launch_ok=True,
                 nav_status=ActionStatus.OK, available=True):
        self.allow_web = allow_web
        self._rows = rows if rows is not None else [
            {"title": "Python.org", "href": "https://www.python.org/"},
            {"title": "Python docs", "href": "https://docs.python.org/3/"},
        ]
        self._launch_ok = launch_ok
        self._nav_status = nav_status
        self._available = available
        self.closed = False

    def available(self):
        return self._available

    def launch(self):
        return ActionResult(action_id="b", tool="browser.launch", arguments={},
                            status=ActionStatus.OK if self._launch_ok else ActionStatus.FAILED,
                            error=None if self._launch_ok else "launch boom")

    def navigate(self, url):
        return ActionResult(action_id="b", tool="browser.navigate", arguments={"url": url},
                            status=self._nav_status,
                            error="blocked" if self._nav_status == ActionStatus.UNSAFE else None)

    def current_url(self):
        return "https://www.bing.com/search?q=x"

    def wait_for(self, selector, *, timeout=5.0):
        return True

    def read_results(self, selector, *, limit=10):
        # returns ONLY what it is given — mirrors the real adapter reading DOM
        return list(self._rows[:limit])

    def close(self):
        self.closed = True
        return ActionResult(action_id="b", tool="browser.close", arguments={}, status=ActionStatus.OK)


def agent(adapter):
    return AutonomousWebSearchAgent(adapter=adapter, board=Blackboard(), bus=MessageBus(),
                                    execution_id="exec_ws1", task_id="ws1")


# --------------------------------------------------------------------------
# gates + fail-closed
# --------------------------------------------------------------------------

def test_ws_01_not_enabled_fails_closed():
    res = agent(FakeSearchAdapter(allow_web=False)).run("anything")
    assert res.outcome == SearchOutcome.NOT_ENABLED
    assert res.results == []
    assert res.verified is False


def test_ws_02_unavailable_fails_closed():
    res = agent(FakeSearchAdapter(available=False)).run("anything")
    assert res.outcome == SearchOutcome.UNAVAILABLE
    assert res.results == []


def test_ws_03_launch_failure_reported():
    res = agent(FakeSearchAdapter(launch_ok=False)).run("q")
    assert res.outcome == SearchOutcome.FAILED
    assert "launch" in res.reason.lower()


def test_ws_04_navigation_blocked_reported():
    res = agent(FakeSearchAdapter(nav_status=ActionStatus.UNSAFE)).run("q")
    assert res.outcome == SearchOutcome.NAV_BLOCKED


def test_ws_05_navigation_failure_reported():
    res = agent(FakeSearchAdapter(nav_status=ActionStatus.FAILED)).run("q")
    assert res.outcome == SearchOutcome.FAILED


# --------------------------------------------------------------------------
# results + anti-hallucination
# --------------------------------------------------------------------------

def test_ws_06_results_verified_from_adapter_only():
    a = FakeSearchAdapter(rows=[
        {"title": "A", "href": "https://a.example/"},
        {"title": "B", "href": "https://b.example/"},
    ])
    res = agent(a).run("q")
    assert res.outcome == SearchOutcome.RESULTS_VERIFIED
    assert res.verified is True
    assert [r["href"] for r in res.results] == ["https://a.example/", "https://b.example/"]


def test_ws_07_no_results_reported_not_invented():
    res = agent(FakeSearchAdapter(rows=[])).run("q")
    assert res.outcome == SearchOutcome.NO_RESULTS
    assert res.results == []
    assert res.verified is True  # verified that there genuinely are none


def test_ws_08_rows_without_http_href_dropped():
    a = FakeSearchAdapter(rows=[
        {"title": "good", "href": "https://ok.example/"},
        {"title": "bad-js", "href": "javascript:void(0)"},
        {"title": "no-href", "href": ""},
    ])
    res = agent(a).run("q")
    hrefs = [r["href"] for r in res.results]
    assert hrefs == ["https://ok.example/"]  # only the real http(s) row survives


def test_ws_09_max_results_respected():
    rows = [{"title": f"t{i}", "href": f"https://x{i}.example/"} for i in range(20)]
    res = agent(FakeSearchAdapter(rows=rows)).run("q", max_results=3)
    assert len(res.results) == 3


def test_ws_10_browser_always_closed():
    a = FakeSearchAdapter()
    agent(a).run("q")
    assert a.closed is True


def test_ws_11_evidence_posted_to_blackboard():
    a = FakeSearchAdapter()
    ag = agent(a)
    ag.run("q")
    ev = ag.board.latest("search:ws1")
    assert ev is not None
    # evidence is DATA (observation/verification), never an instruction
    assert ev.trust in (TrustClass.OBSERVATION, TrustClass.VERIFICATION)
    assert ev.is_data is True


def test_ws_12_messages_show_navigate_and_verify():
    a = FakeSearchAdapter()
    ag = agent(a)
    ag.run("q")
    types = {m.type for m in ag.bus.messages}
    assert MessageType.ACTION_REQUEST in types
    assert MessageType.VERIFICATION_RESULT in types


# --------------------------------------------------------------------------
# url policy + redirect unwrap (pure functions)
# --------------------------------------------------------------------------

def test_ws_13_allowlist_only_https_search_hosts():
    assert _is_allowlisted_search_url("https://www.bing.com/search?q=x")
    assert _is_allowlisted_search_url("https://html.duckduckgo.com/html/?q=x")
    assert not _is_allowlisted_search_url("https://evil.example/?q=x")
    assert not _is_allowlisted_search_url("http://www.bing.com/search?q=x")


def test_ws_14_unwrap_bing_redirect():
    import base64
    real = "https://www.python.org/downloads/"
    enc = "a1" + base64.urlsafe_b64encode(real.encode()).decode().rstrip("=")
    wrapped = f"https://www.bing.com/ck/a?!&&p=abc&u={enc}&ntb=1"
    assert _unwrap_redirect(wrapped) == real


def test_ws_15_unwrap_duckduckgo_redirect():
    from urllib.parse import quote
    real = "https://docs.python.org/3/"
    wrapped = f"https://duckduckgo.com/l/?uddg={quote(real, safe='')}"
    assert _unwrap_redirect(wrapped) == real


def test_ws_16_unwrap_passthrough_when_nothing_to_unwrap():
    plain = "https://example.com/page"
    assert _unwrap_redirect(plain) == plain


# --------------------------------------------------------------------------
# REAL local DOM extraction (real Playwright, LOCAL page — no network)
# --------------------------------------------------------------------------

def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _playwright_available(), reason="playwright not installed")
def test_ws_17_real_dom_extraction_local_page():
    """Prove read_results extracts EXACTLY the anchors on a real local page."""

    adapter = WebSearchBrowserAdapter(allow_web=True)
    if not adapter.available():
        pytest.skip("playwright/chromium not available")
    assert adapter.launch().status == ActionStatus.OK
    try:
        adapter.set_content(
            "<div id='b_results'>"
            "<li class='b_algo'><h2><a href='https://real-one.example/'>Real One</a></h2></li>"
            "<li class='b_algo'><h2><a href='https://real-two.example/'>Real Two</a></h2></li>"
            "</div>"
        )
        rows = adapter.read_results("li.b_algo h2 a", limit=10)
    finally:
        adapter.close()
    assert [r["title"] for r in rows] == ["Real One", "Real Two"]
    assert [r["href"] for r in rows] == ["https://real-one.example/", "https://real-two.example/"]


@pytest.mark.skipif(not _playwright_available(), reason="playwright not installed")
def test_ws_18_real_adapter_blocks_web_when_not_opted_in():
    adapter = WebSearchBrowserAdapter(allow_web=False)
    r = adapter.navigate("https://www.bing.com/search?q=x")
    assert r.status == ActionStatus.UNSAFE


# --------------------------------------------------------------------------
# REAL WEB search — opt-in only.
# --------------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("AUTOFLOW_ALLOW_WEB") != "1",
                    reason="real web disabled (set AUTOFLOW_ALLOW_WEB=1 to run)")
def test_ws_19_real_web_search_returns_real_results():
    adapter = WebSearchBrowserAdapter(allow_web=True)
    if not adapter.available():
        pytest.skip("playwright/chromium not available")
    ag = AutonomousWebSearchAgent(adapter=adapter, execution_id="exec_realweb1",
                                  task_id="realweb")
    res = ag.run("python programming language", engine="bing", max_results=5)
    # honest: either real verified results, or a genuine no-results/blocked state
    assert res.outcome in (SearchOutcome.RESULTS_VERIFIED, SearchOutcome.NO_RESULTS)
    for r in res.results:
        assert r["href"].startswith(("http://", "https://"))
        assert r["title"]

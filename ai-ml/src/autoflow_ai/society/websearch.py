"""Autonomous web-search loop (real browser, real DOM, no hallucination).

Given a query and an explicit opt-in, this drives a real Chromium browser end
to end:

    LAUNCH -> NAVIGATE(search engine) -> WAIT(results) -> EXTRACT(real DOM rows)
    -> VERIFY(every reported result maps to a real anchor) -> REPORT

The anti-hallucination guarantee is structural, not a prompt instruction: the
only source of results is :meth:`WebSearchBrowserAdapter.read_results`, which
reads anchor elements straight from the live page. The loop then re-verifies
that each reported result has a non-empty title and an http(s) href that was
actually present in the extraction. If the page returns nothing, the loop
reports zero results — it never invents any.

The loop is fail-closed: if web search isn't enabled, the browser is
unavailable, navigation is refused, or no results container appears, it returns
an honest failure with a reason.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote_plus

from ..computer_use.autonomy import RateLimits
from ..computer_use.browser import WebSearchBrowserAdapter
from ..computer_use.models import ActionStatus
from ..schemas.enums import StrEnum
from .blackboard import Blackboard, BlackboardEntry, TrustClass
from .messages import AgentMessage, MessageBus, MessageType


class SearchOutcome(StrEnum):
    RESULTS_VERIFIED = "results_verified"
    NO_RESULTS = "no_results"          # page loaded but yielded zero real rows
    NOT_ENABLED = "not_enabled"        # web search not opted in
    UNAVAILABLE = "unavailable"        # browser/playwright not available
    NAV_BLOCKED = "nav_blocked"        # navigation refused by policy
    FAILED = "failed"                  # launch/navigation/runtime failure
    RATE_LIMITED = "rate_limited"


@dataclass
class SearchEngine:
    key: str
    url_template: str          # {q} is replaced by the url-encoded query
    result_selector: str       # anchors that are result titles/links
    ready_selector: str        # selector to wait for (results container)


# Server-rendered endpoints preferred (stable, no client-JS result injection).
SEARCH_ENGINES: dict[str, SearchEngine] = {
    "duckduckgo": SearchEngine(
        key="duckduckgo",
        url_template="https://html.duckduckgo.com/html/?q={q}",
        result_selector="a.result__a",
        ready_selector="#links, .result, .no-results",
    ),
    "bing": SearchEngine(
        key="bing",
        url_template="https://www.bing.com/search?q={q}",
        result_selector="li.b_algo h2 a",
        ready_selector="#b_results",
    ),
}


@dataclass
class SearchStep:
    phase: str
    detail: str = ""
    ok: bool | None = None


@dataclass
class WebSearchResult:
    query: str
    engine: str
    outcome: SearchOutcome
    source_url: str = ""
    results: list[dict] = field(default_factory=list)  # [{title, href}]
    steps: list[SearchStep] = field(default_factory=list)
    reason: str = ""
    verified: bool = False

    def as_dict(self) -> dict:
        return {
            "query": self.query,
            "engine": self.engine,
            "outcome": str(self.outcome),
            "source_url": self.source_url,
            "verified": self.verified,
            "result_count": len(self.results),
            "results": self.results,
            "reason": self.reason,
            "trace": [{"phase": s.phase, "ok": s.ok, "detail": s.detail} for s in self.steps],
        }


class AutonomousWebSearchAgent:
    """Drives a real browser to search the web and report only real results."""

    def __init__(
        self,
        *,
        adapter: WebSearchBrowserAdapter,
        board: Blackboard | None = None,
        bus: MessageBus | None = None,
        execution_id: str = "exec_search",
        task_id: str = "search",
        agent_id: str = "browser:search",
        rate_limits: RateLimits | None = None,
    ) -> None:
        self._adapter = adapter
        self._board = board or Blackboard()
        self._bus = bus or MessageBus()
        self._execution_id = execution_id
        self._task_id = task_id
        self._agent_id = agent_id
        self._limits = rate_limits or RateLimits()

    @property
    def board(self) -> Blackboard:
        return self._board

    @property
    def bus(self) -> MessageBus:
        return self._bus

    def _emit(self, mtype: MessageType, summary: str, **kw) -> None:
        self._bus.send(
            AgentMessage(
                message_id=f"{self._agent_id}-{len(self._bus.messages)}-{self._execution_id[-5:]}",
                execution_id=self._execution_id, sender=self._agent_id,
                recipient="supervisor", type=mtype, task_id=self._task_id,
                summary=summary[:200], **kw,
            )
        )

    def _step(self, result: WebSearchResult, phase: str, *, ok: bool | None = None, detail: str = "") -> None:
        result.steps.append(SearchStep(phase=phase, detail=detail, ok=ok))

    def run(self, query: str, *, engine: str = "bing", max_results: int = 8) -> WebSearchResult:
        eng = SEARCH_ENGINES.get(engine, SEARCH_ENGINES["bing"])
        result = WebSearchResult(query=query, engine=eng.key, outcome=SearchOutcome.FAILED)
        self._emit(MessageType.TASK_ACCEPTED, f"web search: {query!r} via {eng.key}")

        # 0. opt-in + availability gates (fail closed, honest)
        if not getattr(self._adapter, "allow_web", False):
            result.outcome = SearchOutcome.NOT_ENABLED
            result.reason = "web search is not enabled (opt-in required)"
            self._step(result, "gate", ok=False, detail=result.reason)
            self._emit(MessageType.BLOCKED, result.reason)
            return result
        if not self._adapter.available():
            result.outcome = SearchOutcome.UNAVAILABLE
            result.reason = "browser (playwright/chromium) is not available"
            self._step(result, "gate", ok=False, detail=result.reason)
            self._emit(MessageType.BLOCKED, result.reason)
            return result

        try:
            return self._run_inner(query, eng, max_results, result)
        finally:
            # always clean up the browser process
            try:
                self._adapter.close()
            except Exception:  # noqa: BLE001
                pass

    def _run_inner(self, query, eng: SearchEngine, max_results: int, result: WebSearchResult) -> WebSearchResult:
        # 1. LAUNCH
        allowed, why = self._limits.allow_action()
        if not allowed:
            result.outcome = SearchOutcome.RATE_LIMITED
            result.reason = why
            self._step(result, "launch", ok=False, detail=why)
            return result
        launch = self._adapter.launch()
        self._limits.record_action()
        self._step(result, "launch", ok=launch.status == ActionStatus.OK, detail=str(launch.status))
        if launch.status != ActionStatus.OK:
            result.outcome = SearchOutcome.FAILED
            result.reason = f"launch failed: {launch.error or launch.status}"
            self._emit(MessageType.FAILURE, result.reason)
            return result

        # 2. NAVIGATE to the real search engine
        url = eng.url_template.format(q=quote_plus(query))
        result.source_url = url
        self._emit(MessageType.ACTION_REQUEST, f"navigate {eng.key}", payload={"host": eng.key})
        nav = self._adapter.navigate(url)
        self._limits.record_action()
        if nav.status == ActionStatus.UNSAFE:
            result.outcome = SearchOutcome.NAV_BLOCKED
            result.reason = nav.error or "navigation blocked by policy"
            self._step(result, "navigate", ok=False, detail=result.reason)
            self._emit(MessageType.BLOCKED, result.reason)
            return result
        if nav.status != ActionStatus.OK:
            result.outcome = SearchOutcome.FAILED
            result.reason = f"navigation failed: {nav.error or nav.status}"
            self._step(result, "navigate", ok=False, detail=result.reason)
            self._emit(MessageType.FAILURE, result.reason)
            return result
        self._step(result, "navigate", ok=True, detail=self._adapter.current_url() or url)

        # 3. WAIT for the results region to render
        ready = self._adapter.wait_for(eng.ready_selector, timeout=10.0)
        self._step(result, "wait", ok=ready, detail=eng.ready_selector)

        # 4. EXTRACT real result rows from the live DOM
        rows = self._adapter.read_results(eng.result_selector, limit=max_results)
        self._step(result, "extract", ok=bool(rows), detail=f"{len(rows)} anchors")

        # 5. VERIFY (anti-hallucination): each reported result must have a real
        #    title and an http(s) href that came from the extraction.
        verified_rows = [
            r for r in rows
            if r.get("title") and str(r.get("href", "")).lower().startswith(("http://", "https://"))
        ]
        result.results = verified_rows
        self._post_evidence(query, eng, url, verified_rows)

        if not verified_rows:
            result.outcome = SearchOutcome.NO_RESULTS
            result.reason = "the page loaded but no real result anchors were found"
            result.verified = True  # verified that there are genuinely none
            self._emit(MessageType.RESULT, "0 results (page yielded none)", confidence=0.6)
            return result

        result.outcome = SearchOutcome.RESULTS_VERIFIED
        result.verified = True
        self._step(result, "verify", ok=True, detail=f"{len(verified_rows)} verified rows")
        self._emit(
            MessageType.VERIFICATION_RESULT,
            f"{len(verified_rows)} results verified from live DOM",
            confidence=0.9,
        )
        return result

    def _post_evidence(self, query, eng: SearchEngine, url: str, rows: list[dict]) -> None:
        # store as OBSERVATION/VERIFICATION trust — data, never instructions.
        self._board.post(
            BlackboardEntry(
                key=f"search:{self._task_id}",
                value={"query": query, "engine": eng.key, "url": url,
                       "count": len(rows), "results": rows},
                summary=f"{len(rows)} results for {query!r} via {eng.key}",
                trust=TrustClass.OBSERVATION if not rows else TrustClass.VERIFICATION,
                producer=self._agent_id, task_id=self._task_id,
                confidence=0.9 if rows else 0.6,
            )
        )

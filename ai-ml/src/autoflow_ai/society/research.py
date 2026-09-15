"""Provenance-backed web research (grounded, traceable, no hallucination).

The research loop reuses the real :class:`AutonomousWebSearchAgent`: it drives a
real browser to a search engine, extracts REAL result rows from the live DOM,
and optionally deep-reads a top result page for observed passages. Every fact
it reports carries provenance (source URL, title, retrieval timestamp, the
extracted passage, and a provenance id) and an epistemic label:

* DIRECTLY_OBSERVED — text/link that literally appeared on a real page;
* DERIVED — a summary computed from directly-observed content;
* INFERRED — a model interpretation (allowed, but flagged as such);
* UNKNOWN — not found; the loop says so instead of inventing an answer.

The model (when enabled) may choose the query and summarize observed content,
but it can never manufacture a source: the finding's evidence list is built only
from what the browser actually extracted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..schemas.enums import StrEnum
from .blackboard import Blackboard, BlackboardEntry, TrustClass
from .websearch import AutonomousWebSearchAgent, SearchOutcome


class EpistemicLabel(StrEnum):
    DIRECTLY_OBSERVED = "directly_observed"
    DERIVED = "derived"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class ResearchOutcome(StrEnum):
    GROUNDED = "grounded"          # real evidence gathered
    NO_EVIDENCE = "no_evidence"    # searched, found nothing usable (honest)
    NOT_ENABLED = "not_enabled"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


@dataclass
class ResearchFact:
    statement: str
    label: EpistemicLabel
    source_url: str = ""
    source_title: str = ""
    passage: str = ""
    provenance_id: str = ""
    retrieved_at: str = ""


@dataclass
class ResearchReport:
    objective: str
    outcome: ResearchOutcome
    facts: list[ResearchFact] = field(default_factory=list)
    source_url: str = ""
    reason: str = ""
    relevant: bool = True          # results judged relevant to the objective
    mean_relevance: float = 0.0    # token-overlap relevance (grounded, not model memory)

    @property
    def grounded(self) -> bool:
        return self.outcome == ResearchOutcome.GROUNDED and bool(self.facts)

    def observed_facts(self) -> list[ResearchFact]:
        return [f for f in self.facts if f.label == EpistemicLabel.DIRECTLY_OBSERVED]

    def as_dict(self) -> dict:
        return {
            "objective": self.objective,
            "outcome": str(self.outcome),
            "source_url": self.source_url,
            "reason": self.reason,
            "relevant": self.relevant,
            "mean_relevance": self.mean_relevance,
            "fact_count": len(self.facts),
            "directly_observed": len(self.observed_facts()),
            "facts": [
                {
                    "statement": f.statement,
                    "label": str(f.label),
                    "source_url": f.source_url,
                    "source_title": f.source_title,
                    "passage": f.passage[:280],
                    "provenance_id": f.provenance_id,
                    "retrieved_at": f.retrieved_at,
                }
                for f in self.facts
            ],
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WebResearchAgent:
    """Runs grounded research and produces provenance-backed, labeled findings."""

    def __init__(
        self,
        *,
        adapter,
        board: Blackboard | None = None,
        execution_id: str = "exec_research",
        task_id: str = "research",
        agent_id: str = "research:web",
    ) -> None:
        self._adapter = adapter
        self._board = board or Blackboard()
        self._execution_id = execution_id
        self._task_id = task_id
        self._agent_id = agent_id

    @property
    def board(self) -> Blackboard:
        return self._board

    def research(
        self,
        objective: str,
        *,
        engine: str = "bing",
        max_results: int = 6,
        deep_read: bool = False,
    ) -> ResearchReport:
        report = ResearchReport(objective=objective, outcome=ResearchOutcome.FAILED)

        search = AutonomousWebSearchAgent(
            adapter=self._adapter, board=self._board,
            execution_id=self._execution_id, task_id=f"{self._task_id}:search",
            agent_id=self._agent_id,
        )
        sr = search.run(objective, engine=engine, max_results=max_results)
        report.source_url = sr.source_url

        if sr.outcome == SearchOutcome.NOT_ENABLED:
            report.outcome = ResearchOutcome.NOT_ENABLED
            report.reason = sr.reason
            return report
        if sr.outcome == SearchOutcome.UNAVAILABLE:
            report.outcome = ResearchOutcome.UNAVAILABLE
            report.reason = sr.reason
            return report
        if sr.outcome not in (SearchOutcome.RESULTS_VERIFIED, SearchOutcome.NO_RESULTS):
            report.outcome = ResearchOutcome.FAILED
            report.reason = sr.reason
            return report

        # Relevance validation (grounded, token-overlap; never model memory).
        # A real result is not automatically a relevant result.
        from .evidence_broker import validate_search_relevance

        verdict = validate_search_relevance(objective, sr.results)
        report.relevant = verdict.relevant
        report.mean_relevance = verdict.mean_relevance

        # Each real result row is a DIRECTLY_OBSERVED fact (title + real URL).
        ts = _now()
        for i, row in enumerate(sr.results):
            fact = ResearchFact(
                statement=row["title"],
                label=EpistemicLabel.DIRECTLY_OBSERVED,
                source_url=row["href"], source_title=row["title"],
                passage=row["title"], provenance_id=f"obs_{i:03d}", retrieved_at=ts,
            )
            report.facts.append(fact)
            self._post_fact(fact)

        # Optional deep read of the top result page for an observed passage.
        if deep_read and sr.results and getattr(self._adapter, "allow_deep_read", False):
            top = sr.results[0]
            nav = self._adapter.navigate(top["href"])
            from ..computer_use.models import ActionStatus

            if nav.status == ActionStatus.OK:
                page = self._adapter.read_page_text(max_chars=1200)
                if page and page.get("text"):
                    fact = ResearchFact(
                        statement=f"Opened top result: {page['title']}",
                        label=EpistemicLabel.DIRECTLY_OBSERVED,
                        source_url=page["url"], source_title=page["title"],
                        passage=page["text"], provenance_id="obs_page_0",
                        retrieved_at=_now(),
                    )
                    report.facts.append(fact)
                    self._post_fact(fact)

        try:
            self._adapter.close()
        except Exception:  # noqa: BLE001
            pass

        if not report.facts:
            report.outcome = ResearchOutcome.NO_EVIDENCE
            report.reason = "search returned no usable results"
            return report
        report.outcome = ResearchOutcome.GROUNDED
        rel = "relevant" if report.relevant else "LOW-RELEVANCE (consider reformulating)"
        report.reason = (f"{len(report.facts)} facts from live browser evidence; "
                         f"{rel} (mean={report.mean_relevance})")
        return report

    def _post_fact(self, fact: ResearchFact) -> None:
        # research facts are EXTERNAL_DATA (web content) — never instructions.
        self._board.post(
            BlackboardEntry(
                key=f"research:{self._task_id}:{fact.provenance_id}",
                value={"statement": fact.statement, "label": str(fact.label),
                       "source_url": fact.source_url, "passage": fact.passage[:512],
                       "retrieved_at": fact.retrieved_at},
                summary=f"{fact.label}: {fact.statement}"[:512],
                trust=TrustClass.EXTERNAL_DATA, producer=self._agent_id,
                task_id=self._task_id, evidence_refs=(fact.provenance_id,),
                confidence=0.9 if fact.label == EpistemicLabel.DIRECTLY_OBSERVED else 0.5,
            )
        )

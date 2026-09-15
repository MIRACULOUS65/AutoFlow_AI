"""Mission simulation + real-time trace + side-by-side sim-vs-live comparison.

* MissionTracer — a secret-free real-time event stream (SUPERVISOR/RAG/PLANNER/
  AGENT/VERIFY/APPROVAL/CLEANUP/FINAL). An optional sink callback prints events
  as they happen (the development/debug view). Never emits secrets or private
  chain-of-thought.

* simulate_mission — runs the flagship over a fully DETERMINISTIC environment
  (in-memory Gmail DOM + a real local .docx), so the whole agent loop can be
  inspected before any real desktop/browser/live-model use.

* compare_sim_vs_live — runs the same objective in simulation and (when
  permitted) live, then compares plan/actions/deviations/verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..schemas.enums import StrEnum


class TraceStage(StrEnum):
    SUPERVISOR = "supervisor"
    RAG = "rag"
    PLANNER = "planner"
    RESEARCH = "research"
    DOCUMENT = "document"
    COMPUTER = "computer"
    BROWSER = "browser"
    GMAIL = "gmail"
    VERIFY = "verify"
    APPROVAL = "approval"
    CLEANUP = "cleanup"
    FINAL = "final"


_SECRETS = ("api_key", "authorization", "bearer", "token", "password", "secret",
            "cookie", "nvapi-", "ms-cfaabe")


def _clean(text: str) -> str:
    low = (text or "").lower()
    for s in _SECRETS:
        if s in low:
            return "[redacted]"
    return (text or "")[:300]


@dataclass
class TraceEvent:
    stage: TraceStage
    message: str
    detail: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def render(self) -> str:
        d = f" — {_clean(self.detail)}" if self.detail else ""
        return f"[{str(self.stage).upper()}] {_clean(self.message)}{d}"

    def as_dict(self) -> dict:
        return {"stage": str(self.stage), "message": _clean(self.message),
                "detail": _clean(self.detail), "timestamp": self.timestamp}


class MissionTracer:
    """Collects secret-free trace events; prints them live if a sink is set."""

    def __init__(self, *, sink=None) -> None:
        self._events: list[TraceEvent] = []
        self._sink = sink

    def emit(self, stage: TraceStage, message: str, detail: str = "") -> None:
        ev = TraceEvent(stage=stage, message=message, detail=detail)
        self._events.append(ev)
        if self._sink is not None:
            self._sink(ev.render())

    def from_bus(self, bus) -> None:
        """Ingest a MessageBus trace into stage events (secret-free)."""

        from .messages import MessageType

        stage_map = {
            MessageType.TASK_REQUEST: TraceStage.SUPERVISOR,
            MessageType.ACTION_REQUEST: TraceStage.DOCUMENT,
            MessageType.RESULT: TraceStage.DOCUMENT,
            MessageType.VERIFICATION_RESULT: TraceStage.VERIFY,
            MessageType.REPLAN_REQUEST: TraceStage.SUPERVISOR,
            MessageType.HANDOFF: TraceStage.SUPERVISOR,
            MessageType.FAILURE: TraceStage.VERIFY,
            MessageType.BLOCKED: TraceStage.VERIFY,
        }
        for m in bus.messages:
            self.emit(stage_map.get(m.type, TraceStage.SUPERVISOR),
                      f"{m.sender} -> {m.recipient} {m.type}", m.summary)

    @property
    def events(self) -> list[TraceEvent]:
        return list(self._events)

    def as_list(self) -> list[dict]:
        return [e.as_dict() for e in self._events]

    def render(self) -> str:
        return "\n".join(e.render() for e in self._events)


# ---------------------------------------------------------------------------
# simulate a full mission over the deterministic environment
# ---------------------------------------------------------------------------


@dataclass
class SimulationResult:
    outcome: str
    complete: bool
    document_verified: bool
    draft_verified: bool
    sent_verified: bool
    agenticity: dict
    trace: list[dict]
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "outcome": self.outcome, "complete": self.complete,
            "document_verified": self.document_verified,
            "draft_verified": self.draft_verified, "sent_verified": self.sent_verified,
            "agenticity": self.agenticity, "reason": self.reason,
            "trace": self.trace,
        }


def simulate_mission(
    *,
    document_prompt: str,
    document_path: str,
    email,
    execution_id: str = "exec_sim",
    auto_approve: bool = True,
    sink=None,
    gmail_adapter=None,
) -> SimulationResult:
    """Run the flagship over a deterministic document environment with a live
    trace. The email transport is pluggable: pass ``gmail_adapter`` to use a
    real adapter (e.g. real SMTP); defaults to the deterministic in-memory
    ``FakeGmailAdapter`` so the loop can be inspected with no network.
    """

    from ..computer_use.gmail import FakeGmailAdapter
    from .flagship import FlagshipWorkflow

    tracer = MissionTracer(sink=sink)
    tracer.emit(TraceStage.SUPERVISOR, "mission received", document_prompt)
    wf = FlagshipWorkflow(
        gmail_adapter=gmail_adapter or FakeGmailAdapter(), auto_approve=auto_approve
    )
    result = wf.run(document_prompt=document_prompt, document_path=document_path,
                    email=email, execution_id=execution_id)

    # replay the supervisor bus into the stage trace, then annotate phases
    if wf.supervisor is not None:
        tracer.from_bus(wf.supervisor.bus)
    tracer.emit(TraceStage.VERIFY, "document verified", str(result.document_verified))
    if result.draft_verified:
        tracer.emit(TraceStage.GMAIL, "draft verified")
    if str(result.outcome) == "awaiting_approval":
        tracer.emit(TraceStage.APPROVAL, "waiting for user approval")
    if result.sent_verified:
        tracer.emit(TraceStage.VERIFY, "sent message independently verified")
    tracer.emit(TraceStage.CLEANUP, "applications closed")
    tracer.emit(TraceStage.FINAL, "VERIFIED" if result.complete else str(result.outcome))

    return SimulationResult(
        outcome=str(result.outcome), complete=result.complete,
        document_verified=result.document_verified, draft_verified=result.draft_verified,
        sent_verified=result.sent_verified, agenticity=result.agenticity,
        trace=tracer.as_list(), reason=result.reason,
    )


# ---------------------------------------------------------------------------
# side-by-side sim vs live
# ---------------------------------------------------------------------------


@dataclass
class SimVsLive:
    sim: dict
    live: dict | None
    deviations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"sim": self.sim, "live": self.live, "deviations": self.deviations}


def compare_sim_vs_live(sim_result: SimulationResult, live_result) -> SimVsLive:
    """Compare a simulated run to a live run (when a live run is available).

    Reports where the live path DIVERGED from simulation (outcome + which
    verification stages differed). Helps diagnose where real UI differs.
    """

    sim = sim_result.as_dict()
    if live_result is None:
        return SimVsLive(sim=sim, live=None, deviations=["live run not available (skipped)"])
    live = live_result.as_dict() if hasattr(live_result, "as_dict") else dict(live_result)
    deviations: list[str] = []
    for key in ("outcome", "document_verified", "draft_verified", "sent_verified"):
        if sim.get(key) != live.get(key):
            deviations.append(f"{key}: sim={sim.get(key)} live={live.get(key)}")
    return SimVsLive(sim=sim, live=live, deviations=deviations)

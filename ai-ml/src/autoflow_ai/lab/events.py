"""Lab event stream + decision/model trace (secret-safe observability).

These structures make model behavior observable WITHOUT leaking API keys or
private chain-of-thought. Only structured summaries, decisions, timing and
validation status are exposed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..schemas.enums import StrEnum


class LabEventType(StrEnum):
    MODEL_REQUEST = "model_request"
    MODEL_STARTED = "model_started"
    MODEL_CHUNK = "model_chunk"          # streaming delta (content only, no CoT)
    MODEL_COMPLETED = "model_completed"
    MODEL_PARSE = "model_parse"
    MODEL_VALIDATION = "model_validation"
    MODEL_REJECTED = "model_rejected"
    FALLBACK = "fallback"


_SECRET_MARKERS = ("api_key", "authorization", "bearer", "token", "password",
                   "secret", "cookie", "nvapi-", "ms-")


def _redact(text: str) -> str:
    """Best-effort redaction so no secret ever appears in a lab event."""

    if not text:
        return text
    lowered = text.lower()
    for marker in _SECRET_MARKERS:
        if marker in lowered:
            return "[redacted]"
    return text[:2000]


@dataclass
class LabEvent:
    type: LabEventType
    provider: str = ""
    model_id: str = ""
    role: str = ""
    detail: str = ""
    latency_ms: int | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict:
        return {
            "type": str(self.type),
            "provider": self.provider,
            "model_id": self.model_id,
            "role": self.role,
            "detail": _redact(self.detail),
            "latency_ms": self.latency_ms,
            "timestamp": self.timestamp,
        }


@dataclass
class ModelTrace:
    """Traceable, secret-free record of a single model decision.

    Captures the "thinking" we are allowed to expose: a decision summary, the
    observations/evidence used, the selected action, how many alternatives were
    considered, confidence/uncertainty, and why it blocked/replanned — never the
    raw private chain-of-thought.
    """

    model_id: str = ""
    provider: str = ""
    role: str = ""
    prompt_id: str = ""
    prompt_version: int = 1
    decision_summary: str = ""
    observations_used: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    selected_action: str | None = None
    alternative_actions_considered_count: int = 0
    confidence: float = 0.0
    uncertainty: float = 0.0
    why_blocked: str = ""
    why_replanned: str = ""
    schema_valid: bool | None = None
    parse_ok: bool | None = None
    latency_ms: int | None = None

    def as_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "role": self.role,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "decision_summary": _redact(self.decision_summary),
            "observations_used": list(self.observations_used),
            "evidence_refs": list(self.evidence_refs),
            "selected_action": self.selected_action,
            "alternatives_considered": self.alternative_actions_considered_count,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "why_blocked": self.why_blocked,
            "why_replanned": self.why_replanned,
            "schema_valid": self.schema_valid,
            "parse_ok": self.parse_ok,
            "latency_ms": self.latency_ms,
        }


class EventSink:
    """Collects lab events; a hook can print them in real time (secret-safe)."""

    def __init__(self, *, on_event=None) -> None:
        self._events: list[LabEvent] = []
        self._on_event = on_event

    def emit(self, event: LabEvent) -> None:
        self._events.append(event)
        if self._on_event is not None:
            self._on_event(event)

    @property
    def events(self) -> list[LabEvent]:
        return list(self._events)

    def as_list(self) -> list[dict]:
        return [e.as_dict() for e in self._events]

"""Model Lab runner: execute benchmark tasks against configured providers.

Reuses the existing model gateway (registry + providers) — no second gateway,
no hardcoded credentials. For each task it builds a strict structured request,
calls the provider, parses + validates the structured output, applies the
task's structural predicate, and records a secret-free result + trace.

A run NEVER executes a side effect. Malformed/timeout/rejected output is
recorded as a failure (fail-closed) — never faked into a pass.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..model_gateway import build_gateway
from ..model_gateway.structured import StructuredOutputError, parse_into
from ..schemas.models import ModelRequest
from .dataset import BenchmarkTask
from .events import EventSink, LabEvent, LabEventType, ModelTrace


@dataclass
class ProviderInfo:
    model_id: str
    provider: str
    provider_model_name: str
    display_name: str
    roles: tuple[str, ...]
    healthy: bool
    is_local: bool


@dataclass
class LabRunResult:
    task_id: str
    kind: str
    model_id: str
    provider: str
    ok: bool                       # task predicate passed
    schema_valid: bool             # structured output present + dict
    parse_ok: bool                 # structured/text parsed without error
    tool_valid: bool | None        # proposed tool in allowlist (when applicable)
    refused: bool | None           # adversarial: action refused/blocked
    latency_ms: int
    reason: str = ""
    error: str | None = None
    trace: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        return d


def _dict_out(response) -> tuple[dict | None, bool]:
    """Return (structured_dict, parse_ok). Tries structured_output, then text JSON."""

    if response.structured_output is not None and isinstance(response.structured_output, dict):
        return response.structured_output, True
    if response.text:
        try:
            import json

            obj = json.loads(response.text)
            if isinstance(obj, dict):
                return obj, True
        except Exception:  # noqa: BLE001
            return None, False
    return None, False


class ModelLab:
    """Runs benchmark tasks against providers and records structural results."""

    def __init__(self, *, config=None, transport=None, stream_transport=None, on_event=None) -> None:
        self._registry, self._router = build_gateway(
            config, transport=transport, stream_transport=stream_transport
        )
        self._sink = EventSink(on_event=on_event)

    # -- discovery -------------------------------------------------------
    def providers(self) -> list[ProviderInfo]:
        out: list[ProviderInfo] = []
        for model in self._registry.models():
            provider = self._registry.provider_for(model.model_id)
            out.append(
                ProviderInfo(
                    model_id=model.model_id,
                    provider=provider.name,
                    provider_model_name=model.provider_model_name,
                    display_name=model.display_name,
                    roles=tuple(str(r) for r in model.roles),
                    healthy=bool(getattr(provider, "health", lambda: True)()),
                    is_local=provider.name == "local-rule",
                )
            )
        return out

    @property
    def events(self) -> list[dict]:
        return self._sink.as_list()

    # -- single task -----------------------------------------------------
    def run_task(self, task: BenchmarkTask, *, model_id: str) -> LabRunResult:
        model, provider = self._registry.get(model_id)
        self._sink.emit(LabEvent(LabEventType.MODEL_REQUEST, provider=provider.name,
                                 model_id=model_id, role=str(task.role), detail=task.task_id))
        request = ModelRequest(
            request_id="mreq_lab",
            required_role=task.role if task.role in model.roles else model.roles[0],
            required_capabilities={"structured_output": True},
            require_structured_output=True,
            max_output_tokens=384,
            temperature=0.0,
        )
        t0 = time.perf_counter()
        self._sink.emit(LabEvent(LabEventType.MODEL_STARTED, provider=provider.name,
                                 model_id=model_id, role=str(task.role)))
        try:
            response = provider.generate(model, request, task.prompt)
        except Exception as exc:  # noqa: BLE001 - any provider failure fails closed
            latency = int((time.perf_counter() - t0) * 1000)
            self._sink.emit(LabEvent(LabEventType.MODEL_REJECTED, provider=provider.name,
                                     model_id=model_id, detail=type(exc).__name__,
                                     latency_ms=latency))
            return LabRunResult(task_id=task.task_id, kind=str(task.kind), model_id=model_id,
                                provider=provider.name, ok=False, schema_valid=False,
                                parse_ok=False, tool_valid=None, refused=None,
                                latency_ms=latency, error=type(exc).__name__,
                                reason="provider error")
        latency = int((time.perf_counter() - t0) * 1000)
        self._sink.emit(LabEvent(LabEventType.MODEL_COMPLETED, provider=provider.name,
                                 model_id=model_id, latency_ms=latency))

        out, parse_ok = _dict_out(response)
        self._sink.emit(LabEvent(LabEventType.MODEL_PARSE, provider=provider.name,
                                 model_id=model_id, detail=f"parse_ok={parse_ok}"))
        schema_valid = out is not None
        if not schema_valid:
            self._sink.emit(LabEvent(LabEventType.MODEL_REJECTED, provider=provider.name,
                                     model_id=model_id, detail="no structured output"))
            return LabRunResult(task_id=task.task_id, kind=str(task.kind), model_id=model_id,
                                provider=provider.name, ok=False, schema_valid=False,
                                parse_ok=parse_ok, tool_valid=None, refused=None,
                                latency_ms=latency, reason="no structured output")

        ok, reason = task.predicate(out)
        tool_valid = None
        if task.allowed_tools:
            tool = out.get("tool") or out.get("proposed_tool")
            tool_valid = tool in task.allowed_tools if tool is not None else False
        refused = None
        if task.adversarial:
            refused, _r = task.predicate(out)  # refusal predicate == ok for adversarial
        self._sink.emit(LabEvent(LabEventType.MODEL_VALIDATION, provider=provider.name,
                                 model_id=model_id, detail=f"ok={ok}"))

        trace = ModelTrace(
            model_id=model_id, provider=provider.name, role=str(task.role),
            prompt_id=task.task_id, decision_summary=(out.get("reasoning_summary")
                                                      or reason)[:200],
            selected_action=(out.get("tool") or out.get("action")),
            confidence=float(out.get("confidence", 0.0) or 0.0),
            schema_valid=schema_valid, parse_ok=parse_ok, latency_ms=latency,
        ).as_dict()

        return LabRunResult(task_id=task.task_id, kind=str(task.kind), model_id=model_id,
                            provider=provider.name, ok=ok, schema_valid=schema_valid,
                            parse_ok=parse_ok, tool_valid=tool_valid, refused=refused,
                            latency_ms=latency, reason=reason, trace=trace)

    # -- batch -----------------------------------------------------------
    def run_benchmark(self, tasks, *, model_id: str) -> list[LabRunResult]:
        return [self.run_task(t, model_id=model_id) for t in tasks]

    def compare(self, tasks, *, model_ids: list[str]) -> dict:
        """Run the SAME tasks against multiple models; return per-model results."""

        return {mid: self.run_benchmark(tasks, model_id=mid) for mid in model_ids}

    def local_model_id(self) -> str | None:
        for info in self.providers():
            if info.is_local:
                return info.model_id
        models = self._registry.models()
        return models[0].model_id if models else None

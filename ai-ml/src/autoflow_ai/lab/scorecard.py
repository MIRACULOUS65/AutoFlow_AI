"""Model scorecard: aggregate LabRunResults into comparable metrics.

Metrics are computed structurally from the run results (never textual
similarity), so NVIDIA vs Qwen vs deterministic can be compared on the same
tasks. Adversarial tasks contribute to hallucination/false-completion rates:
a model that "acts" on a no-Save-button or unsaved-file trap is penalized.
"""

from __future__ import annotations

from dataclasses import dataclass, field


def _pct(n: int, d: int) -> float:
    return round(n / d, 4) if d else 0.0


def _percentile(values: list[int], p: float) -> int:
    if not values:
        return 0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


@dataclass
class ModelScorecard:
    model_id: str
    provider: str
    total: int = 0
    schema_valid: int = 0
    task_success: int = 0
    tool_considered: int = 0
    tool_valid: int = 0
    adversarial_total: int = 0
    adversarial_refused: int = 0
    provider_errors: int = 0
    latencies_ms: list[int] = field(default_factory=list)

    @property
    def schema_validity(self) -> float:
        return _pct(self.schema_valid, self.total)

    @property
    def task_success_rate(self) -> float:
        return _pct(self.task_success, self.total)

    @property
    def tool_validity(self) -> float:
        return _pct(self.tool_valid, self.tool_considered)

    @property
    def hallucination_rate(self) -> float:
        # fraction of adversarial traps where the model FAILED to refuse
        if not self.adversarial_total:
            return 0.0
        return _pct(self.adversarial_total - self.adversarial_refused, self.adversarial_total)

    @property
    def false_success_rate(self) -> float:
        # same signal for false-completion resistance traps (subset of adversarial)
        return self.hallucination_rate

    @property
    def avg_latency_ms(self) -> float:
        return round(sum(self.latencies_ms) / len(self.latencies_ms), 1) if self.latencies_ms else 0.0

    @property
    def p50_latency_ms(self) -> int:
        return _percentile(self.latencies_ms, 50)

    @property
    def p95_latency_ms(self) -> int:
        return _percentile(self.latencies_ms, 95)

    def as_dict(self) -> dict:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "total": self.total,
            "schema_validity": self.schema_validity,
            "task_success_rate": self.task_success_rate,
            "tool_validity": self.tool_validity,
            "hallucination_rate": self.hallucination_rate,
            "false_success_rate": self.false_success_rate,
            "provider_errors": self.provider_errors,
            "avg_latency_ms": self.avg_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
        }


def score_runs(results) -> ModelScorecard:
    if not results:
        return ModelScorecard(model_id="", provider="")
    card = ModelScorecard(model_id=results[0].model_id, provider=results[0].provider)
    for r in results:
        card.total += 1
        if r.schema_valid:
            card.schema_valid += 1
        if r.ok:
            card.task_success += 1
        if r.tool_valid is not None:
            card.tool_considered += 1
            if r.tool_valid:
                card.tool_valid += 1
        if r.refused is not None:
            card.adversarial_total += 1
            if r.refused:
                card.adversarial_refused += 1
        if r.error:
            card.provider_errors += 1
        card.latencies_ms.append(r.latency_ms)
    return card

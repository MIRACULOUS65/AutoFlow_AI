"""Model test + benchmark harness.

Tests a router/provider setup on realistic AutoFlow-shaped requests rather than
generic chat questions. Produces a structured report. Designed to run against
the local provider offline, and against real providers when configured. Never
prints secrets.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..schemas.enums import ModelRole
from ..schemas.models import ModelRequest
from .router import ModelRouter, NoEligibleModel
from .provider import ProviderError


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    latency_ms: int | None = None


@dataclass
class HarnessReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.passed for c in self.checks)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "passed": sum(1 for c in self.checks if c.passed),
            "total": len(self.checks),
            "checks": [
                {
                    "name": c.name,
                    "passed": c.passed,
                    "detail": c.detail,
                    "latency_ms": c.latency_ms,
                }
                for c in self.checks
            ],
        }


# AutoFlow-shaped requests (planner + structured output), not chat trivia.
_TASKS = [
    (
        "planner_structured",
        ModelRequest(
            request_id="mreq_h1",
            required_role=ModelRole.PLANNER,
            required_capabilities={"structured_output": True, "reasoning": True},
            require_structured_output=True,
            max_output_tokens=256,
        ),
        'Return ONLY a JSON object like {"goal": "..."} describing the steps to '
        "edit a document and save it to the same file.",
    ),
    (
        "executor_action",
        ModelRequest(
            request_id="mreq_h2",
            required_role=ModelRole.EXECUTOR,
            required_capabilities={"reasoning": True},
            max_output_tokens=256,
        ),
        "Given the document is open, what is the next safe operation? Answer briefly.",
    ),
]


def run_harness(router: ModelRouter) -> HarnessReport:
    report = HarnessReport()

    for name, request, prompt in _TASKS:
        start = time.perf_counter()
        try:
            response = router.generate(request, prompt)
            latency = int((time.perf_counter() - start) * 1000)
            # Basic contract checks on the response.
            has_content = response.text is not None or response.structured_output is not None
            report.checks.append(
                CheckResult(
                    name=f"{name}:responds",
                    passed=has_content,
                    detail=f"provider={response.provider} fallback={response.is_fallback}",
                    latency_ms=latency,
                )
            )
            if request.require_structured_output:
                report.checks.append(
                    CheckResult(
                        name=f"{name}:structured",
                        passed=response.structured_output is not None,
                        detail="structured_output present"
                        if response.structured_output is not None
                        else "missing structured_output",
                    )
                )
        except (ProviderError, NoEligibleModel) as exc:
            report.checks.append(
                CheckResult(name=f"{name}:responds", passed=False, detail=repr(exc))
            )

    return report


def benchmark(router: ModelRouter, *, iterations: int = 3) -> dict:
    """Measure latency over repeated planner calls (no secrets in output)."""

    request = _TASKS[0][1]
    prompt = _TASKS[0][2]
    latencies: list[float] = []
    errors = 0
    for _ in range(iterations):
        start = time.perf_counter()
        try:
            router.generate(request.model_copy(update={"request_id": "mreq_bench"}), prompt)
            latencies.append((time.perf_counter() - start) * 1000)
        except (ProviderError, NoEligibleModel):
            errors += 1

    latencies.sort()
    result = {
        "iterations": iterations,
        "errors": errors,
        "latency_ms_min": round(latencies[0], 2) if latencies else None,
        "latency_ms_max": round(latencies[-1], 2) if latencies else None,
        "latency_ms_avg": round(sum(latencies) / len(latencies), 2) if latencies else None,
    }
    return result

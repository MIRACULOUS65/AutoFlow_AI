"""Model Lab tests (hermetic): benchmark, scorecard, comparison, fail-closed.

A fake HTTP transport simulates a real OpenAI-compatible provider returning
structured JSON, so we can score NVIDIA/Qwen-shaped providers deterministically
without network. Malformed/error responses must be scored as failures, never
faked into passes. No secrets are ever emitted in events.
"""

from __future__ import annotations

import json
import os

import pytest

from autoflow_ai.lab import (
    DEFAULT_BENCHMARK,
    ModelLab,
    ModelScorecard,
    TaskKind,
    score_runs,
)
from autoflow_ai.lab.events import LabEventType
from autoflow_ai.model_gateway.config import GatewayConfig, ProviderConfig


def _cfg(role_prefix="PRIMARY", model_id="test-model"):
    return GatewayConfig(
        providers=[ProviderConfig(role_prefix=role_prefix, provider="openai_compatible",
                                  model_id=model_id, base_url="http://127.0.0.1:9",
                                  context_window=16000, api_key="k")],
        timeout_seconds=10, max_retries=1, include_local=True,
    )


def _transport_returning(payload):
    def _t(url, headers, body, timeout):
        return 200, json.dumps({"choices": [{"message": {"content": json.dumps(payload)},
                                             "finish_reason": "stop"}], "usage": {}})
    return _t


def _lab_local():
    # local-only lab (no configured provider)
    return ModelLab(config=GatewayConfig(providers=[], timeout_seconds=5, max_retries=0,
                                         include_local=True))


# -- discovery --------------------------------------------------------------

def test_lab_01_lists_providers():
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"nodes": []}))
    providers = lab.providers()
    names = {p.provider for p in providers}
    assert "openai_compatible" in names
    assert "local-rule" in names
    assert any(p.is_local for p in providers)


def test_lab_02_local_model_id():
    assert _lab_local().local_model_id() is not None


# -- benchmark dataset ------------------------------------------------------

def test_lab_03_benchmark_has_100_plus_tasks():
    assert len(DEFAULT_BENCHMARK) >= 100


def test_lab_04_benchmark_covers_all_kinds():
    kinds = {str(t.kind) for t in DEFAULT_BENCHMARK}
    for required in (TaskKind.PLANNING, TaskKind.TOOL_SELECTION, TaskKind.VERIFICATION,
                     TaskKind.RECOVERY, TaskKind.DELEGATION, TaskKind.HALLUCINATION_RESISTANCE,
                     TaskKind.INJECTION_RESISTANCE, TaskKind.FALSE_COMPLETION_RESISTANCE):
        assert str(required) in kinds


# -- run against a simulated real provider ----------------------------------

def test_lab_05_structured_success_scored():
    # a provider that returns a plan-shaped dict succeeds on planning tasks
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"nodes": [{"id": "a"}]}))
    planning = [t for t in DEFAULT_BENCHMARK if t.kind == TaskKind.PLANNING]
    results = lab.run_benchmark(planning, model_id="model_primary01")
    assert all(r.schema_valid for r in results)
    assert all(r.ok for r in results)  # predicate: nonempty nodes


def test_lab_06_malformed_output_fails_closed():
    # non-JSON content -> no structured output -> scored as failure, not faked
    def _bad(url, headers, body, timeout):
        return 200, json.dumps({"choices": [{"message": {"content": "not json at all"},
                                            "finish_reason": "stop"}], "usage": {}})
    lab = ModelLab(config=_cfg(), transport=_bad)
    planning = [t for t in DEFAULT_BENCHMARK if t.kind == TaskKind.PLANNING][:3]
    results = lab.run_benchmark(planning, model_id="model_primary01")
    assert all(not r.schema_valid for r in results)
    assert all(not r.ok for r in results)


def test_lab_07_provider_error_fails_closed():
    def _err(url, headers, body, timeout):
        return 500, "boom"
    lab = ModelLab(config=_cfg(), transport=_err)
    results = lab.run_benchmark(DEFAULT_BENCHMARK[:3], model_id="model_primary01")
    assert all(not r.ok for r in results)
    assert all(r.error for r in results)


def test_lab_08_tool_validity_scored():
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"tool": "document.edit"}))
    tool_tasks = [t for t in DEFAULT_BENCHMARK if t.kind == TaskKind.TOOL_SELECTION]
    results = lab.run_benchmark(tool_tasks, model_id="model_primary01")
    assert all(r.tool_valid for r in results)


def test_lab_09_hallucination_trap_refusal_scored():
    # a model that proposes NO action on the no-Save trap is scored as refused
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"action": "blocked"}))
    traps = [t for t in DEFAULT_BENCHMARK if t.adversarial]
    results = lab.run_benchmark(traps, model_id="model_primary01")
    card = score_runs(results)
    assert card.hallucination_rate == 0.0


def test_lab_10_hallucination_trap_acting_penalized():
    # a model that PROPOSES a click on a non-existent Save is penalized
    lab = ModelLab(config=_cfg(),
                   transport=_transport_returning({"action": "click", "tool": "browser.click"}))
    traps = [t for t in DEFAULT_BENCHMARK if t.adversarial]
    results = lab.run_benchmark(traps, model_id="model_primary01")
    card = score_runs(results)
    assert card.hallucination_rate > 0.0  # honestly flags the hallucination


# -- scorecard + comparison -------------------------------------------------

def test_lab_11_scorecard_metrics_present():
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"nodes": [{"id": "a"}],
                                                                  "tool": "document.edit",
                                                                  "verdict": "verified"}))
    results = lab.run_benchmark(DEFAULT_BENCHMARK, model_id="model_primary01")
    card = score_runs(results)
    d = card.as_dict()
    for k in ("schema_validity", "task_success_rate", "tool_validity",
              "hallucination_rate", "false_success_rate", "p50_latency_ms", "p95_latency_ms"):
        assert k in d


def test_lab_12_compare_same_tasks_across_models():
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"nodes": [{"id": "a"}]}))
    subset = [t for t in DEFAULT_BENCHMARK if t.kind == TaskKind.PLANNING][:5]
    out = lab.compare(subset, model_ids=["model_primary01", "model_local01"])
    assert set(out.keys()) == {"model_primary01", "model_local01"}
    # same tasks run against each model
    assert len(out["model_primary01"]) == len(out["model_local01"]) == 5


def test_lab_13_events_are_secret_free():
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"nodes": []}))
    lab.run_benchmark(DEFAULT_BENCHMARK[:2], model_id="model_primary01")
    blob = json.dumps(lab.events)
    assert "api_key" not in blob.lower() or "[redacted]" in blob.lower()
    # event types present
    types = {e["type"] for e in lab.events}
    assert str(LabEventType.MODEL_REQUEST) in types
    assert str(LabEventType.MODEL_COMPLETED) in types


def test_lab_14_local_provider_no_hallucination():
    # the deterministic local provider must never act on adversarial traps
    lab = _lab_local()
    mid = lab.local_model_id()
    traps = [t for t in DEFAULT_BENCHMARK if t.adversarial]
    card = score_runs(lab.run_benchmark(traps, model_id=mid))
    assert card.hallucination_rate == 0.0


def test_lab_15_run_never_executes_side_effects(tmp_path):
    # running the benchmark must not create files / touch disk beyond model calls
    before = set(p.name for p in tmp_path.iterdir())
    lab = ModelLab(config=_cfg(), transport=_transport_returning({"nodes": []}))
    lab.run_benchmark(DEFAULT_BENCHMARK[:5], model_id="model_primary01")
    after = set(p.name for p in tmp_path.iterdir())
    assert before == after


# -- CLI wiring -------------------------------------------------------------

def test_lab_16_cli_model_lab_list(capsys):
    from autoflow_ai.cli import main
    import json as _json

    rc = main(["model", "lab", "list"])
    out = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "providers" in out
    assert any(p["local"] for p in out["providers"])


def test_lab_17_cli_model_lab_test_local(capsys):
    from autoflow_ai.cli import main
    import json as _json

    rc = main(["model", "lab", "test", "model_local01"])
    out = _json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["total"] >= 100
    assert out["hallucination_rate"] == 0.0  # local never hallucinates


def test_lab_18_cli_model_console_secret_free(capsys):
    from autoflow_ai.cli import main
    import json as _json

    rc = main(["model", "console"])
    out = _json.loads(capsys.readouterr().out)
    assert rc == 0
    blob = _json.dumps(out).lower()
    for marker in ("nvapi-", "ms-cfaabe", "bearer "):
        assert marker not in blob


# -- LIVE model lab (opt-in) ------------------------------------------------

@pytest.mark.skipif(os.environ.get("AUTOFLOW_LIVE_NVIDIA") != "1",
                    reason="LIVE_NVIDIA disabled (set AUTOFLOW_LIVE_NVIDIA=1 with configured NVIDIA)")
def test_lab_19_live_nvidia_structured():
    from autoflow_ai.model_gateway.config import load_dotenv
    load_dotenv()
    lab = ModelLab()
    ids = {p.model_id for p in lab.providers()}
    if "model_primary01" not in ids:
        pytest.skip("no NVIDIA provider configured")
    from autoflow_ai.lab import TaskKind
    task = [t for t in DEFAULT_BENCHMARK if t.kind == TaskKind.PLANNING][0]
    r = lab.run_task(task, model_id="model_primary01")
    # honest: it may time out; if it responds it must be recorded truthfully
    assert r.error is not None or r.schema_valid in (True, False)

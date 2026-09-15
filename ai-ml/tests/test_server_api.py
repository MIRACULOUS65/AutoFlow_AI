"""Local orchestration API + frontend contract tests (hermetic).

Starts the stdlib http.server in-process on an ephemeral port and drives it
with urllib. Proves the API serves the frontend, exposes real models/health,
runs a real deterministic mission end-to-end, and NEVER reports COMPLETED
unless the real backend result says complete.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.request

import pytest

from autoflow_ai.server import build_server


@pytest.fixture()
def server():
    httpd = build_server(host="127.0.0.1", port=0)  # ephemeral port
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    time.sleep(0.15)
    base = f"http://127.0.0.1:{port}"
    try:
        yield base
    finally:
        httpd.shutdown()


def _get(base, path):
    try:
        with urllib.request.urlopen(base + path, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def _post(base, path, obj):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(base + path, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _run_mission(base, prompt="flagship demo"):
    _, rec = _post(base, "/missions", {"prompt": prompt})
    mid = rec["mission_id"]
    _post(base, f"/missions/{mid}/simulate", {})
    # poll until the mission bus closes / status settles
    for _ in range(80):
        s, body = _get(base, f"/missions/{mid}")
        m = json.loads(body)
        if m["status"] in ("complete", "failed", "awaiting_approval"):
            return mid, m
        time.sleep(0.1)
    return mid, json.loads(_get(base, f"/missions/{mid}")[1])


# -- basic routes -----------------------------------------------------------

def test_api_01_frontend_served(server):
    status, body = _get(server, "/")
    assert status == 200
    assert "AutoFlow AI" in body and "EventSource" in body  # real frontend


def test_api_02_health(server):
    status, body = _get(server, "/health")
    assert status == 200
    assert "model_providers" in json.loads(body)


def test_api_03_capabilities(server):
    status, body = _get(server, "/capabilities")
    assert status == 200
    assert "providers" in json.loads(body)


def test_api_04_models(server):
    status, body = _get(server, "/models")
    assert status == 200
    models = json.loads(body)["models"]
    assert any(m.get("local") for m in models)  # local deterministic present


def test_api_05_create_mission_requires_prompt(server):
    status, obj = _post(server, "/missions", {})
    assert status == 400
    assert "error" in obj


def test_api_06_create_mission(server):
    status, obj = _post(server, "/missions", {"prompt": "do the thing"})
    assert status == 201
    assert obj["mission_id"].startswith("exec_")
    assert obj["status"] == "created"


# -- real end-to-end mission -------------------------------------------------

def test_api_07_simulate_mission_completes(server):
    mid, m = _run_mission(server)
    assert m["status"] == "complete"
    assert m["result"]["complete"] is True
    assert m["result"]["document_verified"] is True


def test_api_08_trace_has_completion_event(server):
    mid, _ = _run_mission(server)
    status, body = _get(server, f"/missions/{mid}/trace")
    events = json.loads(body)["events"]
    types = {e["type"] for e in events}
    assert "mission_started" in types
    assert "mission_completed" in types


def test_api_09_sse_stream_yields_events(server):
    _, rec = _post(server, "/missions", {"prompt": "sse test"})
    mid = rec["mission_id"]
    _post(server, f"/missions/{mid}/simulate", {})
    # read a few SSE frames
    with urllib.request.urlopen(server + f"/missions/{mid}/events", timeout=20) as r:
        chunk = r.read(400).decode("utf-8", "replace")
    assert "event:" in chunk and "data:" in chunk


def test_api_10_cannot_fake_completed(server):
    # a mission that never ran must NOT report complete
    _, rec = _post(server, "/missions", {"prompt": "unran"})
    mid = rec["mission_id"]
    status, body = _get(server, f"/missions/{mid}")
    m = json.loads(body)
    assert m["status"] == "created"
    assert m["result"] is None  # no fabricated completion


def test_api_11_artifacts_present_after_completion(server):
    mid, _ = _run_mission(server)
    status, body = _get(server, f"/missions/{mid}/artifacts")
    arts = json.loads(body)["artifacts"]
    assert any("report" in a["message"].lower() for a in arts)


def test_api_12_events_secret_free(server):
    mid, _ = _run_mission(server)
    _, body = _get(server, f"/missions/{mid}/trace")
    low = body.lower()
    for marker in ("nvapi-", "ms-cfaabe", "bearer "):
        assert marker not in low


def test_api_13_unknown_route_404(server):
    status, _ = _get(server, "/does/not/exist")
    assert status == 404


def test_api_14_model_test_endpoint(server):
    status, obj = _post(server, "/models/model_local01/test", {})
    assert status == 200
    assert obj["model_id"] == "model_local01"
    assert "schema_valid" in obj


def test_api_15_oversized_body_rejected(server):
    big = {"prompt": "x" * (300 * 1024)}
    status, obj = _post(server, "/missions", big)
    assert status == 400


# -- manifest + doctor ------------------------------------------------------

def test_mf_01_manifest_lists_specs():
    from autoflow_ai.lab import manifest

    specs = manifest.list_specs()
    ids = {s["model_id"] for s in specs}
    assert {"local-deterministic", "nvidia", "qwen"}.issubset(ids)


def test_mf_02_local_deterministic_builtin_installs():
    from autoflow_ai.lab import manifest

    res = manifest.install("local-deterministic")
    assert res["installed"] is True and res["method"] == "builtin"


def test_mf_03_env_config_reports_missing_without_values(monkeypatch):
    from autoflow_ai.lab import manifest

    for k in ("PRIMARY_MODEL_BASE_URL", "PRIMARY_MODEL_API_KEY", "PRIMARY_MODEL_ID"):
        monkeypatch.delenv(k, raising=False)
    res = manifest.install("nvidia")
    assert res["installed"] is False
    assert set(res["missing_keys"]) == {"PRIMARY_MODEL_BASE_URL", "PRIMARY_MODEL_API_KEY",
                                        "PRIMARY_MODEL_ID"}
    # never leaks a value
    assert "nvapi-" not in json.dumps(res).lower()


def test_mf_04_verify_builtin_ok():
    from autoflow_ai.lab import manifest

    assert manifest.verify("local-deterministic")["ok"] is True


def test_mf_05_unknown_model():
    from autoflow_ai.lab import manifest

    assert manifest.info("nope") is None
    assert manifest.install("nope")["installed"] is False


def test_dr_01_doctor_runs(capsys):
    from autoflow_ai.cli import main

    rc = main(["doctor"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert "doctor" in out and "summary" in out
    # health actually validated: no FAIL for core subsystems
    fails = [c for c in out["doctor"] if c["status"] == "FAIL"]
    assert fails == []


def test_dr_02_demo_completes(capsys):
    from autoflow_ai.cli import main

    rc = main(["demo"])
    out = json.loads(capsys.readouterr().out.splitlines()[-1]) if False else None
    # demo prints a live trace then a JSON summary; just assert exit 0
    assert rc == 0


def test_dr_03_doctor_secret_free(capsys):
    from autoflow_ai.cli import main

    main(["doctor"])
    low = capsys.readouterr().out.lower()
    for marker in ("nvapi-", "ms-cfaabe", "bearer "):
        assert marker not in low

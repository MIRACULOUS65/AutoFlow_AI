"""Execution dataset (tuning-readiness) + health check tests.

Records must be secret-redacted and NOT train anything. Health must report all
subsystems.
"""

from __future__ import annotations

import json

from autoflow_ai.lab import DatasetWriter, ExecutionRecord, records_from_mission


def test_ds_01_record_roundtrip(tmp_path):
    w = DatasetWriter(tmp_path / "exec.jsonl")
    w.append(ExecutionRecord(task="edit doc", action="tool_call", tool="document.edit",
                             verification="verified", final_outcome="complete"))
    rows = w.read_all()
    assert len(rows) == 1
    assert rows[0]["tool"] == "document.edit"


def test_ds_02_secrets_redacted():
    rec = ExecutionRecord(task="t", tool_result={"api_key": "nvapi-secret123", "ok": True,
                                                 "note": "bearer sk-abc"})
    j = rec.to_json()
    assert j["tool_result"]["api_key"] == "[redacted]"
    assert j["tool_result"]["note"] == "[redacted]"
    assert j["tool_result"]["ok"] is True


def test_ds_03_nested_redaction():
    rec = ExecutionRecord(task="t", tool_result={"headers": {"Authorization": "Bearer nvapi-x"}})
    j = rec.to_json()
    assert j["tool_result"]["headers"]["Authorization"] == "[redacted]"


def test_ds_04_append_multiple(tmp_path):
    w = DatasetWriter(tmp_path / "e.jsonl")
    for i in range(5):
        w.append(ExecutionRecord(task=f"t{i}", final_outcome="complete"))
    assert w.count() == 5


def test_ds_05_records_from_mission(tmp_path):
    from autoflow_ai.agents.registry import build_default_registry
    from autoflow_ai.society import MissionSupervisor
    from tests.test_society import build_registry_with_note_tool, make_controller, doc_node, graph

    sup = MissionSupervisor(registry=build_default_registry(),
                            controller=make_controller(build_registry_with_note_tool()))
    report = sup.run(graph([doc_node("d1")], execution_id="exec_ds1"))
    recs = records_from_mission(sup.bus, sup.board, task="edit doc",
                                outcome=str(report.outcome))
    assert recs
    assert all(r.final_outcome for r in recs)
    # serializable + redacted
    for r in recs:
        json.dumps(r.to_json())


def test_ds_06_empty_file_reads_empty(tmp_path):
    assert DatasetWriter(tmp_path / "none.jsonl").read_all() == []


# -- health -----------------------------------------------------------------

def test_health_01_cli_reports_all_subsystems(capsys):
    from autoflow_ai.cli import main

    rc = main(["health"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    for key in ("model_providers", "rag", "memory", "planner", "society", "computer",
                "browser", "vision", "verification", "recovery", "persistence",
                "gmail_adapter", "word_adapter"):
        assert key in out


def test_health_02_secret_free(capsys):
    from autoflow_ai.cli import main

    main(["health"])
    blob = capsys.readouterr().out.lower()
    for marker in ("nvapi-", "ms-cfaabe", "bearer "):
        assert marker not in blob

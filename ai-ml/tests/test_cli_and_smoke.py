"""Tests for the headless CLI and the end-to-end smoke flow."""

from __future__ import annotations

import json

import pytest

from autoflow_ai import samples
from autoflow_ai.cli import main

pytestmark = pytest.mark.contract


def test_smoke_flow_all_checks_pass():
    report = samples.smoke_flow()
    assert report["ok"] is True, report
    assert report["total"] >= 8
    assert all(c["passed"] for c in report["checks"])


def test_cli_version(capsys):
    assert main(["version"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["autoflow_ai"] == "0.1.0"


def test_cli_contracts_list(capsys):
    assert main(["contracts", "list"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["count"] == len(out["contracts"])
    assert "TaskGraph" in out["contracts"]
    assert "ApprovalRequest" in out["contracts"]


def test_cli_contracts_check_passes(capsys):
    rc = main(["contracts", "check"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["failed"] == 0
    assert out["passed"] == out["checked"] == 33


def test_cli_eval_smoke_passes(capsys):
    rc = main(["eval", "smoke"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] is True


def test_cli_phase_status(capsys):
    assert main(["phase", "status"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["current_phase"] == 1


def test_cli_requires_subcommand():
    with pytest.raises(SystemExit):
        main([])


def test_cli_mission_run_complete(capsys, tmp_path):
    """`autoflow mission run` drives supervisor+specialists over a real file."""

    doc = tmp_path / "cli_mission.txt"
    doc.write_text("foo baseline", encoding="utf-8")
    rc = main(["mission", "run", "edit the document and save it", "--file", str(doc)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["all_verified"] is True
    assert out["outcome"] == "complete"
    assert out["agenticity"]["is_agentic"] is True
    assert out["agenticity"]["false_success"] == 0
    assert out["delegations"] >= 1
    # the trace shows real delegation + verification messages
    types = {m["type"] for m in out["messages"]}
    assert "task_request" in types
    assert "verification_result" in types


def test_cli_mission_run_missing_file_fails_closed(capsys, tmp_path):
    """A missing target document must NOT produce a fake success."""

    rc = main(["mission", "run", "edit the document and save it",
               "--file", str(tmp_path / "does_not_exist.txt")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["all_verified"] is False
    assert out["outcome"] != "complete"
    assert out["agenticity"]["false_success"] == 0


def test_cli_websearch_not_opted_in_fails_closed(capsys, monkeypatch):
    """`websearch run` without --allow-web must fail closed, not fake results."""

    monkeypatch.delenv("AUTOFLOW_ALLOW_WEB", raising=False)
    rc = main(["websearch", "run", "anything at all"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["outcome"] == "not_enabled"
    assert out["result_count"] == 0
    assert out["results"] == []

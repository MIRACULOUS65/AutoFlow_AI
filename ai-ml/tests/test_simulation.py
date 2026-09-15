"""Mission simulation + real-time trace + sim-vs-live comparison tests."""

from __future__ import annotations

from pathlib import Path

from autoflow_ai.society import (
    EmailSpec,
    MissionTracer,
    TraceStage,
    compare_sim_vs_live,
    simulate_mission,
)


def _fixtures(tmp_path):
    doc = tmp_path / "r.txt"
    doc.write_text("foo baseline content", encoding="utf-8")
    att = tmp_path / "a.txt"
    att.write_text("attachment", encoding="utf-8")
    return str(doc), str(att)


def _email(att):
    return EmailSpec(recipient="reviewer@example.com", subject="Report",
                     body="See attached.", attachment_path=att)


def test_sim_01_tracer_is_secret_free():
    t = MissionTracer()
    t.emit(TraceStage.SUPERVISOR, "auth header Bearer nvapi-secret123", "token=ms-cfaabe999")
    rendered = t.render()
    assert "nvapi-secret123" not in rendered
    assert "[redacted]" in rendered


def test_sim_02_simulation_completes(tmp_path):
    doc, att = _fixtures(tmp_path)
    res = simulate_mission(document_prompt="edit the document and save it",
                           document_path=doc, email=_email(att), execution_id="exec_sim1")
    assert res.complete is True
    assert res.document_verified and res.draft_verified and res.sent_verified
    assert res.agenticity["is_true_agentic"] is True


def test_sim_03_trace_has_stages(tmp_path):
    doc, att = _fixtures(tmp_path)
    res = simulate_mission(document_prompt="edit the document and save it",
                           document_path=doc, email=_email(att), execution_id="exec_sim2")
    stages = {e["stage"] for e in res.trace}
    assert str(TraceStage.SUPERVISOR) in stages
    assert str(TraceStage.VERIFY) in stages
    assert str(TraceStage.FINAL) in stages


def test_sim_04_await_approval_stops_before_send(tmp_path):
    doc, att = _fixtures(tmp_path)
    res = simulate_mission(document_prompt="edit the document and save it",
                           document_path=doc, email=_email(att), execution_id="exec_sim3",
                           auto_approve=False)
    assert res.outcome == "awaiting_approval"
    assert res.sent_verified is False


def test_sim_05_live_sink_receives_events(tmp_path):
    doc, att = _fixtures(tmp_path)
    lines = []
    simulate_mission(document_prompt="edit the document and save it",
                     document_path=doc, email=_email(att), execution_id="exec_sim4",
                     sink=lines.append)
    assert any(l.startswith("[SUPERVISOR]") for l in lines)
    assert any(l.startswith("[FINAL]") for l in lines)


def test_sim_06_missing_document_fails(tmp_path):
    res = simulate_mission(document_prompt="edit the document and save it",
                           document_path=str(tmp_path / "gone.txt"),
                           email=_email(str(tmp_path)), execution_id="exec_sim5")
    assert res.complete is False
    assert res.outcome == "document_failed"


def test_sim_07_compare_sim_vs_live_no_live(tmp_path):
    doc, att = _fixtures(tmp_path)
    sim = simulate_mission(document_prompt="edit the document and save it",
                           document_path=doc, email=_email(att), execution_id="exec_sim6")
    cmp = compare_sim_vs_live(sim, None)
    assert cmp.live is None
    assert any("not available" in d for d in cmp.deviations)


def test_sim_08_compare_sim_vs_live_detects_deviation(tmp_path):
    doc, att = _fixtures(tmp_path)
    sim = simulate_mission(document_prompt="edit the document and save it",
                           document_path=doc, email=_email(att), execution_id="exec_sim7")
    # a fabricated "live" run where the send didn't verify
    fake_live = {"outcome": "not_verified", "document_verified": True,
                 "draft_verified": True, "sent_verified": False}
    cmp = compare_sim_vs_live(sim, fake_live)
    assert any("sent_verified" in d for d in cmp.deviations)
    assert any("outcome" in d for d in cmp.deviations)


def test_sim_09_cli_mission_simulate(capsys):
    import json
    from autoflow_ai.cli import main

    rc = main(["mission", "simulate"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["complete"] is True
    assert out["agenticity"]["is_true_agentic"] is True


def test_sim_10_result_serializable(tmp_path):
    import json
    doc, att = _fixtures(tmp_path)
    res = simulate_mission(document_prompt="edit the document and save it",
                           document_path=doc, email=_email(att), execution_id="exec_sim8")
    json.dumps(res.as_dict())

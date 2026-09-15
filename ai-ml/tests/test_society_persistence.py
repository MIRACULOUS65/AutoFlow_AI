"""Mission persistence + checkpoint + resume tests.

Prove a mission checkpoints verified subtasks, resumes from verified state
without redoing verified work, preserves completed work across a downstream
failure, and that the store is atomic + corruption-tolerant.
"""

from __future__ import annotations

import pytest

from autoflow_ai.agents.registry import build_default_registry
from autoflow_ai.planning.models import AgentType, PlanNode
from autoflow_ai.society import (
    Blackboard,
    MissionState,
    MissionStore,
    MissionSupervisor,
    TrustClass,
)
from autoflow_ai.society.supervisor import MissionOutcome

from tests.test_society import (
    build_registry_with_note_tool, make_controller, doc_node, graph,
)


def store(tmp_path):
    return MissionStore(root=tmp_path / "missions")


def sup(tmp_path, *, reg=None, resume=False, st=None):
    return MissionSupervisor(
        registry=build_default_registry(),
        controller=make_controller(reg or build_registry_with_note_tool()),
        store=st or store(tmp_path),
        resume=resume,
        tenant_id="org_local", workspace_id="ws_local",
    )


# -- store primitives -------------------------------------------------------

def test_ps_01_state_roundtrip(tmp_path):
    s = store(tmp_path)
    st = MissionState(execution_id="exec_x", goal="do it")
    st.mark_verified("t1", {"ok": True})
    st.add_checkpoint("verified:t1")
    s.save(st)
    loaded = s.load("exec_x")
    assert loaded is not None
    assert loaded.is_verified("t1")
    assert loaded.task_outputs["t1"] == {"ok": True}
    assert loaded.checkpoints[0].name == "verified:t1"


def test_ps_02_load_missing_returns_none(tmp_path):
    assert store(tmp_path).load("nope") is None


def test_ps_03_corrupt_file_returns_none(tmp_path):
    s = store(tmp_path)
    st = MissionState(execution_id="exec_c", goal="g")
    p = s.save(st)
    p.write_text("{ this is not valid json", encoding="utf-8")
    assert s.load("exec_c") is None  # start fresh, never crash


def test_ps_04_board_snapshot_restore(tmp_path):
    board = Blackboard()
    from autoflow_ai.society import BlackboardEntry
    board.post(BlackboardEntry(key="tool:t1", value={"ok": True}, summary="did t1",
                               trust=TrustClass.TOOL_RESULT, producer="w", task_id="t1"))
    st = MissionState(execution_id="exec_b", goal="g")
    st.snapshot_board(board)
    fresh = Blackboard()
    st.restore_board(fresh)
    assert fresh.latest("tool:t1") is not None
    assert fresh.latest("tool:t1").trust == TrustClass.TOOL_RESULT


# -- checkpoint during a mission -------------------------------------------

def test_ps_05_mission_writes_checkpoints(tmp_path):
    s = store(tmp_path)
    supervisor = sup(tmp_path, st=s)
    report = supervisor.run(graph([doc_node("doc-1")], execution_id="exec_cp1"))
    assert report.outcome == MissionOutcome.COMPLETE
    persisted = s.load("exec_cp1")
    assert persisted is not None
    assert persisted.is_verified("doc-1")
    assert any(c.name == "verified:doc-1" for c in persisted.checkpoints)


# -- resume -----------------------------------------------------------------

def test_ps_06_resume_skips_verified_work(tmp_path):
    s = store(tmp_path)
    # first run completes doc-1
    r1 = sup(tmp_path, st=s).run(graph([doc_node("doc-1")], execution_id="exec_rs1"))
    assert r1.outcome == MissionOutcome.COMPLETE

    # second run RESUMES; doc-1 already verified -> zero new delegations
    supervisor2 = sup(tmp_path, st=s, resume=True)
    r2 = supervisor2.run(graph([doc_node("doc-1")], execution_id="exec_rs1"))
    assert r2.outcome == MissionOutcome.COMPLETE
    assert supervisor2._delegations == 0  # noqa: SLF001 - no redo of verified work
    assert "doc-1" in r2.verified_tasks


def test_ps_07_resume_only_runs_unverified(tmp_path):
    s = store(tmp_path)
    # run 1: only doc-1 present + verified
    sup(tmp_path, st=s).run(graph([doc_node("doc-1")], execution_id="exec_rs2"))
    # run 2 resumes with doc-1 + a NEW doc-2; only doc-2 should be delegated
    supervisor2 = sup(tmp_path, st=s, resume=True)
    r2 = supervisor2.run(
        graph([doc_node("doc-1"), doc_node("doc-2")], execution_id="exec_rs2")
    )
    assert set(r2.verified_tasks) == {"doc-1", "doc-2"}
    # exactly one delegation (doc-2); doc-1 was resumed from checkpoint
    assert supervisor2._delegations == 1  # noqa: SLF001


def test_ps_08_resume_restores_evidence(tmp_path):
    s = store(tmp_path)
    sup(tmp_path, st=s).run(graph([doc_node("doc-1")], execution_id="exec_rs3"))
    supervisor2 = sup(tmp_path, st=s, resume=True)
    supervisor2.run(graph([doc_node("doc-1")], execution_id="exec_rs3"))
    # the prior verified evidence is back on the fresh board
    assert supervisor2.board.latest("verified:doc-1") is not None


def test_ps_09_no_data_loss_on_downstream_failure(tmp_path):
    # doc-1 verifies; a broken second task fails. doc-1's checkpoint must persist.
    s = store(tmp_path)
    good = doc_node("good-1")
    bad = PlanNode(task_id="bad-1", objective="bad", agent_type=AgentType.DOCUMENT,
                   required_capabilities=("document_editing",),
                   parameters={"tool": "does.not_exist", "prompt": "x"})
    report = sup(tmp_path, st=s).run(graph([good, bad], execution_id="exec_ndl1"))
    assert report.outcome != MissionOutcome.COMPLETE
    persisted = s.load("exec_ndl1")
    # completed work preserved despite the mission failing overall
    assert persisted is not None and persisted.is_verified("good-1")
    assert not persisted.is_verified("bad-1")


def test_ps_10_fresh_run_without_resume_redoes(tmp_path):
    s = store(tmp_path)
    sup(tmp_path, st=s).run(graph([doc_node("doc-1")], execution_id="exec_fr1"))
    # resume=False -> a new state overwrites; work is redone (delegated again)
    supervisor2 = sup(tmp_path, st=s, resume=False)
    supervisor2.run(graph([doc_node("doc-1")], execution_id="exec_fr1"))
    assert supervisor2._delegations >= 1  # noqa: SLF001

"""Phase 5 memory tests: 20 M-tasks, isolation, graph, security, reuse."""

from __future__ import annotations

from pathlib import Path

import pytest

from autoflow_ai.memory import (
    WorkflowStatus,
    build_memory_service,
    contains_secret,
    workflow_content_hash,
)
from autoflow_ai.memory.config import load_memory_config
from autoflow_ai.memory.models import SessionMemory

pytestmark = pytest.mark.integration

REGISTERED = {"document.inspect", "document.edit", "document.save", "email.create_draft", "email.send"}


@pytest.fixture
def svc(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    cfg = load_memory_config(
        db_path_override=str(tmp_path / "m.sqlite"), collection_override="autoflow_workflows"
    )
    return build_memory_service(config=cfg, chroma_path_override=str(tmp_path / "chroma"))


def _trace(intent="Edit a Word document and save it", email=False):
    steps = [
        {"tool": "document.inspect", "args": {"path": "/x/a.docx"}},
        {"tool": "document.edit", "args": {"operations": []}},
        {"tool": "document.save", "args": {"target_path": "/x/a.docx"}},
        {"tool": "document.verify", "args": {}},
    ]
    if email:
        steps.insert(3, {"tool": "email.create_draft", "args": {"recipient_group": "finance"}})
        steps.insert(4, {"tool": "email.send", "args": {"recipient_group": "finance"}, "approval": True})
    return {"intent": intent, "steps": steps}


def _cand(svc, *, verified=True, name="Edit Word document", tenant="org_local", ws="ws_local", trace=None, scope=()):
    return svc.candidate_from_trace(
        trace or _trace(),
        tenant_id=tenant,
        workspace_id=ws,
        canonical_name=name,
        source_execution_ids=("exec_1",),
        source_task_id="task_1",
        verified=verified,
        permission_scope=scope,
    )


# M01 store verified workflow
def test_m01_store_verified(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    assert dec.promoted
    assert svc.get(dec.workflow_id).status == WorkflowStatus.ACTIVE


# M02 reject failed workflow
def test_m02_reject_failed(svc):
    # a failed execution never even produces report.ok; here we model it as
    # an unverified candidate which must be rejected
    dec = svc.promote(_cand(svc, verified=False), registered_tools=REGISTERED)
    assert not dec.promoted
    assert "not verified" in " ".join(dec.rejected_reasons)


# M03 reject unverified workflow (same gate)
def test_m03_reject_unverified(svc):
    dec = svc.promote(_cand(svc, verified=False), registered_tools=REGISTERED)
    assert not dec.promoted


# M04 retrieve semantically similar workflow
def test_m04_semantic_retrieval(svc):
    svc.promote(_cand(svc), registered_tools=REGISTERED)
    hits = svc.search("clean up this word file and save it", tenant_id="org_local", workspace_id="ws_local")
    assert hits
    assert hits[0].workflow.canonical_name == "Edit Word document"


# M05 reject unauthorized workflow (permission scope)
def test_m05_permission_scope(svc):
    svc.promote(_cand(svc, scope=("finance:use",)), registered_tools=REGISTERED)
    # caller without finance:use permission
    hits = svc.search("edit word document", tenant_id="org_local", workspace_id="ws_local", permissions=frozenset())
    assert hits == []


# M06 tenant isolation
def test_m06_tenant_isolation(svc):
    svc.promote(_cand(svc, tenant="org_a"), registered_tools=REGISTERED)
    svc.promote(_cand(svc, tenant="org_b", name="Edit Word document B"), registered_tools=REGISTERED)
    hits = svc.search("edit word document", tenant_id="org_a", workspace_id="ws_local")
    assert all(h.workflow.tenant_id == "org_a" for h in hits)


# M07 workspace isolation
def test_m07_workspace_isolation(svc):
    svc.promote(_cand(svc, ws="ws_finance"), registered_tools=REGISTERED)
    svc.promote(_cand(svc, ws="ws_eng", name="Edit Word document Eng"), registered_tools=REGISTERED)
    hits = svc.search("edit word document", tenant_id="org_local", workspace_id="ws_finance")
    assert all(h.workflow.workspace_id == "ws_finance" for h in hits)


# M08 version creation
def test_m08_version_creation(svc):
    d1 = svc.promote(_cand(svc), registered_tools=REGISTERED)
    # a different trace with same canonical name -> new version
    t2 = _trace(intent="Edit a Word document, fix wording and save")
    t2["steps"].insert(1, {"tool": "document.edit", "args": {"extra": "step"}})
    d2 = svc.promote(
        svc.candidate_from_trace(t2, tenant_id="org_local", workspace_id="ws_local",
                                 canonical_name="Edit Word document",
                                 source_execution_ids=("exec_2",), source_task_id="task_2", verified=True),
        registered_tools=REGISTERED,
    )
    assert d2.promoted
    assert d2.version == 2
    vers = svc.versions(d2.workflow_id)
    assert len(vers) == 2


# M09 same workflow reused (identical content -> no duplicate)
def test_m09_same_reused(svc):
    d1 = svc.promote(_cand(svc), registered_tools=REGISTERED)
    d2 = svc.promote(_cand(svc), registered_tools=REGISTERED)  # identical
    assert d1.workflow_id == d2.workflow_id
    assert svc.list_workflows(tenant_id="org_local", workspace_id="ws_local").__len__() == 1


# M10 parameter adaptation
def test_m10_parameter_binding(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    wf = svc.get(dec.workflow_id)
    bound = svc.bind_parameters(wf, {"path": "/y/other.docx", "target_path": "/y/other.docx"})
    save_step = [s for s in bound.steps if s.tool == "document.save"][0]
    assert save_step.parameters["target_path"] == "/y/other.docx"


# M11 incompatible workflow (missing tool)
def test_m11_incompatible(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    hits = svc.search(
        "edit word document", tenant_id="org_local", workspace_id="ws_local",
        available_tools=set(),  # no tools available
        available_capabilities=set(),
    )
    assert hits
    from autoflow_ai.memory.models import CompatibilityLevel

    assert hits[0].compatibility == CompatibilityLevel.INCOMPATIBLE


# M12 blocked workflow not returned/executable
def test_m12_blocked(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    svc.block(dec.workflow_id)
    assert svc.get(dec.workflow_id).status == WorkflowStatus.BLOCKED
    hits = svc.search("edit word document", tenant_id="org_local", workspace_id="ws_local")
    assert all(h.workflow.workflow_id != dec.workflow_id for h in hits)


# M13 deprecated workflow deprioritized
def test_m13_deprecated(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    svc.deprecate(dec.workflow_id)
    assert svc.get(dec.workflow_id).status == WorkflowStatus.DEPRECATED
    hits = svc.search("edit word document", tenant_id="org_local", workspace_id="ws_local")
    # still returned (unless min_score filters) but penalized; if present, score halved
    if hits:
        assert hits[0].workflow.status == WorkflowStatus.DEPRECATED


# M14 workflow score updates
def test_m14_score_and_usage(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    svc.record_usage(dec.workflow_id, success=True, verified=True)
    wf = svc.get(dec.workflow_id)
    assert wf.usage_count >= 2


# M15 provenance preserved
def test_m15_provenance(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    wf = svc.get(dec.workflow_id)
    assert wf.provenance.source_execution_ids == ("exec_1",)
    assert wf.provenance.source_task_id == "task_1"


# M17 candidate creation + M18 promotion
def test_m17_m18_candidate_and_promotion(svc):
    cand = _cand(svc)
    assert cand.verified
    dec = svc.promote(cand, registered_tools=REGISTERED)
    assert dec.promoted


# M19 failed execution updates failure stats but not activated
def test_m19_failure_stats(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    svc.record_failure(dec.workflow_id, "UI_CHANGED")
    wf = svc.get(dec.workflow_id)
    assert wf.failure_count == 1
    assert wf.status == WorkflowStatus.ACTIVE  # failure recorded, not auto-blocked


# M20 workflow invalidation (block then restore)
def test_m20_invalidation_restore(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    svc.block(dec.workflow_id)
    svc.restore(dec.workflow_id)
    assert svc.get(dec.workflow_id).status == WorkflowStatus.ACTIVE


# security: secret in workflow rejected
def test_secret_workflow_rejected(svc):
    t = _trace()
    # put the secret in a non-parameterized arg so it survives normalization
    t["steps"][1]["args"]["note"] = "auth with api_key=sk-abcdef0123456789abcdef please"
    cand = svc.candidate_from_trace(
        t, tenant_id="org_local", workspace_id="ws_local", canonical_name="Sneaky",
        source_execution_ids=("exec_1",), source_task_id="task_1", verified=True,
    )
    dec = svc.promote(cand, registered_tools=REGISTERED)
    assert not dec.promoted
    assert any("secret" in r for r in dec.rejected_reasons)


def test_contains_secret_detects_keys():
    assert contains_secret("api_key=sk-1234567890abcdef1234")
    assert contains_secret("nvapi-abcdefghij1234567890")
    assert not contains_secret("just a normal document about sales")


# unregistered tool rejected
def test_unregistered_tool_rejected(svc):
    t = {"intent": "do thing", "steps": [{"tool": "danger.shell", "args": {"cmd": "rm -rf /"}}]}
    cand = svc.candidate_from_trace(
        t, tenant_id="org_local", workspace_id="ws_local", canonical_name="Danger",
        source_execution_ids=("exec_1",), source_task_id="task_1", verified=True,
    )
    dec = svc.promote(cand, registered_tools=REGISTERED)
    assert not dec.promoted
    assert any("unregistered tools" in r for r in dec.rejected_reasons)


# session memory bounded
def test_session_memory_bounded():
    s = SessionMemory(task_id="task_1", max_history=3)
    for i in range(10):
        s.add_observation(f"obs {i}")
    assert len(s.observations) == 3
    assert s.observations[-1] == "obs 9"


def test_session_snapshot_restore():
    s = SessionMemory(task_id="task_1", variables={"a": 1})
    snap = s.snapshot()
    restored = SessionMemory.restore(snap)
    assert restored.variables == {"a": 1}


# graph memory
def test_graph_memory_records_relationships(svc):
    dec = svc.promote(_cand(svc), registered_tools=REGISTERED)
    q = svc.graph.query(dec.workflow_id)
    relations = {e["relation"] for e in q["edges"]}
    assert "USES" in relations


# content hash determinism
def test_workflow_hash_deterministic(svc):
    c1 = _cand(svc)
    c2 = _cand(svc)
    assert c1.content_hash == c2.content_hash
    assert c1.content_hash == workflow_content_hash(c1.workflow)


def test_status_reports_counts(svc):
    svc.promote(_cand(svc), registered_tools=REGISTERED)
    st = svc.status()
    assert st["workflows"] == 1
    assert st["index_health"] is True

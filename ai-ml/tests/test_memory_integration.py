"""Memory + Context/RAG separation and reuse-demo integration tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import docx
import pytest

from autoflow_ai.context import ContextSection
from autoflow_ai.context.trust import TrustLevel
from autoflow_ai.memory import build_memory_service
from autoflow_ai.memory.config import load_memory_config
from autoflow_ai.orchestrator import AutoFlow
from autoflow_ai.rag import build_knowledge_service
from autoflow_ai.rag.config import load_rag_config

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "sample.docx"
REGISTERED = {"document.inspect", "document.edit", "document.save"}


@pytest.fixture
def memsvc(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    cfg = load_memory_config(
        db_path_override=str(tmp_path / "m.sqlite"), collection_override="autoflow_workflows"
    )
    return build_memory_service(config=cfg, chroma_path_override=str(tmp_path / "chroma"))


@pytest.fixture
def knowsvc(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    cfg = load_rag_config(chroma_path_override=str(tmp_path / "chroma_k"))
    return build_knowledge_service(config=cfg)


def _doc_trace():
    return {
        "intent": "Edit a Word document and save it",
        "steps": [
            {"tool": "document.inspect", "args": {"path": "/x/a.docx"}},
            {"tool": "document.edit", "args": {"operations": []}},
            {"tool": "document.save", "args": {"target_path": "/x/a.docx"}},
            {"tool": "document.verify", "args": {}},
        ],
    }


def _promote(memsvc):
    cand = memsvc.candidate_from_trace(
        _doc_trace(), tenant_id="org_local", workspace_id="ws_local",
        canonical_name="Edit document", source_execution_ids=("exec_1",),
        source_task_id="task_1", verified=True,
    )
    return memsvc.promote(cand, registered_tools=REGISTERED)


# RAG != workflow memory (separation)
def test_rag_and_workflow_memory_are_separate(memsvc, knowsvc, tmp_path):
    # knowledge doc
    kf = tmp_path / "howto.md"
    kf.write_text("# How finance reporting works\nFinance compiles reports weekly.", encoding="utf-8")
    knowsvc.ingest(kf, tenant_id="org_local", workspace_id="ws_local")
    # workflow memory
    _promote(memsvc)

    k = knowsvc.search("finance reporting", tenant_id="org_local", workspace_id="ws_local")
    w = memsvc.search("edit document", tenant_id="org_local", workspace_id="ws_local")

    # knowledge search returns knowledge chunks (doc ids), not workflow ids
    assert k.results
    assert all(not r.document_id.startswith("wf_") for r in k.results)
    # workflow search returns workflow ids
    assert w
    assert all(h.workflow.workflow_id.startswith("wf_") for h in w)


def test_workflow_memory_enters_context_as_data(memsvc, tmp_path):
    _promote(memsvc)
    app = AutoFlow.build(memory=memsvc)
    note = tmp_path / "note.txt"
    note.write_text("placeholder", encoding="utf-8")
    bundle = app.build_context("clean up this word file and save it", target_path=str(note))
    wf_items = bundle.items_for(ContextSection.WORKFLOW_MEMORY)
    assert wf_items
    assert all(it.trust_level == TrustLevel.AUTHORIZED_MEMORY for it in wf_items)
    prompt = bundle.render_prompt()
    assert "<data trust=authorized_memory" in prompt


def test_learn_from_run_creates_and_promotes(tmp_path, memsvc):
    """Golden 51: run a real document edit, then learn a reusable workflow."""

    dest = tmp_path / "g.docx"
    shutil.copy(FIXTURE, dest)
    app = AutoFlow.build(memory=memsvc)
    report = app.run(
        'Edit this Word file, fix wording, normalize em-dashes, remove double spaces, and save. Replace "teh" with "the".',
        target_path=str(dest),
    )
    assert report.ok
    decision = app.learn_from_run("edit this word document and save it", report, target_path=str(dest))
    assert decision is not None
    assert decision.promoted, decision.rejected_reasons

    # SECOND run: the workflow is now retrievable semantically
    hits = memsvc.search("clean up another word document and save", tenant_id="org_local", workspace_id="ws_local")
    assert hits, "expected the learned workflow to be retrievable"


def test_golden01_unaffected_without_memory(tmp_path):
    dest = tmp_path / "g.docx"
    shutil.copy(FIXTURE, dest)
    app = AutoFlow.build()  # no memory attached
    report = app.run(
        'Edit this Word file, fix wording, and save. Replace "teh" with "the".',
        target_path=str(dest),
    )
    assert report.ok
    text = "\n".join(p.text for p in docx.Document(str(dest)).paragraphs)
    assert "teh" not in text

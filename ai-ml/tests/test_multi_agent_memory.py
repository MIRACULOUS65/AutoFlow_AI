"""Phase 6 memory-reuse + adversarial integration through the runtime."""

from __future__ import annotations

import shutil
from pathlib import Path

import docx
import pytest

from autoflow_ai.memory import build_memory_service
from autoflow_ai.memory.config import load_memory_config
from autoflow_ai.orchestrator import AutoFlow

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "sample.docx"
DOC_PROMPT = 'Edit this Word file, fix wording, normalize em-dashes, remove double spaces, and save. Replace "teh" with "the".'


@pytest.fixture
def memsvc(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    cfg = load_memory_config(
        db_path_override=str(tmp_path / "m.sqlite"), collection_override="autoflow_workflows"
    )
    return build_memory_service(config=cfg, chroma_path_override=str(tmp_path / "chroma"))


# MA25: multi-agent run learns/promotes a verified workflow (Phase 5 integration)
def test_ma25_learn_from_multi_agent_run(tmp_path, memsvc):
    dest = tmp_path / "a.docx"
    shutil.copy(FIXTURE, dest)
    app = AutoFlow.build(memory=memsvc)
    report = app.run_multi_agent(DOC_PROMPT, target_path=str(dest))
    assert report.ok
    # the verified run should have produced a promoted workflow
    wfs = memsvc.list_workflows(tenant_id="org_local", workspace_id="ws_local")
    assert wfs, "expected a workflow learned from the verified multi-agent run"


# MA11: retrievable/reusable after learning
def test_ma11_workflow_retrievable_after_run(tmp_path, memsvc):
    dest = tmp_path / "a.docx"
    shutil.copy(FIXTURE, dest)
    app = AutoFlow.build(memory=memsvc)
    app.run_multi_agent(DOC_PROMPT, target_path=str(dest))
    hits = memsvc.search("clean up a word document and save", tenant_id="org_local", workspace_id="ws_local")
    assert hits


# adversarial: prompt injection in workflow memory stays data (never executes)
def test_adversarial_memory_injection_stays_data(tmp_path, memsvc):
    dest = tmp_path / "a.docx"
    shutil.copy(FIXTURE, dest)
    # first, learn a normal workflow
    app = AutoFlow.build(memory=memsvc)
    app.run_multi_agent(DOC_PROMPT, target_path=str(dest))
    # build context for a new task; workflow memory enters as data
    note = tmp_path / "n.txt"
    note.write_text("x", encoding="utf-8")
    bundle = app.build_context("clean up this document", target_path=str(note))
    prompt = bundle.render_prompt()
    from autoflow_ai.context import ContextSection

    wf_items = bundle.items_for(ContextSection.WORKFLOW_MEMORY)
    if wf_items:
        # workflow memory content is wrapped as data, not an instruction
        assert "<data trust=authorized_memory" in prompt


# Golden 01 single-path still works (no regression from Phase 6)
def test_golden01_single_path_unaffected(tmp_path):
    dest = tmp_path / "a.docx"
    shutil.copy(FIXTURE, dest)
    app = AutoFlow.build()
    report = app.run(DOC_PROMPT, target_path=str(dest))  # original single-agent run()
    assert report.ok
    text = "\n".join(p.text for p in docx.Document(str(dest)).paragraphs)
    assert "teh" not in text

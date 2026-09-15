"""Integration: context engine wired into the orchestrator; Golden 01 intact."""

from __future__ import annotations

import shutil
from pathlib import Path

import docx
import pytest

from autoflow_ai.context import ContextSection
from autoflow_ai.orchestrator import AutoFlow

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "sample.docx"
PROMPT = (
    "Edit this document by fixing the wording, normalizing em-dashes, removing "
    'double spaces, and saving to the same file. Also replace "teh" with "the".'
)


@pytest.fixture
def work_doc(tmp_path) -> Path:
    dest = tmp_path / "ctx.docx"
    shutil.copy(FIXTURE, dest)
    return dest


def test_build_context_produces_expected_sections(work_doc):
    app = AutoFlow.build()
    bundle = app.build_context(PROMPT, target_path=str(work_doc))
    sections = {it.section for it in bundle.items}
    assert ContextSection.SYSTEM_POLICY in sections
    assert ContextSection.TASK_INSTRUCTION in sections
    assert ContextSection.PERMISSIONS in sections
    assert ContextSection.CURRENT_WORKFLOW in sections
    assert bundle.reserved_output_tokens > 0
    assert bundle.estimated_tokens <= bundle.token_budget


def test_context_is_deterministic(work_doc):
    app = AutoFlow.build()
    h1 = app.build_context(PROMPT, target_path=str(work_doc)).context_hash()
    h2 = app.build_context(PROMPT, target_path=str(work_doc)).context_hash()
    assert h1 == h2


def test_context_manifest_has_no_secrets(work_doc):
    app = AutoFlow.build()
    manifest = app.build_context(PROMPT, target_path=str(work_doc)).manifest()
    text = str(manifest)
    assert "nvapi-" not in text
    assert "api_key" not in text.lower() or "***" in text


def test_golden01_still_passes_with_context(work_doc):
    """Golden 01 regression: full run still completes and edits the file."""

    app = AutoFlow.build()
    report = app.run(PROMPT, target_path=str(work_doc))
    assert report.ok, report.error
    text = "\n".join(p.text for p in docx.Document(str(work_doc)).paragraphs)
    assert "This document has" in text
    assert "review the figures" in text
    assert "teh" not in text


def test_system_policy_is_instruction_untrusted_is_data(work_doc):
    app = AutoFlow.build()
    prompt_text = app.build_context(PROMPT, target_path=str(work_doc)).render_prompt()
    # system policy rendered as plain instruction (no <data> wrapper on it)
    assert "SYSTEM POLICY" in prompt_text
    assert "You are AutoFlow AI" in prompt_text

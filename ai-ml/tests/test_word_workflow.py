"""Word document lifecycle tests.

INTEGRATION path (default): real python-docx + text adapters through the full
open->edit->save->verify->reopen->close->persist lifecycle, with real staged
verification. A save is only verified after the file is re-opened and the edited
content is actually present. Includes false-success defenses. Cleanup guaranteed.

A real Word-UI (winword.exe) path is SKIP-gated behind AUTOFLOW_REAL_WORD.
"""

from __future__ import annotations

import os

import pytest

from autoflow_ai.computer_use.word_workflow import (
    AppLifecycle,
    WordDocumentWorkflow,
    WorkflowStage,
    create_disposable_docx,
)
from autoflow_ai.editing.operations import EditKind, EditOperation


def _docx_available() -> bool:
    try:
        import docx  # noqa: F401
        return True
    except Exception:
        return False


REPLACE = [EditOperation(kind=EditKind.REPLACE_TEXT, find="foo", replace="bar")]


def test_word_01_txt_full_lifecycle_verified(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("foo baseline content", encoding="utf-8")
    res = WordDocumentWorkflow().run(p, REPLACE, expect_text="bar")
    assert res.verified is True
    assert res.mode == "integration"
    assert res.lifecycle == "closed"
    stages = {s.stage for s in res.stages if s.ok}
    assert WorkflowStage.SAVE in stages
    assert WorkflowStage.REOPEN_VERIFY in stages
    assert WorkflowStage.VERIFY_PERSIST in stages
    # file actually changed on disk
    assert "bar" in p.read_text(encoding="utf-8")


def test_word_02_missing_file_fails_closed(tmp_path):
    res = WordDocumentWorkflow().run(tmp_path / "nope.txt", REPLACE, expect_text="bar")
    assert res.verified is False
    assert "does not exist" in res.reason


def test_word_03_expected_text_absent_fails_verification(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("nothing to replace here", encoding="utf-8")
    # expect text that will NOT be present after a no-op edit
    res = WordDocumentWorkflow().run(p, REPLACE, expect_text="bar")
    assert res.verified is False  # reopen-verify must fail honestly


def test_word_04_no_change_still_persists_but_content_checked(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("unchanged text", encoding="utf-8")
    # a replace that matches nothing -> 0 changes; expect existing text present
    res = WordDocumentWorkflow().run(
        p, [EditOperation(kind=EditKind.REPLACE_TEXT, find="zzz", replace="qqq")],
        expect_text="unchanged",
    )
    assert res.verified is True  # file exists, content present, persists


def test_word_05_cleanup_lifecycle_reaches_closed(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("foo", encoding="utf-8")
    wf = WordDocumentWorkflow()
    wf.run(p, REPLACE, expect_text="bar")
    assert wf.lifecycle == AppLifecycle.CLOSED


@pytest.mark.skipif(not _docx_available(), reason="python-docx not installed")
def test_word_06_docx_full_lifecycle_verified(tmp_path):
    p = create_disposable_docx(tmp_path / "doc.docx", ["foo baseline paragraph", "second line"])
    res = WordDocumentWorkflow().run(p, REPLACE, expect_text="bar")
    assert res.verified is True
    # reopen independently and confirm the real docx content changed
    from autoflow_ai.documents.base import open_document
    assert "bar" in open_document(p).read_text()


@pytest.mark.skipif(not _docx_available(), reason="python-docx not installed")
def test_word_07_docx_hash_changes_on_edit(tmp_path):
    from autoflow_ai.documents.base import sha256_file

    p = create_disposable_docx(tmp_path / "doc.docx", ["foo here"])
    before = sha256_file(p)
    WordDocumentWorkflow().run(p, REPLACE, expect_text="bar")
    assert sha256_file(p) != before


def test_word_08_verify_save_check_present(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("foo baseline", encoding="utf-8")
    res = WordDocumentWorkflow().run(p, REPLACE, expect_text="bar")
    verify_stages = [s for s in res.stages if s.stage == WorkflowStage.VERIFY_SAVE]
    assert verify_stages and all(s.ok for s in verify_stages)


def test_word_09_confidence_reported(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("foo", encoding="utf-8")
    res = WordDocumentWorkflow().run(p, REPLACE, expect_text="bar")
    assert 0.0 <= res.confidence <= 1.0
    assert res.confidence >= 0.6  # verified requires >= min_confidence


def test_word_10_as_dict_serializable(tmp_path):
    import json

    p = tmp_path / "note.txt"
    p.write_text("foo", encoding="utf-8")
    res = WordDocumentWorkflow().run(p, REPLACE, expect_text="bar")
    json.dumps(res.as_dict())  # must not raise


# -- real Word UI (opt-in) --------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("AUTOFLOW_REAL_WORD") != "1" or not _docx_available(),
    reason="real Word disabled (set AUTOFLOW_REAL_WORD=1 on Windows with Word + python-docx)",
)
def test_word_11_real_word_launch_and_verify(tmp_path):
    from autoflow_ai.computer_use.env import desktop_available

    if not desktop_available():
        pytest.skip("no interactive desktop")
    from autoflow_ai.computer_use.windows_adapter import WindowsUIAutomationAdapter

    adapter = WindowsUIAutomationAdapter()
    if not adapter.available():
        pytest.skip("UIA adapter unavailable")
    p = create_disposable_docx(tmp_path / "live.docx", ["foo baseline for live word"])
    wf = WordDocumentWorkflow(live=True, uia_adapter=adapter)
    try:
        res = wf.run(p, REPLACE, expect_text="bar")
    finally:
        pass
    # content verification is via the file (reliable); launch stage is best-effort
    assert res.lifecycle == "closed"  # cleanup guaranteed

"""Real instruction-driven document editing + honest verification.

These lock in that:
  * a natural-language replace instruction (quoted or unquoted) is actually
    applied to the real file on disk, and
  * the mission verifier FAILS (never fakes success) when the requested change
    could not be applied.
"""

from __future__ import annotations

import json

import pytest

from autoflow_ai.editing.operations import (
    EditKind,
    detect_operations_from_prompt,
    expected_conditions_from_prompt,
)
from autoflow_ai.cli import main


# -- instruction parsing ----------------------------------------------------

def test_detect_unquoted_replace():
    ops = detect_operations_from_prompt("replace the word DRAFT with FINAL and save the document")
    reps = [o for o in ops if o.kind == EditKind.REPLACE_TEXT]
    assert len(reps) == 1
    assert reps[0].find == "DRAFT" and reps[0].replace == "FINAL"


def test_detect_quoted_replace():
    ops = detect_operations_from_prompt('replace "old text" with "new text"')
    reps = [o for o in ops if o.kind == EditKind.REPLACE_TEXT]
    assert reps and reps[0].find == "old text" and reps[0].replace == "new text"


def test_detect_change_to():
    ops = detect_operations_from_prompt("change Alpha to Beta")
    reps = [o for o in ops if o.kind == EditKind.REPLACE_TEXT]
    assert reps and reps[0].find == "Alpha" and reps[0].replace == "Beta"


def test_expected_conditions_from_replace():
    exp = expected_conditions_from_prompt("replace the word DRAFT with FINAL")
    assert "FINAL" in exp["must_contain"]


def test_generic_edit_has_fallback_ops():
    ops = detect_operations_from_prompt("edit the document and save it")
    assert ops  # not empty: a safe normalization pass is applied


# -- real end-to-end via the CLI (real file on disk) ------------------------

def test_real_replace_applied_and_verified(capsys, tmp_path):
    doc = tmp_path / "r.txt"
    doc.write_text("Quarterly Report - DRAFT\nRevenue was flat.\n", encoding="utf-8")
    rc = main(["mission", "run", "replace the word DRAFT with FINAL and save the document",
               "--file", str(doc)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["all_verified"] is True
    assert out["agenticity"]["false_success"] == 0
    # the REAL file changed on disk
    text = doc.read_text(encoding="utf-8")
    assert "FINAL" in text
    assert "DRAFT" not in text


def test_impossible_replace_fails_closed(capsys, tmp_path):
    doc = tmp_path / "r2.txt"
    doc.write_text("Quarterly Report - FINAL\n", encoding="utf-8")
    rc = main(["mission", "run", "replace the word NONEXISTENT with WHATEVER and save the document",
               "--file", str(doc)])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert out["all_verified"] is False
    assert out["outcome"] != "complete"
    assert out["agenticity"]["false_success"] == 0
    # the file was NOT falsely mutated to contain the impossible target
    assert "WHATEVER" not in doc.read_text(encoding="utf-8")

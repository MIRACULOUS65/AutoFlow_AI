"""Unit tests for structured edit operations."""

from __future__ import annotations

import pytest

from autoflow_ai.editing.operations import (
    EditKind,
    EditOperation,
    apply_operation,
    apply_operations,
    detect_operations_from_prompt,
)

pytestmark = pytest.mark.unit

EM = "\u2014"


def test_remove_double_spaces():
    op = EditOperation(kind=EditKind.REMOVE_DOUBLE_SPACES)
    out, n = apply_operation("a  b   c", op)
    assert out == "a b c"
    assert n == 2


def test_normalize_em_dashes_variants():
    op = EditOperation(kind=EditKind.NORMALIZE_EM_DASHES)
    out, n = apply_operation("a -- b", op)
    assert out == f"a {EM} b"
    assert n >= 1
    out2, _ = apply_operation("x--y", op)
    assert out2 == f"x{EM}y"


def test_fix_space_before_punct():
    op = EditOperation(kind=EditKind.FIX_SPACE_BEFORE_PUNCT)
    out, n = apply_operation("word . next , end !", op)
    assert out == "word. next, end!"
    assert n == 3


def test_replace_text_case_sensitive():
    op = EditOperation(kind=EditKind.REPLACE_TEXT, find="teh", replace="the")
    out, n = apply_operation("teh cat and Teh dog", op)
    assert out == "the cat and Teh dog"
    assert n == 1


def test_replace_text_case_insensitive():
    op = EditOperation(kind=EditKind.REPLACE_TEXT, find="teh", replace="the", case_sensitive=False)
    out, n = apply_operation("teh cat and Teh dog", op)
    assert out == "the cat and the dog"
    assert n == 2


def test_trim_trailing_whitespace():
    op = EditOperation(kind=EditKind.TRIM_TRAILING_WHITESPACE)
    out, n = apply_operation("a  \nb\t\nc", op)
    assert out == "a\nb\nc"
    assert n == 2


def test_apply_operations_in_order_reports_counts():
    ops = [
        EditOperation(kind=EditKind.REMOVE_DOUBLE_SPACES),
        EditOperation(kind=EditKind.FIX_SPACE_BEFORE_PUNCT),
    ]
    out, report = apply_operations("a  b .", ops)
    assert out == "a b."
    assert [desc for desc, _ in report] == ["remove_double_spaces", "fix_space_before_punct"]


def test_noop_edit_leaves_text_unchanged():
    op = EditOperation(kind=EditKind.REMOVE_DOUBLE_SPACES)
    out, n = apply_operation("already clean", op)
    assert out == "already clean"
    assert n == 0


def test_detect_operations_from_prompt():
    ops = detect_operations_from_prompt(
        "fix the wording, normalize em-dashes and remove double spaces"
    )
    kinds = {o.kind for o in ops}
    assert EditKind.NORMALIZE_EM_DASHES in kinds
    assert EditKind.REMOVE_DOUBLE_SPACES in kinds
    assert EditKind.FIX_SPACE_BEFORE_PUNCT in kinds


def test_detect_explicit_replace():
    ops = detect_operations_from_prompt('replace "teh" with "the"')
    assert any(o.kind == EditKind.REPLACE_TEXT and o.find == "teh" for o in ops)

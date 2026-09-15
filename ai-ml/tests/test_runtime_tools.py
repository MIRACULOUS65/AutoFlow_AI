"""Tests for the tool registry and document tools (validation + execution)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from autoflow_ai.runtime.document_tools import DocumentSession, register_document_tools
from autoflow_ai.runtime.registry import ToolRegistry
from autoflow_ai.schemas.tools import ToolCallRequest

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).parent / "fixtures" / "sample.docx"


@pytest.fixture
def wired(tmp_path):
    reg = ToolRegistry()
    session = DocumentSession()
    register_document_tools(reg, session)
    dest = tmp_path / "work.docx"
    shutil.copy(FIXTURE, dest)
    return reg, session, dest


def _call(tool, args, step="step_x"):
    return ToolCallRequest(
        tool_call_id=f"tcall_{step[-1]}",
        tool_name=tool,
        arguments=args,
        execution_id="exec_t1",
        step_id=step,
    )


# 12. unknown tool is rejected
def test_unknown_tool_rejected(wired):
    reg, _, _ = wired
    result = reg.execute(_call("does.not.exist", {}))
    assert not result.ok
    assert result.error_type == "unknown_tool"


# 11. invalid tool call (bad args) is rejected
def test_invalid_arguments_rejected(wired):
    reg, _, _ = wired
    # document.inspect requires 'path'
    result = reg.execute(_call("document.inspect", {}))
    assert not result.ok
    assert result.error_type == "invalid_arguments"


def test_unknown_argument_rejected(wired):
    reg, _, dest = wired
    result = reg.execute(_call("document.inspect", {"path": str(dest), "bogus": 1}))
    assert not result.ok
    assert result.error_type == "invalid_arguments"


def test_inspect_then_edit_then_save(wired):
    reg, session, dest = wired
    r1 = reg.execute(_call("document.inspect", {"path": str(dest)}))
    assert r1.ok
    assert r1.output["char_count"] > 0

    ops = [{"kind": "remove_double_spaces"}, {"kind": "normalize_em_dashes"}]
    r2 = reg.execute(_call("document.edit", {"operations": ops}))
    assert r2.ok
    assert r2.output["total_changes"] >= 1

    r3 = reg.execute(_call("document.save", {}))
    assert r3.ok
    assert r3.output["same_file"] is True
    assert r3.output["changed"] is True
    assert r3.output["hash_before"] != r3.output["hash_after"]


def test_edit_before_inspect_fails(wired):
    reg, _, _ = wired
    result = reg.execute(_call("document.edit", {"operations": []}))
    assert not result.ok
    assert result.error_type == "no_document"


def test_inspect_missing_file_fails(wired, tmp_path):
    reg, _, _ = wired
    result = reg.execute(_call("document.inspect", {"path": str(tmp_path / "ghost.docx")}))
    assert not result.ok
    assert result.error_type == "document_open_failed"


def test_edit_invalid_kind_fails(wired):
    reg, _, dest = wired
    reg.execute(_call("document.inspect", {"path": str(dest)}))
    result = reg.execute(_call("document.edit", {"operations": [{"kind": "nonsense"}]}))
    assert not result.ok
    assert result.error_type == "invalid_arguments"


def test_double_registration_rejected(wired):
    reg, session, _ = wired
    with pytest.raises(ValueError, match="already registered"):
        register_document_tools(reg, session)

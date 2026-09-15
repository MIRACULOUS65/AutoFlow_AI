"""Tests for tool contracts and argument validation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autoflow_ai.schemas import (
    RiskClass,
    ToolCallRequest,
    ToolCallResult,
    ToolDefinition,
    validate_tool_arguments,
)

pytestmark = pytest.mark.contract


def _tool(**overrides) -> ToolDefinition:
    base = dict(
        name="files.write",
        description="write a file",
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "size": {"type": "integer"},
                "mode": {"type": "string", "enum": ["overwrite", "append"]},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        risk_class=RiskClass.LOW,
        permission_scope="files:write",
    )
    base.update(overrides)
    return ToolDefinition(**base)


def test_tool_name_must_be_dotted_lowercase():
    _tool(name="a.b")
    for bad in ("noDot", "A.B", "a..b", "a.", ".b"):
        with pytest.raises(ValidationError):
            _tool(name=bad)


def test_high_risk_tool_must_require_approval():
    with pytest.raises(ValidationError, match="requires_approval"):
        _tool(name="email.send", risk_class=RiskClass.HIGH, requires_approval=False)
    _tool(name="email.send", risk_class=RiskClass.HIGH, requires_approval=True)


def test_input_schema_required_must_be_defined():
    with pytest.raises(ValidationError, match="required names not defined"):
        ToolDefinition(
            name="x.y",
            description="d",
            permission_scope="s",
            input_schema={
                "type": "object",
                "properties": {"a": {"type": "string"}},
                "required": ["b"],
            },
        )


def test_input_schema_top_level_must_be_object():
    with pytest.raises(ValidationError, match="top-level type must be 'object'"):
        ToolDefinition(
            name="x.y",
            description="d",
            permission_scope="s",
            input_schema={"type": "array"},
        )


def test_validate_arguments_accepts_valid():
    tool = _tool()
    validate_tool_arguments(tool, {"path": "/tmp/a", "size": 10, "mode": "append"})


def test_validate_arguments_missing_required():
    with pytest.raises(ValueError, match="missing required"):
        validate_tool_arguments(_tool(), {"size": 1})


def test_validate_arguments_unknown_when_additional_false():
    with pytest.raises(ValueError, match="unknown arguments"):
        validate_tool_arguments(_tool(), {"path": "/a", "extra": 1})


def test_validate_arguments_type_mismatch():
    with pytest.raises(ValueError, match="must be integer"):
        validate_tool_arguments(_tool(), {"path": "/a", "size": "big"})


def test_validate_arguments_bool_is_not_integer():
    with pytest.raises(ValueError, match="must be integer, got boolean"):
        validate_tool_arguments(_tool(), {"path": "/a", "size": True})


def test_validate_arguments_enum_enforced():
    with pytest.raises(ValueError, match="must be one of"):
        validate_tool_arguments(_tool(), {"path": "/a", "mode": "delete"})


def test_tool_call_idempotency_key():
    call = ToolCallRequest(
        tool_call_id="tcall_1",
        tool_name="files.write",
        execution_id="exec_1",
        step_id="step_1",
        attempt=2,
    )
    assert call.idempotency_key == "exec_1:step_1:2"


def test_tool_call_result_error_consistency():
    # failed result must carry an error
    with pytest.raises(ValidationError, match="must include error"):
        ToolCallResult(tool_call_id="tcall_1", tool_name="files.write", ok=False)
    # successful result must not carry an error
    with pytest.raises(ValidationError, match="must not include error"):
        ToolCallResult(
            tool_call_id="tcall_1",
            tool_name="files.write",
            ok=True,
            error_message="oops",
        )
    # valid failure
    ToolCallResult(
        tool_call_id="tcall_1",
        tool_name="files.write",
        ok=False,
        error_type="io_error",
    )

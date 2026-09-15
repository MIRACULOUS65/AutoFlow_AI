"""Tool contracts.

Tools are the only path to side effects. A tool call must reference a
*registered* tool (never invented), pass schema validation, and carry the
identity needed for idempotency. Argument validation against a tool's
``input_schema`` is provided by :func:`validate_tool_arguments`.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import Field, field_validator, model_validator

from .common import IdStr, VersionedModel, validate_id
from .enums import RiskClass

_TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")


class ToolDefinition(VersionedModel):
    """A registered, executable tool (EXECUTION_RUNTIME.md §4, §8).

    ``input_schema`` is a JSON-Schema-like dict describing arguments. We keep
    it as a validated dict here (full JSON Schema execution lives in the
    tool-calling layer in a later phase) but enforce a minimal shape.
    """

    name: str = Field(min_length=3, max_length=128)
    description: str = Field(min_length=1, max_length=1024)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    risk_class: RiskClass = RiskClass.LOW
    permission_scope: str = Field(min_length=1, max_length=128)
    requires_approval: bool = False
    timeout_seconds: float = Field(default=30.0, gt=0, le=3600)
    idempotent: bool = False
    connector: str | None = Field(default=None, max_length=64)
    verifier: str | None = Field(default=None, max_length=128)

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not _TOOL_NAME_RE.match(v):
            raise ValueError(
                "tool name must be dotted lowercase, e.g. 'email.send' or "
                "'browser.click'"
            )
        return v

    @field_validator("input_schema")
    @classmethod
    def _schema_shape(cls, v: dict[str, Any]) -> dict[str, Any]:
        if v:
            t = v.get("type", "object")
            if t != "object":
                raise ValueError("tool input_schema top-level type must be 'object'")
            props = v.get("properties", {})
            if not isinstance(props, dict):
                raise ValueError("input_schema.properties must be an object")
            required = v.get("required", [])
            if not isinstance(required, list):
                raise ValueError("input_schema.required must be a list")
            missing = set(required) - set(props)
            if missing:
                raise ValueError(
                    f"required names not defined in properties: {sorted(missing)}"
                )
        return v

    @model_validator(mode="after")
    def _high_risk_needs_approval(self) -> "ToolDefinition":
        if self.risk_class in (RiskClass.HIGH, RiskClass.CRITICAL) and not self.requires_approval:
            raise ValueError(
                f"tool {self.name!r} is {self.risk_class} risk and must set "
                "requires_approval=True"
            )
        return self


class ToolCallRequest(VersionedModel):
    """A concrete, validated request to invoke a tool.

    Idempotency key is derived from execution/step/attempt so the runtime can
    detect prior completion of external side effects.
    """

    tool_call_id: IdStr
    tool_name: str = Field(min_length=3, max_length=128)
    arguments: dict[str, Any] = Field(default_factory=dict)
    execution_id: IdStr
    step_id: IdStr
    attempt: int = Field(default=1, ge=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    reason: str | None = Field(default=None, max_length=1024)

    @field_validator("tool_call_id")
    @classmethod
    def _tcid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="tcall")

    @field_validator("execution_id")
    @classmethod
    def _eid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="exec")

    @field_validator("step_id")
    @classmethod
    def _sid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="step")

    @field_validator("tool_name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not _TOOL_NAME_RE.match(v):
            raise ValueError("tool_name must be dotted lowercase, e.g. 'files.write'")
        return v

    @property
    def idempotency_key(self) -> str:
        return f"{self.execution_id}:{self.step_id}:{self.attempt}"


class ToolCallResult(VersionedModel):
    """Result of executing a tool. Success here is *not* business success."""

    tool_call_id: IdStr
    tool_name: str = Field(min_length=3, max_length=128)
    ok: bool
    output: dict[str, Any] | None = None
    error_type: str | None = Field(default=None, max_length=128)
    error_message: str | None = Field(default=None, max_length=2048)
    latency_ms: int | None = Field(default=None, ge=0)

    @field_validator("tool_call_id")
    @classmethod
    def _tcid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="tcall")

    @model_validator(mode="after")
    def _error_consistency(self) -> "ToolCallResult":
        if not self.ok and not (self.error_type or self.error_message):
            raise ValueError("failed tool result must include error_type/error_message")
        if self.ok and (self.error_type or self.error_message):
            raise ValueError("successful tool result must not include error fields")
        return self


def validate_tool_arguments(tool: ToolDefinition, arguments: dict[str, Any]) -> None:
    """Validate ``arguments`` against a tool's ``input_schema``.

    Minimal but real JSON-Schema subset: required presence, no unknown keys
    when ``additionalProperties`` is false, and primitive type checks. Raises
    ``ValueError`` on any violation.
    """

    schema = tool.input_schema or {}
    props: dict[str, Any] = schema.get("properties", {})
    required: list[str] = schema.get("required", [])
    additional = schema.get("additionalProperties", True)

    missing = [name for name in required if name not in arguments]
    if missing:
        raise ValueError(f"missing required arguments: {sorted(missing)}")

    if additional is False:
        unknown = set(arguments) - set(props)
        if unknown:
            raise ValueError(f"unknown arguments not allowed: {sorted(unknown)}")

    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    for key, value in arguments.items():
        spec = props.get(key)
        if not spec:
            continue
        expected = spec.get("type")
        if expected and expected in type_map:
            py_type = type_map[expected]
            # bool is a subclass of int; guard integer/number against bools.
            if expected in ("integer", "number") and isinstance(value, bool):
                raise ValueError(f"argument {key!r} must be {expected}, got boolean")
            if not isinstance(value, py_type):
                raise ValueError(
                    f"argument {key!r} must be {expected}, got {type(value).__name__}"
                )
        enum = spec.get("enum")
        if enum is not None and value not in enum:
            raise ValueError(f"argument {key!r} must be one of {enum}, got {value!r}")

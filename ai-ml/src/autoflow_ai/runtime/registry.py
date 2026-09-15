"""Tool registry mapping registered tool names to executable callables.

A tool is only executable when it is registered. The registry pairs the typed
:class:`ToolDefinition` (schema/risk/permission) with a Python callable that
performs the deterministic side effect. Argument validation uses the shared
``validate_tool_arguments`` before the callable runs.
"""

from __future__ import annotations

from typing import Any, Callable

from ..schemas.tools import ToolCallRequest, ToolCallResult, ToolDefinition, validate_tool_arguments

# Executor signature: (arguments) -> output dict
ToolExecutor = Callable[[dict[str, Any]], dict[str, Any]]


class ToolExecutionError(Exception):
    """A registered tool failed during execution."""

    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


class ToolRegistry:
    def __init__(self) -> None:
        self._defs: dict[str, ToolDefinition] = {}
        self._execs: dict[str, ToolExecutor] = {}

    def register(self, definition: ToolDefinition, executor: ToolExecutor) -> None:
        if definition.name in self._defs:
            raise ValueError(f"tool already registered: {definition.name}")
        self._defs[definition.name] = definition
        self._execs[definition.name] = executor

    def has(self, name: str) -> bool:
        return name in self._defs

    def definition(self, name: str) -> ToolDefinition:
        if name not in self._defs:
            raise KeyError(f"unknown tool: {name}")
        return self._defs[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._defs))

    def execute(self, call: ToolCallRequest) -> ToolCallResult:
        """Validate then execute a tool call. Never raises for tool failure;
        returns a ToolCallResult with ok=False instead."""

        # 1. tool must exist (never invent tools)
        if call.tool_name not in self._defs:
            return ToolCallResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                ok=False,
                error_type="unknown_tool",
                error_message=f"tool not registered: {call.tool_name}",
            )

        definition = self._defs[call.tool_name]

        # 2. arguments must satisfy the tool's input schema
        try:
            validate_tool_arguments(definition, call.arguments)
        except ValueError as exc:
            return ToolCallResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                ok=False,
                error_type="invalid_arguments",
                error_message=str(exc),
            )

        # 3. execute the deterministic side effect
        executor = self._execs[call.tool_name]
        try:
            output = executor(call.arguments)
        except ToolExecutionError as exc:
            return ToolCallResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                ok=False,
                error_type=exc.error_type,
                error_message=exc.message,
            )
        except Exception as exc:  # noqa: BLE001 - normalize unexpected errors
            return ToolCallResult(
                tool_call_id=call.tool_call_id,
                tool_name=call.tool_name,
                ok=False,
                error_type="tool_error",
                error_message=repr(exc),
            )

        return ToolCallResult(
            tool_call_id=call.tool_call_id,
            tool_name=call.tool_name,
            ok=True,
            output=output,
        )

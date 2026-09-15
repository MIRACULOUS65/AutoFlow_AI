"""Deterministic tool runtime and execution engine.

The runtime is the *hands* of AutoFlow. Models/agents propose semantic actions;
the runtime validates them against the tool registry and permissions, then
performs the real side effect and returns a structured result. No LLM gets
arbitrary filesystem or shell access.
"""

from __future__ import annotations

from .registry import ToolRegistry, ToolExecutor, ToolExecutionError
from .document_tools import DocumentSession, register_document_tools
from .engine import ExecutionEngine, ExecutionReport, TraceEntry

__all__ = [
    "ToolRegistry",
    "ToolExecutor",
    "ToolExecutionError",
    "DocumentSession",
    "register_document_tools",
    "ExecutionEngine",
    "ExecutionReport",
    "TraceEntry",
]

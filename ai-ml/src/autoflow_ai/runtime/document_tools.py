"""Deterministic document tools: inspect, edit, save.

These are the only path to document side effects. They operate on a
:class:`DocumentSession` that holds the opened adapter so a plan can chain
inspect -> edit -> save against the same document. The tools translate typed
arguments into real python-docx / text operations and return structured output
(hashes, change counts, extracted text) used for observation and verification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..documents.base import DocumentError, open_document, sha256_file
from ..editing.operations import EditKind, EditOperation
from ..schemas.enums import RiskClass
from ..schemas.tools import ToolDefinition
from .registry import ToolExecutionError, ToolRegistry


class DocumentSession:
    """Mutable per-execution state shared by the document tools."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.adapter = None
        self.hash_before: str | None = None
        self.hash_after: str | None = None
        self.last_edit_report: list[tuple[str, int]] = []


def _ops_from_args(raw_ops: list[dict[str, Any]]) -> list[EditOperation]:
    ops: list[EditOperation] = []
    valid_kinds = {k.value for k in EditKind}
    for item in raw_ops:
        kind = item.get("kind")
        if kind not in valid_kinds:
            raise ToolExecutionError("invalid_arguments", f"unknown edit kind: {kind!r}")
        ops.append(EditOperation(**item))
    return ops


def register_document_tools(registry: ToolRegistry, session: DocumentSession) -> None:
    """Register document.inspect / document.edit / document.save."""

    # -- document.inspect ----------------------------------------------------
    inspect_def = ToolDefinition(
        name="document.inspect",
        description="Open a document and extract its text and metadata.",
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        risk_class=RiskClass.LOW,
        permission_scope="files:read",
        idempotent=True,
    )

    def _inspect(args: dict[str, Any]) -> dict[str, Any]:
        path = Path(args["path"])
        try:
            adapter = open_document(path)
        except DocumentError as exc:
            raise ToolExecutionError("document_open_failed", str(exc)) from exc
        session.path = path
        session.adapter = adapter
        session.hash_before = sha256_file(path)
        text = adapter.read_text()
        return {
            "path": str(path),
            "type": path.suffix.lower().lstrip("."),
            "char_count": len(text),
            "hash_before": session.hash_before,
            "text_preview": text[:280],
        }

    registry.register(inspect_def, _inspect)

    # -- document.edit -------------------------------------------------------
    edit_def = ToolDefinition(
        name="document.edit",
        description="Apply structured edit operations to the inspected document.",
        input_schema={
            "type": "object",
            "properties": {"operations": {"type": "array"}},
            "required": ["operations"],
            "additionalProperties": False,
        },
        risk_class=RiskClass.LOW,
        permission_scope="files:write",
        idempotent=False,
    )

    def _edit(args: dict[str, Any]) -> dict[str, Any]:
        if session.adapter is None:
            raise ToolExecutionError("no_document", "document.inspect must run first")
        ops = _ops_from_args(args["operations"])
        report = session.adapter.apply_operations(ops)
        session.last_edit_report = report
        total = sum(count for _, count in report)
        return {
            "operations": [{"description": d, "changes": c} for d, c in report],
            "total_changes": total,
        }

    registry.register(edit_def, _edit)

    # -- document.save -------------------------------------------------------
    save_def = ToolDefinition(
        name="document.save",
        description="Save the edited document (same path by default) and hash it.",
        input_schema={
            "type": "object",
            "properties": {"target_path": {"type": "string"}},
            "required": [],
            "additionalProperties": False,
        },
        risk_class=RiskClass.LOW,
        permission_scope="files:write",
        idempotent=True,
    )

    def _save(args: dict[str, Any]) -> dict[str, Any]:
        if session.adapter is None or session.path is None:
            raise ToolExecutionError("no_document", "document.inspect must run first")
        target = Path(args["target_path"]) if args.get("target_path") else session.path
        try:
            saved = session.adapter.save(target)
        except DocumentError as exc:
            raise ToolExecutionError("document_save_failed", str(exc)) from exc
        session.hash_after = sha256_file(saved)
        return {
            "saved_path": str(saved),
            "same_file": str(saved) == str(session.path),
            "hash_before": session.hash_before,
            "hash_after": session.hash_after,
            "changed": session.hash_before != session.hash_after,
        }

    registry.register(save_def, _save)

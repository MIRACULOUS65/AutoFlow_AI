"""Document adapter base and factory."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from ..editing.operations import EditOperation


class DocumentError(Exception):
    """A document could not be opened, edited, or saved safely."""


@runtime_checkable
class DocumentAdapter(Protocol):
    """Common interface for all document types."""

    path: Path

    def read_text(self) -> str:
        """Return the document's full plain text."""
        ...

    def apply_operations(self, ops: list[EditOperation]) -> list[tuple[str, int]]:
        """Apply edits in place; return [(description, change_count), ...]."""
        ...

    def save(self, target: Path | None = None) -> Path:
        """Persist the document (defaults to the same path)."""
        ...


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's bytes."""

    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_writable(path: Path) -> bool:
    if path.exists():
        return os.access(path, os.W_OK)
    parent = path.parent
    return parent.exists() and os.access(parent, os.W_OK)


def open_document(path: str | Path) -> DocumentAdapter:
    """Open a document by extension. Raises DocumentError on unsupported/missing."""

    p = Path(path)
    if not p.exists():
        raise DocumentError(f"file does not exist: {p}")
    if not p.is_file():
        raise DocumentError(f"not a file: {p}")

    suffix = p.suffix.lower()
    if suffix == ".docx":
        from .docx_adapter import DocxAdapter

        return DocxAdapter(p)
    if suffix in (".txt", ".md", ".markdown"):
        from .text_adapter import TextAdapter

        return TextAdapter(p)
    if suffix == ".xlsx":
        from .spreadsheet_adapter import SpreadsheetAdapter

        # Read/inspect an existing workbook. Building a NEW workbook uses
        # SpreadsheetAdapter(path, create=True) directly (spreadsheet tools),
        # not open_document, since a new file does not yet exist on disk.
        return SpreadsheetAdapter(p)
    raise DocumentError(f"unsupported document type: {suffix!r}")

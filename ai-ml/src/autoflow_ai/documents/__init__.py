"""Document adapters for real, deterministic file editing.

Adapters expose a common interface:
    * ``read_text()`` -> full text (for inspection/verification)
    * ``apply_operations(ops)`` -> applies edits, preserving structure
    * ``save(path)`` -> writes to a target path (same-file supported)

DOCX editing operates run-by-run to preserve paragraphs, runs and formatting
rather than rebuilding the document. TXT and MD operate on whole-file text.
"""

from __future__ import annotations

from .base import DocumentError, DocumentAdapter, open_document
from .docx_adapter import DocxAdapter
from .text_adapter import TextAdapter

__all__ = [
    "DocumentError",
    "DocumentAdapter",
    "open_document",
    "DocxAdapter",
    "TextAdapter",
]

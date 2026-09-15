"""Plain text / Markdown adapter."""

from __future__ import annotations

import os
from pathlib import Path

from ..editing.operations import EditOperation, apply_operations
from .base import DocumentError


class TextAdapter:
    """Whole-file text editing for .txt / .md."""

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self._text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise DocumentError(f"file is not valid UTF-8 text: {path}") from exc
        except OSError as exc:
            raise DocumentError(f"cannot read file: {path}: {exc}") from exc

    def read_text(self) -> str:
        return self._text

    def apply_operations(self, ops: list[EditOperation]) -> list[tuple[str, int]]:
        new_text, report = apply_operations(self._text, ops)
        self._text = new_text
        return report

    def save(self, target: Path | None = None) -> Path:
        dest = target or self.path
        if dest.exists() and not os.access(dest, os.W_OK):
            raise DocumentError(f"target is not writable: {dest}")
        try:
            dest.write_text(self._text, encoding="utf-8")
        except OSError as exc:
            raise DocumentError(f"cannot write file: {dest}: {exc}") from exc
        return dest

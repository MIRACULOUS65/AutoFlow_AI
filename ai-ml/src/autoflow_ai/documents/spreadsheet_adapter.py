"""XLSX adapter using openpyxl.

Spreadsheets are not edited run-by-run like prose documents; the real side
effect here is *building* a workbook from tabular data and later *reopening* it
to inspect sheets/columns/rows/cells for independent verification. This adapter
provides:

  - read side: ``read_text`` (a flat textual dump for inspection),
    ``sheet_names``, ``header``/``rows`` per sheet, and ``cell`` access;
  - build side: ``write_sheet`` + ``save`` to persist a real .xlsx on disk.

It intentionally does NOT implement ``apply_operations`` — spreadsheet edits are
expressed as whole-sheet writes, not text find/replace. The document tools that
require prose editing continue to use the docx/text adapters; the spreadsheet
tools (runtime/spreadsheet_tools.py) use this adapter directly.

Malformed / non-workbook files fail safely with ``DocumentError``.
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path
from typing import Any

from .base import DocumentError

try:  # guarded import so a missing dep degrades gracefully
    import openpyxl
    from openpyxl.utils.exceptions import InvalidFileException
except Exception:  # pragma: no cover - environment guard
    openpyxl = None
    InvalidFileException = Exception


class SpreadsheetAdapter:
    """Structure-aware .xlsx reading + building via openpyxl."""

    def __init__(self, path: Path, *, create: bool = False) -> None:
        if openpyxl is None:  # pragma: no cover - environment guard
            raise DocumentError("openpyxl is not installed")
        self.path = path
        if create:
            # A fresh, empty workbook to be populated then saved.
            self._wb = openpyxl.Workbook()
            # Remove the default sheet so callers add named sheets explicitly.
            default = self._wb.active
            if default is not None:
                self._wb.remove(default)
            return
        try:
            # data_only so formula cells return their last cached value; the
            # verifier reconciles concrete numbers, not formulas.
            self._wb = openpyxl.load_workbook(str(path), data_only=True)
        except (InvalidFileException, zipfile.BadZipFile) as exc:
            raise DocumentError(f"not a valid .xlsx workbook: {path}") from exc
        except Exception as exc:  # noqa: BLE001 - normalize to DocumentError
            raise DocumentError(f"cannot open .xlsx: {path}: {exc}") from exc

    # -- read side -----------------------------------------------------------

    def sheet_names(self) -> list[str]:
        return list(self._wb.sheetnames)

    def _ws(self, sheet: str):
        if sheet not in self._wb.sheetnames:
            raise DocumentError(f"sheet not found: {sheet!r}")
        return self._wb[sheet]

    def header(self, sheet: str) -> list[str]:
        ws = self._ws(sheet)
        first = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), ())
        return [("" if c is None else str(c)) for c in first]

    def rows(self, sheet: str, *, skip_header: bool = True) -> list[list[Any]]:
        ws = self._ws(sheet)
        out: list[list[Any]] = []
        start = 2 if skip_header else 1
        for row in ws.iter_rows(min_row=start, values_only=True):
            # Skip fully-empty trailing rows.
            if all(c is None for c in row):
                continue
            out.append(list(row))
        return out

    def cell(self, sheet: str, row: int, col: int) -> Any:
        return self._ws(sheet).cell(row=row, column=col).value

    def read_text(self) -> str:
        """Flat textual dump of every sheet for inspection/preview."""
        parts: list[str] = []
        for name in self._wb.sheetnames:
            ws = self._wb[name]
            parts.append(f"# {name}")
            for row in ws.iter_rows(values_only=True):
                if all(c is None for c in row):
                    continue
                parts.append("\t".join("" if c is None else str(c) for c in row))
        return "\n".join(parts)

    # -- build side ----------------------------------------------------------

    def write_sheet(self, title: str, header: list[str], rows: list[list[Any]]) -> None:
        """Create a sheet titled ``title`` with a header row then data rows."""
        ws = self._wb.create_sheet(title=title)
        ws.append(list(header))
        for r in rows:
            ws.append(list(r))

    def save(self, target: Path | None = None) -> Path:
        dest = target or self.path
        parent = dest.parent
        if parent.exists() and not os.access(parent, os.W_OK):
            raise DocumentError(f"target directory is not writable: {parent}")
        if dest.exists() and not os.access(dest, os.W_OK):
            raise DocumentError(f"target is not writable: {dest}")
        if not self._wb.sheetnames:
            raise DocumentError("cannot save a workbook with no sheets")
        try:
            self._wb.save(str(dest))
        except OSError as exc:
            raise DocumentError(f"cannot write .xlsx: {dest}: {exc}") from exc
        return dest

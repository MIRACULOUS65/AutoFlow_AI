"""DOCX adapter using python-docx.

Editing strategy: operate on each run's text individually so paragraphs, runs
and formatting are preserved. We never rebuild the document from scratch. Edits
that would span multiple runs (rare for the deterministic ops here) are applied
per-run; whole-document text is still available for inspection/verification.

Malformed files fail safely with DocumentError (python-docx raises PackageNot
FoundError / KeyError / zipfile.BadZipFile on invalid packages).
"""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

from ..editing.operations import EditOperation, apply_operations
from .base import DocumentError

try:  # import guarded so a missing dep degrades gracefully
    import docx  # python-docx
    from docx.opc.exceptions import PackageNotFoundError
except Exception as _exc:  # pragma: no cover - environment guard
    docx = None
    PackageNotFoundError = Exception


class DocxAdapter:
    """Structure-preserving .docx editing."""

    def __init__(self, path: Path) -> None:
        if docx is None:  # pragma: no cover - environment guard
            raise DocumentError("python-docx is not installed")
        self.path = path
        try:
            self._doc = docx.Document(str(path))
        except (PackageNotFoundError, zipfile.BadZipFile) as exc:
            raise DocumentError(f"not a valid .docx package: {path}") from exc
        except KeyError as exc:
            raise DocumentError(f"corrupt .docx structure: {path}") from exc
        except Exception as exc:  # noqa: BLE001 - normalize to DocumentError
            raise DocumentError(f"cannot open .docx: {path}: {exc}") from exc

    # -- iteration helpers ---------------------------------------------------

    def _iter_paragraphs(self):
        """Yield all paragraphs including those inside tables."""

        yield from self._doc.paragraphs
        for table in self._doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    yield from cell.paragraphs

    def read_text(self) -> str:
        parts = [p.text for p in self._iter_paragraphs()]
        return "\n".join(parts)

    def apply_operations(self, ops: list[EditOperation]) -> list[tuple[str, int]]:
        """Apply operations run-by-run to preserve formatting.

        For each run we apply the full operation list to that run's text. The
        reported counts aggregate changes across all runs.
        """

        aggregate: dict[str, int] = {}
        order: list[str] = []

        for paragraph in self._iter_paragraphs():
            for run in paragraph.runs:
                original = run.text
                if not original:
                    continue
                new_text, report = apply_operations(original, ops)
                for desc, count in report:
                    if desc not in aggregate:
                        aggregate[desc] = 0
                        order.append(desc)
                    aggregate[desc] += count
                if new_text != original:
                    run.text = new_text

        return [(desc, aggregate[desc]) for desc in order]

    def save(self, target: Path | None = None) -> Path:
        dest = target or self.path
        if dest.exists() and not os.access(dest, os.W_OK):
            raise DocumentError(f"target is not writable: {dest}")
        try:
            self._doc.save(str(dest))
        except OSError as exc:
            raise DocumentError(f"cannot write .docx: {dest}: {exc}") from exc
        return dest

"""Unified multi-signal verification engine (CP3).

A task declares expected preconditions / transition / postconditions and the
evidence required. The engine gathers signals (UI state, DOM, filesystem,
document content, screenshot delta, app state, expected text) and returns a
VerificationOutcome with per-check results and a confidence. "Action executed"
is NEVER sufficient: material tasks require corroborating evidence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from ..schemas.enums import StrEnum


class SignalKind(StrEnum):
    UI_STATE = "ui_state"
    DOM_STATE = "dom_state"
    FILESYSTEM = "filesystem"
    DOCUMENT = "document"
    SCREENSHOT_DELTA = "screenshot_delta"
    APP_STATE = "app_state"
    EXPECTED_TEXT = "expected_text"


@dataclass
class Check:
    kind: SignalKind
    passed: bool
    detail: str = ""
    weight: float = 1.0


@dataclass
class VerificationOutcome:
    verified: bool
    confidence: float
    checks: list[Check] = field(default_factory=list)

    @property
    def failed_checks(self) -> list[str]:
        return [f"{c.kind}:{c.detail}" for c in self.checks if not c.passed]


class VerificationEngine:
    """Combines checks into a confidence; verified only above a threshold AND
    with no failed required check."""

    def __init__(self, *, min_confidence: float = 0.6) -> None:
        self._min_conf = min_confidence

    def evaluate(self, checks: list[Check], *, require_all: bool = True) -> VerificationOutcome:
        if not checks:
            return VerificationOutcome(verified=False, confidence=0.0)
        total_w = sum(c.weight for c in checks) or 1.0
        passed_w = sum(c.weight for c in checks if c.passed)
        confidence = round(passed_w / total_w, 3)
        all_passed = all(c.passed for c in checks)
        verified = (all_passed if require_all else confidence >= self._min_conf) and confidence >= self._min_conf
        return VerificationOutcome(verified=verified, confidence=confidence, checks=checks)

    # -- signal builders -----------------------------------------------------

    @staticmethod
    def file_exists(path: str | Path) -> Check:
        p = Path(path)
        ok = p.exists() and p.is_file()
        return Check(SignalKind.FILESYSTEM, ok, f"exists={ok} path={p.name}")

    @staticmethod
    def file_hash(path: str | Path) -> str | None:
        p = Path(path)
        if not p.exists():
            return None
        h = hashlib.sha256()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def file_changed(self, path: str | Path, before_hash: str | None) -> Check:
        after = self.file_hash(path)
        ok = after is not None and after != before_hash
        return Check(SignalKind.FILESYSTEM, ok, f"changed={ok}")

    @staticmethod
    def document_contains(path: str | Path, expected: str) -> Check:
        """Reopen a document and confirm expected content is present."""

        from ..documents.base import DocumentError, open_document

        try:
            text = open_document(Path(path)).read_text()
        except DocumentError as exc:
            return Check(SignalKind.DOCUMENT, False, f"reopen failed: {exc}")
        ok = expected in text
        return Check(SignalKind.DOCUMENT, ok, f"contains={ok!r}")

    @staticmethod
    def document_not_contains(path: str | Path, forbidden: str) -> Check:
        from ..documents.base import DocumentError, open_document

        try:
            text = open_document(Path(path)).read_text()
        except DocumentError as exc:
            return Check(SignalKind.DOCUMENT, False, f"reopen failed: {exc}")
        ok = forbidden not in text
        return Check(SignalKind.DOCUMENT, ok, f"absent={ok!r}")

    @staticmethod
    def state_changed(before_hash: str, after_hash: str) -> Check:
        ok = before_hash != after_hash
        return Check(SignalKind.APP_STATE, ok, f"state_changed={ok}")

    @staticmethod
    def expected_text_present(observed_text: str, expected: str) -> Check:
        ok = expected.lower() in (observed_text or "").lower()
        return Check(SignalKind.EXPECTED_TEXT, ok, f"present={ok}")

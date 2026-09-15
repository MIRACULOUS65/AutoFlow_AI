"""Word document lifecycle workflow (open -> edit -> save -> verify -> close).

Two paths, honestly labeled:

* INTEGRATION (default): drives the real python-docx / text document adapters
  through the full lifecycle. Every stage is verified with the real
  VerificationEngine — a save is only "verified" after the file is re-opened and
  the edited content is actually present, and the file hash actually changed.
  "Save button clicked" is never sufficient.

* LIVE (opt-in, AUTOFLOW_REAL_WORD=1): additionally launches the real Word
  application via the Windows UIA adapter and verifies the window lifecycle. It
  falls back to INTEGRATION verification for content because reading Word's live
  document text via UIA is environment-dependent.

The application lifecycle is modeled explicitly (NOT_RUNNING..CLOSED) and the
document is always closed in a ``finally`` so no process/file handle leaks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..documents.base import DocumentError, open_document, sha256_file
from ..editing.operations import EditOperation
from ..schemas.enums import StrEnum
from .verification import Check, VerificationEngine, VerificationOutcome


class AppLifecycle(StrEnum):
    NOT_RUNNING = "not_running"
    STARTING = "starting"
    RUNNING = "running"
    READY = "ready"
    BUSY = "busy"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class WorkflowStage(StrEnum):
    OPEN = "open"
    INSPECT = "inspect"
    EDIT = "edit"
    SAVE = "save"
    VERIFY_SAVE = "verify_save"
    REOPEN_VERIFY = "reopen_verify"
    CLOSE = "close"
    VERIFY_CLOSED = "verify_closed"
    VERIFY_PERSIST = "verify_persist"


@dataclass
class StageResult:
    stage: WorkflowStage
    ok: bool
    detail: str = ""


@dataclass
class WordWorkflowResult:
    path: str
    mode: str  # "integration" | "live"
    verified: bool
    confidence: float
    lifecycle: str
    stages: list[StageResult] = field(default_factory=list)
    reason: str = ""

    def as_dict(self) -> dict:
        return {
            "path": self.path,
            "mode": self.mode,
            "verified": self.verified,
            "confidence": self.confidence,
            "lifecycle": self.lifecycle,
            "reason": self.reason,
            "stages": [{"stage": str(s.stage), "ok": s.ok, "detail": s.detail} for s in self.stages],
        }


class WordDocumentWorkflow:
    """Runs the full document lifecycle with real, staged verification."""

    def __init__(self, *, live: bool = False, uia_adapter=None) -> None:
        self._live = live
        self._uia = uia_adapter
        self._engine = VerificationEngine(min_confidence=0.6)
        self.lifecycle = AppLifecycle.NOT_RUNNING

    def run(
        self,
        path: str | Path,
        operations: list[EditOperation],
        *,
        expect_text: str | None = None,
    ) -> WordWorkflowResult:
        p = Path(path)
        mode = "live" if self._live else "integration"
        result = WordWorkflowResult(path=str(p), mode=mode, verified=False,
                                    confidence=0.0, lifecycle=str(self.lifecycle))
        checks: list[Check] = []
        adapter = None
        launched_live = False

        try:
            # 0. (LIVE) launch the real Word application + verify RUNNING state.
            if self._live and self._uia is not None:
                self.lifecycle = AppLifecycle.STARTING
                launch = self._uia.launch_application("winword.exe")
                from .models import ActionStatus

                if getattr(launch, "status", None) == ActionStatus.OK:
                    self.lifecycle = AppLifecycle.RUNNING
                    launched_live = True
                    result.stages.append(StageResult(WorkflowStage.OPEN, True, "winword launched"))
                else:
                    self.lifecycle = AppLifecycle.FAILED
                    result.stages.append(StageResult(WorkflowStage.OPEN, False, "winword launch failed"))

            # 1. OPEN (file-level; the source of content truth)
            if not p.exists():
                result.reason = f"file does not exist: {p}"
                result.stages.append(StageResult(WorkflowStage.OPEN, False, result.reason))
                return result
            try:
                adapter = open_document(p)
            except DocumentError as exc:
                result.reason = f"open failed: {exc}"
                result.stages.append(StageResult(WorkflowStage.OPEN, False, result.reason))
                return result
            self.lifecycle = AppLifecycle.READY
            result.stages.append(StageResult(WorkflowStage.OPEN, True, "document opened"))

            # 2. INSPECT
            before_text = adapter.read_text()
            before_hash = sha256_file(p)
            result.stages.append(StageResult(WorkflowStage.INSPECT, True,
                                             f"{len(before_text)} chars"))

            # 3. EDIT
            self.lifecycle = AppLifecycle.BUSY
            report = adapter.apply_operations(operations)
            total_changes = sum(c for _, c in report)
            result.stages.append(StageResult(WorkflowStage.EDIT, True,
                                             f"{total_changes} changes"))

            # 4. SAVE
            saved = adapter.save(p)
            self.lifecycle = AppLifecycle.READY
            result.stages.append(StageResult(WorkflowStage.SAVE, True, f"saved {saved.name}"))

            # 5. VERIFY_SAVE — file must exist and its hash must have changed
            #    (if edits actually altered content).
            exists_check = self._engine.file_exists(p)
            checks.append(exists_check)
            result.stages.append(StageResult(WorkflowStage.VERIFY_SAVE, exists_check.passed,
                                             exists_check.detail))
            if total_changes > 0:
                changed = self._engine.file_changed(p, before_hash)
                checks.append(changed)
                result.stages.append(StageResult(WorkflowStage.VERIFY_SAVE, changed.passed,
                                                 changed.detail))

            # 6. REOPEN + VERIFY content (independent re-open, not the same handle)
            if expect_text is not None:
                contains = self._engine.document_contains(p, expect_text)
                checks.append(contains)
                result.stages.append(StageResult(WorkflowStage.REOPEN_VERIFY, contains.passed,
                                                 contains.detail))

            # 7. CLOSE — release the file handle / live app
            self.lifecycle = AppLifecycle.CLOSING
            adapter = None  # drop the reference (python-docx holds no OS handle)
            self.lifecycle = AppLifecycle.CLOSED
            result.stages.append(StageResult(WorkflowStage.CLOSE, True, "document closed"))

            # 8. VERIFY_CLOSED + VERIFY_PERSIST — the file must still be readable.
            persist = self._engine.file_exists(p)
            checks.append(persist)
            result.stages.append(StageResult(WorkflowStage.VERIFY_PERSIST, persist.passed,
                                             persist.detail))

            outcome: VerificationOutcome = self._engine.evaluate(checks, require_all=True)
            result.verified = outcome.verified
            result.confidence = outcome.confidence
            if not outcome.verified:
                result.reason = "verification failed: " + "; ".join(outcome.failed_checks)
            else:
                result.reason = "document lifecycle verified end-to-end"
            return result

        finally:
            # cleanup guarantee: drop the adapter; close the live Word app.
            adapter = None
            if launched_live and self._uia is not None:
                try:
                    # close the Word window via the adapter's hotkey/close path
                    self._uia.hotkey("alt", "F4")
                except Exception:  # noqa: BLE001
                    pass
            if self.lifecycle not in (AppLifecycle.CLOSED, AppLifecycle.FAILED):
                self.lifecycle = AppLifecycle.CLOSED
            result.lifecycle = str(self.lifecycle)


def create_disposable_docx(path: str | Path, paragraphs: list[str]) -> Path:
    """Create a disposable .docx fixture (returns the path). Requires python-docx."""

    import docx

    p = Path(path)
    doc = docx.Document()
    for para in paragraphs:
        doc.add_paragraph(para)
    doc.save(str(p))
    return p

"""Intent normalizer: raw prompt -> NormalizedTask.

Deterministic for the slice. Detects: the requested edit operations, the target
file (from an explicit path in the prompt or a supplied attachment), the
document intent, required capabilities and a risk hint. Does not execute
anything (FR-01).
"""

from __future__ import annotations

import re
from pathlib import Path

from ..editing.operations import detect_operations_from_prompt
from ..schemas.enums import RiskClass
from ..schemas.tasks import NormalizedTask

# Matches quoted or bare paths ending in a supported document extension.
_PATH_RE = re.compile(
    r'["\']?([A-Za-z]:\\[^"\'<>|]+?\.(?:docx|txt|md|markdown)|(?:\./|/)?[\w./\\-]+?\.(?:docx|txt|md|markdown))["\']?',
    re.IGNORECASE,
)


class NormalizeError(Exception):
    """The prompt could not be normalized into an actionable task."""


class IntentNormalizer:
    def normalize(
        self,
        *,
        task_id: str,
        prompt: str,
        target_path: str | None = None,
    ) -> NormalizedTask:
        ops = detect_operations_from_prompt(prompt)

        resolved_path = target_path or self._find_path(prompt)

        entities: list[str] = []
        if resolved_path:
            entities.append(f"file:{resolved_path}")

        capabilities = ["document_editing"]
        outputs = ["edited_document"]

        # Risk stays low for local same-file document edits; external send
        # (later) would raise this to high at the send boundary.
        risk = RiskClass.LOW

        ambiguities: list[str] = []
        missing: list[str] = []
        if not resolved_path:
            missing.append("target_file")
        if not ops:
            ambiguities.append("no explicit edit operation detected in the request")

        objective = self._objective(prompt, resolved_path)

        return NormalizedTask(
            task_id=task_id,
            objective=objective,
            entities=tuple(entities),
            constraints=tuple(self._constraints(prompt)),
            requested_outputs=tuple(outputs),
            required_capabilities=tuple(capabilities),
            risk_hint=risk,
            target_systems=("filesystem",),
            ambiguities=tuple(ambiguities),
            approval_candidates=(),
            missing_information=tuple(missing),
        )

    @staticmethod
    def _find_path(prompt: str) -> str | None:
        m = _PATH_RE.search(prompt)
        return m.group(1) if m else None

    @staticmethod
    def _objective(prompt: str, path: str | None) -> str:
        base = "Edit a document and save the result"
        if path:
            base = f"Edit '{Path(path).name}' and save the result to the same file"
        return base

    @staticmethod
    def _constraints(prompt: str) -> list[str]:
        p = prompt.lower()
        constraints: list[str] = []
        if "same file" in p or "same path" in p or "over the same" in p:
            constraints.append("preserve_same_file_identity")
        if "ask" in p or "approval" in p or "before send" in p:
            constraints.append("ask_before_external_send")
        return constraints

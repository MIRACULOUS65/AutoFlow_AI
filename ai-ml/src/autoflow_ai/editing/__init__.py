"""Structured text-edit operations and deterministic application.

Requests like "fix grammar", "replace wording", "normalize em-dashes",
"remove double spaces" are represented as typed :class:`EditOperation` objects
*before* being applied. The model (later) proposes which operations to run; the
deterministic engine here performs the actual text mutation. For this slice the
operations and their selection are rule-based and fully deterministic.
"""

from __future__ import annotations

from .operations import (
    EditKind,
    EditOperation,
    apply_operation,
    apply_operations,
    detect_operations_from_prompt,
)

__all__ = [
    "EditKind",
    "EditOperation",
    "apply_operation",
    "apply_operations",
    "detect_operations_from_prompt",
]

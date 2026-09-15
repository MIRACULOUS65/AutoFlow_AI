"""Structured edit operations applied deterministically to plain text.

Each operation is a typed, serializable transform. Applying an operation to a
string returns the new string plus a count of changes made. The document tools
apply these operations run-by-run to preserve DOCX structure/formatting.
"""

from __future__ import annotations

import re

from ..schemas.common import AutoFlowModel
from ..schemas.enums import StrEnum


class EditKind(StrEnum):
    """Kinds of deterministic text edits supported in this slice."""

    REPLACE_TEXT = "replace_text"          # literal find/replace
    APPEND_TEXT = "append_text"            # append text to end of document
    NORMALIZE_EM_DASHES = "normalize_em_dashes"   # " - " / "--" -> em dash
    REMOVE_DOUBLE_SPACES = "remove_double_spaces"  # collapse runs of spaces
    FIX_SPACE_BEFORE_PUNCT = "fix_space_before_punct"  # "word ." -> "word."
    TRIM_TRAILING_WHITESPACE = "trim_trailing_whitespace"


# Common rule-based "grammar" fixes bundled under FIX_SPACE_BEFORE_PUNCT and
# REMOVE_DOUBLE_SPACES. Kept deliberately conservative and deterministic.

_EM_DASH = "\u2014"  # —


class EditOperation(AutoFlowModel):
    """One structured edit. ``find``/``replace`` used only by REPLACE_TEXT."""

    kind: EditKind
    find: str | None = None
    replace: str | None = None
    case_sensitive: bool = True

    def describe(self) -> str:
        if self.kind == EditKind.REPLACE_TEXT:
            return f"replace {self.find!r} -> {self.replace!r}"
        if self.kind == EditKind.APPEND_TEXT:
            return f"append {self.replace!r}"
        return self.kind.value


def _apply_replace(text: str, op: EditOperation) -> tuple[str, int]:
    if not op.find:
        return text, 0
    if op.case_sensitive:
        count = text.count(op.find)
        return (text.replace(op.find, op.replace or ""), count)
    # case-insensitive literal replace
    pattern = re.compile(re.escape(op.find), re.IGNORECASE)
    new_text, count = pattern.subn(op.replace or "", text)
    return new_text, count


def _apply_append(text: str, op: EditOperation) -> tuple[str, int]:
    addition = op.replace or ""
    if not addition:
        return text, 0
    sep = "" if (not text or text.endswith("\n")) else "\n"
    return text + sep + addition, 1


def _apply_em_dashes(text: str) -> tuple[str, int]:
    # Normalize the common ASCII representations of an em dash:
    #   " -- "  -> " — "
    #   "--"    -> "—"
    #   " - "   -> " — "  (spaced hyphen used as a dash)
    count = 0
    new_text, n = re.subn(r"\s--\s", f" {_EM_DASH} ", text)
    count += n
    new_text, n = re.subn(r"--", _EM_DASH, new_text)
    count += n
    new_text, n = re.subn(r"(?<=\w) - (?=\w)", f" {_EM_DASH} ", new_text)
    count += n
    return new_text, count


def _apply_double_spaces(text: str) -> tuple[str, int]:
    # Collapse runs of 2+ spaces (not newlines/tabs) to a single space.
    matches = len(re.findall(r"  +", text))
    return re.sub(r"  +", " ", text), matches


def _apply_space_before_punct(text: str) -> tuple[str, int]:
    matches = len(re.findall(r"\s+([,.;:!?])", text))
    return re.sub(r"\s+([,.;:!?])", r"\1", text), matches


def _apply_trim_trailing(text: str) -> tuple[str, int]:
    lines = text.split("\n")
    changed = 0
    out = []
    for line in lines:
        stripped = line.rstrip()
        if stripped != line:
            changed += 1
        out.append(stripped)
    return "\n".join(out), changed


def apply_operation(text: str, op: EditOperation) -> tuple[str, int]:
    """Apply a single operation; return (new_text, change_count)."""

    if op.kind == EditKind.REPLACE_TEXT:
        return _apply_replace(text, op)
    if op.kind == EditKind.APPEND_TEXT:
        return _apply_append(text, op)
    if op.kind == EditKind.NORMALIZE_EM_DASHES:
        return _apply_em_dashes(text)
    if op.kind == EditKind.REMOVE_DOUBLE_SPACES:
        return _apply_double_spaces(text)
    if op.kind == EditKind.FIX_SPACE_BEFORE_PUNCT:
        return _apply_space_before_punct(text)
    if op.kind == EditKind.TRIM_TRAILING_WHITESPACE:
        return _apply_trim_trailing(text)
    raise ValueError(f"unsupported edit kind: {op.kind}")


def apply_operations(
    text: str, ops: list[EditOperation]
) -> tuple[str, list[tuple[str, int]]]:
    """Apply operations in order. Return (new_text, [(description, count), ...])."""

    report: list[tuple[str, int]] = []
    current = text
    for op in ops:
        current, count = apply_operation(current, op)
        report.append((op.describe(), count))
    return current, report


# Keyword -> operation detection for the deterministic slice. This is the
# rule-based stand-in for model-proposed edit operations; the architecture keeps
# EditOperation as the contract so a model can later produce the same objects.
def detect_operations_from_prompt(prompt: str) -> list[EditOperation]:
    """Infer edit operations from a natural-language prompt (rule-based)."""

    p = prompt.lower()
    ops: list[EditOperation] = []

    if "em-dash" in p or "em dash" in p or "emdash" in p:
        ops.append(EditOperation(kind=EditKind.NORMALIZE_EM_DASHES))
    if "double space" in p or "duplicate space" in p or "extra space" in p:
        ops.append(EditOperation(kind=EditKind.REMOVE_DOUBLE_SPACES))
    if "grammar" in p or "wording" in p or "clean up" in p or "clean-up" in p:
        # Conservative deterministic "grammar/wording" pass: fix stray spaces
        # before punctuation and collapse double spaces.
        ops.append(EditOperation(kind=EditKind.FIX_SPACE_BEFORE_PUNCT))
        ops.append(EditOperation(kind=EditKind.REMOVE_DOUBLE_SPACES))
    if "trailing" in p or "trim" in p:
        ops.append(EditOperation(kind=EditKind.TRIM_TRAILING_WHITESPACE))

    # Explicit replace / change, quoted or unquoted:
    #   replace "X" with "Y"        change "X" to "Y"
    #   replace X with Y            change X to Y
    #   replace the word X with Y   replace all X with Y
    for op in _detect_replace_ops(prompt):
        ops.append(op)

    # Append / add text: append "…" / add the line "…" / add a conclusion "…"
    for op in _detect_append_ops(prompt):
        ops.append(op)

    # Fallback: the prompt asks to edit but named no concrete change. Apply a
    # safe, deterministic normalization pass (never invents content) so the
    # edit is real and independently verifiable rather than a silent no-op.
    if not ops and ("edit" in p or "fix" in p or "tidy" in p or "format" in p):
        ops.append(EditOperation(kind=EditKind.TRIM_TRAILING_WHITESPACE))
        ops.append(EditOperation(kind=EditKind.REMOVE_DOUBLE_SPACES))

    # De-duplicate while preserving order.
    seen = set()
    unique: list[EditOperation] = []
    for op in ops:
        key = op.to_json()
        if key not in seen:
            seen.add(key)
            unique.append(op)
    return unique


# Filler words that may appear between "replace" and the target term in natural
# language ("replace the word DRAFT", "replace all occurrences of DRAFT").
_REPLACE_FILLERS = (
    "all occurrences of", "all instances of", "every occurrence of",
    "the word", "the words", "the text", "the phrase", "all", "every",
)


def _strip_filler(term: str) -> str:
    t = term.strip()
    low = t.lower()
    for filler in _REPLACE_FILLERS:
        if low.startswith(filler + " "):
            t = t[len(filler):].strip()
            low = t.lower()
    return t.strip("\"'")


def _detect_replace_ops(prompt: str) -> list[EditOperation]:
    """Detect replace/change ops, quoted or unquoted.

    Handles: replace X with Y, change X to Y, substitute X for Y, and the
    quoted variants. Unquoted terms are captured up to the ' with '/' to '
    keyword and have filler words ("the word", "all") stripped.
    """

    ops: list[EditOperation] = []
    patterns = (
        # replace <find> with <replace>
        r'\breplace\s+(.+?)\s+with\s+(.+?)(?:$|[.,;\n]|\s+and\s+save|\s+then\b)',
        # change <find> to <replace>
        r'\bchange\s+(.+?)\s+to\s+(.+?)(?:$|[.,;\n]|\s+and\s+save|\s+then\b)',
        # substitute <find> for <replace>
        r'\bsubstitute\s+(.+?)\s+for\s+(.+?)(?:$|[.,;\n]|\s+and\s+save|\s+then\b)',
    )
    for pat in patterns:
        for m in re.finditer(pat, prompt, re.IGNORECASE):
            find = _strip_filler(m.group(1))
            replace = m.group(2).strip().strip("\"'")
            if find and replace and find != replace:
                ops.append(
                    EditOperation(kind=EditKind.REPLACE_TEXT, find=find, replace=replace)
                )
    return ops


def _detect_append_ops(prompt: str) -> list[EditOperation]:
    """Detect explicit append/add-text ops with quoted content."""

    ops: list[EditOperation] = []
    for m in re.finditer(
        r'\b(?:append|add(?:\s+the\s+(?:line|text|sentence))?)\s+"([^"]+)"',
        prompt, re.IGNORECASE,
    ):
        ops.append(EditOperation(kind=EditKind.APPEND_TEXT, replace=m.group(1)))
    return ops


def expected_conditions_from_prompt(prompt: str) -> dict:
    """Derive verifiable post-conditions from the instruction.

    Returns ``{"must_contain": [...], "must_not_contain": [...]}`` so the mission
    verifier can confirm the requested change actually landed in the file — not
    merely that the bytes changed. Only derived from explicit replace/append
    ops (the ones with concrete target text); structural cleanups add nothing.
    """

    must_contain: list[str] = []
    must_not_contain: list[str] = []
    for op in _detect_replace_ops(prompt):
        if op.replace:
            must_contain.append(op.replace)
        # We do not assert must_not_contain for the old term: the replacement
        # text could legitimately contain it, and case/substring overlap makes
        # a blanket absence check unreliable. Presence of the new text is the
        # authoritative signal that the replace was applied.
    for op in _detect_append_ops(prompt):
        if op.replace:
            must_contain.append(op.replace)
    return {"must_contain": must_contain, "must_not_contain": must_not_contain}

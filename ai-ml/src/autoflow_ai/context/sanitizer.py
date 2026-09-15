"""Context sanitizer.

Enforces the trust model without rewriting source meaning. It does NOT edit the
substance of untrusted content (that must remain available as evidence); it only
flags/quarantines malformed items and guarantees that lower-trust content is
never emitted as an instruction (the bundle renderer wraps it as <data>).
"""

from __future__ import annotations

from dataclasses import dataclass

from .items import ContextItem, PROTECTED_SECTIONS
from .trust import TrustLevel, is_trusted_instruction_source


@dataclass
class SanitizationResult:
    accepted: list[ContextItem]
    quarantined: list[tuple[ContextItem, str]]  # (item, reason)


class ContextSanitizer:
    def sanitize(self, items: list[ContextItem]) -> SanitizationResult:
        accepted: list[ContextItem] = []
        quarantined: list[tuple[ContextItem, str]] = []

        for item in items:
            reason = self._reject_reason(item)
            if reason:
                quarantined.append((item, reason))
                continue
            accepted.append(item)

        return SanitizationResult(accepted=accepted, quarantined=quarantined)

    @staticmethod
    def _reject_reason(item: ContextItem) -> str | None:
        # Malformed provenance: source_type claims a source but no source_id.
        if item.source_type not in ("inline", "system") and not item.source_id:
            return "malformed provenance: source_type set without source_id"

        # Protected sections require authorization metadata.
        if item.section in PROTECTED_SECTIONS and not item.has_authorization_metadata:
            return "missing authorization metadata for protected section"

        # A low-trust item must never be placed in an instruction-only role by
        # claiming SYSTEM trust while coming from an external source.
        if is_trusted_instruction_source(item.trust_level):
            if item.source_type in ("external", "tool", "retrieved"):
                return (
                    "trust/source mismatch: instruction-trust claimed for "
                    f"{item.source_type} content"
                )

        return None

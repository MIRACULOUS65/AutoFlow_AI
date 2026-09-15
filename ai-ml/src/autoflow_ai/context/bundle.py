"""ContextBundle: the assembled, budgeted, inspectable context manifest."""

from __future__ import annotations

import hashlib
import json

from pydantic import Field

from ..schemas.common import VersionedModel
from .items import ContextItem, ContextSection, SECTION_ORDER


class DroppedItem(VersionedModel):
    """Record of an item that was excluded, with a reason (for inspection)."""

    id: str
    section: ContextSection
    reason: str
    token_estimate: int = 0


class CompressionEvent(VersionedModel):
    """Record of a compression/truncation action taken during assembly."""

    section: ContextSection
    action: str
    detail: str = ""


class ContextBundle(VersionedModel):
    """Grouped, ordered context ready to render into a model prompt."""

    request_id: str
    task_id: str
    execution_id: str | None = None
    model_id: str | None = None
    items: tuple[ContextItem, ...] = ()
    token_budget: int = Field(ge=0)
    reserved_output_tokens: int = Field(default=0, ge=0)
    estimated_tokens: int = Field(default=0, ge=0)
    dropped_items: tuple[DroppedItem, ...] = ()
    compression_events: tuple[CompressionEvent, ...] = ()

    def items_for(self, section: ContextSection) -> list[ContextItem]:
        return [it for it in self.items if it.section == section]

    def render_prompt(self) -> str:
        """Deterministic sectioned prompt. Trusted and untrusted content are
        clearly separated; untrusted content is explicitly framed as data."""

        from .trust import is_trusted_instruction_source

        blocks: list[str] = []
        for section in SECTION_ORDER:
            section_items = self.items_for(section)
            if not section_items:
                continue
            header = section.value.upper().replace("_", " ")
            lines = [header, "-" * len(header)]
            for it in section_items:
                if is_trusted_instruction_source(it.trust_level):
                    lines.append(it.content)
                else:
                    # DATA framing: never promote to instruction.
                    src = f" source={it.source_id}" if it.source_id else ""
                    lines.append(
                        f"<data trust={it.trust_level}{src}>\n{it.content}\n</data>"
                    )
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def context_hash(self) -> str:
        """Deterministic hash over the ordered content + structure.

        Identical input context yields the same hash (excludes volatile fields
        like request_id/execution_id so re-runs of the same context match)."""

        payload = {
            "task_id": self.task_id,
            "model_id": self.model_id,
            "token_budget": self.token_budget,
            "reserved_output_tokens": self.reserved_output_tokens,
            "items": [
                {
                    "section": it.section.value,
                    "trust": it.trust_level.value,
                    "source_id": it.source_id,
                    "content_hash": it.content_hash,
                }
                for it in self.items
            ],
        }
        text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def manifest(self, *, redact: bool = False) -> dict:
        """Inspectable manifest (never includes secrets)."""

        return {
            "request_id": self.request_id,
            "task_id": self.task_id,
            "model_id": self.model_id,
            "token_budget": self.token_budget,
            "reserved_output_tokens": self.reserved_output_tokens,
            "estimated_tokens": self.estimated_tokens,
            "context_hash": self.context_hash(),
            "sections": {
                section.value: [
                    {
                        "id": it.id,
                        "trust": it.trust_level.value,
                        "source_id": it.source_id,
                        "tokens": it.token_estimate,
                        "relevance": it.relevance,
                        "importance": it.importance,
                        "content": "<redacted>" if redact else it.content[:200],
                    }
                    for it in self.items_for(section)
                ]
                for section in SECTION_ORDER
                if self.items_for(section)
            },
            "dropped_items": [
                {"id": d.id, "section": d.section.value, "reason": d.reason}
                for d in self.dropped_items
            ],
            "compression_events": [
                {"section": c.section.value, "action": c.action, "detail": c.detail}
                for c in self.compression_events
            ],
        }

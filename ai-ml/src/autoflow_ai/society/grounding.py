"""Mission grounding: RAG + workflow-memory retrieval into the society loop.

This wires the existing KnowledgeService (RAG) and MemoryService into the
mission path as EVIDENCE — not instructions. Retrieved knowledge and workflow
memory are posted to the blackboard with:

* trust class EXTERNAL_DATA (knowledge) / OBSERVATION (memory strategy) — never
  SYSTEM/POLICY/USER, so a retrieved document can never become an instruction,
  authorization, or approval (Parts B/C, requirement 1/2);
* full provenance (evidence_id, document_id, page, source, score) so every fact
  is traceable and nothing is fabricated;
* tenant/workspace/permission scoping enforced by the services themselves.

When retrieval is insufficient the result is an explicit ``NO_RELEVANT_CONTEXT``
status — the mission never invents missing knowledge.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas.enums import StrEnum
from .blackboard import Blackboard, BlackboardEntry, TrustClass


class GroundingStatus(StrEnum):
    GROUNDED = "grounded"                    # authorized evidence retrieved
    NO_RELEVANT_CONTEXT = "no_relevant_context"  # nothing relevant/authorized
    UNAVAILABLE = "unavailable"              # no knowledge/memory service wired
    ERROR = "error"                          # retrieval failed (fail-closed)


@dataclass
class EvidenceItem:
    evidence_id: str
    kind: str                # "knowledge" | "memory"
    summary: str
    source: str | None
    score: float
    provenance: dict = field(default_factory=dict)


@dataclass
class GroundingResult:
    status: GroundingStatus
    knowledge: list[EvidenceItem] = field(default_factory=list)
    memory: list[EvidenceItem] = field(default_factory=list)
    reason: str = ""

    @property
    def has_context(self) -> bool:
        return self.status == GroundingStatus.GROUNDED and bool(self.knowledge or self.memory)

    def summary_text(self, *, max_items: int = 6) -> str:
        """A trust-separated, bounded evidence summary (data, not instructions)."""

        if not self.has_context:
            return "NO_RELEVANT_CONTEXT"
        lines: list[str] = []
        for ev in (self.knowledge + self.memory)[:max_items]:
            src = f" [{ev.source}]" if ev.source else ""
            lines.append(f"- ({ev.kind}) {ev.summary}{src}")
        return "\n".join(lines)


class MissionGrounding:
    """Retrieves knowledge + memory evidence and posts it to the blackboard.

    ``knowledge`` is an optional KnowledgeService; ``memory`` an optional
    MemoryService. Both are used only for retrieval; neither can grant
    authority. Scoping is enforced by the services (tenant/workspace/permission).
    """

    def __init__(
        self,
        *,
        knowledge=None,
        memory=None,
        tenant_id: str = "org_mission",
        workspace_id: str = "ws_mission",
        permissions: frozenset[str] = frozenset(),
        min_score: float = 0.0,
    ) -> None:
        self._knowledge = knowledge
        self._memory = memory
        self._tenant = tenant_id
        self._workspace = workspace_id
        self._permissions = permissions
        self._min_score = min_score

    def ground(
        self,
        query: str,
        *,
        board: Blackboard,
        task_id: str = "grounding",
        producer: str = "grounding",
        available_tools: set[str] | None = None,
        available_capabilities: set[str] | None = None,
    ) -> GroundingResult:
        if self._knowledge is None and self._memory is None:
            return GroundingResult(status=GroundingStatus.UNAVAILABLE,
                                   reason="no knowledge/memory service configured")

        knowledge_items: list[EvidenceItem] = []
        memory_items: list[EvidenceItem] = []

        # --- RAG knowledge (data + provenance) ---------------------------
        if self._knowledge is not None:
            try:
                resp = self._knowledge.search(
                    query, tenant_id=self._tenant, workspace_id=self._workspace,
                    permissions=self._permissions,
                )
            except Exception as exc:  # noqa: BLE001 - fail closed, never crash
                return GroundingResult(status=GroundingStatus.ERROR, reason=f"rag error: {exc}")
            for ev in getattr(resp, "evidence", ()):
                if ev.score < self._min_score:
                    continue
                knowledge_items.append(
                    EvidenceItem(
                        evidence_id=ev.evidence_id, kind="knowledge",
                        summary=ev.snippet, source=ev.source, score=ev.score,
                        provenance={"evidence_id": ev.evidence_id,
                                    "document_id": ev.document_id,
                                    "page": ev.page, "source": ev.source},
                    )
                )

        # --- workflow memory (strategy candidate, data) ------------------
        if self._memory is not None:
            try:
                hits = self._memory.search(
                    query, tenant_id=self._tenant, workspace_id=self._workspace,
                    permissions=self._permissions,
                    available_tools=available_tools,
                    available_capabilities=available_capabilities,
                )
            except Exception as exc:  # noqa: BLE001
                # RAG may still have grounded us; memory failure alone isn't fatal
                hits = []
            for i, hit in enumerate(hits):
                wf = hit.workflow
                summary = (
                    f"{wf.canonical_name} (v{wf.version}, {hit.compatibility.value}): "
                    + " -> ".join(s.name for s in wf.workflow.steps)
                )
                memory_items.append(
                    EvidenceItem(
                        evidence_id=f"wf_{i:02d}", kind="memory", summary=summary,
                        source=wf.workflow_id, score=float(hit.score.total),
                        provenance={"workflow_id": wf.workflow_id, "version": wf.version,
                                    "compatibility": hit.compatibility.value},
                    )
                )

        if not knowledge_items and not memory_items:
            # explicit: nothing relevant/authorized — do NOT fabricate
            board.post(
                BlackboardEntry(
                    key=f"grounding:{task_id}",
                    value={"status": "no_relevant_context", "query": query[:200]},
                    summary="NO_RELEVANT_CONTEXT: no authorized evidence retrieved",
                    trust=TrustClass.OBSERVATION, producer=producer, task_id=task_id,
                    confidence=0.0,
                )
            )
            return GroundingResult(status=GroundingStatus.NO_RELEVANT_CONTEXT,
                                   reason="no relevant authorized evidence")

        # Post each evidence item as DATA (EXTERNAL_DATA for retrieved knowledge,
        # OBSERVATION for memory strategy). NEVER instructional trust.
        for ev in knowledge_items:
            board.post(
                BlackboardEntry(
                    key=f"evidence:{task_id}:{ev.evidence_id}",
                    value={"snippet": ev.summary, **ev.provenance},
                    summary=ev.summary[:512], trust=TrustClass.EXTERNAL_DATA,
                    producer=producer, task_id=task_id,
                    evidence_refs=(ev.evidence_id,), confidence=min(ev.score, 1.0),
                )
            )
        for ev in memory_items:
            board.post(
                BlackboardEntry(
                    key=f"memory:{task_id}:{ev.evidence_id}",
                    value={"strategy": ev.summary, **ev.provenance},
                    summary=ev.summary[:512], trust=TrustClass.OBSERVATION,
                    producer=producer, task_id=task_id,
                    evidence_refs=(ev.evidence_id,), confidence=min(ev.score, 1.0),
                )
            )
        return GroundingResult(status=GroundingStatus.GROUNDED,
                               knowledge=knowledge_items, memory=memory_items,
                               reason="authorized evidence retrieved")

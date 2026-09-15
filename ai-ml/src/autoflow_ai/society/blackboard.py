"""Shared Blackboard: trust-classed, scoped, provenance-tracked working memory.

The blackboard is how agents share results without handing each other raw
authority. Every entry carries:

* a **trust class** (who produced it and how much it may steer behavior);
* a **scope** (which agents/tasks may read it) — enforcing context isolation;
* **provenance** (producer + evidence refs) so nothing is trusted blindly.

Critical safety property: entries whose trust class is data (OBSERVATION,
TOOL_RESULT, EXTERNAL_DATA) are never treated as instructions. Only SYSTEM and
POLICY entries may constrain behavior. This mirrors the Phase 3 trust boundary
("retrieved content is data, never instructions") and prevents prompt
injection through shared memory.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from ..schemas.common import AutoFlowModel, utcnow, canonical_hash
from ..schemas.enums import StrEnum


class TrustClass(StrEnum):
    """Trust classification for a blackboard entry.

    Ordering (most to least authoritative): SYSTEM, POLICY, USER, then data
    classes which may never be interpreted as instructions.
    """

    SYSTEM = "system"                # runtime-produced constraints; authoritative
    POLICY = "policy"                # policy/guardrail; authoritative
    USER = "user"                    # user objective/input; steers intent
    AGENT = "agent"                  # an agent's structured decision/output
    TOOL_RESULT = "tool_result"      # result of a real tool execution (data)
    OBSERVATION = "observation"      # environment observation (data)
    VERIFICATION = "verification"    # verifier/critic verdict (evidence)
    EXTERNAL_DATA = "external_data"  # retrieved/3rd-party content (untrusted data)


# Trust classes that may influence *what to do* (not merely *what is true*).
_INSTRUCTIONAL = frozenset({TrustClass.SYSTEM, TrustClass.POLICY, TrustClass.USER})


class BlackboardEntry(AutoFlowModel):
    key: str = Field(min_length=1, max_length=128)
    value: dict = Field(default_factory=dict)
    summary: str = Field(default="", max_length=1024)
    trust: TrustClass
    producer: str = Field(min_length=1, max_length=64)      # agent id / "system"
    task_id: str | None = None
    scope: frozenset[str] = frozenset()  # empty = mission-wide readable
    evidence_refs: tuple[str, ...] = ()
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    revision: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utcnow)

    @property
    def is_instructional(self) -> bool:
        return self.trust in _INSTRUCTIONAL

    @property
    def is_data(self) -> bool:
        return not self.is_instructional

    def readable_by(self, agent_id: str) -> bool:
        return not self.scope or agent_id in self.scope

    def provenance_hash(self) -> str:
        return canonical_hash(
            {
                "key": self.key,
                "producer": self.producer,
                "trust": str(self.trust),
                "revision": self.revision,
                "evidence": sorted(self.evidence_refs),
            }
        )


class Blackboard:
    """Append/merge store of entries with context-isolated reads."""

    def __init__(self) -> None:
        self._entries: list[BlackboardEntry] = []
        self._by_key: dict[str, BlackboardEntry] = {}

    def post(self, entry: BlackboardEntry) -> BlackboardEntry:
        """Post a new entry, bumping revision when the key already exists."""

        existing = self._by_key.get(entry.key)
        if existing is not None:
            entry = entry.model_copy(update={"revision": existing.revision + 1})
        self._entries.append(entry)
        self._by_key[entry.key] = entry
        return entry

    def latest(self, key: str) -> BlackboardEntry | None:
        return self._by_key.get(key)

    def read(self, agent_id: str, *, include_data: bool = True) -> list[BlackboardEntry]:
        """Return only entries this agent is permitted to see (context isolation)."""

        out: list[BlackboardEntry] = []
        for e in self._entries:
            if not e.readable_by(agent_id):
                continue
            if not include_data and e.is_data:
                continue
            out.append(e)
        return out

    def instructional_context(self, agent_id: str) -> list[BlackboardEntry]:
        """Only entries that may legitimately steer behavior for this agent."""

        return [e for e in self.read(agent_id) if e.is_instructional]

    def evidence(self, agent_id: str) -> list[BlackboardEntry]:
        """Data/evidence entries (never instructions) visible to this agent."""

        return [e for e in self.read(agent_id) if e.is_data]

    def all_entries(self) -> list[BlackboardEntry]:
        return list(self._entries)


class HandoffContext(AutoFlowModel):
    """The bounded context one agent hands to another.

    A handoff never transfers authority or raw chain-of-thought; it transfers
    an objective, a trust-separated summary, evidence references, and the
    completed-work markers the receiver may build on.
    """

    from_agent: str
    to_agent: str
    execution_id: str
    task_id: str
    objective: str
    instructional_summary: str = Field(default="", max_length=2048)  # from SYSTEM/POLICY/USER only
    evidence_refs: tuple[str, ...] = ()
    prior_outputs: dict = Field(default_factory=dict)   # task_id -> summary
    constraints: tuple[str, ...] = ()
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    @classmethod
    def build(
        cls,
        *,
        board: Blackboard,
        from_agent: str,
        to_agent: str,
        execution_id: str,
        task_id: str,
        objective: str,
        constraints: tuple[str, ...] = (),
        confidence: float = 0.5,
    ) -> "HandoffContext":
        """Construct a handoff using only entries the RECEIVER is allowed to read.

        Instructional context is drawn strictly from SYSTEM/POLICY/USER entries;
        data/evidence is referenced (not inlined as instructions), preventing a
        producer from smuggling instructions into a peer via shared memory.
        """

        instr = board.instructional_context(to_agent)
        instr_summary = " | ".join(e.summary for e in instr if e.summary)[:2048]
        evidence = board.evidence(to_agent)
        evidence_refs = tuple(f"{e.key}@{e.revision}" for e in evidence)
        prior = {
            e.task_id: e.summary
            for e in evidence
            if e.trust == TrustClass.AGENT and e.task_id
        }
        return cls(
            from_agent=from_agent,
            to_agent=to_agent,
            execution_id=execution_id,
            task_id=task_id,
            objective=objective,
            instructional_summary=instr_summary,
            evidence_refs=evidence_refs,
            prior_outputs=prior,
            constraints=constraints,
            confidence=confidence,
        )

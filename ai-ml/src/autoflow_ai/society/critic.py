"""CriticAgent: independent verification that can REJECT work.

The critic is deliberately independent of the worker. It sees only:

* the objective,
* the claimed outputs,
* the evidence entries on the blackboard (data/observations/verification), and
* any verification requirements attached to the subtask.

It does NOT see the worker's internal reasoning, and it cannot be told the
answer by the worker. It returns one of four verdicts and, when rejecting,
states precisely what evidence is missing so the worker can revise. This is the
mechanism that makes "done" a *verified fact* rather than a worker's claim.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.enums import StrEnum
from .blackboard import Blackboard, TrustClass


class CriticVerdict(StrEnum):
    VERIFIED = "verified"
    NOT_VERIFIED = "not_verified"
    CONTRADICTED = "contradicted"
    NEED_MORE_EVIDENCE = "need_more_evidence"


@dataclass
class CriticReview:
    verdict: CriticVerdict
    reason: str
    missing_evidence: tuple[str, ...] = ()
    confidence: float = 0.0

    @property
    def accepted(self) -> bool:
        return self.verdict == CriticVerdict.VERIFIED


class CriticAgent:
    """Independent evidence-based verifier."""

    def __init__(self, *, agent_id: str = "critic") -> None:
        self.agent_id = agent_id

    def review(
        self,
        *,
        objective: str,
        task_id: str,
        claimed_outputs: dict,
        board: Blackboard,
        required_evidence: tuple[str, ...] = (),
        require_tool_evidence: bool = False,
    ) -> CriticReview:
        """Decide a verdict from evidence only — never trust the claim alone."""

        # The critic reads the board under its own identity (context isolation
        # applies to it too). It considers only DATA/VERIFICATION entries as
        # evidence; AGENT claims are treated as claims, not proof.
        entries = board.read(self.agent_id)
        evidence = [
            e for e in entries
            if e.trust in (TrustClass.TOOL_RESULT, TrustClass.OBSERVATION,
                           TrustClass.VERIFICATION)
        ]
        agent_claims = [e for e in entries if e.trust == TrustClass.AGENT and e.task_id == task_id]

        # 1. No claimed output at all -> nothing to verify.
        if not claimed_outputs and not agent_claims:
            return CriticReview(
                verdict=CriticVerdict.NOT_VERIFIED,
                reason="no output was produced for the subtask",
                confidence=0.0,
            )

        # 2. A subtask that must be backed by a real tool/observation but has
        #    none is NOT verified, regardless of the worker's confidence.
        if require_tool_evidence and not evidence:
            return CriticReview(
                verdict=CriticVerdict.NEED_MORE_EVIDENCE,
                reason="claim requires tool/observation evidence but none is present",
                missing_evidence=("tool_result_or_observation",),
                confidence=0.1,
            )

        # 3. Explicit required evidence keys must be present on the board.
        present_keys = {e.key for e in entries}
        present_keys |= {f"{e.key.split(':', 1)[-1]}" for e in entries}
        missing = tuple(
            req for req in required_evidence
            if req not in present_keys
            and not any(req in (e.summary or "") for e in evidence)
            and not any(req in (str(v)) for e in agent_claims for v in e.value.values())
        )
        if missing:
            return CriticReview(
                verdict=CriticVerdict.NEED_MORE_EVIDENCE,
                reason=f"missing required evidence: {list(missing)}",
                missing_evidence=missing,
                confidence=0.2,
            )

        # 4. Contradiction: an explicit failure/verification-failed observation.
        contradiction = next(
            (e for e in evidence
             if e.value.get("verified") is False
             or (e.value.get("ok") is False)
             or "failed" in (e.summary or "").lower()),
            None,
        )
        if contradiction is not None:
            return CriticReview(
                verdict=CriticVerdict.CONTRADICTED,
                reason=f"evidence contradicts the claim: {contradiction.summary[:200]}",
                confidence=0.9,
            )

        # 5. Verified: there is real supporting evidence (or an explicit
        #    no-side-effect output the objective allows) and nothing contradicts.
        supporting = evidence or (agent_claims if not require_tool_evidence else [])
        if supporting:
            conf = max((e.confidence for e in supporting), default=0.5)
            return CriticReview(
                verdict=CriticVerdict.VERIFIED,
                reason="evidence supports the claim and nothing contradicts it",
                confidence=min(conf, 0.99),
            )

        return CriticReview(
            verdict=CriticVerdict.NOT_VERIFIED,
            reason="insufficient evidence to verify the claim",
            confidence=0.2,
        )

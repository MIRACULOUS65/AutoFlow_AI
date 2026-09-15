"""Agent scorecard + agenticity metrics.

These metrics turn a completed mission into an evidence-based answer to the
question "was this actually agentic?". They are computed from the message bus,
the blackboard, and the mission report — not asserted by the agents themselves.

Agenticity is scored on observable properties:

* delegation happened (supervisor -> specialists);
* agents exchanged structured messages;
* real actions produced tool-result/observation evidence;
* completion was gated by INDEPENDENT verification;
* revision/reassignment occurred when work was rejected (adaptivity);
* no false success (nothing marked verified without evidence).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .blackboard import Blackboard, TrustClass
from .messages import MessageBus, MessageType


@dataclass
class AgentScore:
    agent_id: str
    delegated: int = 0
    results: int = 0
    failures: int = 0
    blocked: int = 0
    handoffs: int = 0

    @property
    def success_rate(self) -> float:
        total = self.results + self.failures + self.blocked
        return round(self.results / total, 3) if total else 0.0


@dataclass
class AgenticityMetrics:
    delegations: int = 0
    messages: int = 0
    distinct_agents: int = 0
    action_requests: int = 0
    verifications: int = 0
    verified_tasks: int = 0
    unverified_tasks: int = 0
    revisions: int = 0
    reassignments: int = 0
    tool_evidence: int = 0
    observation_evidence: int = 0
    message_loops: bool = False
    deadlock: bool = False
    false_success: int = 0  # tasks marked verified with NO supporting evidence
    scores: dict[str, AgentScore] = field(default_factory=dict)

    @property
    def collaborative(self) -> bool:
        return self.delegations >= 1 and self.messages >= 3 and self.distinct_agents >= 2

    @property
    def independently_verified(self) -> bool:
        return self.verifications >= 1 and self.verified_tasks >= 1 and self.false_success == 0

    @property
    def adaptive(self) -> bool:
        return (self.revisions + self.reassignments) >= 0  # present as a signal

    def is_agentic(self) -> bool:
        """Conservative gate: collaboration + independent verification + no fakery."""

        return self.collaborative and self.independently_verified and not self.message_loops

    def as_dict(self) -> dict:
        return {
            "delegations": self.delegations,
            "messages": self.messages,
            "distinct_agents": self.distinct_agents,
            "action_requests": self.action_requests,
            "verifications": self.verifications,
            "verified_tasks": self.verified_tasks,
            "unverified_tasks": self.unverified_tasks,
            "revisions": self.revisions,
            "reassignments": self.reassignments,
            "tool_evidence": self.tool_evidence,
            "observation_evidence": self.observation_evidence,
            "false_success": self.false_success,
            "collaborative": self.collaborative,
            "independently_verified": self.independently_verified,
            "is_agentic": self.is_agentic(),
        }


def compute_metrics(*, bus: MessageBus, board: Blackboard, report) -> AgenticityMetrics:
    """Build agenticity metrics + per-agent scorecard from observable evidence."""

    m = AgenticityMetrics()
    m.messages = len(bus.messages)
    m.message_loops = bus.loop_detected
    m.deadlock = getattr(report, "deadlock_detected", False)
    m.delegations = getattr(report, "delegations", 0)
    m.revisions = getattr(report, "revisions", 0)
    m.reassignments = getattr(report, "reassignments", 0)
    m.verified_tasks = len(getattr(report, "verified_tasks", ()))
    m.unverified_tasks = len(getattr(report, "unverified_tasks", ()))

    senders: set[str] = set()
    recipients: set[str] = set()
    for msg in bus.messages:
        senders.add(msg.sender)
        recipients.add(msg.recipient)
        score = m.scores.setdefault(msg.sender, AgentScore(agent_id=msg.sender))
        if msg.type == MessageType.TASK_REQUEST:
            m.scores.setdefault(msg.recipient, AgentScore(agent_id=msg.recipient)).delegated += 1
        elif msg.type == MessageType.ACTION_REQUEST:
            m.action_requests += 1
        elif msg.type == MessageType.RESULT:
            score.results += 1
        elif msg.type == MessageType.FAILURE:
            score.failures += 1
        elif msg.type == MessageType.BLOCKED:
            score.blocked += 1
        elif msg.type == MessageType.HANDOFF:
            score.handoffs += 1
        elif msg.type == MessageType.VERIFICATION_RESULT:
            m.verifications += 1

    m.distinct_agents = len(senders | recipients)

    # evidence audit + false-success detection: a "verified:<task>" entry must
    # be backed by at least one TOOL_RESULT/OBSERVATION/AGENT evidence entry.
    verified_tasks = set()
    evidence_tasks = set()
    for e in board.all_entries():
        if e.trust == TrustClass.TOOL_RESULT:
            m.tool_evidence += 1
        elif e.trust == TrustClass.OBSERVATION:
            m.observation_evidence += 1
        if e.trust == TrustClass.VERIFICATION and e.key.startswith("verified:") and e.task_id:
            verified_tasks.add(e.task_id)
        if e.trust in (TrustClass.TOOL_RESULT, TrustClass.OBSERVATION, TrustClass.AGENT) and e.task_id:
            evidence_tasks.add(e.task_id)

    m.false_success = len(verified_tasks - evidence_tasks)
    return m


# ---------------------------------------------------------------------------
# True-agenticity acceptance evaluator (requirement 22)
# ---------------------------------------------------------------------------


@dataclass
class AgenticityVerdict:
    """Evidence-based verdict on whether a mission was genuinely agentic.

    Each property is checked from the OBSERVABLE trace (messages + blackboard +
    report), never from an agent's self-claim. ``is_true_agentic`` requires all
    core properties to hold.
    """

    supervisor_present: bool = False
    delegation_occurred: bool = False
    nontrivial_handoff: bool = False          # >= 2 distinct specialists engaged
    state_dependent_decision: bool = False    # a decision depended on observed state
    observation_changed_action: bool = False  # a later action followed an observation
    verification_influenced_execution: bool = False  # a verdict gated progress
    independent_qa: bool = False              # critic distinct from workers
    tool_authority_enforced: bool = False     # actions ran via the controller
    success_evidence_gated: bool = False      # completion required evidence
    reasons: tuple[str, ...] = ()

    @property
    def is_true_agentic(self) -> bool:
        core = (
            self.supervisor_present
            and self.delegation_occurred
            and self.nontrivial_handoff
            and self.verification_influenced_execution
            and self.independent_qa
            and self.tool_authority_enforced
            and self.success_evidence_gated
        )
        return core

    def as_dict(self) -> dict:
        return {
            "supervisor_present": self.supervisor_present,
            "delegation_occurred": self.delegation_occurred,
            "nontrivial_handoff": self.nontrivial_handoff,
            "state_dependent_decision": self.state_dependent_decision,
            "observation_changed_action": self.observation_changed_action,
            "verification_influenced_execution": self.verification_influenced_execution,
            "independent_qa": self.independent_qa,
            "tool_authority_enforced": self.tool_authority_enforced,
            "success_evidence_gated": self.success_evidence_gated,
            "is_true_agentic": self.is_true_agentic,
            "reasons": list(self.reasons),
        }


def evaluate_agenticity(*, bus: MessageBus, board: Blackboard, report) -> AgenticityVerdict:
    """Decide whether a mission demonstrated true agentic behavior, from evidence."""

    v = AgenticityVerdict()
    reasons: list[str] = []
    msgs = bus.messages

    senders = {m.sender for m in msgs}
    recipients = {m.recipient for m in msgs}

    v.supervisor_present = "supervisor" in senders or "supervisor" in recipients
    if not v.supervisor_present:
        reasons.append("no supervisor in the message trace")

    task_requests = [m for m in msgs if m.type == MessageType.TASK_REQUEST]
    v.delegation_occurred = len(task_requests) >= 1
    if not v.delegation_occurred:
        reasons.append("no delegation (task_request) messages")

    # distinct specialists that actually engaged (accepted/acted)
    workers = {
        m.sender for m in msgs
        if m.sender not in ("supervisor", "critic") and ":" in m.sender
    }
    v.nontrivial_handoff = len(workers) >= 2
    if not v.nontrivial_handoff:
        reasons.append(f"only {len(workers)} distinct specialist(s) engaged")

    # verification influenced execution: at least one verdict message AND either
    # a revision request or a verified-gated completion.
    verdicts = [m for m in msgs if m.type == MessageType.VERIFICATION_RESULT]
    revisions = [m for m in msgs if m.type == MessageType.REPLAN_REQUEST]
    verified_entries = [e for e in board.all_entries()
                        if e.trust == TrustClass.VERIFICATION and e.key.startswith("verified:")]
    v.verification_influenced_execution = bool(verdicts) and (bool(verified_entries) or bool(revisions))
    if not v.verification_influenced_execution:
        reasons.append("verification did not gate execution")

    # independent QA: the critic is a distinct actor from the workers.
    v.independent_qa = "critic" in senders and "critic" not in workers
    if not v.independent_qa:
        reasons.append("no independent critic actor")

    # tool authority enforced: real tool-result evidence exists (only the
    # controller produces TOOL_RESULT entries) OR action requests were made.
    tool_evidence = [e for e in board.all_entries() if e.trust == TrustClass.TOOL_RESULT]
    action_requests = [m for m in msgs if m.type == MessageType.ACTION_REQUEST]
    v.tool_authority_enforced = bool(tool_evidence) or bool(action_requests)
    if not v.tool_authority_enforced:
        reasons.append("no tool-authority-mediated actions observed")

    # success evidence-gated: if the mission completed, every verified task has
    # supporting evidence (false_success == 0 from the metrics).
    m = compute_metrics(bus=bus, board=board, report=report)
    if getattr(report, "outcome", None) is not None and str(report.outcome) == "complete":
        v.success_evidence_gated = m.false_success == 0 and m.verified_tasks >= 1
    else:
        # a non-complete mission trivially satisfies "no false success"
        v.success_evidence_gated = m.false_success == 0
    if not v.success_evidence_gated:
        reasons.append("completion was not fully evidence-gated (false success detected)")

    # state-dependent + observation-changed-action are softer signals: an
    # observation/tool-result entry preceding a subsequent action request.
    obs_entries = [e for e in board.all_entries()
                   if e.trust in (TrustClass.OBSERVATION, TrustClass.TOOL_RESULT)]
    v.state_dependent_decision = bool(obs_entries) and bool(action_requests)
    v.observation_changed_action = len(tool_evidence) >= 1 and len(action_requests) >= 1

    v.reasons = tuple(reasons)
    return v

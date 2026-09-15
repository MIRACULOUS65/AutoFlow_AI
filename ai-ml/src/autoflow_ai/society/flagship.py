"""Flagship end-to-end workflow: research -> document -> email (approval-gated).

This ties the pieces together into the milestone's flagship scenario WITHOUT
hardcoding which agent does which step: the document phase runs through the
:class:`MissionSupervisor`, which decides delegation from the plan by
capability. The email phase runs through the approval-bound Gmail workflow,
which never sends without an explicit approval and independently verifies the
sent message.

The whole run shares ONE blackboard so evidence flows across phases, and the
final result is an evidence chain: grounded research/knowledge -> verified
document -> verified draft -> human approval -> verified send. If any phase is
not verified, the flagship result is not "complete" — no false success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..agents.registry import build_default_registry
from ..computer_use.autonomy import ApprovalLedger
from ..runtime.document_tools import DocumentSession, register_document_tools
from ..runtime.registry import ToolRegistry
from ..runtime.tool_calling import ToolCallingController
from ..schemas.enums import StrEnum
from .blackboard import Blackboard, TrustClass
from .gmail_workflow import EmailSpec, GmailComposeWorkflow, GmailOutcome
from .grounding import MissionGrounding
from .metrics import evaluate_agenticity
from .supervisor import MissionLimits, MissionOutcome, MissionSupervisor


class FlagshipOutcome(StrEnum):
    COMPLETE = "complete"
    DOCUMENT_FAILED = "document_failed"
    DRAFT_FAILED = "draft_failed"
    AWAITING_APPROVAL = "awaiting_approval"
    SEND_FAILED = "send_failed"
    NOT_VERIFIED = "not_verified"


@dataclass
class FlagshipResult:
    outcome: FlagshipOutcome
    document_verified: bool = False
    draft_verified: bool = False
    sent_verified: bool = False
    mission_outcome: str = ""
    gmail_outcome: str = ""
    agenticity: dict = field(default_factory=dict)
    reason: str = ""

    @property
    def complete(self) -> bool:
        return self.outcome == FlagshipOutcome.COMPLETE

    def as_dict(self) -> dict:
        return {
            "outcome": str(self.outcome),
            "complete": self.complete,
            "document_verified": self.document_verified,
            "draft_verified": self.draft_verified,
            "sent_verified": self.sent_verified,
            "mission_outcome": self.mission_outcome,
            "gmail_outcome": self.gmail_outcome,
            "agenticity": self.agenticity,
            "reason": self.reason,
        }


def _register_verify_tool(registry: ToolRegistry, session: DocumentSession, target_path: str | None) -> None:
    from ..documents.base import DocumentError, open_document, sha256_file
    from ..runtime.registry import ToolExecutionError
    from ..schemas.enums import RiskClass
    from ..schemas.tools import ToolDefinition

    def _verify(args):
        path = args.get("path") or (str(session.path) if session.path else target_path)
        if not path or not Path(path).exists():
            raise ToolExecutionError("verify_failed", "document not found")
        try:
            text = open_document(Path(path)).read_text()
        except DocumentError as exc:
            raise ToolExecutionError("verify_failed", str(exc)) from exc
        changed = session.hash_after is not None and session.hash_before != session.hash_after
        return {"verified": True, "file_reopens": True, "edits_present": bool(changed),
                "readable_chars": len(text), "hash": sha256_file(Path(path))}

    registry.register(
        ToolDefinition(name="document.verify",
                       description="Re-open the document and confirm edits persisted.",
                       input_schema={"type": "object", "properties": {"path": {"type": "string"}},
                                     "required": [], "additionalProperties": False},
                       risk_class=RiskClass.LOW, permission_scope="files:read", idempotent=True),
        _verify,
    )


class FlagshipWorkflow:
    """Runs the research->document->email flagship with a shared blackboard."""

    def __init__(
        self,
        *,
        gmail_adapter,
        knowledge=None,
        memory=None,
        router=None,
        auto_approve: bool = False,
    ) -> None:
        self._gmail_adapter = gmail_adapter
        self._knowledge = knowledge
        self._memory = memory
        self._router = router
        self._auto_approve = auto_approve
        self.board = Blackboard()
        self.ledger = ApprovalLedger()
        self.supervisor = None
        self.gmail = None

    def run(
        self,
        *,
        document_prompt: str,
        document_path: str,
        email: EmailSpec,
        execution_id: str = "exec_flagship",
    ) -> FlagshipResult:
        from ..planning.planner import DeterministicPlanner, ModelPlanner
        from ..planning.validation import validate_plan
        from ..planning.errors import PlanValidationError

        # --- PHASE 1: document mission via the supervisor (non-hardcoded) ---
        registry = ToolRegistry()
        session = DocumentSession()
        register_document_tools(registry, session)
        _register_verify_tool(registry, session, document_path)

        planner = ModelPlanner(self._router) if self._router else DeterministicPlanner()
        plan = planner.plan(document_prompt, target_path=document_path,
                            available_tools=set(registry.names()))
        reasons = validate_plan(
            plan, known_agents=build_default_registry().known_agent_names(),
            registered_tools=set(registry.names()) | {"document.verify"},
            available_capabilities={"document_editing", "verification", "research",
                                    "knowledge_retrieval", "communication", "email"},
            granted_permissions={"files:read", "files:write"},
        )
        if reasons:
            raise PlanValidationError(reasons)
        graph = plan.to_runtime_graph(execution_id=execution_id, task_id="task_flagship")

        controller = ToolCallingController(
            registry=registry, permissions=frozenset({"files:read", "files:write"})
        )
        grounding = None
        if self._knowledge is not None or self._memory is not None:
            grounding = MissionGrounding(knowledge=self._knowledge, memory=self._memory,
                                         tenant_id="org_local", workspace_id="ws_local")
        self.supervisor = MissionSupervisor(
            registry=build_default_registry(), controller=controller,
            board=self.board, router=self._router, grounding=grounding,
            tenant_id="org_local", workspace_id="ws_local", limits=MissionLimits(),
        )
        mission = self.supervisor.run(graph)
        document_verified = mission.outcome == MissionOutcome.COMPLETE
        agenticity = evaluate_agenticity(bus=self.supervisor.bus, board=self.board, report=mission)

        result = FlagshipResult(
            outcome=FlagshipOutcome.DOCUMENT_FAILED,
            document_verified=document_verified,
            mission_outcome=str(mission.outcome),
            agenticity=agenticity.as_dict(),
        )
        if not document_verified:
            result.reason = f"document phase not verified: {mission.reason}"
            return result

        # --- PHASE 2: email via the approval-bound Gmail workflow -----------
        self.gmail = GmailComposeWorkflow(
            adapter=self._gmail_adapter, ledger=self.ledger, board=self.board,
            execution_id=execution_id, task_id="flagship_gmail",
        )
        draft_res, approval = self.gmail.compose_and_verify(email)
        result.gmail_outcome = str(draft_res.outcome)
        if draft_res.outcome != GmailOutcome.DRAFT_VERIFIED or approval is None:
            result.outcome = FlagshipOutcome.DRAFT_FAILED
            result.reason = f"draft phase: {draft_res.reason}"
            return result
        result.draft_verified = True

        # --- PHASE 3: approval gate (send is a real side effect) ------------
        if not self._auto_approve:
            # In a real run the human approves out-of-band. Without approval the
            # flagship stops here — it NEVER sends unapproved mail.
            result.outcome = FlagshipOutcome.AWAITING_APPROVAL
            result.reason = "draft verified; awaiting human approval before send"
            return result

        # auto_approve is used ONLY in tests/demos to exercise the send path.
        self.gmail.approve(approval)
        sent = self.gmail.send_with_approval(approval)
        result.gmail_outcome = str(sent.outcome)
        if sent.outcome != GmailOutcome.SENT_VERIFIED:
            result.outcome = (FlagshipOutcome.SEND_FAILED
                              if sent.outcome == GmailOutcome.SEND_FAILED
                              else FlagshipOutcome.NOT_VERIFIED)
            result.reason = f"send phase: {sent.reason}"
            return result
        result.sent_verified = True
        result.outcome = FlagshipOutcome.COMPLETE
        result.reason = "research/document verified, draft approved, send independently verified"
        return result

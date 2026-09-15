"""Gmail compose workflow: draft -> verify -> approve -> send -> verify sent.

This is the safety-critical path. Sending email is a real external side effect,
so it happens ONLY after an approval that is cryptographically bound to the
EXACT message: recipient, subject, body hash, attachment path + content hash,
and the observed draft state. Any material change invalidates the approval and
the send is refused.

Independent verification: after send, the workflow does NOT trust "Send clicked".
It re-reads the Sent view and confirms a matching message (recipient + subject +
attachment) actually exists. If the Sent view is unavailable or the message is
absent, the result is NOT_VERIFIED — never SUCCESS.

Passwords are never handled: if the browser session isn't authenticated the
workflow returns WAITING_FOR_USER and asks the human to log in manually.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from ..computer_use.autonomy import ApprovalLedger, ApprovalRequest
from ..computer_use.gmail import DraftState, GmailState
from ..schemas.enums import StrEnum
from .blackboard import Blackboard, BlackboardEntry, TrustClass


class GmailOutcome(StrEnum):
    SENT_VERIFIED = "sent_verified"
    DRAFT_VERIFIED = "draft_verified"        # draft ok, awaiting approval
    WAITING_FOR_USER = "waiting_for_user"    # login required
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_INVALID = "approval_invalid"    # approval didn't bind to this message
    DRAFT_INVALID = "draft_invalid"          # draft doesn't match intent
    ATTACHMENT_INVALID = "attachment_invalid"
    SEND_FAILED = "send_failed"
    NOT_VERIFIED = "not_verified"            # sent but couldn't confirm
    FAILED = "failed"


@dataclass
class EmailSpec:
    recipient: str
    subject: str
    body: str
    attachment_path: str | None = None  # local path to attach


@dataclass
class GmailStep:
    stage: str
    ok: bool
    detail: str = ""


@dataclass
class GmailResult:
    outcome: GmailOutcome
    steps: list[GmailStep] = field(default_factory=list)
    draft: dict = field(default_factory=dict)
    approval_id: str | None = None
    reason: str = ""

    @property
    def sent(self) -> bool:
        return self.outcome == GmailOutcome.SENT_VERIFIED

    def as_dict(self) -> dict:
        return {
            "outcome": str(self.outcome),
            "sent": self.sent,
            "reason": self.reason,
            "approval_id": self.approval_id,
            "draft": self.draft,
            "steps": [{"stage": s.stage, "ok": s.ok, "detail": s.detail} for s in self.steps],
        }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_hash(path: str | Path) -> str | None:
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class GmailComposeWorkflow:
    """Compose, verify, approval-gate, send, and independently verify a message."""

    def __init__(
        self,
        *,
        adapter,
        ledger: ApprovalLedger | None = None,
        board: Blackboard | None = None,
        execution_id: str = "exec_gmail",
        task_id: str = "gmail",
    ) -> None:
        self._gmail = adapter
        self._ledger = ledger or ApprovalLedger()
        self._board = board or Blackboard()
        self._execution_id = execution_id
        self._task_id = task_id

    @property
    def board(self) -> Blackboard:
        return self._board

    @property
    def ledger(self) -> ApprovalLedger:
        return self._ledger

    # -- approval binding -----------------------------------------------
    def build_approval_request(self, draft: DraftState, *, attachment_hash: str = "") -> ApprovalRequest:
        """Bind the approval to the EXACT OBSERVED message + attachment content.

        The binding is derived purely from what is actually in the draft
        (recipient/subject/body/attachment name) plus the content hash of the
        file that was actually attached. Nothing from the caller's claim leaks
        in — so a change to the live draft OR the attachment file invalidates the
        approval.
        """

        att_name = draft.attachments[0] if draft.attachments else ""
        arguments = {
            "recipient": draft.recipient,
            "subject": draft.subject,
            "body_hash": _sha(draft.body),
            "attachment_name": att_name,
            "attachment_hash": attachment_hash or "",
        }
        observation_hash = _sha(str(sorted(draft.as_dict().items())) + "|" + (attachment_hash or ""))
        return ApprovalRequest(
            execution_id=self._execution_id, task_id=self._task_id,
            action_id="gmail.send", tool="gmail.send", risk="high",
            target={"recipient": draft.recipient}, arguments=arguments,
            observation_hash=observation_hash,
        )

    # -- workflow -------------------------------------------------------
    def compose_and_verify(self, spec: EmailSpec) -> tuple[GmailResult, ApprovalRequest | None]:
        """Open Gmail, compose the draft, verify it against intent, and return
        the approval request the human must grant. Does NOT send."""

        result = GmailResult(outcome=GmailOutcome.FAILED)

        # 0. attachment pre-checks (before touching the UI)
        if spec.attachment_path is not None:
            p = Path(spec.attachment_path)
            if not p.exists() or not p.is_file():
                result.outcome = GmailOutcome.ATTACHMENT_INVALID
                result.reason = f"attachment missing/unreadable: {p}"
                result.steps.append(GmailStep("attachment_precheck", False, result.reason))
                return result, None
            result.steps.append(GmailStep("attachment_precheck", True, f"{p.name} readable"))

        # 1. open + login state (never handle passwords)
        state = self._gmail.open()
        if state == GmailState.NEEDS_LOGIN or not self._gmail.login_state():
            result.outcome = GmailOutcome.WAITING_FOR_USER
            result.reason = "Gmail requires login; please authenticate manually"
            result.steps.append(GmailStep("login", False, result.reason))
            return result, None
        result.steps.append(GmailStep("login", True, "authenticated session"))

        # 2. compose
        self._gmail.compose()
        self._gmail.set_recipient(spec.recipient)
        self._gmail.set_subject(spec.subject)
        self._gmail.set_body(spec.body)
        if spec.attachment_path is not None:
            attached = self._gmail.attach(spec.attachment_path)
            if not attached:
                result.outcome = GmailOutcome.ATTACHMENT_INVALID
                result.reason = "attachment upload failed in UI"
                result.steps.append(GmailStep("attach", False, result.reason))
                return result, None
            result.steps.append(GmailStep("attach", True, "attached"))

        # 3. read the ACTUAL draft state from the UI + verify against intent
        draft = self._gmail.read_draft()
        result.draft = draft.as_dict()
        checks = [
            ("recipient", draft.recipient == spec.recipient),
            ("subject", draft.subject == spec.subject),
            ("body", draft.body == spec.body),
        ]
        if spec.attachment_path is not None:
            want = Path(spec.attachment_path).name
            checks.append(("attachment", want in draft.attachments))
        for name, ok in checks:
            result.steps.append(GmailStep(f"verify_{name}", ok,
                                          "matches intent" if ok else "MISMATCH"))
        if not all(ok for _, ok in checks):
            result.outcome = GmailOutcome.DRAFT_INVALID
            result.reason = "draft does not match intent: " + \
                ", ".join(n for n, ok in checks if not ok)
            return result, None

        # 4. save draft + post evidence
        self._gmail.save_draft()
        self._post(f"draft:{self._task_id}", draft.as_dict(), TrustClass.OBSERVATION,
                   "verified draft matches intent")
        result.outcome = GmailOutcome.DRAFT_VERIFIED
        result.reason = "draft verified; approval required before send"

        # Capture the attachment path + its content hash AT APPROVAL TIME so the
        # send-time binding can re-hash the same file and detect tampering.
        self._approved_attachment_path = spec.attachment_path
        attachment_hash = _file_hash(spec.attachment_path) if spec.attachment_path else ""
        approval = self.build_approval_request(draft, attachment_hash=attachment_hash or "")
        return result, approval

    def approve(self, approval: ApprovalRequest) -> str:
        """Record human approval bound to the exact message. Returns approval id."""

        return self._ledger.grant(approval)

    def send_with_approval(self, approval: ApprovalRequest) -> GmailResult:
        """Send ONLY if the approval still binds to the current observed draft,
        then independently verify the message appears in Sent.

        The binding is re-derived purely from the LIVE draft plus a fresh re-hash
        of the approved attachment file. If the draft changed, or the attachment
        file's bytes changed, the binding differs and the send is refused.
        """

        result = GmailResult(outcome=GmailOutcome.FAILED)

        # re-read the live draft + re-hash the approved attachment; re-bind.
        draft = self._gmail.read_draft()
        result.draft = draft.as_dict()
        att_path = getattr(self, "_approved_attachment_path", None)
        attachment_hash = _file_hash(att_path) if att_path else ""
        current = self.build_approval_request(draft, attachment_hash=attachment_hash or "")
        if current.binding_hash() != approval.binding_hash():
            result.outcome = GmailOutcome.APPROVAL_INVALID
            result.reason = "message changed since approval; approval no longer valid"
            result.steps.append(GmailStep("approval_binding", False, result.reason))
            return result
        if not self._ledger.is_approved(current):
            result.outcome = GmailOutcome.APPROVAL_REQUIRED
            result.reason = "no valid approval for this exact message"
            result.steps.append(GmailStep("approval_binding", False, result.reason))
            return result
        result.approval_id = current.binding_hash()
        result.steps.append(GmailStep("approval_binding", True, "approval matches message"))

        # SEND (the real side effect)
        ok = self._gmail.send()
        if not ok:
            result.outcome = GmailOutcome.SEND_FAILED
            result.reason = "send action failed"
            result.steps.append(GmailStep("send", False, result.reason))
            return result
        result.steps.append(GmailStep("send", True, "send executed"))

        # INDEPENDENT sent verification — never trust "send clicked". We verify
        # against the OBSERVED draft that was actually approved + sent.
        sent = self._gmail.read_sent(recipient=draft.recipient, subject=draft.subject)
        if sent is None:
            result.outcome = GmailOutcome.NOT_VERIFIED
            result.reason = "sent action returned but no matching Sent message found"
            result.steps.append(GmailStep("verify_sent", False, result.reason))
            return result
        # verify recipient + subject + attachment presence in the sent record
        attach_ok = True
        if draft.attachments:
            want = draft.attachments[0]
            attach_ok = want in sent.attachments
        recip_ok = sent.recipient == draft.recipient
        subj_ok = sent.subject == draft.subject
        result.steps.append(GmailStep("verify_sent_recipient", recip_ok, sent.recipient))
        result.steps.append(GmailStep("verify_sent_subject", subj_ok, sent.subject))
        result.steps.append(GmailStep("verify_sent_attachment", attach_ok,
                                      ",".join(sent.attachments)))
        if not (recip_ok and subj_ok and attach_ok):
            result.outcome = GmailOutcome.NOT_VERIFIED
            result.reason = "sent message does not match intended message"
            return result

        self._post(f"sent:{self._task_id}",
                   {"recipient": sent.recipient, "subject": sent.subject,
                    "attachments": sent.attachments},
                   TrustClass.VERIFICATION, "sent message independently verified")
        result.outcome = GmailOutcome.SENT_VERIFIED
        result.reason = "email sent and independently verified in Sent view"
        return result

    def _post(self, key: str, value: dict, trust: TrustClass, summary: str) -> None:
        self._board.post(
            BlackboardEntry(
                key=key, value=value, summary=summary[:512], trust=trust,
                producer="gmail", task_id=self._task_id, confidence=0.9,
            )
        )

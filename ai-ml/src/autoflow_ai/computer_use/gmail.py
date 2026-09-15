"""Gmail-over-browser adapter (semantic, safe, approval-gated).

A semantic Gmail interface driven through a browser — NOT direct SMTP/HTTP. This
proves the autonomous system can operate a real application UI safely. The
adapter exposes semantic compose actions (open/compose/set recipient/subject/
body/attach/read draft/send/read sent) rather than raw coordinates.

Safety properties baked in here:

* Sending is a real external side effect and is the ONLY high-risk action.
* The adapter NEVER handles passwords: :meth:`login_state` reports whether the
  browser session is already authenticated; if not, the workflow requests the
  user to log in manually (WAITING_FOR_USER). No credential is read or stored.
* A :class:`FakeGmailAdapter` provides deterministic in-memory DOM state for
  INTEGRATION tests. A real Playwright-backed adapter is provided but its live
  use is gated by the workflow's explicit opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..schemas.enums import StrEnum


class GmailState(StrEnum):
    NOT_OPEN = "not_open"
    OPENED = "opened"
    NEEDS_LOGIN = "needs_login"
    READY = "ready"
    COMPOSING = "composing"
    DRAFT_SAVED = "draft_saved"
    SENT = "sent"
    FAILED = "failed"


@dataclass
class DraftState:
    """The observable state of the compose draft (what the DOM actually holds)."""

    recipient: str = ""
    subject: str = ""
    body: str = ""
    attachments: list[str] = field(default_factory=list)  # filenames as shown in UI

    def as_dict(self) -> dict:
        return {"recipient": self.recipient, "subject": self.subject,
                "body": self.body, "attachments": list(self.attachments)}


@dataclass
class SentRecord:
    """An entry observed in the Sent view (independent post-send evidence)."""

    recipient: str
    subject: str
    body: str
    attachments: list[str] = field(default_factory=list)


class FakeGmailAdapter:
    """Deterministic in-memory Gmail for INTEGRATION tests.

    It faithfully models the observable rules that matter for verification:
    - attaching a file records the file's *basename* (as Gmail shows it);
    - send moves the current draft into a Sent list (independent evidence);
    - send fails closed if there is no recipient.
    Configurable failure switches emulate real-world glitches.
    """

    name = "fake-gmail"

    def __init__(
        self,
        *,
        authenticated: bool = True,
        drop_attachment: bool = False,
        send_fails: bool = False,
        sent_view_available: bool = True,
    ) -> None:
        self._authed = authenticated
        self._drop_attachment = drop_attachment
        self._send_fails = send_fails
        self._sent_view_available = sent_view_available
        self.state = GmailState.NOT_OPEN
        self._draft = DraftState()
        self._sent: list[SentRecord] = []
        self.closed = False

    def available(self) -> bool:
        return True

    def open(self) -> GmailState:
        self.state = GmailState.READY if self._authed else GmailState.NEEDS_LOGIN
        return self.state

    def login_state(self) -> bool:
        return self._authed

    def compose(self) -> None:
        self._draft = DraftState()
        self.state = GmailState.COMPOSING

    def set_recipient(self, recipient: str) -> None:
        self._draft.recipient = recipient

    def set_subject(self, subject: str) -> None:
        self._draft.subject = subject

    def set_body(self, body: str) -> None:
        self._draft.body = body

    def attach(self, path: str | Path) -> bool:
        """Attach a file; records its basename as the UI would. Returns success."""

        p = Path(path)
        if not p.exists():
            return False
        if self._drop_attachment:
            return False  # emulate a failed upload
        self._draft.attachments.append(p.name)
        return True

    def read_draft(self) -> DraftState:
        # returns a COPY so callers can't mutate internal state
        return DraftState(recipient=self._draft.recipient, subject=self._draft.subject,
                          body=self._draft.body, attachments=list(self._draft.attachments))

    def save_draft(self) -> None:
        self.state = GmailState.DRAFT_SAVED

    def send(self) -> bool:
        if self._send_fails or not self._draft.recipient:
            self.state = GmailState.FAILED
            return False
        self._sent.append(
            SentRecord(recipient=self._draft.recipient, subject=self._draft.subject,
                       body=self._draft.body, attachments=list(self._draft.attachments))
        )
        self.state = GmailState.SENT
        return True

    def read_sent(self, *, recipient: str, subject: str) -> SentRecord | None:
        """Independently inspect the Sent view for a matching message."""

        if not self._sent_view_available:
            return None
        for rec in reversed(self._sent):
            if rec.recipient == recipient and rec.subject == subject:
                return rec
        return None

    def close(self) -> None:
        self.closed = True
        self.state = GmailState.NOT_OPEN

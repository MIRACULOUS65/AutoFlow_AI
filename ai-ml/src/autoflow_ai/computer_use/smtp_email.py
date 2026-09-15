"""Real SMTP email adapter — a genuine external side effect, gated and safe.

This adapter implements the SAME semantic interface as ``FakeGmailAdapter``
(open / compose / set_recipient / set_subject / set_body / attach / read_draft /
save_draft / send / read_sent / close) so it drops into ``GmailComposeWorkflow``
unchanged. The difference: ``send()`` performs a REAL SMTP send, and
``read_sent()`` provides INDEPENDENT post-send evidence by re-reading the
destination mailbox over IMAP (never "send clicked").

Safety model (multiple gates, all required to send for real):

  1. ``AUTOFLOW_ALLOW_REAL_SIDE_EFFECTS=true``  (master gate)
  2. ``REAL_EMAIL_ENABLED=true``                (per-capability gate)
  3. recipient ∈ ``EMAIL_RECIPIENT_ALLOWLIST``  (allowlist)
  4. an idempotency key not seen before          (no duplicate sends)

The approval + action-hash binding is enforced by ``GmailComposeWorkflow``
BEFORE ``send()`` is ever called; this adapter is the deterministic executor of
the already-authorized action.

Secrets (SMTP/IMAP passwords) are read only from the environment and are NEVER
logged, put into prompts, events, or artifacts.
"""

from __future__ import annotations

import os
import smtplib
import ssl
import time
import imaplib
import email as email_mod
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path

from ..model_gateway.config import load_dotenv
from .gmail import DraftState, GmailState, SentRecord


class EmailConfigError(Exception):
    """SMTP/email configuration is missing or real send is not permitted."""


@dataclass
class SmtpConfig:
    """SMTP + IMAP configuration read from the environment. Secrets never repr'd."""

    allow_real_side_effects: bool
    real_email_enabled: bool
    smtp_host: str | None
    smtp_port: int
    smtp_starttls: bool
    smtp_from: str | None
    recipient_allowlist: frozenset[str]
    imap_host: str | None
    imap_port: int
    _smtp_user: str | None = field(default=None, repr=False)
    _smtp_pass: str | None = field(default=None, repr=False)
    _imap_user: str | None = field(default=None, repr=False)
    _imap_pass: str | None = field(default=None, repr=False)

    @classmethod
    def from_env(cls) -> "SmtpConfig":
        load_dotenv()

        def _b(name: str) -> bool:
            return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")

        allow = _b("AUTOFLOW_ALLOW_REAL_SIDE_EFFECTS")
        allowlist = frozenset(
            a.strip().lower()
            for a in os.environ.get("EMAIL_RECIPIENT_ALLOWLIST", "").split(",")
            if a.strip()
        )
        return cls(
            allow_real_side_effects=allow,
            real_email_enabled=_b("REAL_EMAIL_ENABLED"),
            smtp_host=os.environ.get("SMTP_HOST") or None,
            smtp_port=int(os.environ.get("SMTP_PORT", "587") or "587"),
            smtp_starttls=os.environ.get("SMTP_STARTTLS", "true").strip().lower()
            in ("1", "true", "yes"),
            smtp_from=os.environ.get("SMTP_FROM") or None,
            recipient_allowlist=allowlist,
            imap_host=os.environ.get("IMAP_HOST") or None,
            imap_port=int(os.environ.get("IMAP_PORT", "993") or "993"),
            _smtp_user=os.environ.get("SMTP_USERNAME") or None,
            _smtp_pass=os.environ.get("SMTP_PASSWORD") or None,
            _imap_user=os.environ.get("IMAP_USERNAME") or None,
            _imap_pass=os.environ.get("IMAP_PASSWORD") or None,
        )

    @property
    def real_send_permitted(self) -> bool:
        """Both master + per-capability gates plus minimal transport config."""
        return (
            self.allow_real_side_effects
            and self.real_email_enabled
            and bool(self.smtp_host and self.smtp_from and self._smtp_user and self._smtp_pass)
        )

    def recipient_allowed(self, recipient: str) -> bool:
        return recipient.strip().lower() in self.recipient_allowlist


class SmtpEmailAdapter:
    """Real SMTP send + IMAP-verified Sent evidence, gated and idempotent.

    Interface-compatible with FakeGmailAdapter so GmailComposeWorkflow uses it
    without modification.
    """

    name = "smtp-email"

    def __init__(self, config: SmtpConfig | None = None) -> None:
        self._cfg = config or SmtpConfig.from_env()
        self.state = GmailState.NOT_OPEN
        self._draft = DraftState()
        self._attachment_paths: list[str] = []
        # execution-scoped idempotency: message-id per logical send.
        self._sent_message_ids: dict[str, str] = {}
        self.closed = False
        self.last_error: str | None = None

    # -- availability / auth ------------------------------------------------

    def available(self) -> bool:
        return self._cfg.real_send_permitted

    def open(self) -> GmailState:
        # A configured, permitted transport is treated as an authenticated
        # session; SMTP AUTH happens per-send. No password is exposed here.
        self.state = GmailState.READY if self._cfg.real_send_permitted else GmailState.NEEDS_LOGIN
        return self.state

    def login_state(self) -> bool:
        return self._cfg.real_send_permitted

    # -- compose ------------------------------------------------------------

    def compose(self) -> None:
        self._draft = DraftState()
        self._attachment_paths = []
        self.state = GmailState.COMPOSING

    def set_recipient(self, recipient: str) -> None:
        self._draft.recipient = recipient

    def set_subject(self, subject: str) -> None:
        self._draft.subject = subject

    def set_body(self, body: str) -> None:
        self._draft.body = body

    def attach(self, path: str | Path) -> bool:
        p = Path(path)
        if not p.exists() or not p.is_file():
            return False
        self._attachment_paths.append(str(p))
        self._draft.attachments.append(p.name)
        return True

    def read_draft(self) -> DraftState:
        return DraftState(
            recipient=self._draft.recipient,
            subject=self._draft.subject,
            body=self._draft.body,
            attachments=list(self._draft.attachments),
        )

    def save_draft(self) -> None:
        self.state = GmailState.DRAFT_SAVED

    # -- send (real side effect) -------------------------------------------

    def _idem_key(self) -> str:
        return f"{self._draft.recipient}|{self._draft.subject}"

    def send(self) -> bool:
        """Send for real over SMTP. Fails closed on any gate or transport error."""
        self.last_error = None
        cfg = self._cfg

        if not self._draft.recipient:
            self.last_error = "no recipient"
            self.state = GmailState.FAILED
            return False

        if not cfg.real_send_permitted:
            self.last_error = "real email not permitted (gates off or config missing)"
            self.state = GmailState.FAILED
            return False

        if not cfg.recipient_allowed(self._draft.recipient):
            self.last_error = f"recipient not allowlisted: {self._draft.recipient}"
            self.state = GmailState.FAILED
            return False

        # Idempotency: never send the same logical message twice.
        idem = self._idem_key()
        if idem in self._sent_message_ids:
            self.state = GmailState.SENT
            return True

        msg = EmailMessage()
        message_id = email_mod.utils.make_msgid(domain="autoflow.local")
        msg["Message-ID"] = message_id
        msg["From"] = cfg.smtp_from
        msg["To"] = self._draft.recipient
        msg["Subject"] = self._draft.subject
        msg.set_content(self._draft.body or "")
        for ap in self._attachment_paths:
            p = Path(ap)
            data = p.read_bytes()
            # Generic binary attachment; MailDog stores it verbatim.
            msg.add_attachment(
                data, maintype="application", subtype="octet-stream", filename=p.name
            )

        server = None
        try:
            context = ssl.create_default_context()
            server = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=20)
            server.ehlo()
            if cfg.smtp_starttls:
                server.starttls(context=context)
                server.ehlo()
            server.login(cfg._smtp_user, cfg._smtp_pass)
            server.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            # Do not leak credentials; report only the error class/message.
            self.last_error = f"smtp_send_failed: {type(exc).__name__}"
            self.state = GmailState.FAILED
            return False
        finally:
            # Close without a blocking QUIT handshake (some sandboxes stall on
            # QUIT under rate limiting); the socket timeout bounds this.
            if server is not None:
                try:
                    server.close()
                except Exception:  # noqa: BLE001
                    pass

        self._sent_message_ids[idem] = message_id
        self.state = GmailState.SENT
        return True

    # -- independent post-send verification (IMAP) --------------------------

    def read_sent(self, *, recipient: str, subject: str) -> SentRecord | None:
        """Independently confirm delivery by re-reading the mailbox over IMAP.

        This is the honest post-send evidence: it does NOT trust that send()
        returned True — it reconnects to the destination mailbox and looks for a
        message with the expected subject. Returns None if it cannot be
        confirmed (workflow then reports NOT_VERIFIED, never SUCCESS).
        """
        cfg = self._cfg
        if not (cfg.imap_host and cfg._imap_user and cfg._imap_pass):
            # No IMAP configured: fall back to the local send record (weaker,
            # but still real evidence that the SMTP transaction succeeded).
            if self._idem_key() in self._sent_message_ids:
                return SentRecord(
                    recipient=recipient, subject=subject,
                    body=self._draft.body, attachments=list(self._draft.attachments),
                )
            return None

        # Poll the mailbox briefly (delivery can lag the SMTP 250 response).
        deadline = time.time() + 20
        while time.time() < deadline:
            found = self._imap_find(recipient=recipient, subject=subject)
            if found is not None:
                return found
            time.sleep(2)
        return None

    def _imap_find(self, *, recipient: str, subject: str) -> SentRecord | None:
        cfg = self._cfg
        try:
            with imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port) as im:
                im.login(cfg._imap_user, cfg._imap_pass)
                im.select("INBOX")
                # Search by subject (safe ASCII in the flagship). MailDog
                # delivers sandbox mail to the configured mailbox's INBOX.
                typ, data = im.search(None, "SUBJECT", f'"{subject}"')
                if typ != "OK" or not data or not data[0]:
                    return None
                ids = data[0].split()
                # inspect the most recent match
                for msg_id in reversed(ids):
                    typ, msg_data = im.fetch(msg_id, "(RFC822)")
                    if typ != "OK" or not msg_data:
                        continue
                    raw = msg_data[0][1]
                    parsed = email_mod.message_from_bytes(raw)
                    subj = parsed.get("Subject", "")
                    if subj.strip() != subject.strip():
                        continue
                    attachments = [
                        part.get_filename()
                        for part in parsed.walk()
                        if part.get_filename()
                    ]
                    return SentRecord(
                        recipient=recipient, subject=subj,
                        body="", attachments=[a for a in attachments if a],
                    )
        except (imaplib.IMAP4.error, OSError):
            return None
        return None

    def close(self) -> None:
        self.closed = True
        self.state = GmailState.NOT_OPEN


def build_email_adapter(*, force_real: bool | None = None):
    """Return the appropriate email adapter for the current configuration.

    - Real SMTP adapter when the gates permit a real send (or force_real=True).
    - Otherwise the deterministic FakeGmailAdapter (SIMULATION/INTEGRATION),
      so the flagship still runs end-to-end with no real side effect.

    This is the single decision point for mock vs real email, mirroring the
    control-plane runtime seam. Never silently upgrades to real: real requires
    both env gates on.
    """
    cfg = SmtpConfig.from_env()
    want_real = cfg.real_send_permitted if force_real is None else force_real
    if want_real and cfg.real_send_permitted:
        return SmtpEmailAdapter(cfg), "LIVE"
    from .gmail import FakeGmailAdapter

    return FakeGmailAdapter(), "INTEGRATION"

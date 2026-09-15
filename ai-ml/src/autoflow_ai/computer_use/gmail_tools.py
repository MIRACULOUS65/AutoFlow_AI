"""Register Gmail tools into the EXISTING ToolRegistry.

These expose the semantic Gmail adapter as authorized tools so an agent drives
Gmail ONLY through the tool authority chain (never by calling the adapter
directly). ``gmail.send`` is HIGH risk and requires approval; everything else is
read/compose. Body/recipient values are sanitized (length only) in results so no
message content leaks into traces.
"""

from __future__ import annotations

from ..runtime.registry import ToolExecutionError, ToolRegistry
from ..schemas.enums import RiskClass
from ..schemas.tools import ToolDefinition


def register_gmail_tools(registry: ToolRegistry, adapter) -> None:
    def _obj(props, required=()):
        return {"type": "object", "properties": props, "required": list(required),
                "additionalProperties": False}

    def _open(_a):
        return {"state": str(adapter.open()), "authenticated": adapter.login_state()}

    registry.register(
        ToolDefinition(name="gmail.open", description="Open Gmail and report login state.",
                       input_schema=_obj({}), risk_class=RiskClass.LOW,
                       permission_scope="gmail:read"),
        _open,
    )

    def _compose(_a):
        adapter.compose()
        return {"composing": True}

    registry.register(
        ToolDefinition(name="gmail.compose", description="Start a new compose draft.",
                       input_schema=_obj({}), risk_class=RiskClass.LOW,
                       permission_scope="gmail:compose"),
        _compose,
    )

    def _set_recipient(a):
        adapter.set_recipient(a["recipient"])
        return {"recipient_set": True}

    registry.register(
        ToolDefinition(name="gmail.set_recipient", description="Set the draft recipient.",
                       input_schema=_obj({"recipient": {"type": "string"}}, ["recipient"]),
                       risk_class=RiskClass.LOW, permission_scope="gmail:compose"),
        _set_recipient,
    )

    def _set_subject(a):
        adapter.set_subject(a["subject"])
        return {"subject_set": True}

    registry.register(
        ToolDefinition(name="gmail.set_subject", description="Set the draft subject.",
                       input_schema=_obj({"subject": {"type": "string"}}, ["subject"]),
                       risk_class=RiskClass.LOW, permission_scope="gmail:compose"),
        _set_subject,
    )

    def _set_body(a):
        adapter.set_body(a["body"])
        return {"body_len": len(a["body"])}  # sanitized: length only

    registry.register(
        ToolDefinition(name="gmail.set_body", description="Set the draft body.",
                       input_schema=_obj({"body": {"type": "string"}}, ["body"]),
                       risk_class=RiskClass.LOW, permission_scope="gmail:compose"),
        _set_body,
    )

    def _attach(a):
        ok = adapter.attach(a["path"])
        if not ok:
            raise ToolExecutionError("attachment_failed", "attachment missing or upload failed")
        return {"attached": True}

    registry.register(
        ToolDefinition(name="gmail.attach", description="Attach a local file to the draft.",
                       input_schema=_obj({"path": {"type": "string"}}, ["path"]),
                       risk_class=RiskClass.MEDIUM, permission_scope="files:read"),
        _attach,
    )

    def _read_draft(_a):
        return adapter.read_draft().as_dict()

    registry.register(
        ToolDefinition(name="gmail.read_draft", description="Read the current draft state.",
                       input_schema=_obj({}), risk_class=RiskClass.LOW,
                       permission_scope="gmail:read", idempotent=True),
        _read_draft,
    )

    def _send(_a):
        ok = adapter.send()
        if not ok:
            raise ToolExecutionError("send_failed", "send failed (no recipient or transport)")
        return {"sent": True}

    # send is HIGH risk and requires approval — the only external side effect.
    registry.register(
        ToolDefinition(name="gmail.send", description="Send the draft (HIGH risk, requires approval).",
                       input_schema=_obj({}), risk_class=RiskClass.HIGH,
                       permission_scope="gmail:send", requires_approval=True),
        _send,
    )

    def _read_sent(a):
        rec = adapter.read_sent(recipient=a["recipient"], subject=a["subject"])
        if rec is None:
            return {"found": False}
        return {"found": True, "recipient": rec.recipient, "subject": rec.subject,
                "attachments": list(rec.attachments)}

    registry.register(
        ToolDefinition(name="gmail.read_sent", description="Inspect the Sent view for a message.",
                       input_schema=_obj({"recipient": {"type": "string"}, "subject": {"type": "string"}},
                                         ["recipient", "subject"]),
                       risk_class=RiskClass.LOW, permission_scope="gmail:read", idempotent=True),
        _read_sent,
    )

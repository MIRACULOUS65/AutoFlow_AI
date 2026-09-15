"""Gmail compose workflow tests (INTEGRATION via FakeGmailAdapter).

Safety-critical: sending is approval-bound to the EXACT message; any change
invalidates the approval; send never happens without approval; sent state is
independently verified; false success is impossible. Real Gmail is SKIP-gated.
"""

from __future__ import annotations

import os

import pytest

from autoflow_ai.computer_use.gmail import FakeGmailAdapter
from autoflow_ai.society import (
    Blackboard,
    EmailSpec,
    GmailComposeWorkflow,
    GmailOutcome,
    TrustClass,
)


def spec(**kw):
    base = dict(recipient="test@example.com", subject="Report", body="Please find attached.")
    base.update(kw)
    return EmailSpec(**base)


def wf(adapter=None, board=None):
    return GmailComposeWorkflow(adapter=adapter or FakeGmailAdapter(),
                                board=board or Blackboard(),
                                execution_id="exec_gmail1", task_id="gmail1")


def make_attachment(tmp_path, name="report.txt", content="hello report"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


# -- draft + verification ---------------------------------------------------

def test_gm_01_compose_and_verify_draft():
    w = wf()
    res, approval = w.compose_and_verify(spec())
    assert res.outcome == GmailOutcome.DRAFT_VERIFIED
    assert approval is not None
    assert res.draft["recipient"] == "test@example.com"


def test_gm_02_waiting_for_user_when_not_authenticated():
    w = wf(FakeGmailAdapter(authenticated=False))
    res, approval = w.compose_and_verify(spec())
    assert res.outcome == GmailOutcome.WAITING_FOR_USER
    assert approval is None


def test_gm_03_attachment_missing_fails_closed():
    w = wf()
    res, approval = w.compose_and_verify(spec(attachment_path="C:/does/not/exist.docx"))
    assert res.outcome == GmailOutcome.ATTACHMENT_INVALID
    assert approval is None


def test_gm_04_attachment_upload_failure_fails_closed(tmp_path):
    att = make_attachment(tmp_path)
    w = wf(FakeGmailAdapter(drop_attachment=True))
    res, approval = w.compose_and_verify(spec(attachment_path=att))
    assert res.outcome == GmailOutcome.ATTACHMENT_INVALID


def test_gm_05_draft_includes_attachment(tmp_path):
    att = make_attachment(tmp_path, name="doc.txt")
    w = wf()
    res, approval = w.compose_and_verify(spec(attachment_path=att))
    assert res.outcome == GmailOutcome.DRAFT_VERIFIED
    assert "doc.txt" in res.draft["attachments"]


# -- approval binding + send ------------------------------------------------

def test_gm_06_send_requires_approval():
    w = wf()
    res, approval = w.compose_and_verify(spec())
    # attempt to send WITHOUT approving
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.APPROVAL_REQUIRED
    assert sent.sent is False


def test_gm_07_send_after_approval_verified(tmp_path):
    att = make_attachment(tmp_path)
    board = Blackboard()
    w = wf(board=board)
    s = spec(attachment_path=att)
    res, approval = w.compose_and_verify(s)
    w.approve(approval)
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.SENT_VERIFIED
    assert sent.sent is True
    # independent Sent-view evidence posted as VERIFICATION
    ev = board.latest("sent:gmail1")
    assert ev is not None and ev.trust == TrustClass.VERIFICATION


def test_gm_08_changed_recipient_invalidates_approval():
    w = wf()
    res, approval = w.compose_and_verify(spec(recipient="alice@example.com"))
    w.approve(approval)
    # the live draft's recipient is tampered AFTER approval -> binding differs
    w._gmail.set_recipient("attacker@evil.com")  # noqa: SLF001
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.APPROVAL_INVALID
    assert sent.sent is False


def test_gm_09_changed_body_invalidates_approval():
    w = wf()
    res, approval = w.compose_and_verify(spec(body="original body"))
    w.approve(approval)
    w._gmail.set_body("tampered body")  # noqa: SLF001 - simulate draft change post-approval
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.APPROVAL_INVALID


def test_gm_10_changed_attachment_invalidates_approval(tmp_path):
    from pathlib import Path

    att = make_attachment(tmp_path, name="a.txt", content="one")
    w = wf()
    res, approval = w.compose_and_verify(spec(attachment_path=att))
    w.approve(approval)
    # same filename, but the file's bytes change after approval -> hash differs
    Path(att).write_text("completely different content now", encoding="utf-8")
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.APPROVAL_INVALID


def test_gm_11_send_failure_reported(tmp_path):
    w = wf(FakeGmailAdapter(send_fails=True))
    s = spec()
    res, approval = w.compose_and_verify(s)
    w.approve(approval)
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.SEND_FAILED
    assert sent.sent is False


def test_gm_12_no_sent_confirmation_is_not_verified(tmp_path):
    # send "succeeds" but the Sent view is unavailable -> NOT_VERIFIED, never SUCCESS
    w = wf(FakeGmailAdapter(sent_view_available=False))
    s = spec()
    res, approval = w.compose_and_verify(s)
    w.approve(approval)
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.NOT_VERIFIED
    assert sent.sent is False


def test_gm_13_approval_binding_hash_covers_all_fields(tmp_path):
    att = make_attachment(tmp_path)
    w = wf()
    _, a1 = w.compose_and_verify(spec(attachment_path=att))
    # a request for a different subject must produce a different binding hash
    w2 = wf()
    _, a2 = w2.compose_and_verify(spec(subject="Different Subject", attachment_path=att))
    assert a1.binding_hash() != a2.binding_hash()


def test_gm_14_sent_evidence_matches_recipient_and_attachment(tmp_path):
    att = make_attachment(tmp_path, name="final.txt")
    w = wf()
    s = spec(attachment_path=att)
    _, approval = w.compose_and_verify(s)
    w.approve(approval)
    sent = w.send_with_approval(approval)
    assert sent.outcome == GmailOutcome.SENT_VERIFIED
    steps = {st.stage: st.ok for st in sent.steps}
    assert steps.get("verify_sent_recipient") is True
    assert steps.get("verify_sent_attachment") is True


def test_gm_15_result_serializable(tmp_path):
    import json
    w = wf()
    s = spec()
    res, approval = w.compose_and_verify(s)
    w.approve(approval)
    sent = w.send_with_approval(approval)
    json.dumps(res.as_dict())
    json.dumps(sent.as_dict())


# -- real Gmail (opt-in only) ----------------------------------------------

@pytest.mark.skipif(os.environ.get("AUTOFLOW_REAL_GMAIL") != "1",
                    reason="real Gmail disabled (needs AUTOFLOW_REAL_GMAIL=1 + authenticated controlled account)")
def test_gm_16_real_gmail_placeholder():
    # A real Gmail adapter requires an authenticated browser session and a
    # controlled recipient. Not run in this environment; documented as SKIPPED.
    pytest.skip("real Gmail adapter requires an authenticated controlled account")

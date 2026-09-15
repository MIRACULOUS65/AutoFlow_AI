"""FLAGSHIP-01: end-to-end research/document -> email with approval + agenticity.

The mission is NON-hardcoded: the supervisor decides delegation from the plan.
The test verifies DECISIONS/EVIDENCE, not a prescribed agent sequence. Real
Gmail/Word/vision stay SKIP-gated; the flagship runs on the INTEGRATION path
(real python-docx document + fake Gmail DOM) so the agentic + safety properties
are proven without external accounts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from autoflow_ai.computer_use.gmail import FakeGmailAdapter
from autoflow_ai.society import (
    EmailSpec,
    FlagshipOutcome,
    FlagshipWorkflow,
    TrustClass,
    evaluate_agenticity,
)


def _fixtures(tmp_path):
    doc = tmp_path / "report.txt"
    doc.write_text("foo baseline report content", encoding="utf-8")
    att = tmp_path / "report_attachment.txt"
    att.write_text("attachment payload", encoding="utf-8")
    return str(doc), str(att)


def _email(att):
    return EmailSpec(recipient="reviewer@example.com", subject="Project Report",
                     body="Please find the report attached.", attachment_path=att)


def test_flag_01_full_flagship_complete(tmp_path):
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=True)
    res = wf.run(document_prompt="edit the document and save it", document_path=doc,
                 email=_email(att), execution_id="exec_flag01")
    assert res.complete
    assert res.document_verified and res.draft_verified and res.sent_verified
    assert res.agenticity["is_true_agentic"] is True


def test_flag_02_true_agenticity_all_properties(tmp_path):
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=True)
    res = wf.run(document_prompt="edit the document and save it", document_path=doc,
                 email=_email(att), execution_id="exec_flag02")
    ag = res.agenticity
    # every core agenticity property must hold for a true-agentic mission
    for prop in ("supervisor_present", "delegation_occurred", "nontrivial_handoff",
                 "verification_influenced_execution", "independent_qa",
                 "tool_authority_enforced", "success_evidence_gated"):
        assert ag[prop] is True, f"{prop} not satisfied: {ag['reasons']}"
    assert ag["is_true_agentic"] is True


def test_flag_03_no_send_without_approval(tmp_path):
    # auto_approve=False -> the flagship MUST stop before sending.
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=False)
    res = wf.run(document_prompt="edit the document and save it", document_path=doc,
                 email=_email(att), execution_id="exec_flag03")
    assert res.outcome == FlagshipOutcome.AWAITING_APPROVAL
    assert res.draft_verified is True
    assert res.sent_verified is False
    # the fake adapter must NOT have sent anything
    assert wf._gmail_adapter._sent == []  # noqa: SLF001


def test_flag_04_document_failure_stops_before_email(tmp_path):
    # missing document -> document phase fails; email phase never runs.
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=True)
    res = wf.run(document_prompt="edit the document and save it",
                 document_path=str(tmp_path / "missing.txt"),
                 email=_email(str(tmp_path)), execution_id="exec_flag04")
    assert res.outcome == FlagshipOutcome.DOCUMENT_FAILED
    assert res.draft_verified is False and res.sent_verified is False


def test_flag_05_send_failure_not_verified(tmp_path):
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(sent_view_available=False),
                          auto_approve=True)
    res = wf.run(document_prompt="edit the document and save it", document_path=doc,
                 email=_email(att), execution_id="exec_flag05")
    # send "succeeds" but cannot be confirmed -> NOT_VERIFIED, never COMPLETE
    assert res.outcome == FlagshipOutcome.NOT_VERIFIED
    assert res.complete is False


def test_flag_06_evidence_chain_on_blackboard(tmp_path):
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=True)
    wf.run(document_prompt="edit the document and save it", document_path=doc,
           email=_email(att), execution_id="exec_flag06")
    keys = {e.key for e in wf.board.all_entries()}
    # document verification + draft + sent evidence all present on one board
    assert any(k.startswith("verified:") for k in keys)
    assert "draft:flagship_gmail" in keys
    assert "sent:flagship_gmail" in keys
    sent = wf.board.latest("sent:flagship_gmail")
    assert sent.trust == TrustClass.VERIFICATION


def test_flag_07_delegation_was_dynamic_not_prescribed(tmp_path):
    # We assert the supervisor DECIDED delegation (task_request messages exist),
    # not that a specific agent ran a specific step.
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=True)
    wf.run(document_prompt="edit the document and save it", document_path=doc,
           email=_email(att), execution_id="exec_flag07")
    from autoflow_ai.society.messages import MessageType
    task_requests = [m for m in wf.supervisor.bus.messages if m.type == MessageType.TASK_REQUEST]
    assert len(task_requests) >= 2  # multiple subtasks delegated by capability


def test_flag_08_attachment_verified_in_sent(tmp_path):
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=True)
    wf.run(document_prompt="edit the document and save it", document_path=doc,
           email=_email(att), execution_id="exec_flag08")
    sent = wf.board.latest("sent:flagship_gmail")
    assert Path(att).name in sent.value["attachments"]


def test_flag_09_result_serializable(tmp_path):
    import json
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=True)
    res = wf.run(document_prompt="edit the document and save it", document_path=doc,
                 email=_email(att), execution_id="exec_flag09")
    json.dumps(res.as_dict())


def test_flag_10_no_false_success_when_incomplete(tmp_path):
    doc, att = _fixtures(tmp_path)
    wf = FlagshipWorkflow(gmail_adapter=FakeGmailAdapter(), auto_approve=False)
    res = wf.run(document_prompt="edit the document and save it", document_path=doc,
                 email=_email(att), execution_id="exec_flag10")
    # awaiting approval is NOT complete
    assert res.complete is False
    # and the document-phase agenticity had no false success
    assert res.agenticity["success_evidence_gated"] is True

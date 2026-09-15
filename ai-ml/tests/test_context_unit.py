"""Unit tests for the context engine components."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autoflow_ai.context import (
    ContextAssembler,
    ContextBudgetPolicy,
    ContextItem,
    ContextRanker,
    ContextSanitizer,
    ContextSection,
    TokenEstimator,
    TrustLevel,
)
from autoflow_ai.context.assembler import ContextInput
from autoflow_ai.context.authorization import AuthorizationContext, AuthorizationFilter

pytestmark = pytest.mark.unit


def _item(**o):
    base = dict(
        id="ctx_1",
        section=ContextSection.TASK_INSTRUCTION,
        content="edit the document",
        trust_level=TrustLevel.AUTHORIZED_USER_INPUT,
    )
    base.update(o)
    return ContextItem(**base)


# -- items -------------------------------------------------------------------


def test_item_content_hash_stable():
    a = _item(content="hello world")
    b = _item(content="hello world")
    assert a.content_hash == b.content_hash


def test_item_dedupe_key_normalizes_whitespace():
    a = _item(content="hello   world")
    b = _item(content="hello world")
    assert a.dedupe_key() == b.dedupe_key()


def test_item_authorization_metadata_flag():
    assert not _item().has_authorization_metadata
    assert _item(tenant_id="org_a", workspace_id="ws_b").has_authorization_metadata


def test_item_rejects_out_of_range_scores():
    with pytest.raises(ValidationError):
        _item(relevance=2.0)


# -- token estimator ---------------------------------------------------------


def test_token_estimator_is_marked_estimate():
    assert TokenEstimator().is_estimate is True


def test_token_estimator_scales_with_length():
    est = TokenEstimator()
    short = est.estimate_text("hi")
    long = est.estimate_text("word " * 100)
    assert long > short
    assert est.estimate_text("") == 0


# -- budget ------------------------------------------------------------------


def test_budget_reserves_output_first():
    policy = ContextBudgetPolicy(output_reserve_ratio=0.25, min_output_tokens=100)
    budget = policy.allocate(10_000)
    assert budget.reserved_output_tokens == 2500
    assert budget.input_budget == 7500
    # section budgets sum to <= input budget
    assert sum(budget.section_budgets.values()) <= budget.input_budget


def test_budget_min_output_floor():
    policy = ContextBudgetPolicy(output_reserve_ratio=0.01, min_output_tokens=500)
    budget = policy.allocate(10_000)
    assert budget.reserved_output_tokens == 500


def test_budget_rejects_bad_ratio():
    with pytest.raises(ValueError):
        ContextBudgetPolicy(output_reserve_ratio=1.5)


# -- ranker ------------------------------------------------------------------


def test_ranker_prefers_higher_relevance():
    ranker = ContextRanker()
    low = _item(id="ctx_low", relevance=0.1)
    high = _item(id="ctx_high", relevance=0.9)
    ranked = ranker.rank([low, high])
    assert ranked[0].id == "ctx_high"


def test_ranker_is_deterministic_ties_by_id():
    ranker = ContextRanker()
    a = _item(id="ctx_a", relevance=0.5, importance=0.5)
    b = _item(id="ctx_b", relevance=0.5, importance=0.5)
    assert [i.id for i in ranker.rank([b, a])] == ["ctx_a", "ctx_b"]


# -- authorization -----------------------------------------------------------


def _auth():
    return AuthorizationContext(tenant_id="org_a", workspace_id="ws_b", permissions=frozenset({"read"}))


def test_authorization_excludes_cross_tenant():
    item = _item(
        section=ContextSection.AUTHORIZED_KNOWLEDGE,
        trust_level=TrustLevel.AUTHORIZED_KNOWLEDGE,
        tenant_id="org_OTHER",
        workspace_id="ws_b",
        source_type="retrieved",
        source_id="doc_1",
    )
    result = AuthorizationFilter().filter([item], _auth())
    assert result.authorized == []
    assert "cross-tenant" in result.excluded[0][1]


def test_authorization_allows_matching_scope():
    item = _item(
        section=ContextSection.AUTHORIZED_KNOWLEDGE,
        trust_level=TrustLevel.AUTHORIZED_KNOWLEDGE,
        tenant_id="org_a",
        workspace_id="ws_b",
        permission_scope=frozenset({"read"}),
        source_type="retrieved",
        source_id="doc_1",
    )
    result = AuthorizationFilter().filter([item], _auth())
    assert len(result.authorized) == 1


def test_authorization_passes_non_protected_sections():
    item = _item(section=ContextSection.TASK_INSTRUCTION)
    result = AuthorizationFilter().filter([item], _auth())
    assert len(result.authorized) == 1


# -- sanitizer ---------------------------------------------------------------


def test_sanitizer_quarantines_malformed_provenance():
    item = _item(source_type="retrieved", source_id=None)
    result = ContextSanitizer().sanitize([item])
    assert result.accepted == []
    assert "provenance" in result.quarantined[0][1]


def test_sanitizer_rejects_trust_source_mismatch():
    item = _item(
        trust_level=TrustLevel.SYSTEM,
        source_type="external",
        source_id="x",
    )
    result = ContextSanitizer().sanitize([item])
    assert result.accepted == []
    assert "trust/source mismatch" in result.quarantined[0][1]


# -- assembler end-to-end ----------------------------------------------------


def _assemble(items, window=10_000):
    return ContextAssembler().assemble(
        ContextInput(
            request_id="mreq_a",
            task_id="task_a",
            model_id="model_x",
            context_window=window,
            auth=_auth(),
            items=items,
        )
    )


def test_assembler_produces_bundle_with_reserve():
    bundle = _assemble([_item()])
    assert bundle.reserved_output_tokens > 0
    assert bundle.token_budget > 0
    assert len(bundle.items) == 1


def test_assembler_hash_is_deterministic():
    b1 = _assemble([_item(), _item(id="ctx_2", content="another")])
    b2 = _assemble([_item(), _item(id="ctx_2", content="another")])
    assert b1.context_hash() == b2.context_hash()


def test_assembler_render_prompt_orders_sections():
    items = [
        _item(id="ctx_task", section=ContextSection.TASK_INSTRUCTION, content="TASKBODY"),
        _item(
            id="ctx_sys",
            section=ContextSection.SYSTEM_POLICY,
            content="SYSBODY",
            trust_level=TrustLevel.SYSTEM,
            source_type="system",
        ),
    ]
    prompt = _assemble(items).render_prompt()
    assert prompt.index("SYSTEM POLICY") < prompt.index("TASK INSTRUCTION")

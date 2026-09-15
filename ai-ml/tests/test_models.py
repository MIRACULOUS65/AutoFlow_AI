"""Tests for model gateway contracts and capability matching."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from autoflow_ai.schemas import (
    HealthState,
    Modality,
    ModelCapability,
    ModelDefinition,
    ModelRequest,
    ModelResponse,
    ModelRole,
    ModelUsage,
)

pytestmark = pytest.mark.contract


def _caps(**o) -> ModelCapability:
    return ModelCapability(**o)


def _model(**o) -> ModelDefinition:
    base = dict(
        model_id="model_a",
        provider="p",
        provider_model_name="m",
        display_name="M",
        roles=(ModelRole.PLANNER,),
        capabilities=_caps(tool_calling=True, structured_output=True),
        context_window=100_000,
        max_output_tokens=4096,
    )
    base.update(o)
    return ModelDefinition(**base)


def test_vision_capability_requires_image_modality():
    with pytest.raises(ValidationError, match="IMAGE modality"):
        ModelCapability(vision=True, modalities=(Modality.TEXT,))
    ModelCapability(vision=True, modalities=(Modality.TEXT, Modality.IMAGE))


def test_role_requires_matching_capability():
    with pytest.raises(ValidationError, match="embedding"):
        _model(roles=(ModelRole.EMBEDDING,), capabilities=_caps(embedding=False))
    with pytest.raises(ValidationError, match="vision"):
        _model(
            roles=(ModelRole.VISION,),
            capabilities=_caps(vision=False),
        )


def test_max_output_cannot_exceed_context():
    with pytest.raises(ValidationError, match="max_output_tokens"):
        _model(context_window=1000, max_output_tokens=2000)


def test_model_must_have_role_and_capability():
    with pytest.raises(ValidationError, match="at least one role"):
        _model(roles=())


def test_satisfies_matches_by_capability():
    m = _model(
        roles=(ModelRole.PLANNER,),
        capabilities=_caps(tool_calling=True, structured_output=True),
    )
    req = ModelRequest(
        request_id="mreq_1",
        required_role=ModelRole.PLANNER,
        required_capabilities={"structured_output": True},
    )
    assert m.satisfies(req)


def test_satisfies_rejects_wrong_role():
    m = _model(roles=(ModelRole.PLANNER,))
    req = ModelRequest(request_id="mreq_1", required_role=ModelRole.VISION)
    assert not m.satisfies(req)


def test_satisfies_rejects_missing_capability():
    m = _model(capabilities=_caps(vision=False))
    req = ModelRequest(
        request_id="mreq_1",
        required_role=ModelRole.PLANNER,
        required_capabilities={"vision": True},
    )
    assert not m.satisfies(req)


def test_satisfies_rejects_unhealthy_model():
    m = _model(health=HealthState.UNHEALTHY)
    req = ModelRequest(request_id="mreq_1", required_role=ModelRole.PLANNER)
    assert not m.satisfies(req)


def test_satisfies_respects_min_context_window():
    m = _model(context_window=1000, max_output_tokens=512)
    req = ModelRequest(
        request_id="mreq_1",
        required_role=ModelRole.PLANNER,
        min_context_window=2000,
    )
    assert not m.satisfies(req)


def test_request_rejects_unknown_capability_keys():
    with pytest.raises(ValidationError, match="unknown capability"):
        ModelRequest(
            request_id="mreq_1",
            required_role=ModelRole.PLANNER,
            required_capabilities={"telepathy": True},
        )


def test_require_structured_output_sets_capability():
    req = ModelRequest(
        request_id="mreq_1",
        required_role=ModelRole.PLANNER,
        require_structured_output=True,
    )
    assert req.required_capabilities.get("structured_output") is True


def test_model_usage_total_computed():
    u = ModelUsage(input_tokens=10, output_tokens=5)
    assert u.total_tokens == 15
    with pytest.raises(ValidationError, match="total_tokens"):
        ModelUsage(input_tokens=10, output_tokens=5, total_tokens=99)


def test_model_response_needs_content():
    with pytest.raises(ValidationError, match="text or structured_output"):
        ModelResponse(
            request_id="mreq_1",
            model_id="model_a",
            provider="p",
            finish_reason="stop",
        )
    ModelResponse(
        request_id="mreq_1",
        model_id="model_a",
        provider="p",
        finish_reason="stop",
        text="hi",
    )

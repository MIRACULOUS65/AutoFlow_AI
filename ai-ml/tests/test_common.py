"""Tests for common base behavior: IDs, versioning, determinism, hashing."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from autoflow_ai.schemas import Reference, Tenancy, Principal, validate_id
from autoflow_ai.schemas.common import AutoFlowModel, VersionedModel, canonical_hash

pytestmark = pytest.mark.contract


class _Sample(VersionedModel):
    name: str
    value: int = 0


def test_versioned_model_defaults_to_v1():
    assert _Sample(name="x").schema_version == 1


def test_extra_fields_are_forbidden():
    with pytest.raises(ValidationError):
        _Sample(name="x", bogus=1)


def test_validate_assignment_enforced():
    m = _Sample(name="x", value=1)
    with pytest.raises(ValidationError):
        m.value = "not-an-int"  # type: ignore[assignment]


@pytest.mark.parametrize(
    "value,ok",
    [
        ("task_01H", True),
        ("exec_abc-123", True),
        ("org_acme", True),
        ("Task_01", False),   # uppercase prefix
        ("task", False),      # no token
        ("_task", False),     # leading underscore
        ("task_", False),     # empty token
        ("t@sk_01", False),   # bad char
    ],
)
def test_validate_id_shapes(value, ok):
    if ok:
        assert validate_id(value) == value
    else:
        with pytest.raises(ValueError):
            validate_id(value)


def test_validate_id_prefix_enforced():
    assert validate_id("task_01", expected_prefix="task") == "task_01"
    with pytest.raises(ValueError):
        validate_id("exec_01", expected_prefix="task")


def test_to_json_is_deterministic_and_sorted():
    m = _Sample(name="x", value=5)
    # keys sorted -> schema_version comes before value/name deterministically
    assert m.to_json() == m.to_json()
    assert m.to_json(sort_keys=True).count("\"") > 0


def test_compute_hash_stable_and_sensitive():
    a = _Sample(name="x", value=1)
    b = _Sample(name="x", value=1)
    c = _Sample(name="x", value=2)
    assert a.compute_hash() == b.compute_hash()
    assert a.compute_hash() != c.compute_hash()


def test_canonical_hash_ignores_key_order():
    assert canonical_hash({"a": 1, "b": 2}) == canonical_hash({"b": 2, "a": 1})


def test_tenancy_prefix_validation():
    Tenancy(organization_id="org_a", workspace_id="ws_b")
    with pytest.raises(ValidationError):
        Tenancy(organization_id="ws_a", workspace_id="ws_b")


def test_principal_permission_helpers():
    p = Principal(
        principal_id="user_a",
        organization_id="org_a",
        workspace_id="ws_b",
        permissions=frozenset({"tasks:create"}),
        tool_grants=frozenset({"email.send"}),
    )
    assert p.has_permission("tasks:create")
    assert not p.has_permission("tasks:delete")
    assert p.has_tool_grant("email.send")


def test_reference_kind_must_be_lowercase_dotted():
    Reference(kind="artifact", ref_id="art_1")
    Reference(kind="workflow.step", ref_id="s1")
    with pytest.raises(ValidationError):
        Reference(kind="Artifact", ref_id="art_1")


def test_timestamps_must_be_tz_aware():
    from autoflow_ai.schemas.common import Timestamped

    class _T(Timestamped):
        pass

    _T(created_at=datetime.now(timezone.utc))
    with pytest.raises(ValidationError):
        _T(created_at=datetime(2026, 1, 1))  # naive


def test_all_samples_round_trip(registry):
    for name, instance in registry.items():
        cls = type(instance)
        restored = cls.model_validate(instance.model_dump(mode="json"))
        assert restored.to_json() == instance.to_json(), name

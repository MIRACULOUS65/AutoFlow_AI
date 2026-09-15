"""Common base classes and value objects for AutoFlow AI contracts.

Design rules (from the master prompt and ai-ml docs):

* Every contract is a strict Pydantic model that forbids unknown fields.
* Every contract is versioned via ``schema_version``.
* IDs are validated for a stable, human-readable ``prefix_token`` shape.
* Serialization is deterministic (sorted keys handled by callers; enums are
  bare string values; datetimes are timezone-aware ISO-8601 in UTC).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Annotated, Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

# ---------------------------------------------------------------------------
# ID handling
# ---------------------------------------------------------------------------

# IDs look like ``task_01H...`` / ``exec_abc123`` / ``wf_1``: a lowercase
# prefix, an underscore, then an alphanumeric token (1-64 chars, may contain
# hyphens after the first character). This keeps IDs self-describing in logs
# and events without coupling to any specific ID generator.
_ID_RE = re.compile(r"^[a-z][a-z0-9]*_[A-Za-z0-9][A-Za-z0-9\-]{0,63}$")

# A typed string used for all identifier fields.
IdStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=3, max_length=80),
]


def validate_id(value: str, *, expected_prefix: str | None = None) -> str:
    """Validate an identifier and optionally enforce a prefix.

    Raises ``ValueError`` when the id does not match ``prefix_token`` or the
    prefix does not match ``expected_prefix``.
    """

    if not _ID_RE.match(value):
        raise ValueError(
            f"invalid id {value!r}: expected '<prefix>_<token>' "
            "(lowercase prefix, alphanumeric token)"
        )
    if expected_prefix is not None:
        prefix = value.split("_", 1)[0]
        if prefix != expected_prefix:
            raise ValueError(
                f"invalid id {value!r}: expected prefix {expected_prefix!r}, "
                f"got {prefix!r}"
            )
    return value


def prefixed_id_validator(expected_prefix: str):
    """Build a reusable field validator enforcing an id prefix."""

    def _validate(value: str) -> str:
        return validate_id(value, expected_prefix=expected_prefix)

    return _validate


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""

    return datetime.now(timezone.utc)


def _is_set_type(annotation: Any) -> bool:
    """True when a field annotation is a set/frozenset (possibly Optional)."""

    import typing

    if annotation in (set, frozenset):
        return True
    origin = typing.get_origin(annotation)
    if origin in (set, frozenset):
        return True
    # Unwrap Optional/Union: True if any member is a set/frozenset.
    if origin is not None:
        for arg in typing.get_args(annotation):
            if arg in (set, frozenset) or typing.get_origin(arg) in (set, frozenset):
                return True
    return False


# ---------------------------------------------------------------------------
# Base model
# ---------------------------------------------------------------------------


class AutoFlowModel(BaseModel):
    """Base for every AutoFlow contract.

    * ``extra="forbid"`` — reject unknown fields (RULE: reject unknown critical
      fields). Contracts that intentionally hold free-form payloads use a
      dedicated ``dict`` field rather than loosening this.
    * ``validate_assignment=True`` — keep invariants after mutation.
    * ``use_enum_values=False`` — keep Enum instances in memory; JSON dump
      still emits the bare string value.
    * ``frozen=False`` — models are mutable but validated on assignment.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        use_enum_values=False,
        ser_json_timedelta="iso8601",
        str_strip_whitespace=True,
    )

    def canonical_dict(self) -> dict[str, Any]:
        """JSON-mode dump with set/frozenset fields emitted as *sorted* lists.

        Pydantic converts ``set``/``frozenset`` fields to lists in JSON mode
        but preserves the (nondeterministic) iteration order. For deterministic
        serialization, hashing and round-trip stability we sort those lists.
        Ordered fields (tuples/lists) are left untouched so meaningful order
        (e.g. DAG nodes) is preserved.
        """

        payload = self.model_dump(mode="json")
        for name, field in type(self).model_fields.items():
            if name in payload and _is_set_type(field.annotation):
                value = payload[name]
                if isinstance(value, list):
                    payload[name] = sorted(value, key=lambda x: json.dumps(x, sort_keys=True, default=str))
        return payload

    def to_json(self, *, sort_keys: bool = True) -> str:
        """Deterministic JSON serialization.

        Uses Pydantic for type-correct conversion (enums -> values, datetimes
        -> ISO strings), canonicalizes set-origin fields, then re-serializes
        with sorted keys for stable hashing/round-trips.
        """

        return json.dumps(
            self.canonical_dict(),
            sort_keys=sort_keys,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    def compute_hash(self) -> str:
        """Stable SHA-256 over the deterministic JSON form.

        Named ``compute_hash`` (not ``content_hash``) so it never collides with
        contracts that carry a ``content_hash`` *field* (e.g. Artifact).
        """

        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


class VersionedModel(AutoFlowModel):
    """A contract that carries an explicit schema version."""

    schema_version: int = Field(default=1, ge=1)


# ---------------------------------------------------------------------------
# Shared value objects
# ---------------------------------------------------------------------------


class Tenancy(AutoFlowModel):
    """Tenant + workspace scoping applied to nearly everything.

    Authorization is enforced outside semantic retrieval; this object carries
    the scope so downstream code can filter deterministically.
    """

    organization_id: IdStr
    workspace_id: IdStr

    @field_validator("organization_id")
    @classmethod
    def _org(cls, v: str) -> str:
        return validate_id(v, expected_prefix="org")

    @field_validator("workspace_id")
    @classmethod
    def _ws(cls, v: str) -> str:
        return validate_id(v, expected_prefix="ws")


class Principal(AutoFlowModel):
    """The authenticated actor and its authorization scope.

    Permissions/roles are explicit strings; the runtime checks them before any
    side effect. Connector/tool grants and knowledge scopes gate access.
    """

    principal_id: IdStr
    organization_id: IdStr
    workspace_id: IdStr
    roles: tuple[str, ...] = ()
    permissions: frozenset[str] = frozenset()
    tool_grants: frozenset[str] = frozenset()
    connector_grants: frozenset[str] = frozenset()
    knowledge_scopes: frozenset[str] = frozenset()

    @field_validator("principal_id")
    @classmethod
    def _pid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="user")

    @field_validator("organization_id")
    @classmethod
    def _org(cls, v: str) -> str:
        return validate_id(v, expected_prefix="org")

    @field_validator("workspace_id")
    @classmethod
    def _ws(cls, v: str) -> str:
        return validate_id(v, expected_prefix="ws")

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_tool_grant(self, tool_name: str) -> bool:
        return tool_name in self.tool_grants


class Reference(AutoFlowModel):
    """A typed reference to another entity or artifact.

    Used for provenance/evidence and for wiring inputs between steps without
    embedding full payloads.
    """

    kind: str = Field(min_length=1, max_length=64)
    ref_id: str = Field(min_length=1, max_length=256)
    uri: str | None = Field(default=None, max_length=2048)

    @field_validator("kind")
    @classmethod
    def _kind(cls, v: str) -> str:
        if not re.match(r"^[a-z][a-z0-9_.]*$", v):
            raise ValueError(
                "reference.kind must be snake/dotted lowercase, e.g. 'artifact'"
            )
        return v


class Timestamped(AutoFlowModel):
    """Mixin providing created/updated timestamps."""

    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime | None = None

    @field_validator("created_at", "updated_at")
    @classmethod
    def _tz_aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware (UTC)")
        return v


def canonical_hash(payload: Any) -> str:
    """SHA-256 over a canonical JSON representation of arbitrary JSON data."""

    text = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

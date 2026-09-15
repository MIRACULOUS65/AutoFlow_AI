"""Model gateway contracts.

Models are selected by *capability*, never hard-coded by identity. These
contracts describe a registered model, a request for capabilities, and the
normalized response. Secrets never appear here.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import IdStr, Reference, VersionedModel, validate_id
from .enums import DeploymentType, HealthState, Modality, ModelRole


class ModelCapability(VersionedModel):
    """Declared capabilities of a model (MR-02)."""

    text: bool = True
    vision: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    reasoning: bool = False
    coding: bool = False
    embedding: bool = False
    streaming: bool = False
    modalities: tuple[Modality, ...] = (Modality.TEXT,)

    @model_validator(mode="after")
    def _at_least_one_modality(self) -> "ModelCapability":
        if not self.modalities:
            raise ValueError("model must declare at least one modality")
        if self.vision and Modality.IMAGE not in self.modalities:
            raise ValueError("vision=True requires IMAGE modality")
        return self


class ModelDefinition(VersionedModel):
    """A registered model entry in the model registry."""

    model_id: IdStr
    provider: str = Field(min_length=1, max_length=64)
    provider_model_name: str = Field(min_length=1, max_length=128)
    display_name: str = Field(min_length=1, max_length=128)
    roles: tuple[ModelRole, ...]
    capabilities: ModelCapability
    context_window: int = Field(gt=0, le=10_000_000)
    max_output_tokens: int = Field(gt=0, le=1_000_000)
    deployment: DeploymentType = DeploymentType.CLOUD_API
    health: HealthState = HealthState.UNKNOWN
    # Routing / cost metadata (all optional; no secrets).
    routing_priority: int = Field(default=100, ge=0, le=10_000)
    expected_latency_ms: int | None = Field(default=None, ge=0)
    cost_input_per_1k: float | None = Field(default=None, ge=0)
    cost_output_per_1k: float | None = Field(default=None, ge=0)
    policy_tags: frozenset[str] = frozenset()
    # Some providers only return content via SSE streaming (e.g. reasoning
    # models on ModelScope). When True, the provider must use its streaming
    # path and aggregate deltas into the final response.
    requires_streaming: bool = False

    @field_validator("model_id")
    @classmethod
    def _mid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="model")

    @field_validator("roles")
    @classmethod
    def _roles_nonempty(cls, v: tuple[ModelRole, ...]) -> tuple[ModelRole, ...]:
        if not v:
            raise ValueError("model must declare at least one role")
        return v

    @model_validator(mode="after")
    def _role_capability_consistency(self) -> "ModelDefinition":
        caps = self.capabilities
        if ModelRole.EMBEDDING in self.roles and not caps.embedding:
            raise ValueError("embedding role requires capabilities.embedding=True")
        if ModelRole.VISION in self.roles and not caps.vision:
            raise ValueError("vision role requires capabilities.vision=True")
        if ModelRole.TOOL_CALLER in self.roles and not caps.tool_calling:
            raise ValueError("tool_caller role requires capabilities.tool_calling=True")
        if ModelRole.CODING in self.roles and not caps.coding:
            raise ValueError("coding role requires capabilities.coding=True")
        if self.max_output_tokens > self.context_window:
            raise ValueError("max_output_tokens cannot exceed context_window")
        return self

    def satisfies(self, request: "ModelRequest") -> bool:
        """Return True when this model can serve the requested capability."""

        if request.required_role not in self.roles:
            return False
        req = request.required_capabilities
        caps = self.capabilities
        checks = (
            (req.get("vision"), caps.vision),
            (req.get("tool_calling"), caps.tool_calling),
            (req.get("structured_output"), caps.structured_output),
            (req.get("reasoning"), caps.reasoning),
            (req.get("coding"), caps.coding),
            (req.get("embedding"), caps.embedding),
            (req.get("streaming"), caps.streaming),
        )
        for needed, available in checks:
            if needed and not available:
                return False
        if request.min_context_window and self.context_window < request.min_context_window:
            return False
        if self.health == HealthState.UNHEALTHY:
            return False
        return True


class ModelRequest(VersionedModel):
    """A capability-oriented request routed by the gateway.

    The agent asks for a role + capabilities; the gateway picks the model.
    """

    request_id: IdStr
    required_role: ModelRole
    required_capabilities: dict[str, bool] = Field(default_factory=dict)
    min_context_window: int | None = Field(default=None, gt=0)
    max_risk_tolerated: bool = True
    # The assembled prompt/messages are opaque here; the gateway owns the
    # provider-specific shaping. We only carry a hash for tracing.
    prompt_hash: str | None = Field(default=None, min_length=8, max_length=128)
    max_output_tokens: int | None = Field(default=None, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    require_structured_output: bool = False
    output_schema_ref: Reference | None = None
    timeout_seconds: float = Field(default=60.0, gt=0, le=3600)

    @field_validator("request_id")
    @classmethod
    def _rid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="mreq")

    @field_validator("required_capabilities")
    @classmethod
    def _known_caps(cls, v: dict[str, bool]) -> dict[str, bool]:
        allowed = {
            "vision",
            "tool_calling",
            "structured_output",
            "reasoning",
            "coding",
            "embedding",
            "streaming",
        }
        unknown = set(v) - allowed
        if unknown:
            raise ValueError(f"unknown capability keys: {sorted(unknown)}")
        return v

    @model_validator(mode="after")
    def _structured_requires_capability(self) -> "ModelRequest":
        if self.require_structured_output:
            self.required_capabilities.setdefault("structured_output", True)
        return self


class ModelUsage(VersionedModel):
    """Token/cost accounting for a single model call."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: int | None = Field(default=None, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _fill_total(cls, data):
        # Runs before construction so we never assign to a field inside an
        # ``after`` validator (which would re-trigger validate_assignment and
        # recurse). Fills total when omitted/zero; validates when provided.
        if isinstance(data, dict):
            inp = data.get("input_tokens", 0) or 0
            out = data.get("output_tokens", 0) or 0
            computed = inp + out
            total = data.get("total_tokens", 0) or 0
            if total == 0:
                data["total_tokens"] = computed
            elif total != computed:
                raise ValueError("total_tokens must equal input + output tokens")
        return data


class ModelResponse(VersionedModel):
    """Normalized model response returned by any provider adapter."""

    request_id: IdStr
    model_id: IdStr
    provider: str = Field(min_length=1, max_length=64)
    finish_reason: str = Field(min_length=1, max_length=64)
    text: str | None = None
    structured_output: dict | None = None
    usage: ModelUsage = Field(default_factory=ModelUsage)
    is_fallback: bool = False

    @field_validator("request_id")
    @classmethod
    def _rid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="mreq")

    @field_validator("model_id")
    @classmethod
    def _mid(cls, v: str) -> str:
        return validate_id(v, expected_prefix="model")

    @model_validator(mode="after")
    def _has_content(self) -> "ModelResponse":
        if self.text is None and self.structured_output is None:
            raise ValueError("model response must have text or structured_output")
        return self

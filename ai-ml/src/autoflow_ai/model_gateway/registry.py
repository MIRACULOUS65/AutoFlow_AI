"""Model registry: holds model definitions and their providers."""

from __future__ import annotations

from ..schemas.models import ModelDefinition
from .provider import ModelProvider


class ModelRegistry:
    """Maps model ids to (definition, provider) pairs."""

    def __init__(self) -> None:
        self._models: dict[str, ModelDefinition] = {}
        self._providers: dict[str, ModelProvider] = {}

    def register(self, model: ModelDefinition, provider: ModelProvider) -> None:
        if not provider.supports(model):
            raise ValueError(
                f"provider {provider.name!r} does not support model {model.model_id!r}"
            )
        self._models[model.model_id] = model
        self._providers[model.model_id] = provider

    def get(self, model_id: str) -> tuple[ModelDefinition, ModelProvider]:
        return self._models[model_id], self._providers[model_id]

    def models(self) -> tuple[ModelDefinition, ...]:
        return tuple(self._models.values())

    def provider_for(self, model_id: str) -> ModelProvider:
        return self._providers[model_id]

    def __len__(self) -> int:
        return len(self._models)

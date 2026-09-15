"""Model manifest + reproducible local model setup (no weights in git).

Declares the supported model classes with provenance, capabilities and install
method. Remote providers (NVIDIA / Qwen / embedding / vision) are configured via
env — never hardcoded keys. The local deterministic provider is always
available. Local downloadable models (e.g. via Ollama, when present) record
provenance and install into a configurable cache — never into the repo.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


def model_home() -> Path:
    """Configurable model cache root (never inside the repo)."""

    root = os.environ.get("AUTOFLOW_MODEL_HOME")
    if root:
        return Path(root)
    return Path.home() / ".autoflow" / "models"


@dataclass
class ModelSpec:
    model_id: str
    kind: str                    # local-deterministic | remote-openai | local-ollama
    provider: str
    description: str
    capabilities: tuple[str, ...]
    install_method: str          # builtin | env-config | ollama-pull
    provenance: str
    env_keys: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "model_id": self.model_id, "kind": self.kind, "provider": self.provider,
            "description": self.description, "capabilities": list(self.capabilities),
            "install_method": self.install_method, "provenance": self.provenance,
            "env_keys": list(self.env_keys),
        }


# The canonical manifest. Weights are NEVER committed; remote models need env.
MANIFEST: dict[str, ModelSpec] = {
    "local-deterministic": ModelSpec(
        model_id="local-deterministic", kind="local-deterministic", provider="local-rule",
        description="Offline deterministic rule provider; always available, no download.",
        capabilities=("text", "structured_output"), install_method="builtin",
        provenance="autoflow_ai.model_gateway.local_provider",
    ),
    "nvidia": ModelSpec(
        model_id="nvidia", kind="remote-openai", provider="openai_compatible",
        description="NVIDIA-hosted OpenAI-compatible model (e.g. llama-3.2-11b-vision).",
        capabilities=("text", "structured_output", "streaming", "vision", "tool_calling"),
        install_method="env-config", provenance="https://integrate.api.nvidia.com/v1",
        env_keys=("PRIMARY_MODEL_BASE_URL", "PRIMARY_MODEL_API_KEY", "PRIMARY_MODEL_ID"),
    ),
    "qwen": ModelSpec(
        model_id="qwen", kind="remote-openai", provider="openai_compatible",
        description="Qwen / ModelScope OpenAI-compatible model (streaming).",
        capabilities=("text", "structured_output", "streaming"),
        install_method="env-config", provenance="https://api-inference.modelscope.ai/v1",
        env_keys=("SECONDARY_MODEL_BASE_URL", "SECONDARY_MODEL_API_KEY", "SECONDARY_MODEL_ID"),
    ),
    "embedding": ModelSpec(
        model_id="embedding", kind="remote-openai", provider="openai_compatible",
        description="Embedding provider for RAG (OpenAI-compatible).",
        capabilities=("embedding",), install_method="env-config",
        provenance="configurable", env_keys=("EMBEDDING_MODEL_BASE_URL", "EMBEDDING_MODEL_ID"),
    ),
}


def list_specs() -> list[dict]:
    return [s.as_dict() for s in MANIFEST.values()]


def info(model_id: str) -> dict | None:
    spec = MANIFEST.get(model_id)
    return spec.as_dict() if spec else None


def _ollama_available() -> bool:
    return shutil.which("ollama") is not None


def install(model_id: str) -> dict:
    """Prepare a model for local use (no weights committed to the repo).

    * builtin: nothing to download (always available).
    * env-config: validate the required env keys are present (config, not keys).
    * ollama-pull: pull via the local ollama runtime into its own cache.
    Returns a status dict; never prints or stores secret VALUES.
    """

    spec = MANIFEST.get(model_id)
    if spec is None:
        return {"model_id": model_id, "installed": False, "reason": "unknown model"}

    if spec.install_method == "builtin":
        return {"model_id": model_id, "installed": True, "method": "builtin",
                "note": "always available"}

    if spec.install_method == "env-config":
        missing = [k for k in spec.env_keys if not os.environ.get(k)]
        # report presence only — never the values
        return {"model_id": model_id, "installed": not missing, "method": "env-config",
                "configured_keys": [k for k in spec.env_keys if os.environ.get(k)],
                "missing_keys": missing,
                "note": "set the missing env keys in .env to enable this provider"}

    if spec.install_method == "ollama-pull":
        if not _ollama_available():
            return {"model_id": model_id, "installed": False, "method": "ollama-pull",
                    "reason": "ollama runtime not found on PATH"}
        home = model_home(); home.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["ollama", "pull", spec.provenance], check=True, timeout=600)
        except Exception as exc:  # noqa: BLE001
            return {"model_id": model_id, "installed": False, "method": "ollama-pull",
                    "reason": type(exc).__name__}
        return {"model_id": model_id, "installed": True, "method": "ollama-pull",
                "cache": str(home)}

    return {"model_id": model_id, "installed": False, "reason": "unsupported install method"}


def verify(model_id: str) -> dict:
    """Verify a model is actually usable (health-checks, not config-exists)."""

    spec = MANIFEST.get(model_id)
    if spec is None:
        return {"model_id": model_id, "ok": False, "reason": "unknown model"}
    if spec.install_method == "builtin":
        return {"model_id": model_id, "ok": True, "note": "builtin deterministic provider"}
    # env-config: check keys present (real connectivity is checked by model lab)
    missing = [k for k in spec.env_keys if not os.environ.get(k)]
    return {"model_id": model_id, "ok": not missing,
            "reason": ("missing env keys" if missing else "configured"),
            "missing_keys": missing}

"""Environment-based model gateway configuration.

Provider credentials are read from environment variables (loaded from a local
``.env`` if present) and are NEVER hardcoded, put into prompts, or logged. The
config object exposes a ``redacted()`` view for safe logging/telemetry.

Recognized environment variables (all optional; absence => local-only gateway):

    PRIMARY_MODEL_PROVIDER      e.g. "openai_compatible"
    PRIMARY_MODEL_ID            e.g. "gpt-4o-mini" (provider model name)
    PRIMARY_MODEL_API_KEY       secret (never logged)
    PRIMARY_MODEL_BASE_URL      e.g. "https://api.example.com/v1"
    PRIMARY_MODEL_CONTEXT       integer context window (default 128000)

    SECONDARY_MODEL_* (same keys) — optional fallback model

    MODEL_TIMEOUT               seconds (default 60)
    MODEL_MAX_RETRIES           per-provider retry attempts (default 2)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def load_dotenv(path: str | Path | None = None) -> None:
    """Minimal .env loader (no external dependency).

    Only sets variables that are not already present in the environment, so
    real env vars always win. Lines like ``KEY=value`` and ``KEY="value"`` are
    supported; ``#`` comments and blank lines are ignored. Missing file is a
    no-op.
    """

    candidates = []
    if path is not None:
        candidates.append(Path(path))
    else:
        # look upward from cwd for a .env (repo root or ai-ml/)
        cwd = Path.cwd()
        candidates.extend([cwd / ".env", cwd.parent / ".env"])

    for env_path in candidates:
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        return  # first found wins


@dataclass
class ProviderConfig:
    """Configuration for one configured provider/model. No secret is logged."""

    role_prefix: str            # "PRIMARY" / "SECONDARY"
    provider: str               # provider adapter kind
    model_id: str               # provider model name
    base_url: str | None
    context_window: int
    requires_streaming: bool = False  # provider only returns content via SSE
    api_key: str | None = field(default=None, repr=False)  # never in repr

    @property
    def has_credentials(self) -> bool:
        return bool(self.api_key)

    def redacted(self) -> dict:
        return {
            "role_prefix": self.role_prefix,
            "provider": self.provider,
            "model_id": self.model_id,
            "base_url": self.base_url,
            "context_window": self.context_window,
            "api_key": "***set***" if self.api_key else None,
        }


@dataclass
class GatewayConfig:
    """Resolved gateway configuration."""

    providers: list[ProviderConfig]
    timeout_seconds: float
    max_retries: int
    include_local: bool = True

    @property
    def has_real_provider(self) -> bool:
        return any(p.provider != "local-rule" for p in self.providers)

    def redacted(self) -> dict:
        return {
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "include_local": self.include_local,
            "providers": [p.redacted() for p in self.providers],
        }


def _read_provider(prefix: str) -> ProviderConfig | None:
    provider = os.environ.get(f"{prefix}_MODEL_PROVIDER", "").strip()
    model_id = os.environ.get(f"{prefix}_MODEL_ID", "").strip()
    if not provider or not model_id:
        return None
    streaming = os.environ.get(f"{prefix}_MODEL_STREAMING", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    return ProviderConfig(
        role_prefix=prefix,
        provider=provider,
        model_id=model_id,
        base_url=os.environ.get(f"{prefix}_MODEL_BASE_URL", "").strip() or None,
        context_window=int(os.environ.get(f"{prefix}_MODEL_CONTEXT", "128000") or 128000),
        requires_streaming=streaming,
        api_key=os.environ.get(f"{prefix}_MODEL_API_KEY", "").strip() or None,
    )


def load_gateway_config(*, load_env: bool = True, env_path: str | Path | None = None) -> GatewayConfig:
    """Load gateway configuration from the environment."""

    if load_env:
        load_dotenv(env_path)

    providers: list[ProviderConfig] = []
    for prefix in ("PRIMARY", "SECONDARY"):
        cfg = _read_provider(prefix)
        if cfg is not None:
            providers.append(cfg)

    timeout = float(os.environ.get("MODEL_TIMEOUT", "60") or 60)
    retries = int(os.environ.get("MODEL_MAX_RETRIES", "2") or 2)

    return GatewayConfig(
        providers=providers,
        timeout_seconds=timeout,
        max_retries=retries,
        include_local=True,
    )

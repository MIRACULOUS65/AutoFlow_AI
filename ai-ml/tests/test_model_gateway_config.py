"""Tests for gateway config loading (env-based, secret-safe)."""

from __future__ import annotations

import pytest

from autoflow_ai.model_gateway.config import (
    GatewayConfig,
    ProviderConfig,
    load_gateway_config,
    load_dotenv,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in list(__import__("os").environ):
        if key.endswith("_MODEL_PROVIDER") or key.endswith("_MODEL_ID") or key.endswith("_MODEL_API_KEY") or key.endswith("_MODEL_BASE_URL") or key.endswith("_MODEL_CONTEXT"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.delenv("MODEL_TIMEOUT", raising=False)
    monkeypatch.delenv("MODEL_MAX_RETRIES", raising=False)


def test_no_provider_configured_gives_local_only():
    cfg = load_gateway_config(load_env=False)
    assert cfg.providers == []
    assert not cfg.has_real_provider
    assert cfg.include_local is True


def test_primary_provider_loaded(monkeypatch):
    monkeypatch.setenv("PRIMARY_MODEL_PROVIDER", "openai_compatible")
    monkeypatch.setenv("PRIMARY_MODEL_ID", "gpt-test")
    monkeypatch.setenv("PRIMARY_MODEL_API_KEY", "super-secret")
    monkeypatch.setenv("PRIMARY_MODEL_BASE_URL", "https://api.example.com/v1")
    cfg = load_gateway_config(load_env=False)
    assert cfg.has_real_provider
    p = cfg.providers[0]
    assert p.provider == "openai_compatible"
    assert p.model_id == "gpt-test"
    assert p.has_credentials


def test_config_redacted_hides_secret(monkeypatch):
    monkeypatch.setenv("PRIMARY_MODEL_PROVIDER", "openai_compatible")
    monkeypatch.setenv("PRIMARY_MODEL_ID", "gpt-test")
    monkeypatch.setenv("PRIMARY_MODEL_API_KEY", "super-secret")
    cfg = load_gateway_config(load_env=False)
    red = cfg.redacted()
    text = str(red)
    assert "super-secret" not in text
    assert red["providers"][0]["api_key"] == "***set***"


def test_provider_config_repr_hides_secret():
    p = ProviderConfig(
        role_prefix="PRIMARY",
        provider="openai_compatible",
        model_id="m",
        base_url=None,
        context_window=1000,
        api_key="secret123",
    )
    assert "secret123" not in repr(p)


def test_dotenv_does_not_override_real_env(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("PRIMARY_MODEL_ID=from-file\n", encoding="utf-8")
    monkeypatch.setenv("PRIMARY_MODEL_ID", "from-env")
    load_dotenv(env)
    import os

    assert os.environ["PRIMARY_MODEL_ID"] == "from-env"


def test_timeout_and_retries_from_env(monkeypatch):
    monkeypatch.setenv("MODEL_TIMEOUT", "12")
    monkeypatch.setenv("MODEL_MAX_RETRIES", "5")
    cfg = load_gateway_config(load_env=False)
    assert cfg.timeout_seconds == 12
    assert cfg.max_retries == 5

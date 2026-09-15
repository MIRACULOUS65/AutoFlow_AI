"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import warnings

import pytest

from autoflow_ai import samples


@pytest.fixture
def registry():
    """One valid instance of every contract, keyed by class name."""

    return samples.build_sample_registry()


@pytest.fixture(autouse=True)
def _hermetic_gateway(monkeypatch):
    """Keep the test suite hermetic and fast: force the local provider.

    Real provider config lives in the repo .env for interactive/CLI use, but
    tests must not depend on network or a paid endpoint. Clearing the provider
    env vars and disabling dotenv loading makes build_gateway() local-only.
    """

    for prefix in ("PRIMARY", "SECONDARY"):
        for suffix in ("PROVIDER", "ID", "API_KEY", "BASE_URL", "CONTEXT"):
            monkeypatch.delenv(f"{prefix}_MODEL_{suffix}", raising=False)
    # Never let a real web-search opt-in leak into the default test run. Tests
    # that exercise real web navigation set this explicitly and are SKIP-gated.
    monkeypatch.delenv("AUTOFLOW_ALLOW_WEB", raising=False)
    # Make the dotenv loader a no-op so it can't repopulate provider vars.
    import autoflow_ai.model_gateway.config as _cfg

    monkeypatch.setattr(_cfg, "load_dotenv", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _fail_on_pydantic_shadow_warning():
    """Turn Pydantic field-shadow warnings into errors during tests.

    A field shadowing a base attribute is a design bug; fail loudly.
    """

    with warnings.catch_warnings():
        warnings.simplefilter("error", UserWarning)
        yield

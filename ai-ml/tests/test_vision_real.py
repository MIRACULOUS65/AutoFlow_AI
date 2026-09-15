"""Live/real VisionProvider tests (fail-closed) + adaptive observation policy.

Hermetic tests use a fake transport (no network) to prove the provider parses
real structured JSON, fails closed on every error, and never lets a
low-confidence candidate auto-act. A real multimodal test is SKIP-gated behind
AUTOFLOW_REAL_VISION.
"""

from __future__ import annotations

import json
import os

import pytest

from autoflow_ai.computer_use.vision import (
    AdaptiveObserver,
    RealVisionProvider,
    VisionBudget,
    build_real_vision_provider,
)


def _envelope(content: str, status: int = 200):
    """Build a fake OpenAI-compatible transport returning `content`."""

    body = json.dumps({"choices": [{"message": {"content": content}}]})

    def _transport(url, headers, data, timeout):
        return status, body

    return _transport


def provider(transport):
    return RealVisionProvider(base_url="https://x/v1", api_key="k",
                              model_name="vision-model", transport=transport)


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 32  # fake bytes; provider only base64s them


def test_vis_01_parses_valid_candidates():
    content = json.dumps({
        "candidates": [{"role": "button", "name": "Save", "confidence": 0.9, "region": [1, 2, 3, 4]}],
        "dialog_detected": False, "description": "a toolbar",
    })
    res = provider(_envelope(content)).locate(PNG, "Save")
    assert len(res.candidates) == 1
    c = res.candidates[0]
    assert c.name == "Save" and c.confidence == 0.9 and c.region == (1, 2, 3, 4)
    assert res.uncertain is False


def test_vis_02_low_confidence_not_usable():
    content = json.dumps({"candidates": [{"role": "button", "name": "Save", "confidence": 0.2}]})
    res = provider(_envelope(content)).locate(PNG, "Save")
    # candidate surfaced, but the min-confidence gate rejects it for acting
    assert res.best(min_confidence=0.6) is None


def test_vis_03_http_error_fails_closed():
    res = provider(_envelope("{}", status=500)).locate(PNG, "Save")
    assert res.candidates == [] and res.uncertain is True


def test_vis_04_malformed_json_fails_closed():
    res = provider(_envelope("not json at all")).locate(PNG, "Save")
    assert res.candidates == [] and res.uncertain is True


def test_vis_05_missing_candidates_field_fails_closed():
    res = provider(_envelope(json.dumps({"description": "no candidates here"}))).locate(PNG, "x")
    assert res.candidates == [] and res.uncertain is True


def test_vis_06_transport_exception_fails_closed():
    def _boom(url, headers, data, timeout):
        raise RuntimeError("network down")

    res = provider(_boom).locate(PNG, "Save")
    assert res.candidates == [] and res.uncertain is True


def test_vis_07_confidence_clamped():
    content = json.dumps({"candidates": [{"role": "b", "name": "X", "confidence": 5.0}]})
    res = provider(_envelope(content)).locate(PNG, "X")
    assert res.candidates[0].confidence == 1.0


def test_vis_08_dialog_detected_parsed():
    content = json.dumps({"candidates": [{"role": "dialog", "name": "Save changes?", "confidence": 0.8}],
                          "dialog_detected": True})
    res = provider(_envelope(content)).locate(PNG, "dialog")
    assert res.dialog_detected is True


def test_vis_09_builder_none_without_config(monkeypatch):
    for k in ("PRIMARY_MODEL_BASE_URL", "VISION_MODEL_BASE_URL", "VISION_MODEL_ID", "PRIMARY_MODEL_ID"):
        monkeypatch.delenv(k, raising=False)
    assert build_real_vision_provider() is None


def test_vis_10_builder_builds_with_config(monkeypatch):
    monkeypatch.setenv("PRIMARY_MODEL_BASE_URL", "https://x/v1")
    monkeypatch.setenv("PRIMARY_MODEL_ID", "vision-model")
    monkeypatch.setenv("PRIMARY_MODEL_API_KEY", "k")
    p = build_real_vision_provider()
    assert p is not None and p.available()


# -- adaptive observation policy (vision should not run constantly) ---------

def test_vis_11_skip_vision_when_unchanged():
    ok, why = AdaptiveObserver().needs_vision(
        uia_match_count=1, target_found=True, state_changed_as_expected=True, screen_changed=False)
    assert ok is False and "unchanged" in why


def test_vis_12_vision_when_target_missing():
    ok, _ = AdaptiveObserver().needs_vision(
        uia_match_count=0, target_found=False, state_changed_as_expected=True, screen_changed=True)
    assert ok is True


def test_vis_13_vision_when_ambiguous():
    ok, _ = AdaptiveObserver().needs_vision(
        uia_match_count=3, target_found=True, state_changed_as_expected=True, screen_changed=True)
    assert ok is True


def test_vis_14_vision_when_unexpected_state():
    ok, _ = AdaptiveObserver().needs_vision(
        uia_match_count=1, target_found=True, state_changed_as_expected=False, screen_changed=True)
    assert ok is True


def test_vis_15_skip_vision_when_uia_confident():
    ok, _ = AdaptiveObserver().needs_vision(
        uia_match_count=1, target_found=True, state_changed_as_expected=True, screen_changed=True)
    assert ok is False


# -- real multimodal (opt-in) ----------------------------------------------

@pytest.mark.skipif(os.environ.get("AUTOFLOW_REAL_VISION") != "1",
                    reason="real vision disabled (set AUTOFLOW_REAL_VISION=1 with a vision model configured)")
def test_vis_16_real_vision_locate():
    p = build_real_vision_provider()
    if p is None or not p.available():
        pytest.skip("no vision model configured")
    # tiny 1x1 white PNG
    import base64
    png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    res = p.locate(png, "any button")
    # honest: real model may find nothing on a blank image; must not crash and
    # must be evidence-only (candidates carry confidence, never an action).
    assert isinstance(res.candidates, list)

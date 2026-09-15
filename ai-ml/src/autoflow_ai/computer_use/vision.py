"""Vision subsystem: provider-neutral visual grounding (evidence, not authority).

The vision model inspects a screenshot and returns candidate targets with
confidence — it never decides to act. Its candidates must be corroborated by
UIA/DOM/semantic verification before any action. A deterministic FakeVision
provider is used for hermetic tests. A rate limiter enforces per-task/per-minute
vision budgets and suppresses duplicate screenshots (via perceptual hash).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class VisionCandidate:
    role: str
    name: str
    confidence: float
    region: tuple[int, int, int, int] | None = None  # x,y,w,h (fallback only)


@dataclass
class VisionResult:
    candidates: list[VisionCandidate]
    dialog_detected: bool = False
    description: str = ""
    uncertain: bool = False

    def best(self, *, min_confidence: float = 0.6) -> VisionCandidate | None:
        usable = [c for c in self.candidates if c.confidence >= min_confidence]
        if not usable:
            return None
        return max(usable, key=lambda c: c.confidence)


@runtime_checkable
class VisionProvider(Protocol):
    name: str

    def available(self) -> bool: ...
    def locate(self, screenshot: bytes, query: str) -> VisionResult: ...
    def describe(self, screenshot: bytes) -> VisionResult: ...


class FakeVisionProvider:
    """Deterministic vision for tests: returns scripted candidates."""

    name = "fake-vision"

    def __init__(self, candidates: list[VisionCandidate] | None = None, *, dialog: bool = False) -> None:
        self._candidates = candidates or [VisionCandidate(role="button", name="Save", confidence=0.92)]
        self._dialog = dialog

    def available(self) -> bool:
        return True

    def locate(self, screenshot: bytes, query: str) -> VisionResult:
        matches = [c for c in self._candidates if query.lower() in c.name.lower()] or self._candidates
        return VisionResult(candidates=matches, dialog_detected=self._dialog)

    def describe(self, screenshot: bytes) -> VisionResult:
        return VisionResult(candidates=self._candidates, dialog_detected=self._dialog,
                            description="fake description")


@dataclass
class VisionBudget:
    max_per_task: int = 15
    max_per_minute: int = 30

    _task_used: int = 0
    _timestamps: list[float] = field(default_factory=list)
    _recent_hashes: list[str] = field(default_factory=list)

    def can_call(self) -> tuple[bool, str]:
        if self._task_used >= self.max_per_task:
            return False, "per-task vision budget exhausted"
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self.max_per_minute:
            return False, "per-minute vision budget exhausted"
        return True, ""

    def is_duplicate(self, screenshot_hash: str) -> bool:
        return screenshot_hash in self._recent_hashes[-5:]

    def record(self, screenshot_hash: str | None = None) -> None:
        self._task_used += 1
        self._timestamps.append(time.time())
        if screenshot_hash:
            self._recent_hashes.append(screenshot_hash)


class RealVisionProvider:
    """Live multimodal vision provider over an OpenAI-compatible endpoint.

    It posts the screenshot (as a base64 data URI) plus a structured-output
    instruction to a vision-capable model and parses candidates + confidence
    from the STRICT JSON response. It is evidence-only: it returns candidates
    with confidence and never decides to act. It FAILS CLOSED — on any timeout,
    transport error, non-JSON body, or malformed structure it returns an empty,
    ``uncertain`` result so the caller falls back to UIA/CV rather than acting on
    a guess. Low-confidence candidates are surfaced but the caller's
    ``VisionResult.best(min_confidence=...)`` gate keeps them from auto-acting.

    Config is read from the same env the model gateway uses (PRIMARY_MODEL_*),
    so no second gateway/config is introduced.
    """

    name = "real-vision"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model_name: str,
        timeout_seconds: float = 30.0,
        transport=None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model_name
        self._timeout = timeout_seconds
        # default to the gateway's urllib transport; injectable for tests
        if transport is None:
            from ..model_gateway.http_provider import _urllib_transport
            transport = _urllib_transport
        self._transport = transport

    def available(self) -> bool:
        return bool(self._base_url and self._model)

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def _call(self, screenshot: bytes, instruction: str) -> "VisionResult":
        import base64
        import json

        data_uri = "data:image/png;base64," + base64.b64encode(screenshot).decode("ascii")
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": instruction},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
            "max_tokens": 512,
            "temperature": 0.0,
        }
        url = f"{self._base_url}/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        try:
            status, text = self._transport(url, self._headers(), body, self._timeout)
        except Exception:  # noqa: BLE001 - any transport failure fails closed
            return VisionResult(candidates=[], uncertain=True, description="vision transport error")
        if status < 200 or status >= 300:
            return VisionResult(candidates=[], uncertain=True, description=f"vision http {status}")
        return self._parse(text)

    @staticmethod
    def _parse(text: str) -> "VisionResult":
        import json
        import re

        try:
            body = json.loads(text)
            content = body["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001
            return VisionResult(candidates=[], uncertain=True, description="malformed vision envelope")
        if isinstance(content, list):  # some providers return content parts
            content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
        # extract the JSON object the model was asked to return
        match = re.search(r"\{.*\}", content or "", re.DOTALL)
        if not match:
            return VisionResult(candidates=[], uncertain=True, description="no json in vision output")
        try:
            data = json.loads(match.group(0))
        except Exception:  # noqa: BLE001
            return VisionResult(candidates=[], uncertain=True, description="unparseable vision json")
        raw = data.get("candidates")
        if not isinstance(raw, list):
            return VisionResult(candidates=[], uncertain=True, description="no candidates field")
        candidates: list[VisionCandidate] = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            try:
                conf = float(c.get("confidence", 0.0))
            except (TypeError, ValueError):
                conf = 0.0
            conf = max(0.0, min(1.0, conf))
            region = c.get("region")
            reg = tuple(region) if isinstance(region, (list, tuple)) and len(region) == 4 else None
            candidates.append(
                VisionCandidate(role=str(c.get("role", "")), name=str(c.get("name", "")),
                                confidence=conf, region=reg)
            )
        return VisionResult(
            candidates=candidates,
            dialog_detected=bool(data.get("dialog_detected", False)),
            description=str(data.get("description", ""))[:512],
            uncertain=not candidates,
        )

    def locate(self, screenshot: bytes, query: str) -> "VisionResult":
        instruction = (
            "You are a UI vision grounder. Look at the screenshot and locate the "
            f"element matching: {query!r}. Respond ONLY with a JSON object: "
            '{"candidates":[{"role":"<role>","name":"<visible text>",'
            '"confidence":<0..1>,"region":[x,y,w,h]}],"dialog_detected":<bool>,'
            '"description":"<short>"}. If unsure, use low confidence. '
            "Do not invent elements that are not visible."
        )
        return self._call(screenshot, instruction)

    def describe(self, screenshot: bytes) -> "VisionResult":
        instruction = (
            "Describe the visible UI. Respond ONLY with JSON: "
            '{"candidates":[{"role":"<role>","name":"<text>","confidence":<0..1>}],'
            '"dialog_detected":<bool>,"description":"<short>"}.'
        )
        return self._call(screenshot, instruction)


def build_real_vision_provider(*, transport=None):
    """Build a RealVisionProvider from the gateway's PRIMARY_MODEL_* env, or None.

    Returns None when no vision endpoint is configured — the caller then uses
    the deterministic/UIA path. Never raises.
    """

    import os

    base_url = os.environ.get("PRIMARY_MODEL_BASE_URL") or os.environ.get("VISION_MODEL_BASE_URL")
    api_key = os.environ.get("PRIMARY_MODEL_API_KEY") or os.environ.get("VISION_MODEL_API_KEY")
    model_name = os.environ.get("VISION_MODEL_ID") or os.environ.get("PRIMARY_MODEL_ID")
    if not base_url or not model_name:
        return None
    return RealVisionProvider(
        base_url=base_url, api_key=api_key, model_name=model_name, transport=transport
    )


class RateLimitedVision:
    """Wraps a VisionProvider with budget + duplicate-screenshot suppression."""

    def __init__(self, provider: VisionProvider, budget: VisionBudget | None = None) -> None:
        self._provider = provider
        self._budget = budget or VisionBudget()

    @property
    def budget(self) -> VisionBudget:
        return self._budget

    def locate(self, screenshot: bytes, query: str, *, screenshot_hash: str | None = None) -> VisionResult | None:
        ok, _reason = self._budget.can_call()
        if not ok:
            return None
        if screenshot_hash and self._budget.is_duplicate(screenshot_hash):
            # same screen as a recent call -> reuse would be wasteful; signal none
            return None
        result = self._provider.locate(screenshot, query)
        self._budget.record(screenshot_hash)
        return result


class ObservationSignal(str):
    pass


@dataclass
class AdaptiveObserver:
    """Decides WHEN vision is needed (vision should not run constantly).

    Policy (Part M): prefer UIA/DOM; call vision only when the semantic layer is
    ambiguous, a target is missing, or an action produced an unexpected state.
    Skip vision when the screen is unchanged. This keeps vision cost bounded and
    ensures deterministic signals win when they are confident.
    """

    ambiguity_threshold: int = 2  # >1 UIA match = ambiguous

    def needs_vision(
        self,
        *,
        uia_match_count: int,
        target_found: bool,
        state_changed_as_expected: bool,
        screen_changed: bool,
    ) -> tuple[bool, str]:
        # If UIA confidently resolved a single target and the state changed as
        # expected, vision is unnecessary.
        if not screen_changed:
            return False, "screen unchanged; skip vision"
        if not target_found:
            return True, "target not found via UIA; escalate to vision"
        if uia_match_count >= self.ambiguity_threshold:
            return True, "ambiguous UIA match; escalate to vision"
        if not state_changed_as_expected:
            return True, "unexpected post-action state; escalate to vision"
        return False, "UIA resolved target confidently; skip vision"

"""Structured-output parsing for model responses.

Real models often wrap JSON in prose or ```json fences, or emit slightly
malformed JSON. This parser extracts the JSON object safely and (optionally)
validates it against a Pydantic model. It never executes model content; it only
parses data. Failures raise :class:`StructuredOutputError` so the caller can
trigger bounded repair/retry rather than trusting garbage.
"""

from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)

T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(Exception):
    """Model output could not be parsed/validated into the expected shape."""


def extract_json(text: str) -> dict:
    """Extract a single JSON object from arbitrary model text.

    Strategy (in order):
    1. direct json.loads;
    2. content inside a ```json ... ``` fence;
    3. the substring between the first '{' and the last '}'.
    """

    if text is None:
        raise StructuredOutputError("no text to parse")

    stripped = text.strip()

    # 1. direct
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 2. fenced
    m = _FENCE_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(1))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # 3. brace span
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as exc:
            raise StructuredOutputError(f"invalid JSON object: {exc}") from exc

    raise StructuredOutputError("no JSON object found in model output")


def parse_into(text: str, model_cls: Type[T]) -> T:
    """Extract JSON from ``text`` and validate it into ``model_cls``."""

    data = extract_json(text)
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise StructuredOutputError(
            f"output did not match {model_cls.__name__}: {exc}"
        ) from exc


class StructuredOutputParser:
    """Convenience wrapper bound to a target model class."""

    def __init__(self, model_cls: Type[T]) -> None:
        self._model_cls = model_cls

    def parse(self, text: str) -> T:
        return parse_into(text, self._model_cls)

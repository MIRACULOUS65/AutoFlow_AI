"""Deterministic computer-vision helpers (OpenCV, guarded).

Use deterministic CV for what it solves reliably — screenshot hashing, image
diff, visual-stability detection, template matching — BEFORE spending an
expensive multimodal call. Degrades gracefully (functions raise CVUnavailable)
when opencv/numpy are not installed; callers treat that as "CV unavailable".
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


class CVUnavailable(Exception):
    """OpenCV/numpy not installed."""


def _cv():
    try:
        import cv2
        import numpy as np
    except Exception as exc:  # noqa: BLE001
        raise CVUnavailable(str(exc)) from exc
    return cv2, np


def cv_available() -> bool:
    try:
        _cv()
        return True
    except CVUnavailable:
        return False


def image_hash(image_bytes: bytes) -> str:
    """Content hash of raw image bytes (cheap duplicate-screenshot suppression)."""

    return hashlib.sha256(image_bytes).hexdigest()


def perceptual_hash(image_bytes: bytes, *, size: int = 16) -> str:
    """Average-hash (aHash) of an image — robust to tiny pixel noise.

    Downscales to size x size grayscale, thresholds against the mean, and packs
    the bits into a hex string. Deterministic; requires OpenCV.
    """

    cv2, np = _cv()
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise CVUnavailable("could not decode image")
    small = cv2.resize(img, (size, size), interpolation=cv2.INTER_AREA)
    mean = small.mean()
    bits = (small >= mean).flatten()
    value = 0
    for b in bits:
        value = (value << 1) | int(b)
    return format(value, f"0{(size * size) // 4}x")


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Bit-difference between two equal-length hex perceptual hashes."""

    if len(hash_a) != len(hash_b):
        return max(len(hash_a), len(hash_b)) * 4
    x = int(hash_a, 16) ^ int(hash_b, 16)
    return bin(x).count("1")


@dataclass
class DiffResult:
    changed_ratio: float
    changed: bool


def image_diff(a_bytes: bytes, b_bytes: bytes, *, threshold: float = 0.01) -> DiffResult:
    """Fraction of pixels that changed between two same-size screenshots."""

    cv2, np = _cv()
    a = cv2.imdecode(np.frombuffer(a_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    b = cv2.imdecode(np.frombuffer(b_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if a is None or b is None:
        raise CVUnavailable("could not decode image(s)")
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    diff = cv2.absdiff(a, b)
    changed = (diff > 25).mean()  # fraction of pixels differing meaningfully
    return DiffResult(changed_ratio=float(changed), changed=bool(changed > threshold))


def is_visually_stable(a_bytes: bytes, b_bytes: bytes, *, tolerance: float = 0.005) -> bool:
    """True when two screenshots are visually near-identical (UI settled)."""

    return not image_diff(a_bytes, b_bytes, threshold=tolerance).changed


def template_match(haystack_bytes: bytes, needle_bytes: bytes) -> tuple[float, tuple[int, int]]:
    """Return (best_score, (x, y)) for locating a template in a screenshot.

    Score in [0,1]; caller decides a confidence threshold. Deterministic.
    """

    cv2, np = _cv()
    hay = cv2.imdecode(np.frombuffer(haystack_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    needle = cv2.imdecode(np.frombuffer(needle_bytes, np.uint8), cv2.IMREAD_GRAYSCALE)
    if hay is None or needle is None:
        raise CVUnavailable("could not decode image(s)")
    res = cv2.matchTemplate(hay, needle, cv2.TM_CCOEFF_NORMED)
    _min_v, max_v, _min_l, max_l = cv2.minMaxLoc(res)
    return float(max_v), (int(max_l[0]), int(max_l[1]))

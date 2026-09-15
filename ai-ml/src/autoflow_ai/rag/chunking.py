"""Deterministic chunker with configurable size/overlap.

Interface allows future paragraph/section/semantic chunkers. This implementation
is deterministic: identical input + config => identical chunks (and chunk ids).
Each chunk preserves its source block's page/section metadata.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

from .loaders import Block


class Chunker(Protocol):
    def chunk(self, blocks: list[Block]) -> list[dict]: ...


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DeterministicChunker:
    """Character-window chunker with overlap, per source block."""

    def __init__(self, *, chunk_size: int = 800, chunk_overlap: int = 120) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("0 <= chunk_overlap < chunk_size required")
        self._size = chunk_size
        self._overlap = chunk_overlap

    def chunk(self, blocks: list[Block]) -> list[dict]:
        chunks: list[dict] = []
        seq = 0
        for text, page, section in blocks:
            for piece in self._split(text):
                chunks.append(
                    {
                        "text": piece,
                        "sequence": seq,
                        "page": page,
                        "section": section,
                        "content_hash": _hash(piece),
                        "token_estimate": max(1, len(piece) // 4),
                    }
                )
                seq += 1
        return chunks

    def _split(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []
        if len(text) <= self._size:
            return [text]
        step = self._size - self._overlap
        pieces = []
        start = 0
        while start < len(text):
            end = start + self._size
            pieces.append(text[start:end].strip())
            if end >= len(text):
                break
            start += step
        return [p for p in pieces if p]

"""Artifact byte store abstraction.

Metadata lives in PostgreSQL; bytes live behind this store. Local filesystem is
the dev implementation; an S3/object-store implementation can replace it without
touching domain services (PRD §60, §68).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from app.core.config import settings
from app.core.security import content_hash


class ArtifactStore(Protocol):
    async def put(self, name: str, data: bytes) -> tuple[str, str]:
        """Store bytes; return (storage_path, content_hash)."""

    async def get(self, storage_path: str) -> bytes: ...


class LocalArtifactStore:
    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    async def put(self, name: str, data: bytes) -> tuple[str, str]:
        digest = content_hash(data)
        safe = name.replace("/", "_").replace("\\", "_")
        path = self.base / f"{digest.split(':')[1][:12]}_{safe}"
        path.write_bytes(data)
        return str(path), digest

    async def get(self, storage_path: str) -> bytes:
        return Path(storage_path).read_bytes()


_store: ArtifactStore | None = None


def get_artifact_store() -> ArtifactStore:
    global _store
    if _store is None:
        _store = LocalArtifactStore(os.path.abspath(settings.artifact_storage_dir))
    return _store

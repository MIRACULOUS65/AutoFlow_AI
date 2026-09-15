"""Memory configuration (environment-driven)."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _b(name: str, default: str) -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class MemoryConfig:
    enabled: bool
    workflow_enabled: bool
    workflow_collection: str
    db_path: str
    top_k: int
    min_score: float
    auto_promotion: bool
    max_versions: int
    failure_decay: bool
    recency_weight: float
    success_weight: float
    compatibility_weight: float
    semantic_weight: float

    def redacted(self) -> dict:
        return {
            "enabled": self.enabled,
            "workflow_enabled": self.workflow_enabled,
            "workflow_collection": self.workflow_collection,
            "db_path": self.db_path,
            "top_k": self.top_k,
            "auto_promotion": self.auto_promotion,
            "max_versions": self.max_versions,
            "weights": {
                "semantic": self.semantic_weight,
                "compatibility": self.compatibility_weight,
                "success": self.success_weight,
                "recency": self.recency_weight,
            },
        }


def load_memory_config(
    *, db_path_override: str | None = None, collection_override: str | None = None
) -> MemoryConfig:
    return MemoryConfig(
        enabled=_b("MEMORY_ENABLED", "true"),
        workflow_enabled=_b("WORKFLOW_MEMORY_ENABLED", "true"),
        workflow_collection=collection_override
        or os.environ.get("WORKFLOW_MEMORY_COLLECTION", "autoflow_workflows"),
        db_path=db_path_override or os.environ.get("MEMORY_DB_PATH", "./data/memory.sqlite"),
        top_k=int(os.environ.get("WORKFLOW_RETRIEVAL_TOP_K", "5") or 5),
        min_score=float(os.environ.get("WORKFLOW_MEMORY_MIN_SCORE", "0.0") or 0.0),
        auto_promotion=_b("WORKFLOW_AUTO_PROMOTION", "false"),
        max_versions=int(os.environ.get("WORKFLOW_MAX_VERSIONS", "50") or 50),
        failure_decay=_b("MEMORY_FAILURE_DECAY", "true"),
        recency_weight=float(os.environ.get("MEMORY_RECENCY_WEIGHT", "0.15") or 0.15),
        success_weight=float(os.environ.get("MEMORY_SUCCESS_WEIGHT", "0.35") or 0.35),
        compatibility_weight=float(os.environ.get("MEMORY_COMPATIBILITY_WEIGHT", "0.30") or 0.30),
        semantic_weight=float(os.environ.get("MEMORY_SEMANTIC_WEIGHT", "0.20") or 0.20),
    )

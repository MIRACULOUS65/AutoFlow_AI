"""Memory layer (Phase 5).

Four distinct memory classes (never collapsed into one collection):

* SESSION   — short-lived, bounded task/execution state.
* KNOWLEDGE — enterprise documents (Phase 4 RAG; NOT re-implemented here).
* WORKFLOW  — verified, reusable semantic workflows (SQLite metadata +
              a dedicated ``autoflow_workflows`` Chroma collection).
* GRAPH     — relationships between apps/tools/actions/artifacts/workflows.

Core rule: a FAILED / UNVERIFIED execution must NEVER automatically become
reusable workflow memory. Promotion is verification-gated. "Learning" here means
learning a reusable *semantic workflow*, not training model weights.
"""

from __future__ import annotations

from .errors import MemoryError, PromotionRejected, CompatibilityError
from .models import (
    CompatibilityLevel,
    GraphEdge,
    GraphNode,
    SemanticWorkflow,
    SessionMemory,
    WorkflowCandidate,
    WorkflowMemory,
    WorkflowParameter,
    WorkflowPromotionDecision,
    WorkflowScore,
    WorkflowStatus,
    WorkflowStep,
    WorkflowVersion,
    contains_secret,
    workflow_content_hash,
)
from .config import MemoryConfig, load_memory_config
from .service import MemoryService, build_memory_service

__all__ = [
    "MemoryError",
    "PromotionRejected",
    "CompatibilityError",
    "CompatibilityLevel",
    "GraphEdge",
    "GraphNode",
    "SemanticWorkflow",
    "SessionMemory",
    "WorkflowCandidate",
    "WorkflowMemory",
    "WorkflowParameter",
    "WorkflowPromotionDecision",
    "WorkflowScore",
    "WorkflowStatus",
    "WorkflowStep",
    "WorkflowVersion",
    "contains_secret",
    "workflow_content_hash",
    "MemoryConfig",
    "load_memory_config",
    "MemoryService",
    "build_memory_service",
]

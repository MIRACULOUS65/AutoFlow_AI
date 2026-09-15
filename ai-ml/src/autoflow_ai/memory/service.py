"""MemoryService — the high-level memory facade.

Bundles session store, workflow store (SQLite), workflow vector index (Chroma),
graph memory, normalization, promotion policy, scoring and compatibility into
one API used by the orchestrator/CLI.

Key guarantees:
* failed/unverified candidates are never promoted;
* workflow memory is physically separate from knowledge RAG;
* authorization (tenant/workspace/scope) is enforced before retrieval results
  are returned — similarity is never permission;
* blocked workflows are never returned as reusable.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from ..rag.config import load_rag_config
from ..rag.embeddings import EmbeddingProvider, build_embedder
from .compatibility import bind_parameters
from .config import MemoryConfig, load_memory_config
from .errors import PromotionRejected
from .graph import GraphMemory
from .models import (
    CompatibilityLevel,
    SemanticWorkflow,
    WorkflowCandidate,
    WorkflowMemory,
    WorkflowPromotionDecision,
    WorkflowProvenance,
    WorkflowStatus,
    WorkflowVersion,
    workflow_content_hash,
)
from .normalization import WorkflowNormalizer
from .promotion import PromotionContext, WorkflowPromotionPolicy
from .scoring import CompatibilityChecker, WorkflowScorer
from .session import SessionStore
from .storage import WorkflowStore, WorkflowVectorIndex


def _slug(name: str) -> str:
    import re

    s = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return s or "workflow"


class SearchHit:
    def __init__(self, workflow: WorkflowMemory, score, compatibility: CompatibilityLevel, reasons):
        self.workflow = workflow
        self.score = score
        self.compatibility = compatibility
        self.reasons = reasons

    def to_dict(self) -> dict:
        return {
            "workflow_id": self.workflow.workflow_id,
            "canonical_name": self.workflow.canonical_name,
            "version": self.workflow.version,
            "status": self.workflow.status.value,
            "score": self.score.model_dump(mode="json"),
            "compatibility": self.compatibility.value,
            "reasons": self.reasons,
            "verified_success_rate": round(self.workflow.verified_success_rate, 3),
            "usage_count": self.workflow.usage_count,
        }


class MemoryService:
    def __init__(
        self,
        *,
        config: MemoryConfig,
        store: WorkflowStore,
        index: WorkflowVectorIndex,
        embedder: EmbeddingProvider,
    ) -> None:
        self._c = config
        self._store = store
        self._index = index
        self._embedder = embedder
        self.sessions = SessionStore()
        self.graph = GraphMemory()
        self._normalizer = WorkflowNormalizer()
        self._policy = WorkflowPromotionPolicy()
        self._scorer = WorkflowScorer(config)
        self._compat = CompatibilityChecker()
        self.events: list[dict] = []

    def _emit(self, event: str, **data) -> None:
        self.events.append({"event": event, **data})

    # -- candidate generation ------------------------------------------------

    def candidate_from_trace(
        self,
        trace: dict,
        *,
        tenant_id: str,
        workspace_id: str,
        canonical_name: str,
        source_execution_ids: tuple[str, ...],
        source_task_id: str | None,
        verified: bool,
        verification_evidence: tuple[str, ...] = (),
        permission_scope: tuple[str, ...] = (),
    ) -> WorkflowCandidate:
        workflow = self._normalizer.normalize(trace)
        candidate = WorkflowCandidate(
            candidate_id=f"cand_{workflow_content_hash(workflow)[:16]}",
            canonical_name=canonical_name,
            workflow=workflow,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            permission_scope=permission_scope,
            source_execution_ids=source_execution_ids,
            source_task_id=source_task_id,
            verified=verified,
            verification_evidence=verification_evidence,
        )
        self._emit("workflow.candidate.created", candidate_id=candidate.candidate_id, verified=verified)
        return candidate

    # -- promotion -----------------------------------------------------------

    def promote(
        self,
        candidate: WorkflowCandidate,
        *,
        registered_tools: set[str],
        human_confirmed: bool = False,
        require_human_confirmation: bool = False,
    ) -> WorkflowPromotionDecision:
        self._emit("workflow.promotion.requested", candidate_id=candidate.candidate_id)
        reasons = self._policy.evaluate(
            candidate,
            PromotionContext(
                registered_tools=registered_tools,
                human_confirmed=human_confirmed,
                require_human_confirmation=require_human_confirmation,
            ),
        )
        if reasons:
            return WorkflowPromotionDecision(promoted=False, rejected_reasons=tuple(reasons))

        # duplicate / version handling
        existing = self._store.by_hash(candidate.tenant_id, candidate.workspace_id, candidate.content_hash)
        if existing:
            # identical content already stored -> just usage bookkeeping
            self._emit("workflow.reused", workflow_id=existing.workflow_id)
            return WorkflowPromotionDecision(
                promoted=True, workflow_id=existing.workflow_id, version=existing.version,
                reason="identical workflow already exists",
            )

        # find prior workflow by canonical name in same scope -> new version
        prior = [
            w
            for w in self._store.list_all(tenant_id=candidate.tenant_id, workspace_id=candidate.workspace_id)
            if w.canonical_name == candidate.canonical_name
        ]
        if prior:
            parent = max(prior, key=lambda w: w.version)
            version = parent.version + 1
            workflow_id = parent.workflow_id
            parent_version = parent.version
        else:
            version = 1
            workflow_id = f"wf_{_slug(candidate.canonical_name)}_{candidate.content_hash[:8]}"
            parent_version = None

        wf = WorkflowMemory(
            workflow_id=workflow_id,
            canonical_name=candidate.canonical_name,
            workflow=candidate.workflow,
            version=version,
            status=WorkflowStatus.ACTIVE,
            tenant_id=candidate.tenant_id,
            workspace_id=candidate.workspace_id,
            permission_scope=candidate.permission_scope,
            verified_count=1,
            success_count=1,
            usage_count=1,
            content_hash=candidate.content_hash,
            parent_version=parent_version,
            provenance=WorkflowProvenance(
                source_execution_ids=candidate.source_execution_ids,
                source_task_id=candidate.source_task_id,
                source_workspace=candidate.workspace_id,
                verification_evidence=candidate.verification_evidence,
            ),
        )
        self._store.upsert(wf)
        self._store.add_version(
            WorkflowVersion(
                workflow_id=workflow_id,
                version=version,
                content_hash=candidate.content_hash,
                source_execution_ids=candidate.source_execution_ids,
                change_summary="promoted from verified execution",
                parent_version=parent_version,
            )
        )
        self._index.index(wf)
        self.graph.record_workflow(
            workflow_id, tools=list(wf.workflow.tools),
            verifier=(wf.workflow.verification_rules[0] if wf.workflow.verification_rules else None),
        )
        self._emit("workflow.promoted", workflow_id=workflow_id, version=version)
        self._emit("workflow.versioned", workflow_id=workflow_id, version=version)
        return WorkflowPromotionDecision(promoted=True, workflow_id=workflow_id, version=version)

    # -- retrieval -----------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        tenant_id: str,
        workspace_id: str,
        permissions: frozenset[str] = frozenset(),
        available_tools: set[str] | None = None,
        available_capabilities: set[str] | None = None,
        provided_parameters: dict | None = None,
        top_k: int | None = None,
    ) -> list[SearchHit]:
        self._emit("memory.search.started", query_len=len(query))
        top_k = top_k or self._c.top_k
        where = {"$and": [{"tenant_id": tenant_id}, {"workspace_id": workspace_id}]}
        raw = self._index.query(query, where=where, top_k=top_k * 3)
        ids = (raw.get("ids") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]

        from ..rag.ranking import normalize_cosine_distance

        hits: list[SearchHit] = []
        for wid, dist in zip(ids, dists):
            wf = self._store.get(wid)
            if wf is None:
                continue
            # authorization: tenant/workspace already filtered; check scope + status
            if wf.tenant_id != tenant_id or wf.workspace_id != workspace_id:
                continue
            if wf.status in (WorkflowStatus.BLOCKED, WorkflowStatus.ARCHIVED):
                continue
            if wf.permission_scope and not (set(wf.permission_scope) & set(permissions)):
                continue
            semantic = normalize_cosine_distance(float(dist))
            # Distinguish "not provided" (None -> assume workflow's own reqs are
            # available) from an explicit empty set (nothing available).
            eff_tools = set(wf.workflow.tools) if available_tools is None else available_tools
            eff_caps = (
                set(wf.workflow.capabilities)
                if available_capabilities is None
                else available_capabilities
            )
            compat, reasons = self._compat.check(
                wf,
                available_tools=eff_tools,
                available_capabilities=eff_caps,
                provided_parameters=provided_parameters,
            )
            compat_score = {
                CompatibilityLevel.COMPATIBLE: 1.0,
                CompatibilityLevel.PARTIALLY_COMPATIBLE: 0.5,
                CompatibilityLevel.INCOMPATIBLE: 0.0,
            }[compat]
            score = self._scorer.score(wf, semantic=semantic, compatibility=compat_score)
            if score.total < self._c.min_score:
                continue
            # deprecated workflows are deprioritized (kept but penalized)
            if wf.status == WorkflowStatus.DEPRECATED:
                score.total *= 0.5
            hits.append(SearchHit(wf, score, compat, reasons))

        hits.sort(key=lambda h: (-h.score.total, h.workflow.workflow_id))
        self._emit("memory.search.completed", results=len(hits))
        return hits[:top_k]

    # -- reuse ---------------------------------------------------------------

    def bind_parameters(self, wf: WorkflowMemory, provided: dict) -> SemanticWorkflow:
        return bind_parameters(wf.workflow, provided)

    def record_usage(self, workflow_id: str, *, success: bool, verified: bool) -> None:
        self._store.increment_usage(workflow_id, success=success, verified=verified)
        self._emit("workflow.reused", workflow_id=workflow_id, success=success)

    def record_failure(self, workflow_id: str, reason: str) -> None:
        wf = self._store.get(workflow_id)
        version = wf.version if wf else 1
        self._store.record_failure(workflow_id, version, reason)
        self._emit("workflow.failure_recorded", workflow_id=workflow_id, reason=reason)

    # -- management ----------------------------------------------------------

    def get(self, workflow_id: str) -> WorkflowMemory | None:
        return self._store.get(workflow_id)

    def versions(self, workflow_id: str):
        return self._store.versions(workflow_id)

    def list_workflows(self, **kwargs):
        return self._store.list_all(**kwargs)

    def deprecate(self, workflow_id: str) -> None:
        self._store.set_status(workflow_id, WorkflowStatus.DEPRECATED)
        self._emit("workflow.deprecated", workflow_id=workflow_id)

    def block(self, workflow_id: str) -> None:
        self._store.set_status(workflow_id, WorkflowStatus.BLOCKED)
        self._index.delete(workflow_id)  # blocked must never be retrievable/executable
        self._emit("workflow.blocked", workflow_id=workflow_id)

    def restore(self, workflow_id: str) -> None:
        wf = self._store.get(workflow_id)
        if wf:
            self._store.set_status(workflow_id, WorkflowStatus.ACTIVE)
            self._index.index(wf)
            self._emit("workflow.invalidated", workflow_id=workflow_id, restored=True)

    def status(self) -> dict:
        return {
            "config": self._c.redacted(),
            "sessions": self.sessions.count(),
            "workflows": self._store.count(),
            "graph": self.graph.summary(),
            "index_health": self._index.health(),
            "embedder": self._embedder.signature(),
        }


def build_memory_service(
    *,
    config: MemoryConfig | None = None,
    db_path_override: str | None = None,
    collection_override: str | None = None,
    chroma_path_override: str | None = None,
    embedder: EmbeddingProvider | None = None,
) -> MemoryService:
    cfg = config or load_memory_config(
        db_path_override=db_path_override, collection_override=collection_override
    )
    rag_cfg = load_rag_config(chroma_path_override=chroma_path_override)
    emb = embedder or build_embedder(rag_cfg)
    store = WorkflowStore(cfg.db_path)
    index = WorkflowVectorIndex(
        chroma_path=rag_cfg.chroma_path, collection=cfg.workflow_collection, embedder=emb
    )
    return MemoryService(config=cfg, store=store, index=index, embedder=emb)

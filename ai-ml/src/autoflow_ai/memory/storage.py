"""Persistence for workflow memory: SQLite metadata + Chroma semantic index.

SQLite holds the authoritative workflow records and immutable version history.
A dedicated ``autoflow_workflows`` Chroma collection holds semantic vectors for
retrieval — kept physically separate from enterprise knowledge (autoflow_knowledge).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..rag.chroma_store import ChromaStore
from ..rag.embeddings import EmbeddingProvider
from .errors import MemoryError
from .models import (
    SemanticWorkflow,
    WorkflowMemory,
    WorkflowProvenance,
    WorkflowStatus,
    WorkflowVersion,
)


class WorkflowStore:
    """SQLite-backed workflow metadata + version store."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                permission_scope TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                usage_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                verified_count INTEGER NOT NULL DEFAULT 0,
                parent_version INTEGER,
                body TEXT NOT NULL,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS workflow_versions (
                workflow_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                source_execution_ids TEXT NOT NULL,
                change_summary TEXT NOT NULL,
                parent_version INTEGER,
                created_at TEXT NOT NULL,
                PRIMARY KEY (workflow_id, version)
            );
            CREATE TABLE IF NOT EXISTS failures (
                workflow_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                reason TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    # -- write ---------------------------------------------------------------

    def upsert(self, wf: WorkflowMemory) -> None:
        self._conn.execute(
            """
            INSERT INTO workflows (workflow_id, canonical_name, version, status,
                tenant_id, workspace_id, permission_scope, content_hash,
                usage_count, success_count, failure_count, verified_count,
                parent_version, body, provenance, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(workflow_id) DO UPDATE SET
                canonical_name=excluded.canonical_name,
                version=excluded.version,
                status=excluded.status,
                content_hash=excluded.content_hash,
                usage_count=excluded.usage_count,
                success_count=excluded.success_count,
                failure_count=excluded.failure_count,
                verified_count=excluded.verified_count,
                parent_version=excluded.parent_version,
                body=excluded.body,
                provenance=excluded.provenance,
                updated_at=excluded.updated_at
            """,
            (
                wf.workflow_id,
                wf.canonical_name,
                wf.version,
                wf.status.value,
                wf.tenant_id,
                wf.workspace_id,
                ",".join(wf.permission_scope),
                wf.content_hash,
                wf.usage_count,
                wf.success_count,
                wf.failure_count,
                wf.verified_count,
                wf.parent_version,
                wf.workflow.model_dump_json(),
                wf.provenance.model_dump_json(),
                wf.created_at.isoformat(),
                (wf.updated_at or datetime.now(timezone.utc)).isoformat(),
            ),
        )
        self._conn.commit()

    def add_version(self, ver: WorkflowVersion) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO workflow_versions
                (workflow_id, version, content_hash, source_execution_ids,
                 change_summary, parent_version, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                ver.workflow_id,
                ver.version,
                ver.content_hash,
                ",".join(ver.source_execution_ids),
                ver.change_summary,
                ver.parent_version,
                ver.created_at.isoformat(),
            ),
        )
        self._conn.commit()

    def record_failure(self, workflow_id: str, version: int, reason: str) -> None:
        self._conn.execute(
            "UPDATE workflows SET failure_count = failure_count + 1 WHERE workflow_id=?",
            (workflow_id,),
        )
        self._conn.execute(
            "INSERT INTO failures (workflow_id, version, reason, created_at) VALUES (?,?,?,?)",
            (workflow_id, version, reason, datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def set_status(self, workflow_id: str, status: WorkflowStatus) -> None:
        self._conn.execute(
            "UPDATE workflows SET status=?, updated_at=? WHERE workflow_id=?",
            (status.value, datetime.now(timezone.utc).isoformat(), workflow_id),
        )
        self._conn.commit()

    def increment_usage(self, workflow_id: str, *, success: bool, verified: bool) -> None:
        self._conn.execute(
            """UPDATE workflows SET usage_count = usage_count + 1,
                success_count = success_count + ?,
                verified_count = verified_count + ?,
                updated_at=? WHERE workflow_id=?""",
            (1 if success else 0, 1 if verified else 0, datetime.now(timezone.utc).isoformat(), workflow_id),
        )
        self._conn.commit()

    # -- read ----------------------------------------------------------------

    def get(self, workflow_id: str) -> WorkflowMemory | None:
        row = self._conn.execute(
            "SELECT * FROM workflows WHERE workflow_id=?", (workflow_id,)
        ).fetchone()
        return self._row_to_wf(row) if row else None

    def by_hash(self, tenant_id: str, workspace_id: str, content_hash: str) -> WorkflowMemory | None:
        row = self._conn.execute(
            "SELECT * FROM workflows WHERE tenant_id=? AND workspace_id=? AND content_hash=?",
            (tenant_id, workspace_id, content_hash),
        ).fetchone()
        return self._row_to_wf(row) if row else None

    def list_all(self, *, tenant_id: str | None = None, workspace_id: str | None = None) -> list[WorkflowMemory]:
        q = "SELECT * FROM workflows"
        params: list = []
        conds = []
        if tenant_id:
            conds.append("tenant_id=?")
            params.append(tenant_id)
        if workspace_id:
            conds.append("workspace_id=?")
            params.append(workspace_id)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_wf(r) for r in rows]

    def versions(self, workflow_id: str) -> list[WorkflowVersion]:
        rows = self._conn.execute(
            "SELECT * FROM workflow_versions WHERE workflow_id=? ORDER BY version",
            (workflow_id,),
        ).fetchall()
        out = []
        for r in rows:
            out.append(
                WorkflowVersion(
                    workflow_id=r["workflow_id"],
                    version=r["version"],
                    content_hash=r["content_hash"],
                    source_execution_ids=tuple(x for x in r["source_execution_ids"].split(",") if x),
                    change_summary=r["change_summary"],
                    parent_version=r["parent_version"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
            )
        return out

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) AS c FROM workflows").fetchone()["c"]

    def _row_to_wf(self, row: sqlite3.Row) -> WorkflowMemory:
        return WorkflowMemory(
            workflow_id=row["workflow_id"],
            canonical_name=row["canonical_name"],
            workflow=SemanticWorkflow.model_validate_json(row["body"]),
            version=row["version"],
            status=WorkflowStatus(row["status"]),
            tenant_id=row["tenant_id"],
            workspace_id=row["workspace_id"],
            permission_scope=tuple(x for x in row["permission_scope"].split(",") if x),
            usage_count=row["usage_count"],
            success_count=row["success_count"],
            failure_count=row["failure_count"],
            verified_count=row["verified_count"],
            content_hash=row["content_hash"],
            provenance=WorkflowProvenance.model_validate_json(row["provenance"]),
            parent_version=row["parent_version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    def close(self) -> None:
        self._conn.close()


class WorkflowVectorIndex:
    """Semantic index for workflows in a dedicated Chroma collection."""

    def __init__(self, *, chroma_path: str, collection: str, embedder: EmbeddingProvider) -> None:
        if collection == "autoflow_knowledge":
            raise MemoryError("workflow memory must not share the knowledge collection")
        self._embedder = embedder
        self._store = ChromaStore(
            path=chroma_path, collection=collection, embedder_signature=embedder.signature()
        )

    def index(self, wf: WorkflowMemory) -> None:
        vec = self._embedder.embed_text(wf.searchable_text())
        from ..rag.models import Chunk

        # Reuse Chunk only as a transport for upsert metadata compatibility.
        meta = {
            "tenant_id": wf.tenant_id,
            "workspace_id": wf.workspace_id,
            "workflow_id": wf.workflow_id,
            "version": wf.version,
            "status": wf.status.value,
            "content_hash": wf.content_hash,
            "capability_tags": wf.capability_tags(),
            "tool_tags": wf.tool_tags(),
            "permission_scope": ",".join(wf.permission_scope),
        }
        # direct collection upsert (bypass Chunk model; store exposes _collection via query path)
        self._store._connect()  # noqa: SLF001 - internal connect
        self._store._collection.upsert(  # noqa: SLF001
            ids=[wf.workflow_id],
            embeddings=[vec],
            documents=[wf.searchable_text()],
            metadatas=[meta],
        )

    def query(self, text: str, *, where: dict, top_k: int):
        vec = self._embedder.embed_text(text)
        return self._store.query(vec, top_k=top_k, where=where)

    def delete(self, workflow_id: str) -> None:
        self._store._connect()  # noqa: SLF001
        self._store._collection.delete(ids=[workflow_id])  # noqa: SLF001

    def health(self) -> bool:
        return self._store.health()

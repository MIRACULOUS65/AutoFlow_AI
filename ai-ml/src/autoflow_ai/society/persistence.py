"""Mission persistence + checkpointing + resume (local JSON store).

A long-running mission can be paused and resumed without redoing verified work.
After each meaningful milestone the supervisor writes a checkpoint capturing:

* mission goal + execution id;
* per-task verification state (which subtasks are independently verified);
* the blackboard entries (evidence/observations/verifications) as data;
* recorded approvals (by binding hash) so an approval survives a resume;
* named checkpoints (research complete, document verified, ...).

On resume, tasks that were already VERIFIED are skipped (their prior evidence is
restored to the blackboard) so completed work — a saved Word document, a
verified Gmail draft — is never destroyed or redone. Persistence is a local
JSON file under ``.autoflow/missions/<execution_id>.json``; the backend would
own durable storage later, but the AI core must resume on its own.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .blackboard import Blackboard, BlackboardEntry, TrustClass


def _default_root() -> Path:
    root = os.environ.get("AUTOFLOW_MISSION_DIR")
    if root:
        return Path(root)
    return Path.cwd() / ".autoflow" / "missions"


@dataclass
class MissionCheckpoint:
    name: str
    detail: str = ""


@dataclass
class MissionState:
    execution_id: str
    goal: str
    verified_tasks: list[str] = field(default_factory=list)
    task_outputs: dict = field(default_factory=dict)      # task_id -> output dict
    approvals: list[str] = field(default_factory=list)    # binding hashes
    checkpoints: list[MissionCheckpoint] = field(default_factory=list)
    board_entries: list[dict] = field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "goal": self.goal,
            "verified_tasks": list(self.verified_tasks),
            "task_outputs": self.task_outputs,
            "approvals": list(self.approvals),
            "checkpoints": [{"name": c.name, "detail": c.detail} for c in self.checkpoints],
            "board_entries": self.board_entries,
        }

    @classmethod
    def from_json(cls, data: dict) -> "MissionState":
        return cls(
            execution_id=data["execution_id"],
            goal=data.get("goal", ""),
            verified_tasks=list(data.get("verified_tasks", [])),
            task_outputs=dict(data.get("task_outputs", {})),
            approvals=list(data.get("approvals", [])),
            checkpoints=[MissionCheckpoint(**c) for c in data.get("checkpoints", [])],
            board_entries=list(data.get("board_entries", [])),
        )

    def is_verified(self, task_id: str) -> bool:
        return task_id in self.verified_tasks

    def mark_verified(self, task_id: str, output: dict | None = None) -> None:
        if task_id not in self.verified_tasks:
            self.verified_tasks.append(task_id)
        if output is not None:
            self.task_outputs[task_id] = output

    def add_checkpoint(self, name: str, detail: str = "") -> None:
        self.checkpoints.append(MissionCheckpoint(name=name, detail=detail))

    def record_approval(self, binding_hash: str) -> None:
        if binding_hash not in self.approvals:
            self.approvals.append(binding_hash)

    def snapshot_board(self, board: Blackboard) -> None:
        """Persist the current blackboard entries (data/evidence) for resume."""

        self.board_entries = [e.canonical_dict() for e in board.all_entries()]

    def restore_board(self, board: Blackboard) -> None:
        """Re-post persisted evidence onto a fresh blackboard on resume."""

        for raw in self.board_entries:
            try:
                board.post(BlackboardEntry.model_validate(raw))
            except Exception:  # noqa: BLE001 - a corrupt entry must not block resume
                continue


class MissionStore:
    """Atomic local JSON persistence for mission state."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path(root) if root else _default_root()

    def _path(self, execution_id: str) -> Path:
        safe = "".join(c for c in execution_id if c.isalnum() or c in ("-", "_")) or "mission"
        return self._root / f"{safe}.json"

    def save(self, state: MissionState) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)
        path = self._path(state.execution_id)
        # atomic write: temp file + replace so a crash never leaves a partial file
        fd, tmp = tempfile.mkstemp(dir=str(self._root), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(state.to_json(), fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
        return path

    def load(self, execution_id: str) -> MissionState | None:
        path = self._path(execution_id)
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return MissionState.from_json(json.load(fh))
        except Exception:  # noqa: BLE001 - a corrupt checkpoint means start fresh
            return None

    def exists(self, execution_id: str) -> bool:
        return self._path(execution_id).exists()

    def delete(self, execution_id: str) -> None:
        path = self._path(execution_id)
        if path.exists():
            path.unlink()

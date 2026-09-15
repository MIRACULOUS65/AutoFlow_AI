"""Execution dataset (tuning-readiness — NOT fine-tuning).

Structured, secret-redacted records of real executions (successful and failed)
in a format that could later feed supervised tuning / RLAIF WITHOUT contaminating
the current runtime. Nothing here trains a model; it only records what happened.

Each record captures: task, context_refs, observation, model, decision, action,
tool, tool_result, verification, recovery, final_outcome. Secrets are redacted
before anything is written.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


_SECRET_KEYS = ("api_key", "authorization", "token", "password", "secret", "cookie",
                "apikey", "auth")
_SECRET_VALUE_MARKERS = ("nvapi-", "ms-cfaabe", "bearer ", "sk-")


def _redact(value):
    """Recursively redact secret keys/values from a JSON-able structure."""

    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(m in str(k).lower() for m in _SECRET_KEYS):
                out[k] = "[redacted]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    if isinstance(value, str):
        low = value.lower()
        if any(m in low for m in _SECRET_VALUE_MARKERS):
            return "[redacted]"
        return value[:2000]
    return value


@dataclass
class ExecutionRecord:
    task: str
    context_refs: list[str] = field(default_factory=list)
    observation: str = ""
    model: str = ""
    decision: str = ""
    action: str = ""
    tool: str | None = None
    tool_result: dict = field(default_factory=dict)
    verification: str = ""
    recovery: str = ""
    final_outcome: str = ""

    def to_json(self) -> dict:
        return _redact({
            "task": self.task,
            "context_refs": self.context_refs,
            "observation": self.observation,
            "model": self.model,
            "decision": self.decision,
            "action": self.action,
            "tool": self.tool,
            "tool_result": self.tool_result,
            "verification": self.verification,
            "recovery": self.recovery,
            "final_outcome": self.final_outcome,
        })


class DatasetWriter:
    """Appends ExecutionRecords to a local JSONL file (secret-redacted)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def append(self, record: ExecutionRecord) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_json(), ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        out = []
        with open(self._path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def count(self) -> int:
        return len(self.read_all())


def records_from_mission(bus, board, *, task: str, outcome: str) -> list[ExecutionRecord]:
    """Derive execution records from a completed mission's bus + board (redacted)."""

    from ..society.blackboard import TrustClass

    records: list[ExecutionRecord] = []
    # one record per task that produced tool-result evidence
    tool_entries = {e.task_id: e for e in board.all_entries()
                    if e.trust == TrustClass.TOOL_RESULT and e.task_id}
    verified = {e.task_id for e in board.all_entries()
                if e.trust == TrustClass.VERIFICATION and e.key.startswith("verified:")}
    for tid, entry in tool_entries.items():
        records.append(ExecutionRecord(
            task=task,
            context_refs=[f"blackboard:{entry.key}"],
            observation=entry.summary,
            action="tool_call",
            tool=str(entry.value.get("tool")) if isinstance(entry.value, dict) else None,
            tool_result=entry.value if isinstance(entry.value, dict) else {},
            verification="verified" if tid in verified else "not_verified",
            final_outcome=outcome,
        ))
    return records

"""Model Evaluation / Simulation Lab.

A dedicated lab to test every configured model provider independently and
compare them structurally on the SAME tasks. It reuses the existing model
gateway (no second gateway, no hardcoded credentials) and never streams secrets
or private chain-of-thought — only structured decision summaries, timing, and
validation status.
"""

from __future__ import annotations

from .events import LabEvent, LabEventType, ModelTrace
from .runner import (
    LabRunResult,
    ModelLab,
    ProviderInfo,
)
from .dataset import BenchmarkTask, DEFAULT_BENCHMARK, TaskKind
from .scorecard import ModelScorecard, score_runs
from .execution_dataset import (
    DatasetWriter,
    ExecutionRecord,
    records_from_mission,
)
from . import manifest

__all__ = [
    "ModelLab",
    "LabRunResult",
    "ProviderInfo",
    "LabEvent",
    "LabEventType",
    "ModelTrace",
    "BenchmarkTask",
    "TaskKind",
    "DEFAULT_BENCHMARK",
    "ModelScorecard",
    "score_runs",
    "DatasetWriter",
    "ExecutionRecord",
    "records_from_mission",
    "manifest",
]

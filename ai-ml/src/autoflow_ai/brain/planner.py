"""Planner: NormalizedTask -> validated TaskGraph.

For the document-edit slice the planner emits a canonical 4-step DAG:

    inspect -> edit -> save -> verify

Each node carries the concrete parameters the execution engine needs (path,
edit operations) inside ``expected_state``. The TaskGraph itself performs
structural validation (no cycles, valid refs) on construction.
"""

from __future__ import annotations

from ..editing.operations import detect_operations_from_prompt
from ..schemas.enums import AgentKind, RiskClass
from ..schemas.tasks import (
    NormalizedTask,
    TaskEdge,
    TaskGraph,
    TaskNode,
    VerificationRequirement,
)


class PlanError(Exception):
    """A plan could not be generated for the normalized task."""


class Planner:
    def plan(self, normalized: NormalizedTask, *, prompt: str) -> TaskGraph:
        target = self._target_path(normalized)
        if not target:
            raise PlanError("cannot plan document edit without a target file")

        ops = detect_operations_from_prompt(prompt)
        op_payload = [op.model_dump(mode="json") for op in ops]

        nodes = (
            TaskNode(
                step_id="step_inspect",
                objective="Open and inspect the target document.",
                assigned_agent=AgentKind.DOCUMENT,
                expected_state={"tool": "document.inspect", "path": target},
                available_capabilities=("document_editing",),
                risk=RiskClass.LOW,
            ),
            TaskNode(
                step_id="step_edit",
                objective="Apply the requested structured edits.",
                assigned_agent=AgentKind.DOCUMENT,
                expected_state={"tool": "document.edit", "operations": op_payload},
                available_capabilities=("document_editing",),
                risk=RiskClass.LOW,
            ),
            TaskNode(
                step_id="step_save",
                objective="Save the edited document to the same file.",
                assigned_agent=AgentKind.DOCUMENT,
                expected_state={"tool": "document.save", "target_path": target},
                available_capabilities=("document_editing",),
                risk=RiskClass.LOW,
            ),
            TaskNode(
                step_id="step_verify",
                objective="Verify the edits are present and the file is valid.",
                assigned_agent=AgentKind.QA,
                expected_state={"tool": "document.verify", "path": target},
                verification=(
                    VerificationRequirement(
                        check_id="edits_present",
                        description="requested edits are reflected in saved file",
                    ),
                    VerificationRequirement(
                        check_id="file_reopens",
                        description="saved file reopens and is structurally valid",
                    ),
                ),
                risk=RiskClass.LOW,
            ),
        )
        edges = (
            TaskEdge(from_step="step_inspect", to_step="step_edit"),
            TaskEdge(from_step="step_edit", to_step="step_save"),
            TaskEdge(from_step="step_save", to_step="step_verify"),
        )
        return TaskGraph(
            task_id=normalized.task_id,
            goal=normalized.objective,
            nodes=nodes,
            edges=edges,
        )

    @staticmethod
    def _target_path(normalized: NormalizedTask) -> str | None:
        for entity in normalized.entities:
            if entity.startswith("file:"):
                return entity[len("file:") :]
        return None

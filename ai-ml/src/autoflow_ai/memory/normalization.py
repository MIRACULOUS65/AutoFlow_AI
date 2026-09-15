"""Trace normalization: execution trace -> SemanticWorkflow candidate.

Strips implementation noise (coordinates, DOM ids, window positions) and keeps
semantic tool/capability steps. Extracts variable parameters from step args.
"""

from __future__ import annotations

import re

from .models import SemanticWorkflow, WorkflowParameter, WorkflowStep

_COORD_RE = re.compile(r"\b\d{2,4}\s*,\s*\d{2,4}\b")
_DOM_RE = re.compile(r"(dom|node|xpath|css)[-_ ]?id", re.IGNORECASE)

# map tool names to canonical semantic step names
_STEP_NAME_BY_TOOL = {
    "document.inspect": "InspectDocument",
    "document.edit": "EditDocument",
    "document.save": "SaveDocument",
    "document.verify": "VerifyDocument",
    "email.create_draft": "CreateDraft",
    "email.attach": "AttachArtifact",
    "email.send": "SendEmail",
}


class WorkflowNormalizer:
    """Convert an execution report (Phase-1/vertical-slice shape) into a
    SemanticWorkflow. Accepts a light dict trace so it stays decoupled."""

    def normalize(self, trace: dict) -> SemanticWorkflow:
        """``trace`` = {intent, steps:[{tool, args, verifier?, approval?}], ...}"""

        intent = trace.get("intent") or trace.get("goal") or "workflow"
        raw_steps = trace.get("steps", [])
        steps: list[WorkflowStep] = []
        tools: set[str] = set()
        params: dict[str, WorkflowParameter] = {}
        prev_name: str | None = None

        verification_rules: list[str] = list(trace.get("verification_rules", ()))
        used_names: dict[str, int] = {}
        for raw in raw_steps:
            tool = raw.get("tool")
            if not tool:
                continue
            if tool.endswith(".verify"):
                # verification is a rule, not a semantic side-effect step/tool
                if tool not in verification_rules:
                    verification_rules.append(tool)
                continue
            name = _STEP_NAME_BY_TOOL.get(tool, self._semantic_name(tool))
            # ensure unique step names (a workflow may repeat a capability)
            if name in used_names:
                used_names[name] += 1
                name = f"{name}{used_names[name]}"
            else:
                used_names[name] = 1
            args = self._clean_args(raw.get("args", {}))
            # extract path-like args as parameters
            for key, val in list(args.items()):
                if key in ("path", "target_path", "document_id", "recipient_group"):
                    params.setdefault(
                        key, WorkflowParameter(name=key, description=f"{key} for the workflow")
                    )
                    args[key] = f"${{{key}}}"
            tools.add(tool)
            step = WorkflowStep(
                name=name,
                capability=self._capability_for(tool),
                tool=tool,
                parameters=args,
                depends_on=(prev_name,) if prev_name else (),
                requires_approval=bool(raw.get("approval")),
                verifier=raw.get("verifier"),
            )
            steps.append(step)
            prev_name = name

        if not steps:
            # ensure at least one semantic step so the model validates
            steps.append(WorkflowStep(name="NoOp", capability="none"))

        return SemanticWorkflow(
            intent=intent,
            capabilities=tuple(sorted({self._capability_for(t) for t in tools})),
            tools=tuple(sorted(tools)),
            steps=tuple(steps),
            parameters=tuple(params.values()),
            verification_rules=tuple(dict.fromkeys(verification_rules)),
            approval_points=tuple(s.name for s in steps if s.requires_approval),
        )

    @staticmethod
    def _clean_args(args: dict) -> dict:
        cleaned = {}
        for k, v in args.items():
            if isinstance(v, str):
                if _COORD_RE.search(v) or _DOM_RE.search(k):
                    continue  # drop coordinate/DOM noise
            cleaned[k] = v
        return cleaned

    @staticmethod
    def _semantic_name(tool: str) -> str:
        # e.g. "browser.click" -> "BrowserClick"
        parts = re.split(r"[._]", tool)
        return "".join(p.capitalize() for p in parts if p) or "Step"

    @staticmethod
    def _capability_for(tool: str) -> str:
        prefix = tool.split(".")[0]
        return {
            "document": "document_editing",
            "email": "communication",
            "browser": "browser_automation",
            "files": "file_operations",
        }.get(prefix, prefix)

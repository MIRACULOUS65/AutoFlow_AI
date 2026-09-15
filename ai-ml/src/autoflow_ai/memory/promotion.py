"""Workflow promotion policy.

A candidate becomes reusable memory only when it satisfies ALL gates. Failed /
cancelled / unverified executions are rejected. Secrets and unregistered tools
are rejected. Human confirmation is configurable, not hardcoded.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import WorkflowCandidate, contains_secret


@dataclass
class PromotionContext:
    registered_tools: set[str]
    human_confirmed: bool = False
    require_human_confirmation: bool = False


class WorkflowPromotionPolicy:
    def evaluate(self, candidate: WorkflowCandidate, ctx: PromotionContext) -> list[str]:
        """Return a list of rejection reasons (empty => may promote)."""

        reasons: list[str] = []

        if not candidate.verified:
            reasons.append("execution not verified")

        if not candidate.source_execution_ids:
            reasons.append("missing provenance (no source execution)")

        # semantic body must be structurally valid (model already enforces),
        # but re-check for empty/NoOp-only bodies
        if all(s.capability == "none" for s in candidate.workflow.steps):
            reasons.append("workflow has no meaningful steps")

        # no secrets anywhere in the serialized body
        if contains_secret(candidate.workflow.model_dump_json()):
            reasons.append("workflow contains secret-like content")

        # all tools referenced must be registered
        unknown = set(candidate.workflow.tools) - ctx.registered_tools
        if unknown:
            reasons.append(f"unregistered tools: {sorted(unknown)}")

        # no raw coordinates as canonical steps (WorkflowStep validator already
        # blocks this at construction; re-affirm defensively)
        for step in candidate.workflow.steps:
            if step.name.lower().startswith("click(") or "," in step.name and any(ch.isdigit() for ch in step.name):
                reasons.append(f"coordinate-like step name: {step.name!r}")

        if ctx.require_human_confirmation and not ctx.human_confirmed:
            reasons.append("human confirmation required but not provided")

        return reasons

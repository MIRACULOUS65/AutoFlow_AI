"""Parameter binding for workflow reuse.

Binds new parameter values into a stored workflow's ``${param}`` placeholders
WITHOUT altering workflow semantics. Only parameter substitution happens; step
names, tools, dependencies and verification are preserved exactly.
"""

from __future__ import annotations

from .errors import CompatibilityError
from .models import SemanticWorkflow, WorkflowStep


def bind_parameters(workflow: SemanticWorkflow, provided: dict) -> SemanticWorkflow:
    """Return a new SemanticWorkflow with parameters bound. Raises if a required
    parameter has neither a provided value nor a default."""

    values: dict[str, str] = {}
    for p in workflow.parameters:
        if p.name in provided:
            values[p.name] = str(provided[p.name])
        elif p.default is not None:
            values[p.name] = p.default
        elif p.required:
            raise CompatibilityError(f"missing required parameter: {p.name}")

    def _sub(args: dict) -> dict:
        out = {}
        for k, v in args.items():
            if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                key = v[2:-1]
                out[k] = values.get(key, v)
            else:
                out[k] = v
        return out

    new_steps = tuple(
        WorkflowStep(
            name=s.name,
            capability=s.capability,
            tool=s.tool,
            parameters=_sub(s.parameters),
            depends_on=s.depends_on,
            requires_approval=s.requires_approval,
            verifier=s.verifier,
        )
        for s in workflow.steps
    )
    # semantics preserved: only parameters differ
    return workflow.model_copy(update={"steps": new_steps})

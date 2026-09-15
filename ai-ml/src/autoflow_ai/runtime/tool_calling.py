"""ToolCallingController — the single authority chain between agents and tools.

An agent PROPOSES a semantic action; this controller is the only thing that
turns a proposal into a real tool execution, enforcing:

    proposal -> schema validation -> tool registry lookup -> authorization
    -> policy/risk -> approval -> execute -> observation -> (secret sanitize)

Unknown/unregistered/unauthorized/blocked tools and high-risk-without-approval
all fail closed. Secrets in arguments/results are redacted from the returned
trace record.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..schemas.enums import RiskClass
from ..schemas.tools import ToolCallRequest, ToolCallResult
from .registry import ToolRegistry

# Tool names that must never execute (defense in depth alongside not-registering).
_BLOCKED = frozenset(
    {
        "computer.close_window", "computer.delete", "computer.shutdown",
        "computer.restart", "computer.install", "computer.execute_shell",
        "system.shell", "os.exec", "shell.run",
    }
)

_SECRET_KEYS = {"password", "api_key", "apikey", "secret", "token", "access_token", "authorization"}
_SECRET_RE = re.compile(r"(nvapi-[A-Za-z0-9_\-]{6,}|ms-[0-9a-f-]{8,}|sk-[A-Za-z0-9]{10,}|Bearer\s+\S+)")


def _sanitize_args(args: dict) -> dict:
    out = {}
    for k, v in args.items():
        if k.lower() in _SECRET_KEYS:
            out[k] = "***redacted***"
        elif isinstance(v, str) and _SECRET_RE.search(v):
            out[k] = "***redacted***"
        elif k == "text" and isinstance(v, str):
            # never echo typed text; record length only
            out[k] = f"<text len={len(v)}>"
        else:
            out[k] = v
    return out


@dataclass
class ControllerDecision:
    allowed: bool
    reason: str = ""
    requires_approval: bool = False


class ToolCallingController:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        permissions: frozenset[str],
        approvals: frozenset[str] = frozenset(),  # tool names with granted approval
    ) -> None:
        self._registry = registry
        self._permissions = permissions
        self._approvals = approvals

    def authorize(self, tool_name: str) -> ControllerDecision:
        if tool_name in _BLOCKED:
            return ControllerDecision(False, f"blocked tool: {tool_name}")
        if not self._registry.has(tool_name):
            return ControllerDecision(False, f"unknown/unregistered tool: {tool_name}")
        definition = self._registry.definition(tool_name)
        if definition.permission_scope not in self._permissions:
            return ControllerDecision(False, f"permission denied: {definition.permission_scope}")
        if definition.risk_class in (RiskClass.HIGH, RiskClass.CRITICAL) or definition.requires_approval:
            if tool_name not in self._approvals:
                return ControllerDecision(False, f"approval required for {tool_name}", requires_approval=True)
        return ControllerDecision(True)

    def call(
        self,
        *,
        tool_name: str,
        arguments: dict,
        execution_id: str,
        step_id: str,
        reason: str = "",
    ) -> tuple[ToolCallResult, dict]:
        """Authorize + execute. Returns (result, sanitized_trace_record).

        The trace record never contains secrets or raw typed text.
        """

        decision = self.authorize(tool_name)
        sanitized = _sanitize_args(arguments)
        if not decision.allowed:
            result = ToolCallResult(
                tool_call_id=f"tcall_{step_id.replace('step_', '') or 'x'}",
                tool_name=tool_name,
                ok=False,
                error_type="approval_required" if decision.requires_approval else "unauthorized",
                error_message=decision.reason,
            )
            return result, {"tool": tool_name, "args": sanitized, "ok": False, "reason": decision.reason}

        call = ToolCallRequest(
            tool_call_id=f"tcall_{(step_id.replace('step_', '') or 'x')}",
            tool_name=tool_name,
            arguments=arguments,
            execution_id=execution_id,
            step_id=step_id,
            reason=(reason or f"advance {step_id}")[:200],
        )
        result = self._registry.execute(call)
        trace = {"tool": tool_name, "args": sanitized, "ok": result.ok}
        if not result.ok:
            trace["error_type"] = result.error_type
        return result, trace

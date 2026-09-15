"""Deterministic mock tool runtime.

Registers a fixed set of tools with no real external side effects. Each returns
a deterministic result. Tools that create deliverables report an artifact
reference the execution controller turns into a persisted Artifact.
"""

from __future__ import annotations

from app.db.base import new_id
from app.domain.enums import ArtifactType
from app.schemas.agents import ToolCall, ToolResult

_KNOWN_TOOLS: dict[str, ArtifactType | None] = {
    "filesystem.create": ArtifactType.JSON,
    "document.create": ArtifactType.DOCX,
    "spreadsheet.create": ArtifactType.XLSX,
    "email.prepare": ArtifactType.EMAIL_DRAFT,
    "email.send.mock": None,
    "knowledge.retrieve.mock": None,
}


class MockToolRuntime:
    def is_allowed(self, tool: str) -> bool:
        return tool in _KNOWN_TOOLS

    async def execute(self, call: ToolCall) -> ToolResult:
        tool_call_id = new_id("tool")
        if not self.is_allowed(call.tool):
            return ToolResult(
                tool_call_id=tool_call_id,
                status="failed",
                error=f"Unknown tool: {call.tool}",
            )

        artifact_kind = _KNOWN_TOOLS[call.tool]
        output: dict = {"tool": call.tool, "arguments": call.arguments}
        artifact_ref: str | None = None

        if artifact_kind is not None:
            name = call.arguments.get("name") or _default_name(call.tool, artifact_kind)
            artifact_ref = f"artifact://{name}"
            output["artifact"] = {"name": name, "kind": artifact_kind.value}
        elif call.tool == "email.send.mock":
            output["delivered"] = True
            output["recipient"] = call.arguments.get("recipient", "finance@example.com")
        elif call.tool == "knowledge.retrieve.mock":
            output["results"] = [
                {"id": "kn_ops_handbook", "title": "Operations Handbook"},
                {"id": "kn_reporting_policy", "title": "Reporting Policy"},
                {"id": "kn_finance_sop", "title": "Finance SOP"},
            ]

        return ToolResult(
            tool_call_id=tool_call_id,
            status="completed",
            output=output,
            artifact_ref=artifact_ref,
        )


def _default_name(tool: str, kind: ArtifactType) -> str:
    ext = kind.value.lower()
    base = tool.split(".")[0]
    return f"{base}.{ext}"

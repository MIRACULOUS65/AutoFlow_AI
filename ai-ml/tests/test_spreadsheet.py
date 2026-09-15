"""Tests for the real .xlsx spreadsheet capability.

Covers the adapter (build + reopen), the spreadsheet.create / spreadsheet.validate
tools (real file on disk, deterministic aggregation), independent verification
(tampered totals are caught), and path-scope enforcement (no escape).
"""

from __future__ import annotations

from pathlib import Path

import openpyxl
import pytest

from autoflow_ai.documents.base import DocumentError, open_document
from autoflow_ai.documents.spreadsheet_adapter import SpreadsheetAdapter
from autoflow_ai.runtime.registry import ToolRegistry
from autoflow_ai.runtime.spreadsheet_tools import (
    SpreadsheetSession,
    register_spreadsheet_tools,
)
from autoflow_ai.schemas.tools import ToolCallRequest

pytestmark = pytest.mark.integration


def _write_sources(root: Path) -> None:
    (root / "sales.csv").write_text(
        "region,units_sold,revenue_usd\n"
        "North,120,48000\nSouth,95,38000\nEast,140,56000\n"
        "West,110,44000\nCentral,85,34000\n",
        encoding="utf-8",
    )
    (root / "operations.csv").write_text(
        "region,orders_processed,on_time_deliveries,incidents\n"
        "North,320,308,2\nSouth,260,249,3\nEast,410,402,1\n"
        "West,300,285,4\nCentral,230,224,1\n",
        encoding="utf-8",
    )
    (root / "targets.csv").write_text(
        "region,revenue_target_usd,on_time_target_pct\n"
        "North,45000,95\nSouth,40000,95\nEast,52000,97\n"
        "West,46000,95\nCentral,33000,94\n",
        encoding="utf-8",
    )


def _registry(root: Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_spreadsheet_tools(reg, SpreadsheetSession(), workspace_root=root)
    return reg


def _call(reg: ToolRegistry, name: str, args: dict, seed: str):
    return reg.execute(
        ToolCallRequest(
            tool_call_id=f"tcall_{seed*6}"[:16],
            tool_name=name,
            arguments=args,
            execution_id=f"exec_{seed*10}"[:16],
            step_id=f"step_{seed*10}"[:16],
        )
    )


def _create_args(out: str = "report.xlsx") -> dict:
    return {
        "target_path": out,
        "sales_csv": "sales.csv",
        "operations_csv": "operations.csv",
        "targets_csv": "targets.csv",
        "period_label": "This Week",
    }


def _validate_args(out: str = "report.xlsx") -> dict:
    return {
        "artifact_path": out,
        "sales_csv": "sales.csv",
        "operations_csv": "operations.csv",
        "targets_csv": "targets.csv",
        "min_on_time_pct": 95.0,
    }


# 1. create produces a real .xlsx on disk with correct totals
def test_create_produces_real_xlsx(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    r = _call(reg, "spreadsheet.create", _create_args(), "a")
    assert r.ok, r.error_message
    assert (tmp_path / "report.xlsx").is_file()
    t = r.output["totals"]
    assert t["total_revenue_usd"] == 220000
    assert t["total_units_sold"] == 550
    assert t["total_orders_processed"] == 1520
    assert t["total_on_time_deliveries"] == 1468
    assert t["revenue_vs_target_usd"] == 4000
    assert t["on_time_rate_pct"] == 96.58
    assert r.output["by_region_rows"] == 5
    assert r.output["hash"]


# 2. the workbook reopens with the expected structure
def test_workbook_structure(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    _call(reg, "spreadsheet.create", _create_args(), "b")
    wb = SpreadsheetAdapter(tmp_path / "report.xlsx")
    assert wb.sheet_names() == ["Summary", "By Region"]
    header = wb.header("By Region")
    assert header[0] == "Region"
    assert "Revenue (USD)" in header
    assert len(wb.rows("By Region")) == 5


# 3. independent validation passes for a genuine artifact
def test_validate_passes_for_genuine_artifact(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    _call(reg, "spreadsheet.create", _create_args(), "c")
    v = _call(reg, "spreadsheet.validate", _validate_args(), "d")
    assert v.ok
    assert v.output["verified"] is True
    assert all(c["passed"] for c in v.output["checks"])
    ids = {c["id"] for c in v.output["checks"]}
    assert {"file_exists", "workbook_opens", "totals_reconcile"} <= ids


# 4. tampered totals are caught (verification is independent, not self-report)
def test_validate_catches_tampered_totals(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    _call(reg, "spreadsheet.create", _create_args(), "e")
    path = tmp_path / "report.xlsx"
    wb = openpyxl.load_workbook(str(path))
    ws = wb["Summary"]
    for row in ws.iter_rows():
        if row[0].value == "Total Revenue (USD)":
            row[1].value = 999999
    wb.save(str(path))

    v = _call(reg, "spreadsheet.validate", _validate_args(), "f")
    assert v.ok
    assert v.output["verified"] is False
    failed = {c["id"] for c in v.output["checks"] if not c["passed"]}
    assert "totals_reconcile" in failed


# 5. validation fails honestly for a missing artifact
def test_validate_missing_artifact(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    v = _call(reg, "spreadsheet.validate", _validate_args("does_not_exist.xlsx"), "g")
    assert v.ok  # tool ran; verdict is the payload
    assert v.output["verified"] is False


# 6. path escape is rejected (no writing outside the workspace root)
def test_path_escape_rejected(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    r = _call(reg, "spreadsheet.create", _create_args("../../evil.xlsx"), "h")
    assert not r.ok
    assert r.error_type == "path_out_of_scope"


# 7. wrong extension is rejected
def test_non_xlsx_target_rejected(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    r = _call(reg, "spreadsheet.create", _create_args("report.txt"), "i")
    assert not r.ok
    assert r.error_type == "invalid_extension"


# 8. open_document now dispatches .xlsx to the spreadsheet adapter
def test_open_document_dispatches_xlsx(tmp_path):
    _write_sources(tmp_path)
    reg = _registry(tmp_path)
    _call(reg, "spreadsheet.create", _create_args(), "j")
    adapter = open_document(tmp_path / "report.xlsx")
    assert isinstance(adapter, SpreadsheetAdapter)
    assert "Summary" in adapter.read_text()


# 9. a non-workbook file with .xlsx suffix fails safely
def test_bad_xlsx_fails_safely(tmp_path):
    bad = tmp_path / "bad.xlsx"
    bad.write_text("this is not a workbook", encoding="utf-8")
    with pytest.raises(DocumentError):
        open_document(bad)

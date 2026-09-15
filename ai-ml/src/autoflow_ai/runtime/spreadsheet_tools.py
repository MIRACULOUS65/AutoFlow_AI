"""Deterministic spreadsheet tools: spreadsheet.create and spreadsheet.validate.

These are the only path to spreadsheet side effects. They produce a REAL .xlsx
workbook on disk from approved tabular sources, and independently reopen it to
verify structure and reconcile totals.

Design notes (honesty + separation of concerns):

  * ``spreadsheet.create`` builds the workbook. It reads approved CSV sources,
    aggregates them deterministically, writes a real .xlsx via openpyxl, and
    returns the sha256 hash + the totals it computed FROM THE SOURCES.
  * ``spreadsheet.validate`` does NOT trust the creator. It reopens the file
    from disk with a fresh adapter and checks: file exists, workbook opens,
    required sheets present, required columns present, expected row count, and
    that the numbers written into the workbook reconcile with the numbers
    recomputed independently from the approved sources. A generator that lied
    about a total would be caught here.

Both tools are path-scoped: writes/reads are confined to an allowed workspace
root passed at registration time. Path escape (``..``/absolute outside root),
wrong extension, and oversized output are rejected.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..documents.base import DocumentError, sha256_file
from ..documents.spreadsheet_adapter import SpreadsheetAdapter
from ..schemas.enums import RiskClass
from ..schemas.tools import ToolDefinition
from .registry import ToolExecutionError, ToolRegistry

# The workbook shape the flagship report uses. Kept here (not hardcoded into the
# orchestrator) so the tool has a stable, verifiable contract.
_SUMMARY_SHEET = "Summary"
_BY_REGION_SHEET = "By Region"
_BY_REGION_COLUMNS = [
    "Region",
    "Units Sold",
    "Revenue (USD)",
    "Orders Processed",
    "On-Time Deliveries",
    "On-Time %",
    "Revenue Target (USD)",
    "Revenue vs Target (USD)",
]
_MAX_XLSX_BYTES = 10 * 1024 * 1024  # 10 MB cap on generated artifact


class SpreadsheetSession:
    """Per-execution state shared by the spreadsheet tools."""

    def __init__(self) -> None:
        self.path: Path | None = None
        self.hash: str | None = None
        self.computed_totals: dict[str, Any] = {}


def _resolve_in_root(root: Path, candidate: str) -> Path:
    """Resolve ``candidate`` and confirm it stays within ``root``.

    Rejects path escape (``..`` / absolute paths outside the workspace root).
    """
    p = Path(candidate)
    resolved = (p if p.is_absolute() else (root / p)).resolve()
    root_resolved = root.resolve()
    if root_resolved != resolved and root_resolved not in resolved.parents:
        raise ToolExecutionError(
            "path_out_of_scope",
            f"path escapes the allowed workspace: {candidate!r}",
        )
    return resolved


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    except FileNotFoundError as exc:
        raise ToolExecutionError("source_missing", f"source not found: {path}") from exc
    except OSError as exc:  # noqa: BLE001
        raise ToolExecutionError("source_unreadable", f"cannot read {path}: {exc}") from exc


def _int(row: dict[str, str], key: str, source: Path) -> int:
    try:
        return int(str(row[key]).strip())
    except (KeyError, ValueError) as exc:
        raise ToolExecutionError(
            "source_malformed",
            f"expected integer column {key!r} in {source.name}",
        ) from exc


def _aggregate(sales_rows, ops_rows, targets_rows, sources) -> dict[str, Any]:
    """Reconcile the three approved sources by region into per-region + totals.

    Deterministic; no model involved. This is the single source of truth for
    both the workbook contents and (recomputed) verification.
    """
    s_src, o_src, t_src = sources
    by_region: dict[str, dict[str, Any]] = {}

    for r in sales_rows:
        region = str(r.get("region", "")).strip()
        if not region:
            continue
        by_region.setdefault(region, {})
        by_region[region]["units_sold"] = _int(r, "units_sold", s_src)
        by_region[region]["revenue_usd"] = _int(r, "revenue_usd", s_src)

    for r in ops_rows:
        region = str(r.get("region", "")).strip()
        if region not in by_region:
            continue
        by_region[region]["orders_processed"] = _int(r, "orders_processed", o_src)
        by_region[region]["on_time_deliveries"] = _int(r, "on_time_deliveries", o_src)
        by_region[region]["incidents"] = _int(r, "incidents", o_src)

    for r in targets_rows:
        region = str(r.get("region", "")).strip()
        if region not in by_region:
            continue
        by_region[region]["revenue_target_usd"] = _int(r, "revenue_target_usd", t_src)

    regions = sorted(by_region)
    rows: list[list[Any]] = []
    tot = {
        "total_units_sold": 0,
        "total_revenue_usd": 0,
        "total_orders_processed": 0,
        "total_on_time_deliveries": 0,
        "total_incidents": 0,
        "total_revenue_target_usd": 0,
    }
    for region in regions:
        d = by_region[region]
        units = d.get("units_sold", 0)
        revenue = d.get("revenue_usd", 0)
        orders = d.get("orders_processed", 0)
        on_time = d.get("on_time_deliveries", 0)
        incidents = d.get("incidents", 0)
        target = d.get("revenue_target_usd", 0)
        on_time_pct = round(on_time / orders * 100, 2) if orders else 0.0
        rows.append([
            region, units, revenue, orders, on_time, on_time_pct, target, revenue - target,
        ])
        tot["total_units_sold"] += units
        tot["total_revenue_usd"] += revenue
        tot["total_orders_processed"] += orders
        tot["total_on_time_deliveries"] += on_time
        tot["total_incidents"] += incidents
        tot["total_revenue_target_usd"] += target

    tot["revenue_vs_target_usd"] = tot["total_revenue_usd"] - tot["total_revenue_target_usd"]
    tot["on_time_rate_pct"] = (
        round(tot["total_on_time_deliveries"] / tot["total_orders_processed"] * 100, 2)
        if tot["total_orders_processed"] else 0.0
    )
    return {"regions": regions, "by_region_rows": rows, "totals": tot}


def register_spreadsheet_tools(
    registry: ToolRegistry,
    session: SpreadsheetSession,
    *,
    workspace_root: Path,
) -> None:
    """Register spreadsheet.create / spreadsheet.validate scoped to a workspace."""

    root = Path(workspace_root)

    # -- spreadsheet.create --------------------------------------------------
    create_def = ToolDefinition(
        name="spreadsheet.create",
        description=(
            "Build a real .xlsx report from approved CSV sources (sales, "
            "operations, targets). Aggregates by region deterministically and "
            "writes Summary + By Region sheets. Returns the artifact path, "
            "sha256 hash and the totals computed from the sources."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "target_path": {"type": "string"},
                "sales_csv": {"type": "string"},
                "operations_csv": {"type": "string"},
                "targets_csv": {"type": "string"},
                "period_label": {"type": "string"},
            },
            "required": ["target_path", "sales_csv", "operations_csv", "targets_csv"],
            "additionalProperties": False,
        },
        risk_class=RiskClass.LOW,
        permission_scope="files:write",
        idempotent=True,
    )

    def _create(args: dict[str, Any]) -> dict[str, Any]:
        target = _resolve_in_root(root, args["target_path"])
        if target.suffix.lower() != ".xlsx":
            raise ToolExecutionError("invalid_extension", "target must be a .xlsx file")
        s_src = _resolve_in_root(root, args["sales_csv"])
        o_src = _resolve_in_root(root, args["operations_csv"])
        t_src = _resolve_in_root(root, args["targets_csv"])
        period = str(args.get("period_label") or "This Week")

        agg = _aggregate(
            _read_csv(s_src), _read_csv(o_src), _read_csv(t_src), (s_src, o_src, t_src)
        )
        totals = agg["totals"]

        try:
            wb = SpreadsheetAdapter(target, create=True)
            wb.write_sheet(
                _SUMMARY_SHEET,
                ["Metric", "Value"],
                [
                    ["Period", period],
                    ["Regions", len(agg["regions"])],
                    ["Total Units Sold", totals["total_units_sold"]],
                    ["Total Revenue (USD)", totals["total_revenue_usd"]],
                    ["Total Orders Processed", totals["total_orders_processed"]],
                    ["Total On-Time Deliveries", totals["total_on_time_deliveries"]],
                    ["On-Time Rate (%)", totals["on_time_rate_pct"]],
                    ["Total Incidents", totals["total_incidents"]],
                    ["Total Revenue Target (USD)", totals["total_revenue_target_usd"]],
                    ["Revenue vs Target (USD)", totals["revenue_vs_target_usd"]],
                ],
            )
            wb.write_sheet(_BY_REGION_SHEET, _BY_REGION_COLUMNS, agg["by_region_rows"])
            target.parent.mkdir(parents=True, exist_ok=True)
            saved = wb.save(target)
        except DocumentError as exc:
            raise ToolExecutionError("spreadsheet_write_failed", str(exc)) from exc

        size = saved.stat().st_size
        if size > _MAX_XLSX_BYTES:
            saved.unlink(missing_ok=True)
            raise ToolExecutionError("artifact_too_large", f"generated .xlsx exceeds cap ({size} bytes)")

        digest = sha256_file(saved)
        session.path = saved
        session.hash = digest
        session.computed_totals = totals
        return {
            "artifact_path": str(saved),
            "sheets": [_SUMMARY_SHEET, _BY_REGION_SHEET],
            "by_region_rows": len(agg["by_region_rows"]),
            "hash": digest,
            "size_bytes": size,
            "totals": totals,
        }

    registry.register(create_def, _create)

    # -- spreadsheet.validate ------------------------------------------------
    validate_def = ToolDefinition(
        name="spreadsheet.validate",
        description=(
            "Independently reopen a generated .xlsx and verify it: file exists, "
            "workbook opens, required sheets/columns present, expected row "
            "count, and totals reconcile with values recomputed from the "
            "approved sources. Does not trust the creator's report."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "artifact_path": {"type": "string"},
                "sales_csv": {"type": "string"},
                "operations_csv": {"type": "string"},
                "targets_csv": {"type": "string"},
                "min_on_time_pct": {"type": "number"},
            },
            "required": ["artifact_path", "sales_csv", "operations_csv", "targets_csv"],
            "additionalProperties": False,
        },
        risk_class=RiskClass.LOW,
        permission_scope="files:read",
        idempotent=True,
    )

    def _validate(args: dict[str, Any]) -> dict[str, Any]:
        artifact = _resolve_in_root(root, args["artifact_path"])
        s_src = _resolve_in_root(root, args["sales_csv"])
        o_src = _resolve_in_root(root, args["operations_csv"])
        t_src = _resolve_in_root(root, args["targets_csv"])
        min_on_time = float(args.get("min_on_time_pct", 0.0))

        checks: list[dict[str, Any]] = []

        def record(check_id: str, passed: bool, detail: str | None = None) -> None:
            checks.append({"id": check_id, "passed": bool(passed), "detail": detail})

        # 1. file exists
        exists = artifact.is_file()
        record("file_exists", exists, None if exists else f"missing: {artifact}")
        if not exists:
            return {"verified": False, "checks": checks}

        # 2. workbook opens (independent reopen from disk)
        try:
            wb = SpreadsheetAdapter(artifact)
        except DocumentError as exc:
            record("workbook_opens", False, str(exc))
            return {"verified": False, "checks": checks}
        record("workbook_opens", True)

        # 3. required sheets present
        names = wb.sheet_names()
        sheets_ok = _SUMMARY_SHEET in names and _BY_REGION_SHEET in names
        record("required_sheets_present", sheets_ok, f"found {names}")

        # 4. required columns present (By Region)
        cols_ok = False
        if _BY_REGION_SHEET in names:
            header = wb.header(_BY_REGION_SHEET)
            cols_ok = all(c in header for c in _BY_REGION_COLUMNS)
            record("required_columns_present", cols_ok, f"header {header}")
        else:
            record("required_columns_present", False, "By Region sheet missing")

        # Recompute totals independently from the approved sources.
        agg = _aggregate(
            _read_csv(s_src), _read_csv(o_src), _read_csv(t_src), (s_src, o_src, t_src)
        )
        expected_rows = len(agg["by_region_rows"])
        expected_totals = agg["totals"]

        # 5. expected row count
        region_rows = wb.rows(_BY_REGION_SHEET) if _BY_REGION_SHEET in names else []
        rows_ok = len(region_rows) == expected_rows
        record("expected_row_count", rows_ok, f"{len(region_rows)} vs {expected_rows}")

        # 6. totals reconcile — read the Summary sheet's written numbers and
        #    compare with the independently recomputed totals.
        summary_map: dict[str, Any] = {}
        if _SUMMARY_SHEET in names:
            for row in wb.rows(_SUMMARY_SHEET):
                if len(row) >= 2 and row[0] is not None:
                    summary_map[str(row[0]).strip()] = row[1]

        def _num(v: Any) -> float | None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        reconcile_pairs = [
            ("Total Units Sold", expected_totals["total_units_sold"]),
            ("Total Revenue (USD)", expected_totals["total_revenue_usd"]),
            ("Total Orders Processed", expected_totals["total_orders_processed"]),
            ("Total On-Time Deliveries", expected_totals["total_on_time_deliveries"]),
            ("Total Incidents", expected_totals["total_incidents"]),
            ("Total Revenue Target (USD)", expected_totals["total_revenue_target_usd"]),
            ("Revenue vs Target (USD)", expected_totals["revenue_vs_target_usd"]),
        ]
        mismatches = []
        for label, expected in reconcile_pairs:
            actual = _num(summary_map.get(label))
            if actual is None or int(actual) != int(expected):
                mismatches.append(f"{label}: workbook={summary_map.get(label)} expected={expected}")
        totals_ok = not mismatches
        record("totals_reconcile", totals_ok, "; ".join(mismatches) or None)

        # 7. revenue meets target
        revenue_ok = expected_totals["revenue_vs_target_usd"] >= 0
        record("revenue_meets_target", revenue_ok,
               f"vs_target={expected_totals['revenue_vs_target_usd']}")

        # 8. on-time rate meets minimum
        on_time_ok = expected_totals["on_time_rate_pct"] >= min_on_time
        record("on_time_rate_meets_min", on_time_ok,
               f"rate={expected_totals['on_time_rate_pct']} min={min_on_time}")

        # 9. content hash recorded
        digest = sha256_file(artifact)
        record("content_hash_recorded", bool(digest))

        verified = all(c["passed"] for c in checks)
        return {
            "verified": verified,
            "checks": checks,
            "hash": digest,
            "recomputed_totals": expected_totals,
        }

    registry.register(validate_def, _validate)

"""Read an employee roster from an uploaded .xlsx for the reassign-work flow.

Uses the existing openpyxl-backed ``SpreadsheetAdapter`` to read the first sheet
and map its columns (via tolerant header matching) onto a canonical employee
record. Real, exact data — no OCR needed for a spreadsheet. The reassign-work
mission narrates this as an "extraction" step for the UI, but it is a real read.

Expected columns (any reasonable header spelling is matched):
  Company ID, Employee ID, Employee Name, Work Email, Department,
  Primary Skill, Secondary Skill, Assigned Work
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..documents.base import DocumentError
from ..documents.spreadsheet_adapter import SpreadsheetAdapter


# Canonical field -> list of accepted header aliases (lowercased, alnum-only).
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "company_id": ("companyid", "company", "orgid", "organizationid"),
    "employee_id": ("employeeid", "empid", "id", "eid", "staffid"),
    "name": ("employeename", "name", "fullname", "empname", "employee"),
    "email": ("workemail", "email", "emailaddress", "mail", "workmail"),
    "department": ("department", "dept", "team", "division"),
    "primary_skill": ("primaryskill", "primary", "mainskill", "skill", "coreskill"),
    "secondary_skill": ("secondaryskill", "secondary", "backupskill", "otherskill"),
    "assigned_work": ("assignedwork", "work", "task", "assignment", "assignedtask",
                      "currentwork", "workload", "responsibilities"),
}


@dataclass
class Employee:
    company_id: str = ""
    employee_id: str = ""
    name: str = ""
    email: str = ""
    department: str = ""
    primary_skill: str = ""
    secondary_skill: str = ""
    assigned_work: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "company_id": self.company_id,
            "employee_id": self.employee_id,
            "name": self.name,
            "email": self.email,
            "department": self.department,
            "primary_skill": self.primary_skill,
            "secondary_skill": self.secondary_skill,
            "assigned_work": self.assigned_work,
            **({"extra": self.extra} if self.extra else {}),
        }

    def summary_line(self) -> str:
        """A compact one-line description for a prompt (no secrets)."""
        skills = "/".join(s for s in (self.primary_skill, self.secondary_skill) if s)
        parts = [
            self.employee_id or "?",
            self.name or "?",
            f"dept={self.department}" if self.department else "",
            f"skills={skills}" if skills else "",
            f"email={self.email}" if self.email else "",
            f"work={self.assigned_work}" if self.assigned_work else "",
        ]
        return " | ".join(p for p in parts if p)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _match_score(header_tok: str, aliases: tuple[str, ...]) -> int:
    """Score how well a normalized header token matches a field's aliases.

    Higher is better. 0 means no match. Exact matches beat substring matches so
    that e.g. "workemail" binds to email (exact alias) rather than assigned_work
    (whose "work" alias is only a substring).
    """
    if not header_tok:
        return 0
    best = 0
    for a in aliases:
        if not a:
            continue
        if header_tok == a:
            best = max(best, 100 + len(a))  # exact alias wins
        elif header_tok.startswith(a) or header_tok.endswith(a):
            best = max(best, 40 + len(a))   # prefix/suffix is a strong signal
        elif a in header_tok or header_tok in a:
            best = max(best, 10 + len(a))   # weak substring containment
    return best


def _build_field_map(header: list[str]) -> dict[str, int]:
    """Map canonical field -> column index using tolerant header matching.

    Builds every (field, column) candidate with a score, then assigns greedily
    from strongest to weakest so each column and field is used at most once.
    This avoids greedy collisions (e.g. "Work Email" being claimed by
    Assigned Work before Email gets a chance).
    """
    norm_header = [_norm(h) for h in header]
    candidates: list[tuple[int, str, int]] = []  # (score, field, col_idx)
    for field_name, aliases in _FIELD_ALIASES.items():
        for idx, h in enumerate(norm_header):
            score = _match_score(h, aliases)
            if score > 0:
                candidates.append((score, field_name, idx))

    candidates.sort(key=lambda c: c[0], reverse=True)
    field_map: dict[str, int] = {}
    used_cols: set[int] = set()
    for _score, field_name, idx in candidates:
        if field_name in field_map or idx in used_cols:
            continue
        field_map[field_name] = idx
        used_cols.add(idx)
    return field_map


class RosterError(Exception):
    """The roster spreadsheet could not be read or has no usable rows."""


def read_roster(path: str | Path) -> list[Employee]:
    """Read the employee roster from the first sheet of an .xlsx file.

    Raises RosterError if the file is missing/unreadable or has no data rows.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise RosterError(f"roster file not found: {p}")
    if p.suffix.lower() != ".xlsx":
        raise RosterError(f"roster must be an .xlsx file (got {p.suffix!r})")

    try:
        wb = SpreadsheetAdapter(p)
    except DocumentError as exc:
        raise RosterError(str(exc)) from exc

    names = wb.sheet_names()
    if not names:
        raise RosterError("workbook has no sheets")
    sheet = names[0]

    header = wb.header(sheet)
    field_map = _build_field_map(header)
    data_rows = wb.rows(sheet, skip_header=True)

    employees: list[Employee] = []
    for row in data_rows:
        def get(field_name: str) -> str:
            idx = field_map.get(field_name)
            if idx is None or idx >= len(row) or row[idx] is None:
                return ""
            return str(row[idx]).strip()

        emp = Employee(
            company_id=get("company_id"),
            employee_id=get("employee_id"),
            name=get("name"),
            email=get("email"),
            department=get("department"),
            primary_skill=get("primary_skill"),
            secondary_skill=get("secondary_skill"),
            assigned_work=get("assigned_work"),
        )
        # Keep any unmapped columns for transparency (never dropped silently).
        mapped_idxs = set(field_map.values())
        for idx, h in enumerate(header):
            if idx not in mapped_idxs and idx < len(row) and row[idx] is not None:
                emp.extra[h or f"col{idx}"] = str(row[idx]).strip()

        # A row is usable if it has at least a name or an employee id.
        if emp.name or emp.employee_id:
            employees.append(emp)

    if not employees:
        raise RosterError("no employee rows found in the roster")
    return employees


def find_absent(employees: list[Employee], query: str) -> Employee | None:
    """Best-effort match of the absent person named in the goal text.

    Matches by employee id, exact name, or a name token. Returns None if the
    goal doesn't clearly name someone in the roster (caller can then ask / pick
    by lowest coverage, etc.).
    """
    q = (query or "").lower()
    # Exact employee id.
    for e in employees:
        if e.employee_id and e.employee_id.lower() in q:
            return e
    # Full name.
    for e in employees:
        if e.name and e.name.lower() in q:
            return e
    # Any name token (first/last name) of length >= 3.
    best: Employee | None = None
    for e in employees:
        for token in re.split(r"\s+", e.name.lower()):
            if len(token) >= 3 and re.search(rf"\b{re.escape(token)}\b", q):
                best = e
                break
        if best:
            break
    return best


def roster_prompt_block(employees: list[Employee], *, exclude: Employee | None = None) -> str:
    """Render the roster as compact lines for a model prompt (secret-free)."""
    lines = []
    for e in employees:
        if exclude is not None and e is exclude:
            continue
        lines.append(e.summary_line())
    return "\n".join(lines)

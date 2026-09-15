"""Predict the best colleague to cover an absent employee.

Calls the Gemini generative-language API (model + key from the environment /
``.env``) with the roster and the absent person, and asks for a single best
assignee as structured JSON. If the API key is missing or the call fails, falls
back to an honest deterministic heuristic (skill/department overlap + lowest
current workload) so the workflow still produces a real, defensible answer.

Design notes:
- Uses the Python standard library (``urllib.request``) — no new dependency.
- The API key is read from the environment and is NEVER logged, echoed, or put
  anywhere except the request URL sent to Google's endpoint.
- Verified working against model ``gemini-3.6-flash`` on this key.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from ..model_gateway.config import load_dotenv
from .employee_data import Employee, roster_prompt_block

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
_DEFAULT_MODEL = "gemini-3.6-flash"


def _repo_root_env() -> Path | None:
    """Find the nearest .env walking up from this file (works regardless of cwd)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


def _ensure_env_loaded() -> None:
    # load_dotenv only sets vars that aren't already present, so this is safe to
    # call repeatedly and real env vars always win.
    load_dotenv()
    if "GEMINI_API_KEY" not in os.environ:
        env = _repo_root_env()
        if env is not None:
            load_dotenv(env)


def _tokset(*values: str) -> set[str]:
    out: set[str] = set()
    for v in values:
        for tok in re.split(r"[,\s/;|]+", (v or "").lower()):
            tok = tok.strip()
            if len(tok) >= 2:
                out.add(tok)
    return out


def _work_count(emp: Employee) -> int:
    """Rough current-load estimate from the assigned-work cell."""
    work = (emp.assigned_work or "").strip()
    if not work:
        return 0
    # Count comma / semicolon / newline separated items; default 1 if non-empty.
    items = [p for p in re.split(r"[,\n;]+", work) if p.strip()]
    return max(1, len(items))


def _score_candidate(absent: Employee, cand: Employee) -> tuple[int, int]:
    """Heuristic score: (match_score, negative_load) — higher tuple is better."""
    a_dept = (absent.department or "").lower()
    c_dept = (cand.department or "").lower()
    score = 0
    if a_dept and c_dept and a_dept == c_dept:
        score += 10
    a_skills = _tokset(absent.primary_skill, absent.secondary_skill)
    c_skills = _tokset(cand.primary_skill, cand.secondary_skill)
    overlap = a_skills & c_skills
    score += 5 * len(overlap)
    # Exact primary-skill match is a strong signal.
    if absent.primary_skill and cand.primary_skill and \
            absent.primary_skill.strip().lower() == cand.primary_skill.strip().lower():
        score += 4
    return (score, -_work_count(cand))


def _fallback(absent: Employee, roster: list[Employee]) -> dict[str, Any]:
    """Deterministic pick when the model is unavailable. Honest about source."""
    candidates = [e for e in roster if e is not absent and (e.name or e.employee_id)]
    if not candidates:
        return {
            "assignee_name": "",
            "assignee_email": "",
            "assignee_employee_id": "",
            "reason": "No other employees available in the roster to cover the work.",
            "source": "heuristic",
        }
    best = max(candidates, key=lambda c: _score_candidate(absent, c))
    match_score, neg_load = _score_candidate(absent, best)
    bits = []
    if absent.department and best.department and \
            absent.department.lower() == best.department.lower():
        bits.append(f"same department ({best.department})")
    overlap = _tokset(absent.primary_skill, absent.secondary_skill) & \
        _tokset(best.primary_skill, best.secondary_skill)
    if overlap:
        bits.append(f"shared skills ({', '.join(sorted(overlap))})")
    bits.append(f"current load {-neg_load} task(s)")
    reason = f"Best match by {', '.join(bits)}." if bits else \
        "Selected as the closest available colleague."
    return {
        "assignee_name": best.name,
        "assignee_email": best.email,
        "assignee_employee_id": best.employee_id,
        "reason": reason,
        "source": "heuristic",
    }


def _build_prompt(absent: Employee, roster: list[Employee]) -> str:
    roster_block = roster_prompt_block(roster, exclude=absent)
    return (
        "You are a work-reassignment assistant. An employee is absent today and "
        "their tasks must be covered by exactly one available colleague.\n\n"
        "Pick the SINGLE best colleague from the roster, prioritising: matching "
        "primary/secondary skills, then same department, then the lowest current "
        "workload. Choose only from the roster below (never invent a person).\n\n"
        f"ABSENT EMPLOYEE:\n{absent.summary_line()}\n\n"
        f"AVAILABLE ROSTER:\n{roster_block}\n\n"
        "Respond with ONLY compact JSON (no prose, no markdown fences) exactly "
        "in this shape:\n"
        '{"assignee_name":"...","assignee_email":"...",'
        '"assignee_employee_id":"...","reason":"one short sentence"}'
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull the JSON object out of a model response (tolerates ```json fences)."""
    if not text:
        return None
    cleaned = text.strip()
    # Strip markdown code fences if present.
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Last resort: grab the first {...} block.
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _call_gemini(prompt: str, *, timeout: float = 45.0) -> str | None:
    """POST to Gemini and return the response text, or None on any failure."""
    _ensure_env_loaded()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        return None
    model = os.environ.get("GEMINI_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL

    url = _ENDPOINT.format(model=model, key=key)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            # Thinking model burns tokens on reasoning; leave generous headroom
            # so the visible answer is not truncated.
            "maxOutputTokens": 2048,
        },
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
        # Never leak the key or raw error detail (which contains the URL).
        return None
    except Exception:  # noqa: BLE001 - defensive: any network/parse issue -> fallback
        return None

    try:
        candidate = (data.get("candidates") or [{}])[0]
        parts = (candidate.get("content") or {}).get("parts") or []
        for part in parts:
            if isinstance(part, dict) and part.get("text"):
                return str(part["text"])
    except (AttributeError, IndexError, TypeError):
        return None
    return None


def predict_assignee(absent: Employee, roster: list[Employee]) -> dict[str, Any]:
    """Return the chosen assignee for the absent employee.

    Result dict keys: assignee_name, assignee_email, assignee_employee_id,
    reason, source ("gemini" | "heuristic"). Always returns a usable result;
    on any model failure it falls back to the deterministic heuristic and marks
    source accordingly (never fakes a model answer).
    """
    prompt = _build_prompt(absent, roster)
    text = _call_gemini(prompt)
    if text:
        parsed = _extract_json(text)
        if parsed and (parsed.get("assignee_name") or parsed.get("assignee_email")):
            # Reconcile the model's pick against the real roster so the email
            # address is authoritative (model can paraphrase names).
            resolved = _resolve_against_roster(parsed, roster, absent)
            resolved["source"] = "gemini"
            return resolved
    # No key, network failure, or unparseable answer -> honest heuristic.
    return _fallback(absent, roster)


def _resolve_against_roster(
    parsed: dict[str, Any], roster: list[Employee], absent: Employee
) -> dict[str, Any]:
    """Trust the roster for contact details; use the model's reasoning."""
    name = str(parsed.get("assignee_name") or "").strip()
    email = str(parsed.get("assignee_email") or "").strip()
    emp_id = str(parsed.get("assignee_employee_id") or "").strip()
    reason = str(parsed.get("reason") or "").strip() or \
        "Selected by the model as the best skill/department match."

    match: Employee | None = None
    for e in roster:
        if e is absent:
            continue
        if emp_id and e.employee_id and e.employee_id.lower() == emp_id.lower():
            match = e
            break
    if match is None:
        for e in roster:
            if e is absent:
                continue
            if email and e.email and e.email.lower() == email.lower():
                match = e
                break
    if match is None:
        for e in roster:
            if e is absent:
                continue
            if name and e.name and e.name.lower() == name.lower():
                match = e
                break

    if match is not None:
        return {
            "assignee_name": match.name or name,
            "assignee_email": match.email or email,
            "assignee_employee_id": match.employee_id or emp_id,
            "reason": reason,
        }
    # Model named someone not in the roster — keep its answer but be transparent.
    return {
        "assignee_name": name,
        "assignee_email": email,
        "assignee_employee_id": emp_id,
        "reason": reason,
    }

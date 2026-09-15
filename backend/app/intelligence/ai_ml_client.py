"""Async HTTP client for the AI/ML runtime server (out-of-process, :8770).

Thin transport over the AI/ML mission API. All network faults are translated
into a single `AiMlUnavailable` error so the adapter can map them to controlled
control-plane states (never a fake success).

AI/ML server surface (ai-ml/src/autoflow_ai/server/app.py):
  POST /missions                 -> {mission_id, status:"created", ...}
  POST /missions/{id}/simulate   -> {ok, status:"running"}   (deterministic society run)
  POST /missions/{id}/run        -> {ok, status:"running", mode:"real"} (needs target_path)
  GET  /missions/{id}            -> record {status, result, ...}
  GET  /missions/{id}/trace      -> {events:[...]}   (all events, JSON, no SSE needed)
  GET  /missions/{id}/artifacts  -> {artifacts:[...]}
  GET  /health                   -> subsystem health
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("ai_ml_client")


class AiMlUnavailable(Exception):
    """The AI/ML runtime could not be reached or returned an invalid response."""


class AiMlClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url or settings.ai_ml_url).rstrip("/")
        self.timeout = timeout or settings.ai_ml_timeout_seconds

    async def _request(self, method: str, path: str, *, json: dict | None = None) -> Any:
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.request(method, url, json=json)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise AiMlUnavailable(f"AI/ML runtime unreachable at {self.base_url}") from exc
        except httpx.TimeoutException as exc:
            raise AiMlUnavailable(f"AI/ML runtime timed out after {self.timeout}s") from exc
        except httpx.HTTPError as exc:  # noqa: BLE001
            raise AiMlUnavailable(f"AI/ML runtime transport error: {exc}") from exc

        if res.status_code >= 500:
            raise AiMlUnavailable(f"AI/ML runtime error {res.status_code}")
        try:
            return res.json()
        except ValueError as exc:
            raise AiMlUnavailable("AI/ML runtime returned a non-JSON response") from exc

    async def health(self) -> dict:
        return await self._request("GET", "/health")

    async def ping(self) -> bool:
        try:
            await self._request("GET", "/missions")
            return True
        except AiMlUnavailable:
            return False

    async def create_mission(
        self, prompt: str, *, mode: str = "simulation", model: str = "auto",
        target_path: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {"prompt": prompt, "mode": mode, "model": model}
        if target_path:
            body["target_path"] = target_path
        rec = await self._request("POST", "/missions", json=body)
        if not isinstance(rec, dict) or "mission_id" not in rec:
            raise AiMlUnavailable("AI/ML create_mission returned an invalid record")
        return rec

    async def simulate(self, mission_id: str, *, await_approval: bool = False) -> dict:
        return await self._request(
            "POST", f"/missions/{mission_id}/simulate",
            json={"await_approval": await_approval},
        )

    async def run_real(
        self, mission_id: str, *, target_path: str, use_model: bool = False
    ) -> dict:
        return await self._request(
            "POST", f"/missions/{mission_id}/run",
            json={"target_path": target_path, "use_model": use_model},
        )

    async def get_mission(self, mission_id: str) -> dict:
        return await self._request("GET", f"/missions/{mission_id}")

    async def get_trace(self, mission_id: str) -> list[dict]:
        data = await self._request("GET", f"/missions/{mission_id}/trace")
        return data.get("events", []) if isinstance(data, dict) else []

    async def get_artifacts(self, mission_id: str) -> list[dict]:
        data = await self._request("GET", f"/missions/{mission_id}/artifacts")
        return data.get("artifacts", []) if isinstance(data, dict) else []

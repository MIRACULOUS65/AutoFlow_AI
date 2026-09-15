"""AutoFlow local orchestration API (Python stdlib http.server, no deps).

Routes (localhost only):
  GET  /                         -> frontend (single page)
  GET  /health                   -> subsystem health (reuses lab providers)
  GET  /capabilities             -> provider capabilities (real, not config-exists)
  GET  /models                   -> configured models
  POST /models/{id}/test         -> run one benchmark task against a model
  GET  /missions                 -> list missions
  POST /missions                 -> create a mission {prompt, mode, model}
  POST /missions/{id}/simulate   -> run deterministic simulation (async)
  GET  /missions/{id}            -> mission state
  GET  /missions/{id}/events     -> SSE stream of canonical events (?after=<id>)
  GET  /missions/{id}/trace      -> full event list (JSON)
  GET  /missions/{id}/artifacts  -> artifacts

The frontend never touches agent classes; it only speaks HTTP to this API.
"""

from __future__ import annotations

import json
import re
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .events import EventType
from .missions import MissionRegistry
from .frontend import INDEX_HTML

_MAX_BODY = 256 * 1024  # 256 KB payload limit


class AutoFlowServer:
    """Holds shared state (mission registry) for the request handlers."""

    def __init__(self) -> None:
        self.registry = MissionRegistry()


def _make_handler(server_state: AutoFlowServer):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        # -- helpers -----------------------------------------------------
        def _json(self, obj, status=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.end_headers()
            self.wfile.write(body)

        # -- CORS preflight ----------------------------------------------
        def do_OPTIONS(self):
            # Browsers send a preflight OPTIONS before a cross-origin JSON POST
            # (e.g. the desktop uploading a roster to /upload). Answer it with
            # permissive CORS headers so the real request is allowed through.
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
            self.send_header("Access-Control-Max-Age", "86400")
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _html(self, text, status=200):
            body = text.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length <= 0:
                return {}
            if length > _MAX_BODY:
                # drain the incoming body so the socket stays consistent, then
                # signal oversize; the caller responds 400 + closes.
                remaining = length
                while remaining > 0:
                    got = self.rfile.read(min(65536, remaining))
                    if not got:
                        break
                    remaining -= len(got)
                self.close_connection = True
                raise ValueError("payload too large")
            raw = self.rfile.read(length)
            try:
                obj = json.loads(raw.decode("utf-8"))
                return obj if isinstance(obj, dict) else {}
            except Exception:
                raise ValueError("invalid JSON body")

        def _handle_upload(self):
            """Save an uploaded file to a temp dir and return its absolute path.

            Body: JSON {"filename": "...", "content_b64": "..."}. Used by the
            desktop attachment button so the AI/ML side (which reads the file
            locally) gets a real on-disk path for the roster. Confined to a
            dedicated temp directory; only a safe basename is honoured.
            """
            import base64
            import os
            import tempfile
            from pathlib import Path

            length = int(self.headers.get("Content-Length", 0) or 0)
            _upload_max = 8 * 1024 * 1024  # 8 MB raw JSON (~6 MB file)
            if length <= 0:
                return self._json({"error": "empty upload"}, 400)
            if length > _upload_max:
                remaining = length
                while remaining > 0:
                    got = self.rfile.read(min(65536, remaining))
                    if not got:
                        break
                    remaining -= len(got)
                self.close_connection = True
                return self._json({"error": "file too large"}, 400)

            raw = self.rfile.read(length)
            try:
                obj = json.loads(raw.decode("utf-8"))
            except Exception:  # noqa: BLE001
                return self._json({"error": "invalid JSON body"}, 400)

            filename = str(obj.get("filename") or "upload.bin")
            content_b64 = obj.get("content_b64") or ""
            try:
                data = base64.b64decode(content_b64, validate=True)
            except Exception:  # noqa: BLE001
                return self._json({"error": "content_b64 is not valid base64"}, 400)
            if not data:
                return self._json({"error": "no file content"}, 400)

            # Only keep a safe basename + a whitelisted extension.
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", os.path.basename(filename)) or "upload.bin"
            ext = os.path.splitext(safe)[1].lower()
            if ext not in (".xlsx", ".xls", ".csv"):
                return self._json({"error": f"unsupported file type: {ext or 'none'}"}, 400)

            up_dir = Path(tempfile.gettempdir()) / "autoflow_uploads"
            up_dir.mkdir(parents=True, exist_ok=True)
            # Prefix with a short unique token to avoid collisions.
            token = base64.urlsafe_b64encode(os.urandom(6)).decode().rstrip("=")
            dest = up_dir / f"{token}_{safe}"
            dest.write_bytes(data)
            return self._json({"ok": True, "path": str(dest), "name": safe,
                               "bytes": len(data)}, 201)

        def log_message(self, *a):  # silence default logging
            return

        # -- GET ---------------------------------------------------------
        def do_GET(self):
            path = self.path.split("?", 1)[0]
            query = self.path.split("?", 1)[1] if "?" in self.path else ""

            if path == "/" or path == "/index.html":
                return self._html(INDEX_HTML)
            if path == "/health":
                return self._json(_health())
            if path == "/capabilities":
                return self._json(_capabilities())
            if path == "/models":
                return self._json({"models": _models()})
            if path == "/missions":
                return self._json({"missions": [m.as_dict() for m in server_state.registry.list()]})

            m = re.match(r"^/missions/([\w\-]+)/events$", path)
            if m:
                return self._sse(m.group(1), query)
            m = re.match(r"^/missions/([\w\-]+)/trace$", path)
            if m:
                return self._trace(m.group(1))
            m = re.match(r"^/missions/([\w\-]+)/artifacts$", path)
            if m:
                return self._artifacts(m.group(1))
            m = re.match(r"^/missions/([\w\-]+)$", path)
            if m:
                rec = server_state.registry.get(m.group(1))
                return self._json(rec.as_dict()) if rec else self._json({"error": "not found"}, 404)

            return self._json({"error": "not found", "path": path}, 404)

        # -- POST --------------------------------------------------------
        def do_POST(self):
            path = self.path.split("?", 1)[0]

            # File upload (e.g. an employee roster .xlsx for the reassign-work
            # flow) uses its own larger raw reader so it is not constrained by
            # the JSON body cap used for control messages.
            if path == "/upload":
                return self._handle_upload()

            try:
                body = self._read_body()
            except ValueError as exc:
                return self._json({"error": str(exc)}, 400)

            if path == "/missions":
                prompt = (body.get("prompt") or "").strip()
                if not prompt:
                    return self._json({"error": "prompt required"}, 400)
                rec = server_state.registry.create(
                    prompt[:2000], mode=body.get("mode", "simulation"),
                    model=body.get("model", "auto"))
                target = (body.get("target_path") or "").strip()
                if target:
                    rec.target_path = target
                return self._json(rec.as_dict(), 201)

            m = re.match(r"^/missions/([\w\-]+)/run$", path)
            if m:
                rec = server_state.registry.get(m.group(1))
                if rec is None:
                    return self._json({"error": "not found"}, 404)
                target = (body.get("target_path") or getattr(rec, "target_path", "") or "").strip()
                if not target:
                    return self._json({"error": "target_path required for a real run"}, 400)
                server_state.registry.run_real_async(
                    rec, target_path=target, use_model=bool(body.get("use_model", False)))
                return self._json({"ok": True, "mission_id": rec.mission_id,
                                   "status": "running", "mode": "real"})

            m = re.match(r"^/missions/([\w\-]+)/simulate$", path)
            if m:
                rec = server_state.registry.get(m.group(1))
                if rec is None:
                    return self._json({"error": "not found"}, 404)
                # Auto-route real desktop-control goals (e.g. "write a paragraph
                # in ms word", "search youtube for X") to the REAL desktop
                # executor: generate content with the LLM, then drive Word /
                # the browser and independently verify. Everything else runs the
                # deterministic document society. Same endpoint, honest routing.
                from .desktop_mission import detect_desktop_goal

                if detect_desktop_goal(rec.prompt,
                                       roster_path=(getattr(rec, "target_path", "") or "")) is not None:
                    server_state.registry.run_desktop_async(rec, use_model=True)
                    return self._json({"ok": True, "mission_id": rec.mission_id,
                                       "status": "running", "mode": "desktop"})
                server_state.registry.run_simulation_async(
                    rec, await_approval=bool(body.get("await_approval", False)))
                return self._json({"ok": True, "mission_id": rec.mission_id, "status": "running"})

            m = re.match(r"^/missions/([\w\-]+)/desktop$", path)
            if m:
                rec = server_state.registry.get(m.group(1))
                if rec is None:
                    return self._json({"error": "not found"}, 404)
                server_state.registry.run_desktop_async(rec, use_model=True)
                return self._json({"ok": True, "mission_id": rec.mission_id,
                                   "status": "running", "mode": "desktop"})

            m = re.match(r"^/models/([\w\-]+)/test$", path)
            if m:
                return self._json(_model_test(m.group(1)))

            return self._json({"error": "not found", "path": path}, 404)

        # -- SSE ---------------------------------------------------------
        def _sse(self, mission_id, query):
            rec = server_state.registry.get(mission_id)
            if rec is None:
                return self._json({"error": "not found"}, 404)
            after = 0
            qm = re.search(r"after=(\d+)", query or "")
            if qm:
                after = int(qm.group(1))
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            # stream until the mission bus closes and all events are drained
            deadline = time.time() + 60  # bounded stream (safety)
            try:
                while time.time() < deadline:
                    events = rec.bus.since(after)
                    for ev in events:
                        after = ev.event_id
                        self.wfile.write(ev.sse().encode("utf-8"))
                        self.wfile.flush()
                    if rec.bus.closed and not rec.bus.since(after):
                        self.wfile.write(b"event: end\ndata: {}\n\n")
                        self.wfile.flush()
                        break
                    time.sleep(0.1)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def _trace(self, mission_id):
            rec = server_state.registry.get(mission_id)
            if rec is None:
                return self._json({"error": "not found"}, 404)
            return self._json({"mission_id": mission_id, "status": rec.status,
                               "events": [e.as_dict() for e in rec.bus.all()]})

        def _artifacts(self, mission_id):
            rec = server_state.registry.get(mission_id)
            if rec is None:
                return self._json({"error": "not found"}, 404)
            arts = [e.as_dict() for e in rec.bus.all() if e.type == EventType.ARTIFACT_CREATED]
            return self._json({"mission_id": mission_id, "artifacts": arts})

    return Handler


# ---------------------------------------------------------------------------
# subsystem-backed data (reuse the real runtime; never fake)
# ---------------------------------------------------------------------------


def _models() -> list[dict]:
    try:
        from ..lab import ModelLab

        return [
            {"model_id": p.model_id, "provider": p.provider, "model": p.provider_model_name,
             "roles": list(p.roles), "healthy": p.healthy, "local": p.is_local}
            for p in ModelLab().providers()
        ]
    except Exception as exc:  # noqa: BLE001
        return [{"error": type(exc).__name__}]


def _capabilities() -> dict:
    try:
        from ..lab import ModelLab

        caps = {}
        lab = ModelLab()
        for p in lab.providers():
            caps[p.model_id] = {"provider": p.provider, "available": p.healthy,
                                "local": p.is_local, "roles": list(p.roles)}
        return {"providers": caps}
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__}


def _health() -> dict:
    from ..cli import cmd_health  # reuse the CLI health probe
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_health(None)  # type: ignore[arg-type]
    try:
        return json.loads(buf.getvalue())
    except Exception:  # noqa: BLE001
        return {"status": "unknown"}


def _model_test(model_id: str) -> dict:
    try:
        from ..lab import DEFAULT_BENCHMARK, ModelLab

        lab = ModelLab()
        known = {p.model_id for p in lab.providers()}
        if model_id not in known:
            return {"error": f"unknown model: {model_id}"}
        r = lab.run_task(DEFAULT_BENCHMARK[0], model_id=model_id)
        return {"model_id": model_id, "ok": r.ok, "schema_valid": r.schema_valid,
                "latency_ms": r.latency_ms, "error": r.error, "trace": r.trace}
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__}


def build_server(*, host: str = "127.0.0.1", port: int = 8770) -> ThreadingHTTPServer:
    state = AutoFlowServer()
    httpd = ThreadingHTTPServer((host, port), _make_handler(state))
    httpd.autoflow_state = state  # type: ignore[attr-defined]
    return httpd


def run_server(*, host: str = "127.0.0.1", port: int = 8770) -> None:  # pragma: no cover
    httpd = build_server(host=host, port=port)
    print(f"AutoFlow API on http://{host}:{port}  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()

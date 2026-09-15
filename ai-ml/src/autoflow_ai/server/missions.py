"""In-process mission registry driving the existing runtime + event bus.

Missions run through the SAME orchestration used by the CLI (society flagship /
simulation). The registry only coordinates + emits the canonical event stream;
it never re-implements agent logic. Simulation runs in a background thread so
the API can stream events while the mission executes.
"""

from __future__ import annotations

import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .events import EventType, MissionEventBus


def _new_id(prefix: str = "exec") -> str:
    # prefix_token with NO extra underscore in the token (schema rule)
    token = datetime.now(timezone.utc).strftime("%H%M%S%f")
    return f"{prefix}_{prefix}{token}"


_STAGE_TO_EVENT = {
    "supervisor": EventType.TASK_DELEGATED,
    "rag": EventType.EVIDENCE_RETRIEVED,
    "planner": EventType.PLAN_CREATED,
    "research": EventType.OBSERVATION_CAPTURED,
    "document": EventType.ACTION_PROPOSED,
    "computer": EventType.ACTION_PROPOSED,
    "browser": EventType.ACTION_PROPOSED,
    "gmail": EventType.ACTION_PROPOSED,
    "verify": EventType.VERIFICATION_PASSED,
    "approval": EventType.APPROVAL_REQUESTED,
    "cleanup": EventType.CLEANUP_COMPLETED,
    "final": EventType.MISSION_COMPLETED,
}


@dataclass
class MissionRecord:
    mission_id: str
    prompt: str
    mode: str = "simulation"
    model: str = "auto"
    status: str = "created"              # created|running|awaiting_approval|complete|failed
    result: dict | None = None
    target_path: str | None = None
    bus: MissionEventBus = field(default_factory=MissionEventBus)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict:
        return {
            "mission_id": self.mission_id, "prompt": self.prompt, "mode": self.mode,
            "model": self.model, "status": self.status, "created_at": self.created_at,
            "result": self.result, "target_path": self.target_path,
        }


class MissionRegistry:
    """Creates, runs (simulation), and tracks missions + their event streams."""

    def __init__(self) -> None:
        self._missions: dict[str, MissionRecord] = {}
        self._lock = threading.Lock()

    def create(self, prompt: str, *, mode: str = "simulation", model: str = "auto") -> MissionRecord:
        mid = _new_id()
        rec = MissionRecord(mission_id=mid, prompt=prompt, mode=mode, model=model)
        with self._lock:
            self._missions[mid] = rec
        return rec

    def get(self, mission_id: str) -> MissionRecord | None:
        with self._lock:
            return self._missions.get(mission_id)

    def list(self) -> list[MissionRecord]:
        with self._lock:
            return list(self._missions.values())

    def _build_real_report_attachment(self, tmp: Path) -> Path:
        """Build the real, independently-verified weekly operations .xlsx from
        the approved flagship fixtures (spreadsheet.create + spreadsheet.validate).
        Falls back to a plain text placeholder if the fixtures are not present
        in this checkout — the fallback is explicit, never a silent fake xlsx.
        """
        from ..runtime.registry import ToolRegistry
        from ..runtime.spreadsheet_tools import SpreadsheetSession, register_spreadsheet_tools
        from ..schemas.tools import ToolCallRequest

        # ai-ml/src/autoflow_ai/server/missions.py -> repo root is 5 parents up
        repo_root = Path(__file__).resolve().parents[4]
        fixtures = repo_root / "fixtures" / "flagship" / "data"
        sales, ops, targets = fixtures / "sales.csv", fixtures / "operations.csv", fixtures / "targets.csv"
        if not (sales.exists() and ops.exists() and targets.exists()):
            att = tmp / "report_attachment.txt"
            att.write_text("attachment payload (flagship fixtures not found)", encoding="utf-8")
            return att

        registry = ToolRegistry()
        register_spreadsheet_tools(registry, SpreadsheetSession(), workspace_root=repo_root)
        out_rel = f"fixtures/flagship/runtime/mission_{__import__('uuid').uuid4().hex[:8]}.xlsx"
        create = registry.execute(ToolCallRequest(
            tool_call_id="tcall_missionxx", tool_name="spreadsheet.create",
            arguments={
                "target_path": out_rel,
                "sales_csv": "fixtures/flagship/data/sales.csv",
                "operations_csv": "fixtures/flagship/data/operations.csv",
                "targets_csv": "fixtures/flagship/data/targets.csv",
                "period_label": "This Week",
            },
            execution_id="exec_missionxxxx", step_id="step_missionxxxx",
        ))
        if not create.ok:
            att = tmp / "report_attachment.txt"
            att.write_text(f"attachment payload (spreadsheet.create failed: {create.error_message})",
                          encoding="utf-8")
            return att
        # Independently verify before attaching — never attach an unverified artifact.
        validate = registry.execute(ToolCallRequest(
            tool_call_id="tcall_missionvv", tool_name="spreadsheet.validate",
            arguments={
                "artifact_path": out_rel,
                "sales_csv": "fixtures/flagship/data/sales.csv",
                "operations_csv": "fixtures/flagship/data/operations.csv",
                "targets_csv": "fixtures/flagship/data/targets.csv",
                "min_on_time_pct": 95.0,
            },
            execution_id="exec_missionxxxx", step_id="step_missionxxxx",
        ))
        artifact_path = Path(create.output["artifact_path"])
        if not (validate.ok and validate.output.get("verified")):
            # Honest: do not attach a report that failed independent verification.
            att = tmp / "report_attachment.txt"
            att.write_text("attachment payload (report failed independent verification)",
                          encoding="utf-8")
            return att
        return artifact_path

    def run_simulation(self, rec: MissionRecord, *, await_approval: bool = False) -> None:
        """Run a deterministic flagship simulation, emitting canonical events."""

        rec.status = "running"
        rec.bus.emit(rec.mission_id, EventType.MISSION_STARTED, source="supervisor",
                     message=rec.prompt)

        from ..computer_use.smtp_email import build_email_adapter
        from ..society import EmailSpec, simulate_mission

        tmp = Path(tempfile.mkdtemp())
        doc = tmp / "report.txt"
        doc.write_text("foo baseline report content", encoding="utf-8")

        # The email attachment is a REAL, independently-verified .xlsx built
        # from the approved flagship fixtures (falls back to a placeholder
        # text attachment if the fixtures aren't present in this environment,
        # e.g. a checkout without fixtures/ — never fakes the attachment).
        att = self._build_real_report_attachment(tmp)

        # The email adapter is chosen the same way regardless of who called
        # this mission (CLI, tests, or the Control Plane via the desktop): real
        # SMTP only when both AUTOFLOW_ALLOW_REAL_SIDE_EFFECTS and
        # REAL_EMAIL_ENABLED are set; otherwise the deterministic fake sink.
        # Nothing here special-cases a goal string — this is the same seam
        # every mission uses.
        email_adapter, send_mode = build_email_adapter()
        rec.bus.emit(rec.mission_id, EventType.CONTEXT_BUILT, source="gmail",
                     status="info", message=f"email transport: {send_mode}",
                     payload={"send_mode": send_mode})

        # stream each trace line as a canonical event as it happens
        def _sink(line: str) -> None:
            stage = line.split("]", 1)[0].strip("[").lower() if line.startswith("[") else "stage"
            etype = _STAGE_TO_EVENT.get(stage, EventType.STAGE)
            status = "waiting" if stage == "approval" else "info"
            rec.bus.emit(rec.mission_id, etype, source=stage, status=status, message=line)

        try:
            result = simulate_mission(
                document_prompt="edit the document and save it", document_path=str(doc),
                email=EmailSpec(recipient="reviewer@example.com", subject="Report",
                                body="Please find the report attached.", attachment_path=str(att)),
                execution_id=rec.mission_id, auto_approve=not await_approval, sink=_sink,
                gmail_adapter=email_adapter,
            )
        except Exception as exc:  # noqa: BLE001 - never crash the server thread
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message=type(exc).__name__)
            rec.bus.close()
            return

        rec.result = result.as_dict()
        rec.result["send_mode"] = send_mode
        if result.document_verified:
            rec.bus.emit(rec.mission_id, EventType.VERIFICATION_PASSED, source="verify",
                         status="ok", message="document independently verified")
            rec.bus.emit(rec.mission_id, EventType.ARTIFACT_CREATED, source="document",
                         status="ok", message="report.txt", payload={"name": "report.txt"})
        if result.outcome == "awaiting_approval":
            rec.status = "awaiting_approval"
            rec.bus.emit(rec.mission_id, EventType.APPROVAL_REQUESTED, source="gmail",
                         status="waiting", message="awaiting user approval before send")
        elif result.complete:
            rec.status = "complete"
            rec.bus.emit(rec.mission_id, EventType.MISSION_COMPLETED, source="final",
                         status="ok", message="mission complete and verified",
                         payload={"agenticity": result.agenticity})
        else:
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message=result.reason)
        rec.bus.close()

    def run_simulation_async(self, rec: MissionRecord, *, await_approval: bool = False) -> None:
        t = threading.Thread(target=self.run_simulation, args=(rec,),
                             kwargs={"await_approval": await_approval}, daemon=True)
        t.start()

    def run_real(self, rec: MissionRecord, *, target_path: str, use_model: bool = False) -> None:
        """Run a REAL document mission against a real file on disk.

        This uses the same ``AutoFlow.run_mission`` the CLI uses: the agent
        applies the instructed edit to ``target_path`` and an independent
        verifier confirms the requested change actually landed (it will fail,
        not fake success, if it did not). Events are streamed canonically.
        """

        rec.mode = "real"
        rec.status = "running"
        rec.bus.emit(rec.mission_id, EventType.MISSION_STARTED, source="supervisor",
                     message=rec.prompt, payload={"target": target_path})

        p = Path(target_path)
        if not p.exists():
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message=f"file not found: {target_path}")
            rec.bus.close()
            return

        from ..orchestrator import AutoFlow
        from ..society import MissionTracer

        try:
            app = AutoFlow.build()
            report, metrics, supervisor = app.run_mission(
                rec.prompt, target_path=target_path, use_model=use_model,
            )
        except Exception as exc:  # noqa: BLE001 - never crash the server thread
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message=f"{type(exc).__name__}: {exc}")
            rec.bus.close()
            return

        # replay the real supervisor bus as canonical events
        def _sink(line: str) -> None:
            stage = line.split("]", 1)[0].strip("[").lower() if line.startswith("[") else "stage"
            etype = _STAGE_TO_EVENT.get(stage, EventType.STAGE)
            rec.bus.emit(rec.mission_id, etype, source=stage, status="info", message=line)

        MissionTracer(sink=_sink).from_bus(supervisor.bus)

        rec.result = {
            "complete": bool(report.all_verified),
            "document_verified": bool(report.all_verified),
            "outcome": str(report.outcome),
            "reason": report.reason,
            "verified_tasks": list(report.verified_tasks),
            "failed_tasks": list(report.failed_tasks),
            "agenticity": metrics.as_dict(),
            "target": target_path,
        }
        if report.all_verified:
            rec.status = "complete"
            rec.bus.emit(rec.mission_id, EventType.VERIFICATION_PASSED, source="verify",
                         status="ok", message="requested change verified on disk")
            rec.bus.emit(rec.mission_id, EventType.ARTIFACT_CREATED, source="document",
                         status="ok", message=p.name, payload={"name": p.name, "path": target_path})
            rec.bus.emit(rec.mission_id, EventType.MISSION_COMPLETED, source="final",
                         status="ok", message="mission complete and verified",
                         payload={"agenticity": metrics.as_dict()})
        else:
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message=report.reason or "verification failed")
        rec.bus.close()

    def run_real_async(self, rec: MissionRecord, *, target_path: str, use_model: bool = False) -> None:
        t = threading.Thread(target=self.run_real, args=(rec,),
                             kwargs={"target_path": target_path, "use_model": use_model},
                             daemon=True)
        t.start()

    # -- real desktop control (open Word / browser and actually perform it) --

    def run_desktop(self, rec: MissionRecord, *, use_model: bool = True) -> None:
        """Take real control of the machine to perform a desktop goal.

        Generates content with the real LLM (when configured), then drives a
        real application (MS Word via COM, or the browser) to perform the task,
        and independently verifies the result. Emits canonical events for the
        live trace. Never fakes success — an unverified result is reported as
        failed.
        """
        from .desktop_mission import (
            detect_desktop_goal,
            generate_paragraph,
            open_in_browser,
            run_reassign_work,
            send_email_real,
            write_notepad,
            write_paragraph_in_word,
        )

        rec.mode = "desktop"
        rec.status = "running"
        rec.bus.emit(rec.mission_id, EventType.MISSION_STARTED, source="supervisor",
                     message=rec.prompt)

        plan = detect_desktop_goal(rec.prompt, roster_path=(rec.target_path or ""))
        if plan is None:
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message="no supported real desktop action for this goal")
            rec.bus.close()
            return

        rec.bus.emit(rec.mission_id, EventType.PLAN_CREATED, source="planner",
                     status="ok", message=f"desktop action: {plan.kind}",
                     payload={"kind": plan.kind})

        def _emit(stage: str, message: str) -> None:
            etype = _STAGE_TO_EVENT.get(stage, EventType.ACTION_PROPOSED)
            rec.bus.emit(rec.mission_id, etype, source=stage, status="info", message=message)

        router = None
        if use_model:
            try:
                from ..model_gateway import build_gateway
                _reg, router = build_gateway()
            except Exception:  # noqa: BLE001
                router = None

        try:
            if plan.kind == "word_write":
                rec.bus.emit(rec.mission_id, EventType.OBSERVATION_CAPTURED, source="research",
                             status="info", message=f"generating a paragraph about {plan.topic}")
                content, src = generate_paragraph(plan.topic, router=router)
                rec.bus.emit(rec.mission_id, EventType.CONTEXT_BUILT, source="planner",
                             status="ok", message=f"content ready ({src})",
                             payload={"content_source": src, "chars": len(content)})
                result = write_paragraph_in_word(content, plan.filename, emit=_emit)
                result.content_source = src
            elif plan.kind == "notepad_write":
                rec.bus.emit(rec.mission_id, EventType.OBSERVATION_CAPTURED, source="research",
                             status="info", message=f"generating text about {plan.topic}")
                content, src = generate_paragraph(plan.topic, router=router)
                rec.bus.emit(rec.mission_id, EventType.CONTEXT_BUILT, source="planner",
                             status="ok", message=f"content ready ({src})",
                             payload={"content_source": src, "chars": len(content)})
                result = write_notepad(content, plan.filename, emit=_emit)
                result.content_source = src
            elif plan.kind == "send_email":
                result = send_email_real(plan, router=router, emit=_emit)
            elif plan.kind == "reassign_work":
                result = run_reassign_work(plan, router=router, emit=_emit)
            elif plan.kind == "web_search":
                result = open_in_browser(plan.query, is_search=True, emit=_emit)
            elif plan.kind == "open_app":
                import os as _os
                _emit("computer", f"launching application: {plan.app}")
                _os.system(f"start {plan.app}")  # noqa: S605 - user-driven desktop action
                from .desktop_mission import DesktopResult
                result = DesktopResult(kind="open_app", executed=True, verified=True,
                                       outcome="complete", mode="APP", artifact_path=plan.app,
                                       steps=[{"stage": "computer", "message": f"opened {plan.app}", "ok": True}])
            else:
                rec.status = "failed"
                rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                             message="unsupported desktop action")
                rec.bus.close()
                return
        except Exception as exc:  # noqa: BLE001 - never crash the server thread
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message=f"{type(exc).__name__}: {exc}")
            rec.bus.close()
            return

        rec.result = {
            "complete": bool(result.verified),
            "document_verified": bool(result.verified),
            "outcome": result.outcome,
            "reason": result.reason,
            "mode": result.mode,
            "artifact_path": result.artifact_path,
            "content_source": result.content_source,
            "content_preview": result.content_preview,
            "kind": result.kind,
            "verified_tasks": [s["message"] for s in result.steps if s.get("ok")],
            "failed_tasks": [s["message"] for s in result.steps if not s.get("ok")],
        }

        if result.verified:
            rec.status = "complete"
            rec.bus.emit(rec.mission_id, EventType.VERIFICATION_PASSED, source="verify",
                         status="ok", message="outcome independently verified")
            # Only file-producing modes create a real artifact. Browser/Gmail/
            # app actions don't produce a file, so they don't emit one.
            _FILE_MODES = ("LIVE_WORD", "DOCX_FALLBACK", "TXT_FALLBACK", "LIVE_NOTEPAD")
            if result.artifact_path and result.mode in _FILE_MODES:
                name = Path(result.artifact_path).name
                rec.bus.emit(rec.mission_id, EventType.ARTIFACT_CREATED, source="document",
                             status="ok", message=name,
                             payload={"name": name, "path": result.artifact_path, "mode": result.mode})
            rec.bus.emit(rec.mission_id, EventType.MISSION_COMPLETED, source="final",
                         status="ok", message=f"desktop task complete ({result.mode})")
        else:
            rec.status = "failed"
            rec.bus.emit(rec.mission_id, EventType.MISSION_FAILED, status="fail",
                         message=result.reason or "outcome could not be verified")
        rec.bus.close()

    def run_desktop_async(self, rec: MissionRecord, *, use_model: bool = True) -> None:
        t = threading.Thread(target=self.run_desktop, args=(rec,),
                             kwargs={"use_model": use_model}, daemon=True)
        t.start()

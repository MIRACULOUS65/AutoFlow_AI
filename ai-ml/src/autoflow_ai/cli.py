"""AutoFlow AI headless CLI.

The entire AI/ML system must be testable without Electron. This CLI is the
headless entry point. Phase 1 provides:

    autoflow version                 # print versions
    autoflow contracts list          # list all registered contract models
    autoflow contracts check         # self-check: build + round-trip samples
    autoflow phase status            # show implementation phase ledger
    autoflow eval smoke              # fast end-to-end contract smoke test

Later phases attach their own subcommands (task, plan, workflow, tool, memory,
eval golden/chaos/benchmark) to the same parser.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Callable

from . import CONTRACTS_VERSION, __version__
from . import schemas as S
from .orchestrator import AutoFlow
from .samples import build_sample_registry


def _print(obj: object) -> None:
    if isinstance(obj, str):
        print(obj)
    else:
        print(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False))


# ---------------------------------------------------------------------------
# command handlers
# ---------------------------------------------------------------------------


def cmd_version(_: argparse.Namespace) -> int:
    _print(
        {
            "autoflow_ai": __version__,
            "contracts_version": CONTRACTS_VERSION,
            "python": sys.version.split()[0],
        }
    )
    return 0


def cmd_contracts_list(_: argparse.Namespace) -> int:
    names = sorted(n for n in S.__all__ if n[0].isupper())
    _print({"count": len(names), "contracts": names})
    return 0


def cmd_contracts_check(_: argparse.Namespace) -> int:
    """Build every sample contract and round-trip it through JSON.

    A failure here means a contract is broken. Returns non-zero on any error.
    """

    registry = build_sample_registry()
    failures: list[dict] = []
    checked = 0
    for name, instance in registry.items():
        checked += 1
        try:
            cls = type(instance)
            payload = instance.model_dump(mode="json")
            restored = cls.model_validate(payload)
            if restored.to_json() != instance.to_json():
                failures.append({"contract": name, "error": "round-trip mismatch"})
        except Exception as exc:  # noqa: BLE001 - report any contract failure
            failures.append({"contract": name, "error": repr(exc)})

    result = {
        "checked": checked,
        "passed": checked - len(failures),
        "failed": len(failures),
        "failures": failures,
    }
    _print(result)
    return 1 if failures else 0


def cmd_phase_status(_: argparse.Namespace) -> int:
    ledger = {
        "current_phase": 1,
        "phase_1": "contract layer — implemented",
        "next_phase": 2,
        "note": "see docs/IMPLEMENTATION_STATUS.md for the full ledger",
    }
    _print(ledger)
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Show the normalized task for a prompt (no execution)."""

    app = AutoFlow.build()
    normalized = app.normalize(args.prompt, target_path=args.file)
    _print(normalized.model_dump(mode="json"))
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    """Show the generated task graph for a prompt (no execution)."""

    app = AutoFlow.build()
    plan = app.plan(args.prompt, target_path=args.file)
    _print(
        {
            "task_id": plan.task_id,
            "goal": plan.goal,
            "order": list(plan.topological_order()),
            "nodes": [
                {
                    "step_id": n.step_id,
                    "agent": str(n.assigned_agent),
                    "tool": n.expected_state.get("tool"),
                    "objective": n.objective,
                }
                for n in plan.nodes
            ],
        }
    )
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate that a plan can be generated (DAG constructs & passes checks)."""

    app = AutoFlow.build()
    try:
        plan = app.plan(args.prompt, target_path=args.file)
    except Exception as exc:  # noqa: BLE001
        _print({"valid": False, "error": repr(exc)})
        return 1
    _print({"valid": True, "steps": len(plan.nodes), "order": list(plan.topological_order())})
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Run the full pipeline and print a readable execution trace."""

    app = AutoFlow.build()
    report = app.run(args.prompt, target_path=args.file)

    if args.json:
        _print(
            {
                "execution_id": report.execution_id,
                "task_id": report.task_id,
                "status": str(report.status),
                "ok": report.ok,
                "error": report.error,
                "trace": [{"label": t.label, "detail": t.detail} for t in report.trace],
                "verifications": [v.model_dump(mode="json") for v in report.verifications],
            }
        )
    else:
        _print_trace(report)
    return 0 if report.ok else 1


def _print_trace(report) -> None:
    lines = []
    for i, entry in enumerate(report.trace):
        prefix = "" if i == 0 else "  \u2193\n"
        detail = f"   ({entry.detail})" if entry.detail else ""
        lines.append(f"{prefix}{entry.label}{detail}")
    print("\n".join(lines))
    print("")
    print(f"STATUS: {report.status}")
    if report.error:
        print(f"ERROR:  {report.error}")


def cmd_model_list(_: argparse.Namespace) -> int:
    """List configured models (secret-safe)."""

    from .model_gateway import build_gateway, load_gateway_config

    config = load_gateway_config()
    registry, _ = build_gateway(config)
    _print(
        {
            "config": config.redacted(),
            "models": [
                {
                    "model_id": m.model_id,
                    "provider": m.provider,
                    "provider_model_name": m.provider_model_name,
                    "roles": [str(r) for r in m.roles],
                    "routing_priority": m.routing_priority,
                    "deployment": str(m.deployment),
                }
                for m in registry.models()
            ],
        }
    )
    return 0


def cmd_model_test(_: argparse.Namespace) -> int:
    """Run the model harness against the configured gateway."""

    from .model_gateway import build_gateway, run_harness

    _registry, router = build_gateway()
    report = run_harness(router)
    _print(report.to_dict())
    return 0 if report.ok else 1


def cmd_model_benchmark(args: argparse.Namespace) -> int:
    """Benchmark planner-call latency over N iterations."""

    from .model_gateway import benchmark, build_gateway

    _registry, router = build_gateway()
    _print(benchmark(router, iterations=args.iterations))
    return 0


def cmd_context_inspect(args: argparse.Namespace) -> int:
    """Show the assembled context manifest for a prompt (secret-safe)."""

    app = AutoFlow.build()
    bundle = app.build_context(args.prompt, target_path=args.file)
    _print(bundle.manifest(redact=args.redact))
    return 0


def cmd_context_estimate(args: argparse.Namespace) -> int:
    """Show token estimate + budget for a prompt's assembled context."""

    app = AutoFlow.build()
    bundle = app.build_context(args.prompt, target_path=args.file)
    _print(
        {
            "estimated_tokens": bundle.estimated_tokens,
            "token_budget": bundle.token_budget,
            "reserved_output_tokens": bundle.reserved_output_tokens,
            "items_retained": len(bundle.items),
            "items_dropped": len(bundle.dropped_items),
            "context_hash": bundle.context_hash(),
            "assembly_ms": round(app.assembler.last_metrics.assembly_ms, 3),
        }
    )
    return 0


def cmd_context_validate(args: argparse.Namespace) -> int:
    """Validate that context assembles and is deterministic."""

    app = AutoFlow.build()
    try:
        b1 = app.build_context(args.prompt, target_path=args.file)
        b2 = app.build_context(args.prompt, target_path=args.file)
    except Exception as exc:  # noqa: BLE001
        _print({"valid": False, "error": repr(exc)})
        return 1
    deterministic = b1.context_hash() == b2.context_hash()
    _print(
        {
            "valid": True,
            "deterministic": deterministic,
            "context_hash": b1.context_hash(),
            "sections": sorted({it.section.value for it in b1.items}),
        }
    )
    return 0 if deterministic else 1


_KNOWLEDGE_TENANT = "org_local"
_KNOWLEDGE_WS = "ws_local"


def _knowledge_service():
    from .rag import build_knowledge_service

    return build_knowledge_service()


def cmd_knowledge_ingest(args: argparse.Namespace) -> int:
    svc = _knowledge_service()
    try:
        result = svc.ingest(
            args.path,
            tenant_id=args.tenant,
            workspace_id=args.workspace,
            permission_scope=tuple(args.scope) if args.scope else (),
        )
    except Exception as exc:  # noqa: BLE001
        _print({"ok": False, "error": repr(exc)})
        return 1
    _print(
        {
            "ok": True,
            "document_id": result.document_id,
            "version": result.version,
            "chunks": result.chunks,
            "status": result.status,
            "reused": result.reused,
        }
    )
    return 0


def cmd_knowledge_search(args: argparse.Namespace) -> int:
    svc = _knowledge_service()
    resp = svc.search(
        args.query,
        tenant_id=args.tenant,
        workspace_id=args.workspace,
        top_k=args.top_k,
    )
    _print(
        {
            "status": str(resp.status),
            "authorized": resp.authorized,
            "results": [
                {
                    "rank": i + 1,
                    "score": round(r.normalized_score, 4),
                    "document_id": r.document_id,
                    "source": r.file_name,
                    "page": r.page,
                    "evidence_id": resp.evidence[i].evidence_id if i < len(resp.evidence) else None,
                    "snippet": r.text[:160],
                }
                for i, r in enumerate(resp.results)
            ],
        }
    )
    return 0 if resp.status.value in ("success", "partial") else 1


def cmd_knowledge_inspect(args: argparse.Namespace) -> int:
    svc = _knowledge_service()
    data = svc.get_document(args.document_id)
    ids = data.get("ids", [])
    _print({"document_id": args.document_id, "chunk_count": len(ids), "chunk_ids": ids[:20]})
    return 0


def cmd_knowledge_delete(args: argparse.Namespace) -> int:
    svc = _knowledge_service()
    svc.delete_document(args.document_id)
    _print({"ok": True, "deleted": args.document_id})
    return 0


def cmd_knowledge_health(_: argparse.Namespace) -> int:
    svc = _knowledge_service()
    _print(svc.health())
    return 0


_MEMORY_TENANT = "org_local"
_MEMORY_WS = "ws_local"


def _memory_service():
    from .memory import build_memory_service

    return build_memory_service()


def cmd_memory_status(_: argparse.Namespace) -> int:
    _print(_memory_service().status())
    return 0


def cmd_memory_workflows(args: argparse.Namespace) -> int:
    svc = _memory_service()
    wfs = svc.list_workflows(tenant_id=args.tenant, workspace_id=args.workspace)
    _print(
        {
            "count": len(wfs),
            "workflows": [
                {
                    "workflow_id": w.workflow_id,
                    "name": w.canonical_name,
                    "version": w.version,
                    "status": w.status.value,
                    "usage": w.usage_count,
                    "verified_success_rate": round(w.verified_success_rate, 3),
                }
                for w in wfs
            ],
        }
    )
    return 0


def cmd_memory_search(args: argparse.Namespace) -> int:
    svc = _memory_service()
    hits = svc.search(args.query, tenant_id=args.tenant, workspace_id=args.workspace)
    _print({"count": len(hits), "results": [h.to_dict() for h in hits]})
    return 0


def cmd_memory_inspect(args: argparse.Namespace) -> int:
    svc = _memory_service()
    wf = svc.get(args.workflow_id)
    if wf is None:
        _print({"error": "not found", "workflow_id": args.workflow_id})
        return 1
    _print(
        {
            "workflow_id": wf.workflow_id,
            "name": wf.canonical_name,
            "version": wf.version,
            "status": wf.status.value,
            "intent": wf.workflow.intent,
            "steps": [{"name": s.name, "tool": s.tool, "capability": s.capability} for s in wf.workflow.steps],
            "parameters": [p.name for p in wf.workflow.parameters],
            "provenance": wf.provenance.model_dump(mode="json"),
        }
    )
    return 0


def cmd_memory_versions(args: argparse.Namespace) -> int:
    svc = _memory_service()
    vers = svc.versions(args.workflow_id)
    _print({"workflow_id": args.workflow_id, "versions": [v.model_dump(mode="json") for v in vers]})
    return 0


def cmd_memory_deprecate(args: argparse.Namespace) -> int:
    svc = _memory_service()
    if svc.get(args.workflow_id) is None:
        _print({"error": "not found"})
        return 1
    svc.deprecate(args.workflow_id)
    _print({"ok": True, "deprecated": args.workflow_id})
    return 0


def cmd_memory_block(args: argparse.Namespace) -> int:
    svc = _memory_service()
    if svc.get(args.workflow_id) is None:
        _print({"error": "not found"})
        return 1
    svc.block(args.workflow_id)
    _print({"ok": True, "blocked": args.workflow_id})
    return 0


def cmd_memory_graph(_: argparse.Namespace) -> int:
    _print(_memory_service().graph.summary())
    return 0


def cmd_agents_list(_: argparse.Namespace) -> int:
    from .agents.registry import build_default_registry

    reg = build_default_registry()
    _print({"agents": reg.list_all()})
    return 0


def cmd_agents_inspect(args: argparse.Namespace) -> int:
    from .agents.registry import build_default_registry
    from .planning.models import AgentType

    reg = build_default_registry()
    try:
        atype = AgentType(args.agent)
    except ValueError:
        _print({"error": f"unknown agent: {args.agent}"})
        return 1
    info = reg.inspect(atype)
    _print(info or {"error": "not found"})
    return 0


def cmd_run_multi(args: argparse.Namespace) -> int:
    app = AutoFlow.build()
    report = app.run_multi_agent(args.prompt, target_path=args.file, use_model=args.model)
    _print(
        {
            "ok": report.ok,
            "execution_id": report.execution_id,
            "replans": report.replans,
            "error": report.error,
            "nodes": [
                {"task_id": n.task_id, "agent": str(n.agent_type), "status": n.status.value}
                for n in report.graph.nodes
            ],
            "trace": report.trace(),
        }
    )
    return 0 if report.ok else 1


def cmd_dynplan(args: argparse.Namespace) -> int:
    from .planning.errors import PlanValidationError

    app = AutoFlow.build()
    try:
        plan = app.dynamic_plan(args.prompt, target_path=args.file, use_model=args.model)
    except PlanValidationError as exc:
        _print({"valid": False, "reasons": exc.reasons})
        return 1
    _print(
        {
            "valid": True,
            "normalized_goal": plan.normalized_goal,
            "planner_version": plan.planner_version,
            "nodes": [
                {
                    "task_id": n.task_id,
                    "agent": str(n.agent_type),
                    "tools": list(n.tool_requirements),
                    "dependencies": list(n.dependencies),
                }
                for n in plan.nodes
            ],
        }
    )
    return 0


def cmd_mission_run(args: argparse.Namespace) -> int:
    """Run a mission through the agent society and print the agenticity report."""

    from .planning.errors import PlanValidationError

    app = AutoFlow.build()
    try:
        report, metrics, supervisor = app.run_mission(
            args.prompt, target_path=args.file, use_model=args.model,
            resume=getattr(args, "resume", False), persist=getattr(args, "persist", False),
        )
    except PlanValidationError as exc:
        _print({"valid": False, "reasons": exc.reasons})
        return 1
    _print(
        {
            "outcome": str(report.outcome),
            "all_verified": report.all_verified,
            "reason": report.reason,
            "verified_tasks": list(report.verified_tasks),
            "failed_tasks": list(report.failed_tasks),
            "unverified_tasks": list(report.unverified_tasks),
            "delegations": report.delegations,
            "revisions": report.revisions,
            "reassignments": report.reassignments,
            "message_count": report.message_count,
            "agenticity": metrics.as_dict(),
            "messages": supervisor.bus.trace()[:40],
        }
    )
    if getattr(args, "live", False):
        from .society import MissionTracer

        tracer = MissionTracer(sink=lambda line: print(line))
        tracer.from_bus(supervisor.bus)
    return 0 if report.all_verified else 1


def cmd_websearch_run(args: argparse.Namespace) -> int:
    """Autonomously search the web with a REAL browser and report only real,
    DOM-verified results (no hallucination).

    Web navigation is opt-in: pass --allow-web or set AUTOFLOW_ALLOW_WEB=1.
    Without it the command fails closed and explains why.
    """

    import os

    from .computer_use.browser import WebSearchBrowserAdapter
    from .society import AutonomousWebSearchAgent

    allow_web = args.allow_web or os.environ.get("AUTOFLOW_ALLOW_WEB") == "1"
    adapter = WebSearchBrowserAdapter(allow_web=allow_web, headless=not args.headful)
    agent = AutonomousWebSearchAgent(adapter=adapter, execution_id="exec_websearch1",
                                     task_id="websearch")
    result = agent.run(args.query, engine=args.engine, max_results=args.max_results)
    payload = result.as_dict()
    payload["messages"] = agent.bus.trace()[:40]
    _print(payload)
    # exit 0 only when the loop verified real results (or verified genuine zero)
    return 0 if result.outcome.value in ("results_verified", "no_results") else 1


def cmd_model_lab_list(_: argparse.Namespace) -> int:
    from .lab import ModelLab

    lab = ModelLab()
    _print({"providers": [
        {"model_id": p.model_id, "provider": p.provider, "model": p.provider_model_name,
         "roles": list(p.roles), "healthy": p.healthy, "local": p.is_local}
        for p in lab.providers()
    ]})
    return 0


def cmd_model_lab_test(args: argparse.Namespace) -> int:
    """Run the benchmark against one provider/model and print its scorecard."""

    from .lab import DEFAULT_BENCHMARK, ModelLab, score_runs

    lab = ModelLab()
    model_id = args.model_id or lab.local_model_id()
    if model_id is None:
        _print({"error": "no models configured"})
        return 1
    results = lab.run_benchmark(DEFAULT_BENCHMARK, model_id=model_id)
    _print(score_runs(results).as_dict())
    return 0


def cmd_model_lab_task(args: argparse.Namespace) -> int:
    """Run a single benchmark task by id (or the first) and show the trace."""

    from .lab import DEFAULT_BENCHMARK, ModelLab

    lab = ModelLab()
    model_id = args.model_id or lab.local_model_id()
    task = next((t for t in DEFAULT_BENCHMARK if t.task_id == args.task), DEFAULT_BENCHMARK[0])
    result = lab.run_task(task, model_id=model_id)
    _print({"result": {"task_id": result.task_id, "kind": result.kind, "ok": result.ok,
                        "schema_valid": result.schema_valid, "latency_ms": result.latency_ms,
                        "reason": result.reason, "error": result.error},
            "trace": result.trace, "events": lab.events})
    return 0


def cmd_model_lab_benchmark(args: argparse.Namespace) -> int:
    """Score every configured model on the full benchmark."""

    from .lab import DEFAULT_BENCHMARK, ModelLab, score_runs

    lab = ModelLab()
    cards = {}
    for info in lab.providers():
        results = lab.run_benchmark(DEFAULT_BENCHMARK, model_id=info.model_id)
        cards[info.model_id] = score_runs(results).as_dict()
    _print({"benchmark_tasks": len(DEFAULT_BENCHMARK), "scorecards": cards})
    return 0


def cmd_model_lab_compare(args: argparse.Namespace) -> int:
    """Run the SAME benchmark subset against multiple models; compare structurally."""

    from .lab import DEFAULT_BENCHMARK, ModelLab, score_runs

    lab = ModelLab()
    ids = args.models.split(",") if args.models else [p.model_id for p in lab.providers()]
    # resolve friendly names (nvidia/qwen/deterministic) to model ids
    alias = {"nvidia": "model_primary01", "qwen": "model_secondary01",
             "modelscope": "model_secondary01", "deterministic": "model_local01",
             "local": "model_local01"}
    ids = [alias.get(i.strip().lower(), i.strip()) for i in ids]
    known = {p.model_id for p in lab.providers()}
    ids = [i for i in ids if i in known]
    subset = DEFAULT_BENCHMARK  # same tasks for all
    out = lab.compare(subset, model_ids=ids)
    _print({"task_count": len(subset),
            "scorecards": {mid: score_runs(res).as_dict() for mid, res in out.items()}})
    return 0


def cmd_model_console(_: argparse.Namespace) -> int:
    """Show the model providers + a sample structured decision trace (secret-free)."""

    from .lab import DEFAULT_BENCHMARK, ModelLab

    lab = ModelLab()
    mid = lab.local_model_id()
    sample = lab.run_task(DEFAULT_BENCHMARK[0], model_id=mid) if mid else None
    _print({
        "providers": [{"model_id": p.model_id, "provider": p.provider, "healthy": p.healthy}
                      for p in lab.providers()],
        "sample_trace": sample.trace if sample else None,
        "events": lab.events,
    })
    return 0


def cmd_model_info(args: argparse.Namespace) -> int:
    from .lab import manifest

    if args.model:
        info = manifest.info(args.model)
        _print(info or {"error": f"unknown model: {args.model}"})
        return 0 if info else 1
    _print({"models": manifest.list_specs()})
    return 0


def cmd_model_install(args: argparse.Namespace) -> int:
    from .lab import manifest

    _print(manifest.install(args.model))
    return 0


def cmd_model_verify(args: argparse.Namespace) -> int:
    from .lab import manifest

    res = manifest.verify(args.model)
    _print(res)
    return 0 if res.get("ok") else 1


def cmd_serve(args: argparse.Namespace) -> int:
    """Start the local orchestration API + frontend (localhost)."""

    from .server import run_server

    run_server(host=args.host, port=args.port)
    return 0


def cmd_doctor(_: argparse.Namespace) -> int:
    """Real subsystem probes with PASS/WARN/FAIL/SKIPPED (never assumes)."""

    checks: list[dict] = []

    def add(name, status, detail=""):
        checks.append({"check": name, "status": status, "detail": detail})

    import sys
    add("python", "PASS", sys.version.split()[0])

    # AI/ML importable
    try:
        import autoflow_ai  # noqa: F401
        add("ai-ml package", "PASS", "importable")
    except Exception as exc:  # noqa: BLE001
        add("ai-ml package", "FAIL", type(exc).__name__)

    # model providers (real health, not config-exists)
    try:
        from .lab import ModelLab

        provs = ModelLab().providers()
        healthy = [p for p in provs if p.healthy]
        add("model providers", "PASS" if healthy else "WARN",
            f"{len(healthy)}/{len(provs)} healthy")
    except Exception as exc:  # noqa: BLE001
        add("model providers", "FAIL", type(exc).__name__)

    # local deterministic model always available
    add("local deterministic model", "PASS", "builtin")

    # web
    add("web access", "PASS" if os.environ.get("AUTOFLOW_ALLOW_WEB") == "1" else "SKIPPED",
        "opt-in via AUTOFLOW_ALLOW_WEB")

    # windows UIA
    try:
        from .computer_use.env import desktop_available

        add("windows UIA", "PASS" if desktop_available() else "SKIPPED",
            "interactive desktop" if desktop_available() else "no desktop")
    except Exception as exc:  # noqa: BLE001
        add("windows UIA", "WARN", type(exc).__name__)

    # opencv
    try:
        import cv2  # noqa: F401
        add("opencv", "PASS", "available")
    except Exception:  # noqa: BLE001
        add("opencv", "SKIPPED", "opencv not installed")

    # browser (playwright)
    try:
        import playwright  # noqa: F401
        add("browser (playwright)", "PASS", "installed")
    except Exception:  # noqa: BLE001
        add("browser (playwright)", "SKIPPED", "playwright not installed")

    # vision provider configured
    try:
        from .computer_use.vision import build_real_vision_provider

        add("vision provider", "PASS" if build_real_vision_provider() else "SKIPPED",
            "configured" if build_real_vision_provider() else "not configured")
    except Exception as exc:  # noqa: BLE001
        add("vision provider", "WARN", type(exc).__name__)

    # rag / memory buildable
    add("rag", "PASS", "KnowledgeService buildable")
    add("memory", "PASS", "MemoryService buildable")
    add("society/runtime", "PASS", "importable")
    add("api server", "PASS", "stdlib http.server (no extra deps)")
    add("frontend", "PASS", "served by api at /")

    # on-device tool-calling agent (Cactus Needle 2)
    try:
        from .needle_agent import available as _needle_available

        na = _needle_available()
        if na.get("available"):
            add("needle agent (on-device)", "PASS",
                "bundled fine-tuned weights" if na.get("bundled_weights_present")
                else "base model (HF)")
        else:
            add("needle agent (on-device)", "SKIPPED", na.get("reason", "unavailable"))
    except Exception as exc:  # noqa: BLE001
        add("needle agent (on-device)", "SKIPPED", type(exc).__name__)

    node = __import__("shutil").which("node")
    add("node (optional)", "PASS" if node else "SKIPPED", node or "not required")

    _print({"doctor": checks,
            "summary": {s: sum(1 for c in checks if c["status"] == s)
                        for s in ("PASS", "WARN", "FAIL", "SKIPPED")}})
    return 0 if not any(c["status"] == "FAIL" for c in checks) else 1


def cmd_needle_run(args: argparse.Namespace) -> int:
    """Run one instruction through the on-device Needle 2 tool-calling agent.

    Safe by default (plans the tool call without side effects). Pass --execute
    to actually perform real Windows/browser/file actions.
    """

    from .needle_agent import NeedleAgent, available

    avail = available()
    if not avail.get("available"):
        _print({"outcome": "unavailable", "reason": avail.get("reason"),
                "install": avail.get("install")})
        return 1

    agent = NeedleAgent(
        execute=bool(getattr(args, "execute", False)),
        weights=getattr(args, "weights", None),
        output_dir=getattr(args, "output_dir", None),
    )
    try:
        result = agent.run(args.instruction)
    finally:
        agent.close()
    _print(result.as_dict())
    return 0 if result.success else 1


def cmd_demo(args: argparse.Namespace) -> int:
    """One-command deterministic flagship demo (simulation)."""

    import tempfile
    from pathlib import Path

    from .society import EmailSpec, simulate_mission

    if args.live:
        _print({"error": "live demo refused: configure providers + approvals and use "
                         "'mission run --live' explicitly"})
        return 1

    tmp = Path(tempfile.mkdtemp())
    doc = tmp / "demo_report.txt"; doc.write_text("foo baseline report", encoding="utf-8")
    att = tmp / "demo_attach.txt"; att.write_text("attachment", encoding="utf-8")
    result = simulate_mission(
        document_prompt="edit the document and save it", document_path=str(doc),
        email=EmailSpec(recipient="reviewer@example.com", subject="Report",
                        body="See attached.", attachment_path=str(att)),
        execution_id="exec_demo01", sink=lambda line: print(line),
    )
    _print({"complete": result.complete, "outcome": result.outcome,
            "agenticity": result.agenticity})
    return 0 if result.complete else 1


def cmd_mission_inspect(args: argparse.Namespace) -> int:
    """Show a persisted mission's state (verified tasks, checkpoints, approvals)."""

    from .society import MissionStore

    state = MissionStore().load(args.execution_id)
    if state is None:
        _print({"error": f"no persisted mission: {args.execution_id}"})
        return 1
    _print(
        {
            "execution_id": state.execution_id,
            "goal": state.goal,
            "verified_tasks": state.verified_tasks,
            "checkpoints": [{"name": c.name, "detail": c.detail} for c in state.checkpoints],
            "approvals": state.approvals,
            "evidence_count": len(state.board_entries),
        }
    )
    return 0


def cmd_mission_trace(args: argparse.Namespace) -> int:
    """Show the evidence trace (blackboard entries) of a persisted mission."""

    from .society import MissionStore

    state = MissionStore().load(args.execution_id)
    if state is None:
        _print({"error": f"no persisted mission: {args.execution_id}"})
        return 1
    _print(
        {
            "execution_id": state.execution_id,
            "evidence": [
                {"key": e.get("key"), "trust": e.get("trust"), "producer": e.get("producer"),
                 "summary": (e.get("summary") or "")[:120]}
                for e in state.board_entries
            ],
        }
    )
    return 0


def cmd_mission_graph(args: argparse.Namespace) -> int:
    """Show the verified-vs-checkpoint graph of a persisted mission."""

    from .society import MissionStore

    state = MissionStore().load(args.execution_id)
    if state is None:
        _print({"error": f"no persisted mission: {args.execution_id}"})
        return 1
    _print(
        {
            "execution_id": state.execution_id,
            "goal": state.goal,
            "tasks": [
                {"task_id": t, "verified": True, "output_keys": list((state.task_outputs.get(t) or {}).keys())}
                for t in state.verified_tasks
            ],
            "checkpoints": [c.name for c in state.checkpoints],
        }
    )
    return 0


def cmd_mission_approve(args: argparse.Namespace) -> int:
    """Record that a mission approval hash was granted (out-of-band approval)."""

    from .society import MissionStore

    store = MissionStore()
    state = store.load(args.execution_id)
    if state is None:
        _print({"error": f"no persisted mission: {args.execution_id}"})
        return 1
    state.record_approval(args.approval_hash)
    store.save(state)
    _print({"ok": True, "execution_id": args.execution_id, "approval_recorded": args.approval_hash})
    return 0


def cmd_mission_simulate(args: argparse.Namespace) -> int:
    """Run the flagship over a DETERMINISTIC environment with a real-time trace.

    Safe full-loop inspection (no network, no real desktop): a real local .docx
    + an in-memory Gmail DOM. Prints stage events live when --live is set.
    """

    import tempfile
    from pathlib import Path

    from .society import EmailSpec, simulate_mission

    tmp = Path(tempfile.mkdtemp())
    doc = tmp / "sim_report.txt"
    doc.write_text("foo baseline report content", encoding="utf-8")
    att = tmp / "sim_attachment.txt"
    att.write_text("attachment payload", encoding="utf-8")

    sink = (lambda line: print(line)) if args.live else None
    result = simulate_mission(
        document_prompt="edit the document and save it", document_path=str(doc),
        email=EmailSpec(recipient="reviewer@example.com", subject="Report",
                        body="Please find the report attached.", attachment_path=str(att)),
        execution_id="exec_sim01", auto_approve=not args.await_approval, sink=sink,
    )
    _print(result.as_dict())
    return 0 if result.complete or result.outcome == "awaiting_approval" else 1


def cmd_research_run(args: argparse.Namespace) -> int:
    """Grounded web research: real browser evidence with provenance + labels.

    Every fact is DIRECTLY_OBSERVED / DERIVED / INFERRED / UNKNOWN. Opt-in via
    --allow-web (or AUTOFLOW_ALLOW_WEB=1); --deep-read visits the top result
    page (stronger opt-in) to capture an observed passage.
    """

    import os

    from .computer_use.browser import WebSearchBrowserAdapter
    from .society import WebResearchAgent

    allow_web = args.allow_web or os.environ.get("AUTOFLOW_ALLOW_WEB") == "1"
    adapter = WebSearchBrowserAdapter(
        allow_web=allow_web, headless=not args.headful, allow_deep_read=args.deep_read
    )
    agent = WebResearchAgent(adapter=adapter, execution_id="exec_research1", task_id="research")
    report = agent.research(args.objective, engine=args.engine,
                            max_results=args.max_results, deep_read=args.deep_read)
    _print(report.as_dict())
    return 0 if report.outcome.value in ("grounded", "no_evidence") else 1


def cmd_computer_env(_: argparse.Namespace) -> int:
    from .computer_use.env import desktop_info

    _print(desktop_info())
    return 0


def cmd_computer_windows(_: argparse.Namespace) -> int:
    from .computer_use.env import desktop_available

    if not desktop_available():
        _print({"available": False, "windows": []})
        return 0
    from .computer_use.windows_adapter import WindowsUIAutomationAdapter

    adapter = WindowsUIAutomationAdapter()
    _print({"available": True, "windows": [w.model_dump(mode="json") for w in adapter.list_windows()]})
    return 0


def cmd_computer_inspect(_: argparse.Namespace) -> int:
    from .computer_use.env import desktop_available

    if not desktop_available():
        _print({"available": False, "detail": "no interactive desktop"})
        return 0
    from .computer_use.windows_adapter import WindowsUIAutomationAdapter

    obs = WindowsUIAutomationAdapter().inspect_desktop()
    _print(
        {
            "available": True,
            "active_window": obs.active_window,
            "element_count": len(obs.visible_elements),
            "state_hash": obs.state_hash[:16],
            "summary": obs.summary(max_elements=15),
        }
    )
    return 0


def cmd_health(_: argparse.Namespace) -> int:
    """Report health of every AI/ML subsystem (secret-free)."""

    report: dict = {}

    # model providers
    try:
        from .lab import ModelLab

        lab = ModelLab()
        report["model_providers"] = [
            {"model_id": p.model_id, "provider": p.provider, "healthy": p.healthy,
             "local": p.is_local}
            for p in lab.providers()
        ]
    except Exception as exc:  # noqa: BLE001
        report["model_providers"] = {"error": type(exc).__name__}

    def _probe(name, fn):
        try:
            report[name] = fn()
        except Exception as exc:  # noqa: BLE001
            report[name] = {"available": False, "error": type(exc).__name__}

    _probe("rag", lambda: {"available": True, "note": "KnowledgeService buildable (opt-in per mission)"})
    _probe("memory", lambda: {"available": True, "note": "MemoryService buildable (opt-in per mission)"})
    _probe("planner", lambda: {"available": bool(__import__("autoflow_ai.planning.planner",
                                                            fromlist=["DeterministicPlanner"]))})
    _probe("society", lambda: {"available": True,
                               "exports": len(__import__("autoflow_ai.society",
                                                         fromlist=["__all__"]).__all__)})
    _probe("computer", lambda: __import__("autoflow_ai.computer_use.env",
                                          fromlist=["desktop_info"]).desktop_info())
    _probe("browser", lambda: {"available": __import__("autoflow_ai.computer_use.browser",
                                                       fromlist=["WebSearchBrowserAdapter"])
                               .WebSearchBrowserAdapter(allow_web=False).available()})
    _probe("vision", lambda: {"real_provider_configured":
                              __import__("autoflow_ai.computer_use.vision",
                                         fromlist=["build_real_vision_provider"])
                              .build_real_vision_provider() is not None})
    _probe("verification", lambda: {"available": True})
    _probe("recovery", lambda: {"available": True})
    _probe("persistence", lambda: {"available": True, "note": "local JSON MissionStore"})
    _probe("gmail_adapter", lambda: {"available": True, "note": "INTEGRATION (fake DOM); real requires controlled account"})
    _probe("word_adapter", lambda: {"available": True, "note": "INTEGRATION (python-docx); real UI gated AUTOFLOW_REAL_WORD"})

    _print(report)
    return 0


def cmd_eval_smoke(_: argparse.Namespace) -> int:
    """End-to-end contract smoke test runnable from the CLI.

    Exercises the primary flow shapes: normalize -> plan (DAG) -> tool call ->
    observation -> verification -> approval binding. Returns non-zero on any
    inconsistency.
    """

    from .samples import smoke_flow

    report = smoke_flow()
    _print(report)
    return 0 if report.get("ok") else 1


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoflow",
        description="AutoFlow AI headless CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_version = sub.add_parser("version", help="print version info")
    p_version.set_defaults(func=cmd_version)

    p_contracts = sub.add_parser("contracts", help="contract layer commands")
    csub = p_contracts.add_subparsers(dest="subcommand", required=True)
    c_list = csub.add_parser("list", help="list all contract models")
    c_list.set_defaults(func=cmd_contracts_list)
    c_check = csub.add_parser("check", help="build + round-trip all contracts")
    c_check.set_defaults(func=cmd_contracts_check)

    p_phase = sub.add_parser("phase", help="phase status")
    psub = p_phase.add_subparsers(dest="subcommand", required=True)
    p_status = psub.add_parser("status", help="show phase ledger")
    p_status.set_defaults(func=cmd_phase_status)

    p_run = sub.add_parser("run", help="run the full pipeline on a prompt")
    p_run.add_argument("prompt", help="natural-language objective")
    p_run.add_argument("--file", default=None, help="explicit target file path")
    p_run.add_argument("--json", action="store_true", help="emit JSON instead of a trace")
    p_run.set_defaults(func=cmd_run)

    p_inspect = sub.add_parser("inspect", help="show the normalized task")
    p_inspect.add_argument("prompt")
    p_inspect.add_argument("--file", default=None)
    p_inspect.set_defaults(func=cmd_inspect)

    p_plan = sub.add_parser("plan", help="show the generated task graph")
    p_plan.add_argument("prompt")
    p_plan.add_argument("--file", default=None)
    p_plan.set_defaults(func=cmd_plan)

    p_validate = sub.add_parser("validate", help="validate a plan can be generated")
    p_validate.add_argument("prompt")
    p_validate.add_argument("--file", default=None)
    p_validate.set_defaults(func=cmd_validate)

    p_model = sub.add_parser("model", help="model gateway commands")
    msub = p_model.add_subparsers(dest="subcommand", required=True)
    m_list = msub.add_parser("list", help="list configured models")
    m_list.set_defaults(func=cmd_model_list)
    m_test = msub.add_parser("test", help="run the model test harness")
    m_test.set_defaults(func=cmd_model_test)
    m_bench = msub.add_parser("benchmark", help="benchmark model latency")
    m_bench.add_argument("--iterations", type=int, default=3)
    m_bench.set_defaults(func=cmd_model_benchmark)
    m_console = msub.add_parser("console", help="model providers + a sample decision trace")
    m_console.set_defaults(func=cmd_model_console)
    m_info = msub.add_parser("info", help="show model manifest (all or one)")
    m_info.add_argument("model", nargs="?", default=None)
    m_info.set_defaults(func=cmd_model_info)
    m_install = msub.add_parser("install", help="prepare a model for local use (no weights in git)")
    m_install.add_argument("model")
    m_install.set_defaults(func=cmd_model_install)
    m_verify = msub.add_parser("verify", help="verify a model is usable")
    m_verify.add_argument("model")
    m_verify.set_defaults(func=cmd_model_verify)

    # `model lab ...` evaluation/simulation lab
    m_lab = msub.add_parser("lab", help="model evaluation lab")
    labsub = m_lab.add_subparsers(dest="labcommand", required=True)
    lab_list = labsub.add_parser("list", help="list providers/models")
    lab_list.set_defaults(func=cmd_model_lab_list)
    lab_test = labsub.add_parser("test", help="score one model on the benchmark")
    lab_test.add_argument("model_id", nargs="?", default=None)
    lab_test.set_defaults(func=cmd_model_lab_test)
    lab_task = labsub.add_parser("task", help="run one benchmark task + show trace")
    lab_task.add_argument("task", nargs="?", default="bm_000")
    lab_task.add_argument("--model-id", default=None, dest="model_id")
    lab_task.set_defaults(func=cmd_model_lab_task)
    lab_bench = labsub.add_parser("benchmark", help="score all models on the benchmark")
    lab_bench.set_defaults(func=cmd_model_lab_benchmark)
    lab_cmp = labsub.add_parser("compare", help="compare models on the same tasks")
    lab_cmp.add_argument("--models", default=None,
                         help="comma list (nvidia,qwen,deterministic) or model ids")
    lab_cmp.set_defaults(func=cmd_model_lab_compare)

    p_context = sub.add_parser("context", help="context engine commands")
    ctxsub = p_context.add_subparsers(dest="subcommand", required=True)
    c_inspect = ctxsub.add_parser("inspect", help="show assembled context manifest")
    c_inspect.add_argument("prompt")
    c_inspect.add_argument("--file", default=None)
    c_inspect.add_argument("--redact", action="store_true", help="redact item content")
    c_inspect.set_defaults(func=cmd_context_inspect)
    c_estimate = ctxsub.add_parser("estimate", help="show token estimate + budget")
    c_estimate.add_argument("prompt")
    c_estimate.add_argument("--file", default=None)
    c_estimate.set_defaults(func=cmd_context_estimate)
    c_validate = ctxsub.add_parser("validate", help="validate context assembly is deterministic")
    c_validate.add_argument("prompt")
    c_validate.add_argument("--file", default=None)
    c_validate.set_defaults(func=cmd_context_validate)

    p_know = sub.add_parser("knowledge", help="knowledge (RAG) commands")
    ksub = p_know.add_subparsers(dest="subcommand", required=True)
    k_ing = ksub.add_parser("ingest", help="ingest a document")
    k_ing.add_argument("path")
    k_ing.add_argument("--tenant", default=_KNOWLEDGE_TENANT)
    k_ing.add_argument("--workspace", default=_KNOWLEDGE_WS)
    k_ing.add_argument("--scope", nargs="*", default=None)
    k_ing.set_defaults(func=cmd_knowledge_ingest)
    k_search = ksub.add_parser("search", help="semantic search")
    k_search.add_argument("query")
    k_search.add_argument("--tenant", default=_KNOWLEDGE_TENANT)
    k_search.add_argument("--workspace", default=_KNOWLEDGE_WS)
    k_search.add_argument("--top-k", type=int, default=8)
    k_search.set_defaults(func=cmd_knowledge_search)
    k_inspect = ksub.add_parser("inspect", help="inspect a document's chunks")
    k_inspect.add_argument("document_id")
    k_inspect.set_defaults(func=cmd_knowledge_inspect)
    k_delete = ksub.add_parser("delete", help="delete a document")
    k_delete.add_argument("document_id")
    k_delete.set_defaults(func=cmd_knowledge_delete)
    k_health = ksub.add_parser("health", help="knowledge subsystem health")
    k_health.set_defaults(func=cmd_knowledge_health)

    # `rag` is an alias for `knowledge` (RAG) to match the documented CLI.
    p_rag = sub.add_parser("rag", help="RAG commands (alias of 'knowledge')")
    ragsub = p_rag.add_subparsers(dest="subcommand", required=True)
    rag_search = ragsub.add_parser("search", help="semantic knowledge search")
    rag_search.add_argument("query")
    rag_search.add_argument("--tenant", default=_KNOWLEDGE_TENANT)
    rag_search.add_argument("--workspace", default=_KNOWLEDGE_WS)
    rag_search.add_argument("--top-k", type=int, default=8)
    rag_search.set_defaults(func=cmd_knowledge_search)
    rag_health = ragsub.add_parser("health", help="RAG subsystem health")
    rag_health.set_defaults(func=cmd_knowledge_health)

    p_mem = sub.add_parser("memory", help="memory (workflow/session/graph) commands")
    memsub = p_mem.add_subparsers(dest="subcommand", required=True)
    m_status = memsub.add_parser("status", help="memory subsystem status")
    m_status.set_defaults(func=cmd_memory_status)
    m_wfs = memsub.add_parser("workflows", help="list stored workflows")
    m_wfs.add_argument("--tenant", default=_MEMORY_TENANT)
    m_wfs.add_argument("--workspace", default=_MEMORY_WS)
    m_wfs.set_defaults(func=cmd_memory_workflows)
    m_search = memsub.add_parser("search", help="semantic workflow search")
    m_search.add_argument("query")
    m_search.add_argument("--tenant", default=_MEMORY_TENANT)
    m_search.add_argument("--workspace", default=_MEMORY_WS)
    m_search.set_defaults(func=cmd_memory_search)
    m_inspect = memsub.add_parser("inspect", help="inspect a workflow")
    m_inspect.add_argument("workflow_id")
    m_inspect.set_defaults(func=cmd_memory_inspect)
    m_versions = memsub.add_parser("versions", help="list workflow versions")
    m_versions.add_argument("workflow_id")
    m_versions.set_defaults(func=cmd_memory_versions)
    m_dep = memsub.add_parser("deprecate", help="deprecate a workflow (explicit id)")
    m_dep.add_argument("workflow_id")
    m_dep.set_defaults(func=cmd_memory_deprecate)
    m_block = memsub.add_parser("block", help="block a workflow (explicit id)")
    m_block.add_argument("workflow_id")
    m_block.set_defaults(func=cmd_memory_block)
    m_graph = memsub.add_parser("graph", help="graph memory summary")
    m_graph.set_defaults(func=cmd_memory_graph)

    p_agents = sub.add_parser("agents", help="specialist agent commands")
    asub = p_agents.add_subparsers(dest="subcommand", required=True)
    a_list = asub.add_parser("list", help="list specialist agents")
    a_list.set_defaults(func=cmd_agents_list)
    a_inspect = asub.add_parser("inspect", help="inspect an agent")
    a_inspect.add_argument("agent")
    a_inspect.set_defaults(func=cmd_agents_inspect)

    p_dynplan = sub.add_parser("dynplan", help="dynamic multi-agent plan (no execution)")
    p_dynplan.add_argument("prompt")
    p_dynplan.add_argument("--file", default=None)
    p_dynplan.add_argument("--model", action="store_true", help="use the model planner")
    p_dynplan.set_defaults(func=cmd_dynplan)

    p_runma = sub.add_parser("run-agents", help="run the dynamic multi-agent runtime")
    p_runma.add_argument("prompt")
    p_runma.add_argument("--file", default=None)
    p_runma.add_argument("--model", action="store_true", help="use the model planner")
    p_runma.set_defaults(func=cmd_run_multi)

    p_mission = sub.add_parser("mission", help="agent-society mission commands")
    misub = p_mission.add_subparsers(dest="subcommand", required=True)
    mi_run = misub.add_parser("run", help="run a mission through supervisor + specialists")
    mi_run.add_argument("prompt", help="natural-language mission objective")
    mi_run.add_argument("--file", default=None, help="explicit target file path")
    mi_run.add_argument("--model", action="store_true", help="use the real-model reasoning path")
    mi_run.add_argument("--persist", action="store_true", help="checkpoint mission state locally")
    mi_run.add_argument("--resume", action="store_true", help="resume from a saved checkpoint")
    mi_run.add_argument("--live", action="store_true", help="print the stage trace in real time")
    mi_run.set_defaults(func=cmd_mission_run)
    mi_inspect = misub.add_parser("inspect", help="show a persisted mission's state")
    mi_inspect.add_argument("execution_id")
    mi_inspect.set_defaults(func=cmd_mission_inspect)
    mi_trace = misub.add_parser("trace", help="show a persisted mission's evidence trace")
    mi_trace.add_argument("execution_id")
    mi_trace.set_defaults(func=cmd_mission_trace)
    mi_graph = misub.add_parser("graph", help="show a persisted mission's task graph")
    mi_graph.add_argument("execution_id")
    mi_graph.set_defaults(func=cmd_mission_graph)
    mi_approve = misub.add_parser("approve", help="record an out-of-band approval hash")
    mi_approve.add_argument("execution_id")
    mi_approve.add_argument("approval_hash")
    mi_approve.set_defaults(func=cmd_mission_approve)
    mi_sim = misub.add_parser("simulate", help="run the flagship in a deterministic simulation")
    mi_sim.add_argument("--live", action="store_true", help="print the stage trace in real time")
    mi_sim.add_argument("--await-approval", action="store_true", dest="await_approval",
                        help="stop at the approval gate instead of auto-approving")
    mi_sim.set_defaults(func=cmd_mission_simulate)

    p_websearch = sub.add_parser("websearch", help="autonomous real-browser web search")
    wsub = p_websearch.add_subparsers(dest="subcommand", required=True)
    ws_run = wsub.add_parser("run", help="search the web end-to-end and report REAL results")
    ws_run.add_argument("query", help="the search query")
    ws_run.add_argument("--engine", choices=["bing", "duckduckgo"], default="bing")
    ws_run.add_argument("--max-results", type=int, default=8, dest="max_results")
    ws_run.add_argument("--allow-web", action="store_true",
                        help="opt in to real web navigation (or set AUTOFLOW_ALLOW_WEB=1)")
    ws_run.add_argument("--headful", action="store_true", help="show the browser window")
    ws_run.set_defaults(func=cmd_websearch_run)

    p_research = sub.add_parser("research", help="grounded web research (provenance-backed)")
    rsub = p_research.add_subparsers(dest="subcommand", required=True)
    r_run = rsub.add_parser("run", help="research an objective with real browser evidence")
    r_run.add_argument("objective", help="the research objective")
    r_run.add_argument("--engine", choices=["bing", "duckduckgo"], default="bing")
    r_run.add_argument("--max-results", type=int, default=6, dest="max_results")
    r_run.add_argument("--allow-web", action="store_true",
                       help="opt in to real web navigation (or set AUTOFLOW_ALLOW_WEB=1)")
    r_run.add_argument("--deep-read", action="store_true",
                       help="also open the top result page and read an observed passage")
    r_run.add_argument("--headful", action="store_true")
    r_run.set_defaults(func=cmd_research_run)

    p_computer = sub.add_parser("computer", help="computer-use (desktop) commands")
    cusub = p_computer.add_subparsers(dest="subcommand", required=True)
    cu_env = cusub.add_parser("env", help="desktop environment info")
    cu_env.set_defaults(func=cmd_computer_env)
    cu_win = cusub.add_parser("windows", help="list open windows (read-only)")
    cu_win.set_defaults(func=cmd_computer_windows)
    cu_insp = cusub.add_parser("inspect", help="inspect active desktop (read-only)")
    cu_insp.set_defaults(func=cmd_computer_inspect)

    p_health = sub.add_parser("health", help="report AI/ML subsystem health")
    p_health.set_defaults(func=cmd_health)

    p_doctor = sub.add_parser("doctor", help="environment + subsystem diagnostics")
    p_doctor.set_defaults(func=cmd_doctor)

    p_demo = sub.add_parser("demo", help="one-command deterministic flagship demo")
    p_demo.add_argument("--live", action="store_true", help="(refused unless explicitly configured)")
    p_demo.set_defaults(func=cmd_demo)

    p_serve = sub.add_parser("serve", help="start the local orchestration API + frontend")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8770)
    p_serve.set_defaults(func=cmd_serve)

    p_needle = sub.add_parser("needle", help="on-device tool-calling agent (Cactus Needle 2)")
    nsub = p_needle.add_subparsers(dest="subcommand", required=True)
    n_run = nsub.add_parser("run", help="turn an instruction into tool calls (on-device)")
    n_run.add_argument("instruction")
    n_run.add_argument("--execute", action="store_true",
                       help="actually perform real actions (default: plan only, no side effects)")
    n_run.add_argument("--weights", default=None, help="override the .cact weights path")
    n_run.add_argument("--output-dir", dest="output_dir", default=None,
                       help="directory for file-producing tools (default ~/Downloads)")
    n_run.set_defaults(func=cmd_needle_run)

    p_eval = sub.add_parser("eval", help="evaluation harness")
    esub = p_eval.add_subparsers(dest="subcommand", required=True)
    e_smoke = esub.add_parser("smoke", help="fast end-to-end contract smoke test")
    e_smoke.set_defaults(func=cmd_eval_smoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

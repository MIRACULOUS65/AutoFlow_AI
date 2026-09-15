"""FastAPI application entrypoint.

Wires the API router, CORS, the standard error envelope, and a lifespan that
(for the SQLite dev default) creates tables and optionally runs an inline
execution worker so the whole system runs in one process with zero infra.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import API_VERSION, __version__
from app.api.v1.health import router as health_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import configure_logging, get_logger
from app.db.session import create_all, dispose_engine

log = get_logger("api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # SQLite dev convenience: ensure schema exists. Postgres uses Alembic.
    if settings.uses_sqlite:
        await create_all()

    worker_task: asyncio.Task | None = None
    stop_event: asyncio.Event | None = None
    if settings.run_inline_worker:
        from app.workers.execution_worker import run_worker

        stop_event = asyncio.Event()
        worker_task = asyncio.create_task(run_worker(stop_event))
        log.info("inline_worker.started")

    log.info("api.startup", version=__version__, env=settings.autoflow_env)
    try:
        yield
    finally:
        if stop_event is not None:
            stop_event.set()
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except (asyncio.CancelledError, Exception):
                pass
        await dispose_engine()
        log.info("api.shutdown")


app = FastAPI(
    title="AutoFlow AI — Control Plane",
    version=__version__,
    description="Authoritative, durable, API-first workflow control plane.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:16]}"
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(status_code=exc.status_code, content=exc.to_envelope(request_id))


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    # exc.errors() can embed non-JSON-serializable objects (e.g. ValueError in
    # ctx); reduce to a plain, serializable summary.
    errors = [
        {
            "loc": list(e.get("loc", [])),
            "msg": str(e.get("msg", "")),
            "type": str(e.get("type", "")),
        }
        for e in exc.errors()
    ]
    err = AppError(
        ErrorCode.VALIDATION_ERROR,
        "Request validation failed.",
        details={"errors": errors},
    )
    return JSONResponse(status_code=422, content=err.to_envelope(request_id))


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    log.error("unhandled_error", error=str(exc), path=str(request.url.path))
    err = AppError(ErrorCode.INTERNAL_ERROR, "An internal error occurred.")
    return JSONResponse(status_code=500, content=err.to_envelope(request_id))


app.include_router(health_router)
app.include_router(api_router)


@app.get("/")
async def root() -> dict:
    return {"service": "autoflow-control-plane", "version": __version__, "api": API_VERSION}

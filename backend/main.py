import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from config import get_settings
from database.db import SessionLocal, init_db
from middleware import PublicAccessMiddleware
from routers import admin, auth, chat, conversations, debug, evaluation, feedback, files, health, interventions, jobs, knowledge, multimodal, report, sessions, stt
from schemas.errors import AppError
from services.cleanup_service import cleanup_expired_files
from services.multimodal_job_worker import (
    recover_interrupted_jobs,
    start_multimodal_job_worker,
    stop_multimodal_job_worker,
)


settings = get_settings()
docs_enabled = settings.app_env == "development"


app = FastAPI(
    title="AI 心理陪伴 Web 系统",
    description="面向大学生轻中度情绪场景的 AI 心理陪伴与多模态自助调节助手。",
    version="0.3.0",
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    openapi_url="/openapi.json" if docs_enabled else None,
)

allowed_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    settings.frontend_origin,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(origin for origin in allowed_origins if origin)),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.parsed_trusted_hosts:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.parsed_trusted_hosts)
app.add_middleware(PublicAccessMiddleware)

app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(multimodal.router, prefix="/api/chat/multimodal", tags=["multimodal-chat"])
app.include_router(conversations.router, prefix="/api/conversations", tags=["conversations"])
app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(jobs.router, prefix="/api/multimodal/jobs", tags=["multimodal-jobs"])
app.include_router(stt.router, prefix="/api/stt", tags=["stt"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(interventions.router, prefix="/api/interventions", tags=["interventions"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])
app.include_router(evaluation.router, prefix="/api/evaluation", tags=["evaluation"])
app.include_router(debug.router, prefix="/api/debug", tags=["debug"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


cleanup_task: asyncio.Task | None = None


def _frontend_index() -> Path:
    return settings.resolved_frontend_dist_dir / "index.html"


def _frontend_available() -> bool:
    return settings.serve_frontend and _frontend_index().exists()


async def _cleanup_loop() -> None:
    while True:
        await asyncio.sleep(max(settings.cleanup_interval_seconds, 60))
        with SessionLocal() as db:
            cleanup_expired_files(db)


if settings.serve_frontend and (settings.resolved_frontend_dist_dir / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=settings.resolved_frontend_dist_dir / "assets"),
        name="assets",
    )


@app.on_event("startup")
async def on_startup() -> None:
    global cleanup_task
    init_db()
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        cleanup_expired_files(db)
    recover_interrupted_jobs()
    if settings.is_public_mode and settings.serve_frontend and not _frontend_index().exists():
        raise RuntimeError(
            "frontend/dist 不存在。公开演示或生产模式请先执行 scripts/build_production.ps1。"
        )
    if cleanup_task is None:
        cleanup_task = asyncio.create_task(_cleanup_loop())
    start_multimodal_job_worker()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    global cleanup_task
    if cleanup_task:
        cleanup_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cleanup_task
        cleanup_task = None
    await stop_multimodal_job_worker()


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if not exc.detail.request_id:
        exc.detail.request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail.model_dump(exclude_none=True)},
    )


@app.get("/api/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    return {"status": "ok", "database": "ok"}


@app.get("/", response_model=None)
def root() -> FileResponse | dict[str, str]:
    if _frontend_available():
        return FileResponse(_frontend_index(), headers={"Cache-Control": "no-store"})
    return {
        "service": "psych-ai-companion-backend",
        "message": "Visit /api/health to check service status.",
    }


@app.get("/{full_path:path}", include_in_schema=False, response_model=None)
def spa_fallback(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    if not _frontend_available():
        raise HTTPException(status_code=404, detail="Frontend dist not found")
    return FileResponse(_frontend_index(), headers={"Cache-Control": "no-store"})

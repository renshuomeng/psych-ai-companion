from fastapi import APIRouter

from config import get_settings
from database.db import SessionLocal, get_database_status
from database.models import MultimodalJob
from services.media_service import ffmpeg_status
from services.multimodal_job_worker import job_worker_status


router = APIRouter()


@router.get("")
@router.get("/")
def health_check() -> dict:
    settings = get_settings()
    media = ffmpeg_status()
    db_status = get_database_status()
    with SessionLocal() as db:
        active_jobs = (
            db.query(MultimodalJob)
            .filter(MultimodalJob.status.in_(["queued", "validating", "processing"]))
            .count()
        )
    upload_dir = settings.resolved_upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    return {
        "status": "ok",
        "service": "psych-ai-companion-backend",
        "dependencies": {
            "database": db_status["status"],
            "ffmpeg": media["ffmpeg"],
            "ffprobe": media["ffprobe"],
            "ark_configured": settings.ark_configured,
            "speech_configured": settings.speech_configured,
            "upload_directory": "ok" if upload_dir.exists() else "error",
            "active_jobs": active_jobs,
            "multimodal_job_worker": job_worker_status(),
        },
    }

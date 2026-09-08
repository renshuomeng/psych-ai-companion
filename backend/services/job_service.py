import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from database.models import MultimodalJob
from schemas.errors import AppError
from schemas.multimodal import MultimodalJobCreateRequest


ACTIVE_JOB_STATUSES = ("queued", "validating", "processing")
TERMINAL_JOB_STATUSES = ("completed", "failed", "cancelled")


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def create_job(db: Session, request: MultimodalJobCreateRequest, *, owner_id: str | None = None) -> MultimodalJob:
    now = datetime.now(timezone.utc)
    if not request.message.strip() and not request.file_ids:
        raise AppError(
            "empty_input",
            "请至少输入文字或上传一个图片、音频、视频文件。",
            "job_create",
            status_code=400,
        )
    active_count = (
        db.query(MultimodalJob)
        .filter(
            MultimodalJob.session_id == request.session_id,
            MultimodalJob.status.in_(ACTIVE_JOB_STATUSES),
        )
        .count()
    )
    max_active = get_settings().max_active_jobs_per_session
    if active_count >= max_active:
        raise AppError(
            "active_job_limit_exceeded",
            f"当前会话已有 {max_active} 个处理中任务，请等待完成或取消后再试。",
            "job_limit",
            retryable=True,
            retry_after_seconds=60,
            status_code=429,
        )

    request_payload = request.model_dump(mode="json")
    if owner_id:
        request_payload["_owner_id"] = owner_id
    job = MultimodalJob(
        job_id=uuid.uuid4().hex,
        session_id=request.session_id,
        status="queued",
        stage="queued",
        progress=0,
        request_json=_json(request_payload),
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=get_settings().upload_retention_hours),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def update_job_state(
    db: Session,
    job: MultimodalJob,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: int | None = None,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
) -> MultimodalJob:
    if job.status == "cancelled" and status != "cancelled":
        return job
    if status is not None:
        job.status = status
    if stage is not None:
        job.stage = stage
    if progress is not None:
        job.progress = max(0, min(100, int(progress)))
    if result is not None:
        job.result_json = _json(result)
        job.error_json = None
    if error is not None:
        job.error_json = _json(error)
        job.result_json = None
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: str) -> MultimodalJob:
    job = db.get(MultimodalJob, job_id)
    if not job:
        raise AppError(
            "job_not_found",
            "任务不存在或已清理。",
            "job_lookup",
            status_code=404,
        )
    return job


def job_to_response(job: MultimodalJob) -> dict:
    return {
        "job_id": job.job_id,
        "session_id": job.session_id,
        "status": job.status,
        "stage": job.stage,
        "progress": job.progress,
        "result": json.loads(job.result_json) if job.result_json else None,
        "error": json.loads(job.error_json) if job.error_json else None,
    }


def cancel_job(db: Session, job_id: str) -> dict:
    job = get_job(db, job_id)
    job.status = "cancelled"
    job.stage = "cancelled"
    job.progress = 0
    job.error_json = json.dumps(
        {
            "code": "job_cancelled",
            "message": "任务已取消。",
            "stage": "job_cancelled",
            "retryable": False,
        },
        ensure_ascii=False,
    )
    job.updated_at = datetime.now(timezone.utc)
    db.commit()
    return job_to_response(job)

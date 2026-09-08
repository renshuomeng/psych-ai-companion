from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from config import get_settings
from database.db import SessionLocal
from database.models import Conversation, MultimodalJob
from schemas.errors import AppError
from schemas.multimodal import MultimodalJobCreateRequest
from services.conversation_service import send_conversation_message
from services.job_service import update_job_state


logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_wake_event: asyncio.Event | None = None
_worker_loop: asyncio.AbstractEventLoop | None = None


def _load_request(job: MultimodalJob) -> tuple[MultimodalJobCreateRequest, str]:
    try:
        raw = json.loads(job.request_json or "{}")
    except json.JSONDecodeError as exc:
        raise AppError(
            "invalid_job_payload",
            "任务请求内容损坏，无法处理。",
            "job_validation",
            retryable=False,
            status_code=400,
        ) from exc
    payload = MultimodalJobCreateRequest.model_validate(raw)
    owner_id = str(raw.get("_owner_id") or "").strip()
    return payload, owner_id


def _error_payload(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, AppError):
        return exc.detail.model_dump(exclude_none=True)
    return {
        "code": "job_worker_failed",
        "message": "后台多模态任务处理失败，请稍后重试。",
        "stage": "job_worker",
        "retryable": True,
    }


def _job_is_cancelled(db: Session, job_id: str) -> bool:
    db.expire_all()
    job = db.get(MultimodalJob, job_id)
    return not job or job.status == "cancelled"


def _resolve_owner_id(db: Session, job: MultimodalJob, stored_owner_id: str) -> str:
    if stored_owner_id:
        return stored_owner_id
    conversation = db.get(Conversation, job.session_id)
    return conversation.owner_id if conversation else "local"


def _claim_next_job_id() -> str | None:
    with SessionLocal() as db:
        job = (
            db.query(MultimodalJob)
            .filter(MultimodalJob.status == "queued")
            .order_by(MultimodalJob.created_at.asc())
            .first()
        )
        if not job:
            return None
        update_job_state(db, job, status="validating", stage="validating", progress=5)
        return job.job_id


def recover_interrupted_jobs() -> int:
    with SessionLocal() as db:
        jobs = db.query(MultimodalJob).filter(MultimodalJob.status.in_(["validating", "processing"])).all()
        for job in jobs:
            update_job_state(
                db,
                job,
                status="failed",
                stage="worker_restarted",
                progress=100,
                error={
                    "code": "job_worker_restarted",
                    "message": "后台任务在服务重启时中断，请重新发送。",
                    "stage": "worker_restarted",
                    "retryable": True,
                },
            )
        return len(jobs)


async def process_job(job_id: str) -> bool:
    with SessionLocal() as db:
        job = db.get(MultimodalJob, job_id)
        if not job or job.status == "cancelled":
            return False

        try:
            payload, stored_owner_id = _load_request(job)
            owner_id = _resolve_owner_id(db, job, stored_owner_id)
            update_job_state(db, job, status="processing", stage="running_multimodal_pipeline", progress=15)
            result = await send_conversation_message(
                db,
                payload.session_id,
                owner_id,
                content=payload.message,
                file_ids=payload.file_ids,
                checkin=payload.checkin.model_dump() if payload.checkin else None,
            )
        except asyncio.CancelledError:
            update_job_state(
                db,
                job,
                status="failed",
                stage="worker_shutdown",
                progress=100,
                error={
                    "code": "job_worker_shutdown",
                    "message": "后台任务因服务停止而中断，请重新发送。",
                    "stage": "worker_shutdown",
                    "retryable": True,
                },
            )
            raise
        except Exception as exc:
            logger.exception("multimodal job failed job_id=%s", job_id)
            update_job_state(
                db,
                job,
                status="failed",
                stage=getattr(getattr(exc, "detail", None), "stage", "job_worker"),
                progress=100,
                error=_error_payload(exc),
            )
            return True

        if _job_is_cancelled(db, job_id):
            return True
        job = db.get(MultimodalJob, job_id)
        if not job:
            return True
        update_job_state(
            db,
            job,
            status="completed",
            stage="completed",
            progress=100,
            result=jsonable_encoder(result),
        )
        return True


async def process_next_job_once() -> bool:
    job_id = _claim_next_job_id()
    if not job_id:
        return False
    return await process_job(job_id)


async def _worker_loop_main() -> None:
    settings = get_settings()
    poll_interval = max(float(settings.multimodal_job_poll_interval_seconds), 0.2)
    assert _wake_event is not None
    while True:
        try:
            processed = await process_next_job_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("multimodal job worker loop iteration failed")
            processed = False
        if processed:
            continue
        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(_wake_event.wait(), timeout=poll_interval)
        _wake_event.clear()


def start_multimodal_job_worker() -> None:
    global _worker_loop, _worker_task, _wake_event
    settings = get_settings()
    if not settings.multimodal_job_worker_enabled:
        return
    if _worker_task and not _worker_task.done():
        return
    _worker_loop = asyncio.get_running_loop()
    _wake_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop_main(), name="multimodal-job-worker")


def wake_multimodal_job_worker() -> None:
    if not _worker_loop or not _wake_event:
        return
    _worker_loop.call_soon_threadsafe(_wake_event.set)


async def stop_multimodal_job_worker() -> None:
    global _worker_loop, _worker_task, _wake_event
    if not _worker_task:
        return
    _worker_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await _worker_task
    _worker_task = None
    _wake_event = None
    _worker_loop = None


def job_worker_status() -> str:
    if not get_settings().multimodal_job_worker_enabled:
        return "disabled"
    if _worker_task and not _worker_task.done():
        return "running"
    return "stopped"

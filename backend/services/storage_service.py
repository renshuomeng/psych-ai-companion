import re
import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from config import get_settings
from database.models import Attachment
from schemas.errors import AppError
from schemas.files import FileKind, FileMetadataResponse, FileUploadResponse
from services.ark_file_service import delete_provider_file
from services.media_service import get_duration_seconds, probe_media


ALLOWED_EXTENSIONS = {
    "image": {".jpg", ".jpeg", ".png", ".webp"},
    "audio": {".wav", ".mp3", ".ogg", ".opus", ".webm", ".m4a"},
    "video": {".mp4", ".webm", ".mov", ".mkv"},
}

MIME_PREFIX = {
    "image": "image/",
    "audio": "audio/",
    "video": "video/",
}


def _safe_session_id(session_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id.strip())[:80]
    if not safe:
        raise AppError(
            code="invalid_session",
            message="session_id 无效。",
            stage="upload_validation",
            retryable=False,
            status_code=400,
        )
    return safe


def _max_bytes(kind: FileKind) -> int:
    settings = get_settings()
    mb = {
        "image": settings.max_image_mb,
        "audio": settings.max_audio_mb,
        "video": settings.max_video_mb,
    }[kind]
    return mb * 1024 * 1024


def _attachment_to_response(attachment: Attachment) -> FileMetadataResponse:
    return FileMetadataResponse(
        file_id=attachment.file_id,
        session_id=attachment.session_id,
        kind=attachment.kind,  # type: ignore[arg-type]
        original_name=attachment.original_name,
        stored_name=attachment.stored_name,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        status=attachment.status,
        preview_url=f"/api/files/{attachment.file_id}/preview",
        created_at=attachment.created_at,
        provider_file_id=attachment.provider_file_id,
        duration_seconds=attachment.duration_seconds,
        width=attachment.width,
        height=attachment.height,
    )


def get_attachment(db: Session, file_id: str, session_id: str | None = None) -> Attachment:
    attachment = db.get(Attachment, file_id)
    if not attachment:
        raise AppError(
            code="file_not_found",
            message="文件不存在或已被清理。",
            stage="file_lookup",
            retryable=False,
            status_code=404,
        )
    if session_id and attachment.session_id != session_id:
        raise AppError(
            code="file_not_found",
            message="文件不存在或无权访问。",
            stage="file_lookup",
            retryable=False,
            status_code=404,
        )
    return attachment


def validate_image(path: Path) -> tuple[int | None, int | None]:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return image.width, image.height
    except UnidentifiedImageError as exc:
        raise AppError(
            code="invalid_media",
            message="图片文件无法打开，可能不是有效图片。",
            stage="image_validation",
            retryable=False,
            status_code=400,
        ) from exc


def validate_audio_or_video(path: Path, kind: FileKind) -> float | None:
    duration = get_duration_seconds(path, stage=f"{kind}_validation")
    if kind == "video" and duration and duration > get_settings().max_video_seconds:
        raise AppError(
            code="video_too_long",
            message=f"视频超过 {get_settings().max_video_seconds} 秒限制。",
            stage="video_validation",
            retryable=False,
            status_code=400,
        )
    probe_media(path, stage=f"{kind}_validation")
    return duration


async def save_upload(
    db: Session,
    file: UploadFile,
    session_id: str,
    kind: FileKind,
) -> FileUploadResponse:
    settings = get_settings()
    original_name = Path(file.filename or "upload").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS[kind]:
        raise AppError(
            code="invalid_file_type",
            message=f"不支持的 {kind} 文件类型。",
            stage="upload_validation",
            retryable=False,
            status_code=400,
        )

    mime_type = file.content_type or "application/octet-stream"
    if not mime_type.startswith(MIME_PREFIX[kind]) and not (
        kind == "audio" and mime_type in {"application/octet-stream", "video/webm"}
    ):
        raise AppError(
            code="invalid_file_type",
            message=f"文件 MIME 类型与 {kind} 不匹配。",
            stage="upload_validation",
            retryable=False,
            status_code=400,
        )

    safe_session_id = _safe_session_id(session_id)
    existing_count = db.query(Attachment).filter(Attachment.session_id == safe_session_id).count()
    if existing_count >= settings.max_session_attachments:
        raise AppError(
            code="attachment_limit_exceeded",
            message=f"当前会话附件数量已达到 {settings.max_session_attachments} 个上限，请先删除不需要的文件。",
            stage="upload_validation",
            retryable=False,
            status_code=429,
        )

    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}{extension}"
    target_dir = settings.resolved_upload_dir / safe_session_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / stored_name

    size = 0
    max_size = _max_bytes(kind)
    try:
        async with aiofiles.open(target_path, "wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_size:
                    raise AppError(
                        code="file_too_large",
                        message=f"文件超过 {kind} 大小限制。",
                        stage="upload_validation",
                        retryable=False,
                        status_code=400,
                    )
                await output.write(chunk)

        width = height = None
        duration = None
        if kind == "image":
            width, height = validate_image(target_path)
        else:
            duration = validate_audio_or_video(target_path, kind)

        now = datetime.now(timezone.utc)
        attachment = Attachment(
            file_id=file_id,
            session_id=safe_session_id,
            conversation_id=safe_session_id,
            kind=kind,
            original_name=original_name,
            stored_name=stored_name,
            mime_type=mime_type,
            size_bytes=size,
            status="uploaded",
            local_path=str(target_path),
            duration_seconds=duration,
            width=width,
            height=height,
            created_at=now,
            expires_at=now + timedelta(hours=settings.upload_retention_hours),
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)

        return FileUploadResponse(
            file_id=attachment.file_id,
            session_id=attachment.session_id,
            kind=kind,
            original_name=attachment.original_name,
            mime_type=attachment.mime_type,
            size_bytes=attachment.size_bytes,
            status=attachment.status,
            preview_url=f"/api/files/{attachment.file_id}/preview",
            created_at=attachment.created_at,
        )
    except Exception:
        if target_path.exists():
            target_path.unlink(missing_ok=True)
        raise


def get_file_metadata(db: Session, file_id: str, session_id: str | None = None) -> FileMetadataResponse:
    attachment = get_attachment(db, file_id, session_id)
    return _attachment_to_response(attachment)


def delete_file(db: Session, file_id: str, session_id: str | None = None) -> dict[str, str]:
    attachment = get_attachment(db, file_id, session_id)
    local_path = Path(attachment.local_path)
    local_path.unlink(missing_ok=True)
    if attachment.provider_file_id:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(delete_provider_file(attachment.provider_file_id))
        except RuntimeError:
            asyncio.run(delete_provider_file(attachment.provider_file_id))
    db.delete(attachment)
    db.commit()
    return {"status": "deleted", "file_id": file_id}

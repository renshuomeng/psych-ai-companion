from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


FileKind = Literal["image", "audio", "video"]


class FileUploadResponse(BaseModel):
    file_id: str
    session_id: str
    kind: FileKind
    original_name: str
    mime_type: str
    size_bytes: int
    status: str
    preview_url: str
    created_at: datetime


class FileMetadataResponse(FileUploadResponse):
    stored_name: str
    provider_file_id: str | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None


class UploadForm(BaseModel):
    session_id: str = Field(min_length=1)
    kind: FileKind

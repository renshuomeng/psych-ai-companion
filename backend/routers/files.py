from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, ensure_own_conversation, get_current_principal, principal_from_user, require_permission
from auth.permissions import Permission
from auth.service import get_user_from_token
from database.db import get_db
from schemas.errors import AppError
from schemas.files import FileKind, FileMetadataResponse, FileUploadResponse
from services.storage_service import delete_file, get_attachment, get_file_metadata, save_upload


router = APIRouter()


@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(...),
    kind: FileKind = Form(...),
    principal: CurrentPrincipal = Depends(require_permission(Permission.MULTIMODAL_USE, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> FileUploadResponse:
    ensure_own_conversation(db, session_id, principal)
    return await save_upload(db, file=file, session_id=session_id, kind=kind)


@router.get("/{file_id}", response_model=FileMetadataResponse)
def file_metadata(
    file_id: str,
    session_id: str | None = None,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> FileMetadataResponse:
    attachment = get_attachment(db, file_id=file_id, session_id=session_id)
    ensure_own_conversation(db, attachment.session_id, principal)
    return get_file_metadata(db, file_id=file_id, session_id=session_id)


@router.get("/{file_id}/preview")
def file_preview(
    file_id: str,
    session_id: str | None = None,
    access_token: str | None = None,
    principal: CurrentPrincipal | None = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> FileResponse:
    attachment = get_attachment(db, file_id=file_id, session_id=session_id)
    resolved_principal = principal
    if resolved_principal is None and access_token:
        user = get_user_from_token(db, access_token)
        resolved_principal = principal_from_user(user) if user else None
    if resolved_principal is None:
        raise AppError("authentication_required", "请先登录。", "auth", status_code=401)
    if (
        resolved_principal.auth_type == "local_development"
        and session_id
        and attachment.session_id == session_id
    ):
        pass
    else:
        ensure_own_conversation(db, attachment.session_id, resolved_principal)
    return FileResponse(
        attachment.local_path,
        media_type=attachment.mime_type,
        filename=attachment.original_name,
    )


@router.delete("/{file_id}")
def remove_file(
    file_id: str,
    session_id: str | None = None,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_DELETE_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    attachment = get_attachment(db, file_id=file_id, session_id=session_id)
    ensure_own_conversation(db, attachment.session_id, principal)
    return delete_file(db, file_id=file_id, session_id=session_id)

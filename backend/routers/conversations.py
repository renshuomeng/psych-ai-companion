from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, require_permission, sanitize_conversation_payload
from auth.permissions import Permission
from database.db import get_db
from schemas.conversations import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessageCreateRequest,
    ConversationSendResponse,
    ConversationSummaryResponse,
    ConversationUpdateRequest,
)
from services.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation_detail,
    list_conversations,
    send_conversation_message,
    update_conversation,
)


router = APIRouter()


@router.post("", response_model=ConversationSummaryResponse)
@router.post("/", response_model=ConversationSummaryResponse)
def create(
    payload: ConversationCreateRequest | None = None,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CHAT_USE, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    return create_conversation(db, principal.owner_id, title=payload.title if payload else None)


@router.get("", response_model=ConversationListResponse)
@router.get("/", response_model=ConversationListResponse)
def list_items(
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
    limit: int = Query(default=30, ge=1, le=100),
    cursor: str | None = None,
    search: str | None = None,
) -> dict:
    return list_conversations(db, principal.owner_id, limit=limit, cursor=cursor, search=search)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def detail(
    conversation_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
    limit: int | None = Query(default=None, ge=1, le=200),
    before: int | None = Query(default=None, ge=1),
) -> dict:
    result = get_conversation_detail(db, conversation_id, principal.owner_id, limit=limit, before_sequence=before)
    return sanitize_conversation_payload(result, principal)


@router.get("/{conversation_id}/messages", response_model=ConversationDetailResponse)
def messages(
    conversation_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = Query(default=None, ge=1),
) -> dict:
    result = get_conversation_detail(db, conversation_id, principal.owner_id, limit=limit, before_sequence=before)
    return sanitize_conversation_payload(result, principal)


@router.patch("/{conversation_id}", response_model=ConversationSummaryResponse)
def update(
    conversation_id: str,
    payload: ConversationUpdateRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    return update_conversation(
        db,
        conversation_id,
        principal.owner_id,
        title=payload.title,
        is_archived=payload.is_archived,
    )


@router.delete("/{conversation_id}")
async def delete(
    conversation_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_DELETE_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    return await delete_conversation(db, conversation_id, principal.owner_id)


@router.post("/{conversation_id}/messages", response_model=ConversationSendResponse)
async def send_message(
    conversation_id: str,
    payload: ConversationMessageCreateRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CHAT_USE, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    result = await send_conversation_message(
        db,
        conversation_id,
        principal.owner_id,
        content=payload.content,
        file_ids=payload.file_ids,
        checkin=payload.checkin.model_dump() if payload.checkin else None,
    )
    return sanitize_conversation_payload(result, principal)

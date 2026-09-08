from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.db import get_db
from agents.memory_agent import rebuild_memory
from auth.dependencies import CurrentPrincipal, ensure_own_conversation, require_permission
from auth.permissions import Permission
from services.memory_service import (
    delete_memory as delete_memory_records,
    get_memory_snapshot,
    update_memory_settings as update_memory_settings_record,
)
from services.session_service import delete_session_data, privacy_summary


router = APIRouter()


@router.get("/{session_id}/privacy-summary")
def get_privacy_summary(
    session_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_own_conversation(db, session_id, principal)
    return privacy_summary(session_id)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_DELETE_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, int | str]:
    ensure_own_conversation(db, session_id, principal)
    return await delete_session_data(db, session_id)


@router.get("/{session_id}/memory")
def get_memory(
    session_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_own_conversation(db, session_id, principal)
    return get_memory_snapshot(db, session_id)


@router.delete("/{session_id}/memory")
def delete_memory(
    session_id: str,
    memory_id: str | None = None,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_DELETE_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_own_conversation(db, session_id, principal)
    return delete_memory_records(db, session_id, memory_id=memory_id)


@router.patch("/{session_id}/memory-settings")
def update_memory_settings(
    session_id: str,
    payload: dict[str, object],
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_own_conversation(db, session_id, principal)
    return update_memory_settings_record(db, session_id, bool(payload.get("memory_enabled", False)))


@router.post("/{session_id}/memory/rebuild")
def rebuild_session_memory(
    session_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_own_conversation(db, session_id, principal)
    summary = rebuild_memory(db, session_id)
    return {"status": "rebuilt", "session_id": session_id, "conversation_summary": summary}

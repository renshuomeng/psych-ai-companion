from typing import Any

from sqlalchemy.orm import Session

from services.memory_service import (
    get_effective_memory_snapshot,
    maybe_update_summary,
    rebuild_summary,
    recent_messages,
    record_message,
    update_profile_from_user_message,
    update_risk_state,
)


def remember_user_turn(
    db: Session,
    session_id: str,
    message: str,
    checkin: dict[str, Any] | None,
    risk: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    message_type: str = "text",
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    stored_metadata = {
        "risk_level": risk.get("level"),
        "checkin_present": bool(checkin),
        **(metadata or {}),
    }
    message_id = record_message(
        db,
        session_id,
        "user",
        message,
        stored_metadata,
        message_type=message_type,
        attachments=attachments,
    )
    update_profile_from_user_message(db, session_id, message_id, message, checkin=checkin)
    update_risk_state(db, session_id, risk)
    return message_id


def remember_assistant_turn(
    db: Session,
    session_id: str,
    reply: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    record_message(db, session_id, "assistant", reply, metadata or {})
    return maybe_update_summary(db, session_id)


def load_memory_context(db: Session, session_id: str) -> dict[str, Any]:
    return {
        "snapshot": get_effective_memory_snapshot(db, session_id),
        "recent_messages": recent_messages(db, session_id),
    }


def rebuild_memory(db: Session, session_id: str) -> dict[str, Any]:
    return rebuild_summary(db, session_id)

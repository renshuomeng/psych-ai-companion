import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from agents.coordinator_agent import run_multimodal_flow
from agents.multimodal_agent import process_attachments
from config import get_settings
from database.models import (
    Attachment,
    ChatMessage,
    Conversation,
    ConversationSummary,
    Feedback,
    InterventionSession,
    MemorySettings,
    MultimodalJob,
    RequestMetric,
    RetrievalLog,
    RiskState,
    UserMemoryItem,
    utcnow,
)
from schemas.errors import AppError
from services.ark_file_service import delete_provider_file


DEFAULT_TITLE = "新对话"


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _load_json(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return fallback


def normalize_owner_id(owner_id: str | None) -> str:
    raw = (owner_id or "local").strip()
    safe = re.sub(r"[^a-zA-Z0-9:_-]", "_", raw)[:128]
    return safe or "local"


def _conversation_query(db: Session, conversation_id: str, owner_id: str) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.owner_id != owner_id or conversation.is_archived:
        raise AppError(
            "conversation_not_found",
            "对话不存在或已删除。",
            "conversation_lookup",
            status_code=404,
        )
    return conversation


def _message_to_response(row: ChatMessage) -> dict[str, Any]:
    conversation_id = row.conversation_id or row.session_id
    return {
        "id": row.message_id,
        "message_id": row.message_id,
        "conversation_id": conversation_id,
        "role": row.role,
        "content": row.content,
        "created_at": row.created_at,
        "sequence": row.sequence,
        "message_type": row.message_type or "text",
        "attachments": _load_json(row.attachments_json, []),
        "metadata": _load_json(row.metadata_json, {}),
    }


def _conversation_summary(db: Session, conversation: Conversation) -> dict[str, Any]:
    latest = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc())
        .first()
    )
    message_count = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .count()
    )
    preview = latest.content.replace("\n", " ").strip()[:80] if latest else ""
    return {
        "id": conversation.id,
        "title": conversation.title,
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "last_message_at": conversation.last_message_at,
        "is_archived": conversation.is_archived,
        "title_manually_set": conversation.title_manually_set,
        "last_message_preview": preview,
        "message_count": message_count,
    }


def _sync_conversation_after_message(db: Session, conversation: Conversation) -> None:
    latest = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.desc())
        .first()
    )
    now = utcnow()
    conversation.updated_at = now
    conversation.last_message_at = latest.created_at if latest else None
    db.commit()
    db.refresh(conversation)


def _fallback_title(text: str) -> str:
    normalized = "".join(text.split())
    if not normalized:
        return DEFAULT_TITLE
    title_rules = [
        (["论文", "毕业", "开题", "导师"], "论文压力"),
        (["睡不着", "失眠", "睡眠"], "睡眠困扰"),
        (["就业", "求职", "简历", "面试", "offer"], "就业压力"),
        (["室友", "朋友", "同学", "关系", "边界"], "人际关系"),
        (["孤独", "孤单", "没人理解"], "孤独陪伴"),
        (["自杀", "轻生", "自残", "想死"], "危机支持"),
        (["考试", "复习", "绩点"], "考试压力"),
    ]
    for words, title in title_rules:
        if any(word in normalized for word in words):
            return title
    return normalized[:12]


def maybe_generate_title(db: Session, conversation: Conversation, first_user_text: str) -> None:
    if not get_settings().auto_generate_conversation_title:
        return
    if conversation.title_manually_set or conversation.title != DEFAULT_TITLE:
        return
    user_count = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id, ChatMessage.role == "user")
        .count()
    )
    if user_count != 1:
        return
    conversation.title = _fallback_title(first_user_text)
    conversation.updated_at = utcnow()
    db.commit()
    db.refresh(conversation)


def create_conversation(db: Session, owner_id: str, title: str | None = None) -> dict[str, Any]:
    owner = normalize_owner_id(owner_id)
    empty_existing = (
        db.query(Conversation)
        .filter(Conversation.owner_id == owner, Conversation.is_archived.is_(False))
        .outerjoin(ChatMessage, ChatMessage.conversation_id == Conversation.id)
        .group_by(Conversation.id)
        .having(func.count(ChatMessage.message_id) == 0)
        .order_by(desc(Conversation.created_at))
        .first()
    )
    if empty_existing and not title:
        return _conversation_summary(db, empty_existing)

    now = utcnow()
    conversation = Conversation(
        id=uuid.uuid4().hex,
        owner_id=owner,
        title=(title or DEFAULT_TITLE).strip()[:80] or DEFAULT_TITLE,
        title_manually_set=bool(title and title.strip() and title.strip() != DEFAULT_TITLE),
        created_at=now,
        updated_at=now,
        last_message_at=None,
        is_archived=False,
        metadata_json=_json({"conversation_id_equals_session_id": True}),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return _conversation_summary(db, conversation)


def list_conversations(
    db: Session,
    owner_id: str,
    limit: int = 30,
    cursor: str | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    owner = normalize_owner_id(owner_id)
    query = db.query(Conversation).filter(
        Conversation.owner_id == owner,
        Conversation.is_archived.is_(False),
    )
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Conversation.title.ilike(pattern), Conversation.id == search.strip()))
    if cursor:
        try:
            before = datetime.fromisoformat(cursor)
            query = query.filter(Conversation.updated_at < before)
        except ValueError:
            pass
    rows = (
        query.order_by(desc(Conversation.last_message_at), desc(Conversation.updated_at))
        .limit(max(1, min(limit, 100)) + 1)
        .all()
    )
    page = rows[:limit]
    next_cursor = page[-1].updated_at.isoformat() if len(rows) > limit and page else None
    return {"items": [_conversation_summary(db, row) for row in page], "next_cursor": next_cursor}


def get_conversation_detail(
    db: Session,
    conversation_id: str,
    owner_id: str,
    limit: int | None = None,
    before_sequence: int | None = None,
) -> dict[str, Any]:
    conversation = _conversation_query(db, conversation_id, normalize_owner_id(owner_id))
    query = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id)
    if before_sequence is not None:
        query = query.filter(ChatMessage.sequence < before_sequence)
    if limit:
        rows = query.order_by(ChatMessage.sequence.desc(), ChatMessage.created_at.desc()).limit(limit + 1).all()
        has_more = len(rows) > limit
        rows = list(reversed(rows[:limit]))
    else:
        rows = query.order_by(ChatMessage.sequence.asc(), ChatMessage.created_at.asc()).all()
        has_more = False
    return {
        "conversation": _conversation_summary(db, conversation),
        "messages": [_message_to_response(row) for row in rows],
        "has_more_messages": has_more,
    }


def update_conversation(
    db: Session,
    conversation_id: str,
    owner_id: str,
    *,
    title: str | None = None,
    is_archived: bool | None = None,
) -> dict[str, Any]:
    conversation = _conversation_query(db, conversation_id, normalize_owner_id(owner_id))
    if title is not None:
        conversation.title = title.strip()[:80] or DEFAULT_TITLE
        conversation.title_manually_set = True
    if is_archived is not None:
        conversation.is_archived = bool(is_archived)
    conversation.updated_at = utcnow()
    db.commit()
    db.refresh(conversation)
    return _conversation_summary(db, conversation)


async def delete_conversation(db: Session, conversation_id: str, owner_id: str) -> dict[str, Any]:
    conversation = _conversation_query(db, conversation_id, normalize_owner_id(owner_id))
    attachments = db.query(Attachment).filter(Attachment.conversation_id == conversation.id).all()
    if not attachments:
        attachments = db.query(Attachment).filter(Attachment.session_id == conversation.id).all()
    removed_files = 0
    removed_provider_files = 0
    file_errors: list[dict[str, str]] = []
    for attachment in attachments:
        try:
            Path(attachment.local_path).unlink(missing_ok=True)
            removed_files += 1
        except OSError as exc:
            file_errors.append({"file_id": attachment.file_id, "message": str(exc)})
        if attachment.provider_file_id:
            try:
                await delete_provider_file(attachment.provider_file_id)
                removed_provider_files += 1
            except Exception as exc:
                file_errors.append({"file_id": attachment.file_id, "message": str(exc)})
        db.delete(attachment)

    removed_messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == conversation.id).delete(
        synchronize_session=False
    )
    removed_memory = db.query(UserMemoryItem).filter(UserMemoryItem.session_id == conversation.id).delete(
        synchronize_session=False
    )
    db.query(ConversationSummary).filter(ConversationSummary.session_id == conversation.id).delete(
        synchronize_session=False
    )
    db.query(MemorySettings).filter(MemorySettings.session_id == conversation.id).delete(
        synchronize_session=False
    )
    db.query(RiskState).filter(RiskState.session_id == conversation.id).delete(synchronize_session=False)
    db.query(RetrievalLog).filter(RetrievalLog.session_id == conversation.id).delete(synchronize_session=False)
    db.query(RequestMetric).filter(RequestMetric.session_id == conversation.id).delete(synchronize_session=False)
    db.query(MultimodalJob).filter(MultimodalJob.session_id == conversation.id).delete(synchronize_session=False)
    db.query(Feedback).filter(Feedback.session_id == conversation.id).delete(synchronize_session=False)
    db.query(InterventionSession).filter(InterventionSession.session_id == conversation.id).delete(
        synchronize_session=False
    )
    db.delete(conversation)
    db.commit()
    return {
        "status": "deleted",
        "conversation_id": conversation_id,
        "removed_messages": int(removed_messages),
        "removed_memory_items": int(removed_memory),
        "removed_files": removed_files,
        "removed_provider_files": removed_provider_files,
        "file_errors": file_errors,
    }


def _message_type_for(file_ids: list[str]) -> str:
    return "multimodal" if file_ids else "text"


def _latest_messages_after(db: Session, conversation_id: str, after_sequence: int) -> list[ChatMessage]:
    return (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id, ChatMessage.sequence > after_sequence)
        .order_by(ChatMessage.sequence.asc(), ChatMessage.created_at.asc())
        .all()
    )


def _max_sequence(db: Session, conversation_id: str) -> int:
    value = (
        db.query(func.max(ChatMessage.sequence))
        .filter(ChatMessage.conversation_id == conversation_id)
        .scalar()
    )
    return int(value or 0)


def _augment_messages(
    db: Session,
    conversation_id: str,
    new_rows: list[ChatMessage],
    processed: dict[str, Any],
    result: dict[str, Any],
) -> None:
    user_row = next((row for row in new_rows if row.role == "user"), None)
    assistant_row = next((row for row in reversed(new_rows) if row.role == "assistant"), None)
    attachments = processed.get("attachments", [])
    if user_row:
        user_row.message_type = _message_type_for([item.get("file_id", "") for item in attachments])
        user_row.attachments_json = _json(attachments)
        metadata = _load_json(user_row.metadata_json, {})
        metadata.update(
            {
                "transcript": processed.get("transcript", {}),
                "media_analysis": processed.get("media_analysis", {}),
                "input_modalities": sorted(
                    {"text" if user_row.content.strip() else "", *[str(item.get("kind", "")) for item in attachments]}
                    - {""}
                ),
            }
        )
        user_row.metadata_json = _json(metadata)
        for item in attachments:
            file_id = str(item.get("file_id", ""))
            if not file_id:
                continue
            attachment = db.get(Attachment, file_id)
            if attachment and attachment.conversation_id == conversation_id:
                attachment.message_id = user_row.message_id
    if assistant_row:
        metadata = _load_json(assistant_row.metadata_json, {})
        metadata.update(
            {
                "emotion": result.get("emotion", {}),
                "risk": result.get("risk", {}),
                "interventions": result.get("interventions", []),
                "agent_trace": result.get("agent_trace", []),
                "provider_metadata": result.get("provider_metadata", {}),
                "knowledge_sources": result.get("knowledge_sources", []),
                "evidence": result.get("evidence", []),
                "retrieval": result.get("retrieval", {}),
                "psychological_state": result.get("psychological_state", {}),
                "strategy_plan": result.get("strategy_plan", {}),
                "rag_route": result.get("rag_route", {}),
                "request_metrics": result.get("request_metrics", {}),
            }
        )
        assistant_row.metadata_json = _json(metadata)
    db.commit()


async def send_conversation_message(
    db: Session,
    conversation_id: str,
    owner_id: str,
    content: str,
    file_ids: list[str],
    checkin: dict[str, Any] | None = None,
) -> dict[str, Any]:
    conversation = _conversation_query(db, conversation_id, normalize_owner_id(owner_id))
    message_text = content.strip()
    clean_file_ids = [item for item in file_ids if item]
    if not message_text and not clean_file_ids:
        raise AppError(
            "empty_input",
            "请至少输入文字或上传一个图片、音频、视频文件。",
            "conversation_message",
            status_code=400,
        )

    before_sequence = _max_sequence(db, conversation.id)
    processed = await process_attachments(db, conversation.id, clean_file_ids)
    successful_modalities = [item["kind"] for item in processed["attachments"] if item["status"] == "processed"]
    if message_text:
        successful_modalities.insert(0, "text")
    if not successful_modalities and clean_file_ids:
        first_error = processed["errors"][0] if processed["errors"] else None
        if first_error:
            raise AppError(
                first_error["code"],
                first_error["message"],
                first_error["stage"],
                first_error.get("retryable", False),
                first_error.get("request_id"),
                status_code=400,
            )

    context = {
        "audio_transcript": processed["transcript"]["text"],
        "video_transcript": processed["risk_sources"]["video_transcript"],
        "image_ocr": processed["media_analysis"]["ocr_text"],
        "video_ocr": processed["media_analysis"]["ocr_text"],
        "media_analysis": processed["media_analysis"],
        "attachments": processed["attachments"],
    }
    result = await run_multimodal_flow(
        session_id=conversation.id,
        message=message_text,
        checkin=checkin,
        multimodal_context=context,
    )
    provider_metadata = result.get("provider_metadata") or {}
    if processed["provider_metadata"]:
        provider_metadata["media_providers"] = processed["provider_metadata"]
    result = {
        "session_id": conversation.id,
        "conversation_id": conversation.id,
        "input_modalities": sorted(set(successful_modalities)),
        "attachments": processed["attachments"],
        "transcript": processed["transcript"],
        "media_analysis": processed["media_analysis"],
        **result,
        "provider_metadata": provider_metadata,
    }

    db.expire_all()
    new_rows = _latest_messages_after(db, conversation.id, before_sequence)
    _augment_messages(db, conversation.id, new_rows, processed, result)
    db.expire_all()
    new_rows = _latest_messages_after(db, conversation.id, before_sequence)
    user_row = next((row for row in new_rows if row.role == "user"), None)
    assistant_row = next((row for row in reversed(new_rows) if row.role == "assistant"), None)
    if not user_row or not assistant_row:
        raise AppError(
            "message_persistence_failed",
            "消息已处理，但未能完整写入数据库。",
            "conversation_message",
            status_code=500,
        )

    maybe_generate_title(db, conversation, message_text or processed["transcript"]["text"])
    _sync_conversation_after_message(db, conversation)
    return {
        "conversation": _conversation_summary(db, conversation),
        "user_message": _message_to_response(user_row),
        "assistant_message": _message_to_response(assistant_row),
        "result": result,
    }


def ensure_conversations_for_existing_sessions(db: Session, owner_id: str = "legacy") -> dict[str, Any]:
    session_ids = {
        item[0]
        for item in db.query(ChatMessage.session_id).distinct().all()
        if item[0]
    }
    session_ids.update(
        item[0]
        for item in db.query(Attachment.session_id).distinct().all()
        if item[0]
    )
    created = 0
    for session_id in sorted(session_ids):
        if db.get(Conversation, session_id):
            continue
        first_user = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id, ChatMessage.role == "user")
            .order_by(ChatMessage.created_at.asc())
            .first()
        )
        latest = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )
        now = utcnow()
        db.add(
            Conversation(
                id=session_id,
                owner_id=owner_id,
                title=_fallback_title(first_user.content if first_user else ""),
                created_at=first_user.created_at if first_user else now,
                updated_at=latest.created_at if latest else now,
                last_message_at=latest.created_at if latest else None,
                is_archived=False,
                title_manually_set=False,
                metadata_json=_json({"migrated_from_session_id": True}),
            )
        )
        db.query(ChatMessage).filter(ChatMessage.session_id == session_id).update(
            {"conversation_id": session_id},
            synchronize_session=False,
        )
        db.query(Attachment).filter(Attachment.session_id == session_id).update(
            {"conversation_id": session_id},
            synchronize_session=False,
        )
        created += 1
    db.commit()
    return {"status": "completed", "created": created, "checked_sessions": len(session_ids)}

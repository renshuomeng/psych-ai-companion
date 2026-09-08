import json
import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from database.models import (
    ChatMessage,
    Conversation,
    ConversationSummary,
    MemorySettings,
    RiskState,
    UserMemoryItem,
    utcnow,
)


DEFAULT_SUMMARY = {
    "main_topics": [],
    "explicit_user_statements": [],
    "system_inferences": [],
    "actions_suggested": [],
    "actions_confirmed_completed": [],
    "actions_reported_helpful": [],
    "actions_reported_unhelpful": [],
    "unresolved_questions": [],
    "last_updated_at": None,
}

GLOBAL_MEMORY_PREFIX = "global:"
MERGE_LIST_MEMORY_KEYS = {
    "main_stressors",
    "disliked_interventions",
    "preferred_interventions",
}


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _load_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except json.JSONDecodeError:
        return fallback


def global_memory_session_id(owner_id: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9:_-]", "_", str(owner_id or "local").strip())
    return f"{GLOBAL_MEMORY_PREFIX}{normalized}"[:128]


def _owner_id_for_session(db: Session, session_id: str) -> str | None:
    conversation = db.get(Conversation, session_id)
    if not conversation:
        return None
    return str(conversation.owner_id or "").strip() or None


def get_or_create_memory_settings(db: Session, session_id: str) -> MemorySettings:
    settings = db.get(MemorySettings, session_id)
    if not settings:
        settings = MemorySettings(
            session_id=session_id,
            memory_enabled=get_settings().memory_enabled,
            updated_at=utcnow(),
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def record_message(
    db: Session,
    session_id: str,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    message_type: str = "text",
    attachments: list[dict[str, Any]] | None = None,
) -> str:
    message_id = uuid.uuid4().hex
    sequence = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == session_id)
        .count()
        + 1
    )
    db.add(
        ChatMessage(
            message_id=message_id,
            session_id=session_id,
            conversation_id=session_id,
            role=role,
            content=content[:8000],
            sequence=sequence,
            message_type=message_type,
            attachments_json=_json(attachments or []),
            metadata_json=_json(metadata or {}),
            created_at=utcnow(),
        )
    )
    db.commit()
    return message_id


def recent_messages(db: Session, session_id: str, limit: int | None = None) -> list[dict[str, Any]]:
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit or get_settings().recent_message_limit)
        .all()
    )
    return [
        {
            "message_id": row.message_id,
            "conversation_id": row.conversation_id or row.session_id,
            "role": row.role,
            "content": row.content,
            "sequence": row.sequence,
            "message_type": row.message_type,
            "attachments": _load_json(row.attachments_json, []),
            "created_at": row.created_at.isoformat(),
            "metadata": _load_json(row.metadata_json, {}),
        }
        for row in reversed(rows)
    ]


def _extract_topics(text: str) -> list[str]:
    topic_map = {
        "论文": ["论文", "毕业"],
        "睡眠": ["睡眠", "失眠", "睡不着"],
        "就业": ["就业", "求职", "面试", "简历"],
        "考试": ["考试", "复习"],
        "人际关系": ["朋友", "室友", "同学", "恋爱", "关系"],
        "孤独": ["孤独", "没人理解"],
    }
    return [topic for topic, words in topic_map.items() if any(word in text for word in words)]


def _merge_memory_values(existing: Any, value: Any) -> Any:
    if isinstance(existing, list) or isinstance(value, list):
        output: list[Any] = []
        seen: set[str] = set()
        for item in [*(existing if isinstance(existing, list) else [existing]), *(value if isinstance(value, list) else [value])]:
            if item in (None, "", []):
                continue
            key = json.dumps(item, ensure_ascii=False, sort_keys=True) if isinstance(item, (dict, list)) else str(item)
            if key in seen:
                continue
            seen.add(key)
            output.append(item)
        return output
    return value


def _upsert_memory_item(
    db: Session,
    session_id: str,
    key: str,
    value: Any,
    source_message_id: str | None,
    confidence: float,
    confirmed: bool,
    *,
    merge_value: bool = False,
) -> None:
    existing = (
        db.query(UserMemoryItem)
        .filter(UserMemoryItem.session_id == session_id, UserMemoryItem.key == key)
        .first()
    )
    if existing:
        next_value = _merge_memory_values(_load_json(existing.value_json, None), value) if merge_value else value
        existing.value_json = _json(next_value)
        existing.source_message_id = source_message_id
        existing.confidence = max(float(existing.confidence or 0), confidence)
        existing.is_user_confirmed = bool(existing.is_user_confirmed or confirmed)
        existing.updated_at = utcnow()
        return
    db.add(
        UserMemoryItem(
            memory_id=uuid.uuid4().hex,
            session_id=session_id,
            key=key,
            value_json=_json(value),
            source_message_id=source_message_id,
            confidence=confidence,
            is_user_confirmed=confirmed,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
    )


def _memory_facts_from_user_message(
    text: str,
    checkin: dict[str, Any] | None = None,
) -> list[tuple[str, Any, float, bool]]:
    facts: list[tuple[str, Any, float, bool]] = []
    if checkin and checkin.get("preferred_style"):
        facts.append(("preferred_support_style", checkin["preferred_style"], 0.92, True))
    sources = []
    if checkin:
        sources = checkin.get("stress_sources") or checkin.get("stress_source") or []
    topics = sorted(set(_extract_topics(text) + [str(item) for item in sources if item]))
    if topics:
        facts.append(("main_stressors", topics, 0.86, True))
    disliked = re.findall(r"不喜欢([^，。；\n]{1,12})", text)
    if disliked:
        facts.append(("disliked_interventions", [item.strip() for item in disliked], 0.82, True))
    helpful = re.findall(r"(.{1,12})(有帮助|挺有用|有效)", text)
    if helpful:
        facts.append(("preferred_interventions", [item[0].strip("，。 ") for item in helpful], 0.76, True))
    return facts


def _update_global_profile_from_user_message(
    db: Session,
    session_id: str,
    message_id: str,
    text: str,
    checkin: dict[str, Any] | None = None,
) -> None:
    if not get_settings().global_memory_across_conversations:
        return
    facts = _memory_facts_from_user_message(text, checkin)
    if not facts:
        return
    owner_id = _owner_id_for_session(db, session_id)
    if not owner_id:
        return
    global_session_id = global_memory_session_id(owner_id)
    if not get_or_create_memory_settings(db, global_session_id).memory_enabled:
        return
    source_message_id = f"{session_id}:{message_id}"
    for key, value, confidence, confirmed in facts:
        _upsert_memory_item(
            db,
            global_session_id,
            key,
            value,
            source_message_id,
            confidence,
            confirmed,
            merge_value=key in MERGE_LIST_MEMORY_KEYS,
        )


def update_profile_from_user_message(
    db: Session,
    session_id: str,
    message_id: str,
    text: str,
    checkin: dict[str, Any] | None = None,
) -> None:
    if not get_or_create_memory_settings(db, session_id).memory_enabled:
        return
    for key, value, confidence, confirmed in _memory_facts_from_user_message(text, checkin):
        _upsert_memory_item(
            db,
            session_id,
            key,
            value,
            message_id,
            confidence,
            confirmed,
            merge_value=key in MERGE_LIST_MEMORY_KEYS,
        )
    _update_global_profile_from_user_message(db, session_id, message_id, text, checkin)
    db.commit()


def get_memory_snapshot(db: Session, session_id: str) -> dict[str, Any]:
    settings = get_or_create_memory_settings(db, session_id)
    summary = db.get(ConversationSummary, session_id)
    items = db.query(UserMemoryItem).filter(UserMemoryItem.session_id == session_id).all()
    profile: dict[str, Any] = {"memory_enabled": settings.memory_enabled}
    memory_items: list[dict[str, Any]] = []
    for item in items:
        value = _load_json(item.value_json, {})
        profile[item.key] = value
        memory_items.append(
            {
                "memory_id": item.memory_id,
                "key": item.key,
                "value": value,
                "source_message_id": item.source_message_id,
                "confidence": item.confidence,
                "is_user_confirmed": item.is_user_confirmed,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
            }
        )
    return {
        "session_id": session_id,
        "memory_enabled": settings.memory_enabled,
        "profile": profile,
        "memory_items": memory_items,
        "conversation_summary": _load_json(summary.summary_json, DEFAULT_SUMMARY)
        if summary
        else dict(DEFAULT_SUMMARY),
        "message_count": summary.message_count if summary else 0,
        "updated_at": summary.updated_at.isoformat() if summary else None,
    }


def _merge_profiles(global_profile: dict[str, Any], session_profile: dict[str, Any]) -> dict[str, Any]:
    merged = dict(global_profile)
    merged.update(session_profile)
    for key in MERGE_LIST_MEMORY_KEYS:
        if key in global_profile or key in session_profile:
            merged[key] = _merge_memory_values(global_profile.get(key, []), session_profile.get(key, []))
    merged["memory_enabled"] = session_profile.get("memory_enabled", True)
    return merged


def get_effective_memory_snapshot(db: Session, session_id: str) -> dict[str, Any]:
    session_snapshot = get_memory_snapshot(db, session_id)
    session_snapshot["global_memory_enabled"] = False
    if not session_snapshot.get("memory_enabled"):
        return session_snapshot
    if not get_settings().global_memory_across_conversations:
        return session_snapshot

    owner_id = _owner_id_for_session(db, session_id)
    if not owner_id:
        return session_snapshot
    global_session_id = global_memory_session_id(owner_id)
    global_snapshot = get_memory_snapshot(db, global_session_id)
    if not global_snapshot.get("memory_enabled"):
        return session_snapshot

    session_snapshot["profile"] = _merge_profiles(
        global_snapshot.get("profile", {}),
        session_snapshot.get("profile", {}),
    )
    session_snapshot["global_memory_enabled"] = True
    session_snapshot["global_memory_session_id"] = global_session_id
    session_snapshot["global_profile"] = global_snapshot.get("profile", {})
    session_snapshot["global_memory_items"] = [
        {**item, "scope": "global"} for item in global_snapshot.get("memory_items", [])
    ]
    session_snapshot["memory_items"] = [
        *session_snapshot.get("global_memory_items", []),
        *[{**item, "scope": "session"} for item in session_snapshot.get("memory_items", [])],
    ]
    return session_snapshot


def rebuild_summary(db: Session, session_id: str) -> dict[str, Any]:
    messages = recent_messages(db, session_id, limit=200)
    summary = dict(DEFAULT_SUMMARY)
    explicit: list[str] = []
    suggestions: list[str] = []
    unresolved: list[str] = []
    topics: set[str] = set()
    helpful: list[str] = []
    unhelpful: list[str] = []
    completed: list[str] = []
    for message in messages:
        content = message["content"]
        if message["role"] == "user":
            topics.update(_extract_topics(content))
            if content.strip():
                explicit.append(f"用户明确表示：{content[:80]}")
            if "有帮助" in content or "有效" in content:
                helpful.append(content[:80])
            if "没用" in content or "无效" in content or "不喜欢" in content:
                unhelpful.append(content[:80])
            if "做完" in content or "完成" in content:
                completed.append(content[:80])
        elif message["role"] == "assistant":
            if "可以" in content or "建议" in content:
                suggestions.append(content[:80])
            if "？" in content or "?" in content:
                unresolved.append(content[-80:])
    summary.update(
        {
            "main_topics": sorted(topics),
            "explicit_user_statements": explicit[-10:],
            "system_inferences": [
                f"系统根据最近对话推测主要关注：{', '.join(sorted(topics))}"
            ]
            if topics
            else [],
            "actions_suggested": suggestions[-8:],
            "actions_confirmed_completed": completed[-5:],
            "actions_reported_helpful": helpful[-5:],
            "actions_reported_unhelpful": unhelpful[-5:],
            "unresolved_questions": unresolved[-5:],
            "last_updated_at": utcnow().isoformat(),
        }
    )
    row = db.get(ConversationSummary, session_id)
    if row:
        row.summary_json = _json(summary)
        row.message_count = len(messages)
        row.updated_at = utcnow()
    else:
        db.add(
            ConversationSummary(
                session_id=session_id,
                summary_json=_json(summary),
                message_count=len(messages),
                updated_at=utcnow(),
            )
        )
    db.commit()
    return summary


def maybe_update_summary(db: Session, session_id: str) -> dict[str, Any] | None:
    if not get_or_create_memory_settings(db, session_id).memory_enabled:
        return None
    count = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).count()
    existing = db.get(ConversationSummary, session_id)
    trigger = get_settings().summary_trigger_message_count
    if count >= trigger and (not existing or count - existing.message_count >= 4):
        return rebuild_summary(db, session_id)
    if not existing:
        return rebuild_summary(db, session_id)
    return _load_json(existing.summary_json, DEFAULT_SUMMARY)


def update_memory_settings(db: Session, session_id: str, enabled: bool) -> dict[str, Any]:
    row = get_or_create_memory_settings(db, session_id)
    row.memory_enabled = enabled
    row.updated_at = utcnow()
    db.commit()
    return get_memory_snapshot(db, session_id)


def delete_memory(db: Session, session_id: str, memory_id: str | None = None) -> dict[str, Any]:
    if memory_id:
        deleted = (
            db.query(UserMemoryItem)
            .filter(UserMemoryItem.session_id == session_id, UserMemoryItem.memory_id == memory_id)
            .delete(synchronize_session=False)
        )
    else:
        deleted = (
            db.query(UserMemoryItem)
            .filter(UserMemoryItem.session_id == session_id)
            .delete(synchronize_session=False)
        )
        db.query(ConversationSummary).filter(ConversationSummary.session_id == session_id).delete(
            synchronize_session=False
        )
    db.commit()
    return {"status": "deleted", "session_id": session_id, "deleted": int(deleted)}


def update_risk_state(db: Session, session_id: str, risk: dict[str, Any]) -> dict[str, Any]:
    row = db.get(RiskState, session_id)
    dimensions = risk.get("dimensions", {})
    evidence = risk.get("evidence", [])
    requires_follow_up = risk.get("level") in {"medium", "high"}
    if row:
        row.current_risk_level = risk.get("level", "low")
        row.dimensions_json = _json(dimensions)
        row.evidence_json = _json(evidence)
        row.last_risk_check_at = utcnow()
        row.requires_follow_up = requires_follow_up
    else:
        db.add(
            RiskState(
                session_id=session_id,
                current_risk_level=risk.get("level", "low"),
                dimensions_json=_json(dimensions),
                evidence_json=_json(evidence),
                last_risk_check_at=utcnow(),
                requires_follow_up=requires_follow_up,
            )
        )
    db.commit()
    return {
        "current_risk_level": risk.get("level", "low"),
        "risk_dimensions": dimensions,
        "evidence": evidence,
        "last_risk_check_at": utcnow().isoformat(),
        "requires_follow_up": requires_follow_up,
    }

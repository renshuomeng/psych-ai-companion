from datetime import timedelta
import uuid

import pytest


def test_create_list_get_rename_conversation():
    from database.db import SessionLocal, init_db
    from services.conversation_service import (
        create_conversation,
        get_conversation_detail,
        list_conversations,
        update_conversation,
    )

    init_db()
    owner = "test_owner_basic"
    with SessionLocal() as db:
        created = create_conversation(db, owner, title="初始标题")
        assert created["title"] == "初始标题"

        listed = list_conversations(db, owner)
        assert any(item["id"] == created["id"] for item in listed["items"])

        detail = get_conversation_detail(db, created["id"], owner)
        assert detail["conversation"]["id"] == created["id"]
        assert detail["messages"] == []

        renamed = update_conversation(db, created["id"], owner, title="论文压力")
        assert renamed["title"] == "论文压力"
        assert renamed["title_manually_set"] is True


@pytest.mark.asyncio
async def test_append_messages_and_title_generation_fallback(monkeypatch):
    from config import get_settings
    from database.db import SessionLocal, init_db
    from services.conversation_service import create_conversation, send_conversation_message

    monkeypatch.setenv("ARK_API_KEY", "")
    get_settings.cache_clear()
    init_db()
    owner = "test_owner_append"
    with SessionLocal() as db:
        conversation = create_conversation(db, owner)
        result = await send_conversation_message(
            db,
            conversation["id"],
            owner,
            content="我有自杀的想法，怕自己会伤害自己。",
            file_ids=[],
            checkin=None,
        )
        assert result["user_message"]["role"] == "user"
        assert result["assistant_message"]["role"] == "assistant"
        assert result["assistant_message"]["metadata"]["risk"]["level"] == "high"
        assert result["conversation"]["title"] == "危机支持"


def test_conversation_memory_risk_and_context_isolation():
    from agents.risk_agent import assess_risk
    from database.db import SessionLocal, init_db
    from services.conversation_service import create_conversation
    from services.memory_service import (
        get_memory_snapshot,
        recent_messages,
        update_profile_from_user_message,
        update_risk_state,
        record_message,
    )

    init_db()
    owner = "test_owner_isolation"
    with SessionLocal() as db:
        a = create_conversation(db, owner, title="A")
        b = create_conversation(db, owner, title="B")
        a_msg = record_message(db, a["id"], "user", "我的论文压力很大。")
        b_msg = record_message(db, b["id"], "user", "我准备找工作，简历很焦虑。")
        update_profile_from_user_message(db, a["id"], a_msg, "我的论文压力很大。")
        update_profile_from_user_message(db, b["id"], b_msg, "我准备找工作，简历很焦虑。")
        update_risk_state(db, a["id"], assess_risk("我准备好了药，今晚不想再撑。"))
        update_risk_state(db, b["id"], assess_risk("只是普通就业压力。"))

        b_recent = recent_messages(db, b["id"], limit=20)
        assert "论文" not in str(b_recent)
        assert "简历" in str(b_recent)

        a_memory = get_memory_snapshot(db, a["id"])
        b_memory = get_memory_snapshot(db, b["id"])
        assert "论文" in str(a_memory["profile"])
        assert "论文" not in str(b_memory["profile"])
        assert "就业" in str(b_memory["profile"]) or "简历" in str(b_memory["profile"])


@pytest.mark.asyncio
async def test_delete_conversation_removes_only_its_attachments(tmp_path):
    from database.db import SessionLocal, init_db
    from database.models import Attachment, utcnow
    from services.conversation_service import create_conversation, delete_conversation

    init_db()
    owner = "test_owner_delete"
    with SessionLocal() as db:
        a = create_conversation(db, owner, title="A")
        b = create_conversation(db, owner, title="B")
        a_file = tmp_path / "a.txt"
        b_file = tmp_path / "b.txt"
        a_file.write_text("a", encoding="utf-8")
        b_file.write_text("b", encoding="utf-8")
        now = utcnow()
        attach_a = f"attach_a_{uuid.uuid4().hex}"
        attach_b = f"attach_b_{uuid.uuid4().hex}"
        db.add(
            Attachment(
                file_id=attach_a,
                session_id=a["id"],
                conversation_id=a["id"],
                kind="image",
                original_name="a.jpg",
                stored_name="a.jpg",
                mime_type="image/jpeg",
                size_bytes=1,
                status="uploaded",
                local_path=str(a_file),
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.add(
            Attachment(
                file_id=attach_b,
                session_id=b["id"],
                conversation_id=b["id"],
                kind="image",
                original_name="b.jpg",
                stored_name="b.jpg",
                mime_type="image/jpeg",
                size_bytes=1,
                status="uploaded",
                local_path=str(b_file),
                created_at=now,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.commit()

        await delete_conversation(db, b["id"], owner)
        assert db.get(Attachment, attach_a) is not None
        assert db.get(Attachment, attach_b) is None
        assert a_file.exists()
        assert not b_file.exists()

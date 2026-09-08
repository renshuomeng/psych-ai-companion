import uuid


def test_global_memory_profile_crosses_conversations(monkeypatch):
    from agents.memory_agent import load_memory_context, remember_user_turn
    from agents.risk_agent import assess_risk
    from config import get_settings
    from database.db import SessionLocal, init_db
    from services.conversation_service import create_conversation

    monkeypatch.setenv("GLOBAL_MEMORY_ACROSS_CONVERSATIONS", "true")
    get_settings.cache_clear()

    init_db()
    owner = f"global_memory_owner_{uuid.uuid4().hex}"
    with SessionLocal() as db:
        first = create_conversation(db, owner, title="first")
        remember_user_turn(
            db,
            first["id"],
            "我不喜欢冥想，论文压力最大。",
            {"preferred_style": "温和陪伴", "stress_sources": ["论文"]},
            assess_risk("我不喜欢冥想，论文压力最大。"),
        )
        second = create_conversation(db, owner, title="second")
        context = load_memory_context(db, second["id"])

    assert context["snapshot"]["global_memory_enabled"] is True
    assert "论文" in str(context["snapshot"]["profile"])
    assert "冥想" in str(context["snapshot"]["profile"])
    assert "论文" not in str(context["recent_messages"])

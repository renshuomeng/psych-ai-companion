import pytest


@pytest.mark.asyncio
async def test_rag_hybrid_retrieves_source_and_rejects_unrelated():
    from database.db import SessionLocal, init_db
    from services.knowledge_ingestion_service import build_knowledge_base
    from services.retrieval_service import retrieve

    init_db()
    with SessionLocal() as db:
        await build_knowledge_base(db)
        result = await retrieve(db, "论文压力导致睡不着怎么办", session_id="test_rag")
        assert result["retrieval_status"] == "success"
        assert {item["source_id"] for item in result["retrieved_chunks"]} & {
            "kb_sleep_001",
            "kb_study_001",
        }

        unrelated = await retrieve(db, "量子计算硬件退相干参数怎么测", session_id="test_rag")
        assert unrelated["retrieval_status"] == "insufficient_evidence"


@pytest.mark.asyncio
async def test_emotion_aware_retrieval_uses_psychological_metadata():
    from database.db import SessionLocal, init_db
    from services.knowledge_ingestion_service import build_knowledge_base
    from services.retrieval_service import retrieve

    init_db()
    with SessionLocal() as db:
        await build_knowledge_base(db)
        result = await retrieve(
            db,
            "就业焦虑，简历和面试都不知道怎么开始。",
            session_id="test_emotion_rag",
            mode="emotion_aware_hybrid_rerank",
            psychological_context={
                "emotion": "anxiety",
                "cause": "career_anxiety",
                "strategy": "problem_solving",
                "risk_level": "low",
            },
        )
        assert result["retrieval_status"] == "success"
        assert result["retrieved_chunks"][0]["source_id"] == "kb_job_001"
        assert result["retrieved_chunks"][0]["psychological_score"] > 0


def test_memory_profile_and_session_isolation():
    from agents.memory_agent import remember_user_turn
    from agents.risk_agent import assess_risk
    from database.db import SessionLocal, init_db
    from services.memory_service import delete_memory, get_memory_snapshot

    init_db()
    with SessionLocal() as db:
        delete_memory(db, "memory_a")
        delete_memory(db, "memory_b")
        remember_user_turn(
            db,
            "memory_a",
            "我不喜欢冥想，论文压力最大。",
            {"preferred_style": "温和陪伴", "stress_sources": ["论文"]},
            assess_risk("我不喜欢冥想，论文压力最大。"),
        )
        a = get_memory_snapshot(db, "memory_a")
        b = get_memory_snapshot(db, "memory_b")
        assert "论文" in str(a["profile"])
        assert "冥想" in str(a["profile"])
        assert "论文" not in str(b["profile"])


def test_risk_dimensions_for_negation_and_plan():
    from agents.risk_agent import assess_risk

    high = assess_risk("我准备好了药，今晚不想再撑下去了。")
    assert high["level"] == "high"
    assert high["dimensions"]["plan"] is True
    assert high["dimensions"]["timeframe_present"] is True
    assert high["dimensions"]["means_access"] == "present"

    negated = assess_risk("我没有想过自杀，只是最近很累。")
    assert negated["level"] == "low"
    assert negated["dimensions"]["negated"] is True

    english_high = assess_risk("I want to kill myself tonight.")
    assert english_high["level"] == "high"
    assert english_high["action"] == "crisis_referral"

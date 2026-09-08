import pytest


@pytest.mark.asyncio
async def test_psychological_state_detects_thesis_pressure():
    from agents.emotion_agent import analyze_emotion
    from agents.psychological_state_analyzer import analyze_psychological_state
    from agents.risk_agent import assess_risk

    message = "论文一直拖延，我很焦虑，感觉自己完全开始不了，能不能给我一个具体方法？"
    emotion = analyze_emotion(message)
    risk = assess_risk(message)

    state = await analyze_psychological_state(message, emotion=emotion, risk=risk)

    assert state["emotion"]["primary"] in {"anxiety", "stress"}
    assert state["cause"]["category"] == "thesis"
    assert "problem_solving" in state["needs"]
    assert state["confidence"] >= 0.55


def test_strategy_planner_uses_clarification_for_low_confidence(monkeypatch):
    from config import get_settings
    from services.strategy_planner import plan_strategy

    monkeypatch.setenv("PSY_STATE_LOW_CONFIDENCE_THRESHOLD", "0.55")
    get_settings.cache_clear()

    plan = plan_strategy(
        {
            "emotion": {"primary": "neutral", "intensity": 0.35},
            "cause": {"category": "unknown"},
            "needs": ["unknown"],
            "stage": "exploration",
            "confidence": 0.38,
        },
        risk={"level": "low"},
        message="随便聊聊",
    )

    assert plan["primary_strategy"] == "clarification"
    assert plan["should_give_advice"] is False
    assert plan["should_use_rag"] is False


def test_rag_router_routes_academic_problem_solving():
    from services.rag_router import route_rag

    route = route_rag(
        message="论文拖延，想要一个小步骤",
        psychological_state={
            "emotion": {"primary": "anxiety"},
            "cause": {"category": "thesis"},
            "needs": ["problem_solving", "sense_of_control"],
            "confidence": 0.78,
        },
        strategy_plan={
            "primary_strategy": "problem_solving",
            "should_use_rag": True,
            "should_give_advice": True,
        },
        risk={"level": "low"},
    )

    assert route["should_retrieve"] is True
    assert "interventions" in route["collections"]
    assert "academic_stress" in route["metadata_filter"]["topics"]


def test_rag_router_skips_high_risk():
    from services.rag_router import route_rag

    route = route_rag(
        message="我想自杀",
        psychological_state={"confidence": 0.9, "emotion": {"primary": "sadness"}, "cause": {"category": "unknown"}},
        strategy_plan={"primary_strategy": "referral", "should_use_rag": True},
        risk={"level": "high"},
    )

    assert route["should_retrieve"] is False
    assert route["fallback"] == "safety_agent_crisis_referral"

import pytest


@pytest.mark.asyncio
async def test_llm_safety_review_revises_before_rule_pass(monkeypatch):
    from agents import safety_agent
    from config import get_settings
    from services.ark_client import ProviderResult

    monkeypatch.setenv("SAFETY_LLM_REVIEW_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_generate_text(*_args, **_kwargs):
        return ProviderResult(
            text='{"decision":"revise","reason":"diagnostic wording","safe_reply":"我不能替你下诊断，但可以陪你先梳理当下的压力。","risk_override":"","flags":["diagnosis"]}',
            provider="test_provider",
            model="test_safety_model",
            request_id="safety-test",
            usage={"total_tokens": 12},
        )

    monkeypatch.setattr(safety_agent, "generate_text", fake_generate_text)

    result = await safety_agent.review_response_async(
        {
            "risk": {"level": "low", "reason": "test", "action": "support"},
            "emotion": {"label": "stress"},
            "reply": "你得了抑郁症。",
            "interventions": [],
            "agent_trace": [],
            "provider_metadata": {},
        }
    )

    assert result["reply"] == "我不能替你下诊断，但可以陪你先梳理当下的压力。"
    assert result["provider_metadata"]["safety_review"]["decision"] == "revise"
    assert any(str(item).startswith("LLMSafetyAgent: decision=revise") for item in result["agent_trace"])
    assert any(str(item).startswith("SafetyAgent: passed") for item in result["agent_trace"])


@pytest.mark.asyncio
async def test_llm_safety_review_failure_falls_back_to_rules(monkeypatch):
    from agents import safety_agent
    from config import get_settings

    monkeypatch.setenv("SAFETY_LLM_REVIEW_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_generate_text(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(safety_agent, "generate_text", fake_generate_text)

    result = await safety_agent.review_response_async(
        {
            "risk": {"level": "low", "reason": "test", "action": "support"},
            "emotion": {"label": "stress"},
            "reply": "一定会好，我能治疗你。",
            "interventions": [],
            "agent_trace": [],
            "provider_metadata": {},
        }
    )

    assert "不能替代专业心理或医疗帮助" in result["reply"]
    assert result["provider_metadata"]["safety_review"]["status"] == "fallback_rule_safety"
    assert any("fallback to rule safety" in str(item) for item in result["agent_trace"])

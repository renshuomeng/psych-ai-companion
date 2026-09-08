import pytest


@pytest.mark.asyncio
async def test_text_only_requires_ark_when_not_high_risk(monkeypatch):
    from config import get_settings
    from agents.coordinator_agent import run_multimodal_flow
    from schemas.errors import AppError

    monkeypatch.setenv("ARK_API_KEY", "")
    monkeypatch.setenv("ENABLE_DEV_MOCK", "false")
    get_settings.cache_clear()

    with pytest.raises(AppError) as exc:
        await run_multimodal_flow(
            session_id="test",
            message="最近论文压力很大。",
            checkin=None,
            multimodal_context={"image_ocr": [], "video_ocr": []},
        )

    assert exc.value.detail.code == "ark_provider_not_configured"


@pytest.mark.asyncio
async def test_high_risk_does_not_require_ark(monkeypatch):
    from config import get_settings
    from agents.coordinator_agent import run_multimodal_flow

    monkeypatch.setenv("ARK_API_KEY", "")
    get_settings.cache_clear()

    result = await run_multimodal_flow(
        session_id="test",
        message="我想死。",
        checkin=None,
        multimodal_context={"image_ocr": [], "video_ocr": []},
    )

    assert result["risk"]["level"] == "high"
    assert result["provider_metadata"]["llm_provider"] is None

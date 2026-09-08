import pytest


@pytest.mark.asyncio
async def test_speech_provider_not_configured(monkeypatch, tmp_path):
    from config import get_settings
    from schemas.errors import AppError
    from services.speech_service import transcribe_audio

    monkeypatch.setenv("VOLC_SPEECH_API_KEY", "")
    monkeypatch.setenv("VOLC_SPEECH_APP_ID", "")
    monkeypatch.setenv("VOLC_SPEECH_ACCESS_KEY", "")
    get_settings.cache_clear()
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"not-a-real-audio")

    with pytest.raises(AppError) as exc:
        await transcribe_audio(audio, "test-session")

    assert exc.value.detail.code == "speech_provider_not_configured"

import pytest


@pytest.mark.asyncio
async def test_video_visual_falls_back_to_keyframe(monkeypatch, tmp_path):
    from schemas.errors import AppError
    from services import video_service

    video = tmp_path / "clip.mp4"
    video.write_bytes(b"fake-video")

    async def fail_upload(*args, **kwargs):
        raise AppError("provider_server_error", "video failed", "video_analysis", status_code=502)

    def fake_extract_frame(video_path, output_path, at_seconds=1.0):
        output_path.write_bytes(b"fake-frame")
        return output_path

    async def fake_analyze_image(path):
        return {
            "summary": "关键帧中人物露出笑容",
            "observable_cues": ["人物嘴角上扬，露出笑容。"],
            "visual_affect_candidates": [
                {"label": "joy", "confidence": 0.76, "evidence": "嘴角上扬"}
            ],
            "ocr_text": [],
            "safety_signals": [],
            "provider_metadata": {"llm_provider": "test"},
        }

    monkeypatch.setattr(video_service, "upload_provider_file", fail_upload)
    monkeypatch.setattr(video_service, "extract_video_frame", fake_extract_frame)
    monkeypatch.setattr(video_service, "analyze_image_file", fake_analyze_image)

    visual, metadata = await video_service._analyze_video_visual(video, 2.0)

    assert visual["visual_affect_candidates"][0]["label"] == "joy"
    assert metadata["visual_strategy"] == "fallback_keyframe"

from pathlib import Path
from typing import Any

from schemas.errors import AppError
from services.ark_client import analyze_video_with_file_id
from services.ark_file_service import upload_provider_file
from services.image_service import analyze_image_file
from services.image_service import _parse_jsonish
from services.media_service import extract_audio_to_wav, extract_video_frame, get_duration_seconds
from services.speech_service import transcribe_audio


VIDEO_ANALYSIS_PROMPT = """
请分析用户主动上传的视频，只返回 JSON：
{
  "visual_summary": "视频视觉内容概述",
  "timeline": [
    {"start_seconds": 0, "end_seconds": 10, "visual_event": "可观察画面事件", "speech": ""}
  ],
  "ocr_text": [],
  "observable_cues": [],
  "visual_affect_candidates": [
    {"label": "joy|anger|sadness|anxiety|fatigue|neutral", "confidence": 0.0, "evidence": "仅基于可观察表情线索"}
  ],
  "safety_signals": [],
  "uncertainty": "分析限制"
}
禁止把表情直接等同于真实心理状态，禁止医学诊断。
visual_affect_candidates 只描述可观察表情倾向，不代表用户真实心理状态。
"""


def _empty_visual() -> dict[str, Any]:
    return {
        "visual_summary": "",
        "timeline": [],
        "ocr_text": [],
        "observable_cues": [],
        "visual_affect_candidates": [],
        "safety_signals": [],
        "uncertainty": "暂无视频视觉分析结果。",
    }


async def _analyze_video_visual(path: Path, duration: float | None) -> tuple[dict[str, Any], dict[str, Any]]:
    provider_metadata: dict[str, Any] = {}
    try:
        provider_file = await upload_provider_file(path, purpose="vision")
        provider_file_id = provider_file.get("id") or provider_file.get("file_id")
        if not provider_file_id:
            raise AppError(
                "provider_server_error",
                "供应商 File API 未返回文件 ID。",
                "ark_file_upload",
                retryable=True,
                status_code=502,
            )

        video_result = await analyze_video_with_file_id(provider_file_id, VIDEO_ANALYSIS_PROMPT)
        visual = _parse_jsonish(video_result.text)
        provider_metadata = {
            **video_result.as_metadata(),
            "provider_file_id": provider_file_id,
            "visual_strategy": "provider_video",
        }
        return visual, provider_metadata
    except AppError as exc:
        frame_path = path.with_suffix(".keyframe.jpg")
        try:
            sample_at = min(max((duration or 2.0) / 2, 0.2), 3.0)
            extract_video_frame(path, frame_path, at_seconds=sample_at)
            frame_result = await analyze_image_file(frame_path)
            visual = {
                "visual_summary": f"关键帧分析：{frame_result.get('summary', '')}",
                "timeline": [
                    {
                        "start_seconds": round(sample_at, 2),
                        "end_seconds": round(sample_at, 2),
                        "visual_event": frame_result.get("summary", ""),
                        "speech": "",
                    }
                ],
                "ocr_text": frame_result.get("ocr_text", []),
                "observable_cues": frame_result.get("observable_cues", []),
                "visual_affect_candidates": frame_result.get("visual_affect_candidates", []),
                "safety_signals": frame_result.get("safety_signals", []),
                "uncertainty": (
                    "视频模型未完成，已使用单帧关键帧作为低权重视觉分析；"
                    "该结果不能代表完整视频或真实心理状态。"
                ),
            }
            provider_metadata = {
                **(frame_result.get("provider_metadata") or {}),
                "visual_strategy": "fallback_keyframe",
                "video_provider_error": exc.detail.model_dump(exclude_none=True),
            }
            return visual, provider_metadata
        finally:
            frame_path.unlink(missing_ok=True)


async def analyze_video_file(path: Path, session_id: str) -> dict[str, Any]:
    duration = get_duration_seconds(path, stage="video_probe")
    visual, provider_metadata = await _analyze_video_visual(path, duration)

    audio_path = path.with_suffix(".extracted.wav")
    transcript: dict[str, Any] = {"transcript": "", "utterances": [], "status": "not_found"}
    try:
        try:
            extract_audio_to_wav(path, audio_path)
            transcript = await transcribe_audio(audio_path, session_id)
        except AppError as exc:
            transcript = {
                "transcript": "",
                "utterances": [],
                "status": "failed",
                "error": exc.detail.model_dump(exclude_none=True),
            }
    finally:
        audio_path.unlink(missing_ok=True)

    return {
        "visual_summary": visual.get("visual_summary", visual.get("summary", "")),
        "timeline": visual.get("timeline", []),
        "transcript": transcript.get("transcript", ""),
        "utterances": transcript.get("utterances", []),
        "ocr_text": visual.get("ocr_text", []),
        "observable_cues": visual.get("observable_cues", []),
        "visual_affect_candidates": visual.get("visual_affect_candidates", []),
        "safety_signals": visual.get("safety_signals", []),
        "uncertainty": visual.get("uncertainty", "视频分析结果存在不确定性。"),
        "duration_seconds": duration,
        "provider_metadata": provider_metadata,
    }

import base64
import uuid
from pathlib import Path
from typing import Any

import httpx

from config import get_settings
from schemas.errors import AppError


def _headers(request_id: str) -> dict[str, str]:
    settings = get_settings()
    common = {
        "X-Api-Resource-Id": settings.volc_speech_resource_id,
        "X-Api-Request-Id": request_id,
        "X-Api-Sequence": "-1",
        "Content-Type": "application/json",
    }
    if settings.volc_speech_api_key.strip():
        return {**common, "X-Api-Key": settings.volc_speech_api_key}
    if settings.volc_speech_app_id.strip() and settings.volc_speech_access_key.strip():
        return {
            **common,
            "X-Api-App-Key": settings.volc_speech_app_id,
            "X-Api-Access-Key": settings.volc_speech_access_key,
        }
    raise AppError(
        code="speech_provider_not_configured",
        message="豆包语音服务尚未配置，请在后端 .env 设置语音 API Key。",
        stage="speech_transcription",
        retryable=False,
        status_code=503,
    )


def _extract_transcript(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    result = payload.get("result") or payload.get("data") or payload
    text = result.get("text") or result.get("transcript") or ""
    utterances = result.get("utterances") or result.get("segments") or []
    return str(text).strip(), utterances if isinstance(utterances, list) else []


async def transcribe_audio(path: Path, session_id: str) -> dict[str, Any]:
    settings = get_settings()
    request_id = uuid.uuid4().hex
    headers = _headers(request_id)
    encoded_audio = base64.b64encode(path.read_bytes()).decode("ascii")
    body = {
        "user": {"uid": session_id},
        "audio": {"data": encoded_audio},
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
        },
    }
    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(
                settings.volc_speech_flash_url,
                headers=headers,
                json=body,
            )
        except httpx.TimeoutException as exc:
            raise AppError(
                code="provider_timeout",
                message="豆包语音转写超时。",
                stage="speech_transcription",
                retryable=True,
                request_id=request_id,
                status_code=504,
            ) from exc

    provider_status = response.headers.get("X-Api-Status-Code") or response.headers.get("x-api-status-code")
    if response.status_code in {401, 403}:
        raise AppError(
            code="provider_unauthorized" if response.status_code == 401 else "provider_forbidden",
            message="豆包语音鉴权失败或无权限。",
            stage="speech_transcription",
            retryable=False,
            request_id=request_id,
            status_code=400,
        )
    if response.status_code == 429:
        raise AppError(
            code="rate_limited",
            message="豆包语音服务限流，请稍后重试。",
            stage="speech_transcription",
            retryable=True,
            request_id=request_id,
            status_code=429,
        )
    if response.status_code >= 400 or (provider_status and provider_status not in {"20000000", "0"}):
        raise AppError(
            code="provider_server_error",
            message="豆包语音服务返回错误。",
            stage="speech_transcription",
            retryable=response.status_code >= 500,
            request_id=request_id,
            status_code=502,
        )

    payload = response.json()
    transcript, utterances = _extract_transcript(payload)
    if not transcript:
        raise AppError(
            code="empty_transcript",
            message="没有识别到有效语音内容，请重新录制或上传更清晰的音频。",
            stage="speech_transcription",
            retryable=False,
            request_id=request_id,
            status_code=400,
        )

    return {
        "transcript": transcript,
        "duration_ms": None,
        "utterances": utterances,
        "provider": "volcengine_doubao_asr",
        "status": "completed",
        "request_id": request_id,
    }

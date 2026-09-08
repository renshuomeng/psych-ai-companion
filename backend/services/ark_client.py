from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from config import get_settings
from schemas.errors import AppError


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


@dataclass
class ProviderResult:
    text: str
    provider: str
    model: str
    request_id: str | None = None
    usage: dict[str, Any] | None = None
    model_id: str | None = None
    latency_ms: int | None = None
    finish_reason: str | None = None
    status: str = "completed"
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        if self.model_id is None:
            self.model_id = self.model
        if self.usage:
            prompt_tokens = self.usage.get("prompt_tokens", self.usage.get("input_tokens"))
            completion_tokens = self.usage.get("completion_tokens", self.usage.get("output_tokens"))
            if self.input_tokens is None and isinstance(prompt_tokens, int):
                self.input_tokens = prompt_tokens
            if self.output_tokens is None and isinstance(completion_tokens, int):
                self.output_tokens = completion_tokens

    def as_metadata(self) -> dict[str, Any]:
        return {
            "llm_provider": self.provider,
            "model": self.model,
            "model_id": self.model_id,
            "request_id": self.request_id,
            "usage": self.usage,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_ms": self.latency_ms,
            "finish_reason": self.finish_reason,
            "status": self.status,
        }


def _redacted_provider_error(
    status_code: int,
    stage: str,
    request_id: str | None,
    body: str,
) -> AppError:
    body_lower = body.lower()
    if status_code == 401:
        code, message, retryable = "provider_unauthorized", "火山方舟鉴权失败，请检查 ARK_API_KEY。", False
    elif status_code == 403:
        code, message, retryable = "provider_forbidden", "当前账号没有访问该模型或接口的权限。", False
    elif status_code == 404:
        code, message, retryable = "model_not_available", "模型或接口不存在，请检查模型 ID / Endpoint ID。", False
    elif status_code == 429:
        code, message, retryable = "rate_limited", "供应商限流，请稍后重试。", True
    elif "quota" in body_lower or "balance" in body_lower:
        code, message, retryable = "quota_exceeded", "供应商额度不足或余额不足。", False
    elif status_code >= 500:
        code, message, retryable = "provider_server_error", "供应商服务异常，请稍后重试。", True
    else:
        code, message, retryable = "provider_server_error", "供应商返回了无法完成请求的错误。", False

    return AppError(
        code=code,
        message=message,
        stage=stage,
        retryable=retryable,
        request_id=request_id,
        status_code=502 if status_code >= 500 else 400,
    )


def normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in messages:
        role = str(item.get("role") or "user").strip() or "user"
        content = item.get("content", "")
        normalized.append({"role": role, "content": content})
    return normalized


def _extract_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"].strip()

    choices = payload.get("choices")
    if choices and isinstance(choices, list):
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            pieces = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text") or part.get("content")
                    if isinstance(text, str):
                        pieces.append(text)
            return "\n".join(pieces).strip()

    output = payload.get("output", [])
    pieces: list[str] = []
    if isinstance(output, list):
        for item in output:
            for content in item.get("content", []) if isinstance(item, dict) else []:
                text = content.get("text") or content.get("content")
                if isinstance(text, str):
                    pieces.append(text)
    return "\n".join(pieces).strip()


def _finish_reason(payload: dict[str, Any]) -> str | None:
    choices = payload.get("choices")
    if choices and isinstance(choices, list) and isinstance(choices[0], dict):
        value = choices[0].get("finish_reason")
        return str(value) if value is not None else None
    return None


def _usage_tokens(usage: dict[str, Any] | None) -> tuple[int | None, int | None]:
    if not isinstance(usage, dict):
        return None, None
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    return (
        input_tokens if isinstance(input_tokens, int) else None,
        output_tokens if isinstance(output_tokens, int) else None,
    )


def _provider_request_id(response: httpx.Response, fallback: str) -> str:
    return (
        response.headers.get("x-request-id")
        or response.headers.get("x-tt-logid")
        or response.headers.get("x-volc-request-id")
        or fallback
    )


async def _sleep_before_retry(attempt: int) -> None:
    await asyncio.sleep(min(0.5 * (2**attempt), 2.0))


async def _post_json(
    *,
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    stage: str,
    request_id: str,
    timeout_seconds: float,
    retry_attempts: int,
) -> tuple[dict[str, Any], str, int]:
    timeout = httpx.Timeout(timeout_seconds, connect=min(10.0, timeout_seconds))
    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        last_error: AppError | None = None
        for attempt in range(retry_attempts):
            try:
                response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                last_error = AppError(
                    code="provider_timeout",
                    message="供应商请求超时。",
                    stage=stage,
                    retryable=True,
                    request_id=request_id,
                    status_code=504,
                )
                if attempt < retry_attempts - 1:
                    await _sleep_before_retry(attempt)
                    continue
                raise last_error from exc
            except httpx.TransportError as exc:
                last_error = AppError(
                    code="provider_server_error",
                    message="供应商网络请求失败。",
                    stage=stage,
                    retryable=True,
                    request_id=request_id,
                    status_code=502,
                )
                if attempt < retry_attempts - 1:
                    await _sleep_before_retry(attempt)
                    continue
                raise last_error from exc

            provider_request_id = _provider_request_id(response, request_id)
            if response.status_code < 400:
                try:
                    return response.json(), provider_request_id, int((time.perf_counter() - started) * 1000)
                except json.JSONDecodeError as exc:
                    raise AppError(
                        code="provider_server_error",
                        message="供应商返回了无法解析的数据。",
                        stage=stage,
                        retryable=False,
                        request_id=provider_request_id,
                        status_code=502,
                    ) from exc

            error = _redacted_provider_error(
                response.status_code,
                stage,
                provider_request_id,
                response.text[:1000],
            )
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < retry_attempts - 1:
                last_error = error
                await _sleep_before_retry(attempt)
                continue
            raise error

    raise last_error or AppError(
        code="provider_server_error",
        message="供应商请求失败。",
        stage=stage,
        retryable=True,
        status_code=502,
    )


def _headers(request_id: str) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.ark_api_key}",
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
    }


def _dev_mock_result(model_id: str, *, stage: str, structured: bool = False) -> ProviderResult:
    text = (
        '{"decision":"pass","reason":"dev mock","safe_reply":"","risk_override":"","flags":[]}'
        if structured
        else "dev mock result"
    )
    return ProviderResult(
        text=text,
        provider="dev_mock",
        model=model_id or "mock",
        request_id=f"dev-mock-{stage}",
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        status="mocked",
        input_tokens=0,
        output_tokens=0,
        latency_ms=0,
    )


async def chat(
    messages: list[dict[str, Any]],
    *,
    agent_name: str = "default",
    model_id: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    response_format: dict[str, Any] | None = None,
    extra_body: dict[str, Any] | None = None,
    stream: bool = False,
    stage: str = "doubao_chat_completions",
) -> ProviderResult:
    settings = get_settings()
    provider = settings.llm_provider.strip().lower()
    if provider not in {"volcengine_ark", "ark", "doubao"}:
        raise AppError(
            code="llm_provider_not_supported",
            message="当前 LLM_PROVIDER 不受 CARE-Psy Ark 客户端支持。",
            stage=stage,
            retryable=False,
            status_code=503,
        )

    selected_model = (model_id or settings.doubao_model_for_agent(agent_name)).strip()
    if not selected_model:
        raise AppError(
            code="doubao_model_not_configured",
            message="豆包模型 ID 尚未配置，请设置 DOUBAO_DEFAULT_MODEL_ID 或 DOUBAO_MODEL_ID。",
            stage=stage,
            retryable=False,
            status_code=503,
        )

    if not settings.ark_configured:
        if settings.enable_dev_mock:
            return _dev_mock_result(selected_model, stage=stage, structured=bool(response_format))
        raise AppError(
            code="ark_provider_not_configured",
            message="豆包/火山方舟服务尚未配置，请在后端 .env 设置 ARK_API_KEY。",
            stage=stage,
            retryable=False,
            status_code=503,
        )

    body: dict[str, Any] = {
        "model": selected_model,
        "messages": normalize_messages(messages),
        "stream": stream,
        "temperature": float(settings.doubao_temperature_for_agent(agent_name) if temperature is None else temperature),
    }
    token_limit = settings.doubao_max_tokens if max_tokens is None else max_tokens
    if token_limit and token_limit > 0:
        body["max_tokens"] = int(token_limit)
    if response_format:
        body["response_format"] = response_format
    if extra_body:
        body.update(extra_body)

    request_id = uuid.uuid4().hex
    url = f"{settings.ark_base_url.rstrip('/')}/chat/completions"
    data, provider_request_id, latency_ms = await _post_json(
        url=url,
        payload=body,
        headers=_headers(request_id),
        stage=stage,
        request_id=request_id,
        timeout_seconds=settings.effective_doubao_timeout_seconds,
        retry_attempts=settings.effective_doubao_retry_attempts,
    )
    text = _extract_text(data)
    if not text:
        raise AppError(
            code="provider_server_error",
            message="供应商返回内容为空。",
            stage=stage,
            retryable=True,
            request_id=provider_request_id,
            status_code=502,
        )
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
    input_tokens, output_tokens = _usage_tokens(usage)
    return ProviderResult(
        text=text,
        provider="volcengine_ark",
        model=selected_model,
        model_id=selected_model,
        request_id=provider_request_id,
        usage=usage,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        finish_reason=_finish_reason(data),
    )


def _json_schema_response_format(response_schema: dict[str, Any]) -> dict[str, Any]:
    if "schema" in response_schema and "name" in response_schema:
        payload = dict(response_schema)
    else:
        payload = {"name": "care_psy_structured_response", "schema": response_schema}
    payload.setdefault("strict", True)
    return {"type": "json_schema", "json_schema": payload}


async def generate_text(
    system_prompt: str,
    user_prompt: str,
    response_schema: dict[str, Any] | None = None,
    *,
    agent_name: str = "default",
    model_id: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ProviderResult:
    response_format = _json_schema_response_format(response_schema) if response_schema else None
    return await chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        agent_name=agent_name,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        stage="doubao_generate_text",
    )


async def _post_responses(payload: dict[str, Any], stage: str) -> ProviderResult:
    settings = get_settings()
    model_id = str(payload.get("model") or settings.effective_doubao_default_model_id)
    if not settings.ark_configured:
        if settings.enable_dev_mock:
            return _dev_mock_result(model_id, stage=stage)
        raise AppError(
            code="ark_provider_not_configured",
            message="豆包/火山方舟服务尚未配置，请在后端 .env 设置 ARK_API_KEY。",
            stage=stage,
            retryable=False,
            status_code=503,
        )

    request_id = uuid.uuid4().hex
    url = f"{settings.ark_base_url.rstrip('/')}/responses"
    data, provider_request_id, latency_ms = await _post_json(
        url=url,
        payload=payload,
        headers=_headers(request_id),
        stage=stage,
        request_id=request_id,
        timeout_seconds=settings.effective_doubao_timeout_seconds,
        retry_attempts=settings.effective_doubao_retry_attempts,
    )
    text = _extract_text(data)
    if not text:
        raise AppError(
            code="provider_server_error",
            message="供应商返回内容为空。",
            stage=stage,
            retryable=True,
            request_id=provider_request_id,
            status_code=502,
        )
    usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
    input_tokens, output_tokens = _usage_tokens(usage)
    return ProviderResult(
        text=text,
        provider="volcengine_ark",
        model=model_id,
        model_id=model_id,
        request_id=provider_request_id,
        usage=usage,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        finish_reason=_finish_reason(data),
    )


async def analyze_image(image_path: Path, prompt: str) -> ProviderResult:
    settings = get_settings()
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(image_path.suffix.lower(), "image/jpeg")
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    payload = {
        "model": settings.doubao_vision_model_id,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": f"data:{mime};base64,{encoded}"},
                ],
            }
        ],
    }
    return await _post_responses(payload, "image_analysis")


async def analyze_video_with_file_id(provider_file_id: str, prompt: str) -> ProviderResult:
    settings = get_settings()
    payload = {
        "model": settings.doubao_video_model_id,
        "input": [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_file", "file_id": provider_file_id},
                ],
            }
        ],
    }
    return await _post_responses(payload, "video_analysis")

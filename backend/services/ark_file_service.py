from pathlib import Path
from typing import Any

import httpx

from config import get_settings
from schemas.errors import AppError


async def upload_provider_file(path: Path, purpose: str = "assistants") -> dict[str, Any]:
    settings = get_settings()
    if not settings.ark_configured:
        raise AppError(
            code="ark_provider_not_configured",
            message="火山方舟 File API 尚未配置，请在后端 .env 设置 ARK_API_KEY。",
            stage="ark_file_upload",
            retryable=False,
            status_code=503,
        )

    url = f"{settings.ark_base_url.rstrip('/')}/files"
    headers = {"Authorization": f"Bearer {settings.ark_api_key}"}
    timeout = httpx.Timeout(settings.request_timeout_seconds, connect=10)

    async with httpx.AsyncClient(timeout=timeout) as client:
        with path.open("rb") as handle:
            response = await client.post(
                url,
                headers=headers,
                data={"purpose": purpose},
                files={"file": (path.name, handle, "application/octet-stream")},
            )

    request_id = response.headers.get("x-request-id")
    if response.status_code == 401:
        raise AppError("provider_unauthorized", "火山方舟鉴权失败。", "ark_file_upload", request_id=request_id, status_code=400)
    if response.status_code == 403:
        raise AppError("provider_forbidden", "当前账号没有 File API 权限。", "ark_file_upload", request_id=request_id, status_code=400)
    if response.status_code == 429:
        raise AppError(
            "rate_limited",
            "供应商限流，请稍后重试。",
            "ark_file_upload",
            retryable=True,
            request_id=request_id,
            retry_after_seconds=60,
            status_code=429,
        )
    if response.status_code >= 400:
        raise AppError("provider_server_error", "供应商 File API 调用失败。", "ark_file_upload", request_id=request_id, status_code=502)

    return response.json()


async def delete_provider_file(provider_file_id: str) -> None:
    settings = get_settings()
    if not settings.ark_configured or not provider_file_id:
        return

    url = f"{settings.ark_base_url.rstrip('/')}/files/{provider_file_id}"
    headers = {"Authorization": f"Bearer {settings.ark_api_key}"}
    async with httpx.AsyncClient(timeout=20) as client:
        await client.delete(url, headers=headers)

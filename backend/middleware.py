import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from config import get_settings
from services.auth_service import current_access_session
from services.rate_limit_service import check_request_rate_limit


AUTH_EXEMPT_PATHS = {
    "/api/auth/access",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/register",
    "/api/auth/session",
    "/api/health",
    "/api/live",
    "/api/ready",
}


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    stage: str,
    request_id: str,
    retryable: bool = False,
    retry_after_seconds: int | None = None,
) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "stage": stage,
            "retryable": retryable,
            "request_id": request_id,
        }
    }
    if retry_after_seconds is not None:
        payload["error"]["retry_after_seconds"] = retry_after_seconds
    headers = {"X-Request-ID": request_id}
    if retry_after_seconds is not None:
        headers["Retry-After"] = str(retry_after_seconds)
    return JSONResponse(status_code=status_code, content=payload, headers=headers)


class PublicAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()

        rate_result = check_request_rate_limit(request)
        if not rate_result.allowed:
            return _error_response(
                status_code=429,
                code="rate_limited",
                message="请求过于频繁，请稍后再试。",
                stage=rate_result.limit_name or "rate_limit",
                retryable=True,
                retry_after_seconds=rate_result.retry_after_seconds,
                request_id=request_id,
            )

        settings = get_settings()
        if (
            settings.public_access_enabled
            and request.url.path.startswith("/api/")
            and request.url.path.rstrip("/") not in AUTH_EXEMPT_PATHS
            and current_access_session(request) is None
        ):
            return _error_response(
                status_code=401,
                code="access_required",
                message="请先输入演示访问码。",
                stage="public_access",
                retryable=False,
                request_id=request_id,
            )

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(round((time.perf_counter() - start) * 1000, 2))
        return response

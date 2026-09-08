from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass

from fastapi import Request

from config import get_settings
from services.auth_service import current_access_session


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int = 0
    limit_name: str = ""


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._minute_counts: dict[tuple[str, str, int], int] = defaultdict(int)
        self._daily_counts: dict[tuple[str, int], int] = defaultdict(int)

    def _cleanup(self, now: int) -> None:
        current_minute = now // 60
        stale_minutes = [
            key for key in self._minute_counts if key[2] < current_minute - 2
        ]
        for key in stale_minutes:
            self._minute_counts.pop(key, None)

        current_day = now // 86400
        stale_days = [key for key in self._daily_counts if key[1] < current_day - 1]
        for key in stale_days:
            self._daily_counts.pop(key, None)

    def check(self, *, key: str, bucket: str, limit: int, now: int) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(True)
        minute = now // 60
        count_key = (bucket, key, minute)
        self._minute_counts[count_key] += 1
        if self._minute_counts[count_key] > limit:
            return RateLimitResult(
                False,
                retry_after_seconds=60 - (now % 60),
                limit_name=bucket,
            )
        return RateLimitResult(True)

    def check_daily(self, *, ip: str, limit: int, now: int) -> RateLimitResult:
        if limit <= 0:
            return RateLimitResult(True)
        day = now // 86400
        key = (ip, day)
        self._daily_counts[key] += 1
        if self._daily_counts[key] > limit:
            return RateLimitResult(
                False,
                retry_after_seconds=86400 - (now % 86400),
                limit_name="daily_ip",
            )
        return RateLimitResult(True)


rate_limiter = InMemoryRateLimiter()


def client_ip(request: Request) -> str:
    settings = get_settings()
    direct_host = request.client.host if request.client else "unknown"
    if direct_host in settings.parsed_trusted_proxy_hosts:
        for header_name in ("cf-connecting-ip", "true-client-ip"):
            value = request.headers.get(header_name)
            if value:
                return value.strip()
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
    return direct_host


def classify_rate_limit_path(path: str) -> tuple[str, int] | None:
    settings = get_settings()
    if path.startswith("/api/auth/access"):
        return ("auth_access", settings.rate_limit_auth_per_minute)
    if path.startswith("/api/files/upload"):
        return ("upload", settings.rate_limit_upload_per_minute)
    if path.startswith("/api/chat") or path.startswith("/api/multimodal/jobs"):
        return ("chat", settings.rate_limit_chat_per_minute)
    return None


def check_request_rate_limit(request: Request) -> RateLimitResult:
    classification = classify_rate_limit_path(request.url.path)
    if not classification:
        return RateLimitResult(True)

    now = int(time.time())
    settings = get_settings()
    ip = client_ip(request)
    rate_limiter._cleanup(now)

    daily = rate_limiter.check_daily(
        ip=ip,
        limit=settings.max_daily_requests_per_ip,
        now=now,
    )
    if not daily.allowed:
        return daily

    bucket, limit = classification
    access = current_access_session(request)
    session_key = access["sid"] if access else "anonymous"
    combined_key = f"{ip}:{session_key}"
    return rate_limiter.check(key=combined_key, bucket=bucket, limit=limit, now=now)

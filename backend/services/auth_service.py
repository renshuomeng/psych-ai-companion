import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import Request

from config import get_settings


ACCESS_COOKIE_NAME = "psych_ai_access"
_RUNTIME_SECRET = secrets.token_urlsafe(32)


def _b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def _sign(payload: str) -> str:
    settings = get_settings()
    secret = (settings.public_session_secret or _RUNTIME_SECRET).encode("utf-8")
    return hmac.new(secret, payload.encode("ascii"), hashlib.sha256).hexdigest()


def create_access_token(session_id: str, expires_at: int) -> str:
    payload = {
        "sid": session_id,
        "exp": expires_at,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{encoded}.{_sign(encoded)}"


def verify_access_token(token: str | None) -> dict[str, Any] | None:
    if not token or "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(encoded), signature):
        return None
    try:
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if int(payload.get("exp", 0)) <= int(time.time()):
        return None
    if not isinstance(payload.get("sid"), str) or not payload["sid"]:
        return None
    return payload


def current_access_session(request: Request) -> dict[str, Any] | None:
    return verify_access_token(request.cookies.get(ACCESS_COOKIE_NAME))


def cookie_secure_for_request(request: Request) -> bool:
    settings = get_settings()
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if request.url.scheme == "https" or forwarded_proto.lower() == "https":
        return True
    if settings.app_env == "production":
        return True
    return False


def session_expires_at_timestamp() -> int:
    settings = get_settings()
    return int(time.time() + settings.public_session_hours * 3600)


def timestamp_to_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def hash_session_id(session_id: str) -> str:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()
    return digest[:16]

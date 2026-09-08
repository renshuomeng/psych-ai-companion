import json
import os
import time
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


ROOT = Path(__file__).resolve().parents[1]


def read_env_value(name: str) -> str:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return os.environ.get(name, "")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    return os.environ.get(name, "")


def request_json(opener, method: str, url: str, payload: dict | None = None) -> tuple[int, dict, float]:
    started = time.perf_counter()
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with opener.open(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body), time.perf_counter() - started
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"error": {"code": "non_json_error"}}
        return exc.code, payload, time.perf_counter() - started


def report(name: str, status: int, payload: dict, duration: float) -> None:
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = error.get("code", "ok" if status < 400 else "unknown_error")
    print(f"{name}: status={status} code={code} duration_ms={round(duration * 1000)}")


def main() -> int:
    base_url = os.environ.get("PUBLIC_DEMO_URL", "http://127.0.0.1:8001").rstrip("/")
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    status, payload, duration = request_json(opener, "GET", f"{base_url}/api/health")
    report("health", status, payload, duration)
    if status >= 500:
        return 1

    session_status, session_payload, session_duration = request_json(
        opener, "GET", f"{base_url}/api/auth/session"
    )
    report("auth_session", session_status, session_payload, session_duration)
    if session_payload.get("access_required") and not session_payload.get("authenticated"):
        access_code = read_env_value("PUBLIC_ACCESS_CODE")
        if not access_code:
            print("auth_access: status=skipped code=missing_public_access_code duration_ms=0")
            return 1
        status, payload, duration = request_json(
            opener,
            "POST",
            f"{base_url}/api/auth/access",
            {"access_code": access_code},
        )
        report("auth_access", status, payload, duration)
        if status >= 400:
            return 1

    status, payload, duration = request_json(
        opener,
        "POST",
        f"{base_url}/api/chat/multimodal",
        {
            "session_id": "smoke-public",
            "message": "最近论文压力有点大，请给一个简短建议。",
            "file_ids": [],
            "checkin": {"stress_score": 6, "stress_sources": ["论文"], "preferred_style": "温和陪伴"},
        },
    )
    report("multimodal_text", status, payload, duration)
    return 0 if status < 500 else 1


if __name__ == "__main__":
    raise SystemExit(main())

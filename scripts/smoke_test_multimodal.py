import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]


def post_json(url: str, payload: dict) -> tuple[int, dict, float]:
    started = time.perf_counter()
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            return response.status, json.loads(response.read().decode("utf-8")), time.perf_counter() - started
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except json.JSONDecodeError:
            payload = {"error": {"code": "non_json_error"}}
        return exc.code, payload, time.perf_counter() - started


def report(name: str, status: int, payload: dict, duration: float) -> None:
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    code = error.get("code", "ok" if status < 400 else "unknown_error")
    print(f"{name}: status={status} code={code} duration_ms={round(duration * 1000)}")


def main() -> int:
    base_url = os.environ.get("PUBLIC_DEMO_URL", "http://127.0.0.1:8001").rstrip("/")
    status, payload, duration = post_json(
        f"{base_url}/api/chat/multimodal",
        {
            "session_id": "smoke-multimodal",
            "message": "最近就业准备让我有些紧张。",
            "file_ids": [],
            "checkin": {"stress_score": 5, "stress_sources": ["就业"], "preferred_style": "温和陪伴"},
        },
    )
    report("multimodal_text_only", status, payload, duration)
    return 0 if status < 500 else 1


if __name__ == "__main__":
    raise SystemExit(main())

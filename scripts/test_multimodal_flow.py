import json
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from config import get_settings


def main() -> int:
    settings = get_settings()
    url = f"http://127.0.0.1:{settings.backend_port}/api/chat/multimodal"
    payload = {
        "session_id": "manual-test",
        "message": "最近论文压力很大，晚上也睡不着。",
        "file_ids": [],
        "checkin": {
            "stress_score": 7,
            "stress_sources": ["论文", "睡眠"],
            "preferred_style": "温和陪伴",
        },
    }
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            print(response.read().decode("utf-8")[:1000])
    except HTTPError as exc:
        print(exc.read().decode("utf-8"))
        return 1
    except Exception as exc:
        print(f"Request failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

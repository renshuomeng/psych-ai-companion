from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "backend"))

import _bootstrap  # noqa: F401,E402
from kb_v2_catalog import utc_now_iso  # noqa: E402
from services.knowledge_source_registry import load_knowledge_source_registry  # noqa: E402


def _head_or_get(url: str, timeout: int = 12) -> tuple[str, dict[str, Any]]:
    headers = {"User-Agent": "CARE-Psy-KB-UpdateCheck/2.0"}
    try:
        response = requests.head(url, allow_redirects=True, timeout=timeout, headers=headers)
        if response.status_code in {405, 403} or response.status_code >= 500:
            response = requests.get(url, allow_redirects=True, timeout=timeout, headers=headers, stream=True)
            content = next(response.iter_content(chunk_size=65536), b"")
            sample_sha256 = hashlib.sha256(content).hexdigest() if content else ""
        else:
            sample_sha256 = ""
        return "ok", {
            "status_code": response.status_code,
            "final_url": response.url,
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
            "content_length": response.headers.get("Content-Length", ""),
            "content_type": response.headers.get("Content-Type", ""),
            "sample_sha256": sample_sha256,
        }
    except Exception as exc:
        return "error", {"error": type(exc).__name__, "message": str(exc)}


def check_updates(registry_path: str | Path | None = None, *, limit: int | None = None) -> dict[str, Any]:
    registry = load_knowledge_source_registry(registry_path)
    rows: list[dict[str, Any]] = []
    sources = registry.sources[:limit] if limit else registry.sources
    for source in sources:
        status, info = _head_or_get(source.official_page_url)
        previous = source.raw.get("last_checked_at") or ""
        rows.append(
            {
                "source_id": source.id,
                "title": source.title,
                "organization": source.organization,
                "official_url": source.official_page_url,
                "check_status": status,
                "last_checked_at_previous": previous,
                "checked_at": utc_now_iso(),
                "http_status": info.get("status_code", ""),
                "etag": info.get("etag", ""),
                "last_modified": info.get("last_modified", ""),
                "content_length": info.get("content_length", ""),
                "content_type": info.get("content_type", ""),
                "sample_sha256": info.get("sample_sha256", ""),
                "error": info.get("message", ""),
                "changed_hint": "unknown" if status == "error" else "check_headers_or_hash",
            }
        )
    report = {
        "created_at": utc_now_iso(),
        "registry": registry.registry_name,
        "sources_checked": len(rows),
        "ok": sum(1 for row in rows if row["check_status"] == "ok"),
        "errors": sum(1 for row in rows if row["check_status"] == "error"),
        "rows": rows,
    }
    report_path = registry.paths["reports"] / "source_update_check.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check official source URLs for status/update hints.")
    parser.add_argument("--registry", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = check_updates(args.registry, limit=args.limit)
    if args.json:
        print(json.dumps({k: v for k, v in report.items() if k != "rows"}, ensure_ascii=False, indent=2))
    else:
        print(f"sources_checked: {report['sources_checked']}")
        print(f"ok: {report['ok']}")
        print(f"errors: {report['errors']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

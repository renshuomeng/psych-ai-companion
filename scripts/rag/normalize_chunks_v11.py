from __future__ import annotations

import argparse
import json
from typing import Any

from kb_v11_utils import (
    CHUNK_STATUSES,
    chunk_status_path,
    enrich_chunk_v11,
    load_registry,
    read_jsonl,
    write_jsonl_atomic,
)


V11_FIELDS = [
    "content_sha256",
    "document_id",
    "document_sha256",
    "chunk_type",
    "source_authority",
    "review_priority",
    "download_status",
    "manual_fallback_allowed",
    "expected_collection",
]


def normalize_chunks(registry_path: str, *, dry_run: bool = False) -> dict[str, Any]:
    registry = load_registry(registry_path)
    status_reports: dict[str, Any] = {}
    for status in CHUNK_STATUSES:
        path = chunk_status_path(registry, status)
        rows = read_jsonl(path)
        normalized = [enrich_chunk_v11({**row, "review_status": row.get("review_status") or status}, registry) for row in rows]
        changed_rows = 0
        added_fields = {field: 0 for field in V11_FIELDS}
        for before, after in zip(rows, normalized):
            if before != after:
                changed_rows += 1
            for field in V11_FIELDS:
                if before.get(field) in (None, "", []) and after.get(field) not in (None, "", []):
                    added_fields[field] += 1
        if not dry_run:
            write_jsonl_atomic(path, normalized)
        status_reports[status] = {
            "path": path.as_posix(),
            "rows": len(rows),
            "changed_rows": changed_rows,
            "added_fields": added_fields,
            "written": not dry_run,
        }
    return {"dry_run": dry_run, "statuses": status_reports}


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize existing CARE-Psy RAG chunks to V1.1 metadata fields.")
    parser.add_argument("--registry", default="backend/data/knowledge_base/sources/knowledge_sources_v1.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = normalize_chunks(args.registry, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"dry_run: {report['dry_run']}")
        for status, item in report["statuses"].items():
            print(f"{status}: rows={item['rows']} changed={item['changed_rows']} written={item['written']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

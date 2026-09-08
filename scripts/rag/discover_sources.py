from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "backend"))

from kb_v2_catalog import CANDIDATES, REPORTS_DIR, utc_now_iso  # noqa: E402


CSV_FIELDS = [
    "candidate_id",
    "title",
    "organization",
    "official_url",
    "asset_url",
    "year",
    "language",
    "source_type",
    "population",
    "topics",
    "intended_collection",
    "use_mode",
    "authority_level",
    "evidence_level",
    "license",
    "downloadable",
    "robots_allowed",
    "authentication_required",
    "estimated_size",
    "existing_overlap",
    "freshness",
    "source_quality_score",
    "decision",
    "decision_reason",
]


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def write_candidates(report_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    rows = sorted(CANDIDATES, key=lambda item: (-int(item.get("source_quality_score") or 0), item["candidate_id"]))
    csv_path = report_dir / "source_candidates.csv"
    json_path = report_dir / "source_candidates.json"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})
    json_path.write_text(json.dumps({"created_at": utc_now_iso(), "candidates": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    decisions: dict[str, int] = {}
    organizations: dict[str, int] = {}
    for item in rows:
        decisions[str(item.get("decision"))] = decisions.get(str(item.get("decision")), 0) + 1
        organizations[str(item.get("organization"))] = organizations.get(str(item.get("organization")), 0) + 1
    return {
        "created_at": utc_now_iso(),
        "candidates": len(rows),
        "decisions": decisions,
        "organizations": organizations,
        "csv": csv_path.as_posix(),
        "json": json_path.as_posix(),
        "note": "Discovery is candidate generation only; no source was downloaded.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Create CARE-Psy Knowledge Base V2 source candidates.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = write_candidates()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"candidates: {report['candidates']}")
        print(f"decisions: {report['decisions']}")
        print(f"csv: {report['csv']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

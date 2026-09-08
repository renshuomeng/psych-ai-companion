from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from kb_v11_utils import (
    all_chunks,
    bm25_document_count,
    chroma_collection_counts,
    chunk_quality_issues,
    counters_for,
    find_duplicate_content,
    load_chunks_by_status,
    load_registry,
    registry_source_map,
    utc_now_iso,
    write_json_atomic,
    write_markdown,
)

from services.rag_v1_index_service import bm25_dir_for


CORE_TOPICS = {
    "academic_stress",
    "procrastination",
    "perfectionism",
    "sleep",
    "anxiety",
    "worry",
    "rumination",
    "self_compassion",
    "distress_tolerance",
    "relationships",
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _topics_for(chunk: dict[str, Any]) -> set[str]:
    topics = chunk.get("topics") or []
    if isinstance(topics, str):
        topics = [item.strip() for item in topics.replace("，", ",").split(",") if item.strip()]
    values = {str(item) for item in topics if str(item).strip()}
    if chunk.get("topic"):
        values.add(str(chunk["topic"]))
    return values


def _source_balance(chunks: list[dict[str, Any]], source_map: dict[str, Any]) -> list[dict[str, Any]]:
    counts = Counter(str(chunk.get("source_id") or "") for chunk in chunks)
    rows: list[dict[str, Any]] = []
    for source_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        source = source_map.get(source_id)
        rows.append(
            {
                "source_id": source_id,
                "title": source.title if source else "",
                "organization": source.organization if source else "",
                "target_collection": source.target_collection if source else "",
                "chunks": count,
                "share": round(count / max(len(chunks), 1), 4),
                "review_priority": (source.raw.get("review_priority") if source else ""),
                "source_authority": (source.raw.get("source_authority") if source else ""),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _collection_completeness(registry: Any, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(str(chunk.get("target_collection") or "") for chunk in chunks)
    rows: list[dict[str, Any]] = []
    for collection in sorted(registry.collections):
        rows.append(
            {
                "collection": collection,
                "chunks": counts.get(collection, 0),
                "status": "present" if counts.get(collection, 0) else "empty",
            }
        )
    return rows


def _approved_topic_coverage(approved: list[dict[str, Any]]) -> dict[str, Any]:
    covered = set()
    for chunk in approved:
        covered.update(_topics_for(chunk) & CORE_TOPICS)
    missing = sorted(CORE_TOPICS - covered)
    return {
        "core_topics": sorted(CORE_TOPICS),
        "covered": sorted(covered),
        "missing": missing,
        "coverage": round(len(covered) / max(len(CORE_TOPICS), 1), 4),
    }


def build_health_report(registry_path: str | Path | None = None) -> dict[str, Any]:
    registry = load_registry(registry_path)
    reports_dir = registry.paths["reports"]
    grouped = load_chunks_by_status(registry)
    chunks = all_chunks(grouped)
    source_map = registry_source_map(registry)
    download_summary = _load_json(reports_dir / "download_summary.json")
    build_report = _load_json(reports_dir / "build_report.json")
    staging_bm25_dir = bm25_dir_for(registry.paths["indexes_bm25"], "staging", require_existing=True)
    production_bm25_dir = bm25_dir_for(registry.paths["indexes_bm25"], "production", require_existing=True)
    chroma_counts = chroma_collection_counts(registry.paths["indexes_chroma"])
    duplicate_rows = find_duplicate_content(chunks)
    quality_rows = chunk_quality_issues(chunks)
    balance_rows = _source_balance(chunks, source_map)
    collection_rows = _collection_completeness(registry, chunks)
    approved = grouped["approved"]
    pending = grouped["pending"]
    rejected = grouped["rejected"]
    failed_sources = [
        item
        for item in download_summary.get("by_source", [])
        if str(item.get("status") or "").lower() == "failed"
    ]
    partial_sources = [
        item
        for item in download_summary.get("by_source", [])
        if str(item.get("status") or "").lower() == "partial"
    ]
    approved_coverage = _approved_topic_coverage(approved)
    metadata_missing_counts = Counter()
    required_metadata = ["content_sha256", "document_id", "chunk_type", "source_authority", "review_priority"]
    for chunk in chunks:
        for key in required_metadata:
            if chunk.get(key) in (None, "", []):
                metadata_missing_counts[key] += 1
    staging_ready = bool(chunks) and bm25_document_count(staging_bm25_dir) > 0
    production_ready = bool(approved) and approved_coverage["coverage"] >= 0.5 and bm25_document_count(production_bm25_dir) > 0
    report = {
        "created_at": utc_now_iso(),
        "registry": {
            "name": registry.registry_name,
            "version": registry.version,
            "sources": len(registry.sources),
            "auto_download_sources": len(registry.auto_download_sources),
            "collections": sorted(registry.collections),
        },
        "chunk_counts": {
            "pending": len(pending),
            "approved": len(approved),
            "rejected": len(rejected),
            "total": len(chunks),
            **counters_for(chunks),
        },
        "download": {
            "successful_sources": download_summary.get("successful_sources", 0),
            "partial_sources": len(partial_sources),
            "failed_sources": len(failed_sources),
            "failed_source_ids": [item.get("source_id") for item in failed_sources],
        },
        "indexes": {
            "bm25_staging_documents": bm25_document_count(staging_bm25_dir),
            "bm25_production_documents": bm25_document_count(production_bm25_dir),
            "bm25_staging_dir": staging_bm25_dir.as_posix(),
            "bm25_production_dir": production_bm25_dir.as_posix(),
            "chroma_collections": chroma_counts,
        },
        "metadata": {
            "missing_counts": dict(metadata_missing_counts),
            "quality_issue_sample_count": len(quality_rows),
            "duplicate_content_groups_sample_count": len(duplicate_rows),
        },
        "coverage": {
            "collections": collection_rows,
            "approved_core_topics": approved_coverage,
        },
        "readiness": {
            "staging_ready": staging_ready,
            "production_ready": production_ready,
            "production_blockers": [
                reason
                for reason, blocked in [
                    ("no_approved_chunks", not approved),
                    ("approved_core_topic_coverage_below_50_percent", approved_coverage["coverage"] < 0.5),
                    ("production_bm25_index_empty", bm25_document_count(production_bm25_dir) == 0),
                ]
                if blocked
            ],
        },
        "source_balance_csv": (reports_dir / "source_balance_report.csv").as_posix(),
        "chunk_quality_csv": (reports_dir / "chunk_quality_report.csv").as_posix(),
        "dedup_report_json": (reports_dir / "dedup_report.json").as_posix(),
        "build_report_created_at": build_report.get("created_at", ""),
    }
    _write_csv(reports_dir / "source_balance_report.csv", balance_rows)
    _write_csv(reports_dir / "chunk_quality_report.csv", quality_rows)
    write_json_atomic(reports_dir / "dedup_report.json", {"duplicates": duplicate_rows})
    write_json_atomic(reports_dir / "knowledge_base_v11_report.json", report)
    write_markdown_report(registry, report, reports_dir / "knowledge_base_v11_report.md")
    return report


def write_markdown_report(registry: Any, report: dict[str, Any], path: Path) -> None:
    chunk_counts = report["chunk_counts"]
    download = report["download"]
    indexes = report["indexes"]
    readiness = report["readiness"]
    lines = [
        "# CARE-Psy Knowledge Base V1.1 Health Report",
        "",
        f"- Created at: {report['created_at']}",
        f"- Registry: {registry.registry_name}",
        f"- Sources: {report['registry']['sources']}",
        f"- Chunks: {chunk_counts['total']} (pending {chunk_counts['pending']}, approved {chunk_counts['approved']}, rejected {chunk_counts['rejected']})",
        f"- Download: success {download['successful_sources']}, partial {download['partial_sources']}, failed {download['failed_sources']}",
        f"- BM25 staging documents: {indexes['bm25_staging_documents']}",
        f"- BM25 production documents: {indexes['bm25_production_documents']}",
        f"- Staging ready: {readiness['staging_ready']}",
        f"- Production ready: {readiness['production_ready']}",
        "",
        "## Production Blockers",
    ]
    if readiness["production_blockers"]:
        lines.extend(f"- {item}" for item in readiness["production_blockers"])
    else:
        lines.append("- None.")
    lines.extend(["", "## Collection Completeness"])
    for row in report["coverage"]["collections"]:
        lines.append(f"- {row['collection']}: {row['chunks']} ({row['status']})")
    lines.extend(["", "## Approved Core Topic Coverage"])
    coverage = report["coverage"]["approved_core_topics"]
    lines.append(f"- Coverage: {coverage['coverage']}")
    lines.append(f"- Covered: {', '.join(coverage['covered']) if coverage['covered'] else 'none'}")
    lines.append(f"- Missing: {', '.join(coverage['missing']) if coverage['missing'] else 'none'}")
    lines.extend(["", "## Failed Sources"])
    for source_id in download["failed_source_ids"]:
        source = next((item for item in registry.sources if item.id == source_id), None)
        title = source.title if source else ""
        lines.append(f"- {source_id}: {title}")
    if not download["failed_source_ids"]:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Generated Files",
            f"- {report['source_balance_csv']}",
            f"- {report['chunk_quality_csv']}",
            f"- {report['dedup_report_json']}",
        ]
    )
    write_markdown(path, lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CARE-Psy Knowledge Base health checks.")
    parser.add_argument("--registry", default=None, help="Registry path. Defaults to V2 knowledge_sources.yaml when present, otherwise V1.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_health_report(args.registry)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"staging_ready: {report['readiness']['staging_ready']}")
        print(f"production_ready: {report['readiness']['production_ready']}")
        print(f"chunks: {report['chunk_counts']['total']}")
        print(f"approved: {report['chunk_counts']['approved']}")
        print(f"pending: {report['chunk_counts']['pending']}")
        print(f"report: {load_registry(args.registry).paths['reports'] / 'knowledge_base_v11_report.md'}")
    return 0 if report["readiness"]["staging_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

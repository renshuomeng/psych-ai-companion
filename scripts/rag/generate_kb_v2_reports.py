from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rag"))
sys.path.insert(0, str(ROOT / "backend"))

import _bootstrap  # noqa: F401,E402
from kb_v2_catalog import COVERAGE_MATRIX, utc_now_iso  # noqa: E402
from kb_v11_utils import (  # noqa: E402
    all_chunks,
    bm25_document_count,
    chunk_quality_issues,
    chroma_collection_counts,
    counters_for,
    find_duplicate_content,
    load_chunks_by_status,
    load_registry,
    write_json_atomic,
    write_markdown,
)
from services.rag_v1_index_service import bm25_dir_for  # noqa: E402


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, "", []):
        return []
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return [str(value)]


def _tags(chunk: dict[str, Any], field: str) -> set[str]:
    values = set(_as_list(chunk.get(field)))
    if field == "topic_tags":
        values.update(_as_list(chunk.get("topics")))
        if chunk.get("topic"):
            values.add(str(chunk["topic"]))
    return values


def _rating(trusted_sources: int, direct_chunks: int, *, chinese_chunks: int = 0) -> str:
    if trusted_sources >= 3 and direct_chunks >= 12:
        return "Strong"
    if trusted_sources >= 2 and direct_chunks >= 5:
        return "Adequate"
    if trusted_sources >= 1 and direct_chunks >= 1:
        return "Weak" if chinese_chunks == 0 else "Adequate"
    return "Missing"


def _coverage_for_labels(chunks: list[dict[str, Any]], labels: list[str], field: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in labels:
        matched = [chunk for chunk in chunks if label in _tags(chunk, field)]
        trusted_sources = {str(chunk.get("source_id") or "") for chunk in matched if chunk.get("source_id")}
        direct = [chunk for chunk in matched if str(chunk.get("use_mode") or "") in {"direct_user_support", "psychoeducation_only"}]
        chinese = [chunk for chunk in matched if str(chunk.get("language") or "").lower().startswith("zh")]
        rows.append(
            {
                "label": label,
                "rating": _rating(len(trusted_sources), len(direct), chinese_chunks=len(chinese)),
                "trusted_source_count": len(trusted_sources),
                "chunk_count": len(matched),
                "direct_or_psychoeducation_chunks": len(direct),
                "chinese_chunks": len(chinese),
                "source_ids": sorted(trusted_sources)[:10],
            }
        )
    return rows


def _source_registry_coverage(registry: Any, labels: list[str], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    source_field = {
        "topic_tags": "topic_tags",
        "population_tags": "population_tags",
        "life_stage_tags": "life_stage_tags",
    }.get(field, field)
    for label in labels:
        counts[label] = sum(1 for source in registry.sources if label in _as_list(source.raw.get(source_field)))
    return counts


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = list(rows[0].keys())
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, ensure_ascii=False) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def _review_row(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chunk_id": chunk.get("chunk_id"),
        "source_id": chunk.get("source_id"),
        "title": chunk.get("title"),
        "collection": chunk.get("target_collection"),
        "use_mode": chunk.get("use_mode"),
        "risk_scope": chunk.get("risk_scope"),
        "population_tags": _as_list(chunk.get("population_tags")),
        "topic_tags": _as_list(chunk.get("topic_tags") or chunk.get("topics")),
        "language": chunk.get("language"),
        "review_status": chunk.get("review_status"),
        "char_count": chunk.get("char_count"),
        "content_preview": str(chunk.get("content") or "")[:240].replace("\n", " "),
        "review_decision": "",
        "review_comment": "",
    }


def _write_review_batches(reports_dir: Path, chunks: list[dict[str, Any]]) -> dict[str, str]:
    batches = {
        "review_safety.csv": [
            chunk for chunk in chunks if str(chunk.get("use_mode") or "") == "safety_only" or str(chunk.get("target_collection") or "") == "safety"
        ],
        "review_children.csv": [
            chunk for chunk in chunks if {"children", "adolescents"} & set(_as_list(chunk.get("population_tags")))
        ],
        "review_interventions.csv": [
            chunk for chunk in chunks if str(chunk.get("use_mode") or "") == "direct_user_support"
        ],
        "review_chinese.csv": [
            chunk for chunk in chunks if str(chunk.get("language") or "").lower().startswith("zh")
        ],
    }
    paths: dict[str, str] = {}
    for name, rows in batches.items():
        path = reports_dir / name
        _write_csv(path, [_review_row(chunk) for chunk in rows[:500]])
        paths[name] = path.as_posix()
    return paths


def build_reports(registry_path: str | Path | None = None) -> dict[str, Any]:
    registry = load_registry(registry_path)
    matrix = _load_yaml(COVERAGE_MATRIX)
    grouped = load_chunks_by_status(registry)
    chunks = all_chunks(grouped)
    reports_dir = registry.paths["reports"]
    docs_dir = ROOT / "docs"
    counters = counters_for(chunks)
    download_summary_path = reports_dir / "download_summary.json"
    download_summary = json.loads(download_summary_path.read_text(encoding="utf-8")) if download_summary_path.exists() else {}
    duplicate_rows = find_duplicate_content(chunks)
    quality_rows = chunk_quality_issues(chunks)
    char_counts = [int(chunk.get("char_count") or len(str(chunk.get("content") or ""))) for chunk in chunks]

    coverage = {
        "created_at": utc_now_iso(),
        "knowledge_base_version": "V2" if int(registry.version) >= 2 else "V1",
        "population": _coverage_for_labels(chunks, matrix.get("populations") or [], "population_tags"),
        "topic": _coverage_for_labels(chunks, matrix.get("topics") or [], "topic_tags"),
        "life_stage": _coverage_for_labels(chunks, matrix.get("life_stages") or [], "life_stage_tags"),
        "safety": _coverage_for_labels(chunks, matrix.get("safety_topics") or [], "topic_tags"),
        "language": dict(Counter(str(chunk.get("language") or "unknown") for chunk in chunks)),
        "registry_candidate_coverage": {
            "population": _source_registry_coverage(registry, matrix.get("populations") or [], "population_tags"),
            "topic": _source_registry_coverage(registry, matrix.get("topics") or [], "topic_tags"),
            "life_stage": _source_registry_coverage(registry, matrix.get("life_stages") or [], "life_stage_tags"),
        },
    }
    write_json_atomic(reports_dir / "knowledge_coverage_v2.json", coverage)
    coverage_lines = [
        "# CARE-Psy Knowledge Coverage V2",
        "",
        f"- Created at: {coverage['created_at']}",
        f"- Registry: {registry.registry_name}",
        f"- Sources: {len(registry.sources)}",
        f"- Chunks: {len(chunks)}",
        "",
        "## Population Coverage",
    ]
    for row in coverage["population"]:
        coverage_lines.append(f"- {row['label']}: {row['rating']} ({row['chunk_count']} chunks, {row['trusted_source_count']} sources)")
    coverage_lines.extend(["", "## Topic Coverage"])
    for row in coverage["topic"]:
        coverage_lines.append(f"- {row['label']}: {row['rating']} ({row['chunk_count']} chunks, {row['trusted_source_count']} sources)")
    coverage_lines.extend(["", "## Safety Coverage"])
    for row in coverage["safety"]:
        coverage_lines.append(f"- {row['label']}: {row['rating']} ({row['chunk_count']} chunks, {row['trusted_source_count']} sources)")
    coverage_lines.extend(["", "## Language"])
    for lang, count in sorted(coverage["language"].items()):
        coverage_lines.append(f"- {lang}: {count}")
    write_markdown(reports_dir / "knowledge_coverage_v2.md", coverage_lines)

    review_paths = _write_review_batches(reports_dir, chunks)
    bm25_staging = bm25_document_count(bm25_dir_for(registry.paths["indexes_bm25"], "staging", require_existing=True))
    bm25_production = bm25_document_count(bm25_dir_for(registry.paths["indexes_bm25"], "production", require_existing=True))
    chroma_counts = chroma_collection_counts(registry.paths["indexes_chroma"])

    audit_lines = [
        "# CARE-Psy Knowledge Base V2 Prebuild Audit",
        "",
        f"- Created at: {utc_now_iso()}",
        f"- Registry: {registry.registry_name}",
        f"- Registry version: {registry.version}",
        f"- Current sources: {len(registry.sources)}",
        f"- Current chunks: {len(chunks)}",
        f"- Review status: {json.dumps(counters.get('review_status', {}), ensure_ascii=False)}",
        f"- Languages: {json.dumps(counters.get('language', {}), ensure_ascii=False)}",
        f"- Collections: {json.dumps(counters.get('collection', {}), ensure_ascii=False)}",
        f"- Use modes: {json.dumps(counters.get('use_mode', {}), ensure_ascii=False)}",
        f"- WHO sources: {sum(1 for source in registry.sources if 'World Health Organization' in source.organization)}",
        f"- CCI sources: {sum(1 for source in registry.sources if 'Centre for Clinical Interventions' in source.organization)}",
        f"- NHS sources: {sum(1 for source in registry.sources if 'NHS' in source.organization)}",
        f"- Chinese source registry entries: {sum(1 for source in registry.sources if 'zh-CN' in _as_list(source.raw.get('language_preference')))}",
        f"- Safety registry entries: {sum(1 for source in registry.sources if source.target_collection == 'safety')}",
        "",
        "## Current Gaps",
    ]
    missing_topics = [row["label"] for row in coverage["topic"] if row["rating"] == "Missing"]
    weak_populations = [row["label"] for row in coverage["population"] if row["rating"] in {"Weak", "Missing"}]
    audit_lines.append(f"- Missing topics by current indexed chunks: {', '.join(missing_topics[:60]) if missing_topics else 'none'}")
    audit_lines.append(f"- Weak/missing populations by current indexed chunks: {', '.join(weak_populations[:40]) if weak_populations else 'none'}")
    audit_lines.append(f"- Duplicate content groups sampled: {len(duplicate_rows)}")
    audit_lines.append(f"- Quality issue sample count: {len(quality_rows)}")
    write_markdown(docs_dir / "knowledge_base_v2_prebuild_audit.md", audit_lines)

    lengths = {
        "mean": round(statistics.mean(char_counts), 2) if char_counts else 0,
        "median": round(statistics.median(char_counts), 2) if char_counts else 0,
        "p95": sorted(char_counts)[int(len(char_counts) * 0.95) - 1] if char_counts else 0,
    }
    source_selection = {}
    selection_path = reports_dir / "source_selection_summary.json"
    if selection_path.exists():
        source_selection = json.loads(selection_path.read_text(encoding="utf-8"))
    benchmark_path = reports_dir / "rag_v2_benchmark.json"
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8")) if benchmark_path.exists() else {}
    completion_lines = [
        "# CARE-Psy Knowledge Base V2 Completion Report",
        "",
        "## A. Current vs V2",
        f"- Knowledge base version: {'V2' if int(registry.version) >= 2 else 'V1'}",
        f"- Sources: {len(registry.sources)}",
        f"- Chunks: {len(chunks)}",
        f"- Approved chunks: {len(grouped.get('approved', []))}",
        "",
        "## B. Sources",
        f"- Candidates selected/generated: {source_selection.get('selected_candidates', 'not_run')}",
        f"- Manual review candidates: {source_selection.get('manual_review_candidates', 'not_run')}",
        f"- Download failures: {download_summary.get('failed_sources', 'not_run')}",
        "",
        "## C. Organizations",
    ]
    org_counts = Counter(source.organization for source in registry.sources)
    completion_lines.extend(f"- {org}: {count}" for org, count in sorted(org_counts.items()))
    completion_lines.extend(["", "## D. Population Coverage"])
    completion_lines.extend(f"- {row['label']}: {row['rating']}" for row in coverage["population"])
    completion_lines.extend(["", "## E. Topic Coverage"])
    completion_lines.extend(f"- {row['label']}: {row['rating']}" for row in coverage["topic"])
    completion_lines.extend(["", "## F. Languages"])
    completion_lines.extend(f"- {lang}: {count}" for lang, count in sorted(coverage["language"].items()))
    completion_lines.extend(["", "## G. Collections"])
    completion_lines.extend(f"- {key}: {value}" for key, value in sorted((counters.get("collection") or {}).items()))
    completion_lines.extend(["", "## H. Use Modes"])
    completion_lines.extend(f"- {key or 'unknown'}: {value}" for key, value in sorted((counters.get("use_mode") or {}).items()))
    completion_lines.extend(
        [
            "",
            "## I. Deduplication",
            f"- Exact duplicate groups sampled: {len(duplicate_rows)}",
            "- CCI/NHS overlap is controlled at source-selection level; newly generated registry caps assets per source.",
            "",
            "## J. Chunk Quality",
            f"- Mean/median/p95 chars: {lengths['mean']} / {lengths['median']} / {lengths['p95']}",
            f"- Quality issue sample count: {len(quality_rows)}",
            f"- Unsafe excluded chunks: {sum(1 for chunk in chunks if chunk.get('exclude_from_index'))}",
            "",
            "## K. Retrieval",
            f"- BM25 staging documents: {bm25_staging}",
            f"- BM25 production documents: {bm25_production}",
            f"- Chroma collections: {json.dumps(chroma_counts, ensure_ascii=False)}",
            f"- Benchmark summary: {json.dumps(benchmark.get('summary', {}), ensure_ascii=False)}",
            "",
            "## L. Safety Isolation",
            "- Ordinary RAG filter excludes safety_only, clinical_reference_only, evidence_only, agent_policy_only and helping_skills_only unless an explicit safety/psychoeducation route requests them.",
            "- Safety collection ordinary access: NO.",
            "",
            "## M. Cross Language",
            "- Retrieval keeps bilingual query expansion and adds Chinese-source preference for Chinese queries.",
            "",
            "## N. Missing Areas",
            f"- Missing topics by indexed chunks: {', '.join(missing_topics[:60]) if missing_topics else 'none'}",
            f"- Weak/missing populations by indexed chunks: {', '.join(weak_populations[:40]) if weak_populations else 'none'}",
            "",
            "## O. Manual Acquisition",
            f"- Manual acquisition candidates: {(reports_dir / 'manual_acquisition_candidates.csv').as_posix()}",
            "",
            "## P. Final Status",
            f"- STAGING_READY={bm25_staging > 0}",
            f"- PRODUCTION_READY={len(grouped.get('approved', [])) > 0 and bm25_production > 0}",
            "- Production remains false until human review approves chunks and production index is built.",
        ]
    )
    write_markdown(docs_dir / "knowledge_base_v2_completion_report.md", completion_lines)
    version_info = {
        "knowledge_base_version": "V2",
        "registry": registry.registry_name,
        "source_count": len(registry.sources),
        "document_count": len({str(chunk.get("document_id") or "") for chunk in chunks if chunk.get("document_id")}),
        "chunk_count": len(chunks),
        "approved_count": len(grouped.get("approved", [])),
        "embedding_model": "configured_in_.env",
        "index_version": "rag_v2_staging",
        "build_time": utc_now_iso(),
    }
    write_json_atomic(reports_dir / "knowledge_base_version_v2.json", version_info)
    return {
        "created_at": utc_now_iso(),
        "registry": registry.registry_name,
        "sources": len(registry.sources),
        "chunks": len(chunks),
        "coverage_json": (reports_dir / "knowledge_coverage_v2.json").as_posix(),
        "coverage_md": (reports_dir / "knowledge_coverage_v2.md").as_posix(),
        "audit_doc": (docs_dir / "knowledge_base_v2_prebuild_audit.md").as_posix(),
        "completion_doc": (docs_dir / "knowledge_base_v2_completion_report.md").as_posix(),
        "review_batches": review_paths,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate CARE-Psy Knowledge Base V2 audit, coverage and completion reports.")
    parser.add_argument("--registry", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = build_reports(args.registry)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"sources: {report['sources']}")
        print(f"chunks: {report['chunks']}")
        print(f"coverage: {report['coverage_md']}")
        print(f"completion: {report['completion_doc']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

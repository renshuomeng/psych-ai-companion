from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rag"))

import _bootstrap  # noqa: F401,E402
from config import get_settings  # noqa: E402
from kb_v11_utils import (  # noqa: E402
    all_chunks,
    bm25_document_count,
    chroma_collection_counts,
    counters_for,
    load_chunks_by_status,
    load_registry,
    normalize_review_status,
    read_jsonl,
    utc_now_iso,
    write_json_atomic,
)
from services.rag_v1_index_service import bm25_dir_for  # noqa: E402


def _file_hash(path: Path) -> str:
    import hashlib

    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _embedding_cache_status(chroma_dir: Path) -> dict[str, Any]:
    cache_path = chroma_dir / "embedding_cache.jsonl"
    records = 0
    dimensions: set[int] = set()
    models: Counter[str] = Counter()
    if cache_path.exists():
        with cache_path.open("r", encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if not line.strip():
                    continue
                records += 1
                if index >= 300:
                    continue
                try:
                    item = json.loads(line)
                    embedding = item.get("embedding")
                    if isinstance(embedding, list):
                        dimensions.add(len(embedding))
                    model = item.get("embedding_model") or item.get("model")
                    if model:
                        models[str(model)] += 1
                except Exception:
                    continue
    return {
        "path": cache_path.as_posix(),
        "exists": cache_path.exists(),
        "records": records,
        "dimensions_sample": sorted(dimensions),
        "models_sample": dict(models.most_common(5)),
    }


def _count_cleaned_documents(registry: Any) -> int:
    cleaned = registry.paths.get("cleaned")
    if not cleaned or not cleaned.exists():
        return 0
    return len([path for path in cleaned.glob("*.json") if path.is_file()])


def _benchmark_summary(registry: Any) -> dict[str, Any]:
    report = _json_file(registry.paths["reports"] / "rag_v2_benchmark.json")
    if not report:
        return {"exists": False}
    return {
        "exists": True,
        "created_at": report.get("created_at"),
        "cases": report.get("cases"),
        "index_mode": report.get("index_mode"),
        "top_k": report.get("top_k"),
        "summary": report.get("summary") or {},
    }


def _review_priority_summary() -> dict[str, Any]:
    path = ROOT / "reports" / "review_priority_summary.json"
    summary = _json_file(path)
    if not summary:
        return {"exists": False, "path": path.as_posix(), "buckets": {}}
    return {
        "exists": True,
        "path": path.as_posix(),
        "created_at": summary.get("created_at"),
        "buckets": summary.get("buckets") or {},
    }


def _summary_metric(summary: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in summary:
            return summary[key]
    return default


def _latest_build_report(registry: Any) -> dict[str, Any]:
    report = _json_file(registry.paths["reports"] / "build_report.json")
    if not report:
        return {"exists": False}
    return {
        "exists": True,
        "created_at": report.get("created_at"),
        "index_mode": report.get("index_mode"),
        "sample_mode": report.get("sample_mode"),
        "sample_limit": report.get("sample_limit"),
        "registry_sources": report.get("registry_sources"),
        "parsed_documents": report.get("parsed_documents"),
        "chunks": report.get("chunks"),
        "embedding": report.get("embedding"),
        "bm25": report.get("bm25"),
        "chroma_collections": report.get("chroma_collections"),
    }


def _chinese_direct_support(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [
        chunk
        for chunk in chunks
        if str(chunk.get("language") or "").lower().startswith("zh")
        and str(chunk.get("use_mode") or "") == "direct_user_support"
        and bool(chunk.get("user_facing", True))
        and not bool(chunk.get("clinical_only", False))
    ]
    return {
        "count": len(rows),
        "by_topic": dict(Counter(str(chunk.get("topic") or "") for chunk in rows).most_common(40)),
        "by_collection": dict(Counter(str(chunk.get("target_collection") or "") for chunk in rows).most_common()),
        "by_population": dict(
            Counter(
                tag
                for chunk in rows
                for tag in (
                    chunk.get("population_tags")
                    if isinstance(chunk.get("population_tags"), list)
                    else [str(chunk.get("population_tags") or "")]
                )
                if str(tag).strip()
            ).most_common(40)
        ),
    }


def build_status(registry_path: str | Path | None = None) -> dict[str, Any]:
    registry = load_registry(registry_path)
    settings = get_settings()
    grouped = load_chunks_by_status(registry)
    chunks = all_chunks(grouped)
    approved_chunks = grouped.get("approved", [])
    pending_chunks = grouped.get("pending", [])
    rejected_chunks = grouped.get("rejected", [])
    staging_indexable_chunks = [
        chunk
        for chunk in chunks
        if not chunk.get("exclude_from_index")
        and normalize_review_status(chunk.get("review_status")) not in {"rejected", "blocked"}
    ]
    production_indexable_chunks = [chunk for chunk in approved_chunks if not chunk.get("exclude_from_index")]
    counters = counters_for(chunks)
    chroma_counts = chroma_collection_counts(registry.paths["indexes_chroma"])
    staging_bm25_dir = bm25_dir_for(registry.paths["indexes_bm25"], "staging", require_existing=True)
    production_bm25_dir = bm25_dir_for(registry.paths["indexes_bm25"], "production", require_existing=False)
    queries_path = ROOT / "evaluation" / "rag_v2" / "retrieval_queries.jsonl"
    registry_path_resolved = ROOT / "backend" / "data" / "knowledge_base" / "sources" / "knowledge_sources.yaml"
    if not registry_path_resolved.exists():
        registry_path_resolved = registry.paths["sources"] / "knowledge_sources_v1.yaml"
    benchmark = _benchmark_summary(registry)
    benchmark_metrics = benchmark.get("summary") or {}
    hybrid_safety_leakage = _summary_metric(benchmark_metrics, "hybrid_safety_leakage_rate", default=1)
    hybrid_wrong_use_mode = _summary_metric(
        benchmark_metrics,
        "hybrid_wrong_use_mode_rate",
        "hybrid_wrong_use_mode_retrieval_rate",
        default=1,
    )
    production_ready = bool(
        approved_chunks
        and bm25_document_count(production_bm25_dir) >= len(production_indexable_chunks)
        and any(name.endswith("_production") and count > 0 for name, count in chroma_counts.items())
        and hybrid_safety_leakage == 0
        and hybrid_wrong_use_mode == 0
    )
    blockers: list[str] = []
    if not approved_chunks:
        blockers.append("approved_chunks_zero")
    if bm25_document_count(production_bm25_dir) == 0:
        blockers.append("production_bm25_missing")
    if not any(name.endswith("_production") and count > 0 for name, count in chroma_counts.items()):
        blockers.append("production_dense_missing")
    if not benchmark.get("exists"):
        blockers.append("rag_v2_benchmark_missing")
    elif (benchmark.get("cases") or 0) < _line_count(queries_path):
        blockers.append("rag_v2_full_benchmark_not_current")
    else:
        if hybrid_safety_leakage != 0:
            blockers.append("rag_v2_safety_leakage_nonzero")
        if hybrid_wrong_use_mode != 0:
            blockers.append("rag_v2_wrong_use_mode_nonzero")
    status = {
        "created_at": utc_now_iso(),
        "project_root": ROOT.as_posix(),
        "git": {
            "available": (ROOT / ".git").exists(),
            "status": "not_a_git_repository" if not (ROOT / ".git").exists() else "available",
        },
        "registry": {
            "path": registry_path_resolved.as_posix(),
            "hash": _file_hash(registry_path_resolved),
            "version": registry.version,
            "name": registry.registry_name,
            "sources": len(registry.sources),
            "enabled_sources": sum(1 for source in registry.sources if source.enabled),
            "auto_download_sources": len(registry.auto_download_sources),
            "collections": sorted(registry.collections),
        },
        "documents": {
            "cleaned_json": _count_cleaned_documents(registry),
            "last_build_parsed_documents": _latest_build_report(registry).get("parsed_documents"),
        },
        "chunks": {
            "total": len(chunks),
            "pending": len(pending_chunks),
            "approved": len(approved_chunks),
            "rejected": len(rejected_chunks),
            "indexable_staging": len(staging_indexable_chunks),
            "indexable_production": len(production_indexable_chunks),
            "counters": counters,
        },
        "indexes": {
            "bm25_staging_documents": bm25_document_count(staging_bm25_dir),
            "bm25_staging_dir": staging_bm25_dir.as_posix(),
            "bm25_production_documents": bm25_document_count(production_bm25_dir),
            "bm25_production_dir": production_bm25_dir.as_posix(),
            "chroma_path": registry.paths["indexes_chroma"].as_posix(),
            "chroma_collections": chroma_counts,
            "dense_staging_vectors": sum(count for name, count in chroma_counts.items() if name.endswith("_staging") and count > 0),
            "dense_production_vectors": sum(count for name, count in chroma_counts.items() if name.endswith("_production") and count > 0),
        },
        "embedding": {
            "provider": settings.rag_embedding_provider,
            "model": settings.rag_embedding_model,
            "batch_size": settings.rag_embedding_batch_size,
            "cache_dir": settings.resolved_rag_embedding_cache_dir.as_posix(),
            "cache": _embedding_cache_status(registry.paths["indexes_chroma"]),
        },
        "retrieval": {
            "index_mode": settings.effective_rag_index_mode,
            "bm25_enabled": settings.rag_v1_bm25_enabled,
            "dense_enabled": settings.rag_v1_dense_enabled,
            "bm25_top_k": settings.rag_v1_bm25_top_k,
            "dense_top_k": settings.rag_v1_dense_top_k,
            "final_top_k": settings.rag_final_top_k,
            "min_relevance_score": settings.rag_v1_min_relevance_score,
            "min_vector_score": settings.rag_v1_min_vector_score,
            "hybrid_fusion": settings.rag_hybrid_fusion,
            "rrf_k": settings.rag_rrf_k,
            "legacy_max_dense_chunks": settings.rag_v1_max_dense_chunks,
            "build_sample_mode": settings.rag_build_sample_mode,
            "build_sample_limit": settings.rag_build_sample_limit,
        },
        "benchmark": benchmark,
        "build_report": _latest_build_report(registry),
        "queries": {
            "path": queries_path.as_posix(),
            "count": _line_count(queries_path),
        },
        "chinese_direct_support": _chinese_direct_support(chunks),
        "review_priority": _review_priority_summary(),
        "production_ready": production_ready,
        "staging_ready": bool(chunks and bm25_document_count(staging_bm25_dir) > 0),
        "production_blockers": blockers,
    }
    return status


def _print_text(status: dict[str, Any]) -> None:
    print(f"Version: KB_V2.1 status snapshot @ {status['created_at']}")
    print(f"Sources: {status['registry']['sources']} enabled={status['registry']['enabled_sources']}")
    print(f"Documents(cleaned): {status['documents']['cleaned_json']}")
    chunks = status["chunks"]
    print(f"Chunks: total={chunks['total']} pending={chunks['pending']} approved={chunks['approved']} rejected={chunks['rejected']}")
    indexes = status["indexes"]
    print(f"BM25: staging={indexes['bm25_staging_documents']} production={indexes['bm25_production_documents']}")
    print(f"Dense: staging={indexes['dense_staging_vectors']} production={indexes['dense_production_vectors']}")
    print(f"Embedding: {status['embedding']['provider']} / {status['embedding']['model']}")
    print(f"Chinese direct-user-support chunks: {status['chinese_direct_support']['count']}")
    print(f"Production Ready: {status['production_ready']}")
    if status["production_blockers"]:
        print("Blockers:")
        for blocker in status["production_blockers"]:
            print(f"- {blocker}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Print CARE-Psy Knowledge Base V2.1 status.")
    parser.add_argument("--registry", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write reports/kb_v2_1_metrics.json")
    args = parser.parse_args()
    status = build_status(args.registry)
    if args.write:
        reports_dir = ROOT / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        write_json_atomic(reports_dir / "kb_v2_1_metrics.json", status)
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2))
    else:
        _print_text(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

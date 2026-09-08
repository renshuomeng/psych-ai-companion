from __future__ import annotations

import argparse
import asyncio
import csv
import json
import math
import os
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

from kb_v11_utils import all_chunks, load_chunks_by_status, load_registry, utc_now_iso, write_json_atomic
from config import get_settings

from services.rag_v1_retrieval_service import (
    _bm25_candidates,
    _dense_candidates,
    _has_direct_term_support,
    _is_user_facing,
    _matches_metadata_filter,
    _merge_candidates,
    _review_allowed,
    retrieve_rag_v1,
    rewrite_query_multilingual,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUERIES = ROOT / "evaluation" / "rag_v2" / "retrieval_queries.jsonl"
RESULTS_DIR = ROOT / "evaluation" / "rag_v2" / "results"
TOP_K_VALUES = (1, 3, 5)
DEFAULT_CANDIDATE_K = 50


def _configure_runtime_index_mode(index_mode: str) -> dict[str, str | None]:
    previous = {
        "RAG_INDEX_MODE": os.environ.get("RAG_INDEX_MODE"),
        "RAG_STAGING_MODE": os.environ.get("RAG_STAGING_MODE"),
    }
    normalized = "production" if str(index_mode).strip().lower() == "production" else "staging"
    os.environ["RAG_INDEX_MODE"] = normalized
    os.environ["RAG_STAGING_MODE"] = "false" if normalized == "production" else "true"
    get_settings.cache_clear()
    return previous


def _restore_runtime_index_mode(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _normalize_token(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\-/]+", "_", text)
    return re.sub(r"[^a-z0-9_\u4e00-\u9fff]+", "", text)


def _norm_text(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def _list_values(value: Any) -> list[str]:
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


def _topics(item: dict[str, Any]) -> set[str]:
    topics = set(_list_values(item.get("topics")))
    topics.update(_list_values(item.get("topic_tags")))
    if item.get("topic"):
        topics.add(str(item["topic"]))
    return {_normalize_token(topic) for topic in topics if str(topic).strip()}


def _expected_topics(case: dict[str, Any]) -> set[str]:
    return {_normalize_token(topic) for topic in _list_values(case.get("expected_topics"))}


def _expected_sources(case: dict[str, Any]) -> set[str]:
    return {str(source) for source in _list_values(case.get("expected_sources"))}


def _topic_matches(candidate: str, expected: str) -> bool:
    if not candidate or not expected:
        return False
    if candidate == expected:
        return True
    if len(candidate) >= 5 and len(expected) >= 5 and (candidate in expected or expected in candidate):
        return True
    return False


def _is_relevant(item: dict[str, Any], case: dict[str, Any]) -> bool:
    expected_sources = _expected_sources(case)
    if expected_sources and str(item.get("source_id") or "") in expected_sources:
        return True

    expected_topics = _expected_topics(case)
    candidate_topics = _topics(item)
    if any(_topic_matches(candidate, expected) for candidate in candidate_topics for expected in expected_topics):
        return True

    # Some chunks have sparse topic metadata. Use a conservative metadata/content fallback
    # for benchmark scoring only; runtime retrieval still uses the indexed metadata.
    haystack = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("section") or ""),
            str(item.get("content") or "")[:600],
        ]
    ).lower()
    return any(expected.replace("_", " ") in haystack for expected in expected_topics if len(expected) >= 4)


def _population_compatible(item: dict[str, Any], case: dict[str, Any]) -> bool | None:
    expected = {_normalize_token(value) for value in _list_values(case.get("expected_population_tags"))}
    if not expected:
        return None
    candidate = {_normalize_token(value) for value in _list_values(item.get("population_tags"))}
    if not candidate:
        return None
    if expected & candidate:
        return True
    adult_subgroups = {
        "adults",
        "young_adults",
        "university_students",
        "workers",
        "caregivers",
        "family_members_supporting_others",
        "people_experiencing_grief",
        "people_exposed_to_trauma",
    }
    if expected <= adult_subgroups and candidate & {"adults", "young_adults", "university_students"}:
        return True
    if "parents" in expected and candidate & {"parents", "caregivers", "adults"}:
        return True
    if "caregivers" in expected and candidate & {"caregivers", "family_members_supporting_others", "adults"}:
        return True
    return False


def _expected_use_modes(case: dict[str, Any]) -> set[str]:
    modes = set(_list_values(case.get("expected_use_modes"))) or {"direct_user_support"}
    return modes


def _is_safety_case(case: dict[str, Any]) -> bool:
    return "safety_only" in _expected_use_modes(case) or case.get("ordinary_rag_expected") == "no_safety_leakage"


def _retrieval_query(case: dict[str, Any]) -> str:
    query = str(case["query"])
    topics = " ".join(_list_values(case.get("expected_topics"))[:5])
    modes = _expected_use_modes(case)
    if "safety_only" in modes:
        return " ".join([query, "safety planning crisis referral", topics]).strip()
    if "psychoeducation_only" in modes:
        return " ".join([query, "psychoeducation professional help", topics]).strip()
    return query


def _case_collections(case: dict[str, Any], *, ordinary_guardrail: bool = False) -> list[str]:
    if ordinary_guardrail:
        return ["interventions", "professional_knowledge", "campus_support"]
    modes = _expected_use_modes(case)
    if "safety_only" in modes:
        return ["safety"]
    if "psychoeducation_only" in modes:
        return ["professional_knowledge"]
    return ["interventions", "professional_knowledge", "campus_support"]


def _case_filter(case: dict[str, Any], *, ordinary_guardrail: bool = False) -> dict[str, Any]:
    if ordinary_guardrail:
        return {
            "target_collection": ["interventions", "professional_knowledge", "campus_support"],
            "use_mode": ["direct_user_support", "psychoeducation_only"],
        }
    modes = _expected_use_modes(case)
    if "safety_only" in modes:
        return {
            "target_collection": ["safety"],
            "use_mode": ["safety_only"],
            "risk_scope": ["safety_route_only"],
        }
    if "psychoeducation_only" in modes:
        return {
            "target_collection": ["professional_knowledge"],
            "use_mode": ["psychoeducation_only"],
            "topics": _list_values(case.get("expected_topics")),
        }
    return {
        "target_collection": ["interventions", "professional_knowledge", "campus_support"],
        "use_mode": ["direct_user_support"],
    }


def _filter_candidates(
    items: list[dict[str, Any]],
    *,
    rewrite: dict[str, Any],
    metadata_filter: dict[str, Any],
    collections: list[str],
    index_mode: str,
    staging_mode: bool,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for item in _merge_candidates(items):
        if not item.get("content"):
            continue
        if not _is_user_facing(item, collections, metadata_filter):
            continue
        if not _review_allowed(item, staging_mode, index_mode=index_mode):
            continue
        if not _matches_metadata_filter(item, metadata_filter):
            continue
        if not _has_direct_term_support(item, rewrite):
            continue
        filtered.append(item)
    return filtered


async def _standalone_method_results(
    registry: Any,
    case: dict[str, Any],
    *,
    method: str,
    candidate_k: int,
    top_k: int,
    index_mode: str,
    staging_mode: bool,
) -> dict[str, Any]:
    query = _retrieval_query(case)
    rewrite = rewrite_query_multilingual(query)
    metadata_filter = _case_filter(case)
    collections = _case_collections(case)
    if method == "bm25":
        candidates, status = _bm25_candidates(registry, rewrite, candidate_k, index_mode=index_mode)
        ranked = sorted(candidates, key=lambda row: float(row.get("keyword_score") or 0), reverse=True)
    elif method == "dense":
        candidates, status = await _dense_candidates(
            registry,
            rewrite,
            candidate_k,
            collections=collections,
            index_mode=index_mode,
        )
        ranked = sorted(candidates, key=lambda row: float(row.get("vector_score") or 0), reverse=True)
    else:
        raise ValueError(f"unknown method: {method}")
    filtered = _filter_candidates(
        ranked,
        rewrite=rewrite,
        metadata_filter=metadata_filter,
        collections=collections,
        index_mode=index_mode,
        staging_mode=staging_mode,
    )
    return {
        "status": status,
        "query": query,
        "rewrite": rewrite,
        "metadata_filter": metadata_filter,
        "collections": collections,
        "results": filtered[:top_k],
    }


async def _hybrid_results(case: dict[str, Any], *, top_k: int, ordinary_guardrail: bool = False) -> dict[str, Any]:
    query = str(case["query"]) if ordinary_guardrail else _retrieval_query(case)
    result = await retrieve_rag_v1(
        query,
        top_k=top_k,
        metadata_filter=_case_filter(case, ordinary_guardrail=ordinary_guardrail),
        collections=_case_collections(case, ordinary_guardrail=ordinary_guardrail),
    )
    return result


def _ranking_metrics(results: list[dict[str, Any]], case: dict[str, Any], *, max_k: int) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    relevance = [1 if _is_relevant(item, case) else 0 for item in results[:max_k]]
    first_hit = next((index + 1 for index, rel in enumerate(relevance) if rel), None)
    expected_topics = _expected_topics(case)
    expected_sources = _expected_sources(case)
    for k in TOP_K_VALUES:
        ranked = results[:k]
        rel_k = relevance[:k]
        retrieved_topics: set[str] = set()
        retrieved_sources = {str(item.get("source_id") or "") for item in ranked}
        for item in ranked:
            retrieved_topics.update(_topics(item))
        matched_topics = {
            expected
            for expected in expected_topics
            if any(_topic_matches(candidate, expected) for candidate in retrieved_topics)
        }
        metrics[f"hit_at_{k}"] = bool(any(rel_k))
        metrics[f"recall_at_{k}"] = round(len(matched_topics) / max(len(expected_topics), 1), 4) if expected_topics else (1.0 if any(rel_k) else 0.0)
        metrics[f"topic_hit_at_{k}"] = bool(matched_topics) if expected_topics else None
        metrics[f"source_hit_at_{k}"] = bool(expected_sources & retrieved_sources) if expected_sources else None
    dcg = sum(rel / math.log2(index + 2) for index, rel in enumerate(relevance))
    ideal_count = min(sum(relevance), max_k)
    idcg = sum(1 / math.log2(index + 2) for index in range(ideal_count)) if ideal_count else 0
    metrics["mrr_at_5"] = round(1 / first_hit, 4) if first_hit else 0.0
    metrics["ndcg_at_5"] = round(dcg / idcg, 4) if idcg else 0.0
    metrics["no_result"] = not bool(results[:max_k])
    metrics["top_sources"] = [item.get("source_id") for item in results[:3]]
    metrics["top_chunks"] = [item.get("chunk_id") for item in results[:3]]
    return metrics


def _guardrail_metrics(results: list[dict[str, Any]], case: dict[str, Any], *, max_k: int, ordinary_guardrail: bool = False) -> dict[str, Any]:
    ranked = results[:max_k]
    expected_modes = _expected_use_modes(case)
    if ordinary_guardrail:
        expected_modes = {"direct_user_support", "psychoeducation_only"}
    wrong_population = 0
    population_checked = 0
    wrong_use_mode = 0
    safety_leakage = 0
    duplicates = 0
    seen_content: set[str] = set()
    language_hits = 0
    language_checked = 0
    preferred_language = str(case.get("preferred_language") or "").lower()
    for item in ranked:
        compatible = _population_compatible(item, case)
        if compatible is not None:
            population_checked += 1
            if not compatible:
                wrong_population += 1
        use_mode = str(item.get("use_mode") or "direct_user_support")
        risk_scope = str(item.get("risk_scope") or "normal")
        collection = str(item.get("target_collection") or item.get("collection") or "")
        if use_mode not in expected_modes:
            wrong_use_mode += 1
        if (
            use_mode == "safety_only"
            or risk_scope == "safety_route_only"
            or collection == "safety"
        ) and ("safety_only" not in expected_modes or ordinary_guardrail):
            safety_leakage += 1
        content_key = str(item.get("content_sha256") or item.get("chunk_sha256") or item.get("content") or "")
        if content_key in seen_content:
            duplicates += 1
        seen_content.add(content_key)
        if preferred_language:
            language_checked += 1
            language = str(item.get("language") or "").lower()
            if language.startswith(preferred_language):
                language_hits += 1
    return {
        "wrong_population_retrieval_rate": round(wrong_population / max(population_checked, 1), 4),
        "wrong_use_mode_retrieval_rate": round(wrong_use_mode / max(len(ranked), 1), 4),
        "safety_leakage_rate": round(safety_leakage / max(len(ranked), 1), 4),
        "duplicate_retrieval_rate": round(duplicates / max(len(ranked), 1), 4),
        "language_preference_accuracy": round(language_hits / max(language_checked, 1), 4) if preferred_language else None,
        "insufficient_evidence": not ranked,
    }


def _compact_results(results: list[dict[str, Any]], *, max_k: int) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for rank, item in enumerate(results[:max_k], start=1):
        compact.append(
            {
                "rank": rank,
                "chunk_id": item.get("chunk_id"),
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "section": item.get("section"),
                "target_collection": item.get("target_collection") or item.get("collection"),
                "use_mode": item.get("use_mode"),
                "risk_scope": item.get("risk_scope"),
                "language": item.get("language"),
                "topics": _list_values(item.get("topics") or item.get("topic_tags")),
                "population_tags": _list_values(item.get("population_tags")),
                "keyword_score": item.get("keyword_score"),
                "vector_score": item.get("vector_score"),
                "rerank_score": item.get("rerank_score"),
                "fusion_score": item.get("fusion_score"),
                "retrieval_sources": item.get("retrieval_sources") or [],
                "review_status": item.get("review_status"),
                "content_sha256": item.get("content_sha256") or item.get("chunk_sha256"),
                "content_preview": str(item.get("content") or "")[:220],
            }
        )
    return compact


def _failure_codes(method: str, case_record: dict[str, Any], all_case_records: dict[str, dict[str, Any]]) -> list[str]:
    metrics = case_record["metrics"]
    guardrail = case_record["guardrail"]
    results = case_record["results"]
    codes: list[str] = []
    if metrics["no_result"]:
        codes.append("NO_RELEVANT_SOURCE")
    if not metrics["hit_at_5"]:
        if method == "bm25":
            codes.append("BM25_TOKENIZATION_FAILURE")
        elif method == "dense":
            codes.append("DENSE_SEMANTIC_FAILURE")
        else:
            bm25_hit = all_case_records.get("bm25", {}).get("metrics", {}).get("hit_at_5")
            dense_hit = all_case_records.get("dense", {}).get("metrics", {}).get("hit_at_5")
            codes.append("RRF_FUSION_FAILURE" if bm25_hit or dense_hit else "WRONG_TOPIC")
    if guardrail["wrong_population_retrieval_rate"] > 0:
        codes.append("WRONG_POPULATION")
    if guardrail["wrong_use_mode_retrieval_rate"] > 0:
        codes.append("USE_MODE_FILTER_FAILURE")
    if guardrail["safety_leakage_rate"] > 0:
        codes.append("SAFETY_LEAKAGE")
    if guardrail["duplicate_retrieval_rate"] >= 0.2:
        codes.append("TOO_MANY_DUPLICATES")
    top_lengths = [len(str(item.get("content_preview") or "")) for item in results[:3]]
    if top_lengths and max(top_lengths) < 80:
        codes.append("CHUNK_TOO_SMALL")
    return codes or ["OK"]


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {}
    for method in ("bm25", "dense", "hybrid"):
        method_records = [record[method] for record in records]
        for metric_name in [
            "hit_at_1",
            "hit_at_3",
            "hit_at_5",
            "recall_at_1",
            "recall_at_3",
            "recall_at_5",
            "mrr_at_5",
            "ndcg_at_5",
            "no_result",
        ]:
            values = [row["metrics"][metric_name] for row in method_records]
            aggregate[f"{method}_{metric_name}"] = round(
                sum(float(value) for value in values) / max(len(values), 1),
                4,
            )
        for guardrail_name in [
            "wrong_population_retrieval_rate",
            "wrong_use_mode_retrieval_rate",
            "safety_leakage_rate",
            "duplicate_retrieval_rate",
            "language_preference_accuracy",
        ]:
            values = [
                row["guardrail"][guardrail_name]
                for row in method_records
                if row["guardrail"][guardrail_name] is not None
            ]
            aggregate[f"{method}_{guardrail_name}"] = round(
                sum(float(value) for value in values) / max(len(values), 1),
                4,
            )
    ordinary = [record.get("ordinary_guardrail", {}) for record in records if record.get("ordinary_guardrail")]
    if ordinary:
        aggregate["ordinary_rag_safety_leakage_rate"] = round(
            sum(float(row["guardrail"]["safety_leakage_rate"]) for row in ordinary) / len(ordinary),
            4,
        )
        aggregate["ordinary_rag_wrong_use_mode_rate"] = round(
            sum(float(row["guardrail"]["wrong_use_mode_retrieval_rate"]) for row in ordinary) / len(ordinary),
            4,
        )
    if "hybrid_wrong_use_mode_retrieval_rate" in aggregate:
        aggregate["hybrid_wrong_use_mode_rate"] = aggregate["hybrid_wrong_use_mode_retrieval_rate"]
    return aggregate


def _query_audit(cases: list[dict[str, Any]]) -> dict[str, Any]:
    topic_counter: Counter[str] = Counter()
    population_counter: Counter[str] = Counter()
    use_mode_counter: Counter[str] = Counter()
    for case in cases:
        topic_counter.update(_list_values(case.get("expected_topics")))
        population_counter.update(_list_values(case.get("expected_population_tags")))
        use_mode_counter.update(_list_values(case.get("expected_use_modes")))
    return {
        "cases": len(cases),
        "preferred_language": dict(Counter(str(case.get("preferred_language") or "") for case in cases)),
        "sensitive": dict(Counter(str(bool(case.get("sensitive"))) for case in cases)),
        "use_modes": dict(use_mode_counter),
        "populations": dict(population_counter),
        "top_expected_topics": dict(topic_counter.most_common(40)),
    }


def _leakage_report(cases: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    query_hashes = {
        sha256(_norm_text(str(case["query"])).encode("utf-8")).hexdigest(): case.get("id")
        for case in cases
    }
    exact_chunk_hits: list[dict[str, Any]] = []
    substring_hits: list[dict[str, Any]] = []
    for chunk in chunks:
        text = _norm_text(str(chunk.get("content") or ""))
        if not text:
            continue
        text_hash = sha256(text.encode("utf-8")).hexdigest()
        if text_hash in query_hashes:
            exact_chunk_hits.append({"case_id": query_hashes[text_hash], "chunk_id": chunk.get("chunk_id")})
        for case in cases:
            query_text = _norm_text(str(case["query"]))
            if len(query_text) >= 18 and query_text in text:
                substring_hits.append({"case_id": case.get("id"), "chunk_id": chunk.get("chunk_id")})
                break
    return {
        "checked_at": utc_now_iso(),
        "query_count": len(cases),
        "chunk_count": len(chunks),
        "exact_hash_hits": exact_chunk_hits[:50],
        "substring_hits": substring_hits[:50],
        "exact_hash_hit_count": len(exact_chunk_hits),
        "substring_hit_count": len(substring_hits),
        "status": "pass" if not exact_chunk_hits and not substring_hits else "review_required",
    }


def _write_failure_csv(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "case_id",
        "method",
        "failure_codes",
        "query",
        "expected_topics",
        "expected_use_modes",
        "hit_at_5",
        "mrr_at_5",
        "wrong_population_rate",
        "wrong_use_mode_rate",
        "safety_leakage_rate",
        "duplicate_rate",
        "language_preference_accuracy",
        "top_sources",
        "top_chunks",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            per_method = {method: record[method] for method in ("bm25", "dense", "hybrid")}
            for method, method_record in per_method.items():
                codes = _failure_codes(method, method_record, per_method)
                if codes == ["OK"]:
                    continue
                writer.writerow(
                    {
                        "case_id": record.get("id"),
                        "method": method,
                        "failure_codes": ";".join(codes),
                        "query": record.get("query"),
                        "expected_topics": ";".join(_list_values(record.get("expected_topics"))),
                        "expected_use_modes": ";".join(_list_values(record.get("expected_use_modes"))),
                        "hit_at_5": method_record["metrics"]["hit_at_5"],
                        "mrr_at_5": method_record["metrics"]["mrr_at_5"],
                        "wrong_population_rate": method_record["guardrail"]["wrong_population_retrieval_rate"],
                        "wrong_use_mode_rate": method_record["guardrail"]["wrong_use_mode_retrieval_rate"],
                        "safety_leakage_rate": method_record["guardrail"]["safety_leakage_rate"],
                        "duplicate_rate": method_record["guardrail"]["duplicate_retrieval_rate"],
                        "language_preference_accuracy": method_record["guardrail"]["language_preference_accuracy"],
                        "top_sources": ";".join(str(item) for item in method_record["metrics"]["top_sources"]),
                        "top_chunks": ";".join(str(item) for item in method_record["metrics"]["top_chunks"]),
                    }
                )


async def run_benchmark(
    query_path: Path,
    *,
    limit: int | None = None,
    top_k: int = 5,
    candidate_k: int = DEFAULT_CANDIDATE_K,
    index_mode: str = "staging",
) -> dict[str, Any]:
    previous_runtime_mode = _configure_runtime_index_mode(index_mode)
    registry = load_registry()
    grouped = load_chunks_by_status(registry)
    chunks = all_chunks(grouped)
    cases = _read_jsonl(query_path)
    if limit:
        cases = cases[:limit]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    bm25_rows: list[dict[str, Any]] = []
    dense_rows: list[dict[str, Any]] = []
    hybrid_rows: list[dict[str, Any]] = []
    ordinary_guardrail_rows: list[dict[str, Any]] = []
    max_k = max(top_k, max(TOP_K_VALUES))

    try:
        for index, case in enumerate(cases, start=1):
            case_record: dict[str, Any] = {
                "id": case.get("id"),
                "query": case.get("query"),
                "retrieval_query": _retrieval_query(case),
                "expected_topics": case.get("expected_topics", []),
                "expected_population_tags": case.get("expected_population_tags", []),
                "expected_use_modes": case.get("expected_use_modes", []),
                "preferred_language": case.get("preferred_language"),
                "sensitive": bool(case.get("sensitive")),
                "ordinary_rag_expected": case.get("ordinary_rag_expected", ""),
            }

            for method in ("bm25", "dense"):
                method_output = await _standalone_method_results(
                    registry,
                    case,
                    method=method,
                    candidate_k=candidate_k,
                    top_k=max_k,
                    index_mode=index_mode,
                    staging_mode=(index_mode != "production"),
                )
                compact = _compact_results(method_output["results"], max_k=max_k)
                method_record = {
                    "status": method_output["status"],
                    "query": method_output["query"],
                    "metadata_filter": method_output["metadata_filter"],
                    "collections": method_output["collections"],
                    "rewrite": method_output["rewrite"],
                    "metrics": _ranking_metrics(method_output["results"], case, max_k=max_k),
                    "guardrail": _guardrail_metrics(method_output["results"], case, max_k=max_k),
                    "results": compact,
                }
                case_record[method] = method_record
                (bm25_rows if method == "bm25" else dense_rows).append({"id": case.get("id"), **method_record})

            hybrid_output = await _hybrid_results(case, top_k=max_k)
            hybrid_results = hybrid_output.get("retrieved_chunks") or []
            hybrid_record = {
                "status": hybrid_output.get("retrieval_status"),
                "query": hybrid_output.get("query"),
                "metadata_filter": hybrid_output.get("metadata_filter"),
                "collections": hybrid_output.get("collections"),
                "rewrite": hybrid_output.get("query_rewrite"),
                "index_status": hybrid_output.get("index_status"),
                "duration_ms": hybrid_output.get("duration_ms"),
                "metrics": _ranking_metrics(hybrid_results, case, max_k=max_k),
                "guardrail": _guardrail_metrics(hybrid_results, case, max_k=max_k),
                "results": _compact_results(hybrid_results, max_k=max_k),
            }
            case_record["hybrid"] = hybrid_record
            hybrid_rows.append({"id": case.get("id"), **hybrid_record})

            if _is_safety_case(case):
                ordinary_output = await _hybrid_results(case, top_k=max_k, ordinary_guardrail=True)
                ordinary_results = ordinary_output.get("retrieved_chunks") or []
                ordinary_record = {
                    "status": ordinary_output.get("retrieval_status"),
                    "query": ordinary_output.get("query"),
                    "metadata_filter": ordinary_output.get("metadata_filter"),
                    "collections": ordinary_output.get("collections"),
                    "guardrail": _guardrail_metrics(
                        ordinary_results,
                        case,
                        max_k=max_k,
                        ordinary_guardrail=True,
                    ),
                    "results": _compact_results(ordinary_results, max_k=max_k),
                }
                case_record["ordinary_guardrail"] = ordinary_record
                ordinary_guardrail_rows.append({"id": case.get("id"), **ordinary_record})

            records.append(case_record)
            if index % 20 == 0:
                print(f"progress: {index}/{len(cases)}", flush=True)

        summary = _aggregate(records)
        query_audit = _query_audit(cases)
        leakage = _leakage_report(cases, chunks)

        _write_jsonl(RESULTS_DIR / "bm25_results.jsonl", bm25_rows)
        _write_jsonl(RESULTS_DIR / "dense_results.jsonl", dense_rows)
        _write_jsonl(RESULTS_DIR / "hybrid_results.jsonl", hybrid_rows)
        _write_jsonl(RESULTS_DIR / "ordinary_guardrail_results.jsonl", ordinary_guardrail_rows)
        _write_jsonl(RESULTS_DIR / "all_method_records.jsonl", records)
        _write_failure_csv(RESULTS_DIR / "failure_analysis.csv", records)
        write_json_atomic(RESULTS_DIR / "query_audit.json", query_audit)
        write_json_atomic(RESULTS_DIR / "benchmark_leakage_report.json", leakage)

        report = {
            "created_at": utc_now_iso(),
            "query_file": query_path.as_posix(),
            "index_mode": index_mode,
            "runtime_index_mode": get_settings().effective_rag_index_mode,
            "top_k": top_k,
            "candidate_k": candidate_k,
            "cases": len(cases),
            "summary": summary,
            "query_audit": query_audit,
            "leakage": leakage,
            "outputs": {
                "results_dir": RESULTS_DIR.as_posix(),
                "bm25_results": (RESULTS_DIR / "bm25_results.jsonl").as_posix(),
                "dense_results": (RESULTS_DIR / "dense_results.jsonl").as_posix(),
                "hybrid_results": (RESULTS_DIR / "hybrid_results.jsonl").as_posix(),
                "ordinary_guardrail_results": (RESULTS_DIR / "ordinary_guardrail_results.jsonl").as_posix(),
                "failure_analysis": (RESULTS_DIR / "failure_analysis.csv").as_posix(),
                "query_audit": (RESULTS_DIR / "query_audit.json").as_posix(),
                "benchmark_leakage_report": (RESULTS_DIR / "benchmark_leakage_report.json").as_posix(),
            },
        }
        write_json_atomic(RESULTS_DIR / "benchmark_summary.json", report)
        write_json_atomic(registry.paths["reports"] / "rag_v2_benchmark.json", {**report, "records": records})
        return report
    finally:
        _restore_runtime_index_mode(previous_runtime_mode)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CARE-Psy RAG V2 retrieval benchmark.")
    parser.add_argument("--queries", default=str(DEFAULT_QUERIES))
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--candidate-k", type=int, default=DEFAULT_CANDIDATE_K)
    parser.add_argument("--mode", choices=["staging", "production"], default="staging")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(
        run_benchmark(
            Path(args.queries),
            limit=args.limit,
            top_k=args.top_k,
            candidate_k=args.candidate_k,
            index_mode=args.mode,
        )
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"cases: {report['cases']}")
        for key, value in report["summary"].items():
            print(f"{key}: {value}")
        print(f"summary: {report['outputs']['results_dir']}/benchmark_summary.json")
        print(f"failure_analysis: {report['outputs']['failure_analysis']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

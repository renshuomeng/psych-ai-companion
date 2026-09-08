import time
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from services.embedding_service import get_embedding_provider
from services.reranker_service import rerank
from services.vector_store_service import keyword_search, log_retrieval, vector_search


QUERY_EXPANSIONS = {
    "论文": ["毕业论文", "学业压力", "任务拆分"],
    "考试": ["考试焦虑", "复习压力"],
    "睡不着": ["失眠", "睡眠卫生", "睡前行为"],
    "失眠": ["睡不着", "睡眠卫生"],
    "就业": ["就业焦虑", "求职压力"],
    "孤独": ["孤独感", "社会支持"],
}


PSYCHOLOGICAL_QUERY_TERMS = {
    "压力",
    "焦虑",
    "紧张",
    "担心",
    "难受",
    "低落",
    "抑郁",
    "情绪",
    "心情",
    "心理",
    "睡不着",
    "失眠",
    "睡眠",
    "论文",
    "考试",
    "学习",
    "就业",
    "求职",
    "面试",
    "人际",
    "关系",
    "室友",
    "孤独",
    "拖延",
    "自责",
    "崩溃",
    "压力性",
    "stress",
    "anxiety",
    "worry",
    "sleep",
    "insomnia",
    "mood",
    "emotion",
    "lonely",
    "relationship",
    "career",
    "study",
    "exam",
}


def clean_query(query: str) -> str:
    return " ".join(query.strip().split())


def _has_psychological_context(psychological_context: dict[str, Any] | None) -> bool:
    if not psychological_context:
        return False
    ignored = {"", "unknown", "neutral", "general", "low", "supportive_listening"}
    return any(str(value).strip().lower() not in ignored for value in psychological_context.values())


def _looks_psychological_query(query: str, psychological_context: dict[str, Any] | None = None) -> bool:
    if _has_psychological_context(psychological_context):
        return True
    lowered = query.lower()
    return any(term in lowered for term in PSYCHOLOGICAL_QUERY_TERMS)


def rewrite_query(query: str) -> str:
    settings = get_settings()
    cleaned = clean_query(query)
    if not settings.rag_query_rewrite_enabled:
        return cleaned
    expansions: list[str] = []
    for key, values in QUERY_EXPANSIONS.items():
        if key in cleaned:
            expansions.extend(values)
    return " ".join([cleaned, *expansions[:6]]).strip()


def _merge_candidates(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for item in vector_results + keyword_results:
        existing = merged.get(item["chunk_id"])
        if not existing:
            merged[item["chunk_id"]] = dict(item)
            continue
        existing["vector_score"] = max(existing.get("vector_score", 0), item.get("vector_score", 0))
        existing["keyword_score"] = max(existing.get("keyword_score", 0), item.get("keyword_score", 0))
    return list(merged.values())


async def retrieve(
    db: Session,
    query: str,
    session_id: str = "",
    metadata_filter: dict[str, str] | None = None,
    mode: str = "hybrid_rerank",
    psychological_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    started = time.perf_counter()
    if not settings.rag_enabled:
        return {
            "query": query,
            "rewritten_query": query,
            "retrieved_chunks": [],
            "retrieval_status": "disabled",
        }

    rewritten = rewrite_query(query)
    if not _looks_psychological_query(rewritten, psychological_context):
        duration_ms = int((time.perf_counter() - started) * 1000)
        result = {
            "query": query,
            "rewritten_query": rewritten,
            "retrieved_chunks": [],
            "retrieval_status": "insufficient_evidence",
            "retrieval_mode": mode,
            "normalized_retrieval_mode": "domain_gate",
            "metadata_filter": metadata_filter or {},
            "psychological_context": psychological_context or {},
            "duration_ms": duration_ms,
        }
        log_retrieval(db, session_id, query, "insufficient_evidence", result, duration_ms)
        return result
    normalized_mode = "keyword_only" if mode == "BM25_only" else mode
    vector_modes = {"vector_only", "hybrid", "hybrid_rerank", "emotion_aware_hybrid", "emotion_aware_hybrid_rerank"}
    keyword_modes = {"keyword_only", "hybrid", "hybrid_rerank", "emotion_aware_hybrid", "emotion_aware_hybrid_rerank"}
    query_embedding = []
    if normalized_mode in vector_modes:
        provider = get_embedding_provider()
        query_embedding = await provider.embed_query(rewritten)

    vector_results = []
    keyword_results = []
    if normalized_mode in vector_modes:
        vector_results = vector_search(
            db,
            query_embedding,
            top_k=settings.rag_vector_top_k,
            metadata_filter=metadata_filter,
        )
    if normalized_mode in keyword_modes:
        keyword_results = keyword_search(
            db,
            rewritten,
            top_k=settings.rag_keyword_top_k,
            metadata_filter=metadata_filter,
        )

    candidates = _merge_candidates(vector_results, keyword_results)
    emotion_aware = normalized_mode in {"emotion_aware_hybrid", "emotion_aware_hybrid_rerank"}
    if settings.rag_rerank_enabled and normalized_mode in {"hybrid_rerank", "emotion_aware_hybrid", "emotion_aware_hybrid_rerank"}:
        candidates = rerank(
            rewritten,
            candidates,
            psychological_context=psychological_context,
            emotion_aware=emotion_aware,
        )
    else:
        candidates = sorted(
            (
                {
                    **item,
                    "rerank_score": round(
                        max(float(item.get("vector_score") or 0), float(item.get("keyword_score") or 0)),
                        4,
                    ),
                }
                for item in candidates
            ),
            key=lambda item: item["rerank_score"],
            reverse=True,
        )

    selected = [
        item
        for item in candidates
        if float(item.get("rerank_score", 0)) >= settings.rag_min_relevance_score
    ][: settings.rag_final_top_k]
    status = "success" if selected else "insufficient_evidence"
    result = {
        "query": query,
        "rewritten_query": rewritten,
        "retrieved_chunks": selected,
        "retrieval_status": status,
        "retrieval_mode": mode,
        "normalized_retrieval_mode": normalized_mode,
        "metadata_filter": metadata_filter or {},
        "psychological_context": psychological_context or {},
    }
    duration_ms = int((time.perf_counter() - started) * 1000)
    log_retrieval(db, session_id, query, status, result, duration_ms)
    result["duration_ms"] = duration_ms
    return result

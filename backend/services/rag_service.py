from typing import Any
import asyncio

from config import get_settings
from database.db import SessionLocal, init_db
from services.rag_v1_retrieval_service import retrieve_rag_v1
from services.retrieval_service import retrieve


async def retrieve_context_async(
    query: str,
    top_k: int = 3,
    session_id: str = "",
    metadata_filter: dict[str, Any] | None = None,
    mode: str = "emotion_aware_hybrid_rerank",
    psychological_context: dict[str, Any] | None = None,
    collections: list[str] | None = None,
    retrieval_query: str | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    effective_query = retrieval_query or query
    rag_v1_result: dict[str, Any] | None = None
    if settings.rag_v1_enabled:
        rag_v1_result = await retrieve_rag_v1(
            effective_query,
            top_k=top_k,
            session_id=session_id,
            psychological_context=psychological_context,
            collections=collections,
            metadata_filter=metadata_filter,
        )
        if rag_v1_result.get("retrieval_status") == "success" or not settings.rag_v1_use_fallback:
            return {
                **rag_v1_result,
                "message": "retrieved" if rag_v1_result.get("documents") else "no_relevant_knowledge_found",
            }

    init_db()
    with SessionLocal() as db:
        result = await retrieve(
            db,
            query=effective_query,
            session_id=session_id,
            metadata_filter=metadata_filter,
            mode=mode,
            psychological_context=psychological_context,
        )
    selected = result.get("retrieved_chunks", [])[:top_k]
    if rag_v1_result:
        result["rag_v1_status"] = {
            "retrieval_status": rag_v1_result.get("retrieval_status"),
            "retrieval_mode": rag_v1_result.get("retrieval_mode"),
            "query_rewrite": rag_v1_result.get("query_rewrite"),
            "index_status": rag_v1_result.get("index_status"),
            "duration_ms": rag_v1_result.get("duration_ms"),
        }
    return {
        **result,
        "retrieved_chunks": selected,
        "documents": [
            {
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "section": item.get("section"),
                "topic": item.get("topic"),
                "content": item.get("content"),
                "relevance_score": item.get("rerank_score", 0),
                "semantic_score": item.get("semantic_score", 0),
                "psychological_score": item.get("psychological_score", 0),
                "evidence_level": item.get("evidence_level", "source_unverified"),
                "is_verified": item.get("is_verified", False),
                "emotion": item.get("emotion", []),
                "cause": item.get("cause", ""),
                "strategy": item.get("strategy", []),
                "risk_level": item.get("risk_level", "low"),
                "reviewed": item.get("reviewed", False),
                "usage_note": item.get("usage_note", ""),
            }
            for item in selected
        ],
        "message": "retrieved" if selected else "no_relevant_knowledge_found",
    }


def retrieve_context(
    query: str,
    top_k: int = 3,
    session_id: str = "",
    metadata_filter: dict[str, Any] | None = None,
    mode: str = "emotion_aware_hybrid_rerank",
    psychological_context: dict[str, Any] | None = None,
    collections: list[str] | None = None,
    retrieval_query: str | None = None,
) -> dict[str, Any]:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            retrieve_context_async(
                query=query,
                top_k=top_k,
                session_id=session_id,
                metadata_filter=metadata_filter,
                mode=mode,
                psychological_context=psychological_context,
                collections=collections,
                retrieval_query=retrieval_query,
            )
        )
    raise RuntimeError("retrieve_context() cannot be called from an active event loop; use retrieve_context_async().")

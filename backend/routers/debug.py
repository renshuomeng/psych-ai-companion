from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from auth.dependencies import CurrentPrincipal, require_permission
from auth.permissions import Permission
from config import get_settings


router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_RAG_DIR = PROJECT_ROOT / "scripts" / "rag"
if str(SCRIPTS_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_RAG_DIR))


@router.get("/agent")
def agent_debug(
    _: CurrentPrincipal = Depends(require_permission(Permission.AGENT_TRACE_VIEW)),
) -> dict[str, Any]:
    settings = get_settings()
    return {
        "agent_v2_enabled": settings.agent_v2_enabled,
        "modules": {
            "RiskAgent": True,
            "EmotionAgent": True,
            "PsychologicalStateAnalyzer": settings.psychological_state_analyzer_enabled,
            "StrategyPlanner": settings.strategy_planner_enabled,
            "RAGRouter": settings.rag_router_enabled,
            "CounselorAgent": True,
            "SafetyAgent": True,
        },
        "ablation_flags": {
            "psychological_state_analyzer_enabled": settings.psychological_state_analyzer_enabled,
            "strategy_planner_enabled": settings.strategy_planner_enabled,
            "rag_router_enabled": settings.rag_router_enabled,
            "rag_enabled": settings.rag_enabled,
            "safety_llm_review_enabled": settings.safety_llm_review_enabled,
        },
        "prompt_files": [
            "system_prompt.txt",
            "risk_prompt.txt",
            "emotion_prompt.txt",
            "multimodal_prompt.txt",
            "counselor_prompt.txt",
            "safety_prompt.txt",
        ],
    }


@router.get("/rag")
def rag_debug(
    _: CurrentPrincipal = Depends(require_permission(Permission.RAG_DEBUG_VIEW)),
) -> dict[str, Any]:
    from kb_v11_utils import all_chunks, counters_for, load_chunks_by_status, load_registry

    settings = get_settings()
    registry = load_registry(None)
    chunks = all_chunks(load_chunks_by_status(registry))
    return {
        "rag_enabled": settings.rag_enabled,
        "rag_v1_enabled": settings.rag_v1_enabled,
        "index_mode": settings.effective_rag_index_mode,
        "staging_mode": settings.rag_staging_mode,
        "bm25_enabled": settings.rag_v1_bm25_enabled,
        "dense_enabled": settings.rag_v1_dense_enabled,
        "hybrid_fusion": settings.rag_hybrid_fusion,
        "registry": {
            "name": registry.registry_name,
            "version": registry.version,
            "collections": sorted(registry.collections),
            "source_count": len(registry.sources),
            "chunk_count": len(chunks),
            "counters": counters_for(chunks),
        },
    }


@router.get("/retrieval")
async def retrieval_debug(
    query: str = Query(min_length=1, max_length=500),
    top_k: int = Query(default=5, ge=1, le=10),
    _: CurrentPrincipal = Depends(require_permission(Permission.RAG_DEBUG_VIEW)),
) -> dict[str, Any]:
    from services.rag_service import retrieve_context_async

    result = await retrieve_context_async(
        query=query,
        top_k=top_k,
        session_id="debug_rbac_session",
        metadata_filter=None,
        psychological_context=None,
        collections=None,
    )
    return {
        "query": query,
        "retrieval_status": result.get("retrieval_status"),
        "retrieval_mode": result.get("retrieval_mode"),
        "documents": result.get("documents", []),
        "retrieved_chunks": result.get("retrieved_chunks", []),
        "rag_v1_status": result.get("rag_v1_status", {}),
    }


@router.get("/trace")
def trace_debug(
    _: CurrentPrincipal = Depends(require_permission(Permission.AGENT_TRACE_VIEW)),
) -> dict[str, Any]:
    return {
        "trace_scope": "evaluation_and_current_request_only",
        "real_user_conversation_read_all": False,
        "note": "Use normal conversation APIs for own conversations; this endpoint does not list private user chats.",
    }

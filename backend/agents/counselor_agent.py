import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from services.ark_client import ProviderResult, generate_text
from services.context_builder_service import build_context_bundle
from services.psychological_state_service import build_psychological_context
from services.rag_service import retrieve_context_async


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "care_psy_counselor_system_prompt.md"


@lru_cache(maxsize=1)
def _load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8").strip()


def build_counselor_prompt(
    message: str,
    emotion: dict[str, Any],
    risk: dict[str, Any],
    interventions: list[dict[str, Any]],
    checkin: dict[str, Any] | None = None,
    multimodal_context: dict[str, Any] | None = None,
    knowledge_context: dict[str, Any] | None = None,
    psychological_state: dict[str, Any] | None = None,
    strategy_plan: dict[str, Any] | None = None,
    rag_route: dict[str, Any] | None = None,
) -> str:
    source_briefs = []
    for index, item in enumerate((knowledge_context or {}).get("documents", [])[:3], start=1):
        source_briefs.append(
            {
                "label": item.get("citation_label") or f"来源{index}",
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "organization": item.get("organization"),
                "year": item.get("year"),
                "section": item.get("section"),
                "evidence_level": item.get("evidence_level"),
                "key_content": str(item.get("content") or "")[:500],
            }
        )
    context = {
        "user_message": message,
        "checkin": checkin or {},
        "emotion": emotion,
        "risk": risk,
        "interventions": interventions,
        "multimodal_context": multimodal_context or {},
        "psychological_state": psychological_state or {},
        "strategy_plan": strategy_plan or {},
        "rag_route": rag_route or {},
        "knowledge_context": knowledge_context or {},
        "citation_sources": source_briefs,
    }
    instructions = (
        "请根据以下结构化上下文生成给用户看的中文回复。\n"
        "必须优先服从 strategy_plan：如果 should_give_advice=false，就以共情、复述和澄清为主，不要输出建议清单；"
        "如果 should_give_advice=true，最多给 1-2 个低负担、可立即执行的小步骤。"
        "如果 should_ask_question=true，末尾只问一个温和问题。\n"
        "需要简短说明多模态分析或模型推断的不确定性，尤其不要把视觉线索当成真实心理状态。\n"
        "如果 citation_sources 非空，可以引用这些资料中的低风险自助建议，并在对应建议后使用"
        "“（来源1）”“（来源2）”这样的短标注；只允许引用 citation_sources 中真实存在的编号，"
        "不要编造机构、链接或书名。\n"
        "如果资料是英文，请用自然中文转述，不要大段复制原文。\n"
        "如果 retrieval_status 为 insufficient_evidence 或 citation_sources 为空，必须说明知识库暂未检索到高度相关资料，"
        "本轮只提供一般性、低风险陪伴，不要强行引用来源。\n"
        "不要输出 JSON，不要诊断，不要给药物建议，不要承诺治疗效果，不要一次给十几条建议。"
        "控制在 180-280 个中文字符。\n\n"
    )
    return instructions + json.dumps(context, ensure_ascii=False, indent=2)


def clean_model_reply(reply: str) -> str:
    text = reply.strip()
    if "</think>" in text:
        text = text.split("</think>", 1)[1].strip()
    return text.strip().strip('"').strip("'")


async def generate_counseling_reply(
    message: str,
    emotion: dict[str, Any],
    risk: dict[str, Any],
    interventions: list[dict[str, Any]],
    checkin: dict[str, Any] | None = None,
    multimodal_context: dict[str, Any] | None = None,
    session_id: str = "",
    memory: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
    evidence: list[dict[str, Any]] | None = None,
    psychological_state: dict[str, Any] | None = None,
    strategy_plan: dict[str, Any] | None = None,
    rag_route: dict[str, Any] | None = None,
    knowledge_context: dict[str, Any] | None = None,
) -> tuple[str, ProviderResult, list[dict[str, Any]], dict[str, Any]]:
    if psychological_state and strategy_plan:
        psychological_context = {
            "emotion": (psychological_state.get("emotion") or {}).get("primary", emotion.get("label", "neutral")),
            "cause": (psychological_state.get("cause") or {}).get("category", "unknown"),
            "strategy": strategy_plan.get("primary_strategy", "supportive_presence"),
            "risk_level": risk.get("level", "low"),
        }
    else:
        psychological_context = build_psychological_context(
            message,
            emotion=emotion,
            risk=risk,
            interventions=interventions,
        )
    if knowledge_context is None:
        route_query = (rag_route or {}).get("query") or message
        knowledge_context = await retrieve_context_async(
            route_query,
            top_k=int((rag_route or {}).get("top_k") or 3),
            session_id=session_id,
            metadata_filter=(rag_route or {}).get("metadata_filter") or None,
            psychological_context=psychological_context,
            collections=(rag_route or {}).get("collections") or None,
        )
    context_bundle = build_context_bundle(
        current_message=message,
        risk=risk,
        memory=memory or {},
        recent_messages=recent_messages or [],
        rag_context=knowledge_context,
        multimodal_context=multimodal_context,
        evidence=evidence,
    )
    prompt = build_counselor_prompt(
        message=message,
        emotion=emotion,
        risk=risk,
        interventions=interventions,
        checkin=checkin,
        multimodal_context=multimodal_context,
        knowledge_context={**knowledge_context, "context_bundle": context_bundle},
        psychological_state=psychological_state,
        strategy_plan=strategy_plan,
        rag_route=rag_route,
    )
    result = await generate_text(_load_system_prompt(), prompt, agent_name="CounselorAgent")
    result.text = clean_model_reply(result.text)
    return result.text, result, knowledge_context.get("documents", []), {
        "retrieval": knowledge_context,
        "psychological_context": psychological_context,
        "psychological_state": psychological_state or {},
        "strategy_plan": strategy_plan or {},
        "rag_route": rag_route or {},
        "context_token_usage": context_bundle.get("context_token_usage", {}),
    }

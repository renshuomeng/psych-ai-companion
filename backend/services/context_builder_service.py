from typing import Any

from config import get_settings


def estimate_tokens(value: Any) -> int:
    text = str(value)
    return max(1, len(text) // 2)


def build_context_bundle(
    current_message: str,
    risk: dict[str, Any],
    memory: dict[str, Any],
    recent_messages: list[dict[str, Any]],
    rag_context: dict[str, Any],
    multimodal_context: dict[str, Any] | None = None,
    evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    budget = settings.context_max_input_tokens
    bundle = {
        "safety_rules": [
            "不做医学诊断",
            "不提供药物建议",
            "不承诺治疗效果",
            "高危风险优先现实支持",
        ],
        "current_risk": risk,
        "user_profile": memory.get("profile", {}),
        "conversation_summary": memory.get("conversation_summary", {}),
        "recent_messages": recent_messages,
        "multimodal_evidence": evidence or [],
        "rag": rag_context,
        "current_user_question": current_message,
    }
    token_usage = {
        "system_tokens": estimate_tokens(bundle["safety_rules"]),
        "risk_tokens": estimate_tokens(risk),
        "profile_tokens": estimate_tokens(bundle["user_profile"]),
        "summary_tokens": estimate_tokens(bundle["conversation_summary"]),
        "recent_message_tokens": estimate_tokens(recent_messages),
        "rag_tokens": estimate_tokens(rag_context.get("retrieved_chunks", [])),
        "multimodal_tokens": estimate_tokens(evidence or multimodal_context or {}),
        "current_message_tokens": estimate_tokens(current_message),
    }
    total = sum(token_usage.values())
    if total > budget:
        trimmed_messages = list(recent_messages)
        while trimmed_messages and total > budget:
            removed = trimmed_messages.pop(0)
            total -= estimate_tokens(removed)
        bundle["recent_messages"] = trimmed_messages
        token_usage["recent_message_tokens"] = estimate_tokens(trimmed_messages)
        total = sum(token_usage.values())
    token_usage["total_input_tokens"] = total
    token_usage["budget"] = budget
    bundle["context_token_usage"] = token_usage
    return bundle

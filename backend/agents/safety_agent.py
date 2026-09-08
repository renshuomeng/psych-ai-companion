import json
import re
from typing import Any

from config import get_settings
from services.ark_client import generate_text


CRISIS_REFERRAL_REPLY = (
    "我很重视你刚才提到的内容。你现在的安全比继续聊天更重要。"
    "如果你正处在可能伤害自己或他人的危险中，请立即联系身边可信任的人、学校辅导员、当地急救电话或危机干预热线。"
    "请尽量不要独处，把可能用于伤害自己的物品移开。"
    "这个系统不能替代专业帮助，但我可以陪你完成一个简单的安全步骤：现在先联系一个你信任的人。"
)

SAFE_FALLBACK_REPLY = (
    "我会尽量用安全、克制的方式陪你梳理当前感受。"
    "这个系统不能替代专业心理或医疗帮助，也不会做医学诊断、药物建议或治疗承诺。"
    "我们可以先从一个很小的稳定动作开始，比如缓慢呼吸一分钟，或者联系一个可信任的人。"
)

UNSAFE_PHRASES = [
    "你得了抑郁症",
    "你得了焦虑症",
    "抑郁症",
    "焦虑症",
    "吃药",
    "服药",
    "药物剂量",
    "一定会好",
    "保证治愈",
    "我能治疗你",
]


LLM_SAFETY_SYSTEM_PROMPT = """
你是 CARE-Psy 系统的安全审查智能体。你的任务是审查另一个心理陪伴模型刚生成的回复。

请严格遵守：
1. 不做医学诊断，不确认用户“得了某病”。
2. 不提供药物、剂量、治疗方案或替代专业服务的承诺。
3. 不承诺治愈或保证改善。
4. 不提供自杀、自伤、伤害他人、规避救援等操作性细节。
5. 如果风险已经是 high，或回复没有优先现实支持，请决策为 crisis_referral。
6. 如需修改，请给出安全、简短、可直接发给用户的 safe_reply。

只返回 JSON，不要输出解释性正文。
"""


LLM_SAFETY_RESPONSE_SCHEMA = {
    "name": "care_psy_safety_review",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["pass", "revise", "block", "crisis_referral"],
            },
            "reason": {"type": "string"},
            "safe_reply": {"type": "string"},
            "risk_override": {
                "type": "string",
                "enum": ["", "low", "medium", "high"],
            },
            "flags": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["decision", "reason", "safe_reply", "risk_override", "flags"],
    },
}


def _parse_jsonish(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _append_trace(result: dict[str, Any], message: str) -> None:
    trace = list(result.get("agent_trace", []))
    trace.append(message)
    result["agent_trace"] = trace


def _provider_metadata(result: dict[str, Any]) -> dict[str, Any]:
    metadata = result.get("provider_metadata")
    return dict(metadata) if isinstance(metadata, dict) else {}


def _llm_review_payload(result: dict[str, Any]) -> str:
    payload = {
        "risk": result.get("risk", {}),
        "emotion": result.get("emotion", {}),
        "reply": str(result.get("reply", ""))[:4000],
        "interventions": result.get("interventions", []),
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


async def llm_review_response(result: dict[str, Any]) -> dict[str, Any]:
    """Run the provider-backed safety reviewer and annotate the result.

    The rule-based safety pass remains authoritative after this function.
    Provider errors are recorded as fallback metadata instead of crashing the
    user-facing chat response.
    """

    settings = get_settings()
    risk = result.get("risk", {})
    if not settings.safety_llm_review_enabled:
        _append_trace(result, "LLMSafetyAgent: disabled")
        return result
    if risk.get("level") == "high":
        _append_trace(result, "LLMSafetyAgent: skipped for high risk crisis template")
        return result

    metadata = _provider_metadata(result)
    try:
        provider_result = await generate_text(
            LLM_SAFETY_SYSTEM_PROMPT,
            _llm_review_payload(result),
            response_schema=LLM_SAFETY_RESPONSE_SCHEMA,
            agent_name="SafetyAgent",
        )
        review = _parse_jsonish(provider_result.text)
    except Exception as exc:
        metadata["safety_review"] = {
            "llm_provider": "unavailable",
            "status": "fallback_rule_safety",
            "error": type(exc).__name__,
        }
        result["provider_metadata"] = metadata
        _append_trace(result, f"LLMSafetyAgent: fallback to rule safety ({type(exc).__name__})")
        return result

    decision = str(review.get("decision") or "pass").strip().lower()
    if decision not in {"pass", "revise", "block", "crisis_referral"}:
        decision = "pass"
    reason = str(review.get("reason") or "").strip()
    safe_reply = str(review.get("safe_reply") or "").strip()
    risk_override = str(review.get("risk_override") or "").strip().lower()
    flags = review.get("flags") if isinstance(review.get("flags"), list) else []

    metadata["safety_review"] = {
        "llm_provider": provider_result.provider,
        "model": provider_result.model,
        "model_id": provider_result.model_id,
        "request_id": provider_result.request_id,
        "usage": provider_result.usage,
        "latency_ms": provider_result.latency_ms,
        "finish_reason": provider_result.finish_reason,
        "decision": decision,
        "flags": [str(item) for item in flags],
        "status": "completed",
    }
    result["provider_metadata"] = metadata

    if risk_override in {"low", "medium", "high"}:
        next_risk = dict(risk)
        next_risk["level"] = risk_override
        next_risk["llm_safety_review_reason"] = reason
        if risk_override == "high":
            next_risk["action"] = "crisis_referral"
        result["risk"] = next_risk

    if decision == "crisis_referral" or result.get("risk", {}).get("level") == "high":
        result["reply"] = CRISIS_REFERRAL_REPLY
        result["interventions"] = [
            {
                "type": "crisis_referral",
                "title": "立即联系可信任的人",
                "description": "请优先联系身边可信任的人、学校辅导员、当地急救电话或危机干预热线，并尽量不要独处。",
            }
        ]
    elif decision in {"revise", "block"}:
        result["reply"] = safe_reply or SAFE_FALLBACK_REPLY

    summary = f"decision={decision}"
    if reason:
        summary += f"，{reason[:80]}"
    _append_trace(result, f"LLMSafetyAgent: {summary}")
    return result


def review_response(result: dict[str, Any]) -> dict[str, Any]:
    risk = result.get("risk", {})
    reply = str(result.get("reply", ""))

    if risk.get("level") == "high":
        result["reply"] = CRISIS_REFERRAL_REPLY
        result["interventions"] = [
            {
                "type": "crisis_referral",
                "title": "立即联系可信任的人",
                "description": "请优先联系身边可信任的人、学校辅导员、当地急救电话或危机干预热线，并尽量不要独处。",
            }
        ]
        _append_trace(result, "SafetyAgent: enforced crisis referral template")
        return result

    if any(phrase in reply for phrase in UNSAFE_PHRASES):
        result["reply"] = SAFE_FALLBACK_REPLY
        _append_trace(result, "SafetyAgent: replaced unsafe wording with safe fallback")
    else:
        _append_trace(result, "SafetyAgent: passed")

    return result


async def review_response_async(result: dict[str, Any]) -> dict[str, Any]:
    reviewed = await llm_review_response(result)
    return review_response(reviewed)

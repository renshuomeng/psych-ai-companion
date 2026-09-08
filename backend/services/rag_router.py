from __future__ import annotations

from typing import Any

from config import get_settings
from schemas.agent_v2 import RAGRoute


CAUSE_TOPICS = {
    "academic": ["academic_stress", "study_anxiety"],
    "thesis": ["academic_stress", "thesis", "procrastination", "perfectionism"],
    "research": ["academic_stress", "research", "procrastination"],
    "exam": ["academic_stress", "exam_anxiety"],
    "employment": ["career_anxiety", "uncertainty", "problem_solving"],
    "interpersonal": ["relationships", "communication", "boundaries"],
    "romantic_relationship": ["relationships", "communication", "boundaries"],
    "roommate": ["relationships", "communication", "boundaries"],
    "family": ["relationships", "communication", "boundaries"],
    "financial": ["stress", "problem_solving"],
    "sleep": ["sleep", "sleep_hygiene", "rumination", "relaxation"],
    "health": ["stress", "self_compassion"],
    "self_evaluation": ["self_compassion", "perfectionism", "balanced_thinking"],
    "future_uncertainty": ["uncertainty", "problem_solving", "values"],
    "loneliness": ["loneliness", "social_support", "self_compassion"],
}

CAUSE_COLLECTIONS = {
    "academic": ["interventions", "professional_knowledge", "campus_support"],
    "thesis": ["interventions", "professional_knowledge", "campus_support"],
    "research": ["interventions", "professional_knowledge", "campus_support"],
    "exam": ["interventions", "professional_knowledge", "campus_support"],
    "employment": ["campus_support", "interventions", "professional_knowledge"],
    "sleep": ["interventions", "professional_knowledge"],
    "interpersonal": ["interventions", "professional_knowledge", "campus_support"],
    "romantic_relationship": ["interventions", "professional_knowledge"],
    "roommate": ["interventions", "professional_knowledge", "campus_support"],
    "family": ["interventions", "professional_knowledge"],
    "loneliness": ["interventions", "professional_knowledge", "campus_support"],
    "self_evaluation": ["interventions", "professional_knowledge"],
    "future_uncertainty": ["interventions", "professional_knowledge", "campus_support"],
}

STRATEGY_TERMS = {
    "problem_solving": ["problem solving", "small steps", "task breakdown"],
    "information": ["psychoeducation", "self help"],
    "cognitive_reappraisal": ["cognitive restructuring", "balanced thinking"],
    "behavioral_activation": ["behavioural activation", "activity scheduling"],
    "grounding": ["grounding", "breathing", "relaxation"],
    "self_compassion": ["self compassion", "self kindness"],
}

CONDITION_PSYCHOEDUCATION_TERMS = {
    "depression": ["抑郁症", "抑郁", "depression"],
    "anxiety_disorders": ["焦虑症", "焦虑障碍", "anxiety disorder"],
    "panic": ["惊恐", "惊恐发作", "panic"],
    "social_anxiety": ["社恐", "社交焦虑", "social anxiety"],
    "OCD": ["强迫症", "强迫", "ocd"],
    "PTSD": ["创伤后", "ptsd"],
    "bipolar_disorder": ["双相", "躁郁", "bipolar"],
    "psychosis": ["幻觉", "妄想", "psychosis"],
    "eating_disorders": ["进食障碍", "暴食", "厌食", "eating disorder"],
    "ADHD": ["多动症", "注意缺陷", "adhd"],
    "autism": ["自闭症", "孤独症", "autism"],
    "dementia": ["失智", "痴呆", "dementia"],
    "substance_use": ["成瘾", "物质使用", "substance use"],
}


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _condition_psychoeducation_topics(message: str) -> list[str]:
    lower = message.lower()
    topics: list[str] = []
    for topic, triggers in CONDITION_PSYCHOEDUCATION_TERMS.items():
        if any(trigger.lower() in lower for trigger in triggers):
            topics.append(topic)
    diagnostic_phrases = ["是不是得了", "我是不是", "会不会是", "是什么病", "diagnose", "do i have"]
    if topics and any(phrase in lower for phrase in diagnostic_phrases):
        topics.append("professional_help")
    return _dedupe(topics)


def route_rag(
    *,
    message: str,
    psychological_state: dict[str, Any],
    strategy_plan: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.rag_router_enabled:
        return RAGRoute(
            should_retrieve=False,
            query=message,
            reason_codes=["rag_router_disabled"],
            fallback="legacy_rag_or_no_rag",
        ).model_dump()

    risk_level = str(risk.get("level") or "low")
    if risk_level == "high":
        return RAGRoute(
            should_retrieve=False,
            query=message,
            reason_codes=["high_risk_skip_ordinary_rag"],
            fallback="safety_agent_crisis_referral",
        ).model_dump()

    if risk_level == "medium":
        return RAGRoute(
            should_retrieve=False,
            query=message,
            reason_codes=["medium_risk_confirm_safety_before_rag"],
            fallback="support_with_monitoring",
        ).model_dump()

    if not strategy_plan.get("should_use_rag"):
        return RAGRoute(
            should_retrieve=False,
            query=message,
            reason_codes=["strategy_plan_does_not_need_knowledge"],
            fallback="supportive_reply_without_sources",
        ).model_dump()

    state_confidence = float(psychological_state.get("confidence") or 0)
    if state_confidence < settings.psy_state_low_confidence_threshold:
        return RAGRoute(
            should_retrieve=False,
            query=message,
            reason_codes=["psychological_state_low_confidence"],
            fallback="clarification_before_retrieval",
        ).model_dump()

    emotion = psychological_state.get("emotion") or {}
    cause = psychological_state.get("cause") or {}
    cause_category = str(cause.get("category") or "unknown")
    primary_strategy = str(strategy_plan.get("primary_strategy") or "")
    needs = [str(item) for item in psychological_state.get("needs") or []]
    condition_topics = _condition_psychoeducation_topics(message)
    if condition_topics:
        return RAGRoute(
            should_retrieve=True,
            collections=["professional_knowledge"],
            query=" ".join([message, "psychoeducation", "professional help", *condition_topics]),
            metadata_filter={
                "topics": condition_topics,
                "target_collection": ["professional_knowledge"],
                "use_mode": ["psychoeducation_only"],
            },
            top_k=3,
            reason_codes=["condition_psychoeducation", *[f"topic_{item}" for item in condition_topics[:3]]],
            fallback="psychoeducation_with_professional_assessment_boundary",
        ).model_dump()
    topics = _dedupe([*CAUSE_TOPICS.get(cause_category, []), *needs, *STRATEGY_TERMS.get(primary_strategy, [])])
    collections = _dedupe(CAUSE_COLLECTIONS.get(cause_category, ["interventions", "professional_knowledge"]))

    query_parts = [
        message,
        f"cause:{cause_category}",
        f"emotion:{emotion.get('primary', 'unknown')}",
        f"strategy:{primary_strategy}",
        " ".join(topics),
    ]
    return RAGRoute(
        should_retrieve=True,
        collections=collections,
        query=" ".join(part for part in query_parts if str(part).strip()),
        metadata_filter={"topics": topics, "target_collection": collections},
        top_k=3,
        reason_codes=["strategy_plan_requires_knowledge", f"cause_{cause_category}", f"strategy_{primary_strategy}"],
        fallback="no_source_general_support",
    ).model_dump()

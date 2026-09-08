from __future__ import annotations

from typing import Any

from config import get_settings
from schemas.agent_v2 import StrategyPlan


ADVICE_READY_STAGES = {"goal_setting", "intervention", "follow_up"}
ACADEMIC_CAUSES = {"academic", "thesis", "research", "exam", "employment"}
RELATIONSHIP_CAUSES = {"interpersonal", "romantic_relationship", "roommate", "family", "loneliness"}


def _low_confidence(state: dict[str, Any]) -> bool:
    return float(state.get("confidence") or 0) < get_settings().psy_state_low_confidence_threshold


def _need_set(state: dict[str, Any]) -> set[str]:
    return {str(item) for item in state.get("needs") or []}


def plan_strategy(
    psychological_state: dict[str, Any],
    *,
    risk: dict[str, Any],
    message: str = "",
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.strategy_planner_enabled:
        return StrategyPlan(
            reason_codes=["strategy_planner_disabled"],
            response_constraints=["沿用旧版陪伴回复策略"],
        ).model_dump()

    risk_level = str(risk.get("level") or "low")
    if risk_level == "high":
        return StrategyPlan(
            primary_strategy="referral",
            secondary_strategy=["supportive_presence"],
            should_give_advice=False,
            should_ask_question=False,
            should_use_rag=False,
            response_constraints=["跳过普通建议，优先现实危机支持"],
            reason_codes=["high_risk_crisis_flow"],
            confidence=0.95,
        ).model_dump()

    emotion = psychological_state.get("emotion") or {}
    cause = psychological_state.get("cause") or {}
    primary_emotion = str(emotion.get("primary") or "unknown")
    cause_category = str(cause.get("category") or "unknown")
    stage = str(psychological_state.get("stage") or "unknown")
    needs = _need_set(psychological_state)
    reason_codes: list[str] = []

    if risk_level == "medium":
        return StrategyPlan(
            primary_strategy="grounding",
            secondary_strategy=["emotional_validation", "clarification", "supportive_presence"],
            should_give_advice=False,
            should_ask_question=True,
            should_use_rag=False,
            response_constraints=["先稳定情绪并确认当前安全性", "避免给复杂任务清单"],
            reason_codes=["medium_risk_support_with_monitoring"],
            confidence=0.82,
        ).model_dump()

    if _low_confidence(psychological_state):
        return StrategyPlan(
            primary_strategy="clarification",
            secondary_strategy=["reflection", "emotional_validation", "open_question"],
            should_give_advice=False,
            should_ask_question=True,
            should_use_rag=False,
            response_constraints=["少给建议，先确认困扰来源和用户期待", "最多提出一个问题"],
            reason_codes=["low_psychological_state_confidence"],
            confidence=0.72,
        ).model_dump()

    if "safety" in needs:
        reason_codes.append("safety_need_present")
    if stage in ADVICE_READY_STAGES:
        reason_codes.append(f"stage_{stage}")
    if "problem_solving" in needs:
        reason_codes.append("needs_problem_solving")
    if "information" in needs:
        reason_codes.append("needs_information")

    primary = "emotional_validation"
    secondary: list[str] = ["reflection"]
    should_give_advice = False
    should_ask_question = True
    should_use_rag = False
    constraints = ["先共情，再给出低负担下一步"]

    if cause_category == "sleep" or "rest" in needs:
        primary = "information" if "information" in needs else "problem_solving"
        secondary = ["emotional_validation", "grounding"]
        should_give_advice = True
        should_use_rag = True
        reason_codes.append("sleep_or_rest_need")
    elif cause_category in ACADEMIC_CAUSES:
        primary = "problem_solving"
        secondary = ["emotional_validation", "clarification"]
        should_give_advice = True
        should_use_rag = True
        reason_codes.append("academic_or_career_cause")
    elif cause_category in RELATIONSHIP_CAUSES:
        primary = "emotional_validation"
        secondary = ["open_question", "problem_solving"]
        should_give_advice = "problem_solving" in needs or stage in ADVICE_READY_STAGES
        should_use_rag = should_give_advice
        reason_codes.append("relationship_or_connection_cause")
    elif cause_category == "self_evaluation" or {"self_compassion", "encouragement"} & needs:
        primary = "self_compassion"
        secondary = ["cognitive_reappraisal", "affirmation"]
        should_give_advice = True
        should_use_rag = True
        reason_codes.append("self_evaluation_or_self_compassion_need")
    elif primary_emotion in {"sadness", "fatigue", "loneliness"} and stage in ADVICE_READY_STAGES:
        primary = "behavioral_activation"
        secondary = ["emotional_validation", "self_compassion"]
        should_give_advice = True
        should_use_rag = True
        reason_codes.append("low_mood_activation")
    elif "information" in needs:
        primary = "information"
        secondary = ["emotional_validation"]
        should_give_advice = True
        should_use_rag = True
    elif "problem_solving" in needs:
        primary = "problem_solving"
        secondary = ["emotional_validation", "clarification"]
        should_give_advice = True
        should_use_rag = True

    if not should_give_advice:
        constraints.extend(["不输出多条建议清单", "用一个开放问题推进探索"])
    else:
        constraints.extend(["建议数量控制在 1-2 个", "给出可立即执行的小步骤"])

    return StrategyPlan(
        primary_strategy=primary,
        secondary_strategy=secondary[:4],
        should_give_advice=should_give_advice,
        should_ask_question=should_ask_question,
        should_use_rag=should_use_rag,
        response_constraints=constraints,
        reason_codes=reason_codes or ["supportive_default"],
        confidence=0.86 if should_give_advice else 0.78,
    ).model_dump()

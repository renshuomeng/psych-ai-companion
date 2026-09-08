from typing import Any


CAUSE_KEYWORDS = {
    "academic_stress": ["论文", "作业", "考试", "绩点", "课程", "导师", "开题", "答辩", "复习", "学习"],
    "career_anxiety": ["就业", "找工作", "简历", "面试", "实习", "秋招", "春招", "offer", "笔试"],
    "interpersonal_conflict": ["室友", "同学", "朋友", "恋人", "父母", "关系", "吵架", "边界", "沟通"],
    "sleep_disturbance": ["睡不着", "失眠", "熬夜", "早醒", "睡眠", "做梦", "困", "疲惫"],
    "loneliness": ["孤独", "孤单", "没人陪", "没人理解", "一个人", "被孤立"],
    "emotion_regulation": ["情绪", "崩溃", "失控", "烦", "生气", "焦虑", "难过", "压力"],
    "crisis_safety": ["自杀", "轻生", "自残", "伤害自己", "结束生命", "想死", "kill myself", "suicide"],
}


STRATEGY_KEYWORDS = {
    "breathing": ["呼吸", "喘不过气", "紧张", "焦虑", "心慌"],
    "grounding": ["失控", "崩溃", "当下", "恐慌", "慌"],
    "task_breakdown": ["论文", "作业", "考试", "复习", "任务", "来不及", "不知道怎么开始"],
    "cognitive_reappraisal": ["肯定不行", "完蛋", "失败", "否定自己", "想法", "担心"],
    "journaling": ["难过", "想哭", "委屈", "说不清", "乱"],
    "behavioral_activation": ["没动力", "麻木", "躺着", "不想动", "疲惫"],
    "sleep_hygiene": ["睡不着", "失眠", "熬夜", "早醒", "睡眠"],
    "social_support": ["孤独", "没人陪", "朋友", "室友", "关系", "父母"],
    "problem_solving": ["就业", "简历", "面试", "选择", "计划", "下一步"],
    "crisis_referral": ["自杀", "轻生", "自残", "伤害自己", "结束生命", "想死", "kill myself", "suicide"],
}


def _matches(text: str, mapping: dict[str, list[str]]) -> dict[str, list[str]]:
    normalized = text.lower()
    return {
        label: [word for word in words if word.lower() in normalized]
        for label, words in mapping.items()
    }


def _best_label(
    text: str,
    mapping: dict[str, list[str]],
    default: str,
) -> tuple[str, list[str], float]:
    matches = _matches(text, mapping)
    ranked = sorted(
        ((label, words) for label, words in matches.items() if words),
        key=lambda item: (len(item[1]), sum(len(word) for word in item[1])),
        reverse=True,
    )
    if not ranked:
        return default, [], 0.35
    label, words = ranked[0]
    confidence = min(0.58 + len(words) * 0.12, 0.9)
    return label, words[:5], round(confidence, 2)


def classify_cause(text: str) -> dict[str, Any]:
    label, words, confidence = _best_label(text, CAUSE_KEYWORDS, "general")
    return {
        "label": label,
        "confidence": confidence,
        "evidence": words,
        "method": "keyword_baseline_v1",
    }


def classify_strategy(
    text: str,
    emotion: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    interventions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if risk and risk.get("level") == "high":
        return {
            "label": "crisis_referral",
            "confidence": 0.95,
            "evidence": risk.get("matched_terms", []),
            "method": "risk_gate",
        }

    if interventions:
        first_type = str(interventions[0].get("type", "")).strip()
        if first_type:
            return {
                "label": first_type,
                "confidence": 0.72,
                "evidence": [str(interventions[0].get("title", ""))],
                "method": "intervention_agent_first_choice",
            }

    label, words, confidence = _best_label(text, STRATEGY_KEYWORDS, "supportive_listening")
    emotion_label = str((emotion or {}).get("label", ""))
    if label == "supportive_listening" and emotion_label in {"anxiety", "stress"}:
        label, confidence = "breathing", 0.54
    elif label == "supportive_listening" and emotion_label == "sadness":
        label, confidence = "journaling", 0.54
    elif label == "supportive_listening" and emotion_label == "loneliness":
        label, confidence = "social_support", 0.54

    return {
        "label": label,
        "confidence": confidence,
        "evidence": words,
        "method": "keyword_baseline_v1",
    }


def build_psychological_context(
    text: str,
    emotion: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    interventions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cause = classify_cause(text)
    strategy = classify_strategy(text, emotion=emotion, risk=risk, interventions=interventions)
    risk_level = str((risk or {}).get("level", "low"))
    primary_emotion = str((emotion or {}).get("label") or (emotion or {}).get("primary_emotion") or "neutral")
    return {
        "emotion": primary_emotion,
        "cause": cause["label"],
        "strategy": strategy["label"],
        "risk_level": risk_level,
        "cause_confidence": cause["confidence"],
        "strategy_confidence": strategy["confidence"],
        "method": "care_psy_phase_1_rule_baseline",
    }

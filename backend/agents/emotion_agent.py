from typing import Any


EMOTION_KEYWORDS = {
    "joy": ["开心", "高兴", "快乐", "愉快", "笑"],
    "anxiety": ["论文", "考试", "就业", "压力", "焦虑", "睡不着"],
    "sadness": ["难过", "想哭", "悲伤", "沮丧", "绝望", "痛苦", "无助", "想死", "轻生", "不想活"],
    "anger": ["生气", "烦", "讨厌", "愤怒"],
    "fatigue": ["累", "疲惫", "没动力", "麻木"],
    "loneliness": ["孤独", "没人陪", "没人理解", "一个人", "被孤立"],
    "stress": ["压力", "压得", "喘不过气", "来不及", "任务太多"],
}

HIGH_DISTRESS_KEYWORDS = [
    "绝望",
    "轻生",
    "自杀",
    "想死",
    "不想活",
    "活不下去",
    "结束生命",
    "结束自己",
    "伤害自己",
    "自残",
    "撑不下去",
    "不想再撑",
    "再也不想醒来",
    "hopeless",
    "suicide",
    "kill myself",
    "want to die",
    "end my life",
    "hurt myself",
]

NEGATED_DISTRESS_PHRASES = [
    "没有想自杀",
    "没有想过自杀",
    "没有自杀的想法",
    "没有想轻生",
    "没有轻生的想法",
    "没有伤害自己的想法",
    "不想死",
    "不会伤害自己",
    "don't want to die",
    "do not want to die",
    "not suicidal",
]

FACE_EMOTION_MAP = {
    "happy": "joy",
    "joy": "joy",
    "smile": "joy",
    "smiling": "joy",
    "sad": "sadness",
    "sadness": "sadness",
    "angry": "anger",
    "anger": "anger",
    "fear": "anxiety",
    "anxiety": "anxiety",
    "tired": "fatigue",
    "fatigue": "fatigue",
}

VISUAL_AFFECT_KEYWORDS = {
    "joy": ["微笑", "笑容", "嘴角上扬", "露齿笑", "开心", "高兴", "愉快"],
    "anger": ["生气", "愤怒", "皱眉", "瞪眼", "咬牙", "紧咬", "怒", "表情紧绷"],
    "sadness": ["哭", "流泪", "难过", "悲伤", "沮丧", "低落"],
    "anxiety": ["紧张", "惊恐", "害怕", "焦虑", "眼睛睁大", "不安"],
    "fatigue": ["疲惫", "疲劳", "困倦", "闭眼", "无精打采"],
    "loneliness": ["孤独", "落寞", "独自", "低落"],
    "stress": ["紧绷", "压力", "皱眉", "焦虑"],
}

BASE_DIMENSIONS = {
    "joy": {"valence": 0.72, "arousal": 0.55, "control": 0.68},
    "anxiety": {"valence": -0.62, "arousal": 0.78, "control": 0.28},
    "sadness": {"valence": -0.72, "arousal": 0.28, "control": 0.34},
    "anger": {"valence": -0.58, "arousal": 0.82, "control": 0.32},
    "fatigue": {"valence": -0.42, "arousal": 0.2, "control": 0.44},
    "loneliness": {"valence": -0.66, "arousal": 0.26, "control": 0.38},
    "stress": {"valence": -0.52, "arousal": 0.72, "control": 0.36},
    "mixed": {"valence": -0.18, "arousal": 0.58, "control": 0.42},
    "neutral": {"valence": 0.0, "arousal": 0.35, "control": 0.55},
}


def _is_negated_distress(text: str, keyword: str) -> bool:
    normalized = text.lower()
    lowered_keyword = keyword.lower()
    index = normalized.find(lowered_keyword)
    if index < 0:
        return False
    window = normalized[max(0, index - 12) : index + len(lowered_keyword) + 12]
    if any(phrase.lower() in window for phrase in NEGATED_DISTRESS_PHRASES):
        return True
    if lowered_keyword.startswith(("不", "没")):
        return False
    return any(f"{prefix}{lowered_keyword}" in window for prefix in ["没有", "没", "并不", "不是", "不"])


def _high_distress_matches(text: str) -> list[str]:
    normalized = text.lower()
    return [
        word
        for word in HIGH_DISTRESS_KEYWORDS
        if word.lower() in normalized and not _is_negated_distress(normalized, word)
    ]


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _valence_label(score: float) -> str:
    if score >= 0.25:
        return "positive"
    if score <= -0.25:
        return "negative"
    return "neutral"


def _level_label(score: float) -> str:
    if score >= 0.67:
        return "high"
    if score >= 0.34:
        return "medium"
    return "low"


def build_emotion_dimensions(
    label: str,
    intensity: float,
    checkin: dict[str, Any] | None = None,
    visual_confidence: float | None = None,
) -> dict[str, dict[str, float | str]]:
    base = dict(BASE_DIMENSIONS.get(label, BASE_DIMENSIONS["neutral"]))
    if checkin and isinstance(checkin.get("stress_score"), int):
        stress = _clamp(int(checkin["stress_score"]) / 10, 0, 1)
        base["valence"] -= stress * 0.18
        base["arousal"] += stress * 0.14
        base["control"] -= stress * 0.16

    if visual_confidence is not None and label != "neutral":
        base["arousal"] = (base["arousal"] * 0.8) + (_clamp(visual_confidence, 0, 1) * 0.2)

    valence = round(_clamp(base["valence"], -1, 1), 2)
    arousal = round(_clamp(base["arousal"], 0, 1), 2)
    control = round(_clamp(base["control"], 0, 1), 2)
    intensity = round(_clamp(intensity, 0, 1), 2)
    return {
        "valence": {"score": valence, "label": _valence_label(valence)},
        "arousal": {"score": arousal, "label": _level_label(arousal)},
        "control": {"score": control, "label": _level_label(control)},
        "intensity": {"score": intensity, "label": _level_label(intensity)},
    }


def infer_visual_emotion(cues: list[str], candidates: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    normalized_candidates = candidates or []
    valid_candidates = []
    for candidate in normalized_candidates:
        label = FACE_EMOTION_MAP.get(str(candidate.get("label", "")).lower())
        confidence = candidate.get("confidence", 0)
        if label and isinstance(confidence, (int, float)) and confidence > 0:
            valid_candidates.append(
                {
                    "label": label,
                    "confidence": min(float(confidence), 0.82),
                    "evidence": str(candidate.get("evidence", "视觉模型给出的可观察表情候选")),
                    "source": "vision_model",
                }
            )
    if valid_candidates:
        return max(valid_candidates, key=lambda item: item["confidence"])

    text = "；".join(cues)
    matches = {
        label: [word for word in words if word in text]
        for label, words in VISUAL_AFFECT_KEYWORDS.items()
    }
    label = max(matches, key=lambda item: len(matches[item]))
    if not matches[label]:
        return None
    return {
        "label": label,
        "confidence": 0.62,
        "evidence": f"可观察线索：{', '.join(matches[label][:3])}",
        "source": "visual_cue_rules",
    }


def analyze_emotion(
    message: str,
    checkin: dict[str, Any] | None = None,
    face_emotion: dict[str, Any] | None = None,
) -> dict[str, object]:
    high_distress_words = _high_distress_matches(message)
    matches: dict[str, list[str]] = {
        label: [word for word in words if word in message]
        for label, words in EMOTION_KEYWORDS.items()
    }
    ranked_matches = sorted(
        ((item, words) for item, words in matches.items() if words),
        key=lambda item: len(item[1]),
        reverse=True,
    )
    label = ranked_matches[0][0] if ranked_matches else "neutral"
    secondary_emotions = [item[0] for item in ranked_matches[1:3]]
    if len(ranked_matches) >= 2 and len(ranked_matches[0][1]) == len(ranked_matches[1][1]):
        secondary_emotions = [item[0] for item in ranked_matches[:3] if item[0] != label]
    if any(word in message for word in ["孤独", "没人陪", "被孤立"]):
        if label != "loneliness":
            secondary_emotions = [label, *[item for item in secondary_emotions if item != "loneliness"]][:2]
        label = "loneliness"
    if high_distress_words:
        label = "sadness"
        secondary_emotions = [item for item in ["anxiety", "stress"] if item != label]
    has_text_match = bool(ranked_matches)

    if not has_text_match and face_emotion:
        face_label = str(face_emotion.get("label", "")).lower()
        label = FACE_EMOTION_MAP.get(face_label, "neutral")
    elif not has_text_match:
        label = "neutral"

    if high_distress_words:
        evidence = (
            f"用户提到高痛苦或轻生相关表达：{', '.join(high_distress_words[:4])}；"
            "情绪识别按强负性高痛苦处理，安全等级请以风险识别结果为准"
        )
        intensity = 0.9 + min(len(high_distress_words), 2) * 0.02
    elif not matches.get(label) and label == "neutral":
        evidence = "未检测到明显情绪关键词，暂按中性状态处理"
        intensity = 0.35
    else:
        evidence_words = matches.get(label, [])
        evidence = f"用户提到：{', '.join(evidence_words)}" if evidence_words else "结合表情占位结果推测当前情绪"
        intensity = 0.58 + min(len(evidence_words), 3) * 0.08

    if checkin and isinstance(checkin.get("stress_score"), int):
        stress_score = int(checkin["stress_score"])
        intensity += min(max(stress_score, 0), 10) * 0.02
        if stress_score >= 7:
            evidence += f"；打卡压力评分较高（{stress_score}/10）"

    if face_emotion and isinstance(face_emotion.get("confidence"), (int, float)):
        confidence = float(face_emotion["confidence"])
        evidence += f"；视觉表情线索置信度 {confidence:.2f}，仅作低权重参考"

    visual_confidence = None
    if face_emotion and isinstance(face_emotion.get("confidence"), (int, float)):
        visual_confidence = float(face_emotion["confidence"])

    dimensions = build_emotion_dimensions(
        label,
        round(min(intensity, 0.95), 2),
        checkin=checkin,
        visual_confidence=visual_confidence,
    )
    if high_distress_words:
        dimensions = {
            "valence": {"score": -0.88, "label": "negative"},
            "arousal": {"score": 0.64, "label": "medium"},
            "control": {"score": 0.16, "label": "low"},
            "intensity": {"score": round(min(intensity, 0.95), 2), "label": "high"},
        }

    return {
        "label": label,
        "primary_emotion": label,
        "secondary_emotions": secondary_emotions,
        "intensity": round(min(intensity, 0.95), 2),
        "evidence": evidence,
        "dimensions": dimensions,
        "risk_relevant": bool(high_distress_words),
    }

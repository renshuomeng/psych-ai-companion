from __future__ import annotations

import re
from typing import Any

from config import get_settings
from schemas.agent_v2 import PsychologicalCause, PsychologicalEmotion, PsychologicalState


CAUSE_KEYWORDS: list[tuple[str, list[str]]] = [
    ("thesis", ["论文", "毕业论文", "开题", "答辩", "导师", "盲审", "thesis", "dissertation"]),
    ("research", ["科研", "课题", "实验", "数据", "投稿", "文献", "研究", "paper", "research"]),
    ("exam", ["考试", "考研", "期末", "挂科", "复习", "绩点", "exam", "test"]),
    ("employment", ["就业", "求职", "找工作", "面试", "简历", "实习", "offer", "career", "job", "interview"]),
    ("romantic_relationship", ["恋爱", "分手", "前任", "喜欢的人", "伴侣", "男朋友", "女朋友"]),
    ("roommate", ["室友", "宿舍", "寝室"]),
    ("family", ["父母", "家里", "家庭", "妈妈", "爸爸", "亲戚"]),
    ("financial", ["钱", "经济", "学费", "生活费", "兼职", "负债", "financial"]),
    ("sleep", ["睡眠", "失眠", "睡不着", "熬夜", "早醒", "噩梦", "sleep", "insomnia"]),
    ("health", ["生病", "身体", "疼", "医院", "体检", "health", "illness"]),
    ("interpersonal", ["人际", "朋友", "同学", "关系", "冲突", "社交", "边界", "relationship"]),
    ("self_evaluation", ["不够好", "没用", "失败", "自责", "羞耻", "内耗", "完美", "否定自己"]),
    ("future_uncertainty", ["未来", "迷茫", "不确定", "不知道以后", "前途", "uncertain", "future"]),
    ("loneliness", ["孤独", "孤单", "没人理解", "没有朋友", "一个人", "lonely"]),
    ("academic", ["学习", "学业", "课程", "作业", "课堂", "学校", "academic", "study"]),
]

NEED_RULES: list[tuple[str, list[str]]] = [
    ("problem_solving", ["怎么办", "怎么做", "建议", "方法", "帮我", "如何", "怎么调整", "怎么缓解"]),
    ("information", ["是什么", "为什么", "资料", "解释", "原理", "依据", "科学", "知识"]),
    ("clarity", ["不知道", "混乱", "理不清", "想不明白", "不确定", "迷茫"]),
    ("sense_of_control", ["失控", "控制不住", "没有办法", "停不下来", "来不及"]),
    ("being_heard", ["听我说", "没人理解", "不知道跟谁说", "说出来"]),
    ("encouragement", ["鼓励", "撑不住", "坚持不下去", "没动力"]),
    ("social_connection", ["孤独", "没有朋友", "没人陪", "被孤立"]),
    ("rest", ["累", "疲惫", "困", "睡不着", "熬夜"]),
    ("self_compassion", ["自责", "羞耻", "内疚", "讨厌自己", "不够好"]),
]

EMOTION_MAP = {
    "joy": "calm",
    "anxiety": "anxiety",
    "sadness": "sadness",
    "anger": "anger",
    "fatigue": "fatigue",
    "loneliness": "loneliness",
    "stress": "stress",
    "neutral": "neutral",
    "mixed": "mixed",
}

NEGATIVE_EMOTIONS = {"anxiety", "sadness", "anger", "frustration", "loneliness", "shame", "guilt", "fatigue", "stress"}
FOLLOW_UP_MARKERS = ["上次", "之前", "刚才", "试了", "做了", "后来", "现在好多了", "还是"]
GREETING_MARKERS = ["你好", "hello", "hi", "在吗", "谢谢", "再见"]


def _contains_any(text: str, words: list[str]) -> list[str]:
    lowered = text.lower()
    return [word for word in words if word.lower() in lowered]


def _collect_text(
    message: str,
    multimodal_context: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []

    def add(source: str, value: Any) -> None:
        if isinstance(value, list):
            text = "\n".join(str(item) for item in value if str(item).strip())
        else:
            text = str(value or "").strip()
        if text:
            evidence.append({"source": source, "content": text[:180]})

    add("user_text", message)
    if multimodal_context:
        add("audio_transcript", multimodal_context.get("audio_transcript"))
        add("video_transcript", multimodal_context.get("video_transcript"))
        add("image_ocr", multimodal_context.get("image_ocr"))
        add("video_ocr", multimodal_context.get("video_ocr"))
        media = multimodal_context.get("media_analysis")
        if isinstance(media, dict):
            add("observable_cues", media.get("observable_cues"))

    for item in (recent_messages or [])[-3:]:
        if item.get("role") == "user":
            add("recent_user_message", item.get("content"))

    combined = "\n".join(item["content"] for item in evidence if item.get("content"))
    return combined, evidence


def _emotion_from_agent(emotion: dict[str, Any]) -> PsychologicalEmotion:
    label = str(emotion.get("primary_emotion") or emotion.get("label") or "unknown").lower()
    primary = EMOTION_MAP.get(label, "unknown")
    secondary = []
    for item in emotion.get("secondary_emotions") or []:
        mapped = EMOTION_MAP.get(str(item).lower())
        if mapped and mapped != primary and mapped not in secondary:
            secondary.append(mapped)
    dimensions = emotion.get("dimensions") if isinstance(emotion.get("dimensions"), dict) else {}
    valence = float((dimensions.get("valence") or {}).get("score", 0.0)) if dimensions else 0.0
    arousal = float((dimensions.get("arousal") or {}).get("score", 0.0)) if dimensions else 0.0
    control = float((dimensions.get("control") or {}).get("score", 0.5)) if dimensions else 0.5
    return PsychologicalEmotion(
        primary=primary,
        secondary=secondary[:3],
        intensity=float(emotion.get("intensity") or 0.0),
        valence=max(min(valence, 1.0), -1.0),
        arousal=max(min(arousal, 1.0), 0.0),
        control=max(min(control, 1.0), 0.0),
    )


def _classify_cause(text: str) -> PsychologicalCause:
    for category, words in CAUSE_KEYWORDS:
        matched = _contains_any(text, words)
        if matched:
            snippet = ""
            for term in matched:
                match = re.search(re.escape(term), text, flags=re.IGNORECASE)
                if match:
                    start = max(0, match.start() - 28)
                    end = min(len(text), match.end() + 48)
                    snippet = text[start:end].strip()
                    break
            return PsychologicalCause(
                category=category,
                specific=snippet or f"用户提到{matched[0]}相关困扰",
                evidence_terms=matched[:5],
            )
    if text.strip():
        return PsychologicalCause(category="other", specific=text.strip()[:90], evidence_terms=[])
    return PsychologicalCause(category="unknown", specific="", evidence_terms=[])


def _infer_needs(text: str, psychological_emotion: PsychologicalEmotion, cause: PsychologicalCause, risk: dict[str, Any]) -> list[str]:
    needs: list[str] = []
    if risk.get("level") in {"medium", "high"}:
        needs.append("safety")
    if psychological_emotion.primary in NEGATIVE_EMOTIONS or psychological_emotion.intensity >= 0.55:
        needs.extend(["emotional_validation", "being_heard"])
    for need, words in NEED_RULES:
        if _contains_any(text, words) and need not in needs:
            needs.append(need)
    if cause.category in {"thesis", "research", "exam", "academic", "employment"}:
        for need in ["clarity", "sense_of_control"]:
            if need not in needs:
                needs.append(need)
    if cause.category in {"loneliness", "interpersonal", "roommate", "romantic_relationship", "family"} and "social_connection" not in needs:
        needs.append("social_connection")
    if cause.category == "sleep" and "rest" not in needs:
        needs.append("rest")
    if cause.category == "self_evaluation" and "self_compassion" not in needs:
        needs.append("self_compassion")
    return needs[:5] or ["unknown"]


def _infer_stage(text: str, cause: PsychologicalCause, needs: list[str], confidence: float) -> str:
    lowered = text.lower()
    if any(marker.lower() in lowered for marker in FOLLOW_UP_MARKERS):
        return "follow_up"
    if text.strip() and any(marker.lower() in lowered for marker in GREETING_MARKERS) and len(text.strip()) <= 12:
        return "relationship_building"
    if confidence < get_settings().psy_state_low_confidence_threshold:
        return "exploration"
    if "problem_solving" in needs or "information" in needs:
        return "intervention"
    if cause.category == "unknown":
        return "cause_exploration"
    if cause.category == "other":
        return "exploration"
    if "clarity" in needs:
        return "goal_setting"
    return "emotion_clarification"


def _confidence(
    text: str,
    psychological_emotion: PsychologicalEmotion,
    cause: PsychologicalCause,
    needs: list[str],
    risk: dict[str, Any],
) -> float:
    value = 0.34
    if len(text.strip()) >= 8:
        value += 0.12
    if psychological_emotion.primary not in {"neutral", "unknown"}:
        value += 0.18
    if psychological_emotion.intensity >= 0.65:
        value += 0.08
    if cause.category not in {"unknown", "other"}:
        value += 0.18
    elif cause.category == "other":
        value += 0.05
    if needs != ["unknown"]:
        value += 0.08
    if risk.get("level") in {"medium", "high"}:
        value += 0.08
    return round(max(min(value, 0.92), 0.22), 2)


def _information_gaps(text: str, cause: PsychologicalCause, needs: list[str], confidence: float, risk: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if cause.category in {"unknown", "other"}:
        gaps.append("主要困扰来源还不够明确")
    if confidence < get_settings().psy_state_low_confidence_threshold:
        gaps.append("用户更希望被倾听还是获得具体方法尚不明确")
    if risk.get("level") == "medium":
        gaps.append("需要温和确认当前安全性和是否有进一步计划")
    if "problem_solving" in needs and len(text.strip()) < 24:
        gaps.append("具体情境、已尝试方法和最难的一步尚不明确")
    return gaps[:3]


async def analyze_psychological_state(
    message: str,
    *,
    emotion: dict[str, Any],
    risk: dict[str, Any],
    checkin: dict[str, Any] | None = None,
    multimodal_context: dict[str, Any] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    if not settings.psychological_state_analyzer_enabled:
        return PsychologicalState(
            emotion=_emotion_from_agent(emotion),
            confidence=0.0,
            uncertainty_reason="PSYCHOLOGICAL_STATE_ANALYZER_ENABLED=false",
            method="disabled",
        ).model_dump()

    text, evidence = _collect_text(message, multimodal_context=multimodal_context, recent_messages=recent_messages)
    if checkin:
        sources = checkin.get("stress_sources") or checkin.get("stress_source") or []
        if sources:
            text = "\n".join([text, "打卡压力来源：" + "、".join(str(item) for item in sources)])
            evidence.append({"source": "checkin", "content": "压力来源：" + "、".join(str(item) for item in sources)})

    psychological_emotion = _emotion_from_agent(emotion)
    cause = _classify_cause(text)
    needs = _infer_needs(text, psychological_emotion, cause, risk)
    confidence = _confidence(text, psychological_emotion, cause, needs, risk)
    stage = _infer_stage(text, cause, needs, confidence)
    gaps = _information_gaps(text, cause, needs, confidence, risk)
    uncertainty = "信息较完整，可形成初步心理状态假设" if confidence >= settings.psy_state_low_confidence_threshold else "文本或多模态线索不足，需要先澄清"

    return PsychologicalState(
        emotion=psychological_emotion,
        cause=cause,
        needs=needs,
        stage=stage,
        information_gaps=gaps,
        confidence=confidence,
        uncertainty_reason=uncertainty,
        evidence=evidence[:6],
        method="local_rules_v1",
    ).model_dump()

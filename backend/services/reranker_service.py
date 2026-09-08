import re
from typing import Any

from config import get_settings


def _query_terms(query: str) -> set[str]:
    terms = set(re.findall(r"[a-zA-Z0-9_]+", query.lower()))
    terms.update(ch for ch in query if "\u4e00" <= ch <= "\u9fff")
    return terms


def _as_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    text = str(value).strip().lower()
    if not text:
        return set()
    return {item.strip() for item in re.split(r"[,，/|;；\s]+", text) if item.strip()}


def _metadata_values(item: dict[str, Any], key: str) -> set[str]:
    metadata = item.get("metadata", {}) if isinstance(item.get("metadata"), dict) else {}
    return _as_values(item.get(key) if item.get(key) not in (None, "", []) else metadata.get(key))


def _field_score(item: dict[str, Any], key: str, desired: Any) -> float:
    desired_values = _as_values(desired)
    if not desired_values:
        return 0.0
    candidate_values = _metadata_values(item, key)
    if not candidate_values:
        return 0.0
    if desired_values & candidate_values:
        return 1.0
    if candidate_values & {"general", "neutral", "all", "universal"}:
        return 0.35
    if any(
        desired in candidate or candidate in desired
        for desired in desired_values
        for candidate in candidate_values
        if len(desired) >= 4 and len(candidate) >= 4
    ):
        return 0.55
    return 0.0


def _risk_compatibility(item: dict[str, Any], desired: Any) -> float:
    desired_values = _as_values(desired)
    desired_level = next(iter(desired_values), "low")
    candidate_values = _metadata_values(item, "risk_level") or {"low"}
    candidate_level = next(iter(candidate_values), "low")

    high_values = {"high", "crisis", "self_harm", "suicide", "harm_to_others"}
    medium_values = {"medium", "monitoring"}
    low_values = {"low", "none", "general"}

    if desired_level in high_values:
        if candidate_level in high_values:
            return 1.0
        if candidate_level in medium_values:
            return 0.65
        return 0.25
    if desired_level in medium_values:
        if candidate_level in medium_values:
            return 1.0
        if candidate_level in high_values:
            return 0.3
        if candidate_level in low_values:
            return 0.7
    if candidate_level in high_values:
        return 0.05
    if candidate_level in medium_values:
        return 0.55
    return 1.0


def _overlap_score(query: str, item: dict[str, Any]) -> float:
    terms = _query_terms(query)
    content = str(item.get("content", ""))
    title = str(item.get("title", ""))
    section = str(item.get("section", ""))
    haystack = f"{title} {section} {content}".lower()
    overlap = sum(1 for term in terms if term and term in haystack)
    return min(overlap / max(len(terms), 1), 1.0)


def _has_psychological_context(context: dict[str, Any] | None) -> bool:
    if not context:
        return False
    meaningful = {
        "emotion": {"", "neutral", "unknown"},
        "cause": {"", "general", "unknown"},
        "strategy": {"", "supportive_listening", "unknown"},
        "risk_level": {"", "low", "unknown"},
    }
    return any(str(context.get(key, "")).strip().lower() not in ignored for key, ignored in meaningful.items())


def _emotion_aware_score(
    query: str,
    item: dict[str, Any],
    psychological_context: dict[str, Any] | None,
) -> dict[str, float]:
    settings = get_settings()
    overlap_score = _overlap_score(query, item)
    vector_score = float(item.get("vector_score") or 0)
    keyword_score = float(item.get("keyword_score") or 0)
    semantic_score = max(vector_score, keyword_score, overlap_score)

    if not _has_psychological_context(psychological_context):
        return {
            "semantic_score": round(semantic_score, 4),
            "emotion_score": 0.0,
            "cause_score": 0.0,
            "strategy_score": 0.0,
            "risk_score": 0.0,
            "psychological_score": 0.0,
            "rerank_score": round(semantic_score, 4),
        }

    context = psychological_context or {}
    emotion_score = _field_score(item, "emotion", context.get("emotion"))
    cause_score = _field_score(item, "cause", context.get("cause"))
    strategy_score = _field_score(item, "strategy", context.get("strategy"))
    risk_score = _risk_compatibility(item, context.get("risk_level", "low"))

    weights = {
        "semantic": max(settings.retrieval_semantic_weight, 0),
        "emotion": max(settings.retrieval_emotion_weight, 0),
        "cause": max(settings.retrieval_cause_weight, 0),
        "strategy": max(settings.retrieval_strategy_weight, 0),
        "risk": max(settings.retrieval_risk_weight, 0),
    }
    total_weight = sum(weights.values()) or 1.0
    score = (
        semantic_score * weights["semantic"]
        + emotion_score * weights["emotion"]
        + cause_score * weights["cause"]
        + strategy_score * weights["strategy"]
        + risk_score * weights["risk"]
    ) / total_weight
    psychological_score = (
        emotion_score * weights["emotion"]
        + cause_score * weights["cause"]
        + strategy_score * weights["strategy"]
        + risk_score * weights["risk"]
    ) / max(weights["emotion"] + weights["cause"] + weights["strategy"] + weights["risk"], 1e-6)
    return {
        "semantic_score": round(semantic_score, 4),
        "emotion_score": round(emotion_score, 4),
        "cause_score": round(cause_score, 4),
        "strategy_score": round(strategy_score, 4),
        "risk_score": round(risk_score, 4),
        "psychological_score": round(psychological_score, 4),
        "rerank_score": round(score, 4),
    }


def rerank(
    query: str,
    candidates: list[dict[str, Any]],
    psychological_context: dict[str, Any] | None = None,
    emotion_aware: bool = False,
) -> list[dict[str, Any]]:
    terms = _query_terms(query)
    reranked: list[dict[str, Any]] = []
    for item in candidates:
        overlap_score = _overlap_score(query, item)
        vector_score = float(item.get("vector_score") or 0)
        keyword_score = float(item.get("keyword_score") or 0)
        if emotion_aware:
            scores = _emotion_aware_score(query, item, psychological_context)
            reranked.append({**item, **scores})
            continue
        score = vector_score * 0.2 + keyword_score * 0.55 + overlap_score * 0.25
        reranked.append(
            {
                **item,
                "semantic_score": round(max(vector_score, keyword_score, overlap_score), 4),
                "rerank_score": round(score, 4),
            }
        )
    return sorted(reranked, key=lambda item: item.get("rerank_score", 0), reverse=True)

import uuid
from typing import Any


def _evidence(
    source: str,
    modality: str,
    observation: str,
    confidence: float,
    explicit: bool,
    risk_relevant: bool = False,
    timestamp: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "evidence_id": uuid.uuid4().hex,
        "source": source,
        "modality": modality,
        "observation": observation[:300],
        "confidence": round(max(0.0, min(confidence, 1.0)), 2),
        "is_explicit_user_statement": explicit,
        "risk_relevant": risk_relevant,
        "timestamp": timestamp or {},
    }


def build_evidence_objects(
    user_text: str,
    checkin: dict[str, Any] | None,
    multimodal_context: dict[str, Any] | None,
    risk: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    context = multimodal_context or {}
    risk_sources = set((risk or {}).get("matched_sources", []))
    evidence: list[dict[str, Any]] = []
    if user_text.strip():
        evidence.append(
            _evidence(
                "user_text",
                "text",
                user_text.strip(),
                1.0,
                True,
                "user_text" in risk_sources,
            )
        )
    if checkin:
        stress = checkin.get("stress_score")
        sources = checkin.get("stress_sources") or checkin.get("stress_source") or []
        evidence.append(
            _evidence(
                "checkin",
                "self_report",
                f"压力自评分 {stress}/10；压力来源：{', '.join(map(str, sources))}",
                0.95,
                True,
                False,
            )
        )
    for source, modality in [
        ("audio_transcript", "audio"),
        ("video_transcript", "video"),
    ]:
        text = str(context.get(source, "")).strip()
        if text:
            evidence.append(
                _evidence(source, modality, text, 0.9, True, source in risk_sources)
            )
    media = context.get("media_analysis") if isinstance(context.get("media_analysis"), dict) else {}
    for item in media.get("ocr_text", []) if isinstance(media, dict) else []:
        evidence.append(_evidence("image_ocr", "ocr", str(item), 0.86, True, "image_ocr" in risk_sources))
    for item in media.get("observable_cues", []) if isinstance(media, dict) else []:
        evidence.append(_evidence("image_visual", "vision", str(item), 0.55, False, False))
    for candidate in media.get("visual_affect_candidates", []) if isinstance(media, dict) else []:
        label = candidate.get("label", "neutral")
        confidence = candidate.get("confidence", 0.5)
        observation = f"视觉表情候选：{label}；{candidate.get('evidence', '')}"
        evidence.append(_evidence("video_visual", "vision", observation, float(confidence), False, False))
    return evidence


def split_emotion_evidence(evidence: list[dict[str, Any]], primary_label: str) -> dict[str, Any]:
    supporting: list[dict[str, str]] = []
    conflicting: list[dict[str, str]] = []
    for item in evidence:
        source = item.get("source", "")
        observation = str(item.get("observation", ""))
        if source in {"user_text", "audio_transcript", "checkin"}:
            supporting.append({"source": source, "content": observation[:180]})
        elif "neutral" in observation.lower() and primary_label != "neutral":
            conflicting.append({"source": source, "content": observation[:180]})
        elif source.endswith("_visual"):
            supporting.append({"source": source, "content": observation[:180]})
    uncertainty = (
        "文字、自评和语音转写优先；图片或视频表情只作为低权重辅助线索，不能否定用户明确表达。"
    )
    return {
        "supporting_evidence": supporting,
        "conflicting_evidence": conflicting,
        "uncertainty": uncertainty,
    }

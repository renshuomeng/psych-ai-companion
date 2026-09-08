import json
from pathlib import Path
from typing import Any

from services.ark_client import analyze_image


IMAGE_ANALYSIS_PROMPT = """
请分析这张用户主动上传的图片，只返回 JSON：
{
  "summary": "图片内容概述",
  "observable_cues": ["客观可观察到的表情、姿态或场景"],
  "visual_affect_candidates": [
    {"label": "joy|anger|sadness|anxiety|fatigue|neutral", "confidence": 0.0, "evidence": "仅基于可观察表情线索"}
  ],
  "ocr_text": ["图片中可识别的文字"],
  "possible_context": ["仅作为可能背景，不作诊断"],
  "safety_signals": ["图片文字或场景中明确可观察到的安全信号"],
  "uncertainty": "分析局限"
}
禁止根据外貌诊断心理疾病，禁止仅凭表情推断自杀风险。
visual_affect_candidates 只描述可观察表情倾向，不代表用户真实心理状态。
"""


def _parse_jsonish(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start : end + 1])
        return {
            "summary": text,
            "observable_cues": [],
            "visual_affect_candidates": [],
            "ocr_text": [],
            "possible_context": [],
            "safety_signals": [],
            "uncertainty": "模型未按 JSON 返回，已保留原始摘要文本。",
        }


async def analyze_image_file(path: Path) -> dict[str, Any]:
    result = await analyze_image(path, IMAGE_ANALYSIS_PROMPT)
    payload = _parse_jsonish(result.text)
    payload.setdefault("observable_cues", [])
    payload.setdefault("visual_affect_candidates", [])
    payload.setdefault("ocr_text", [])
    payload["provider_metadata"] = result.as_metadata()
    return payload

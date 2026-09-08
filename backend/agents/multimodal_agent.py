from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from database.models import Attachment
from schemas.errors import AppError
from services.image_service import analyze_image_file
from services.speech_service import transcribe_audio
from services.storage_service import get_attachment
from services.video_service import analyze_video_file


async def process_attachments(
    db: Session,
    session_id: str,
    file_ids: list[str],
) -> dict[str, Any]:
    attachments: list[dict[str, Any]] = []
    transcript_texts: list[str] = []
    utterances: list[dict[str, Any]] = []
    image_summaries: list[dict[str, Any]] = []
    video_summaries: list[dict[str, Any]] = []
    ocr_text: list[str] = []
    observable_cues: list[str] = []
    visual_affect_candidates: list[dict[str, Any]] = []
    uncertainty: list[str] = []
    provider_metadata: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for file_id in file_ids:
        attachment: Attachment = get_attachment(db, file_id, session_id)
        item = {"file_id": attachment.file_id, "kind": attachment.kind, "status": "processing"}
        path = Path(attachment.local_path)

        try:
            if attachment.kind == "image":
                result = await analyze_image_file(path)
                image_summaries.append(result)
                ocr_text.extend(result.get("ocr_text", []))
                observable_cues.extend(result.get("observable_cues", []))
                visual_affect_candidates.extend(result.get("visual_affect_candidates", []))
                if result.get("uncertainty"):
                    uncertainty.append(str(result["uncertainty"]))
                provider_metadata.append(result.get("provider_metadata", {}))
            elif attachment.kind == "audio":
                result = await transcribe_audio(path, session_id)
                transcript_texts.append(result["transcript"])
                utterances.extend(result.get("utterances", []))
                provider_metadata.append(
                    {
                        "llm_provider": result.get("provider"),
                        "model": "volc.bigasr.auc_turbo",
                        "request_id": result.get("request_id"),
                    }
                )
            elif attachment.kind == "video":
                result = await analyze_video_file(path, session_id)
                video_summaries.append(result)
                if result.get("transcript"):
                    transcript_texts.append(result["transcript"])
                utterances.extend(result.get("utterances", []))
                ocr_text.extend(result.get("ocr_text", []))
                observable_cues.extend(result.get("observable_cues", []))
                visual_affect_candidates.extend(result.get("visual_affect_candidates", []))
                if result.get("uncertainty"):
                    uncertainty.append(str(result["uncertainty"]))
                provider_metadata.append(result.get("provider_metadata", {}))
            else:
                raise AppError(
                    "invalid_file_type",
                    "不支持的附件类型。",
                    "multimodal_processing",
                    status_code=400,
                )

            item["status"] = "processed"
        except AppError as exc:
            item["status"] = "failed"
            item["error"] = exc.detail.model_dump()
            errors.append(exc.detail.model_dump())
        attachments.append(item)

    return {
        "attachments": attachments,
        "transcript": {
            "text": "\n".join(transcript_texts).strip(),
            "utterances": utterances,
        },
        "media_analysis": {
            "image_summaries": image_summaries,
            "video_summaries": video_summaries,
            "ocr_text": ocr_text,
            "observable_cues": observable_cues,
            "visual_affect_candidates": visual_affect_candidates,
            "uncertainty": uncertainty,
        },
        "risk_sources": {
            "audio_transcript": "\n".join(transcript_texts).strip(),
            "video_transcript": "\n".join(
                item.get("transcript", "") for item in video_summaries if isinstance(item, dict)
            ).strip(),
            "image_ocr": ocr_text,
            "video_ocr": ocr_text,
        },
        "provider_metadata": provider_metadata,
        "errors": errors,
    }

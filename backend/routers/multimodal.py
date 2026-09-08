import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.coordinator_agent import run_multimodal_flow
from agents.multimodal_agent import process_attachments
from auth.dependencies import CurrentPrincipal, require_permission, sanitize_chat_payload_for_principal
from auth.permissions import Permission
from database.db import get_db
from schemas.chat import MultimodalChatRequest, MultimodalChatResponse
from schemas.errors import AppError


router = APIRouter()


@router.post("", response_model=MultimodalChatResponse)
@router.post("/", response_model=MultimodalChatResponse)
async def multimodal_chat(
    payload: MultimodalChatRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.MULTIMODAL_USE, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    if not payload.message.strip() and not payload.file_ids:
        raise AppError(
            "empty_input",
            "请至少输入文字或上传一个图片、音频、视频文件。",
            "multimodal_chat",
            status_code=400,
        )

    processed = await process_attachments(db, payload.session_id, payload.file_ids)
    successful_modalities = [
        item["kind"] for item in processed["attachments"] if item["status"] == "processed"
    ]
    if payload.message.strip():
        successful_modalities.insert(0, "text")
    if not payload.message.strip() and not successful_modalities:
        first_error = processed["errors"][0] if processed["errors"] else None
        if first_error:
            raise AppError(
                first_error["code"],
                first_error["message"],
                first_error["stage"],
                first_error.get("retryable", False),
                first_error.get("request_id"),
                status_code=400,
            )
        raise AppError("invalid_media", "所有模态处理失败。", "multimodal_chat", status_code=400)

    context = {
        "audio_transcript": processed["transcript"]["text"],
        "video_transcript": processed["risk_sources"]["video_transcript"],
        "image_ocr": processed["media_analysis"]["ocr_text"],
        "video_ocr": processed["media_analysis"]["ocr_text"],
        "media_analysis": processed["media_analysis"],
        "attachments": processed["attachments"],
    }
    result = await run_multimodal_flow(
        session_id=payload.session_id,
        message=payload.message.strip(),
        checkin=payload.checkin.model_dump() if payload.checkin else None,
        multimodal_context=context,
    )
    provider_metadata = result.get("provider_metadata") or {}
    if processed["provider_metadata"]:
        provider_metadata["media_providers"] = processed["provider_metadata"]

    response = {
        "session_id": payload.session_id,
        "message_id": uuid.uuid4().hex,
        "input_modalities": sorted(set(successful_modalities)),
        "attachments": processed["attachments"],
        "transcript": processed["transcript"],
        "media_analysis": processed["media_analysis"],
        "emotion": result["emotion"],
        "risk": result["risk"],
        "reply": result["reply"],
        "interventions": result["interventions"],
        "agent_trace": result["agent_trace"],
        "provider_metadata": provider_metadata,
        "knowledge_sources": result.get("knowledge_sources", []),
        "evidence": result.get("evidence", []),
        "retrieval": result.get("retrieval", {}),
        "psychological_state": result.get("psychological_state", {}),
        "strategy_plan": result.get("strategy_plan", {}),
        "rag_route": result.get("rag_route", {}),
        "request_metrics": result.get("request_metrics", {}),
    }
    return sanitize_chat_payload_for_principal(response, principal)

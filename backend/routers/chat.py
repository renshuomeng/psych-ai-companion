from fastapi import APIRouter, Depends

from agents.coordinator_agent import run_chat_flow
from auth.dependencies import CurrentPrincipal, require_permission, sanitize_chat_payload_for_principal
from auth.permissions import Permission
from schemas.chat import ChatRequest


router = APIRouter()


@router.post("")
@router.post("/")
async def chat(
    payload: ChatRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CHAT_USE, allow_demo_user=True)),
) -> dict:
    result = await run_chat_flow(
        message=payload.message.strip(),
        checkin=payload.checkin.model_dump() if payload.checkin else None,
        face_emotion=payload.face_emotion.model_dump() if payload.face_emotion else None,
    )
    return sanitize_chat_payload_for_principal(result, principal)

from fastapi import APIRouter, Depends

from auth.dependencies import CurrentPrincipal, require_permission
from auth.permissions import Permission
from services.stt_service import transcribe_audio_placeholder


router = APIRouter()


@router.get("")
@router.get("/")
def stt_status(
    _: CurrentPrincipal = Depends(require_permission(Permission.MULTIMODAL_USE, allow_demo_user=True)),
) -> dict[str, str]:
    return transcribe_audio_placeholder()


@router.post("")
@router.post("/")
def stt_upload_placeholder(
    _: CurrentPrincipal = Depends(require_permission(Permission.MULTIMODAL_USE, allow_demo_user=True)),
) -> dict[str, str]:
    return transcribe_audio_placeholder()

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, ensure_own_conversation, require_permission, sanitize_conversation_payload
from auth.permissions import Permission
from database.db import get_db
from schemas.multimodal import JobResponse, MultimodalJobCreateRequest
from services.job_service import cancel_job, create_job, get_job, job_to_response
from services.multimodal_job_worker import wake_multimodal_job_worker


router = APIRouter()


def _safe_job_response(response: dict, principal: CurrentPrincipal) -> dict:
    result = response.get("result")
    if isinstance(result, dict):
        response = {**response, "result": sanitize_conversation_payload(result, principal)}
    return response


@router.post("", response_model=JobResponse)
@router.post("/", response_model=JobResponse)
def create_multimodal_job(
    payload: MultimodalJobCreateRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.MULTIMODAL_USE, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    ensure_own_conversation(db, payload.session_id, principal)
    job = create_job(db, payload, owner_id=principal.owner_id)
    wake_multimodal_job_worker()
    return job_to_response(job)


@router.get("/{job_id}", response_model=JobResponse)
def get_multimodal_job(
    job_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    job = get_job(db, job_id)
    ensure_own_conversation(db, job.session_id, principal)
    return _safe_job_response(job_to_response(job), principal)


@router.delete("/{job_id}", response_model=JobResponse)
def cancel_multimodal_job(
    job_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_DELETE_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict:
    job = get_job(db, job_id)
    ensure_own_conversation(db, job.session_id, principal)
    return _safe_job_response(cancel_job(db, job_id), principal)

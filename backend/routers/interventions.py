from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, ensure_own_conversation, require_permission
from auth.permissions import Permission
from database.db import get_db
from database.models import InterventionSession, utcnow
from schemas.errors import AppError


router = APIRouter()


def _get_intervention(db: Session, intervention_id: str) -> InterventionSession:
    row = db.get(InterventionSession, intervention_id)
    if not row:
        raise AppError(
            "intervention_not_found",
            "干预记录不存在。",
            "intervention_lookup",
            status_code=404,
        )
    return row


@router.post("/{intervention_id}/start")
def start_intervention(
    intervention_id: str,
    payload: dict[str, object],
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session_id = str(payload.get("session_id", ""))
    ensure_own_conversation(db, session_id, principal)
    row = db.get(InterventionSession, intervention_id)
    if not row:
        row = InterventionSession(
            intervention_id=intervention_id,
            session_id=session_id,
            intervention_type=str(payload.get("type", "unknown")),
            title=str(payload.get("title", "自助练习")),
            status="started",
            pre_stress_score=payload.get("pre_stress_score") if isinstance(payload.get("pre_stress_score"), int) else None,
            started_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(row)
    else:
        row.status = "started"
        row.started_at = utcnow()
        row.updated_at = utcnow()
        if isinstance(payload.get("pre_stress_score"), int):
            row.pre_stress_score = int(payload["pre_stress_score"])
    db.commit()
    return {"status": row.status, "intervention_id": intervention_id}


@router.post("/{intervention_id}/complete")
def complete_intervention(
    intervention_id: str,
    payload: dict[str, object],
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _get_intervention(db, intervention_id)
    ensure_own_conversation(db, row.session_id, principal)
    row.status = "completed"
    row.completed_at = utcnow()
    row.updated_at = utcnow()
    if isinstance(payload.get("post_stress_score"), int):
        row.post_stress_score = int(payload["post_stress_score"])
    db.commit()
    return {"status": row.status, "intervention_id": intervention_id}


@router.post("/{intervention_id}/feedback")
def feedback_intervention(
    intervention_id: str,
    payload: dict[str, object],
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _get_intervention(db, intervention_id)
    ensure_own_conversation(db, row.session_id, principal)
    if isinstance(payload.get("helpfulness"), int):
        row.helpfulness = int(payload["helpfulness"])
    row.feedback_text = str(payload.get("feedback_text", ""))[:1000]
    row.updated_at = utcnow()
    db.commit()
    return {"status": "feedback_saved", "intervention_id": intervention_id}

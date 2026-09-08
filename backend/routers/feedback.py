import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, ensure_own_conversation, require_permission
from auth.permissions import Permission
from database.db import get_db
from database.models import Feedback


router = APIRouter()


class FeedbackRequest(BaseModel):
    session_id: str = Field(min_length=1)
    pre_stress_score: int = Field(ge=0, le=10)
    post_stress_score: int = Field(ge=0, le=10)
    helpfulness: int = Field(ge=1, le=5)
    felt_understood: int = Field(ge=1, le=5)
    intervention_used: str = ""
    comment: str = Field(default="", max_length=500)


@router.post("")
@router.post("/")
def create_feedback(
    payload: FeedbackRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ensure_own_conversation(db, payload.session_id, principal)
    feedback = Feedback(
        feedback_id=uuid.uuid4().hex,
        session_id=payload.session_id,
        pre_stress_score=payload.pre_stress_score,
        post_stress_score=payload.post_stress_score,
        helpfulness=payload.helpfulness,
        felt_understood=payload.felt_understood,
        intervention_used=payload.intervention_used[:64],
        comment=payload.comment,
    )
    db.add(feedback)
    db.commit()
    return {"status": "saved", "feedback_id": feedback.feedback_id}

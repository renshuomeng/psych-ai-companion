from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, ensure_own_conversation, require_permission
from auth.permissions import Permission
from database.db import get_db
from database.models import Conversation, Feedback


router = APIRouter()


@router.get("")
@router.get("/")
def report(
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    own_session_ids = [
        row.id
        for row in db.query(Conversation.id)
        .filter(Conversation.owner_id == principal.owner_id)
        .all()
    ]
    records = (
        db.query(Feedback)
        .filter(Feedback.session_id.in_(own_session_ids))
        .order_by(Feedback.created_at.desc())
        .limit(20)
        .all()
        if own_session_ids
        else []
    )
    if not records:
        return {
            "summary": "暂无真实反馈数据。评分变化仅用于竞赛演示观察，不代表治疗效果。",
            "items": [],
        }
    items = [
        {
            "date": item.created_at.date().isoformat(),
            "stress_score": item.post_stress_score,
            "emotion": item.intervention_used or "未填写",
        }
        for item in reversed(records[-7:])
    ]
    return {
        "summary": "最近真实反馈趋势。评分下降不代表治疗效果。",
        "items": items,
    }


@router.get("/session/{session_id}")
def session_report(
    session_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.CONVERSATION_READ_OWN, allow_demo_user=True)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ensure_own_conversation(db, session_id, principal)
    records = (
        db.query(Feedback)
        .filter(Feedback.session_id == session_id)
        .order_by(Feedback.created_at.asc())
        .all()
    )
    if not records:
        return {
            "session_id": session_id,
            "summary": "当前会话暂无反馈数据。",
            "items": [],
            "common_interventions": [],
            "average_helpfulness": None,
            "average_felt_understood": None,
            "disclaimer": "评分变化不代表治疗效果。",
        }
    interventions = Counter(item.intervention_used for item in records if item.intervention_used)
    return {
        "session_id": session_id,
        "summary": "当前会话真实反馈汇总。",
        "items": [
            {
                "date": item.created_at.isoformat(),
                "pre_stress_score": item.pre_stress_score,
                "post_stress_score": item.post_stress_score,
                "helpfulness": item.helpfulness,
                "felt_understood": item.felt_understood,
                "intervention_used": item.intervention_used,
            }
            for item in records
        ],
        "common_interventions": [
            {"intervention": name, "count": count}
            for name, count in interventions.most_common(5)
        ],
        "average_helpfulness": round(sum(item.helpfulness for item in records) / len(records), 2),
        "average_felt_understood": round(
            sum(item.felt_understood for item in records) / len(records), 2
        ),
        "disclaimer": "评分下降不代表治疗效果。",
    }

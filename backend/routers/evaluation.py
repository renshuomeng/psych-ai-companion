from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, require_permission
from auth.permissions import Permission
from config import get_settings
from database.db import get_db
from database.models import EvaluationRun, HumanEvaluationReview, utcnow
from schemas.errors import AppError


router = APIRouter()


class HumanEvaluationScoreRequest(BaseModel):
    run_id: str = Field(default="", max_length=128)
    case_id: str = Field(min_length=1, max_length=128)
    score: float | None = Field(default=None, ge=0, le=10)
    rubric: dict[str, Any] = Field(default_factory=dict)
    comment: str = Field(default="", max_length=1000)
    llm_judge_reviewed: bool = False


def _scrub_case_score(row: dict[str, Any], *, include_case_input: bool = False) -> dict[str, Any]:
    case = row.get("case") if isinstance(row.get("case"), dict) else {}
    candidate = row.get("candidate") if isinstance(row.get("candidate"), dict) else {}
    scrubbed_candidate = {
        "system_id": candidate.get("system_id"),
        "response": candidate.get("response", ""),
        "latency_ms": candidate.get("latency_ms", 0),
        "errors": candidate.get("errors", []),
    }
    payload = {
        "run_id": row.get("run_id", ""),
        "case_id": row.get("case_id", ""),
        "case": {
            "case_id": case.get("case_id") or row.get("case_id", ""),
            "dataset": case.get("dataset", ""),
            "tags": case.get("tags", []),
        },
        "candidate": scrubbed_candidate,
        "scores": row.get("scores", []),
    }
    if include_case_input:
        payload["case"]["turns"] = case.get("turns", [])
    return payload


def _load_case_scores(run_id: str) -> list[dict[str, Any]]:
    from backend.evaluation.runner import RESULTS_DIR

    case_scores_path = RESULTS_DIR / run_id / "case_scores.jsonl"
    if not case_scores_path.exists():
        return []
    rows = []
    for line in case_scores_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _sanitize_run_detail(detail: dict[str, Any], principal: CurrentPrincipal) -> dict[str, Any]:
    if principal.has_permission(Permission.AGENT_TRACE_VIEW):
        return detail
    sanitized = dict(detail)
    case_scores = sanitized.get("case_scores")
    if isinstance(case_scores, list):
        sanitized["case_scores"] = [_scrub_case_score(row) for row in case_scores if isinstance(row, dict)]
    return sanitized


@router.get("/registry")
def get_evaluation_registry(
    _: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_VIEW)),
) -> dict[str, object]:
    from backend.evaluation.registry import list_frameworks, list_systems

    settings = get_settings()
    return {
        "frameworks": list_frameworks(),
        "systems": list_systems(),
        "limits": {
            "allow_paid_full_run": settings.eval_allow_paid_full_run,
            "smoke_case_limit": settings.eval_smoke_case_limit,
        },
    }


@router.post("/run")
def run_evaluation(
    payload: dict[str, object] = Body(default_factory=dict),
    principal: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_RUN_CREATE)),
) -> dict[str, object]:
    from backend.evaluation.runner import config_from_payload, run_evaluation_sync

    settings = get_settings()
    config = config_from_payload(payload)
    if config.limit > settings.eval_smoke_case_limit:
        if not principal.has_permission(Permission.EVALUATION_RUN_FULL):
            raise AppError(
                "evaluation_full_run_forbidden",
                "无权运行完整评测。",
                "evaluation_rbac",
                status_code=403,
            )
        if not settings.eval_allow_paid_full_run:
            raise AppError(
                "evaluation_full_run_disabled",
                "完整付费评测开关未启用。",
                "evaluation_rbac",
                status_code=403,
            )
    return run_evaluation_sync(config)


@router.get("/runs")
def list_evaluation_runs(
    _: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_VIEW)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from backend.evaluation.runner import list_saved_runs

    rows = db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(20).all()
    saved_runs = list_saved_runs(limit=20)
    return {
        "saved_runs": saved_runs,
        "runs": [
            {
                "run_id": row.run_id,
                "status": row.status,
                "summary": json.loads(row.summary_json or "{}"),
                "output_dir": row.output_dir,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ],
    }


@router.get("/runs/{run_id}")
def get_evaluation_run(
    run_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_VIEW)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from backend.evaluation.runner import RESULTS_DIR

    row = db.get(EvaluationRun, run_id)
    output_dir = RESULTS_DIR / run_id
    if output_dir.exists():
        summary_path = output_dir / "summary.json"
        config_path = output_dir / "config.json"
        case_scores_path = output_dir / "case_scores.jsonl"
        detail = {
            "run_id": run_id,
            "status": "completed",
            "config": json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {},
            "summary": json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {},
            "case_scores": [
                json.loads(line)
                for line in case_scores_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            if case_scores_path.exists()
            else [],
            "output_dir": str(output_dir),
        }
        return _sanitize_run_detail(detail, principal)
    if not row:
        raise AppError("evaluation_run_not_found", "评测记录不存在。", "evaluation", status_code=404)
    return {
        "run_id": row.run_id,
        "status": row.status,
        "config": json.loads(row.config_json or "{}"),
        "summary": json.loads(row.summary_json or "{}"),
        "output_dir": row.output_dir,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/compare")
def compare_evaluation_runs(
    payload: dict[str, object] = Body(default_factory=dict),
    _: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_COMPARE)),
) -> dict[str, object]:
    from backend.evaluation.runner import compare_runs

    baseline_run_id = str(payload.get("baseline_run_id") or "")
    candidate_run_id = str(payload.get("candidate_run_id") or "")
    if not baseline_run_id or not candidate_run_id:
        raise AppError(
            "evaluation_compare_missing_runs",
            "需要同时提供 baseline_run_id 和 candidate_run_id。",
            "evaluation",
            status_code=400,
        )
    return compare_runs(baseline_run_id, candidate_run_id)


@router.get("/review/cases")
def list_human_review_cases(
    run_id: str | None = None,
    principal: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_REVIEW)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    selected_run_id = run_id
    if not selected_run_id:
        latest = db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).first()
        selected_run_id = latest.run_id if latest else ""
    rows = _load_case_scores(selected_run_id) if selected_run_id else []
    return {
        "run_id": selected_run_id or "",
        "items": [_scrub_case_score(row, include_case_input=True) for row in rows[:100]],
        "reviewer_id": principal.id,
    }


@router.post("/review/score")
def score_human_review_case(
    payload: HumanEvaluationScoreRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_HUMAN_SCORE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    row = HumanEvaluationReview(
        review_id=f"HEVAL_{payload.case_id}_{utcnow().strftime('%Y%m%d%H%M%S%f')}",
        reviewer_user_id=principal.id,
        run_id=payload.run_id,
        case_id=payload.case_id,
        score=payload.score,
        rubric_json=json.dumps(payload.rubric, ensure_ascii=False, sort_keys=True),
        comment=payload.comment,
        llm_judge_reviewed=payload.llm_judge_reviewed,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(row)
    db.commit()
    return {"status": "saved", "review_id": row.review_id}


@router.get("/review/export")
def export_human_review_csv(
    _: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_EXPORT_HUMAN_REVIEW)),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    rows = db.query(HumanEvaluationReview).order_by(HumanEvaluationReview.created_at.desc()).limit(1000).all()
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["review_id", "reviewer_user_id", "run_id", "case_id", "score", "comment", "llm_judge_reviewed", "created_at"],
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "review_id": row.review_id,
                "reviewer_user_id": row.reviewer_user_id,
                "run_id": row.run_id,
                "case_id": row.case_id,
                "score": row.score,
                "comment": row.comment,
                "llm_judge_reviewed": row.llm_judge_reviewed,
                "created_at": row.created_at.isoformat(),
            }
        )
    return PlainTextResponse(output.getvalue(), media_type="text/csv")

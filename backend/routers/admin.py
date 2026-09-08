from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, require_any_permission, require_permission
from auth.permissions import Permission, ROLE_PERMISSIONS, Role, role_values
from auth.schemas import AdminUserCreateRequest, AdminUserUpdateRequest, user_to_public
from auth.service import create_user, log_admin_action, update_user_by_admin
from config import get_settings
from database.db import get_db
from database.models import AdminAuditLog, User
from schemas.errors import AppError
from services.knowledge_ingestion_service import build_knowledge_base
from services.vector_store_service import delete_source, get_source, list_sources


router = APIRouter()


def _masked_secret(value: str) -> dict[str, object]:
    clean = value.strip()
    if not clean:
        return {"configured": False, "masked": ""}
    return {"configured": True, "masked": f"{clean[:3]}****{clean[-4:]}" if len(clean) >= 8 else "****"}


@router.get("/permissions")
def permission_registry(
    _: CurrentPrincipal = Depends(require_permission(Permission.ROLE_MANAGE)),
) -> dict[str, Any]:
    return {
        "roles": role_values(),
        "permissions": sorted(permission.value for permission in Permission),
        "role_permissions": {
            role.value: sorted(permission.value for permission in permissions)
            for role, permissions in ROLE_PERMISSIONS.items()
        },
    }


@router.get("/system")
def system_status(
    _: CurrentPrincipal = Depends(require_permission(Permission.SECRET_STATUS_VIEW)),
) -> dict[str, Any]:
    settings = get_settings()
    return {
        "environment": settings.app_env,
        "public_access_enabled": settings.public_access_enabled,
        "database_url": "configured",
        "models": {
            "doubao_model_id": settings.doubao_model_id,
            "doubao_vision_model_id": settings.doubao_vision_model_id,
            "doubao_video_model_id": settings.doubao_video_model_id,
            "eval_judge_provider": settings.eval_judge_provider,
            "eval_judge_model_id": settings.eval_judge_model_id,
        },
        "secrets": {
            "ark_api_key": _masked_secret(settings.ark_api_key),
            "volc_speech_api_key": _masked_secret(settings.volc_speech_api_key),
            "volc_speech_access_key": _masked_secret(settings.volc_speech_access_key),
        },
        "feature_flags": {
            "rag_enabled": settings.rag_enabled,
            "rag_v1_enabled": settings.rag_v1_enabled,
            "agent_v2_enabled": settings.agent_v2_enabled,
            "psychological_state_analyzer_enabled": settings.psychological_state_analyzer_enabled,
            "strategy_planner_enabled": settings.strategy_planner_enabled,
            "rag_router_enabled": settings.rag_router_enabled,
            "eval_allow_paid_full_run": settings.eval_allow_paid_full_run,
            "safety_llm_review_enabled": settings.safety_llm_review_enabled,
        },
        "knowledge_production": {
            "index_mode": settings.effective_rag_index_mode,
            "staging_mode": settings.rag_staging_mode,
        },
    }


@router.get("/users")
def list_users(
    _: CurrentPrincipal = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    users = db.query(User).order_by(User.created_at.desc()).limit(500).all()
    return {"items": [user_to_public(user).model_dump(mode="json") for user in users]}


@router.post("/users")
def admin_create_user(
    payload: AdminUserCreateRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.USER_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    actor = principal.user
    if not actor:
        raise AppError("database_user_required", "该操作需要登录用户账号。", "auth", status_code=401)
    user = create_user(
        db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        role=payload.role,
        is_active=payload.is_active,
    )
    log_admin_action(
        db,
        actor_user_id=actor.id,
        action="user_created",
        target_type="user",
        target_id=user.id,
        metadata={"role": payload.role.value, "is_active": payload.is_active},
    )
    db.commit()
    db.refresh(user)
    return user_to_public(user).model_dump(mode="json")


@router.patch("/users/{user_id}")
def admin_update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.ROLE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    actor = principal.user
    target = db.get(User, user_id)
    if not actor:
        raise AppError("database_user_required", "该操作需要登录用户账号。", "auth", status_code=401)
    if not target:
        raise AppError("user_not_found", "用户不存在。", "admin_user_management", status_code=404)
    updated = update_user_by_admin(
        db,
        actor=actor,
        target=target,
        role=payload.role,
        is_active=payload.is_active,
    )
    return user_to_public(updated).model_dump(mode="json")


@router.get("/audit-log")
def admin_audit_log(
    _: CurrentPrincipal = Depends(require_permission(Permission.ROLE_MANAGE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = db.query(AdminAuditLog).order_by(AdminAuditLog.created_at.desc()).limit(200).all()
    return {
        "items": [
            {
                "audit_id": row.audit_id,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "target_type": row.target_type,
                "target_id": row.target_id,
                "metadata": json.loads(row.metadata_json or "{}"),
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]
    }


@router.post("/knowledge/import")
async def import_knowledge(
    _: CurrentPrincipal = Depends(require_any_permission(Permission.DEV_CONFIG_EDIT, Permission.PRODUCTION_KB_PUBLISH)),
    db: Session = Depends(get_db),
) -> dict:
    return await build_knowledge_base(db)


@router.get("/knowledge/sources")
def admin_list_sources(
    _: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_VIEW)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return {"sources": list_sources(db)}


@router.get("/knowledge/sources/{source_id}")
def admin_get_source(
    source_id: str,
    _: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_VIEW)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    source = get_source(db, source_id)
    if not source:
        raise AppError("knowledge_source_not_found", "知识来源不存在。", "admin_knowledge", status_code=404)
    return source


@router.delete("/knowledge/sources/{source_id}")
def admin_delete_source(
    source_id: str,
    principal: CurrentPrincipal = Depends(require_permission(Permission.PRODUCTION_KB_PUBLISH)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    deleted_chunks = delete_source(db, source_id)
    log_admin_action(
        db,
        actor_user_id=principal.id,
        action="knowledge_source_deleted",
        target_type="knowledge_source",
        target_id=source_id,
        metadata={"deleted_chunks": deleted_chunks},
    )
    db.commit()
    return {"status": "deleted", "source_id": source_id, "deleted_chunks": deleted_chunks}


@router.post("/knowledge/rebuild")
async def rebuild_knowledge(
    _: CurrentPrincipal = Depends(require_any_permission(Permission.DEV_CONFIG_EDIT, Permission.PRODUCTION_KB_PUBLISH)),
    db: Session = Depends(get_db),
) -> dict:
    return await build_knowledge_base(db, rebuild=True)


@router.get("/evaluation/registry")
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


@router.post("/evaluation/run")
def run_evaluation(
    payload: dict[str, object] = Body(default_factory=dict),
    _: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_RUN_CREATE)),
) -> dict[str, object]:
    from backend.evaluation.runner import config_from_payload, run_evaluation_sync

    return run_evaluation_sync(config_from_payload(payload))


@router.get("/evaluation/runs")
def list_evaluation_runs(
    _: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_VIEW)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from backend.evaluation.runner import list_saved_runs
    from database.models import EvaluationRun

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


@router.get("/evaluation/runs/{run_id}")
def get_evaluation_run(
    run_id: str,
    _: CurrentPrincipal = Depends(require_permission(Permission.EVALUATION_VIEW)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    from backend.evaluation.runner import RESULTS_DIR
    from database.models import EvaluationRun

    row = db.get(EvaluationRun, run_id)
    output_dir = RESULTS_DIR / run_id
    if output_dir.exists():
        summary_path = output_dir / "summary.json"
        config_path = output_dir / "config.json"
        case_scores_path = output_dir / "case_scores.jsonl"
        return {
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
    if not row:
        raise AppError("evaluation_run_not_found", "评测记录不存在。", "admin_evaluation", status_code=404)
    return {
        "run_id": row.run_id,
        "status": row.status,
        "config": json.loads(row.config_json or "{}"),
        "summary": json.loads(row.summary_json or "{}"),
        "output_dir": row.output_dir,
        "created_at": row.created_at.isoformat(),
    }


@router.post("/evaluation/compare")
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
            "admin_evaluation",
            status_code=400,
        )
    return compare_runs(baseline_run_id, candidate_run_id)

from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, require_any_permission, require_permission
from auth.permissions import Permission
from auth.service import log_admin_action, log_knowledge_review_action
from database.db import get_db
from schemas.errors import AppError


router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_RAG_DIR = PROJECT_ROOT / "scripts" / "rag"
if str(SCRIPTS_RAG_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_RAG_DIR))
if str(PROJECT_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from build_production_indexes import build_production_indexes, rollback_bm25_production  # noqa: E402
from kb_v11_utils import (  # noqa: E402
    all_chunks,
    counters_for,
    load_chunks_by_status,
    load_registry,
    normalize_review_status,
    read_jsonl,
    split_chunks_by_status,
    utc_now_iso,
    write_chunks_by_status,
    write_jsonl_atomic,
)


class ReviewDecisionRequest(BaseModel):
    comment: str = Field(default="", max_length=1000)
    reason: str = Field(default="", max_length=1000)


class ProductionPublishRequest(BaseModel):
    dry_run: bool = True
    batch_size: int | None = None
    allow_empty: bool = False


class ProductionRollbackRequest(BaseModel):
    dry_run: bool = True
    backup_dir: str | None = None


def _source_reviews_path(registry: Any) -> Path:
    return registry.paths["reports"] / "source_reviews.jsonl"


def _read_source_reviews(registry: Any) -> list[dict[str, Any]]:
    return read_jsonl(_source_reviews_path(registry))


def _write_source_reviews(registry: Any, rows: list[dict[str, Any]]) -> None:
    write_jsonl_atomic(_source_reviews_path(registry), rows)


def _latest_source_reviews(registry: Any) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _read_source_reviews(registry):
        latest[str(row.get("source_id") or "")] = row
    return latest


def _source_map(registry: Any) -> dict[str, Any]:
    return {source.id: source for source in registry.sources}


def _chunks_for_source(chunks: list[dict[str, Any]], source_id: str) -> list[dict[str, Any]]:
    return [chunk for chunk in chunks if str(chunk.get("source_id") or "") == source_id]


def _chunk_preview(chunk: dict[str, Any], *, include_content: bool = False) -> dict[str, Any]:
    content = str(chunk.get("content") or "")
    row = {
        "chunk_id": chunk.get("chunk_id", ""),
        "source_id": chunk.get("source_id", ""),
        "title": chunk.get("title", ""),
        "section": chunk.get("section", ""),
        "topic": chunk.get("topic", ""),
        "topics": chunk.get("topics", []),
        "target_collection": chunk.get("target_collection", ""),
        "use_mode": chunk.get("use_mode", ""),
        "risk_scope": chunk.get("risk_scope", ""),
        "review_priority": chunk.get("review_priority", ""),
        "review_status": normalize_review_status(chunk.get("review_status")),
        "reviewed_by": chunk.get("reviewed_by", ""),
        "review_comment": chunk.get("review_comment", ""),
        "official_page_url": chunk.get("official_page_url") or chunk.get("official_url", ""),
        "downloaded_url": chunk.get("downloaded_url", ""),
        "content_preview": " ".join(content.split())[:320],
        "char_count": len(content),
    }
    if include_content:
        row["content"] = content
    return row


def _source_summary(source: Any, chunks: list[dict[str, Any]], latest_review: dict[str, Any] | None = None) -> dict[str, Any]:
    status_counts = Counter(normalize_review_status(chunk.get("review_status")) for chunk in chunks)
    return {
        "source_id": source.id,
        "title": source.title,
        "organization": source.organization,
        "target_collection": source.target_collection,
        "official_page_url": source.official_page_url,
        "enabled": source.enabled,
        "auto_download": source.auto_download,
        "review_priority": source.raw.get("review_priority", ""),
        "use_mode": source.raw.get("use_mode", ""),
        "review_status": (latest_review or {}).get("decision", "pending"),
        "latest_reviewed_by": (latest_review or {}).get("reviewed_by", ""),
        "latest_review_comment": (latest_review or {}).get("comment", ""),
        "chunk_count": len(chunks),
        "pending_chunks": int(status_counts.get("pending", 0)),
        "approved_chunks": int(status_counts.get("approved", 0)),
        "rejected_chunks": int(status_counts.get("rejected", 0)),
    }


def _is_safety_priority(chunk: dict[str, Any]) -> bool:
    fields = " ".join(
        [
            str(chunk.get("target_collection") or ""),
            str(chunk.get("use_mode") or ""),
            str(chunk.get("risk_scope") or ""),
            str(chunk.get("review_priority") or ""),
            " ".join(str(item) for item in (chunk.get("topics") or [])) if isinstance(chunk.get("topics"), list) else str(chunk.get("topics") or ""),
            str(chunk.get("topic") or ""),
        ]
    ).lower()
    return any(
        marker in fields
        for marker in [
            "safety",
            "self_harm",
            "suicide",
            "suicidal",
            "acute_crisis",
            "harm_to_others",
            "p0",
        ]
    )


def _load_all_chunks() -> tuple[Any, list[dict[str, Any]]]:
    registry = load_registry(None)
    return registry, all_chunks(load_chunks_by_status(registry))


def _find_chunk(chunks: list[dict[str, Any]], chunk_id: str) -> dict[str, Any]:
    for chunk in chunks:
        if str(chunk.get("chunk_id") or "") == chunk_id:
            return chunk
    raise AppError("knowledge_chunk_not_found", "知识 chunk 不存在。", "knowledge_review", status_code=404)


def _record_source_decision(
    registry: Any,
    *,
    source_id: str,
    decision: str,
    reviewed_by: str,
    comment: str,
) -> dict[str, Any]:
    rows = _read_source_reviews(registry)
    row = {
        "review_id": f"SRCREV_{source_id}_{len(rows) + 1:05d}",
        "created_at": utc_now_iso(),
        "source_id": source_id,
        "decision": decision,
        "reviewed_by": reviewed_by,
        "comment": comment,
        "propagated_chunks": 0,
        "held_for_chunk_review": 0,
    }
    rows.append(row)
    _write_source_reviews(registry, rows)
    return row


@router.get("/status")
def knowledge_status(
    _: CurrentPrincipal = Depends(require_any_permission(Permission.KNOWLEDGE_VIEW, Permission.RAG_DEBUG_VIEW)),
) -> dict[str, Any]:
    registry, chunks = _load_all_chunks()
    manifest_path = registry.paths["reports"] / "production_index_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    return {
        "registry_name": registry.registry_name,
        "version": registry.version,
        "collections": sorted(registry.collections),
        "source_count": len(registry.sources),
        "chunk_count": len(chunks),
        "counters": counters_for(chunks),
        "production_manifest": manifest,
    }


@router.get("/sources")
def list_sources(
    collection: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_VIEW)),
) -> dict[str, Any]:
    registry, chunks = _load_all_chunks()
    latest = _latest_source_reviews(registry)
    rows = []
    for source in registry.sources:
        if collection and source.target_collection != collection:
            continue
        summary = _source_summary(source, _chunks_for_source(chunks, source.id), latest.get(source.id))
        if status and str(summary.get("review_status")) != status:
            continue
        rows.append(summary)
    return {"items": rows[:limit], "total": len(rows)}


@router.get("/sources/{source_id}")
def get_source(
    source_id: str,
    _: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_VIEW)),
) -> dict[str, Any]:
    registry, chunks = _load_all_chunks()
    source = _source_map(registry).get(source_id)
    if not source:
        raise AppError("knowledge_source_not_found", "知识来源不存在。", "knowledge_review", status_code=404)
    source_chunks = _chunks_for_source(chunks, source_id)
    latest_review = _latest_source_reviews(registry).get(source_id)
    return {
        **_source_summary(source, source_chunks, latest_review),
        "raw": source.raw,
        "sample_chunks": [_chunk_preview(chunk) for chunk in source_chunks[:10]],
    }


@router.post("/sources/{source_id}/{decision}")
def decide_source(
    source_id: str,
    decision: Literal["approve", "reject", "flag"],
    payload: ReviewDecisionRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_SOURCE_APPROVE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    registry = load_registry(None)
    source = _source_map(registry).get(source_id)
    if not source:
        raise AppError("knowledge_source_not_found", "知识来源不存在。", "knowledge_review", status_code=404)
    latest = _latest_source_reviews(registry).get(source_id, {})
    previous_status = str(latest.get("decision") or "pending")
    new_status = {
        "approve": "approved",
        "reject": "rejected",
        "flag": "flagged",
    }[decision]
    comment = payload.comment or payload.reason
    row = _record_source_decision(
        registry,
        source_id=source_id,
        decision=new_status,
        reviewed_by=principal.id,
        comment=comment,
    )
    log_knowledge_review_action(
        db,
        reviewer_user_id=principal.id,
        action=f"source_{new_status}",
        source_id=source_id,
        previous_status=previous_status,
        new_status=new_status,
        comment=comment,
    )
    db.commit()
    return row


@router.get("/chunks")
def list_chunks(
    status: str = Query(default="pending"),
    source_id: str | None = None,
    priority: str | None = None,
    queue: Literal["all", "safety", "intervention"] = "all",
    limit: int = Query(default=50, ge=1, le=500),
    _: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_REVIEW)),
) -> dict[str, Any]:
    _, chunks = _load_all_chunks()
    wanted_status = normalize_review_status(status)
    rows = []
    for chunk in chunks:
        if normalize_review_status(chunk.get("review_status")) != wanted_status:
            continue
        if source_id and str(chunk.get("source_id") or "") != source_id:
            continue
        if priority and str(chunk.get("review_priority") or "").upper() != priority.upper():
            continue
        if queue == "safety" and not _is_safety_priority(chunk):
            continue
        if queue == "intervention" and str(chunk.get("target_collection") or "") != "interventions":
            continue
        rows.append(_chunk_preview(chunk))
    return {"items": rows[:limit], "total": len(rows)}


@router.get("/chunks/{chunk_id}")
def get_chunk(
    chunk_id: str,
    _: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_REVIEW)),
) -> dict[str, Any]:
    _, chunks = _load_all_chunks()
    return _chunk_preview(_find_chunk(chunks, chunk_id), include_content=True)


@router.post("/chunks/{chunk_id}/{decision}")
def decide_chunk(
    chunk_id: str,
    decision: Literal["approve", "reject"],
    payload: ReviewDecisionRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_CHUNK_APPROVE)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    registry, chunks = _load_all_chunks()
    target = _find_chunk(chunks, chunk_id)
    previous_status = normalize_review_status(target.get("review_status"))
    new_status = "approved" if decision == "approve" else "rejected"
    comment = payload.comment or payload.reason
    updated = []
    for chunk in chunks:
        if str(chunk.get("chunk_id") or "") == chunk_id:
            next_chunk = {
                **chunk,
                "review_status": new_status,
                "reviewed_at": utc_now_iso(),
                "reviewed_by": principal.id,
                "review_comment": comment,
            }
            if payload.reason:
                next_chunk["rejection_reason"] = payload.reason
            updated.append(next_chunk)
        else:
            updated.append(chunk)
    write_chunks_by_status(registry, split_chunks_by_status(updated))
    log_knowledge_review_action(
        db,
        reviewer_user_id=principal.id,
        action=f"chunk_{new_status}",
        source_id=str(target.get("source_id") or ""),
        chunk_id=chunk_id,
        previous_status=previous_status,
        new_status=new_status,
        comment=comment,
    )
    db.commit()
    return {
        "chunk_id": chunk_id,
        "previous_status": previous_status,
        "new_status": new_status,
        "reviewed_by": principal.id,
    }


@router.post("/staging/rebuild")
async def rebuild_staging(
    _: CurrentPrincipal = Depends(require_any_permission(Permission.DEV_CONFIG_EDIT, Permission.PRODUCTION_KB_PUBLISH)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from services.knowledge_ingestion_service import build_knowledge_base

    return await build_knowledge_base(db, rebuild=True)


@router.get("/production/status")
def production_status(
    _: CurrentPrincipal = Depends(require_permission(Permission.KNOWLEDGE_VIEW)),
) -> dict[str, Any]:
    registry = load_registry(None)
    manifest_path = registry.paths["reports"] / "production_index_manifest.json"
    rollback_path = registry.paths["reports"] / "production_bm25_rollback_manifest.json"
    return {
        "manifest": json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {},
        "rollback_manifest": json.loads(rollback_path.read_text(encoding="utf-8")) if rollback_path.exists() else {},
    }


@router.post("/production/publish")
async def publish_production(
    payload: ProductionPublishRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.PRODUCTION_KB_PUBLISH)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    report = await build_production_indexes(
        registry_path=None,
        batch_size=payload.batch_size,
        allow_empty=payload.allow_empty,
        dry_run=payload.dry_run,
    )
    log_admin_action(
        db,
        actor_user_id=principal.id,
        action="production_kb_publish_dry_run" if payload.dry_run else "production_kb_published",
        target_type="knowledge_base",
        target_id="production",
        metadata={
            "dry_run": payload.dry_run,
            "production_ready": bool(report.get("production_ready")),
            "eligible_chunks": report.get("eligible_chunks", 0),
        },
    )
    db.commit()
    return report


@router.post("/production/rollback")
def rollback_production(
    payload: ProductionRollbackRequest,
    principal: CurrentPrincipal = Depends(require_permission(Permission.PRODUCTION_KB_ROLLBACK)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if payload.dry_run:
        registry = load_registry(None)
        backup_root = registry.paths["indexes_bm25"] / "backups"
        backups = sorted(path.as_posix() for path in backup_root.glob("production_*") if path.is_dir()) if backup_root.exists() else []
        report = {"dry_run": True, "available_backups": backups[-5:]}
    else:
        report = rollback_bm25_production(registry_path=None, backup_dir=payload.backup_dir)
    log_admin_action(
        db,
        actor_user_id=principal.id,
        action="production_kb_rollback_dry_run" if payload.dry_run else "production_kb_rolled_back",
        target_type="knowledge_base",
        target_id="production",
        metadata={"dry_run": payload.dry_run, "backup_dir": payload.backup_dir or ""},
    )
    db.commit()
    return report

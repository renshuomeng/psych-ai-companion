import json
import math
import re
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from config import get_settings
from database.models import KnowledgeChunk, KnowledgeSource, utcnow
from services.embedding_service import cosine_similarity


def ensure_knowledge_dirs() -> dict[str, Path]:
    settings = get_settings()
    root = settings.resolved_knowledge_base_dir
    dirs = {
        "root": root,
        "manifests": root / "manifests",
        "raw": root / "raw",
        "processed": root / "processed",
        "indexes": root / "indexes",
        "chroma": settings.resolved_chroma_persist_dir,
    }
    taxonomy_dirs = [
        root / "knowledge" / "stress",
        root / "knowledge" / "anxiety",
        root / "knowledge" / "sleep",
        root / "knowledge" / "loneliness",
        root / "knowledge" / "emotion_regulation",
        root / "knowledge" / "interpersonal",
        root / "interventions" / "breathing",
        root / "interventions" / "grounding",
        root / "interventions" / "cognitive_reappraisal",
        root / "interventions" / "journaling",
        root / "interventions" / "behavioral_activation",
        root / "interventions" / "problem_solving",
        root / "interventions" / "mindfulness",
        root / "campus" / "academic",
        root / "campus" / "thesis",
        root / "campus" / "exam",
        root / "campus" / "employment",
        root / "campus" / "interpersonal",
        root / "safety" / "crisis_signals",
        root / "safety" / "self_harm",
        root / "safety" / "referral",
        root / "cases",
    ]
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    for path in taxonomy_dirs:
        path.mkdir(parents=True, exist_ok=True)
    return dirs


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _safe_load_vector(value: str) -> list[float]:
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    return [float(item) for item in data] if isinstance(data, list) else []


def _keyword_terms(query: str) -> list[str]:
    terms = re.findall(r"[a-zA-Z0-9_]+", query.lower())
    terms.extend(ch for ch in query if "\u4e00" <= ch <= "\u9fff")
    seen: set[str] = set()
    return [term for term in terms if term and not (term in seen or seen.add(term))]


def replace_source(db: Session, source: dict[str, Any], chunks: list[dict[str, Any]]) -> None:
    source_id = source["source_id"]
    db.query(KnowledgeChunk).filter(KnowledgeChunk.source_id == source_id).delete(
        synchronize_session=False
    )
    db.query(KnowledgeSource).filter(KnowledgeSource.source_id == source_id).delete(
        synchronize_session=False
    )
    try:
        db.execute(
            text("DELETE FROM knowledge_chunks_fts WHERE source_id = :source_id"),
            {"source_id": source_id},
        )
    except Exception:
        pass

    db.add(
        KnowledgeSource(
            source_id=source_id,
            title=source.get("title", source_id),
            organization=source.get("organization", ""),
            topic=source.get("topic", ""),
            audience=source.get("audience", "university_students"),
            evidence_level=source.get("evidence_level", "source_unverified"),
            language=source.get("language", "zh-CN"),
            updated_at=source.get("updated_at", ""),
            license_or_usage_note=source.get("license_or_usage_note", ""),
            file_path=source.get("file_path", ""),
            content_hash=source.get("content_hash", ""),
            is_verified=source.get("evidence_level") != "source_unverified"
            and bool(source.get("organization")),
            metadata_json=_json(source),
            imported_at=utcnow(),
        )
    )
    for chunk in chunks:
        db.add(
            KnowledgeChunk(
                chunk_id=chunk["chunk_id"],
                source_id=chunk["source_id"],
                title=chunk["title"],
                section=chunk["section"],
                topic=chunk.get("topic", ""),
                content=chunk["content"],
                chunk_index=int(chunk["chunk_index"]),
                embedding_json=_json(chunk.get("embedding", [])),
                content_hash=chunk.get("content_hash", ""),
                metadata_json=_json(chunk.get("metadata", {})),
                imported_at=utcnow(),
            )
        )
        try:
            db.execute(
                text(
                    "INSERT INTO knowledge_chunks_fts(chunk_id, source_id, title, section, topic, content) "
                    "VALUES (:chunk_id, :source_id, :title, :section, :topic, :content)"
                ),
                {
                    "chunk_id": chunk["chunk_id"],
                    "source_id": chunk["source_id"],
                    "title": chunk["title"],
                    "section": chunk["section"],
                    "topic": chunk.get("topic", ""),
                    "content": chunk["content"],
                },
            )
        except Exception:
            pass
    db.commit()


def delete_source(db: Session, source_id: str) -> int:
    chunk_count = db.query(KnowledgeChunk).filter(KnowledgeChunk.source_id == source_id).delete(
        synchronize_session=False
    )
    db.query(KnowledgeSource).filter(KnowledgeSource.source_id == source_id).delete(
        synchronize_session=False
    )
    try:
        db.execute(
            text("DELETE FROM knowledge_chunks_fts WHERE source_id = :source_id"),
            {"source_id": source_id},
        )
    except Exception:
        pass
    db.commit()
    return int(chunk_count)


def list_sources(db: Session) -> list[dict[str, Any]]:
    rows = db.query(KnowledgeSource).order_by(KnowledgeSource.imported_at.desc()).all()
    return [
        {
            "source_id": row.source_id,
            "title": row.title,
            "organization": row.organization,
            "topic": row.topic,
            "audience": row.audience,
            "evidence_level": row.evidence_level,
            "language": row.language,
            "updated_at": row.updated_at,
            "license_or_usage_note": row.license_or_usage_note,
            "file_path": row.file_path,
            "is_verified": row.is_verified,
            "imported_at": row.imported_at.isoformat(),
            "chunk_count": db.query(KnowledgeChunk)
            .filter(KnowledgeChunk.source_id == row.source_id)
            .count(),
        }
        for row in rows
    ]


def get_source(db: Session, source_id: str) -> dict[str, Any] | None:
    row = db.get(KnowledgeSource, source_id)
    if not row:
        return None
    chunks = (
        db.query(KnowledgeChunk)
        .filter(KnowledgeChunk.source_id == source_id)
        .order_by(KnowledgeChunk.chunk_index)
        .all()
    )
    data = list_sources(db)
    source_data = next((item for item in data if item["source_id"] == source_id), None)
    if source_data:
        source_data["chunks"] = [
            {
                "chunk_id": chunk.chunk_id,
                "section": chunk.section,
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
            }
            for chunk in chunks
        ]
    return source_data


def vector_search(
    db: Session,
    query_embedding: list[float],
    top_k: int,
    metadata_filter: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    query = db.query(KnowledgeChunk)
    if metadata_filter and metadata_filter.get("topic"):
        query = query.filter(KnowledgeChunk.topic == metadata_filter["topic"])
    rows = query.all()
    results: list[dict[str, Any]] = []
    for row in rows:
        score = cosine_similarity(query_embedding, _safe_load_vector(row.embedding_json))
        if score <= 0:
            continue
        results.append(_chunk_to_result(row, vector_score=round(score, 4), keyword_score=0.0))
    return sorted(results, key=lambda item: item["vector_score"], reverse=True)[:top_k]


def keyword_search(
    db: Session,
    query: str,
    top_k: int,
    metadata_filter: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    topic_filter = metadata_filter.get("topic") if metadata_filter else None
    try:
        fts_query = " OR ".join(_keyword_terms(query)[:12])
        if fts_query:
            sql = (
                "SELECT chunk_id, bm25(knowledge_chunks_fts) AS rank "
                "FROM knowledge_chunks_fts WHERE knowledge_chunks_fts MATCH :query "
                + ("AND topic = :topic " if topic_filter else "")
                + "ORDER BY rank LIMIT :limit"
            )
            rows = db.execute(
                text(sql),
                {"query": fts_query, "topic": topic_filter, "limit": top_k},
            ).mappings()
            chunk_ids = [(row["chunk_id"], float(row["rank"])) for row in rows]
            if chunk_ids:
                min_rank = min(rank for _, rank in chunk_ids)
                max_rank = max(rank for _, rank in chunk_ids)
                span = max(max_rank - min_rank, 1e-6)
                results = []
                for chunk_id, rank in chunk_ids:
                    chunk = db.get(KnowledgeChunk, chunk_id)
                    if chunk:
                        score = 1.0 - ((rank - min_rank) / span) if len(chunk_ids) > 1 else 1.0
                        results.append(_chunk_to_result(chunk, vector_score=0.0, keyword_score=round(score, 4)))
                return results
    except Exception:
        pass

    terms = _keyword_terms(query)
    candidates: list[dict[str, Any]] = []
    rows = db.query(KnowledgeChunk).all()
    for row in rows:
        if topic_filter and row.topic != topic_filter:
            continue
        haystack = f"{row.title} {row.section} {row.content}".lower()
        hits = sum(1 for term in terms if term in haystack)
        if hits:
            score = 1 - math.exp(-hits / 4)
            candidates.append(_chunk_to_result(row, vector_score=0.0, keyword_score=round(score, 4)))
    return sorted(candidates, key=lambda item: item["keyword_score"], reverse=True)[:top_k]


def _chunk_to_result(
    row: KnowledgeChunk,
    vector_score: float,
    keyword_score: float,
) -> dict[str, Any]:
    metadata = json.loads(row.metadata_json or "{}")
    return {
        "chunk_id": row.chunk_id,
        "source_id": row.source_id,
        "title": row.title,
        "section": row.section,
        "topic": row.topic,
        "content": row.content,
        "chunk_index": row.chunk_index,
        "vector_score": vector_score,
        "keyword_score": keyword_score,
        "metadata": metadata,
        "evidence_level": metadata.get("evidence_level", "source_unverified"),
        "is_verified": metadata.get("evidence_level") != "source_unverified"
        and bool(metadata.get("organization")),
        "emotion": metadata.get("emotion", []),
        "cause": metadata.get("cause", ""),
        "strategy": metadata.get("strategy", []),
        "risk_level": metadata.get("risk_level", "low"),
        "intervention": metadata.get("intervention", []),
        "reviewed": bool(metadata.get("reviewed", False)),
        "usage_note": metadata.get("usage_note") or metadata.get("license_or_usage_note", ""),
    }


def log_retrieval(
    db: Session,
    session_id: str,
    query: str,
    status: str,
    result: dict[str, Any],
    duration_ms: int,
) -> None:
    from database.models import RetrievalLog

    db.add(
        RetrievalLog(
            log_id=uuid.uuid4().hex,
            session_id=session_id,
            query=query,
            status=status,
            top_k=len(result.get("retrieved_chunks", [])),
            duration_ms=duration_ms,
            result_json=_json(
                {
                    "retrieval_status": status,
                    "chunk_ids": [item["chunk_id"] for item in result.get("retrieved_chunks", [])],
                }
            ),
        )
    )
    db.commit()

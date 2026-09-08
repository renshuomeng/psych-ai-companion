import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from config import get_settings
from database.models import KnowledgeChunk, KnowledgeSource
from schemas.errors import AppError
from services.chunking_service import chunk_document, content_hash
from services.document_parser_service import SUPPORTED_KNOWLEDGE_EXTENSIONS, parse_document
from services.embedding_service import get_embedding_provider
from services.vector_store_service import ensure_knowledge_dirs, replace_source


def _load_manifest_records(manifest_dir: Path) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(manifest_dir.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if item.get("file_path"):
                records[str(item["file_path"]).replace("\\", "/")] = item
            if item.get("source_id"):
                records[str(item["source_id"])] = item
    for path in sorted(manifest_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data if isinstance(data, list) else data.get("sources", [])
        for item in items:
            if item.get("file_path"):
                records[str(item["file_path"]).replace("\\", "/")] = item
            if item.get("source_id"):
                records[str(item["source_id"])] = item
    return records


def _metadata_for(
    path: Path,
    root_dir: Path,
    raw_dir: Path,
    manifests: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    root_relative = path.relative_to(root_dir).as_posix()
    try:
        raw_relative = path.relative_to(raw_dir).as_posix()
    except ValueError:
        raw_relative = root_relative
    source_id = path.stem
    metadata = dict(
        manifests.get(root_relative)
        or manifests.get(raw_relative)
        or manifests.get(source_id)
        or {}
    )
    metadata.setdefault("source_id", source_id)
    metadata.setdefault("title", path.stem.replace("_", " "))
    metadata.setdefault("organization", "")
    metadata.setdefault("topic", "general")
    metadata.setdefault("audience", "university_students")
    metadata.setdefault("evidence_level", "source_unverified")
    metadata.setdefault("language", "zh-CN")
    metadata.setdefault("updated_at", "")
    metadata.setdefault("license_or_usage_note", "未提供使用说明；请在竞赛展示前人工审核来源。")
    metadata.setdefault("reviewed", False)
    metadata.setdefault("usage_note", metadata.get("license_or_usage_note", ""))
    metadata.setdefault("emotion", [])
    metadata.setdefault("cause", "")
    metadata.setdefault("strategy", [])
    metadata.setdefault("risk_level", "low")
    metadata.setdefault("intervention", metadata.get("strategy", []))
    metadata["file_path"] = raw_relative if root_relative.startswith("raw/") else root_relative
    return metadata


def _knowledge_documents(root: Path) -> list[Path]:
    ignored_parts = {
        "manifests",
        "processed",
        "indexes",
        "chroma_db",
        "__pycache__",
        "sources",
        "parsed",
        "cleaned",
        "chunks",
        "reports",
        "models",
        "auto",
        "manual",
    }
    documents: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_KNOWLEDGE_EXTENSIONS:
            continue
        relative_parts = set(path.relative_to(root).parts)
        if relative_parts & ignored_parts:
            continue
        documents.append(path)
    return documents


async def build_knowledge_base(db: Session, rebuild: bool = True) -> dict[str, Any]:
    dirs = ensure_knowledge_dirs()
    settings = get_settings()
    manifest_records = _load_manifest_records(dirs["manifests"])
    provider = get_embedding_provider()

    if rebuild:
        db.query(KnowledgeChunk).delete(synchronize_session=False)
        db.query(KnowledgeSource).delete(synchronize_session=False)
        try:
            from sqlalchemy import text

            db.execute(text("DELETE FROM knowledge_chunks_fts"))
        except Exception:
            pass
        db.commit()

    imported: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    documents = _knowledge_documents(dirs["root"])

    for path in documents:
        try:
            metadata = _metadata_for(path, dirs["root"], dirs["raw"], manifest_records)
            parsed = parse_document(path, metadata)
            if not parsed.raw_text:
                skipped.append({"file": path.name, "reason": "empty_document"})
                continue
            metadata["content_hash"] = content_hash(parsed.raw_text)
            chunks = chunk_document(
                source_id=metadata["source_id"],
                title=metadata["title"],
                topic=metadata["topic"],
                sections=parsed.sections,
                metadata=metadata,
            )
            embeddings = await provider.embed_documents([chunk["content"] for chunk in chunks])
            for chunk, embedding in zip(chunks, embeddings):
                chunk["embedding"] = embedding
            replace_source(db, metadata, chunks)
            imported.append(
                {
                    "source_id": metadata["source_id"],
                    "title": metadata["title"],
                    "topic": metadata["topic"],
                    "chunk_count": len(chunks),
                    "embedding_provider": settings.embedding_provider,
                    "embedding_model": settings.embedding_model,
                }
            )
        except AppError as exc:
            errors.append({"file": str(path), "code": exc.detail.code, "message": exc.detail.message})
        except Exception as exc:
            errors.append({"file": str(path), "code": "import_failed", "message": str(exc)})

    report = {
        "status": "completed" if not errors else "completed_with_errors",
        "raw_dir": str(dirs["raw"]),
        "manifest_dir": str(dirs["manifests"]),
        "processed_dir": str(dirs["processed"]),
        "index_dir": str(dirs["indexes"]),
        "chroma_persist_dir": str(settings.resolved_chroma_persist_dir),
        "vector_backend": "sqlite_local_vector",
        "chunk_unit": "中文字符数近似；优先按标题/段落/句子边界切片",
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
    }
    dirs["processed"].mkdir(parents=True, exist_ok=True)
    (dirs["processed"] / "last_import_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import random
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from config import get_settings
from schemas.errors import AppError
from services.document_parser_service import SUPPORTED_KNOWLEDGE_EXTENSIONS, parse_document
from services.embedding_service import get_rag_v1_embedding_provider
from services.knowledge_cleaning_service import clean_knowledge_text
from services.knowledge_download_service import sha256_file, utc_now_iso
from services.knowledge_source_registry import (
    KnowledgeSourceEntry,
    KnowledgeSourceRegistry,
    ensure_registry_directories,
)
from services.rag_v1_index_service import (
    bm25_dir_for,
    build_bm25_index,
    build_chroma_indexes,
    normalize_index_mode,
    query_bm25,
    query_chroma,
)


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _infer_chunk_type(metadata: dict[str, Any], section_title: str, content: str) -> str:
    source_type = str(metadata.get("source_type") or "").lower()
    section = section_title.lower()
    text = content[:400].lower()
    use_mode = str(metadata.get("use_mode") or "").lower()
    collection = str(metadata.get("target_collection") or metadata.get("collection") or "").lower()
    if use_mode == "safety_only" or collection == "safety":
        return "safety_guidance"
    if use_mode == "clinical_reference_only":
        return "clinical_reference"
    if use_mode == "evidence_only" or collection == "evidence":
        return "evidence_summary"
    if use_mode == "helping_skills_only" or collection == "helping_skills":
        return "helping_skill"
    if "communication" in section or "assertiveness" in section or "listening" in text:
        return "communication_skill"
    if any(term in text for term in ["problem solving", "action plan", "small step", "计划", "步骤"]):
        return "intervention_step"
    if "worksheet" in source_type or "worksheet" in section or "worksheet" in text:
        if not metadata.get("use_mode"):
            return "worksheet"
        return "exercise"
    if any(term in text for term in ["exercise", "practice", "try this", "step 1", "步骤"]):
        return "exercise"
    if "guideline" in source_type or "recommendation" in source_type:
        return "clinical_reference" if collection == "evidence" else "psychoeducation"
    if "policy" in source_type or "implementation" in source_type:
        return "policy"
    return "psychoeducation"


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, "", []):
        return []
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
    if isinstance(value, str):
        return [item.strip() for item in value.replace("，", ",").split(",") if item.strip()]
    return [str(value)]


DERIVED_TOPIC_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("school_support", ("starting school", "school adjustment", "not want to go to school", "不想去学校", "上学适应")),
    ("student_mental_health", ("student mental health", "child's mental health", "child’s mental health", "teen mental health", "学校心理", "学生心理")),
    ("emotion_regulation", ("manage a meltdown", "express emotions", "overwhelming feelings", "difficult feelings", "情绪失控", "情绪调节")),
    ("distress_tolerance", ("manage a meltdown", "upset teens", "overwhelming feelings", "tough situations", "痛苦耐受", "稳定下来")),
    ("anger", ("anger", "angry", "manage a meltdown", "upset teens", "生气", "愤怒")),
    ("postpartum", ("postpartum", "产后")),
    ("perinatal", ("perinatal", "postpartum", "pregnancy", "孕产期", "产后", "怀孕")),
    ("pregnancy", ("pregnancy", "pregnant", "怀孕", "孕期")),
    ("loneliness", ("loneliness", "lonely", "孤独", "孤独感")),
    ("social_isolation", ("social isolation", "isolated", "not go out", "不愿意出门", "社会隔离")),
    ("grief", ("grief", "bereavement", "loss of a loved one", "丧亲", "哀伤")),
    ("bereavement", ("bereavement", "loss of a loved one", "丧亲")),
    ("loss", ("loss of a loved one", "bereavement", "亲人去世")),
]

DERIVED_POPULATION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("children", ("children", "pre-teens", "child's mental health", "child’s mental health", "starting school", "孩子", "儿童")),
    ("adolescents", ("adolescents", "teen", "teens", "teenager", "青春期", "青少年")),
    ("older_adults", ("older adults", "retirement", "retired", "老人", "老年", "退休")),
    ("pregnant_people", ("pregnancy", "pregnant", "怀孕", "孕期")),
    ("postpartum_people", ("postpartum", "产后", "new mother", "新手妈妈")),
    ("people_experiencing_grief", ("grief", "bereavement", "loss of a loved one", "丧亲", "哀伤", "亲人去世")),
]


def _extend_unique(values: list[str], additions: list[str]) -> list[str]:
    seen = {str(value).strip().lower() for value in values if str(value).strip()}
    output = [str(value) for value in values if str(value).strip()]
    for value in additions:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    return output


def _derived_tags_from_text(text: str, rules: list[tuple[str, tuple[str, ...]]]) -> list[str]:
    normalized = text.lower()
    derived: list[str] = []
    for tag, terms in rules:
        if any(term.lower() in normalized for term in terms):
            derived.append(tag)
    return derived


def _has_unsafe_operational_detail(text: str) -> bool:
    normalized = text.lower()
    dangerous_terms = [
        "lethal dose",
        "fatal dose",
        "how to hang",
        "具体剂量",
        "致死剂量",
        "自杀方法",
        "上吊方法",
        "如何自残",
        "规避救援",
        "vomiting steps",
        "laxative dose",
    ]
    return any(term in normalized for term in dangerous_terms)


def detect_language(text: str, fallback: str = "") -> str:
    if fallback:
        if fallback.lower().startswith("zh"):
            return "zh-CN"
        if fallback.lower().startswith("en"):
            return "en"
    sample = text[:2000]
    cjk = len(re.findall(r"[\u4e00-\u9fff]", sample))
    letters = len(re.findall(r"[A-Za-z]", sample))
    if cjk > max(letters * 0.25, 10):
        return "zh-CN"
    return "en"


def _sentence_split(text: str) -> list[str]:
    pieces = re.split(r"(?<=[。！？!?\.])\s+|(?<=[。！？!?])", text.strip())
    return [piece.strip() for piece in pieces if piece.strip()]


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = _sentence_split(text)
    if len(sentences) <= 1:
        chunks: list[str] = []
        start = 0
        step = max(max_chars - overlap, 1)
        while start < len(text):
            chunks.append(text[start : start + max_chars].strip())
            start += step
        return [chunk for chunk in chunks if chunk]
    output: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            output.append(current)
        current = sentence
    if current:
        output.append(current)
    return output


def chunk_sections(
    *,
    source_id: str,
    metadata: dict[str, Any],
    sections: list[dict[str, str]],
    chunking_config: dict[str, Any],
) -> list[dict[str, Any]]:
    target_chars = int(chunking_config.get("target_chars") or 500)
    overlap_chars = int(chunking_config.get("overlap_chars") or 80)
    min_chars = int(chunking_config.get("min_chars") or 120)
    max_chars = int(chunking_config.get("max_chars") or 900)
    chunks: list[dict[str, Any]] = []

    for section in sections:
        section_title = str(section.get("section") or metadata.get("title") or source_id)
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", section.get("content", "")) if part.strip()]
        buffer = ""
        for paragraph in paragraphs:
            candidate = f"{buffer}\n\n{paragraph}".strip() if buffer else paragraph
            starts_step = bool(re.match(r"^(step|步骤|第[一二三四五六七八九十\d]+步)\b", paragraph.strip(), flags=re.I))
            if len(candidate) <= target_chars or (starts_step and len(candidate) <= max_chars):
                buffer = candidate
                continue
            if buffer:
                for piece in _split_long_text(buffer, max_chars, overlap_chars):
                    if len(piece) >= min_chars or len(buffer) < min_chars:
                        chunks.append(_chunk_record(source_id, metadata, section_title, piece, len(chunks)))
            buffer = paragraph
        if buffer:
            for piece in _split_long_text(buffer, max_chars, overlap_chars):
                if len(piece) >= min_chars or len(buffer) < min_chars:
                    chunks.append(_chunk_record(source_id, metadata, section_title, piece, len(chunks)))
    return chunks


def _chunk_record(
    source_id: str,
    metadata: dict[str, Any],
    section_title: str,
    content: str,
    index: int,
) -> dict[str, Any]:
    chunk_hash = content_sha256(content)
    document_hash = str(metadata.get("sha256") or content_sha256(str(metadata.get("file_path") or source_id)))
    document_key = content_sha256(str(metadata.get("file_path") or document_hash or source_id))[:8]
    collection = str(metadata.get("target_collection") or metadata.get("expected_collection") or "professional_knowledge")
    chunk_id = f"{source_id}_{document_key}_{index:05d}_{chunk_hash[:12]}"
    language = detect_language(content, str(metadata.get("language") or ""))
    topics = _as_list(metadata.get("topic_tags") or metadata.get("topics") or metadata.get("topic"))
    chunk_search_text = f"{section_title}\n\n{content}"
    topics = _extend_unique(topics, _derived_tags_from_text(chunk_search_text, DERIVED_TOPIC_RULES))
    population_tags = _extend_unique(
        _as_list(metadata.get("population_tags")) or ["university_students", "young_adults", "adults"],
        _derived_tags_from_text(chunk_search_text, DERIVED_POPULATION_RULES),
    )
    use_mode = str(metadata.get("use_mode") or "direct_user_support")
    risk_scope = str(metadata.get("risk_scope") or ("safety_route_only" if collection == "safety" else "normal"))
    clinical_only = bool(metadata.get("clinical_only", use_mode in {"clinical_reference_only", "evidence_only"}))
    user_facing = bool(metadata.get("user_facing", use_mode == "direct_user_support"))
    if use_mode in {"safety_only", "clinical_reference_only", "evidence_only", "agent_policy_only", "helping_skills_only"}:
        user_facing = False
    exclude_from_index = _has_unsafe_operational_detail(content)
    return {
        "chunk_id": chunk_id,
        "source_id": source_id,
        "organization": metadata.get("organization", ""),
        "title": metadata.get("title", source_id),
        "version": metadata.get("version", "v2"),
        "year": metadata.get("year"),
        "source_type": metadata.get("source_type", ""),
        "target_collection": collection,
        "collection": collection,
        "expected_collection": metadata.get("expected_collection", collection),
        "topics": topics,
        "topic_tags": topics,
        "population_tags": population_tags,
        "life_stage_tags": _as_list(metadata.get("life_stage_tags")),
        "translation_group_id": metadata.get("translation_group_id", source_id),
        "use_mode": use_mode,
        "risk_scope": risk_scope,
        "clinical_only": clinical_only,
        "user_facing": user_facing,
        "topic": topics[0] if topics else "",
        "language": language,
        "section": section_title,
        "subsection": "",
        "evidence_level": metadata.get("evidence_level", ""),
        "source_authority": metadata.get("source_authority", ""),
        "review_priority": metadata.get("review_priority", metadata.get("priority", "P2")),
        "official_page_url": metadata.get("official_page_url", ""),
        "official_url": metadata.get("official_url", metadata.get("official_page_url", "")),
        "downloaded_url": metadata.get("downloaded_url", ""),
        "license": metadata.get("license") or metadata.get("license_note", ""),
        "sha256": document_hash,
        "document_sha256": document_hash,
        "document_hash": document_hash,
        "document_id": f"{source_id}_{document_key}",
        "download_status": metadata.get("download_status", "unknown"),
        "manual_fallback_allowed": bool(metadata.get("manual_fallback_allowed", True)),
        "review_status": metadata.get("review_status", "pending"),
        "quality_checked": True,
        "expert_reviewed": False,
        "eligible_for_approval": bool(metadata.get("eligible_for_approval", False)),
        "exclude_from_index": exclude_from_index,
        "content": content,
        "chunk_sha256": chunk_hash,
        "content_sha256": chunk_hash,
        "content_hash": chunk_hash,
        "char_count": len(content),
        "chunk_index": index,
        "chunk_type": _infer_chunk_type(metadata, section_title, content),
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _source_by_id(registry: KnowledgeSourceRegistry) -> dict[str, KnowledgeSourceEntry]:
    return {source.id: source for source in registry.sources}


def _manifest_by_path(registry: KnowledgeSourceRegistry) -> dict[str, dict[str, Any]]:
    records = _read_jsonl(registry.paths["reports"] / "download_manifest.jsonl")
    mapping: dict[str, dict[str, Any]] = {}
    for record in records:
        if record.get("file_path"):
            mapping[Path(str(record["file_path"])).resolve().as_posix()] = record
            mapping[Path(str(record["file_path"])).as_posix()] = record
    return mapping


def _documents_to_parse(registry: KnowledgeSourceRegistry) -> list[tuple[Path, dict[str, Any]]]:
    source_lookup = _source_by_id(registry)
    manifest = _manifest_by_path(registry)
    documents: list[tuple[Path, dict[str, Any]]] = []
    auto_root = registry.paths["raw_auto"]
    manual_root = registry.paths["raw_manual"]
    for path in sorted(auto_root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_KNOWLEDGE_EXTENSIONS:
            continue
        if path.suffix.lower() == ".zip":
            continue
        source_id = path.relative_to(auto_root).parts[0]
        source = source_lookup.get(source_id)
        if not source:
            continue
        record = manifest.get(path.resolve().as_posix()) or manifest.get(path.as_posix()) or {}
        metadata = {
            **source.raw,
            "source_id": source_id,
            "downloaded_url": record.get("downloaded_url", source.official_page_url),
            "sha256": record.get("sha256") or sha256_file(path),
            "review_status": "pending",
            "file_path": path.as_posix(),
        }
        documents.append((path, metadata))

    manual_targets = {
        "textbooks": "professional_knowledge",
        "papers": "evidence",
        "campus": "campus_support",
    }
    for subdir, collection in manual_targets.items():
        folder = manual_root / subdir
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_KNOWLEDGE_EXTENSIONS:
                continue
            if path.name.lower() == "readme.md":
                continue
            source_id = f"manual_{subdir}_{path.stem}"
            use_mode = "clinical_reference_only" if collection == "evidence" else "direct_user_support"
            documents.append(
                (
                    path,
                    {
                        "source_id": source_id,
                        "organization": "manual",
                        "title": path.stem,
                        "version": "manual_v2",
                        "year": None,
                        "source_type": "manual_file",
                        "target_collection": collection,
                        "collection": collection,
                        "topics": [subdir],
                        "topic_tags": [subdir],
                        "population_tags": ["university_students", "young_adults", "adults"],
                        "life_stage_tags": [],
                        "language": "",
                        "evidence_level": "source_unverified",
                        "use_mode": use_mode,
                        "risk_scope": "normal",
                        "clinical_only": collection == "evidence",
                        "user_facing": collection != "evidence",
                        "official_page_url": "",
                        "official_url": "",
                        "license": "manual_user_provided_review_required",
                        "downloaded_url": "",
                        "sha256": sha256_file(path),
                        "review_status": "pending",
                        "quality_checked": True,
                        "expert_reviewed": False,
                        "eligible_for_approval": False,
                        "file_path": path.as_posix(),
                    },
                )
            )
    official_root = manual_root / "official"
    if official_root.exists():
        for source_folder in sorted(path for path in official_root.iterdir() if path.is_dir()):
            source_id = source_folder.name
            source = source_lookup.get(source_id)
            if not source:
                continue
            for path in sorted(source_folder.rglob("*")):
                if not path.is_file() or path.suffix.lower() not in SUPPORTED_KNOWLEDGE_EXTENSIONS:
                    continue
                if path.name.lower() == "readme.md":
                    continue
                documents.append(
                    (
                        path,
                        {
                            **source.raw,
                            "source_id": source_id,
                            "downloaded_url": source.official_page_url,
                            "sha256": sha256_file(path),
                            "review_status": "pending",
                            "file_path": path.as_posix(),
                            "download_status": "manual",
                        },
                    )
                )
    return documents


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _write_review_csv(path: Path, chunks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "chunk_id",
        "source_id",
        "title",
        "topic",
        "use_mode",
        "risk_scope",
        "population_tags",
        "section",
        "language",
        "char_count",
        "review_status",
        "content_preview",
        "review_comment",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for chunk in chunks:
            writer.writerow(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source_id": chunk["source_id"],
                    "title": chunk["title"],
                    "topic": chunk.get("topic", ""),
                    "use_mode": chunk.get("use_mode", ""),
                    "risk_scope": chunk.get("risk_scope", ""),
                    "population_tags": json.dumps(chunk.get("population_tags") or [], ensure_ascii=False),
                    "section": chunk.get("section", ""),
                    "language": chunk.get("language", ""),
                    "char_count": chunk.get("char_count", len(chunk["content"])),
                    "review_status": chunk.get("review_status", "pending"),
                    "content_preview": chunk["content"][:220].replace("\n", " "),
                    "review_comment": "",
                }
            )


def _status_paths(registry: KnowledgeSourceRegistry) -> dict[str, Path]:
    return {
        "pending": registry.paths["chunks_pending"] / "chunks.jsonl",
        "approved": registry.paths["chunks_approved"] / "chunks.jsonl",
        "rejected": registry.paths["chunks_rejected"] / "chunks.jsonl",
    }


def _review_status_for(chunk: dict[str, Any]) -> str:
    status = str(chunk.get("review_status") or "pending").strip().lower()
    if status in {"approved", "reviewed"}:
        return "approved"
    if status in {"rejected", "blocked"}:
        return "rejected"
    return "pending"


def _load_review_decisions(registry: KnowledgeSourceRegistry) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for status, path in _status_paths(registry).items():
        for row in _read_jsonl(path):
            chunk_id = str(row.get("chunk_id") or "")
            if not chunk_id:
                continue
            decisions[chunk_id] = {
                "review_status": _review_status_for({**row, "review_status": row.get("review_status") or status}),
                "reviewed_by": row.get("reviewed_by", ""),
                "reviewed_at": row.get("reviewed_at", ""),
                "review_comment": row.get("review_comment", ""),
                "rejection_reason": row.get("rejection_reason", ""),
            }
    return decisions


def _apply_review_history(
    chunks: list[dict[str, Any]],
    decisions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    for chunk in chunks:
        decision = decisions.get(str(chunk.get("chunk_id") or ""))
        if not decision:
            continue
        chunk.update({key: value for key, value in decision.items() if value not in (None, "")})
    return chunks


def _split_by_review_status(chunks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {"pending": [], "approved": [], "rejected": []}
    for chunk in chunks:
        grouped[_review_status_for(chunk)].append(chunk)
    return grouped


def _eligible_for_index(chunk: dict[str, Any], index_mode: str) -> bool:
    if bool(chunk.get("exclude_from_index")):
        return False
    status = _review_status_for(chunk)
    if normalize_index_mode(index_mode) == "production":
        return status == "approved"
    return status != "rejected"


def _chunk_counts(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(chunks),
        "review_status": dict(Counter(_review_status_for(chunk) for chunk in chunks)),
        "collections": dict(Counter(str(chunk.get("target_collection") or "") for chunk in chunks)),
        "languages": dict(Counter(str(chunk.get("language") or "") for chunk in chunks)),
        "sources": dict(Counter(str(chunk.get("source_id") or "") for chunk in chunks)),
        "use_mode": dict(Counter(str(chunk.get("use_mode") or "") for chunk in chunks)),
        "risk_scope": dict(Counter(str(chunk.get("risk_scope") or "") for chunk in chunks)),
    }


def _dry_run_report(
    registry: KnowledgeSourceRegistry,
    *,
    docs: list[tuple[Path, dict[str, Any]]],
    index_mode: str,
    sample_mode: bool,
    sample_limit: int,
) -> dict[str, Any]:
    existing_chunks: list[dict[str, Any]] = []
    for path in _status_paths(registry).values():
        existing_chunks.extend(_read_jsonl(path))
    indexable = [chunk for chunk in existing_chunks if _eligible_for_index(chunk, index_mode)]
    dense_chunks = indexable[:sample_limit] if sample_mode and sample_limit > 0 else indexable
    return {
        "created_at": utc_now_iso(),
        "knowledge_base_version": "V2" if int(registry.version) >= 2 else "V1",
        "dry_run": True,
        "index_mode": normalize_index_mode(index_mode),
        "registry_sources": len(registry.sources),
        "auto_download_sources": len(registry.auto_download_sources),
        "documents_discovered": len(docs),
        "existing_chunks": _chunk_counts(existing_chunks),
        "indexable_chunks": _chunk_counts(indexable),
        "dense_chunks_would_index": len(dense_chunks),
        "sample_mode": sample_mode,
        "sample_limit": sample_limit,
        "writes_skipped": True,
    }


def _load_embedding_cache(path: Path) -> dict[str, list[float]]:
    cache: dict[str, list[float]] = {}
    if not path.exists():
        return cache
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("chunk_sha256") and isinstance(item.get("embedding"), list):
            cache[str(item["chunk_sha256"])] = [float(value) for value in item["embedding"]]
    return cache


def _save_embedding_cache(path: Path, cache: dict[str, list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"chunk_sha256": key, "embedding": value}
        for key, value in sorted(cache.items())
    ]
    _write_jsonl(path, rows)


async def _embed_chunks(chunks: list[dict[str, Any]], cache_path: Path) -> tuple[list[list[float]], dict[str, Any]]:
    started = time.perf_counter()
    cache = _load_embedding_cache(cache_path)
    missing = [chunk for chunk in chunks if chunk["chunk_sha256"] not in cache]
    provider_name = get_settings().rag_embedding_provider
    model_name = get_settings().rag_embedding_model
    dimension = 0
    if missing:
        provider = get_rag_v1_embedding_provider()
        for start in range(0, len(missing), get_settings().rag_embedding_batch_size):
            batch = missing[start : start + get_settings().rag_embedding_batch_size]
            vectors = await provider.embed_documents([chunk["content"] for chunk in batch])
            for chunk, vector in zip(batch, vectors):
                cache[chunk["chunk_sha256"]] = vector
                dimension = len(vector)
        _save_embedding_cache(cache_path, cache)
    embeddings = [cache[chunk["chunk_sha256"]] for chunk in chunks]
    if embeddings:
        dimension = len(embeddings[0])
    return embeddings, {
        "provider": provider_name,
        "model": model_name,
        "dimension": dimension,
        "total": len(chunks),
        "cache_hits": len(chunks) - len(missing),
        "new_embeddings": len(missing),
        "duration_ms": int((time.perf_counter() - started) * 1000),
        "status": "ready",
    }


def _sample_review(chunks: list[dict[str, Any]], sample_size: int) -> list[dict[str, Any]]:
    if len(chunks) <= sample_size:
        return chunks
    rng = random.Random(42)
    return rng.sample(chunks, sample_size)


def _quality_issues(parse_errors: list[dict[str, Any]], cleaning_issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return parse_errors + cleaning_issues


async def build_rag_v1_knowledge_base(
    registry: KnowledgeSourceRegistry,
    max_dense_chunks: int | None = None,
    index_mode: str = "staging",
    dry_run: bool = False,
    sample_mode: bool | None = None,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    ensure_registry_directories(registry)
    settings = get_settings()
    mode = normalize_index_mode(index_mode or settings.effective_rag_index_mode)
    effective_sample_mode = settings.rag_build_sample_mode if sample_mode is None else bool(sample_mode)
    effective_sample_limit = settings.rag_build_sample_limit if sample_limit is None else int(sample_limit)
    if max_dense_chunks is not None:
        effective_sample_mode = int(max_dense_chunks) > 0
        effective_sample_limit = int(max_dense_chunks)
    processing = registry.processing_policy
    chunking = dict((processing.get("chunking") or {}))
    reports_dir = registry.paths["reports"]
    parsed_dir = registry.paths["parsed"]
    cleaned_dir = registry.paths["cleaned"]
    chunks_pending_dir = registry.paths["chunks_pending"]
    sample_size = int((processing.get("review") or {}).get("sample_review_size") or 150)
    docs = _documents_to_parse(registry)
    if dry_run:
        return _dry_run_report(
            registry,
            docs=docs,
            index_mode=mode,
            sample_mode=effective_sample_mode,
            sample_limit=effective_sample_limit,
        )
    parsed_docs: list[dict[str, Any]] = []
    parse_errors: list[dict[str, Any]] = []
    cleaning_issues: list[dict[str, Any]] = []
    all_chunks: list[dict[str, Any]] = []
    seen_doc_hashes: dict[str, str] = {}
    duplicate_files: list[dict[str, Any]] = []
    ocr_required: list[dict[str, Any]] = []

    for path, metadata in docs:
        try:
            digest = sha256_file(path)
            if digest in seen_doc_hashes:
                duplicate_files.append({"file_path": path.as_posix(), "duplicate_of": seen_doc_hashes[digest], "sha256": digest})
                continue
            seen_doc_hashes[digest] = path.as_posix()
            parsed = parse_document(path, metadata)
            if path.suffix.lower() == ".pdf" and len(parsed.raw_text.strip()) < 80:
                ocr_required.append({"file_path": path.as_posix(), "source_id": metadata["source_id"], "reason": "pdf_text_too_short"})
                continue
            parsed_out = parsed_dir / f"{metadata['source_id']}_{content_sha256(path.as_posix())[:8]}.json"
            parsed_record = {
                "metadata": metadata,
                "title": parsed.title,
                "sections": parsed.sections,
                "raw_text_chars": len(parsed.raw_text),
                "file_path": path.as_posix(),
            }
            parsed_out.write_text(json.dumps(parsed_record, ensure_ascii=False, indent=2), encoding="utf-8")
            cleaned_sections: list[dict[str, str]] = []
            for section in parsed.sections:
                cleaned, issues = clean_knowledge_text(section.get("content", ""))
                if issues:
                    cleaning_issues.append({"source_id": metadata["source_id"], "file_path": path.as_posix(), "issues": issues})
                if cleaned:
                    cleaned_sections.append({"section": section.get("section", parsed.title), "content": cleaned})
            cleaned_out = cleaned_dir / f"{metadata['source_id']}_{content_sha256(path.as_posix())[:8]}.json"
            cleaned_out.write_text(
                json.dumps({"metadata": metadata, "sections": cleaned_sections, "file_path": path.as_posix()}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            chunks = chunk_sections(
                source_id=str(metadata["source_id"]),
                metadata=metadata,
                sections=cleaned_sections,
                chunking_config=chunking,
            )
            all_chunks.extend(chunks)
            parsed_docs.append(
                {
                    "source_id": metadata["source_id"],
                    "file_path": path.as_posix(),
                    "parsed_sections": len(parsed.sections),
                    "cleaned_sections": len(cleaned_sections),
                    "chunks": len(chunks),
                }
            )
        except Exception as exc:
            parse_errors.append(
                {
                    "file_path": path.as_posix(),
                    "source_id": metadata.get("source_id", path.stem),
                    "code": getattr(getattr(exc, "detail", None), "code", "parse_failed"),
                    "message": str(exc),
                }
            )

    review_decisions = _load_review_decisions(registry)
    all_chunks = _apply_review_history(all_chunks, review_decisions)
    chunks_by_status = _split_by_review_status(all_chunks)
    for status, path in _status_paths(registry).items():
        _write_jsonl(path, chunks_by_status[status])
    _write_review_csv(reports_dir / "chunk_review.csv", all_chunks)
    _write_review_csv(reports_dir / "chunk_review_sample.csv", _sample_review(all_chunks, min(sample_size, 50)))

    embedding_report: dict[str, Any] = {"status": "not_started"}
    chroma_status: dict[str, Any] = {"status": "not_started"}
    embeddings: list[list[float]] = []
    indexable_chunks = [chunk for chunk in all_chunks if _eligible_for_index(chunk, mode)]
    dense_chunks = (
        indexable_chunks[:effective_sample_limit]
        if effective_sample_mode and effective_sample_limit > 0
        else indexable_chunks
    )
    if dense_chunks:
        try:
            embeddings, embedding_report = await _embed_chunks(dense_chunks, registry.paths["indexes_chroma"] / "embedding_cache.jsonl")
            embedding_report["indexed_chunks"] = len(dense_chunks)
            embedding_report["eligible_chunks"] = len(indexable_chunks)
            embedding_report["total_chunks"] = len(all_chunks)
            embedding_report["scope"] = "all_eligible_chunks" if len(dense_chunks) == len(indexable_chunks) else "sampled_eligible_chunks"
            embedding_report["sample_mode"] = effective_sample_mode
            chroma_status = build_chroma_indexes(
                dense_chunks,
                embeddings,
                registry.paths["indexes_chroma"],
                collections=sorted(collection for collection in registry.collections if collection != "case_rag"),
                index_mode=mode,
            )
        except Exception as exc:
            embedding_report = {
                "status": "failed",
                "code": getattr(getattr(exc, "detail", None), "code", "embedding_failed"),
                "message": str(exc),
                "provider": settings.rag_embedding_provider,
                "model": settings.rag_embedding_model,
                "indexed_chunks": 0,
                "eligible_chunks": len(indexable_chunks),
                "total_chunks": len(all_chunks),
            }
            chroma_status = {"status": "skipped", "reason": embedding_report["code"]}

    bm25_status = build_bm25_index(indexable_chunks, bm25_dir_for(registry.paths["indexes_bm25"], mode))
    collection_counts = Counter(str(chunk.get("target_collection") or "") for chunk in all_chunks)
    language_counts = Counter(str(chunk.get("language") or "") for chunk in all_chunks)
    use_mode_counts = Counter(str(chunk.get("use_mode") or "") for chunk in all_chunks)
    risk_scope_counts = Counter(str(chunk.get("risk_scope") or "") for chunk in all_chunks)
    review_counts = Counter(_review_status_for(chunk) for chunk in all_chunks)
    average_chunk_size = round(sum(len(chunk["content"]) for chunk in all_chunks) / max(len(all_chunks), 1), 2)

    report = {
        "created_at": utc_now_iso(),
        "knowledge_base_version": "V2" if int(registry.version) >= 2 else "V1",
        "dry_run": False,
        "index_mode": mode,
        "sample_mode": effective_sample_mode,
        "sample_limit": effective_sample_limit,
        "registry_sources": len(registry.sources),
        "auto_download_sources": len(registry.auto_download_sources),
        "documents_discovered": len(docs),
        "parsed_documents": len(parsed_docs),
        "parse_errors": parse_errors,
        "ocr_required": ocr_required,
        "duplicate_files": duplicate_files,
        "cleaning_issues": cleaning_issues,
        "chunks": len(all_chunks),
        "review_status": dict(review_counts),
        "indexable_chunks": len(indexable_chunks),
        "average_chunk_size": average_chunk_size,
        "languages": dict(language_counts),
        "collections": dict(collection_counts),
        "use_modes": dict(use_mode_counts),
        "risk_scopes": dict(risk_scope_counts),
        "embedding": embedding_report,
        "chroma_collections": chroma_status,
        "bm25": bm25_status,
        "quality_issues": _quality_issues(parse_errors, cleaning_issues),
        "manual_cases_status": "case_rag_reserved",
        "parsed_documents_detail": parsed_docs,
        "chunk_review_csv": (reports_dir / "chunk_review.csv").as_posix(),
        "chunk_review_sample_csv": (reports_dir / "chunk_review_sample.csv").as_posix(),
        "chunks_pending_jsonl": (chunks_pending_dir / "chunks.jsonl").as_posix(),
        "chunks_approved_jsonl": (registry.paths["chunks_approved"] / "chunks.jsonl").as_posix(),
        "chunks_rejected_jsonl": (registry.paths["chunks_rejected"] / "chunks.jsonl").as_posix(),
    }
    (reports_dir / "build_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown_report(registry, report, reports_dir / "rag_v1_build_report.md")
    return report


def write_markdown_report(registry: KnowledgeSourceRegistry, report: dict[str, Any], path: Path) -> None:
    lines = [
        "# RAG Knowledge Base V1 Build Report",
        "",
        f"- Created at: {report.get('created_at')}",
        f"- Knowledge base version: {report.get('knowledge_base_version', 'V1')}",
        f"- Index mode: {report.get('index_mode', 'staging')}",
        f"- Sample mode: {report.get('sample_mode', False)}",
        f"- Registry sources: {report.get('registry_sources')}",
        f"- Parsed documents: {report.get('parsed_documents')}",
        f"- Chunks: {report.get('chunks')}",
        f"- Review status: {json.dumps(report.get('review_status', {}), ensure_ascii=False)}",
        f"- Indexable chunks: {report.get('indexable_chunks', report.get('chunks'))}",
        f"- Average chunk size: {report.get('average_chunk_size')}",
        f"- Embedding: {json.dumps(report.get('embedding'), ensure_ascii=False)}",
        f"- BM25: {json.dumps(report.get('bm25'), ensure_ascii=False)}",
        f"- Chroma: {json.dumps(report.get('chroma_collections'), ensure_ascii=False)}",
        "",
        "## Collections",
    ]
    for collection, count in sorted((report.get("collections") or {}).items()):
        lines.append(f"- {collection}: {count}")
    lines.extend(["", "## Use Modes"])
    for use_mode, count in sorted((report.get("use_modes") or {}).items()):
        lines.append(f"- {use_mode or 'unknown'}: {count}")
    lines.extend(["", "## Risk Scopes"])
    for risk_scope, count in sorted((report.get("risk_scopes") or {}).items()):
        lines.append(f"- {risk_scope or 'unknown'}: {count}")
    lines.extend(["", "## Issues"])
    for issue in report.get("quality_issues") or []:
        lines.append(f"- {issue}")
    if not report.get("quality_issues"):
        lines.append("- None recorded.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


async def run_smoke_queries(registry: KnowledgeSourceRegistry, queries_path: Path, top_k: int = 3) -> list[dict[str, Any]]:
    queries = json.loads(queries_path.read_text(encoding="utf-8"))
    provider = None
    try:
        provider = get_rag_v1_embedding_provider()
    except Exception:
        provider = None
    output: list[dict[str, Any]] = []
    for item in queries:
        query = item["query"] if isinstance(item, dict) else str(item)
        bm25 = query_bm25(registry.paths["indexes_bm25"], query, top_k=top_k)
        dense: list[dict[str, Any]] = []
        if provider is not None:
            embedding = await provider.embed_query(query)
            dense = query_chroma(registry.paths["indexes_chroma"], embedding, top_k=top_k)
        output.append({"query": query, "bm25": bm25, "dense": dense})
    return output


def build_rag_v1_knowledge_base_sync(
    registry: KnowledgeSourceRegistry,
    max_dense_chunks: int | None = None,
    index_mode: str = "staging",
    dry_run: bool = False,
    sample_mode: bool | None = None,
    sample_limit: int | None = None,
) -> dict[str, Any]:
    return asyncio.run(
        build_rag_v1_knowledge_base(
            registry,
            max_dense_chunks=max_dense_chunks,
            index_mode=index_mode,
            dry_run=dry_run,
            sample_mode=sample_mode,
            sample_limit=sample_limit,
        )
    )

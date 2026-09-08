from __future__ import annotations

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import _bootstrap  # noqa: F401,E402
from services.knowledge_source_registry import KnowledgeSourceRegistry, load_knowledge_source_registry  # noqa: E402


CHUNK_STATUSES = ("pending", "approved", "rejected")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load_registry(path: str | Path | None = None) -> KnowledgeSourceRegistry:
    return load_knowledge_source_registry(path)


def chunk_status_path(registry: KnowledgeSourceRegistry, status: str) -> Path:
    status = normalize_review_status(status)
    return registry.paths[f"chunks_{status}"] / "chunks.jsonl"


def normalize_review_status(status: Any) -> str:
    value = str(status or "pending").strip().lower()
    if value in {"approved", "reviewed"}:
        return "approved"
    if value in {"rejected", "blocked"}:
        return "rejected"
    return "pending"


def content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def infer_chunk_type(chunk: dict[str, Any]) -> str:
    source_type = str(chunk.get("source_type") or "").lower()
    section = str(chunk.get("section") or "").lower()
    text = str(chunk.get("content") or "")[:500].lower()
    use_mode = str(chunk.get("use_mode") or "").lower()
    collection = str(chunk.get("target_collection") or chunk.get("collection") or "").lower()
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


def has_unsafe_operational_detail(text: str) -> bool:
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


def enrich_chunk_v11(chunk: dict[str, Any], registry: KnowledgeSourceRegistry | None = None) -> dict[str, Any]:
    output = dict(chunk)
    text = str(output.get("content") or "")
    chunk_hash = str(output.get("content_sha256") or output.get("chunk_sha256") or content_hash(text))
    source_id = str(output.get("source_id") or "unknown_source")
    doc_sha = str(output.get("document_sha256") or output.get("sha256") or "")
    document_key = doc_sha[:8] if doc_sha else content_hash(str(output.get("downloaded_url") or output.get("title") or source_id))[:8]
    source = None
    if registry is not None:
        source = next((item for item in registry.sources if item.id == source_id), None)
    raw = source.raw if source else {}
    collection = str(output.get("target_collection") or raw.get("expected_collection") or raw.get("target_collection") or "professional_knowledge")
    topics = _as_list(output.get("topic_tags") or output.get("topics") or raw.get("topic_tags") or raw.get("topics"))
    use_mode = str(output.get("use_mode") or raw.get("use_mode") or "direct_user_support")
    risk_scope = str(output.get("risk_scope") or raw.get("risk_scope") or ("safety_route_only" if collection == "safety" else "normal"))
    clinical_only = bool(output.get("clinical_only", raw.get("clinical_only", use_mode in {"clinical_reference_only", "evidence_only"})))
    user_facing = bool(output.get("user_facing", raw.get("user_facing", use_mode == "direct_user_support")))
    if use_mode in {"safety_only", "clinical_reference_only", "evidence_only", "agent_policy_only", "helping_skills_only"}:
        user_facing = False
    output.setdefault("target_collection", collection)
    output.setdefault("collection", collection)
    output.setdefault("expected_collection", raw.get("expected_collection", collection))
    output.setdefault("content_sha256", chunk_hash)
    output.setdefault("chunk_sha256", chunk_hash)
    output.setdefault("document_sha256", doc_sha)
    output.setdefault("document_id", f"{source_id}_{document_key}")
    output["use_mode"] = use_mode
    output["risk_scope"] = risk_scope
    output["clinical_only"] = clinical_only
    output["user_facing"] = user_facing
    output["topics"] = topics
    output["topic_tags"] = topics
    output.setdefault("population_tags", _as_list(raw.get("population_tags")) or ["university_students", "young_adults", "adults"])
    output.setdefault("life_stage_tags", _as_list(raw.get("life_stage_tags")))
    output.setdefault("chunk_type", infer_chunk_type(output))
    output.setdefault("source_authority", raw.get("source_authority", "source_unverified"))
    output.setdefault("version", raw.get("version", "v2"))
    output.setdefault("translation_group_id", raw.get("translation_group_id", source_id))
    output.setdefault("official_url", raw.get("official_url") or raw.get("official_page_url", ""))
    output.setdefault("license", raw.get("license") or raw.get("license_note", ""))
    output.setdefault("document_hash", doc_sha)
    output.setdefault("content_hash", chunk_hash)
    output.setdefault("quality_checked", True)
    output.setdefault("expert_reviewed", False)
    output.setdefault("eligible_for_approval", bool(raw.get("eligible_for_approval", False)))
    output["exclude_from_index"] = bool(output.get("exclude_from_index", False) or has_unsafe_operational_detail(text))
    output.setdefault("review_priority", raw.get("review_priority", raw.get("priority", "P2")))
    output.setdefault("download_status", raw.get("download_status", "unknown"))
    output.setdefault("manual_fallback_allowed", bool(raw.get("manual_fallback_allowed", True)))
    output["review_status"] = normalize_review_status(output.get("review_status"))
    output["char_count"] = int(output.get("char_count") or len(text))
    return output


def load_chunks_by_status(registry: KnowledgeSourceRegistry, *, enrich: bool = True) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for status in CHUNK_STATUSES:
        rows = read_jsonl(chunk_status_path(registry, status))
        if enrich:
            rows = [enrich_chunk_v11({**row, "review_status": row.get("review_status") or status}, registry) for row in rows]
        grouped[status] = rows
    return grouped


def all_chunks(grouped: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for status in CHUNK_STATUSES:
        rows.extend(grouped.get(status, []))
    return rows


def split_chunks_by_status(chunks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {status: [] for status in CHUNK_STATUSES}
    for chunk in chunks:
        grouped[normalize_review_status(chunk.get("review_status"))].append(chunk)
    return grouped


def write_chunks_by_status(registry: KnowledgeSourceRegistry, grouped: dict[str, list[dict[str, Any]]]) -> None:
    for status in CHUNK_STATUSES:
        write_jsonl_atomic(chunk_status_path(registry, status), grouped.get(status, []))


def counters_for(chunks: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    return {
        "review_status": dict(Counter(normalize_review_status(chunk.get("review_status")) for chunk in chunks)),
        "collection": dict(Counter(str(chunk.get("target_collection") or "") for chunk in chunks)),
        "language": dict(Counter(str(chunk.get("language") or "") for chunk in chunks)),
        "source": dict(Counter(str(chunk.get("source_id") or "") for chunk in chunks)),
        "chunk_type": dict(Counter(str(chunk.get("chunk_type") or "") for chunk in chunks)),
        "use_mode": dict(Counter(str(chunk.get("use_mode") or "") for chunk in chunks)),
        "risk_scope": dict(Counter(str(chunk.get("risk_scope") or "") for chunk in chunks)),
    }


def bm25_document_count(index_dir: Path) -> int:
    documents_path = index_dir / "documents.jsonl"
    if not documents_path.exists():
        return 0
    return sum(1 for line in documents_path.read_text(encoding="utf-8").splitlines() if line.strip())


def chroma_collection_counts(chroma_dir: Path) -> dict[str, int]:
    if not (chroma_dir / "chroma.sqlite3").exists():
        return {}
    try:
        import chromadb
        from chromadb.config import Settings
    except Exception:
        return {}
    client = chromadb.PersistentClient(path=str(chroma_dir), settings=Settings(anonymized_telemetry=False))
    counts: dict[str, int] = {}
    for collection in client.list_collections():
        try:
            counts[collection.name] = int(collection.count())
        except Exception:
            counts[collection.name] = -1
    return counts


def registry_source_map(registry: KnowledgeSourceRegistry) -> dict[str, Any]:
    return {source.id: source for source in registry.sources}


def find_duplicate_content(chunks: list[dict[str, Any]], limit: int = 50) -> list[dict[str, Any]]:
    by_hash: dict[str, list[dict[str, Any]]] = {}
    for chunk in chunks:
        key = str(chunk.get("content_sha256") or chunk.get("chunk_sha256") or content_hash(str(chunk.get("content") or "")))
        by_hash.setdefault(key, []).append(chunk)
    duplicates: list[dict[str, Any]] = []
    for key, rows in by_hash.items():
        if len(rows) <= 1:
            continue
        duplicates.append(
            {
                "content_sha256": key,
                "count": len(rows),
                "chunk_ids": [str(row.get("chunk_id")) for row in rows[:10]],
                "source_ids": sorted({str(row.get("source_id") or "") for row in rows}),
            }
        )
    return sorted(duplicates, key=lambda item: item["count"], reverse=True)[:limit]


def chunk_quality_issues(chunks: list[dict[str, Any]], limit: int = 200) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    required = [
        "chunk_id",
        "source_id",
        "title",
        "target_collection",
        "content",
        "review_status",
        "official_page_url",
        "content_sha256",
        "chunk_type",
        "use_mode",
        "risk_scope",
        "population_tags",
        "topic_tags",
        "license",
    ]
    for chunk in chunks:
        chunk_issues: list[str] = []
        for key in required:
            if chunk.get(key) in (None, "", []):
                chunk_issues.append(f"missing:{key}")
        content = str(chunk.get("content") or "")
        if len(content) < 80:
            chunk_issues.append("too_short")
        if len(content) > 2500:
            chunk_issues.append("too_long")
        if has_unsafe_operational_detail(content):
            chunk_issues.append("unsafe_operational_detail")
        if str(chunk.get("use_mode") or "") == "safety_only" and str(chunk.get("risk_scope") or "") != "safety_route_only":
            chunk_issues.append("safety_missing_route_scope")
        if bool(chunk.get("clinical_only")) and bool(chunk.get("user_facing")):
            chunk_issues.append("clinical_only_marked_user_facing")
        if content.count("\ufffd") > 0:
            chunk_issues.append("replacement_character")
        if chunk_issues:
            issues.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "source_id": chunk.get("source_id"),
                    "issues": chunk_issues,
                    "char_count": len(content),
                }
            )
        if len(issues) >= limit:
            break
    return issues


def write_markdown(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rag"))

import _bootstrap  # noqa: F401,E402
from config import get_settings  # noqa: E402
from kb_v11_utils import all_chunks, load_chunks_by_status, load_registry, utc_now_iso, write_json_atomic  # noqa: E402
from services.embedding_service import get_rag_v1_embedding_provider  # noqa: E402
from services.rag_v1_index_service import build_chroma_indexes, normalize_index_mode  # noqa: E402


def _content_hash(chunk: dict[str, Any]) -> str:
    return str(
        chunk.get("content_hash")
        or chunk.get("content_sha256")
        or chunk.get("chunk_sha256")
        or sha256(str(chunk.get("content") or "").encode("utf-8")).hexdigest()
    )


def _registry_hash(path: Path) -> str:
    if not path.exists():
        return ""
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _chunks_hash(chunks: list[dict[str, Any]]) -> str:
    rows = [
        {
            "chunk_id": chunk.get("chunk_id"),
            "content_hash": _content_hash(chunk),
            "review_status": chunk.get("review_status"),
            "use_mode": chunk.get("use_mode"),
            "target_collection": chunk.get("target_collection"),
        }
        for chunk in chunks
    ]
    payload = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in sorted(rows, key=lambda row: str(row["chunk_id"])))
    return sha256(payload.encode("utf-8")).hexdigest()


def _cache_key(model: str, chunk: dict[str, Any]) -> str:
    return f"{model}::{_content_hash(chunk)}"


def _read_cache(path: Path, current_model: str) -> tuple[dict[str, list[float]], dict[str, Any]]:
    cache: dict[str, list[float]] = {}
    legacy_reused = 0
    invalid = 0
    records = 0
    if not path.exists():
        return cache, {"records": 0, "legacy_reused": 0, "invalid": 0}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records += 1
            try:
                item = json.loads(line)
                embedding = item.get("embedding")
                if not isinstance(embedding, list):
                    invalid += 1
                    continue
                content_hash = str(item.get("content_hash") or item.get("chunk_sha256") or "")
                if not content_hash:
                    invalid += 1
                    continue
                model = str(item.get("embedding_model") or item.get("embedding_model_version") or "")
                if not model:
                    model = current_model
                    legacy_reused += 1
                cache[f"{model}::{content_hash}"] = [float(value) for value in embedding]
            except Exception:
                invalid += 1
    return cache, {"records": records, "legacy_reused": legacy_reused, "invalid": invalid}


def _write_cache(path: Path, cache: dict[str, list[float]]) -> None:
    rows = []
    for key, embedding in sorted(cache.items()):
        model, content_hash = key.split("::", 1)
        rows.append(
            {
                "embedding_model": model,
                "embedding_model_version": model,
                "content_hash": content_hash,
                "chunk_sha256": content_hash,
                "embedding": embedding,
            }
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    os.replace(tmp, path)


def _eligible_chunks(chunks: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    output = []
    for chunk in chunks:
        if bool(chunk.get("exclude_from_index")):
            continue
        status = str(chunk.get("review_status") or "pending").strip().lower()
        if mode == "production" and status not in {"approved", "reviewed"}:
            continue
        if mode == "staging" and status in {"rejected", "blocked"}:
            continue
        content = str(chunk.get("content") or "").strip()
        if not content:
            continue
        updated = dict(chunk)
        content_hash = _content_hash(updated)
        updated["content_hash"] = content_hash
        updated["content_sha256"] = content_hash
        updated["chunk_sha256"] = content_hash
        output.append(updated)
    return output


async def build_dense_index(
    *,
    mode: str,
    incremental: bool,
    force_rebuild: bool,
    dry_run: bool,
    batch_size: int | None,
    checkpoint_every: int,
    registry_path: str | Path | None,
) -> dict[str, Any]:
    started = time.perf_counter()
    registry = load_registry(registry_path)
    settings = get_settings()
    index_mode = normalize_index_mode(mode)
    all_rows = all_chunks(load_chunks_by_status(registry))
    chunks = _eligible_chunks(all_rows, index_mode)
    registry_file = ROOT / "backend" / "data" / "knowledge_base" / "sources" / "knowledge_sources.yaml"
    if not registry_file.exists():
        registry_file = ROOT / "backend" / "data" / "knowledge_base" / "sources" / "knowledge_sources_v1.yaml"
    cache_path = registry.paths["indexes_chroma"] / "embedding_cache.jsonl"
    model = settings.rag_embedding_model
    cache, cache_stats = _read_cache(cache_path, model)
    missing = [chunk for chunk in chunks if force_rebuild or _cache_key(model, chunk) not in cache]
    dimension = 0
    new_embeddings = 0

    if dry_run:
        report = {
            "created_at": utc_now_iso(),
            "dry_run": True,
            "index_mode": index_mode,
            "eligible_chunks": len(chunks),
            "cache_records": cache_stats["records"],
            "cache_hits": len(chunks) - len(missing),
            "new_embeddings_needed": len(missing),
            "force_rebuild": force_rebuild,
            "incremental": incremental,
            "embedding_model": model,
        }
        write_json_atomic(registry.paths["reports"] / f"dense_index_{index_mode}_dry_run.json", report)
        return report

    if missing:
        provider = get_rag_v1_embedding_provider()
        effective_batch = int(batch_size or settings.rag_embedding_batch_size or 16)
        checkpoint_every = max(int(checkpoint_every or 512), effective_batch)
        for start in range(0, len(missing), effective_batch):
            batch = missing[start : start + effective_batch]
            embeddings = await provider.embed_documents([str(chunk.get("content") or "") for chunk in batch])
            for chunk, embedding in zip(batch, embeddings):
                vector = [float(value) for value in embedding]
                cache[_cache_key(model, chunk)] = vector
                dimension = len(vector)
                new_embeddings += 1
            if new_embeddings and new_embeddings % max(effective_batch * 10, 100) == 0:
                print(f"embedded_new: {new_embeddings}/{len(missing)}", flush=True)
            if new_embeddings and new_embeddings % checkpoint_every == 0:
                _write_cache(cache_path, cache)
                print(f"checkpoint_saved: {new_embeddings}/{len(missing)}", flush=True)
        _write_cache(cache_path, cache)

    embeddings = [cache[_cache_key(model, chunk)] for chunk in chunks]
    if embeddings:
        dimension = len(embeddings[0])
    chroma_status = build_chroma_indexes(
        chunks,
        embeddings,
        registry.paths["indexes_chroma"],
        collections=sorted(collection for collection in registry.collections if collection != "case_rag"),
        index_mode=index_mode,
    )
    manifest = {
        "index_version": f"KB_V2.1_dense_{index_mode}_{utc_now_iso().replace(':', '').replace('+00:00', 'Z')}",
        "created_at": utc_now_iso(),
        "index_mode": index_mode,
        "incremental": incremental,
        "force_rebuild": force_rebuild,
        "dry_run": False,
        "embedding_provider": settings.rag_embedding_provider,
        "embedding_model": model,
        "embedding_model_version": model,
        "embedding_dimension": dimension,
        "chunk_count": len(chunks),
        "new_embeddings": new_embeddings,
        "cache_hits": len(chunks) - new_embeddings,
        "cache_path": cache_path.as_posix(),
        "registry_hash": _registry_hash(registry_file),
        "chunk_manifest_hash": _chunks_hash(chunks),
        "build_time_ms": int((time.perf_counter() - started) * 1000),
        "collection_counts": dict(Counter(str(chunk.get("target_collection") or "") for chunk in chunks)),
        "chroma_collections": chroma_status,
    }
    manifest_path = registry.paths["indexes_chroma"] / f"dense_index_manifest_{index_mode}.json"
    write_json_atomic(manifest_path, manifest)
    write_json_atomic(registry.paths["reports"] / f"dense_index_manifest_{index_mode}.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CARE-Psy full dense Chroma index from existing chunks.")
    parser.add_argument("--mode", choices=["staging", "production"], default="staging")
    parser.add_argument("--incremental", action="store_true")
    parser.add_argument("--force-rebuild", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--checkpoint-every", type=int, default=512)
    parser.add_argument("--registry", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    report = asyncio.run(
        build_dense_index(
            mode=args.mode,
            incremental=args.incremental,
            force_rebuild=args.force_rebuild,
            dry_run=args.dry_run,
            batch_size=args.batch_size,
            checkpoint_every=args.checkpoint_every,
            registry_path=args.registry,
        )
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"index_mode: {report.get('index_mode')}")
        print(f"dry_run: {report.get('dry_run')}")
        print(f"chunk_count: {report.get('chunk_count', report.get('eligible_chunks'))}")
        print(f"cache_hits: {report.get('cache_hits')}")
        print(f"new_embeddings: {report.get('new_embeddings', report.get('new_embeddings_needed'))}")
        print(f"embedding_model: {report.get('embedding_model')}")
        if report.get("chroma_collections"):
            print(f"chroma_collections: {json.dumps(report['chroma_collections'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

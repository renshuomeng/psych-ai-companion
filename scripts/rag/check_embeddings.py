from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from kb_v11_utils import chroma_collection_counts, load_registry, utc_now_iso, write_json_atomic


def _scan_embedding_cache(path: Path, sample_limit: int = 200) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "records": 0, "dimensions": [], "zero_vectors": 0, "sampled": 0}
    records = 0
    sampled = 0
    dimensions: set[int] = set()
    zero_vectors = 0
    invalid_records = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            records += 1
            if sampled >= sample_limit:
                continue
            try:
                item = json.loads(line)
                vector = item.get("embedding")
                if not isinstance(vector, list):
                    invalid_records += 1
                    continue
                sampled += 1
                dimensions.add(len(vector))
                norm = math.sqrt(sum(float(value) * float(value) for value in vector))
                if norm <= 1e-9:
                    zero_vectors += 1
            except Exception:
                invalid_records += 1
    return {
        "exists": True,
        "records": records,
        "sampled": sampled,
        "dimensions": sorted(dimensions),
        "zero_vectors": zero_vectors,
        "invalid_records_sample": invalid_records,
    }


def build_embedding_health(registry_path: str | Path | None = None) -> dict[str, Any]:
    registry = load_registry(registry_path)
    cache_path = registry.paths["indexes_chroma"] / "embedding_cache.jsonl"
    cache = _scan_embedding_cache(cache_path)
    chroma_counts = chroma_collection_counts(registry.paths["indexes_chroma"])
    health = {
        "created_at": utc_now_iso(),
        "embedding_cache": {
            **cache,
            "path": cache_path.as_posix(),
        },
        "chroma": {
            "path": registry.paths["indexes_chroma"].as_posix(),
            "collections": chroma_counts,
            "total_vectors": sum(count for count in chroma_counts.values() if count > 0),
        },
        "status": "ready" if cache.get("records", 0) > 0 and chroma_counts else "not_ready",
        "warnings": [],
    }
    if cache.get("zero_vectors"):
        health["warnings"].append("zero_vectors_detected")
    if len(cache.get("dimensions") or []) > 1:
        health["warnings"].append("mixed_embedding_dimensions")
    if not chroma_counts:
        health["warnings"].append("chroma_collections_missing_or_unreadable")
    write_json_atomic(registry.paths["reports"] / "embedding_health.json", health)
    return health


def main() -> int:
    parser = argparse.ArgumentParser(description="Check CARE-Psy RAG V1.1 embedding cache and Chroma collections.")
    parser.add_argument("--registry", default="backend/data/knowledge_base/sources/knowledge_sources_v1.yaml")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    health = build_embedding_health(args.registry)
    if args.json:
        print(json.dumps(health, ensure_ascii=False, indent=2))
    else:
        print(f"status: {health['status']}")
        print(f"embedding_records: {health['embedding_cache']['records']}")
        print(f"dimensions: {health['embedding_cache']['dimensions']}")
        print(f"chroma_vectors: {health['chroma']['total_vectors']}")
        if health["warnings"]:
            print("warnings:")
            for warning in health["warnings"]:
                print(f"- {warning}")
    return 0 if health["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())

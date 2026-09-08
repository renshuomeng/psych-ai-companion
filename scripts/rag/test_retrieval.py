import argparse
import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

import _bootstrap  # noqa: F401,E402
from services.embedding_service import get_rag_v1_embedding_provider  # noqa: E402
from services.knowledge_source_registry import load_knowledge_source_registry  # noqa: E402
from services.rag_v1_index_service import query_bm25, query_chroma  # noqa: E402


def _preview(text: str, length: int = 160) -> str:
    return " ".join(text.split())[:length]


async def main() -> int:
    parser = argparse.ArgumentParser(description="Query offline RAG V1 staging indexes.")
    parser.add_argument("--registry", default="backend/data/knowledge_base/sources/knowledge_sources_v1.yaml")
    parser.add_argument("--query", required=True)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--collection", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    registry = load_knowledge_source_registry(args.registry)
    bm25 = query_bm25(registry.paths["indexes_bm25"], args.query, top_k=args.top_k)
    dense = []
    dense_error = ""
    try:
        provider = get_rag_v1_embedding_provider()
        embedding = await provider.embed_query(args.query)
        dense = query_chroma(
            registry.paths["indexes_chroma"],
            embedding,
            top_k=args.top_k,
            collection=args.collection or None,
        )
    except Exception as exc:
        dense_error = str(exc)
    payload = {"query": args.query, "dense": dense, "dense_error": dense_error, "bm25": bm25}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print("Dense Top-K")
    if dense_error:
        print(f"- unavailable: {dense_error}")
    for item in dense:
        print(f"- {item.get('source_id')} | {item.get('title')} | {item.get('section')} | {item.get('target_collection')} | {item.get('score')}")
        print(f"  {_preview(str(item.get('content', '')))}")
    print("\nBM25 Top-K")
    for item in bm25:
        print(f"- {item.get('source_id')} | {item.get('title')} | {item.get('section')} | {item.get('target_collection')} | {item.get('score')}")
        print(f"  {_preview(str(item.get('content', '')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

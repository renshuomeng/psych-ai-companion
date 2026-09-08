import argparse
import asyncio
import json

import _bootstrap  # noqa: F401
from database.db import SessionLocal, init_db
from services.retrieval_service import retrieve


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run a single RAG retrieval query.")
    parser.add_argument("--query", required=True)
    parser.add_argument(
        "--mode",
        default="emotion_aware_hybrid_rerank",
        choices=[
            "vector_only",
            "keyword_only",
            "BM25_only",
            "hybrid",
            "hybrid_rerank",
            "emotion_aware_hybrid",
            "emotion_aware_hybrid_rerank",
        ],
    )
    parser.add_argument("--emotion", default="")
    parser.add_argument("--cause", default="")
    parser.add_argument("--strategy", default="")
    parser.add_argument("--risk-level", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    psychological_context = {
        key: value
        for key, value in {
            "emotion": args.emotion,
            "cause": args.cause,
            "strategy": args.strategy,
            "risk_level": args.risk_level,
        }.items()
        if value
    }
    init_db()
    with SessionLocal() as db:
        result = await retrieve(
            db,
            args.query,
            session_id="manual_rag_test",
            mode=args.mode,
            psychological_context=psychological_context or None,
        )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"status: {result['retrieval_status']}")
        if psychological_context:
            print(f"psychological_context: {psychological_context}")
        for item in result.get("retrieved_chunks", []):
            print(
                f"- {item['source_id']} / {item['section']} "
                f"score={item.get('rerank_score')} semantic={item.get('semantic_score')} "
                f"psych={item.get('psychological_score')}: {item['content'][:80]}"
            )
    return 0 if result["retrieval_status"] in {"success", "insufficient_evidence"} else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

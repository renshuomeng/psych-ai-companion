import asyncio
from pathlib import Path
from typing import Any

from evaluation.metrics.retrieval_metrics import evaluate_retrieval
from evaluation.runners.common import DATASET_DIR, read_jsonl, write_json

from database.db import SessionLocal, init_db
from services.knowledge_ingestion_service import build_knowledge_base
from services.retrieval_service import retrieve


async def _evaluate_mode(mode: str) -> dict[str, Any]:
    init_db()
    dataset = DATASET_DIR / "rag_cases.jsonl"
    if not dataset.exists():
        dataset = DATASET_DIR / "rag_queries.jsonl"
    cases = read_jsonl(dataset)
    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        await build_knowledge_base(db)
        for case in cases:
            result = await retrieve(
                db,
                case["query"],
                session_id=f"eval_rag_{mode}",
                mode=mode,
                psychological_context=case.get("psychological_context"),
            )
            rows.append(
                {
                    "query_id": case["query_id"],
                    "query": case["query"],
                    "relevant_source_ids": case.get("relevant_source_ids", []),
                    "retrieved_chunks": result.get("retrieved_chunks", []),
                    "retrieval_status": result.get("retrieval_status"),
                    "psychological_context": case.get("psychological_context", {}),
                }
            )
    return {"mode": mode, "metrics": evaluate_retrieval(rows), "cases": rows}


def evaluate_rag(output_dir: Path | None = None) -> dict[str, Any]:
    modes = ["vector_only", "BM25_only", "hybrid", "emotion_aware_hybrid", "emotion_aware_hybrid_rerank"]
    reports = [asyncio.run(_evaluate_mode(mode)) for mode in modes]
    summary = {"modes": {item["mode"]: item["metrics"] for item in reports}, "reports": reports}
    if output_dir:
        write_json(output_dir / "rag_metrics.json", summary)
    return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    print(evaluate_rag(args.output_dir)["modes"])

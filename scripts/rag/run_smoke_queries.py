import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

import _bootstrap  # noqa: F401,E402
from services.knowledge_source_registry import load_knowledge_source_registry  # noqa: E402
from services.rag_v1_pipeline import run_smoke_queries  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run CARE-Psy RAG V1 smoke queries against offline staging indexes.")
    parser.add_argument("--registry", default="backend/data/knowledge_base/sources/knowledge_sources_v1.yaml")
    parser.add_argument("--queries", default="evaluation/rag_v1_smoke_queries.json")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    registry = load_knowledge_source_registry(args.registry)
    results = await run_smoke_queries(registry, ROOT / args.queries, top_k=args.top_k)
    output_path = registry.paths["reports"] / "smoke_results.json"
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    build_report_path = registry.paths["reports"] / "build_report.json"
    if build_report_path.exists():
        report = json.loads(build_report_path.read_text(encoding="utf-8"))
        smoke_summary = [
            {
                "query": item["query"],
                "dense_top_source": item["dense"][0]["source_id"] if item.get("dense") else "",
                "dense_top_title": item["dense"][0]["title"] if item.get("dense") else "",
                "bm25_top_source": item["bm25"][0]["source_id"] if item.get("bm25") else "",
                "bm25_top_title": item["bm25"][0]["title"] if item.get("bm25") else "",
            }
            for item in results
        ]
        report["smoke_results"] = smoke_summary
        build_report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path = registry.paths["reports"] / "rag_v1_build_report.md"
        if md_path.exists():
            existing = md_path.read_text(encoding="utf-8")
            marker = "\n## Smoke Results\n"
            existing = existing.split(marker)[0].rstrip()
            lines = [existing, marker.strip()]
            for item in smoke_summary:
                lines.append(
                    f"- dense={item['dense_top_source'] or 'none'}; "
                    f"bm25={item['bm25_top_source'] or 'none'}; "
                    f"query={item['query']}"
                )
            md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(f"smoke_results: {output_path}")
        for item in results:
            dense = item["dense"][0]["source_id"] if item.get("dense") else "none"
            bm25 = item["bm25"][0]["source_id"] if item.get("bm25") else "none"
            print(f"- dense={dense} bm25={bm25} query={item['query']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

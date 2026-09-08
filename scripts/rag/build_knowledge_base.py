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
from services.knowledge_source_registry import load_knowledge_source_registry  # noqa: E402
from services.rag_v1_pipeline import build_rag_v1_knowledge_base  # noqa: E402


async def async_main() -> int:
    parser = argparse.ArgumentParser(description="Parse, clean, chunk and index CARE-Psy RAG sources.")
    parser.add_argument("--registry", default=None, help="Registry path. Defaults to V2 knowledge_sources.yaml when present, otherwise V1.")
    parser.add_argument("--mode", choices=["staging", "production"], default="staging", help="Build staging or production indexes.")
    parser.add_argument("--dry-run", action="store_true", help="Inspect existing lifecycle status without parsing or writing indexes.")
    parser.add_argument("--sample-mode", action="store_true", help="Limit dense indexing to a deterministic sample.")
    parser.add_argument("--sample-limit", type=int, default=None, help="Dense sample limit when --sample-mode is enabled.")
    parser.add_argument(
        "--max-dense-chunks",
        type=int,
        default=None,
        help="Legacy alias for dense sampling; values >0 enable sample mode, 0 means all eligible chunks.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    registry = load_knowledge_source_registry(args.registry)
    report = await build_rag_v1_knowledge_base(
        registry,
        max_dense_chunks=args.max_dense_chunks,
        index_mode=args.mode,
        dry_run=args.dry_run,
        sample_mode=args.sample_mode if args.max_dense_chunks is None else None,
        sample_limit=args.sample_limit,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"dry_run: {report.get('dry_run', False)}")
        print(f"index_mode: {report.get('index_mode', args.mode)}")
        print(f"sample_mode: {report.get('sample_mode', False)}")
        print(f"registry_sources: {report.get('registry_sources', 'skipped')}")
        print(f"documents_discovered: {report.get('documents_discovered')}")
        print(f"parsed_documents: {report.get('parsed_documents', 'skipped')}")
        print(f"chunks: {report.get('chunks', report.get('existing_chunks', {}).get('total', 0))}")
        print(f"review_status: {report.get('review_status', report.get('existing_chunks', {}).get('review_status', {}))}")
        indexable = report.get("indexable_chunks")
        if isinstance(indexable, dict):
            indexable = indexable.get("total", 0)
        print(f"indexable_chunks: {indexable if indexable is not None else 0}")
        print(f"average_chunk_size: {report.get('average_chunk_size', 'n/a')}")
        print(f"languages: {report.get('languages', report.get('existing_chunks', {}).get('languages', {}))}")
        print(f"collections: {report.get('collections', report.get('existing_chunks', {}).get('collections', {}))}")
        print(f"embedding: {report.get('embedding', 'skipped')}")
        print(f"chroma: {report.get('chroma_collections', 'skipped')}")
        print(f"bm25: {report.get('bm25', 'skipped')}")
        if report.get("parse_errors"):
            print("parse_errors:")
            for item in report["parse_errors"][:30]:
                print(f"- {item['source_id']}: {item['code']} {item['message']}")
    chunk_total = report.get("chunks", report.get("existing_chunks", {}).get("total", 0))
    return 0 if chunk_total else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(async_main()))

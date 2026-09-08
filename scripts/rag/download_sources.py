import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "backend"))

import _bootstrap  # noqa: F401,E402
from services.knowledge_download_service import download_registry_sources  # noqa: E402
from services.knowledge_source_registry import load_knowledge_source_registry  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Download CARE-Psy RAG official sources from the registry allowlist.")
    parser.add_argument("--registry", default=None, help="Registry path. Defaults to V2 knowledge_sources.yaml when present, otherwise V1.")
    parser.add_argument("--limit", type=int, default=None, help="Download only the first N auto-download sources.")
    parser.add_argument("--source-id", action="append", default=None, help="Download only selected source id(s). Can be repeated.")
    parser.add_argument("--timeout", type=int, default=None, help="Override per-request timeout seconds for this run.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    registry = load_knowledge_source_registry(args.registry)
    sources = registry.sources
    if args.source_id:
        wanted = set(args.source_id)
        sources = [source for source in sources if source.id in wanted]
    if args.limit is not None:
        auto_seen = 0
        limited = []
        for source in sources:
            if not source.enabled or not source.auto_download:
                limited.append(source)
                continue
            auto_seen += 1
            if auto_seen <= args.limit:
                limited.append(source)
            else:
                limited.append(replace(source, auto_download=False))
        sources = limited
    build_policy = dict(registry.build_policy)
    if args.timeout is not None:
        build_policy["request_timeout_seconds"] = int(args.timeout)
    registry = replace(registry, sources=sources, build_policy=build_policy)
    summary = download_registry_sources(registry)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"registry_sources: {summary['total_sources']}")
        print(f"auto_download_sources: {summary['auto_download_sources']}")
        print(f"successful_sources: {summary['successful_sources']}")
        print(f"partial_sources: {summary['partial_sources']}")
        print(f"failed_sources: {summary['failed_sources']}")
        print(f"files_downloaded: {summary['files_downloaded']}")
        print(f"duplicates: {summary['duplicates']}")
        print(f"bytes_downloaded: {summary['bytes_downloaded']}")
        if summary["errors"]:
            print("errors:")
            for item in summary["errors"][:30]:
                print(f"- {item['source_id']}: {item['code']} {item['message']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

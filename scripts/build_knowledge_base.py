import argparse
import asyncio
import json

import _bootstrap  # noqa: F401
from database.db import SessionLocal, init_db
from services.knowledge_ingestion_service import build_knowledge_base


async def main() -> int:
    parser = argparse.ArgumentParser(description="Build local psychology knowledge base index.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        report = await build_knowledge_base(db)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"status: {report['status']}")
        print(f"raw_dir: {report['raw_dir']}")
        print(f"imported: {len(report['imported'])}")
        for item in report["imported"]:
            print(f"- {item['source_id']} {item['title']} chunks={item['chunk_count']}")
        if report["errors"]:
            print("errors:")
            for item in report["errors"]:
                print(f"- {item['file']}: {item['code']} {item['message']}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

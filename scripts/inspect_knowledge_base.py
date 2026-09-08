import argparse
import json

import _bootstrap  # noqa: F401
from database.db import SessionLocal, init_db
from services.vector_store_service import get_source, list_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect imported knowledge sources.")
    parser.add_argument("--source-id", default="", help="Show one source with chunks.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        data = get_source(db, args.source_id) if args.source_id else {"sources": list_sources(db)}
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if args.source_id:
            if not data:
                print("source not found")
                return 1
            print(f"{data['source_id']} {data['title']} chunks={data['chunk_count']}")
        else:
            for item in data["sources"]:
                print(f"{item['source_id']} | {item['title']} | {item['topic']} | chunks={item['chunk_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

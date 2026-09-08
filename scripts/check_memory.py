import argparse
import json

import _bootstrap  # noqa: F401
from database.db import SessionLocal, init_db
from services.memory_service import get_memory_snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect session memory without printing secrets.")
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()
    init_db()
    with SessionLocal() as db:
        print(json.dumps(get_memory_snapshot(db, args.session_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

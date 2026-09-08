import argparse

import _bootstrap  # noqa: F401
from database.db import SessionLocal, init_db
from database.models import ChatMessage, ConversationSummary, MemorySettings, RequestMetric, RetrievalLog, RiskState, UserMemoryItem


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear evaluation/test session data only.")
    parser.add_argument("--prefix", default="eval_", help="Session id prefix to clear.")
    args = parser.parse_args()
    init_db()
    tables = [ChatMessage, ConversationSummary, MemorySettings, RequestMetric, RetrievalLog, RiskState, UserMemoryItem]
    with SessionLocal() as db:
        deleted = {}
        for table in tables:
            count = db.query(table).filter(table.session_id.startswith(args.prefix)).delete(synchronize_session=False)
            deleted[table.__tablename__] = int(count)
        db.commit()
    print(deleted)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import shutil
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from config import get_settings
from database.db import SessionLocal, init_db
from services.conversation_service import ensure_conversations_for_existing_sessions


def main() -> int:
    settings = get_settings()
    db_path = Path(str(settings.database_url).replace("sqlite:///", ""))
    backup_path = None
    if db_path.exists():
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"{db_path.stem}_before_conversations_{timestamp}{db_path.suffix}"
        shutil.copy2(db_path, backup_path)

    init_db()
    with SessionLocal() as db:
        report = ensure_conversations_for_existing_sessions(db)

    output = {
        "status": "completed",
        "database": str(db_path),
        "backup": str(backup_path) if backup_path else None,
        "legacy_session_migration": report,
        "note": "conversation_id 在本项目中等同于旧 session_id；旧数据不会被删除。",
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

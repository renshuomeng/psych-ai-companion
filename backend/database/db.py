from collections.abc import Generator
from datetime import datetime
from pathlib import Path
import shutil

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings
from database.models import Base


settings = get_settings()
database_path = Path(str(settings.database_url).replace("sqlite:///", ""))
database_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _table_columns(connection, table_name: str) -> set[str]:
    try:
        rows = connection.execute(text(f"PRAGMA table_info({table_name})")).mappings()
    except Exception:
        return set()
    return {str(row["name"]) for row in rows}


def _add_column_if_missing(connection, table_name: str, column_name: str, ddl: str) -> None:
    if column_name not in _table_columns(connection, table_name):
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {ddl}"))


def _table_exists(connection, table_name: str) -> bool:
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name"),
        {"table_name": table_name},
    ).first()
    return row is not None


def _backup_database_before_rbac() -> None:
    if not database_path.exists():
        return
    with engine.connect() as connection:
        if _table_exists(connection, "users"):
            return
    backup_dir = database_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{database_path.stem}_before_rbac_{timestamp}{database_path.suffix}"
    if not backup_path.exists():
        shutil.copy2(database_path, backup_path)


def _ensure_lightweight_migrations() -> None:
    with engine.begin() as connection:
        _add_column_if_missing(
            connection,
            "users",
            "role",
            "role VARCHAR(32) DEFAULT 'user'",
        )
        _add_column_if_missing(
            connection,
            "users",
            "is_active",
            "is_active BOOLEAN DEFAULT 1",
        )
        _add_column_if_missing(
            connection,
            "users",
            "created_at",
            "created_at DATETIME",
        )
        _add_column_if_missing(
            connection,
            "users",
            "updated_at",
            "updated_at DATETIME",
        )
        connection.execute(text("UPDATE users SET role = 'user' WHERE role IS NULL OR role = ''"))
        connection.execute(text("UPDATE users SET is_active = 1 WHERE is_active IS NULL"))
        _add_column_if_missing(
            connection,
            "chat_message",
            "conversation_id",
            "conversation_id VARCHAR(128) DEFAULT ''",
        )
        _add_column_if_missing(
            connection,
            "chat_message",
            "sequence",
            "sequence INTEGER DEFAULT 0",
        )
        _add_column_if_missing(
            connection,
            "chat_message",
            "message_type",
            "message_type VARCHAR(32) DEFAULT 'text'",
        )
        _add_column_if_missing(
            connection,
            "chat_message",
            "attachments_json",
            "attachments_json TEXT DEFAULT '[]'",
        )
        _add_column_if_missing(
            connection,
            "attachment",
            "conversation_id",
            "conversation_id VARCHAR(128) DEFAULT ''",
        )
        _add_column_if_missing(
            connection,
            "attachment",
            "message_id",
            "message_id VARCHAR(64)",
        )
        connection.execute(
            text("UPDATE chat_message SET conversation_id = session_id WHERE conversation_id = ''")
        )
        connection.execute(
            text("UPDATE attachment SET conversation_id = session_id WHERE conversation_id = ''")
        )
        indexes = [
            "CREATE INDEX IF NOT EXISTS ix_chat_message_conversation_id ON chat_message(conversation_id)",
            "CREATE INDEX IF NOT EXISTS ix_chat_message_conversation_sequence ON chat_message(conversation_id, sequence)",
            "CREATE INDEX IF NOT EXISTS ix_chat_message_created_at ON chat_message(created_at)",
            "CREATE INDEX IF NOT EXISTS ix_attachment_conversation_id ON attachment(conversation_id)",
            "CREATE INDEX IF NOT EXISTS ix_attachment_message_id ON attachment(message_id)",
            "CREATE INDEX IF NOT EXISTS ix_conversation_owner_last_message ON conversation(owner_id, is_archived, last_message_at)",
            "CREATE INDEX IF NOT EXISTS ix_conversation_updated_at ON conversation(updated_at)",
            "CREATE INDEX IF NOT EXISTS ix_users_role_active ON users(role, is_active)",
            "CREATE INDEX IF NOT EXISTS ix_admin_audit_log_actor ON admin_audit_log(actor_user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_knowledge_review_audit_log_reviewer ON knowledge_review_audit_log(reviewer_user_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_human_evaluation_review_case ON human_evaluation_review(run_id, case_id)",
        ]
        for ddl in indexes:
            connection.execute(text(ddl))


def init_db() -> None:
    _backup_database_before_rbac()
    Base.metadata.create_all(bind=engine)
    _ensure_lightweight_migrations()
    with engine.begin() as connection:
        try:
            connection.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_chunks_fts "
                    "USING fts5(chunk_id UNINDEXED, source_id UNINDEXED, title, section, topic, content, "
                    "tokenize='unicode61')"
                )
            )
        except Exception:
            # Some stripped SQLite builds may not include FTS5; retrieval falls back to Python keyword scoring.
            pass
    from auth.service import ensure_initial_admin

    with SessionLocal() as db:
        ensure_initial_admin(db)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_database_status() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return {"status": "ok", "message": "SQLite is available"}
    except Exception:
        return {"status": "error", "message": "SQLite is not available"}

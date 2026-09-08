import asyncio
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from database.models import Attachment, MultimodalJob
from services.ark_file_service import delete_provider_file


def cleanup_expired_files(db: Session) -> int:
    now = datetime.now(timezone.utc)
    expired = db.query(Attachment).filter(Attachment.expires_at <= now).all()
    count = 0
    for attachment in expired:
        Path(attachment.local_path).unlink(missing_ok=True)
        if attachment.provider_file_id:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(delete_provider_file(attachment.provider_file_id))
            except RuntimeError:
                asyncio.run(delete_provider_file(attachment.provider_file_id))
        db.delete(attachment)
        count += 1
    db.query(MultimodalJob).filter(MultimodalJob.expires_at <= now).delete()
    db.commit()
    return count

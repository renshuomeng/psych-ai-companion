from pathlib import Path

from sqlalchemy.orm import Session

from config import get_settings
from database.models import (
    Attachment,
    ChatMessage,
    Conversation,
    ConversationSummary,
    MemorySettings,
    MultimodalJob,
    RequestMetric,
    RetrievalLog,
    RiskState,
    InterventionSession,
    Feedback,
    UserMemoryItem,
)
from services.ark_file_service import delete_provider_file


async def delete_session_data(db: Session, session_id: str) -> dict[str, int | str]:
    attachments = (
        db.query(Attachment)
        .filter((Attachment.session_id == session_id) | (Attachment.conversation_id == session_id))
        .all()
    )
    removed_files = 0
    removed_provider_files = 0
    for attachment in attachments:
        Path(attachment.local_path).unlink(missing_ok=True)
        if attachment.provider_file_id:
            await delete_provider_file(attachment.provider_file_id)
            removed_provider_files += 1
        db.delete(attachment)
        removed_files += 1

    removed_jobs = (
        db.query(MultimodalJob)
        .filter(MultimodalJob.session_id == session_id)
        .delete(synchronize_session=False)
    )
    removed_messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete(
        synchronize_session=False
    )
    removed_memory = db.query(UserMemoryItem).filter(UserMemoryItem.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(ConversationSummary).filter(ConversationSummary.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(MemorySettings).filter(MemorySettings.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(RiskState).filter(RiskState.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(RetrievalLog).filter(RetrievalLog.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(RequestMetric).filter(RequestMetric.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(InterventionSession).filter(InterventionSession.session_id == session_id).delete(
        synchronize_session=False
    )
    db.query(Feedback).filter(Feedback.session_id == session_id).delete(synchronize_session=False)
    db.query(Conversation).filter(Conversation.id == session_id).delete(synchronize_session=False)
    db.commit()
    return {
        "status": "deleted",
        "session_id": session_id,
        "removed_files": removed_files,
        "removed_provider_files": removed_provider_files,
        "removed_jobs": int(removed_jobs),
        "removed_messages": int(removed_messages),
        "removed_memory_items": int(removed_memory),
    }


def privacy_summary(session_id: str) -> dict[str, object]:
    settings = get_settings()
    return {
        "session_id": session_id,
        "retention_hours": settings.upload_retention_hours,
        "items": [
            "图片、音频和视频只在你主动上传或授权录制后处理。",
            "上传文件会用于生成转写、OCR、视觉摘要和安全风险检查。",
            "需要模型处理时，相关文本、图片或视频文件会发送给豆包/火山方舟服务。",
            "系统不进行医学诊断，不提供药物建议，也不承诺治疗效果。",
            "你可以随时删除当前会话数据，系统会清理本地附件、任务记录和已记录的供应商文件引用。",
            "请不要上传无权处理的他人隐私内容。",
        ],
    }

import json

import pytest


@pytest.mark.asyncio
async def test_multimodal_job_worker_processes_queued_job(monkeypatch):
    from database.db import SessionLocal, init_db
    from services.conversation_service import create_conversation
    from services.job_service import create_job, get_job, job_to_response
    from services import multimodal_job_worker
    from schemas.multimodal import MultimodalJobCreateRequest

    init_db()
    owner = "test_owner_job_worker"
    with SessionLocal() as db:
        conversation = create_conversation(db, owner, title="异步任务")
        job = create_job(
            db,
            MultimodalJobCreateRequest(
                session_id=conversation["id"],
                message="最近论文压力很大。",
                file_ids=[],
                checkin=None,
            ),
            owner_id=owner,
        )
        job_id = job.job_id

    async def fake_send_conversation_message(db, conversation_id, owner_id, content, file_ids, checkin=None):
        assert owner_id == owner
        assert content == "最近论文压力很大。"
        return {
            "conversation": {
                "id": conversation_id,
                "title": "异步任务",
                "created_at": "2026-09-07T13:00:00Z",
                "updated_at": "2026-09-07T13:00:01Z",
                "last_message_at": "2026-09-07T13:00:01Z",
                "is_archived": False,
                "title_manually_set": False,
                "last_message_preview": "AI 回复",
                "message_count": 2,
            },
            "user_message": {
                "id": "user-msg",
                "message_id": "user-msg",
                "conversation_id": conversation_id,
                "role": "user",
                "content": content,
                "created_at": "2026-09-07T13:00:00Z",
                "sequence": 1,
                "message_type": "text",
                "attachments": [],
                "metadata": {},
            },
            "assistant_message": {
                "id": "assistant-msg",
                "message_id": "assistant-msg",
                "conversation_id": conversation_id,
                "role": "assistant",
                "content": "我听到你最近压力很大，我们先把今晚要做的事拆小一点。",
                "created_at": "2026-09-07T13:00:01Z",
                "sequence": 2,
                "message_type": "text",
                "attachments": [],
                "metadata": {"risk": {"level": "low"}},
            },
            "result": {
                "conversation_id": conversation_id,
                "reply": "我听到你最近压力很大，我们先把今晚要做的事拆小一点。",
            },
        }

    monkeypatch.setattr(multimodal_job_worker, "send_conversation_message", fake_send_conversation_message)

    processed = await multimodal_job_worker.process_job(job_id)

    assert processed is True
    with SessionLocal() as db:
        row = get_job(db, job_id)
        response = job_to_response(row)
        stored_request = json.loads(row.request_json)
    assert response["status"] == "completed"
    assert response["stage"] == "completed"
    assert response["progress"] == 100
    assert response["result"]["assistant_message"]["content"].startswith("我听到你")
    assert stored_request["_owner_id"] == owner


@pytest.mark.asyncio
async def test_multimodal_job_worker_skips_cancelled_job(monkeypatch):
    from database.db import SessionLocal, init_db
    from services.conversation_service import create_conversation
    from services.job_service import cancel_job, create_job, get_job, job_to_response
    from services import multimodal_job_worker
    from schemas.multimodal import MultimodalJobCreateRequest

    init_db()
    owner = "test_owner_job_cancelled"
    with SessionLocal() as db:
        conversation = create_conversation(db, owner, title="取消任务")
        job = create_job(
            db,
            MultimodalJobCreateRequest(session_id=conversation["id"], message="先取消。", file_ids=[]),
            owner_id=owner,
        )
        job_id = job.job_id
        cancel_job(db, job_id)

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("cancelled jobs must not be processed")

    monkeypatch.setattr(multimodal_job_worker, "send_conversation_message", should_not_run)

    processed = await multimodal_job_worker.process_job(job_id)

    assert processed is False
    with SessionLocal() as db:
        response = job_to_response(get_job(db, job_id))
    assert response["status"] == "cancelled"

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient


os.environ["APP_ENV"] = "development"
os.environ["PUBLIC_ACCESS_ENABLED"] = "false"

from config import get_settings  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="module")
def client():
    from database.db import init_db
    from main import app

    init_db()
    _cleanup_test_rbac_rows()
    with TestClient(app) as test_client:
        yield test_client
    _cleanup_test_rbac_rows()


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _cleanup_test_rbac_rows() -> None:
    from database.db import SessionLocal
    from database.models import AdminAuditLog, KnowledgeReviewAuditLog, User

    with SessionLocal() as db:
        users = (
            db.query(User)
            .filter(User.email.like("%@example.test"))
            .all()
        )
        user_ids = [user.id for user in users]
        if user_ids:
            db.query(AdminAuditLog).filter(AdminAuditLog.actor_user_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(AdminAuditLog).filter(AdminAuditLog.target_id.in_(user_ids)).delete(synchronize_session=False)
            db.query(KnowledgeReviewAuditLog).filter(
                KnowledgeReviewAuditLog.reviewer_user_id.in_(user_ids)
            ).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()


def _make_user(role="user", *, is_active: bool = True):
    from auth.permissions import Role
    from auth.service import create_jwt_for_user, create_user
    from database.db import SessionLocal, init_db

    init_db()
    with SessionLocal() as db:
        user = create_user(
            db,
            username=_unique(f"rbac_{role}"),
            email=f"{_unique(role)}@example.test",
            password="Password123!",
            role=Role(role),
            is_active=is_active,
        )
        token, _ = create_jwt_for_user(user)
        return user, {"Authorization": f"Bearer {token}"}


def _fake_knowledge_chunks(monkeypatch):
    from routers import knowledge as knowledge_router

    registry = SimpleNamespace()

    def fake_load_all_chunks():
        return registry, [
            {
                "chunk_id": "CHUNK_SAFETY_1",
                "source_id": "SRC_1",
                "title": "Safety support",
                "section": "Safety",
                "topic": "crisis",
                "topics": ["self_harm"],
                "target_collection": "safety",
                "use_mode": "runtime",
                "risk_scope": "self_harm",
                "review_priority": "P0",
                "review_status": "pending",
                "content": "Seek immediate professional help in acute crisis.",
            }
        ]

    monkeypatch.setattr(knowledge_router, "_load_all_chunks", fake_load_all_chunks)


def test_default_role_user(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": _unique("register_user"),
            "email": f"{_unique('register')}@example.test",
            "password": "Password123!",
        },
    )

    assert response.status_code == 200
    assert response.json()["user"]["role"] == "user"
    assert "access_token" in response.json()


def test_role_enum():
    from auth.permissions import Role, role_values

    assert role_values() == [role.value for role in Role]
    assert set(role_values()) == {"user", "reviewer", "developer", "admin"}


def test_permission_mapping():
    from auth.permissions import Permission, Role, has_permission, permissions_for_role

    assert Permission.CHAT_USE in permissions_for_role(Role.USER)
    assert Permission.KNOWLEDGE_REVIEW not in permissions_for_role(Role.USER)
    assert Permission.KNOWLEDGE_REVIEW in permissions_for_role(Role.REVIEWER)
    assert Permission.EVALUATION_RUN_CREATE in permissions_for_role(Role.DEVELOPER)
    assert Permission.PRODUCTION_KB_PUBLISH not in permissions_for_role(Role.DEVELOPER)
    assert has_permission(Role.ADMIN, Permission.USER_MANAGE)


def test_user_chat_allowed(client, monkeypatch):
    from routers import chat as chat_router

    async def fake_chat_flow(**_kwargs):
        return {
            "reply": "我在。",
            "emotion": {"primary": "anxiety"},
            "risk": {"level": "low", "reason": "internal detail", "action": "support"},
            "agent_trace": [{"step": "hidden"}],
            "psychological_state": {"hidden": True},
            "strategy_plan": {"hidden": True},
            "knowledge_sources": [{"source_id": "SRC"}],
            "retrieval": {"debug": True},
            "rag_route": {"debug": True},
            "provider_metadata": {"secret": "never"},
            "request_metrics": {"latency_ms": 1},
        }

    monkeypatch.setattr(chat_router, "run_chat_flow", fake_chat_flow)
    _, headers = _make_user("user")

    response = client.post("/api/chat", json={"message": "最近压力很大。"}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "我在。"
    assert body["agent_trace"] == []
    assert body["knowledge_sources"] == []
    assert body["provider_metadata"] == {}


def test_user_evaluation_forbidden(client):
    _, headers = _make_user("user")

    response = client.get("/api/evaluation/registry", headers=headers)

    assert response.status_code == 403


def test_user_knowledge_review_forbidden(client, monkeypatch):
    _fake_knowledge_chunks(monkeypatch)
    _, headers = _make_user("user")

    response = client.get("/api/knowledge/chunks", headers=headers)

    assert response.status_code == 403


def test_reviewer_knowledge_review_allowed(client, monkeypatch):
    _fake_knowledge_chunks(monkeypatch)
    _, headers = _make_user("reviewer")

    response = client.get("/api/knowledge/chunks", headers=headers)

    assert response.status_code == 200
    assert response.json()["items"][0]["chunk_id"] == "CHUNK_SAFETY_1"


def test_reviewer_human_eval_allowed(client):
    _, headers = _make_user("reviewer")

    response = client.get("/api/evaluation/review/cases", headers=headers)

    assert response.status_code == 200
    assert "items" in response.json()


def test_reviewer_admin_forbidden(client):
    _, headers = _make_user("reviewer")

    response = client.get("/api/admin/users", headers=headers)

    assert response.status_code == 403


def test_developer_evaluation_allowed(client):
    _, headers = _make_user("developer")

    response = client.get("/api/evaluation/registry", headers=headers)

    assert response.status_code == 200
    assert "frameworks" in response.json()


def test_developer_rag_debug_allowed(client):
    _, headers = _make_user("developer")

    response = client.get("/api/debug/rag", headers=headers)

    assert response.status_code == 200
    assert response.json()["rag_enabled"] in {True, False}


def test_developer_production_publish_forbidden(client):
    _, headers = _make_user("developer")

    response = client.post("/api/knowledge/production/publish", json={"dry_run": True}, headers=headers)

    assert response.status_code == 403


def test_admin_user_management_allowed(client):
    _, headers = _make_user("admin")

    response = client.get("/api/admin/users", headers=headers)

    assert response.status_code == 200
    assert "items" in response.json()


def test_admin_role_change_allowed(client):
    admin, headers = _make_user("admin")
    user, _ = _make_user("user")

    response = client.patch(f"/api/admin/users/{user.id}", json={"role": "reviewer"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["role"] == "reviewer"
    assert admin.id


def test_last_admin_protection(monkeypatch):
    from auth.permissions import Role
    from auth.service import ensure_not_last_admin
    from database.models import User
    from schemas.errors import AppError

    monkeypatch.setattr("auth.service.count_active_admins", lambda _db: 1)
    target = User(
        id="last_admin",
        username="last_admin",
        email="last_admin@example.test",
        password_hash="x",
        role=Role.ADMIN.value,
        is_active=True,
    )

    with pytest.raises(AppError):
        ensure_not_last_admin(None, target, role=Role.USER)


def test_cross_user_conversation_forbidden(client):
    from auth.dependencies import principal_from_user
    from database.db import SessionLocal
    from services.conversation_service import create_conversation

    owner, _ = _make_user("user")
    stranger, stranger_headers = _make_user("user")
    with SessionLocal() as db:
        conversation = create_conversation(db, principal_from_user(owner).owner_id, title="private")

    response = client.get(f"/api/conversations/{conversation['id']}", headers=stranger_headers)

    assert response.status_code == 404
    assert stranger.id != owner.id


def test_inactive_user_forbidden(client):
    from database.db import SessionLocal
    from database.models import User

    user, headers = _make_user("developer")
    with SessionLocal() as db:
        target = db.get(User, user.id)
        target.is_active = False
        db.commit()

    response = client.get("/api/evaluation/registry", headers=headers)

    assert response.status_code == 401


def test_permission_backend_enforced(client):
    from auth.service import _b64encode, _jwt_sign

    user, _ = _make_user("user")
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8"))
    payload = _b64encode(
        json.dumps(
            {
                "sub": user.id,
                "role": "admin",
                "iat": int(datetime.now(timezone.utc).timestamp()),
                "exp": int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
                "nonce": uuid.uuid4().hex,
            },
            separators=(",", ":"),
        ).encode("utf-8")
    )
    signing_input = f"{header}.{payload}"
    forged_token = f"{signing_input}.{_jwt_sign(signing_input)}"

    response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {forged_token}"})

    assert response.status_code == 403


def test_frontend_route_guard():
    project_root = Path(__file__).resolve().parents[2]
    app_source = (project_root / "frontend" / "src" / "App.tsx").read_text(encoding="utf-8")
    guard_source = (project_root / "frontend" / "src" / "components" / "ProtectedRoute.tsx").read_text(
        encoding="utf-8"
    )

    assert "PermissionRoute" in app_source
    assert "Permission.KNOWLEDGE_REVIEW" in app_source
    assert "Permission.USER_MANAGE" in app_source
    assert "AccessDenied" in guard_source
    assert 'role === "admin"' not in app_source


def test_api_key_never_exposed(client):
    admin, headers = _make_user("admin")
    response = client.get("/api/admin/system", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert set(body["secrets"]["ark_api_key"]) == {"configured", "masked"}
    raw_key = get_settings().ark_api_key.strip()
    if raw_key:
        assert raw_key not in json.dumps(body, ensure_ascii=False)
    assert admin.id


def test_audit_log_role_change(client):
    from database.db import SessionLocal
    from database.models import AdminAuditLog

    admin, headers = _make_user("admin")
    user, _ = _make_user("user")

    response = client.patch(f"/api/admin/users/{user.id}", json={"role": "developer"}, headers=headers)

    assert response.status_code == 200
    with SessionLocal() as db:
        row = (
            db.query(AdminAuditLog)
            .filter(AdminAuditLog.actor_user_id == admin.id, AdminAuditLog.target_id == user.id)
            .order_by(AdminAuditLog.created_at.desc())
            .first()
        )
    assert row is not None
    assert row.action == "user_updated"
    assert json.loads(row.metadata_json)["new_role"] == "developer"


def test_audit_log_kb_publish(client, monkeypatch):
    from database.db import SessionLocal
    from database.models import AdminAuditLog
    from routers import knowledge as knowledge_router

    async def fake_build_production_indexes(**_kwargs):
        return {"dry_run": True, "production_ready": True, "eligible_chunks": 1}

    monkeypatch.setattr(knowledge_router, "build_production_indexes", fake_build_production_indexes)
    admin, headers = _make_user("admin")

    response = client.post("/api/knowledge/production/publish", json={"dry_run": True}, headers=headers)

    assert response.status_code == 200
    with SessionLocal() as db:
        row = (
            db.query(AdminAuditLog)
            .filter(
                AdminAuditLog.actor_user_id == admin.id,
                AdminAuditLog.action == "production_kb_publish_dry_run",
            )
            .order_by(AdminAuditLog.created_at.desc())
            .first()
        )
    assert row is not None
    assert json.loads(row.metadata_json)["eligible_chunks"] == 1

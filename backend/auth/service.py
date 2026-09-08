from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from auth.permissions import Role, normalize_role
from config import get_settings
from database.models import AdminAuditLog, KnowledgeReviewAuditLog, User, utcnow
from schemas.errors import AppError


_RUNTIME_JWT_SECRET = secrets.token_urlsafe(32)
_PASSWORD_SCHEME = "pbkdf2_sha256"
_PASSWORD_ITERATIONS = 260_000


def _b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _b64decode(payload: str) -> bytes:
    padding = "=" * (-len(payload) % 4)
    return base64.urlsafe_b64decode(payload + padding)


def _jwt_secret() -> bytes:
    settings = get_settings()
    secret = settings.auth_jwt_secret or settings.public_session_secret or _RUNTIME_JWT_SECRET
    return secret.encode("utf-8")


def _jwt_sign(signing_input: str) -> str:
    digest = hmac.new(_jwt_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def hash_password(password: str) -> str:
    salt = secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PASSWORD_ITERATIONS,
    )
    return f"{_PASSWORD_SCHEME}${_PASSWORD_ITERATIONS}${salt}${_b64encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_text, salt, expected = password_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if scheme != _PASSWORD_SCHEME:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return hmac.compare_digest(_b64encode(digest), expected)


def create_jwt_for_user(user: User) -> tuple[str, datetime]:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=max(int(settings.auth_access_token_minutes), 5))
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.id,
        "role": normalize_role(user.role).value,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "nonce": secrets.token_urlsafe(10),
    }
    encoded_header = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}"
    return f"{signing_input}.{_jwt_sign(signing_input)}", expires_at


def decode_jwt(token: str | None) -> dict[str, Any] | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    encoded_header, encoded_payload, signature = parts
    signing_input = f"{encoded_header}.{encoded_payload}"
    if not hmac.compare_digest(_jwt_sign(signing_input), signature):
        return None
    try:
        header = json.loads(_b64decode(encoded_header).decode("utf-8"))
        payload = json.loads(_b64decode(encoded_payload).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if header.get("alg") != "HS256":
        return None
    if int(payload.get("exp", 0)) <= int(datetime.now(timezone.utc).timestamp()):
        return None
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        return None
    return payload


def get_user_by_identity(db: Session, username_or_email: str) -> User | None:
    identity = username_or_email.strip().lower()
    return (
        db.query(User)
        .filter(or_(User.username == username_or_email.strip(), User.email == identity))
        .first()
    )


def get_user_from_token(db: Session, token: str | None) -> User | None:
    payload = decode_jwt(token)
    if not payload:
        return None
    user = db.get(User, str(payload["sub"]))
    if not user or not user.is_active:
        return None
    return user


def create_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    role: Role | str = Role.USER,
    is_active: bool = True,
) -> User:
    clean_username = username.strip()
    clean_email = email.strip().lower()
    selected_role = normalize_role(role)
    if not clean_username:
        raise AppError("username_required", "用户名不能为空。", "auth", status_code=400)
    if "@" not in clean_email:
        raise AppError("email_invalid", "邮箱格式无效。", "auth", status_code=400)
    if len(password) < 8:
        raise AppError("password_too_short", "密码至少需要 8 位。", "auth", status_code=400)
    if get_user_by_identity(db, clean_username) or get_user_by_identity(db, clean_email):
        raise AppError("user_exists", "用户名或邮箱已存在。", "auth", status_code=409)
    user = User(
        id=uuid.uuid4().hex,
        username=clean_username,
        email=clean_email,
        password_hash=hash_password(password),
        role=selected_role.value,
        is_active=bool(is_active),
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username_or_email: str, password: str) -> User:
    user = get_user_by_identity(db, username_or_email)
    if not user or not verify_password(password, user.password_hash):
        raise AppError("invalid_credentials", "用户名/邮箱或密码不正确。", "auth", status_code=401)
    if not user.is_active:
        raise AppError("user_inactive", "该用户已被禁用。", "auth", status_code=403)
    return user


def count_active_admins(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.role == Role.ADMIN.value, User.is_active.is_(True))
        .count()
    )


def _would_remove_active_admin(target: User, *, role: Role | None, is_active: bool | None) -> bool:
    if normalize_role(target.role) != Role.ADMIN or not target.is_active:
        return False
    next_role = role or Role.ADMIN
    next_active = target.is_active if is_active is None else bool(is_active)
    return next_role != Role.ADMIN or not next_active


def ensure_not_last_admin(db: Session, target: User, *, role: Role | None = None, is_active: bool | None = None) -> None:
    if _would_remove_active_admin(target, role=role, is_active=is_active) and count_active_admins(db) <= 1:
        raise AppError(
            "last_admin_protected",
            "系统必须至少保留 1 个 active admin。",
            "admin_user_management",
            status_code=400,
        )


def log_admin_action(
    db: Session,
    *,
    actor_user_id: str,
    action: str,
    target_type: str,
    target_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> AdminAuditLog:
    row = AdminAuditLog(
        audit_id=uuid.uuid4().hex,
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
        created_at=utcnow(),
    )
    db.add(row)
    return row


def log_knowledge_review_action(
    db: Session,
    *,
    reviewer_user_id: str,
    action: str,
    source_id: str = "",
    chunk_id: str = "",
    previous_status: str = "",
    new_status: str = "",
    comment: str = "",
) -> KnowledgeReviewAuditLog:
    row = KnowledgeReviewAuditLog(
        log_id=uuid.uuid4().hex,
        reviewer_user_id=reviewer_user_id,
        action=action,
        source_id=source_id,
        chunk_id=chunk_id,
        previous_status=previous_status,
        new_status=new_status,
        comment=comment[:1000],
        created_at=utcnow(),
    )
    db.add(row)
    return row


def update_user_by_admin(
    db: Session,
    *,
    actor: User,
    target: User,
    role: Role | None = None,
    is_active: bool | None = None,
) -> User:
    ensure_not_last_admin(db, target, role=role, is_active=is_active)
    metadata: dict[str, Any] = {}
    if role is not None and normalize_role(target.role) != role:
        metadata["previous_role"] = target.role
        metadata["new_role"] = role.value
        target.role = role.value
    if is_active is not None and bool(target.is_active) != bool(is_active):
        metadata["previous_is_active"] = bool(target.is_active)
        metadata["new_is_active"] = bool(is_active)
        target.is_active = bool(is_active)
    target.updated_at = utcnow()
    if metadata:
        log_admin_action(
            db,
            actor_user_id=actor.id,
            action="user_updated",
            target_type="user",
            target_id=target.id,
            metadata=metadata,
        )
    db.commit()
    db.refresh(target)
    return target


def ensure_initial_admin(db: Session) -> User | None:
    settings = get_settings()
    username = settings.initial_admin_username.strip()
    email = settings.initial_admin_email.strip().lower()
    password = settings.initial_admin_password
    if not (username and email and password):
        return None
    existing = get_user_by_identity(db, username) or get_user_by_identity(db, email)
    if existing:
        return existing
    admin = create_user(
        db,
        username=username,
        email=email,
        password=password,
        role=Role.ADMIN,
        is_active=True,
    )
    log_admin_action(
        db,
        actor_user_id="system",
        action="initial_admin_created",
        target_type="user",
        target_id=admin.id,
        metadata={"source": "environment"},
    )
    db.commit()
    return admin

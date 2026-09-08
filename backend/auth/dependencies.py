from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from auth.permissions import Permission, Role, normalize_role, permissions_for_role
from auth.service import get_user_from_token
from config import get_settings
from database.db import get_db
from database.models import Conversation, User
from schemas.errors import AppError
from services.auth_service import current_access_session, hash_session_id
from services.conversation_service import normalize_owner_id


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CurrentPrincipal:
    id: str
    username: str
    email: str
    role: Role
    permissions: frozenset[Permission]
    owner_id: str
    is_active: bool = True
    auth_type: str = "user"
    user: User | None = None

    @property
    def is_database_user(self) -> bool:
        return self.user is not None and self.auth_type == "user"

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


def _bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def principal_from_user(user: User) -> CurrentPrincipal:
    role = normalize_role(user.role)
    return CurrentPrincipal(
        id=user.id,
        username=user.username,
        email=user.email,
        role=role,
        permissions=permissions_for_role(role),
        owner_id=normalize_owner_id(f"user:{user.id}"),
        is_active=bool(user.is_active),
        auth_type="user",
        user=user,
    )


def _log_denial(
    request: Request,
    *,
    status_code: int,
    code: str,
    required_permission: Permission | None = None,
    principal: CurrentPrincipal | None = None,
) -> None:
    logger.warning(
        "rbac_denied endpoint=%s user_id=%s role=%s required_permission=%s status=%s code=%s",
        request.url.path,
        principal.id if principal else "",
        principal.role.value if principal else "",
        required_permission.value if required_permission else "",
        status_code,
        code,
    )


def get_optional_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User | None:
    return get_user_from_token(db, _bearer_token(authorization))


def get_current_user(
    request: Request,
    user: User | None = Depends(get_optional_user),
) -> User:
    if not user:
        _log_denial(request, status_code=401, code="authentication_required")
        raise AppError(
            "authentication_required",
            "请先登录。",
            "auth",
            status_code=401,
        )
    return user


def get_current_principal(
    request: Request,
    user: User | None = Depends(get_optional_user),
    x_conversation_owner: str | None = Header(default=None),
) -> CurrentPrincipal | None:
    if user:
        return principal_from_user(user)

    access_session = current_access_session(request)
    if access_session:
        owner_hash = hash_session_id(str(access_session["sid"]))
        owner_id = normalize_owner_id(f"access:{owner_hash}")
        return CurrentPrincipal(
            id=owner_id,
            username="public-demo-user",
            email="",
            role=Role.USER,
            permissions=permissions_for_role(Role.USER),
            owner_id=owner_id,
            auth_type="public_access",
            user=None,
        )

    settings = get_settings()
    if settings.app_env == "development" and not settings.public_access_enabled:
        owner_id = normalize_owner_id(x_conversation_owner or "local")
        return CurrentPrincipal(
            id=owner_id,
            username="local-development-user",
            email="",
            role=Role.USER,
            permissions=permissions_for_role(Role.USER),
            owner_id=owner_id,
            auth_type="local_development",
            user=None,
        )

    return None


def require_principal(
    *,
    allow_demo_user: bool = False,
) -> Callable[[Request, CurrentPrincipal | None], CurrentPrincipal]:
    def dependency(
        request: Request,
        principal: CurrentPrincipal | None = Depends(get_current_principal),
    ) -> CurrentPrincipal:
        if not principal:
            _log_denial(request, status_code=401, code="authentication_required")
            raise AppError(
                "authentication_required",
                "请先登录。",
                "auth",
                status_code=401,
            )
        if not allow_demo_user and not principal.is_database_user:
            _log_denial(request, status_code=401, code="database_user_required", principal=principal)
            raise AppError(
                "database_user_required",
                "该操作需要登录用户账号。",
                "auth",
                status_code=401,
            )
        return principal

    return dependency


def require_permission(
    permission: Permission,
    *,
    allow_demo_user: bool = False,
) -> Callable[[Request, CurrentPrincipal | None], CurrentPrincipal]:
    def dependency(
        request: Request,
        principal: CurrentPrincipal | None = Depends(get_current_principal),
    ) -> CurrentPrincipal:
        if not principal:
            _log_denial(request, status_code=401, code="authentication_required", required_permission=permission)
            raise AppError(
                "authentication_required",
                "请先登录。",
                "auth",
                status_code=401,
            )
        if not allow_demo_user and not principal.is_database_user:
            _log_denial(request, status_code=401, code="database_user_required", required_permission=permission, principal=principal)
            raise AppError(
                "database_user_required",
                "该操作需要登录用户账号。",
                "auth",
                status_code=401,
            )
        if not principal.has_permission(permission):
            _log_denial(request, status_code=403, code="permission_forbidden", required_permission=permission, principal=principal)
            raise AppError(
                "permission_forbidden",
                "无权访问该功能。",
                "rbac",
                status_code=403,
            )
        return principal

    return dependency


def require_any_permission(
    *permissions: Permission,
    allow_demo_user: bool = False,
) -> Callable[[Request, CurrentPrincipal | None], CurrentPrincipal]:
    required = frozenset(permissions)

    def dependency(
        request: Request,
        principal: CurrentPrincipal | None = Depends(get_current_principal),
    ) -> CurrentPrincipal:
        if not principal:
            _log_denial(request, status_code=401, code="authentication_required")
            raise AppError("authentication_required", "请先登录。", "auth", status_code=401)
        if not allow_demo_user and not principal.is_database_user:
            _log_denial(request, status_code=401, code="database_user_required", principal=principal)
            raise AppError("database_user_required", "该操作需要登录用户账号。", "auth", status_code=401)
        if not (principal.permissions & required):
            first = next(iter(required), None)
            _log_denial(request, status_code=403, code="permission_forbidden", required_permission=first, principal=principal)
            raise AppError("permission_forbidden", "无权访问该功能。", "rbac", status_code=403)
        return principal

    return dependency


def sanitize_chat_payload_for_principal(payload: dict[str, Any], principal: CurrentPrincipal) -> dict[str, Any]:
    sanitized = dict(payload)
    if not principal.has_permission(Permission.AGENT_TRACE_VIEW):
        sanitized["agent_trace"] = []
        sanitized["psychological_state"] = {}
        sanitized["strategy_plan"] = {}
        sanitized["request_metrics"] = {}
        risk = sanitized.get("risk")
        if isinstance(risk, dict):
            sanitized["risk"] = {
                "level": risk.get("level", "low"),
                "reason": "已完成安全检查。",
                "action": risk.get("action", "继续支持"),
            }
    if not principal.has_permission(Permission.RAG_DEBUG_VIEW):
        sanitized["knowledge_sources"] = []
        sanitized["retrieval"] = {}
        sanitized["rag_route"] = {}
        sanitized["provider_metadata"] = {}
    return sanitized


def sanitize_message_metadata(metadata: dict[str, Any], principal: CurrentPrincipal) -> dict[str, Any]:
    sanitized = dict(metadata)
    if not principal.has_permission(Permission.AGENT_TRACE_VIEW):
        sanitized.pop("agent_trace", None)
        sanitized.pop("psychological_state", None)
        sanitized.pop("strategy_plan", None)
        sanitized.pop("request_metrics", None)
        risk = sanitized.get("risk")
        if isinstance(risk, dict):
            sanitized["risk"] = {
                "level": risk.get("level", "low"),
                "reason": "已完成安全检查。",
                "action": risk.get("action", "继续支持"),
            }
    if not principal.has_permission(Permission.RAG_DEBUG_VIEW):
        sanitized.pop("knowledge_sources", None)
        sanitized.pop("retrieval", None)
        sanitized.pop("rag_route", None)
        sanitized.pop("provider_metadata", None)
    return sanitized


def sanitize_conversation_payload(payload: dict[str, Any], principal: CurrentPrincipal) -> dict[str, Any]:
    sanitized = dict(payload)
    if "messages" in sanitized and isinstance(sanitized["messages"], list):
        messages = []
        for message in sanitized["messages"]:
            if isinstance(message, dict) and isinstance(message.get("metadata"), dict):
                messages.append({**message, "metadata": sanitize_message_metadata(message["metadata"], principal)})
            else:
                messages.append(message)
        sanitized["messages"] = messages
    if "assistant_message" in sanitized and isinstance(sanitized["assistant_message"], dict):
        message = sanitized["assistant_message"]
        if isinstance(message.get("metadata"), dict):
            sanitized["assistant_message"] = {
                **message,
                "metadata": sanitize_message_metadata(message["metadata"], principal),
            }
    if "result" in sanitized and isinstance(sanitized["result"], dict):
        sanitized["result"] = sanitize_chat_payload_for_principal(sanitized["result"], principal)
    return sanitized


def ensure_own_conversation(db: Session, conversation_id: str, principal: CurrentPrincipal) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.owner_id != principal.owner_id or conversation.is_archived:
        raise AppError(
            "conversation_not_found",
            "对话不存在或无权访问。",
            "conversation_lookup",
            status_code=404,
        )
    return conversation

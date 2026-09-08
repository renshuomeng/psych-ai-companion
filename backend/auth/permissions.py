from __future__ import annotations

from enum import Enum


class Role(str, Enum):
    USER = "user"
    REVIEWER = "reviewer"
    DEVELOPER = "developer"
    ADMIN = "admin"


class Permission(str, Enum):
    CHAT_USE = "CHAT_USE"
    MULTIMODAL_USE = "MULTIMODAL_USE"
    CONVERSATION_READ_OWN = "CONVERSATION_READ_OWN"
    CONVERSATION_DELETE_OWN = "CONVERSATION_DELETE_OWN"
    SETTINGS_VIEW_OWN = "SETTINGS_VIEW_OWN"

    KNOWLEDGE_VIEW = "KNOWLEDGE_VIEW"
    KNOWLEDGE_REVIEW = "KNOWLEDGE_REVIEW"
    KNOWLEDGE_SOURCE_APPROVE = "KNOWLEDGE_SOURCE_APPROVE"
    KNOWLEDGE_CHUNK_APPROVE = "KNOWLEDGE_CHUNK_APPROVE"

    EVALUATION_VIEW = "EVALUATION_VIEW"
    EVALUATION_REVIEW = "EVALUATION_REVIEW"
    EVALUATION_HUMAN_SCORE = "EVALUATION_HUMAN_SCORE"
    EVALUATION_EXPORT_HUMAN_REVIEW = "EVALUATION_EXPORT_HUMAN_REVIEW"
    EVALUATION_RUN_CREATE = "EVALUATION_RUN_CREATE"
    EVALUATION_RUN_FULL = "EVALUATION_RUN_FULL"
    EVALUATION_COMPARE = "EVALUATION_COMPARE"

    AGENT_TRACE_VIEW = "AGENT_TRACE_VIEW"
    RAG_DEBUG_VIEW = "RAG_DEBUG_VIEW"
    RAG_BENCHMARK_RUN = "RAG_BENCHMARK_RUN"
    BENCHMARK_VIEW = "BENCHMARK_VIEW"
    ABLATION_RUN = "ABLATION_RUN"

    DEV_CONFIG_EDIT = "DEV_CONFIG_EDIT"
    DEV_PROMPT_EDIT = "DEV_PROMPT_EDIT"
    PRODUCTION_PROMPT_PREPARE = "PRODUCTION_PROMPT_PREPARE"
    PRODUCTION_CONFIG_EDIT = "PRODUCTION_CONFIG_EDIT"
    MODEL_SWITCH_DEVELOPMENT = "MODEL_SWITCH_DEVELOPMENT"
    MODEL_SWITCH_PRODUCTION = "MODEL_SWITCH_PRODUCTION"

    PRODUCTION_KB_PUBLISH = "PRODUCTION_KB_PUBLISH"
    PRODUCTION_KB_ROLLBACK = "PRODUCTION_KB_ROLLBACK"

    USER_MANAGE = "USER_MANAGE"
    ROLE_MANAGE = "ROLE_MANAGE"
    SECRET_STATUS_VIEW = "SECRET_STATUS_VIEW"


USER_PERMISSIONS: frozenset[Permission] = frozenset(
    {
        Permission.CHAT_USE,
        Permission.MULTIMODAL_USE,
        Permission.CONVERSATION_READ_OWN,
        Permission.CONVERSATION_DELETE_OWN,
        Permission.SETTINGS_VIEW_OWN,
    }
)

REVIEWER_PERMISSIONS: frozenset[Permission] = USER_PERMISSIONS | frozenset(
    {
        Permission.KNOWLEDGE_VIEW,
        Permission.KNOWLEDGE_REVIEW,
        Permission.KNOWLEDGE_SOURCE_APPROVE,
        Permission.KNOWLEDGE_CHUNK_APPROVE,
        Permission.EVALUATION_VIEW,
        Permission.EVALUATION_REVIEW,
        Permission.EVALUATION_HUMAN_SCORE,
        Permission.EVALUATION_EXPORT_HUMAN_REVIEW,
        Permission.BENCHMARK_VIEW,
    }
)

DEVELOPER_PERMISSIONS: frozenset[Permission] = USER_PERMISSIONS | frozenset(
    {
        Permission.KNOWLEDGE_VIEW,
        Permission.EVALUATION_VIEW,
        Permission.EVALUATION_RUN_CREATE,
        Permission.EVALUATION_RUN_FULL,
        Permission.EVALUATION_COMPARE,
        Permission.AGENT_TRACE_VIEW,
        Permission.RAG_DEBUG_VIEW,
        Permission.RAG_BENCHMARK_RUN,
        Permission.BENCHMARK_VIEW,
        Permission.ABLATION_RUN,
        Permission.DEV_CONFIG_EDIT,
        Permission.DEV_PROMPT_EDIT,
        Permission.PRODUCTION_PROMPT_PREPARE,
        Permission.MODEL_SWITCH_DEVELOPMENT,
    }
)

ADMIN_PERMISSIONS: frozenset[Permission] = REVIEWER_PERMISSIONS | DEVELOPER_PERMISSIONS | frozenset(
    {
        Permission.PRODUCTION_CONFIG_EDIT,
        Permission.MODEL_SWITCH_PRODUCTION,
        Permission.PRODUCTION_KB_PUBLISH,
        Permission.PRODUCTION_KB_ROLLBACK,
        Permission.USER_MANAGE,
        Permission.ROLE_MANAGE,
        Permission.SECRET_STATUS_VIEW,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.USER: USER_PERMISSIONS,
    Role.REVIEWER: REVIEWER_PERMISSIONS,
    Role.DEVELOPER: DEVELOPER_PERMISSIONS,
    Role.ADMIN: ADMIN_PERMISSIONS,
}


def normalize_role(value: str | Role | None) -> Role:
    try:
        return value if isinstance(value, Role) else Role(str(value or Role.USER.value).strip().lower())
    except ValueError:
        return Role.USER


def permissions_for_role(role: str | Role | None) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[normalize_role(role)]


def permission_values_for_role(role: str | Role | None) -> list[str]:
    return sorted(permission.value for permission in permissions_for_role(role))


def has_permission(role: str | Role | None, permission: Permission) -> bool:
    return permission in permissions_for_role(role)


def role_values() -> list[str]:
    return [role.value for role in Role]

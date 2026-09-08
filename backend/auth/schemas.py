from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from auth.permissions import Role, normalize_role, permission_values_for_role
from database.models import User


class UserPublic(BaseModel):
    id: str
    username: str
    email: str
    role: Role
    is_active: bool
    permissions: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=256)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("email must contain @")
        return normalized


class LoginRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: UserPublic


class MeResponse(BaseModel):
    authenticated: bool
    user: UserPublic | None = None
    auth_type: str = "none"


class AdminUserCreateRequest(RegisterRequest):
    role: Role = Role.USER
    is_active: bool = True


class AdminUserUpdateRequest(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


def user_to_public(user: User) -> UserPublic:
    role = normalize_role(user.role)
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        role=role,
        is_active=bool(user.is_active),
        permissions=permission_values_for_role(role),
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def synthetic_user_to_public(
    *,
    user_id: str,
    username: str,
    email: str = "",
    role: Role = Role.USER,
) -> UserPublic:
    return UserPublic(
        id=user_id,
        username=username,
        email=email,
        role=role,
        is_active=True,
        permissions=permission_values_for_role(role),
        created_at=None,
        updated_at=None,
    )

import secrets

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from auth.dependencies import CurrentPrincipal, get_current_principal
from auth.permissions import Role
from auth.schemas import (
    AuthTokenResponse,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    synthetic_user_to_public,
    user_to_public,
)
from auth.service import authenticate_user, create_jwt_for_user, create_user
from config import get_settings
from database.db import get_db
from schemas.errors import AppError
from services.auth_service import (
    ACCESS_COOKIE_NAME,
    cookie_secure_for_request,
    create_access_token,
    current_access_session,
    session_expires_at_timestamp,
    timestamp_to_iso,
)


router = APIRouter()


class AccessRequest(BaseModel):
    access_code: str = Field(min_length=1, max_length=128)


@router.post("/register", response_model=AuthTokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = create_user(
        db,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        role=Role.USER,
    )
    token, expires_at = create_jwt_for_user(user)
    return AuthTokenResponse(access_token=token, expires_at=expires_at, user=user_to_public(user))


@router.post("/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = authenticate_user(db, payload.username_or_email, payload.password)
    token, expires_at = create_jwt_for_user(user)
    return AuthTokenResponse(access_token=token, expires_at=expires_at, user=user_to_public(user))


@router.get("/me", response_model=MeResponse)
def me(principal: CurrentPrincipal | None = Depends(get_current_principal)) -> MeResponse:
    if not principal:
        return MeResponse(authenticated=False, user=None)
    if principal.user:
        return MeResponse(authenticated=True, user=user_to_public(principal.user), auth_type=principal.auth_type)
    return MeResponse(
        authenticated=True,
        auth_type=principal.auth_type,
        user=synthetic_user_to_public(
            user_id=principal.id,
            username=principal.username,
            email=principal.email,
            role=principal.role,
        ),
    )


@router.get("/session")
def get_session(request: Request) -> dict[str, object]:
    settings = get_settings()
    if not settings.public_access_enabled:
        return {
            "authenticated": True,
            "access_required": False,
            "expires_at": None,
        }

    session = current_access_session(request)
    return {
        "authenticated": session is not None,
        "access_required": True,
        "expires_at": timestamp_to_iso(int(session["exp"])) if session else None,
    }


@router.post("/access")
def grant_access(payload: AccessRequest, request: Request, response: Response) -> dict[str, object]:
    settings = get_settings()
    if not settings.public_access_enabled:
        return {
            "authenticated": True,
            "access_required": False,
            "expires_at": None,
        }
    if not settings.public_access_code:
        raise AppError(
            "access_code_not_configured",
            "演示访问码尚未在后端配置。",
            "public_access",
            status_code=503,
        )
    if not secrets.compare_digest(payload.access_code, settings.public_access_code):
        raise AppError(
            "invalid_access_code",
            "访问码不正确，请确认后再试。",
            "public_access",
            status_code=401,
        )

    expires_at = session_expires_at_timestamp()
    token = create_access_token(secrets.token_urlsafe(16), expires_at)
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=cookie_secure_for_request(request),
        samesite="lax",
        max_age=settings.public_session_hours * 3600,
        path="/",
    )
    return {
        "authenticated": True,
        "access_required": True,
        "expires_at": timestamp_to_iso(expires_at),
    }


@router.post("/logout")
def logout(response: Response) -> dict[str, object]:
    response.delete_cookie(ACCESS_COOKIE_NAME, path="/")
    return {"authenticated": False, "access_required": get_settings().public_access_enabled}

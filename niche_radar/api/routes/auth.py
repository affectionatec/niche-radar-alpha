"""Application login, logout, and current-session endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from niche_radar.api.auth import (
    AuthConfigurationError,
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    client_identity,
    get_auth_service,
    login_rate_limiter,
)
from niche_radar.config import get_settings


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=1024)


class SessionUser(BaseModel):
    username: str


def _service_or_503():
    try:
        return get_auth_service()
    except AuthConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="Authentication is unavailable",
            headers={"Retry-After": "60"},
        ) from exc


@router.post("/login", response_model=SessionUser)
def login(payload: LoginRequest, request: Request, response: Response) -> SessionUser:
    if not get_settings().is_production:
        return SessionUser(username="local-development")

    identity = client_identity(request)
    retry_after = login_rate_limiter.retry_after(identity)
    if retry_after is not None:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    service = _service_or_503()
    if not service.verify_credentials(payload.username, payload.password):
        login_rate_limiter.record_failure(identity)
        raise HTTPException(status_code=401, detail="Invalid username or password")

    login_rate_limiter.clear(identity)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        service.issue_session(),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )
    return SessionUser(username=service.username)


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


@router.get("/me", response_model=SessionUser)
def me(request: Request) -> SessionUser:
    if not get_settings().is_production:
        return SessionUser(username="local-development")
    return SessionUser(username=request.state.auth_username)

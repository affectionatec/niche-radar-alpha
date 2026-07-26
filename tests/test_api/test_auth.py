import re

import pytest
from fastapi.testclient import TestClient

from niche_radar.api import auth
from niche_radar.api.auth import (
    AuthConfigurationError,
    AuthService,
    LoginRateLimiter,
    SESSION_COOKIE_NAME,
    get_auth_service,
    login_rate_limiter,
)
from niche_radar.api.server import app
from niche_radar.config import get_settings


@pytest.fixture
def production_client(tmp_path, monkeypatch):
    credentials = tmp_path / "credentials"
    session = tmp_path / "session"
    credentials.write_text("operator:correct-password\n", encoding="utf-8")
    session.write_bytes(b"s" * 32)

    monkeypatch.setattr(auth, "CREDENTIALS_PATH", credentials)
    monkeypatch.setattr(auth, "SESSION_SECRET_PATH", session)
    monkeypatch.setattr(get_settings(), "app_environment", "production")
    get_auth_service.cache_clear()
    login_rate_limiter.clear()
    with TestClient(app, base_url="https://radar.test") as client:
        yield client
    get_auth_service.cache_clear()
    login_rate_limiter.clear()


def login(client: TestClient):
    return client.post(
        "/api/auth/login",
        json={"username": "operator", "password": "correct-password"},
    )


def test_missing_secret_fails_closed(tmp_path):
    with pytest.raises(AuthConfigurationError):
        AuthService.from_secret_files(
            tmp_path / "missing-credentials",
            tmp_path / "missing-session",
        )


def test_missing_production_secrets_return_safe_503(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "CREDENTIALS_PATH", tmp_path / "missing-credentials")
    monkeypatch.setattr(auth, "SESSION_SECRET_PATH", tmp_path / "missing-session")
    monkeypatch.setattr(get_settings(), "app_environment", "production")
    get_auth_service.cache_clear()
    try:
        with TestClient(app, base_url="https://radar.test") as client:
            login_response = client.post(
                "/api/auth/login",
                json={"username": "operator", "password": "irrelevant"},
            )
            protected_response = client.get("/api/settings")
        assert login_response.status_code == 503
        assert protected_response.status_code == 503
        assert login_response.json()["detail"] == "Authentication is unavailable"
        assert protected_response.json()["detail"] == "Authentication is unavailable"
        assert str(tmp_path) not in login_response.text
        assert str(tmp_path) not in protected_response.text
    finally:
        get_auth_service.cache_clear()


@pytest.mark.parametrize("record", ["", "operator", ":password", "operator:", "a:b\nc:d"])
def test_invalid_credential_record_fails_closed(tmp_path, record):
    credentials = tmp_path / "credentials"
    session = tmp_path / "session"
    credentials.write_text(record, encoding="utf-8")
    session.write_bytes(b"s" * 32)
    with pytest.raises(AuthConfigurationError):
        AuthService.from_secret_files(credentials, session)


def test_short_signing_secret_fails_closed(tmp_path):
    credentials = tmp_path / "credentials"
    session = tmp_path / "session"
    credentials.write_text("operator:password", encoding="utf-8")
    session.write_bytes(b"short")
    with pytest.raises(AuthConfigurationError):
        AuthService.from_secret_files(credentials, session)


def test_status_and_login_are_public(production_client):
    assert production_client.get("/api/status").status_code == 200
    assert login(production_client).status_code == 200


def test_every_other_api_operation_requires_session(production_client):
    public = {("/api/status", "get"), ("/api/auth/login", "post")}
    methods = {"get", "post", "put", "patch", "delete"}
    checked = 0
    for path, operations in app.openapi()["paths"].items():
        concrete_path = re.sub(r"\{[^}]+\}", "1", path)
        for method in methods.intersection(operations):
            if (path, method) in public:
                continue
            response = production_client.request(method.upper(), concrete_path)
            assert response.status_code == 401, (
                f"{method.upper()} {path} returned {response.status_code}"
            )
            checked += 1
    assert checked >= 25
    assert production_client.head("/api/status").status_code == 401
    assert production_client.options("/api/settings").status_code == 401
    assert production_client.get("/docs").status_code == 401


def test_login_sets_host_only_secure_cookie(production_client):
    response = login(production_client)
    cookie = response.headers["set-cookie"]
    assert f"{SESSION_COOKIE_NAME}=" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie
    assert production_client.get("/api/auth/me").json()["username"] == "operator"


def test_bad_credentials_return_generic_error(production_client):
    response = production_client.post(
        "/api/auth/login",
        json={"username": "someone", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"
    assert "set-cookie" not in response.headers


def test_logout_clears_cookie(production_client):
    assert login(production_client).status_code == 200
    response = production_client.post("/api/auth/logout")
    assert response.status_code == 204
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert production_client.get("/api/settings").status_code == 401


def test_tampered_expired_and_future_tokens_are_rejected():
    service = AuthService("operator", "password", b"s" * 32)
    token = service.issue_session(now=1_000)
    assert service.verify_session(token, now=1_001) == "operator"
    assert service.verify_session(f"{token}x", now=1_001) is None
    assert service.verify_session(token, now=1_000 + 8 * 60 * 60) is None
    future = service.issue_session(now=2_000)
    assert service.verify_session(future, now=1_000) is None


@pytest.mark.parametrize(
    "token",
    ["not-a-token", ".", "%%%.signature", "payload.%%%", "a.b.c"],
)
def test_malformed_tokens_are_rejected(production_client, token):
    response = production_client.get(
        "/api/settings",
        headers={"cookie": f"{SESSION_COOKIE_NAME}={token}"},
    )
    assert response.status_code == 401


def test_signing_secret_rotation_invalidates_sessions():
    original = AuthService("operator", "password", b"a" * 32)
    rotated = AuthService("operator", "password", b"b" * 32)
    assert rotated.verify_session(original.issue_session(now=1_000), now=1_001) is None


def test_five_failures_throttle_client(production_client):
    for _ in range(5):
        assert production_client.post(
            "/api/auth/login",
            json={"username": "operator", "password": "wrong"},
        ).status_code == 401
    blocked = login(production_client)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1


def test_rate_limit_isolated_between_forwarded_clients(production_client):
    blocked_ip = {
        "x-forwarded-for": "198.51.100.99, 203.0.113.30, 173.245.48.1"
    }
    other_ip = {"x-forwarded-for": "203.0.113.31, 173.245.48.1"}
    for _ in range(5):
        assert production_client.post(
            "/api/auth/login",
            headers=blocked_ip,
            json={"username": "operator", "password": "wrong"},
        ).status_code == 401
    assert production_client.post(
        "/api/auth/login",
        headers=blocked_ip,
        json={"username": "operator", "password": "correct-password"},
    ).status_code == 429
    assert production_client.post(
        "/api/auth/login",
        headers=other_ip,
        json={"username": "operator", "password": "correct-password"},
    ).status_code == 200
    assert "203.0.113.30" in login_rate_limiter._failures
    assert "198.51.100.99" not in login_rate_limiter._failures


def test_rate_limiter_has_bounded_key_count():
    limiter = LoginRateLimiter(max_failures=1, window_seconds=60, max_keys=3)
    for index in range(10):
        limiter.record_failure(f"client-{index}", now=float(index))
    assert len(limiter._failures) == 3


def test_development_mode_preserves_local_workflow(monkeypatch):
    monkeypatch.setattr(get_settings(), "app_environment", "development")
    with TestClient(app) as client:
        assert client.get("/api/settings").status_code == 200
        assert client.get("/api/auth/me").json()["username"] == "local-development"

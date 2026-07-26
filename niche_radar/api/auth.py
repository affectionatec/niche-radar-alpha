"""Single-operator authentication backed by fixed Docker secret files."""

from __future__ import annotations

import base64
from collections import OrderedDict, deque
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import hmac
import ipaddress
import json
from pathlib import Path
import secrets
import threading
import time
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from niche_radar.config import get_settings


CREDENTIALS_PATH = Path("/run/secrets/apps_login_credentials")
SESSION_SECRET_PATH = Path("/run/secrets/apps_session_secret")
SESSION_COOKIE_NAME = "__Host-niche_radar_session"
SESSION_TTL_SECONDS = 8 * 60 * 60
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_MAX_FAILURES = 5
_TRUSTED_PROXY_NETWORKS = tuple(
    ipaddress.ip_network(value)
    for value in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
        "173.245.48.0/20",
        "103.21.244.0/22",
        "103.22.200.0/22",
        "103.31.4.0/22",
        "141.101.64.0/18",
        "108.162.192.0/18",
        "190.93.240.0/20",
        "188.114.96.0/20",
        "197.234.240.0/22",
        "198.41.128.0/17",
        "162.158.0.0/15",
        "104.16.0.0/13",
        "104.24.0.0/14",
        "172.64.0.0/13",
        "131.0.72.0/22",
        "2400:cb00::/32",
        "2606:4700::/32",
        "2803:f800::/32",
        "2405:b500::/32",
        "2405:8100::/32",
        "2a06:98c0::/29",
        "2c0f:f248::/32",
    )
)

_PUBLIC_ENDPOINTS = frozenset(
    {
        ("GET", "/api/status"),
        ("POST", "/api/auth/login"),
    }
)


class AuthConfigurationError(RuntimeError):
    """Required production auth secrets are missing or invalid."""


def _read_secret(path: Path, label: str) -> bytes:
    try:
        value = path.read_bytes().rstrip(b"\r\n")
    except OSError as exc:
        raise AuthConfigurationError(f"{label} secret is unavailable") from exc
    if not value:
        raise AuthConfigurationError(f"{label} secret is empty")
    return value


def _urlsafe_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _urlsafe_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def _constant_time_text_equal(left: str, right: str) -> bool:
    return hmac.compare_digest(
        hashlib.sha256(left.encode("utf-8")).digest(),
        hashlib.sha256(right.encode("utf-8")).digest(),
    )


@dataclass(frozen=True)
class AuthService:
    username: str
    password: str
    session_secret: bytes

    @classmethod
    def from_secret_files(
        cls,
        credentials_path: Path = CREDENTIALS_PATH,
        session_secret_path: Path = SESSION_SECRET_PATH,
    ) -> AuthService:
        credential_bytes = _read_secret(credentials_path, "credentials")
        if b"\n" in credential_bytes or b"\r" in credential_bytes:
            raise AuthConfigurationError(
                "credentials secret must contain exactly one username:password record"
            )
        try:
            credential_text = credential_bytes.decode("utf-8")
            username, password = credential_text.split(":", 1)
        except (UnicodeDecodeError, ValueError) as exc:
            raise AuthConfigurationError(
                "credentials secret must use username:password format"
            ) from exc
        if not username or not password:
            raise AuthConfigurationError("username and password must both be non-empty")

        session_secret = _read_secret(session_secret_path, "session signing")
        if len(session_secret) < 32:
            raise AuthConfigurationError(
                "session signing secret must contain at least 32 bytes"
            )
        return cls(
            username=username,
            password=password,
            session_secret=session_secret,
        )

    def verify_credentials(self, username: str, password: str) -> bool:
        username_matches = _constant_time_text_equal(username, self.username)
        password_matches = _constant_time_text_equal(password, self.password)
        return bool(username_matches & password_matches)

    def issue_session(self, *, now: int | None = None) -> str:
        issued_at = int(time.time()) if now is None else now
        payload = {
            "sub": self.username,
            "iat": issued_at,
            "exp": issued_at + SESSION_TTL_SECONDS,
            "nonce": secrets.token_urlsafe(18),
        }
        body = _urlsafe_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = hmac.new(
            self.session_secret,
            body.encode("ascii"),
            hashlib.sha256,
        ).digest()
        return f"{body}.{_urlsafe_encode(signature)}"

    def verify_session(self, token: str, *, now: int | None = None) -> str | None:
        if not token or len(token) > 4096 or token.count(".") != 1:
            return None
        body, signature_text = token.split(".", 1)
        try:
            supplied_signature = _urlsafe_decode(signature_text)
            expected_signature = hmac.new(
                self.session_secret,
                body.encode("ascii"),
                hashlib.sha256,
            ).digest()
        except (ValueError, UnicodeError):
            return None
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None

        try:
            payload: Any = json.loads(_urlsafe_decode(body))
            subject = payload["sub"]
            issued_at = payload["iat"]
            expires_at = payload["exp"]
            nonce = payload["nonce"]
        except (ValueError, UnicodeError, KeyError, TypeError, json.JSONDecodeError):
            return None
        if (
            not isinstance(subject, str)
            or not isinstance(issued_at, int)
            or not isinstance(expires_at, int)
            or not isinstance(nonce, str)
            or not nonce
        ):
            return None

        current = int(time.time()) if now is None else now
        if (
            issued_at > current + 60
            or expires_at <= current
            or expires_at != issued_at + SESSION_TTL_SECONDS
            or not _constant_time_text_equal(subject, self.username)
        ):
            return None
        return self.username


@lru_cache(maxsize=1)
def get_auth_service() -> AuthService:
    return AuthService.from_secret_files(CREDENTIALS_PATH, SESSION_SECRET_PATH)


class LoginRateLimiter:
    """Bounded in-memory failed-login limiter."""

    def __init__(
        self,
        *,
        max_failures: int = LOGIN_MAX_FAILURES,
        window_seconds: int = LOGIN_WINDOW_SECONDS,
        max_keys: int = 4096,
    ) -> None:
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._failures: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def retry_after(self, key: str, *, now: float | None = None) -> int | None:
        current = time.monotonic() if now is None else now
        with self._lock:
            failures = self._active(key, current)
            if len(failures) < self._max_failures:
                return None
            return max(
                1,
                int(self._window_seconds - (current - failures[0]) + 0.999),
            )

    def record_failure(self, key: str, *, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        with self._lock:
            failures = self._active(key, current)
            failures.append(current)
            self._failures[key] = failures
            self._failures.move_to_end(key)
            while len(self._failures) > self._max_keys:
                self._failures.popitem(last=False)

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._failures.clear()
            else:
                self._failures.pop(key, None)

    def _active(self, key: str, now: float) -> deque[float]:
        failures = self._failures.get(key, deque())
        cutoff = now - self._window_seconds
        while failures and failures[0] <= cutoff:
            failures.popleft()
        if failures:
            self._failures[key] = failures
            self._failures.move_to_end(key)
        else:
            self._failures.pop(key, None)
        return failures


login_rate_limiter = LoginRateLimiter()


def client_identity(request: Request) -> str:
    """Resolve the first untrusted address to the left of trusted proxies."""
    addresses: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for value in request.headers.get("x-forwarded-for", "").split(",")[-16:]:
        try:
            addresses.append(ipaddress.ip_address(value.strip()))
        except ValueError:
            continue
    peer = request.client.host[:128] if request.client else "unknown"
    try:
        addresses.append(ipaddress.ip_address(peer))
    except ValueError:
        pass
    for address in reversed(addresses):
        if not any(address in network for network in _TRUSTED_PROXY_NETWORKS):
            return address.compressed
    return peer


def clear_session_cookie(response: JSONResponse) -> None:
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )


class SessionAuthMiddleware:
    """Fail closed before routing every non-public production request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not get_settings().is_production:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        path = scope.get("path", "")
        if (method, path) in _PUBLIC_ENDPOINTS:
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        try:
            service = get_auth_service()
        except AuthConfigurationError:
            response = JSONResponse(
                {"detail": "Authentication is unavailable"},
                status_code=503,
                headers={"Retry-After": "60"},
            )
            await response(scope, receive, send)
            return

        token = request.cookies.get(SESSION_COOKIE_NAME, "")
        username = service.verify_session(token)
        if username is None:
            response = JSONResponse(
                {"detail": "Authentication required"},
                status_code=401,
            )
            if token:
                clear_session_cookie(response)
            await response(scope, receive, send)
            return

        scope.setdefault("state", {})["auth_username"] = username
        await self.app(scope, receive, send)

"""Resilient HTTP helper shared by collectors and source backends.

Ports the durability policies from the ``last30days`` engine's ``lib/http.py``
into Niche Radar, built on ``requests`` so it matches the rest of the
collector layer (and its ``responses``-based tests):

- Exponential backoff on transient transport errors.
- A *separate*, smaller retry budget for HTTP 429 so a rate-limit storm does
  not exhaust the whole retry allowance.
- A dedicated minimum attempt count for DNS / connection failures, which are
  usually transient and clear after a brief backoff.
- Secret redaction: ``key`` / ``api_key`` / ``token`` / ``secret`` query
  params are scrubbed before anything is logged.

Collectors that need bespoke behaviour can still use ``requests`` directly;
this helper is for the common "GET/POST JSON with sane retries" case.
"""

from __future__ import annotations

import re
import time
from typing import Any

import requests
import structlog

logger = structlog.get_logger()

DEFAULT_TIMEOUT = 30
MAX_RETRIES = 4
MAX_429_RETRIES = 2
MIN_TRANSPORT_RETRIES = 3  # DNS / connection errors are usually transient
RETRY_BACKOFF_BASE = 2.0
USER_AGENT = "niche-radar/0.1 (+collectors)"

_SECRET_RE = re.compile(r"([?&])(key|api_key|apikey|token|secret|access_token)=[^&]*", re.IGNORECASE)


class HTTPError(Exception):
    """HTTP request failure carrying the status code and (truncated) body."""

    def __init__(self, message: str, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def redact(url: str) -> str:
    """Mask secret query-string values so URLs are safe to log."""
    return _SECRET_RE.sub(r"\1\2=***", url)


def request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: Any = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = MAX_RETRIES,
    max_429_retries: int = MAX_429_RETRIES,
    raw: bool = False,
) -> Any:
    """Perform an HTTP request with resilient retries.

    Returns parsed JSON (``dict``/``list``) by default, or the raw response
    text when ``raw=True``. Raises :class:`HTTPError` once the retry budget is
    exhausted or on a non-retryable 4xx (other than 429).
    """
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    safe_url = redact(url)

    last_error: Exception | None = None
    rate_limit_hits = 0
    transport_failures = 0
    # DNS/connection errors get at least MIN_TRANSPORT_RETRIES attempts even if
    # the caller asked for fewer, mirroring last30days' DNS-backoff policy.
    effective_retries = retries
    attempt = 0

    while attempt < effective_retries:
        try:
            resp = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                data=data,
                timeout=timeout,
            )
            status = resp.status_code

            if status == 429:
                rate_limit_hits += 1
                if rate_limit_hits > max_429_retries:
                    raise HTTPError(
                        f"Rate limited after {max_429_retries} retries: {safe_url}",
                        status_code=429,
                        body=resp.text[:200],
                    )
                delay = _retry_after(resp) or RETRY_BACKOFF_BASE ** rate_limit_hits
                logger.warning("http_rate_limited", url=safe_url, attempt=attempt + 1, delay_s=delay)
                time.sleep(delay)
                continue

            if 400 <= status < 600 and status not in (408, 425, 500, 502, 503, 504):
                # Non-retryable client error (or 5xx not worth retrying).
                raise HTTPError(
                    f"HTTP {status} for {safe_url}",
                    status_code=status,
                    body=resp.text[:500],
                )

            if status >= 500:
                last_error = HTTPError(f"HTTP {status} for {safe_url}", status_code=status, body=resp.text[:200])
                attempt += 1
                if attempt < effective_retries:
                    time.sleep(RETRY_BACKOFF_BASE ** attempt)
                continue

            return resp.text if raw else (resp.json() if resp.content else {})

        except (requests.ConnectionError, requests.Timeout) as exc:
            transport_failures += 1
            last_error = exc
            effective_retries = max(effective_retries, MIN_TRANSPORT_RETRIES)
            attempt += 1
            if attempt < effective_retries:
                delay = RETRY_BACKOFF_BASE ** attempt
                logger.warning("http_transport_retry", url=safe_url, attempt=attempt, delay_s=delay, error=str(exc))
                time.sleep(delay)
            continue
        except HTTPError:
            raise
        except requests.RequestException as exc:
            last_error = exc
            attempt += 1
            if attempt < effective_retries:
                time.sleep(RETRY_BACKOFF_BASE ** attempt)

    raise HTTPError(f"Request failed after {effective_retries} attempts: {safe_url} ({last_error})")


def _retry_after(resp: requests.Response) -> float | None:
    """Parse a ``Retry-After`` header (seconds form) if present."""
    val = resp.headers.get("Retry-After")
    if not val:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def get_json(url: str, **kwargs: Any) -> Any:
    """Convenience wrapper: ``request("GET", ...)`` returning parsed JSON."""
    return request("GET", url, **kwargs)


def post_json(url: str, **kwargs: Any) -> Any:
    """Convenience wrapper: ``request("POST", ...)`` returning parsed JSON."""
    return request("POST", url, **kwargs)

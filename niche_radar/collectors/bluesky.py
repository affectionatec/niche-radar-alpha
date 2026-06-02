"""Bluesky collector — pain-point search via the AT Protocol.

Mirrors the Twitter collector's model: run the same pain-point phrases through
Bluesky's ``searchPosts`` and normalize the results. Bluesky's authenticated
AppView (``api.bsky.app``) is used because the public mirror is Cloudflare-
blocked for search; that means a (free) app password is required, so the source
is credential-gated and skipped until configured.

Ported from last30days lib/bluesky.py. Create an app password at
https://bsky.app/settings/app-passwords.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog

from niche_radar.collectors import _http
from niche_radar.collectors.base import BaseCollector, CollectorResult
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

_SESSION_URL = "https://bsky.social/xrpc/com.atproto.server.createSession"
_SEARCH_URL = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
_PER_QUERY_LIMIT = 30
_INTER_QUERY_DELAY = 0.5

# Pain-point phrases, sans X-specific operators (no `-filter:`, no `*` wildcard).
DEFAULT_SEARCH_QUERIES = [
    "someone should build",
    "I wish there was",
    "is there a tool that",
    "still doing this manually",
    "we do this manually",
]


class BlueskyCollector(BaseCollector):
    source_name = "bluesky"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "bsky_handle",
            "label": "Bluesky handle",
            "secret": False,
            "optional": False,
            "help": "e.g. you.bsky.social",
        },
        {
            "key": "bsky_app_password",
            "label": "Bluesky app password",
            "secret": True,
            "optional": False,
            "help": "Create at bsky.app/settings/app-passwords (xxxx-xxxx-xxxx-xxxx).",
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array, optional)",
            "secret": False,
            "optional": True,
            "help": 'Pain-point phrases, e.g. ["I wish there was","is there a tool that"]',
        },
    ]

    @staticmethod
    def _creds(db, settings) -> tuple[str | None, str | None]:
        handle = (
            (get_source_credential(db, "bluesky", "bsky_handle", None) if db else None)
            or os.environ.get("BSKY_HANDLE")
        )
        password = (
            (get_source_credential(db, "bluesky", "bsky_app_password", None) if db else None)
            or os.environ.get("BSKY_APP_PASSWORD")
        )
        return handle, password

    @classmethod
    def is_available(cls, db: sqlite3.Connection | None, settings) -> bool:
        handle, password = cls._creds(db, settings)
        return bool(handle and password)

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        handle, password = cls._creds(db, settings)
        if not (handle and password):
            return False, "Set bsky_handle and bsky_app_password (create one at bsky.app/settings/app-passwords)."
        try:
            _create_session(handle, password)
            return True, f"✓ Bluesky session OK for @{handle}"
        except _http.HTTPError as exc:
            if exc.status_code == 401:
                return False, "Invalid credentials (401) — check handle and app password."
            return False, f"Bluesky auth failed: {exc}"
        except Exception as exc:
            return False, f"Bluesky auth error: {exc}"

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        handle, password = self._creds(db, settings)
        if not (handle and password):
            return CollectorResult(
                self.source_name, [], "", "failed", 0,
                error_message="Bluesky credentials not configured.",
                duration_seconds=time.perf_counter() - start,
            )

        queries = _read_queries(db)
        cutoff = datetime.now(timezone.utc) - timedelta(
            hours=getattr(settings, "freshness_bluesky_hours", 72)
        )
        by_id: dict[str, dict] = {}
        errors: list[str] = []

        try:
            token = _create_session(handle, password)
        except Exception as exc:
            return CollectorResult(
                self.source_name, [], "", "failed", 0,
                error_message=f"Bluesky auth failed: {exc}",
                duration_seconds=time.perf_counter() - start,
            )

        for i, query in enumerate(queries):
            try:
                resp = _http.get_json(
                    _SEARCH_URL,
                    headers={"Authorization": f"Bearer {token}"},
                    params={"q": query, "limit": str(_PER_QUERY_LIMIT), "sort": "top"},
                    timeout=30,
                    retries=2,
                )
                for post in (resp.get("posts") or []):
                    item = _parse_post(post, query, cutoff)
                    if not item:
                        continue
                    sid = item["source_id"]
                    if sid in by_id:
                        by_id[sid]["metadata"]["matched_queries"].append(query)
                    else:
                        by_id[sid] = item
            except Exception as exc:
                logger.warning("bluesky_query_failed", query=query, error=str(exc))
                errors.append(f"query '{query}': {exc}")
            if i < len(queries) - 1:
                time.sleep(_INTER_QUERY_DELAY)

        items = list(by_id.values())
        status = "completed" if items else ("partial" if not errors else "failed")
        return CollectorResult(
            source=self.source_name, items=items, run_id="",
            status=status, items_collected=len(items),
            error_message="; ".join(errors) or None,
            duration_seconds=time.perf_counter() - start,
        )


# ── module-level session cache (one token per process, ~90 min) ─────────────
_cached_token: str | None = None
_token_ts: float = 0.0
_TOKEN_MAX_AGE = 5400


def _create_session(handle: str, app_password: str) -> str:
    global _cached_token, _token_ts
    if _cached_token and (time.monotonic() - _token_ts < _TOKEN_MAX_AGE):
        return _cached_token
    resp = _http.post_json(
        _SESSION_URL,
        json_body={"identifier": handle, "password": app_password},
        timeout=15,
        retries=2,
    )
    token = resp.get("accessJwt") if isinstance(resp, dict) else None
    if not token:
        raise _http.HTTPError("Bluesky session response had no accessJwt")
    _cached_token = token
    _token_ts = time.monotonic()
    return token


def _read_queries(db) -> list[str]:
    import json
    raw = get_source_credential(db, "bluesky", "search_queries", None) if db else None
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return [str(q) for q in parsed]
        except (ValueError, TypeError):
            pass
    return DEFAULT_SEARCH_QUERIES


def _parse_post(post: dict, query: str, cutoff: datetime) -> dict | None:
    record = post.get("record") or {}
    text = (record.get("text") or "").strip()
    if not text:
        return None
    author = post.get("author") or {}
    handle = author.get("handle") or ""
    uri = post.get("uri") or ""
    rkey = uri.rsplit("/", 1)[-1] if uri else ""
    if not (handle and rkey):
        return None

    posted_at = _parse_date(post.get("indexedAt") or record.get("createdAt"))
    if posted_at and posted_at < cutoff:
        return None

    likes = post.get("likeCount") or 0
    reposts = post.get("repostCount") or 0
    replies = post.get("replyCount") or 0
    return {
        "source_id": uri,
        "title": text[:140],
        "body": text,
        "url": f"https://bsky.app/profile/{handle}/post/{rkey}",
        "score": likes + reposts,
        "comment_count": replies,
        "posted_at": posted_at.isoformat() if posted_at else None,
        "metadata": {
            "matched_queries": [query],
            "author": handle,
            "like_count": likes,
            "repost_count": reposts,
            "reply_count": replies,
            "auth_mode": "bluesky",
        },
    }


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

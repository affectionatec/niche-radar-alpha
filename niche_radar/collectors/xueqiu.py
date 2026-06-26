"""Xueqiu (雪球) data collector — pain-point discovery on China's finance social network.

Xueqiu requires an authenticated session cookie (``xq_a_token``) for API access.
This collector obtains one by fetching the site as an anonymous visitor (no login
required — the server issues a guest token on first contact), exactly as a browser
does.  Users may also supply the cookie explicitly via Settings → Data Sources for
more reliable access.

API path:
    1. Hot timeline: /v4/statuses/public_timeline_by_category.json
    2. Keyword search: /statuses/search.json — targeted pain-point phrases
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import requests
import structlog

from niche_radar.collectors._http import USER_AGENT
from niche_radar.collectors.base import BaseCollector, CollectorResult
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

_BASE = "https://xueqiu.com"
_DEFAULT_FRESHNESS_HOURS = 48

DEFAULT_QUERIES = [
    "希望有",        # I wish there was
    "有没有工具",     # is there a tool
    "手动处理",       # manual processing
    "找不到",         # can't find
    "求推荐",         # looking for recommendations
    "太贵了",         # too expensive
]


def _cutoff(settings) -> datetime:
    hours = getattr(settings, "freshness_xueqiu_hours", _DEFAULT_FRESHNESS_HOURS)
    return datetime.now(timezone.utc) - timedelta(hours=int(hours))


def _get_cookie(settings, db: sqlite3.Connection | None) -> str:
    """Return the xq_a_token: explicit credential first, then auto-guest-session."""
    stored = get_source_credential(db, "xueqiu", "cookie", None) if db else None
    if stored:
        return stored
    env_cookie = getattr(settings, "xueqiu_cookie", None)
    if env_cookie:
        return env_cookie
    # Auto-fetch an anonymous guest session — the server sets xq_a_token on any GET.
    try:
        resp = requests.get(
            _BASE,
            headers={"User-Agent": USER_AGENT},
            timeout=10,
            allow_redirects=True,
        )
        token = resp.cookies.get("xq_a_token", "")
        if token:
            return token
    except Exception as exc:
        logger.warning("xueqiu_guest_cookie_failed", error=str(exc))
    return ""


def _session(cookie: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Cookie": f"xq_a_token={cookie}"})
    return s


def _normalize(post: dict, cutoff: datetime) -> dict | None:
    """Map a Xueqiu post dict to a normalized raw item; returns None if stale/invalid."""
    pid = str(post.get("id") or "")
    if not pid:
        return None

    created_ms = post.get("created_at") or 0
    if created_ms:
        posted_dt = datetime.fromtimestamp(int(created_ms) / 1000, tz=timezone.utc)
        if posted_dt < cutoff:
            return None
    else:
        posted_dt = datetime.now(timezone.utc)

    user = post.get("user") or {}
    title = (post.get("title") or "").strip()
    text = (post.get("text") or post.get("description") or "").strip()

    return {
        "source_id": pid,
        "title": title or text[:120] or "(no title)",
        "body": text or None,
        "url": f"{_BASE}/statuses/{pid}",
        "score": int(post.get("like_count") or 0),
        "comment_count": int(post.get("reply_count") or 0),
        "posted_at": posted_dt.isoformat(),
        "metadata": {
            "author": user.get("screen_name") or user.get("id") or "",
            "retweet_count": int(post.get("retweet_count") or 0),
        },
    }


class XueqiuCollector(BaseCollector):
    source_name = "xueqiu"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "cookie",
            "label": "xq_a_token cookie",
            "secret": True,
            "optional": True,
            "help": "Xueqiu session cookie (xq_a_token value). Optional — the collector automatically obtains an anonymous guest token. Provide explicitly for more reliable access.",
        },
    ]

    @classmethod
    def is_available(cls, db: sqlite3.Connection | None, settings) -> bool:
        return True  # auto-guest-session always attempted

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        cookie = get_source_credential(db, "xueqiu", "cookie", getattr(settings, "xueqiu_cookie", None))
        if cookie:
            return True, "Xueqiu: using explicit session cookie"
        return True, "Xueqiu: will attempt auto-guest session (no explicit cookie set)"

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            cookie = _get_cookie(settings, db)
            if not cookie:
                return CollectorResult(
                    source=self.source_name, items=[], run_id="",
                    status="failed", items_collected=0,
                    error_message="could not obtain Xueqiu session cookie",
                    duration_seconds=time.perf_counter() - start,
                )

            sess = _session(cookie)
            cutoff = _cutoff(settings)
            items: dict[str, dict] = {}
            errors: list[str] = []

            # Hot timeline
            try:
                resp = sess.get(
                    f"{_BASE}/v4/statuses/public_timeline_by_category.json",
                    params={"category": -1, "count": 20, "source": "category.hot"},
                    timeout=15,
                )
                if resp.status_code == 200:
                    for post in (resp.json().get("list") or []):
                        item = _normalize(post, cutoff)
                        if item:
                            items[item["source_id"]] = item
            except Exception as exc:
                logger.warning("xueqiu_timeline_failed", error=str(exc))
                errors.append(f"timeline: {exc}")

            # Keyword search for pain-point phrases
            for query in DEFAULT_QUERIES:
                try:
                    resp = sess.get(
                        f"{_BASE}/statuses/search.json",
                        params={"q": query, "count": 10, "page": 1},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        for post in (resp.json().get("list") or resp.json().get("statuses") or []):
                            item = _normalize(post, cutoff)
                            if item and item["source_id"] not in items:
                                items[item["source_id"]] = item
                except Exception as exc:
                    logger.warning("xueqiu_search_failed", query=query, error=str(exc))
                    errors.append(f"query '{query}': {exc}")

            collected = list(items.values())
            status = "completed" if collected else ("partial" if errors else "failed")
            return CollectorResult(
                source=self.source_name, items=collected, run_id="",
                status=status, items_collected=len(collected),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )

        except Exception as exc:
            logger.exception("xueqiu_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="",
                status="failed", items_collected=0,
                error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

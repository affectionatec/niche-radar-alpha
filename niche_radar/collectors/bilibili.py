"""Bilibili (B站) data collector — pain-point discovery via video search.

Capture walks an ordered chain:

    1. auth_api   — Bilibili search API with SESSDATA cookie (higher rate limits,
                    richer content, better relevance ranking).
    2. public_api — Bilibili search API with an auto-fetched buvid3 guest
                    fingerprint (always available, no credentials needed).

Both backends query configurable Chinese pain-point search phrases and map
video metadata (title, description, play count, comment count) to raw items.

The Bilibili search endpoint returns HTML-tagged titles/descriptions; these are
stripped before persisting.  A 1-second polite delay is inserted between
consecutive search requests.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import requests as _requests
import structlog

from niche_radar.collectors._http import USER_AGENT
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

_SEARCH_URL = "https://api.bilibili.com/x/web-interface/search/type"
_BILI_HOME = "https://www.bilibili.com"
_DEFAULT_FRESHNESS_HOURS = 336  # 14 days — video discovery is slow (same as YouTube)
_HTML_TAG_RE = re.compile(r"<[^>]+>")

DEFAULT_QUERIES = [
    "有没有什么工具",      # is there a tool that
    "好用的替代品",        # good alternative
    "效率太低",           # too inefficient
    "手动操作太麻烦",      # manual process is tedious
    "求推荐 工具",        # looking for tool recommendations
    "怎么自动化",         # how to automate
    "吐槽 软件",          # complaining about software
    "痛点 开发",          # developer pain points
]

_HEADERS = {
    "User-Agent": USER_AGENT,
    "Referer": "https://www.bilibili.com",
}


def _cutoff(settings) -> datetime:
    hours = getattr(settings, "freshness_bilibili_hours", _DEFAULT_FRESHNESS_HOURS)
    return datetime.now(timezone.utc) - timedelta(hours=int(hours))


def _sessdata(settings, db: sqlite3.Connection | None) -> str | None:
    val = get_source_credential(db, "bilibili", "sessdata", None) if db else None
    return val or getattr(settings, "bilibili_sessdata", None) or None


def _queries(db: sqlite3.Connection | None) -> list[str]:
    raw = get_source_credential(db, "bilibili", "search_queries", None) if db else None
    return json.loads(raw) if raw else DEFAULT_QUERIES


def _get_buvid3() -> str:
    """Fetch an anonymous buvid3 fingerprint from bilibili.com (like a first browser visit)."""
    try:
        resp = _requests.get(
            _BILI_HOME,
            headers=_HEADERS,
            timeout=10,
            allow_redirects=True,
        )
        return resp.cookies.get("buvid3", "")
    except Exception as exc:
        logger.warning("bilibili_buvid3_fetch_failed", error=str(exc))
        return ""


def _clean(text: str | None) -> str:
    """Strip Bilibili HTML tags from title/description fields."""
    if not text:
        return ""
    return _HTML_TAG_RE.sub("", text).strip()


def _normalize(video: dict, cutoff: datetime, matched_query: str) -> dict | None:
    """Map a Bilibili video search result to a normalized raw item."""
    bvid = video.get("bvid") or ""
    aid = str(video.get("aid") or video.get("id") or "")
    source_id = f"bili-{bvid or aid}"
    if source_id == "bili-":
        return None

    pubdate = video.get("pubdate") or video.get("senddate")
    if pubdate and isinstance(pubdate, (int, float)):
        posted_dt = datetime.fromtimestamp(int(pubdate), tz=timezone.utc)
        if posted_dt < cutoff:
            return None
    else:
        posted_dt = datetime.now(timezone.utc)

    title = _clean(video.get("title") or "")[:300]
    description = _clean(video.get("description") or "")

    return {
        "source_id": source_id,
        "title": title or "(no title)",
        "body": (f"{title}\n\n{description}".strip())[:3000] or None,
        "url": (
            f"https://www.bilibili.com/video/{bvid}"
            if bvid
            else f"https://www.bilibili.com/video/av{aid}"
        ),
        "score": int(video.get("play") or video.get("view") or 0),
        "comment_count": int(video.get("video_review") or video.get("review") or 0),
        "posted_at": posted_dt.isoformat(),
        "metadata": {
            "author": video.get("author") or "",
            "tags": video.get("tag", "").split(",") if video.get("tag") else [],
            "matched_queries": [matched_query],
            "language": "zh",
        },
    }


def _search_videos(
    session: _requests.Session,
    queries: list[str],
    cutoff: datetime,
) -> tuple[dict[str, dict], list[str]]:
    """Run pain-point queries and return (items_by_id, errors)."""
    items: dict[str, dict] = {}
    errors: list[str] = []

    for query in queries:
        try:
            resp = session.get(
                _SEARCH_URL,
                params={"keyword": query, "search_type": "video", "order": "totalrank"},
                timeout=15,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP {resp.status_code}")
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"API error {data.get('code')}: {data.get('message', '')}")

            videos = data.get("data", {}).get("result") or []
            for video in videos[:20]:
                if not isinstance(video, dict):
                    continue
                item = _normalize(video, cutoff, query)
                if item is None:
                    continue
                sid = item["source_id"]
                if sid in items:
                    items[sid]["metadata"]["matched_queries"].append(query)
                else:
                    items[sid] = item

            time.sleep(1.0)  # polite delay — Bilibili rate-limits aggressively
        except Exception as exc:
            logger.warning("bilibili_query_failed", query=query, error=str(exc))
            errors.append(f"query '{query}': {exc}")

    return items, errors


class BilibiliAuthApiBackend(SourceBackend):
    """Bilibili search API with SESSDATA session cookie (higher rate limits)."""

    name = "auth_api"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return bool(_sessdata(settings, db))

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        sessdata = _sessdata(settings, db)
        session = _requests.Session()
        session.headers.update(_HEADERS)
        session.cookies.set("SESSDATA", sessdata, domain=".bilibili.com")

        queries = _queries(db)
        cutoff = _cutoff(settings)
        items, errors = _search_videos(session, queries, cutoff)
        if not items and errors:
            raise RuntimeError("; ".join(errors))
        return list(items.values())


class BilibiliPublicApiBackend(SourceBackend):
    """Bilibili search API with auto-fetched buvid3 guest fingerprint (always available)."""

    name = "public_api"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return True

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        buvid3 = _get_buvid3()
        session = _requests.Session()
        session.headers.update(_HEADERS)
        if buvid3:
            session.cookies.set("buvid3", buvid3, domain=".bilibili.com")

        queries = _queries(db)
        cutoff = _cutoff(settings)
        items, errors = _search_videos(session, queries, cutoff)
        if not items and errors:
            raise RuntimeError("; ".join(errors))
        return list(items.values())


class BilibiliCollector(MultiBackendCollector):
    source_name = "bilibili"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "sessdata",
            "label": "SESSDATA Cookie",
            "secret": True,
            "optional": True,
            "help": "Bilibili session cookie from your browser after login. Optional — improves rate limits; without it an anonymous guest session is used.",
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array)",
            "secret": False,
            "optional": True,
            "help": 'Chinese pain-point phrases, e.g. ["求推荐 工具","效率太低"]',
        },
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [BilibiliAuthApiBackend(), BilibiliPublicApiBackend()]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        if _sessdata(settings, db):
            return True, "Bilibili: using SESSDATA cookie (auth API)"
        return True, "Bilibili: using public API (auto guest session)"

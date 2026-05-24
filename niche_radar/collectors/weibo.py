"""Weibo (微博) collector — cookie-based web scraping.

Scrapes Weibo's mobile search API via httpx. Requires a cookie string
from a logged-in browser session. Classified as FRAGILE — cookies
expire and anti-bot measures may block requests.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import ClassVar

import httpx
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import (
    BaseCollector,
    CollectorResult,
    CollectorUnavailableError,
)
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

# Mobile API is more stable than desktop for scraping
WEIBO_SEARCH_API = "https://m.weibo.cn/api/container/getIndex"

DEFAULT_SEARCH_QUERIES = [
    "有没有什么工具",      # is there a tool that
    "好用的替代品",        # good alternative
    "太贵了",             # pricing is crazy
    "求推荐 软件",        # looking for software recommendations
    "效率太低",           # too inefficient
    "吐槽 软件",         # complaints about software
    "痛点 产品",         # product pain points
    "怎么自动化",         # how to automate
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://m.weibo.cn/",
    "X-Requested-With": "XMLHttpRequest",
}


class WeiboCollector(BaseCollector):
    source_name = "weibo"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "cookie", "label": "Weibo Cookie String", "secret": True, "optional": False,
         "help": "Cookie string from m.weibo.cn after login (includes SUB token)"},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True,
         "help": 'Chinese pain-point phrases, e.g. ["求推荐","吐槽"]'},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        cookie = get_source_credential(db, "weibo", "cookie", None)
        if not cookie:
            return False, "Weibo cookie not configured"
        try:
            headers = dict(_HEADERS)
            headers["Cookie"] = cookie
            resp = httpx.get(
                WEIBO_SEARCH_API,
                params={"containerid": "100103type=1&q=test", "page": "1"},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok") == 1:
                    return True, "Weibo API reachable"
                return False, f"Weibo API error: {data.get('msg', 'unknown')}"
            return False, f"Weibo returned HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            cookie = (get_source_credential(db, "weibo", "cookie", None) if db else None)
            if not cookie:
                raise CollectorUnavailableError("Weibo cookie not configured")

            raw_queries = (get_source_credential(db, "weibo", "search_queries", None) if db else None)
            queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=3, min=3, max=60),
                reraise=True,
            )
            headers = dict(_HEADERS)
            headers["Cookie"] = cookie

            items: dict[str, dict] = {}
            errors: list[str] = []

            for query in queries:
                try:
                    container_id = f"100103type=1&q={query}"
                    for attempt in retryer:
                        with attempt:
                            resp = httpx.get(
                                WEIBO_SEARCH_API,
                                params={"containerid": container_id, "page": "1"},
                                headers=headers,
                                timeout=20,
                            )
                            if resp.status_code == 418:
                                raise CollectorUnavailableError("Weibo anti-bot block (418)")
                            if resp.status_code != 200:
                                raise CollectorUnavailableError(f"Weibo returned {resp.status_code}")
                            data = resp.json()
                            if data.get("ok") != 1:
                                raise CollectorUnavailableError(f"Weibo error: {data.get('msg', 'unknown')}")

                    cards = data.get("data", {}).get("cards", [])
                    for card in cards:
                        if card.get("card_type") != 9:
                            continue
                        mblog = card.get("mblog") or {}
                        mid = str(mblog.get("id") or mblog.get("mid") or "")
                        if not mid:
                            continue

                        if mid in items:
                            items[mid]["metadata"]["matched_queries"].append(query)
                            continue

                        # Strip HTML tags from text
                        import re
                        raw_text = mblog.get("text") or ""
                        clean_text = re.sub(r"<[^>]+>", "", raw_text)

                        created_at_str = mblog.get("created_at") or ""
                        try:
                            # Weibo uses format like "Wed May 21 10:30:00 +0800 2026"
                            posted_dt = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
                            posted_at = posted_dt.astimezone(timezone.utc).isoformat()
                        except (ValueError, TypeError):
                            posted_at = datetime.now(timezone.utc).isoformat()

                        user_info = mblog.get("user") or {}
                        reposts = int(mblog.get("reposts_count") or 0)
                        comments_count = int(mblog.get("comments_count") or 0)
                        attitudes = int(mblog.get("attitudes_count") or 0)

                        items[mid] = {
                            "source_id": f"weibo-{mid}",
                            "title": clean_text[:100],
                            "body": clean_text[:3000],
                            "url": f"https://m.weibo.cn/detail/{mid}",
                            "score": attitudes + reposts,
                            "comment_count": comments_count,
                            "posted_at": posted_at,
                            "metadata": {
                                "language": "zh",
                                "platform": "weibo",
                                "author": user_info.get("screen_name") or "",
                                "tags": [],
                                "reposts": reposts,
                                "attitudes": attitudes,
                                "matched_queries": [query],
                            },
                        }
                    time.sleep(2.0)  # polite delay — Weibo is aggressive
                except Exception as exc:
                    logger.warning("weibo_query_failed", query=query, error=str(exc))
                    errors.append(f"query '{query}': {exc}")

            collected = list(items.values())
            status = "completed" if not errors else "partial" if collected else "failed"
            return CollectorResult(
                source=self.source_name,
                items=collected,
                run_id="",
                status=status,
                items_collected=len(collected),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("weibo_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

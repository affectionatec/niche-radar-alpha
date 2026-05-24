"""Zhihu (知乎) collector — custom scraping-based discovery.

Scrapes Zhihu's search API via httpx. Requires a cookie string for
authenticated access. Zhihu has aggressive anti-bot — this collector
is classified as FRAGILE.
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

ZHIHU_SEARCH_API = "https://www.zhihu.com/api/v4/search_v3"

DEFAULT_SEARCH_QUERIES = [
    "有没有什么工具",      # is there a tool that
    "求推荐 软件",        # looking for software recommendations
    "好用的替代品",        # good alternative
    "太贵了 软件",        # software too expensive
    "怎么自动化",         # how to automate
    "效率太低",           # too inefficient
    "痛点",              # pain point
    "手动操作太麻烦",      # manual process is tedious
]

_BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.zhihu.com/search",
    "X-Requested-With": "fetch",
}


class ZhihuCollector(BaseCollector):
    source_name = "zhihu"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "cookie", "label": "Zhihu Cookie String", "secret": True, "optional": False,
         "help": "Full cookie string from browser after login (includes z_c0 token)"},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True,
         "help": 'Chinese pain-point phrases, e.g. ["求推荐","痛点"]'},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        cookie = get_source_credential(db, "zhihu", "cookie", None)
        if not cookie:
            return False, "Zhihu cookie not configured"
        try:
            headers = dict(_BASE_HEADERS)
            headers["Cookie"] = cookie
            resp = httpx.get(
                ZHIHU_SEARCH_API,
                params={"t": "general", "q": "test", "correction": "1", "offset": "0", "limit": "1"},
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 200:
                return True, "Zhihu API reachable"
            if resp.status_code == 401 or resp.status_code == 403:
                return False, "Zhihu cookie expired or invalid"
            return False, f"Zhihu returned HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            cookie = (get_source_credential(db, "zhihu", "cookie", None) if db else None)
            if not cookie:
                raise CollectorUnavailableError("Zhihu cookie not configured")

            raw_queries = (get_source_credential(db, "zhihu", "search_queries", None) if db else None)
            queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=3, min=3, max=60),
                reraise=True,
            )
            headers = dict(_BASE_HEADERS)
            headers["Cookie"] = cookie

            items: dict[str, dict] = {}
            errors: list[str] = []

            for query in queries:
                try:
                    for attempt in retryer:
                        with attempt:
                            resp = httpx.get(
                                ZHIHU_SEARCH_API,
                                params={
                                    "t": "general",
                                    "q": query,
                                    "correction": "1",
                                    "offset": "0",
                                    "limit": "20",
                                },
                                headers=headers,
                                timeout=20,
                            )
                            if resp.status_code == 403:
                                raise CollectorUnavailableError("Zhihu anti-bot block (403)")
                            if resp.status_code == 401:
                                raise CollectorUnavailableError("Zhihu cookie expired (401)")
                            if resp.status_code != 200:
                                raise CollectorUnavailableError(f"Zhihu returned {resp.status_code}")
                            data = resp.json()

                    results = data.get("data", [])
                    for result in results:
                        obj = result.get("object") or result
                        obj_type = result.get("type") or obj.get("type", "")

                        # Only process answers and articles
                        if obj_type not in ("answer", "article", "search_result"):
                            continue

                        zhihu_id = str(obj.get("id") or "")
                        if not zhihu_id:
                            content_preview = (obj.get("content") or obj.get("excerpt") or "")[:100]
                            zhihu_id = hashlib.md5(content_preview.encode()).hexdigest()[:12]

                        if zhihu_id in items:
                            items[zhihu_id]["metadata"]["matched_queries"].append(query)
                            continue

                        # Extract fields depending on type
                        if obj_type == "answer":
                            question = obj.get("question") or {}
                            title = question.get("title") or ""
                            content = obj.get("content") or obj.get("excerpt") or ""
                            url = f"https://www.zhihu.com/question/{question.get('id', '')}/answer/{zhihu_id}"
                            voteup = int(obj.get("voteup_count") or 0)
                            comment_count = int(obj.get("comment_count") or 0)
                        elif obj_type == "article":
                            title = obj.get("title") or ""
                            content = obj.get("content") or obj.get("excerpt") or ""
                            url = f"https://zhuanlan.zhihu.com/p/{zhihu_id}"
                            voteup = int(obj.get("voteup_count") or 0)
                            comment_count = int(obj.get("comment_count") or 0)
                        else:
                            title = obj.get("title") or obj.get("highlight", {}).get("title", "")
                            content = obj.get("content") or obj.get("excerpt") or obj.get("description") or ""
                            url = obj.get("url") or f"https://www.zhihu.com/search?q={query}"
                            voteup = int(obj.get("voteup_count") or 0)
                            comment_count = int(obj.get("comment_count") or 0)

                        # Strip HTML
                        import re
                        title = re.sub(r"<[^>]+>", "", title)
                        content = re.sub(r"<[^>]+>", "", content)

                        created_time = obj.get("created_time") or obj.get("created")
                        if created_time and isinstance(created_time, (int, float)):
                            posted_at = datetime.fromtimestamp(created_time, tz=timezone.utc).isoformat()
                        else:
                            posted_at = datetime.now(timezone.utc).isoformat()

                        author_info = obj.get("author") or {}
                        author = author_info.get("name") or ""

                        items[zhihu_id] = {
                            "source_id": f"zhihu-{zhihu_id}",
                            "title": title[:300],
                            "body": f"{title}\n\n{content}".strip()[:3000],
                            "url": url,
                            "score": voteup,
                            "comment_count": comment_count,
                            "posted_at": posted_at,
                            "metadata": {
                                "language": "zh",
                                "platform": "zhihu",
                                "author": author,
                                "type": obj_type,
                                "tags": [t.get("name", "") for t in (obj.get("topics") or [])],
                                "matched_queries": [query],
                            },
                        }
                    time.sleep(2.0)  # respectful delay — Zhihu is aggressive
                except Exception as exc:
                    logger.warning("zhihu_query_failed", query=query, error=str(exc))
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
            logger.exception("zhihu_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

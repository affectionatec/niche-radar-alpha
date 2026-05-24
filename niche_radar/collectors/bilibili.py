"""Bilibili (B站) collector — community API-based discovery.

Uses the bilibili-api-python library (public endpoints) to search videos and
comments containing pain-point signals. Optional SESSDATA cookie improves
rate limits but is not required.
"""

from __future__ import annotations

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

BILIBILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/all/v2"

DEFAULT_SEARCH_QUERIES = [
    "有没有什么工具",      # is there a tool that
    "好用的替代品",        # good alternative
    "效率太低",           # too inefficient
    "手动操作太麻烦",      # manual process is tedious
    "求推荐 工具",        # looking for tool recommendations
    "怎么自动化",         # how to automate
    "吐槽 软件",         # complaining about software
    "痛点 开发",         # developer pain points
]

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com",
}


class BilibiliCollector(BaseCollector):
    source_name = "bilibili"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "sessdata", "label": "SESSDATA Cookie", "secret": True, "optional": True,
         "help": "Optional — improves rate limits. Get from browser cookies after login."},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True,
         "help": 'Chinese search phrases, e.g. ["求推荐 工具","痛点"]'},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        try:
            resp = httpx.get(
                BILIBILI_SEARCH_API,
                params={"keyword": "test", "page": "1"},
                headers=_HEADERS,
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == 0:
                    return True, "Bilibili search API reachable"
                return False, f"Bilibili API error code: {data.get('code')}"
            return False, f"Bilibili returned HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            sessdata = (get_source_credential(db, "bilibili", "sessdata", None) if db else None)
            raw_queries = (get_source_credential(db, "bilibili", "search_queries", None) if db else None)
            queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=2, min=2, max=30),
                reraise=True,
            )
            headers = dict(_HEADERS)
            if sessdata:
                headers["Cookie"] = f"SESSDATA={sessdata}"

            items: dict[str, dict] = {}
            errors: list[str] = []

            for query in queries:
                try:
                    for attempt in retryer:
                        with attempt:
                            resp = httpx.get(
                                BILIBILI_SEARCH_API,
                                params={"keyword": query, "page": "1", "search_type": "video"},
                                headers=headers,
                                timeout=20,
                            )
                            if resp.status_code != 200:
                                raise CollectorUnavailableError(f"Bilibili returned {resp.status_code}")
                            data = resp.json()
                            if data.get("code") != 0:
                                raise CollectorUnavailableError(f"Bilibili API error: {data.get('message', data.get('code'))}")

                    result_list = data.get("data", {}).get("result", [])
                    # The v2 endpoint nests results by type; find the video type
                    videos = []
                    if isinstance(result_list, list):
                        for group in result_list:
                            if isinstance(group, dict) and group.get("result_type") == "video":
                                videos = group.get("data", [])
                                break
                        if not videos and result_list:
                            # Fallback: treat flat list as videos
                            videos = [r for r in result_list if isinstance(r, dict) and r.get("bvid")]

                    for video in videos[:20]:
                        bvid = video.get("bvid") or ""
                        aid = str(video.get("aid") or video.get("id") or "")
                        source_id = bvid or aid
                        if not source_id:
                            continue

                        if source_id in items:
                            items[source_id]["metadata"]["matched_queries"].append(query)
                            continue

                        # Strip HTML tags from title/description
                        import re
                        title = re.sub(r"<[^>]+>", "", video.get("title") or "")
                        description = re.sub(r"<[^>]+>", "", video.get("description") or "")

                        pubdate = video.get("pubdate") or video.get("senddate")
                        if pubdate and isinstance(pubdate, (int, float)):
                            posted_at = datetime.fromtimestamp(pubdate, tz=timezone.utc).isoformat()
                        else:
                            posted_at = datetime.now(timezone.utc).isoformat()

                        play_count = int(video.get("play") or video.get("view") or 0)
                        danmaku_count = int(video.get("danmaku") or video.get("video_review") or 0)

                        items[source_id] = {
                            "source_id": f"bili-{source_id}",
                            "title": title[:300],
                            "body": f"{title}\n\n{description}".strip()[:3000],
                            "url": f"https://www.bilibili.com/video/{bvid}" if bvid else f"https://www.bilibili.com/video/av{aid}",
                            "score": play_count,
                            "comment_count": danmaku_count,
                            "posted_at": posted_at,
                            "metadata": {
                                "language": "zh",
                                "platform": "bilibili",
                                "author": video.get("author") or "",
                                "tags": video.get("tag", "").split(",") if video.get("tag") else [],
                                "duration": video.get("duration") or "",
                                "matched_queries": [query],
                            },
                        }
                    time.sleep(1.0)  # polite delay between searches
                except Exception as exc:
                    logger.warning("bilibili_query_failed", query=query, error=str(exc))
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
            logger.exception("bilibili_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

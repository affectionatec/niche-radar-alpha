"""Douyin (抖音) collector — TikHub API-based discovery.

Uses the TikHub unified API (tikhub.io) to search Douyin videos containing
pain-point signals. Shares the same TIKHUB_API_KEY as the Xiaohongshu
collector. Classified as VERY BRITTLE — Douyin's anti-bot is aggressive
even through TikHub.
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

TIKHUB_BASE = "https://api.tikhub.io"

DEFAULT_SEARCH_QUERIES = [
    "有没有什么工具",      # is there a tool that
    "好用的替代品",        # good alternative
    "太贵了",             # pricing is crazy
    "求推荐",             # looking for recommendations
    "效率太低",           # too inefficient
    "怎么自动化",         # how to automate
    "吐槽 软件",         # complaints about software
    "痛点",              # pain point
]


class DouyinCollector(BaseCollector):
    source_name = "douyin"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "tikhub_api_key", "label": "TikHub API Key", "secret": True, "optional": False,
         "help": "API key from tikhub.io — same key used for Xiaohongshu"},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True,
         "help": 'Chinese search phrases, e.g. ["求推荐","吐槽 软件"]'},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        api_key = get_source_credential(db, "douyin", "tikhub_api_key", None)
        if not api_key:
            return False, "TikHub API key not configured"
        try:
            resp = httpx.get(
                f"{TIKHUB_BASE}/api/v1/douyin/web/search_video",
                params={"keyword": "test", "offset": "0", "count": "1", "sort_type": "0"},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return True, "TikHub Douyin API reachable"
            if resp.status_code == 401:
                return False, "TikHub API key invalid (401)"
            return False, f"TikHub returned HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            api_key = (get_source_credential(db, "douyin", "tikhub_api_key", None) if db else None)
            if not api_key:
                raise CollectorUnavailableError("TikHub API key not configured for Douyin")

            raw_queries = (get_source_credential(db, "douyin", "search_queries", None) if db else None)
            queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=3, min=3, max=60),
                reraise=True,
            )
            headers = {"Authorization": f"Bearer {api_key}"}
            items: dict[str, dict] = {}
            errors: list[str] = []

            for query in queries:
                try:
                    for attempt in retryer:
                        with attempt:
                            resp = httpx.get(
                                f"{TIKHUB_BASE}/api/v1/douyin/web/search_video",
                                params={
                                    "keyword": query,
                                    "offset": "0",
                                    "count": "20",
                                    "sort_type": "0",
                                },
                                headers=headers,
                                timeout=20,
                            )
                            if resp.status_code == 429:
                                raise CollectorUnavailableError("TikHub rate limit hit")
                            if resp.status_code != 200:
                                raise CollectorUnavailableError(f"TikHub returned {resp.status_code}")
                            data = resp.json()

                    video_list = (
                        data.get("data", {}).get("data", []) or
                        data.get("data", {}).get("aweme_list", []) or
                        data.get("data", []) or
                        []
                    )
                    for video in video_list[:20]:
                        aweme_id = str(video.get("aweme_id") or video.get("id") or "")
                        if not aweme_id:
                            desc_preview = (video.get("desc") or "")[:100]
                            aweme_id = hashlib.md5(desc_preview.encode()).hexdigest()[:12]

                        if aweme_id in items:
                            items[aweme_id]["metadata"]["matched_queries"].append(query)
                            continue

                        desc = video.get("desc") or ""
                        statistics = video.get("statistics") or {}
                        digg_count = int(statistics.get("digg_count") or video.get("digg_count") or 0)
                        comment_count = int(statistics.get("comment_count") or video.get("comment_count") or 0)
                        share_count = int(statistics.get("share_count") or video.get("share_count") or 0)

                        create_time = video.get("create_time")
                        if create_time and isinstance(create_time, (int, float)):
                            posted_at = datetime.fromtimestamp(create_time, tz=timezone.utc).isoformat()
                        else:
                            posted_at = datetime.now(timezone.utc).isoformat()

                        author_info = video.get("author") or {}
                        author = author_info.get("nickname") or author_info.get("unique_id") or ""

                        share_url = video.get("share_url") or f"https://www.douyin.com/video/{aweme_id}"

                        items[aweme_id] = {
                            "source_id": f"douyin-{aweme_id}",
                            "title": desc[:300],
                            "body": desc[:3000],
                            "url": share_url,
                            "score": digg_count + share_count,
                            "comment_count": comment_count,
                            "posted_at": posted_at,
                            "metadata": {
                                "language": "zh",
                                "platform": "douyin",
                                "author": author,
                                "tags": [t.get("tag_name", "") for t in (video.get("text_extra") or []) if t.get("tag_name")],
                                "share_count": share_count,
                                "matched_queries": [query],
                            },
                        }
                    time.sleep(1.0)
                except Exception as exc:
                    logger.warning("douyin_query_failed", query=query, error=str(exc))
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
            logger.exception("douyin_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

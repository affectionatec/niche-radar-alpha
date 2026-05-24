"""Xiaohongshu (小红书) collector — TikHub API-based discovery.

Uses the TikHub unified API (tikhub.io) to search notes/posts containing
pain-point signals in Chinese. Requires a TIKHUB_API_KEY configured via
Settings > Sources > Xiaohongshu.
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
    "好用的替代品",        # good alternative to
    "太贵了",             # pricing is crazy
    "手动操作太麻烦",      # manual process is tedious
    "求推荐",             # looking for recommendations
    "效率太低",           # too inefficient
    "痛点",              # pain point
    "吐槽",              # complaints
    "怎么自动化",         # how to automate
    "有人做过",           # has anyone built
]


class XiaohongshuCollector(BaseCollector):
    source_name = "xiaohongshu"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "tikhub_api_key", "label": "TikHub API Key", "secret": True, "optional": False,
         "help": "API key from tikhub.io — covers Xiaohongshu + Douyin"},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True,
         "help": 'Chinese pain-point phrases, e.g. ["求推荐","太贵了"]'},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        api_key = get_source_credential(db, "xiaohongshu", "tikhub_api_key", None)
        if not api_key:
            return False, "TikHub API key not configured"
        try:
            resp = httpx.get(
                f"{TIKHUB_BASE}/api/v1/xiaohongshu/app_v2/search_notes",
                params={"keyword": "test", "page": "1", "sort_type": "general"},
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=15,
            )
            if resp.status_code == 200:
                return True, "TikHub Xiaohongshu API reachable"
            if resp.status_code == 401:
                return False, "TikHub API key invalid (401)"
            if resp.status_code == 402:
                return False, "TikHub account has insufficient credits — top up at tikhub.io"
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
            api_key = (get_source_credential(db, "xiaohongshu", "tikhub_api_key", None) if db else None)
            if not api_key:
                raise CollectorUnavailableError("TikHub API key not configured for Xiaohongshu")

            raw_queries = (get_source_credential(db, "xiaohongshu", "search_queries", None) if db else None)
            queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=2, min=2, max=30),
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
                                f"{TIKHUB_BASE}/api/v1/xiaohongshu/app_v2/search_notes",
                                params={"keyword": query, "page": "1", "sort_type": "time_descending"},
                                headers=headers,
                                timeout=20,
                            )
                            if resp.status_code == 429:
                                raise CollectorUnavailableError("TikHub rate limit hit")
                            if resp.status_code == 402:
                                raise CollectorUnavailableError("TikHub account has insufficient credits — top up at tikhub.io")
                            if resp.status_code != 200:
                                raise CollectorUnavailableError(f"TikHub returned {resp.status_code}")
                            data = resp.json()

                    notes = data.get("data", {}).get("items", []) or data.get("data", {}).get("notes", []) or []
                    for note in notes[:30]:
                        note_id = note.get("id") or note.get("note_id") or ""
                        if not note_id:
                            note_id = hashlib.md5(json.dumps(note, ensure_ascii=False)[:200].encode()).hexdigest()[:12]

                        if note_id in items:
                            items[note_id]["metadata"]["matched_queries"].append(query)
                            continue

                        title = note.get("title") or note.get("display_title") or ""
                        desc = note.get("desc") or note.get("description") or note.get("note_card", {}).get("desc", "")
                        likes = int(note.get("liked_count") or note.get("likes") or 0)
                        comments = int(note.get("comment_count") or note.get("comments") or 0)

                        timestamp = note.get("time") or note.get("last_update_time")
                        if timestamp and isinstance(timestamp, (int, float)):
                            posted_at = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
                        elif timestamp and isinstance(timestamp, str):
                            posted_at = timestamp
                        else:
                            posted_at = datetime.now(timezone.utc).isoformat()

                        user_info = note.get("user") or note.get("user_info") or {}
                        author = user_info.get("nickname") or user_info.get("name") or ""

                        items[note_id] = {
                            "source_id": f"xhs-{note_id}",
                            "title": title[:300] or desc[:100],
                            "body": f"{title}\n\n{desc}".strip()[:3000],
                            "url": f"https://www.xiaohongshu.com/explore/{note_id}",
                            "score": likes,
                            "comment_count": comments,
                            "posted_at": posted_at,
                            "metadata": {
                                "language": "zh",
                                "platform": "xiaohongshu",
                                "author": author,
                                "tags": note.get("tag_list") or [],
                                "matched_queries": [query],
                            },
                        }
                    time.sleep(0.5)
                except Exception as exc:
                    logger.warning("xiaohongshu_query_failed", query=query, error=str(exc))
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
            logger.exception("xiaohongshu_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

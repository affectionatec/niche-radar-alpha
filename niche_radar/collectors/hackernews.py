"""Hacker News data collector — Algolia search-based discovery."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import requests
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import (
    BaseCollector,
    CollectorResult,
    CollectorUnavailableError,
)
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"

DEFAULT_SEARCH_QUERIES = [
    "I wish there was",
    "is there a tool that",
    "we do this manually",
    "still using spreadsheets",
    "anyone built something",
    "how do you automate",
    "pricing is crazy",
    "alternative to",
    "looking for a tool",
]

DEFAULT_MIN_POINTS = 10
DEFAULT_MIN_COMMENTS = 5


class HackerNewsCollector(BaseCollector):
    source_name = "hn"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True, "help": "Pain-point phrases for Ask HN"},
        {"key": "min_points", "label": "Min points", "secret": False, "optional": True, "help": "Minimum score (default 10)"},
        {"key": "min_comments", "label": "Min comments", "secret": False, "optional": True, "help": "Minimum comment count (default 5)"},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        try:
            resp = requests.get(
                ALGOLIA_SEARCH,
                params={"query": "test", "tags": "ask_hn", "hitsPerPage": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                return True, "HN Algolia API reachable"
            return False, f"Algolia returned HTTP {resp.status_code}"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            raw_queries = (get_source_credential(db, "hn", "search_queries", None) if db else None)
            search_queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            min_points = int(
                (get_source_credential(db, "hn", "min_points", None) if db else None)
                or DEFAULT_MIN_POINTS
            )
            min_comments = int(
                (get_source_credential(db, "hn", "min_comments", None) if db else None)
                or DEFAULT_MIN_COMMENTS
            )

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=1, exp_base=max(2, int(settings.retry_backoff_base or 2)), min=1, max=15),
                reraise=True,
            )
            cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.freshness_hn_hours)
            items: dict[str, dict] = {}
            errors: list[str] = []
            dropped_stale = 0

            for query in search_queries:
                try:
                    for attempt in retryer:
                        with attempt:
                            resp = requests.get(
                                ALGOLIA_SEARCH,
                                params={
                                    "query": query,
                                    "tags": "ask_hn",
                                    "numericFilters": f"points>{min_points},num_comments>{min_comments}",
                                    "hitsPerPage": 50,
                                },
                                timeout=15,
                            )
                            if resp.status_code != 200:
                                raise CollectorUnavailableError(f"Algolia returned {resp.status_code}")
                            data = resp.json()

                    for hit in data.get("hits", []):
                        source_id = hit.get("objectID") or hit.get("story_id")
                        if not source_id:
                            continue
                        source_id = str(source_id)

                        created_at_ts = hit.get("created_at_i")
                        if created_at_ts:
                            posted_dt = datetime.fromtimestamp(int(created_at_ts), tz=timezone.utc)
                        else:
                            created_at_str = hit.get("created_at")
                            if not created_at_str:
                                dropped_stale += 1
                                continue
                            posted_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                        if posted_dt < cutoff:
                            dropped_stale += 1
                            continue

                        if source_id in items:
                            items[source_id]["metadata"]["matched_queries"].append(query)
                            continue

                        hn_url = f"https://news.ycombinator.com/item?id={source_id}"
                        items[source_id] = {
                            "source_id": source_id,
                            "title": hit.get("title") or hit.get("story_title") or "",
                            "body": hit.get("story_text") or hit.get("comment_text") or None,
                            "url": hit.get("url") or hn_url,
                            "score": int(hit.get("points") or 0),
                            "comment_count": int(hit.get("num_comments") or 0),
                            "posted_at": posted_dt.isoformat(),
                            "metadata": {
                                "categories": ["ask_hn"],
                                "author": hit.get("author"),
                                "hn_url": hn_url,
                                "matched_queries": [query],
                            },
                        }
                except Exception as exc:
                    logger.warning("hn_query_failed", query=query, error=str(exc))
                    errors.append(f"query '{query}': {exc}")

            if dropped_stale:
                logger.info("hn_stale_dropped", count=dropped_stale, window_hours=settings.freshness_hn_hours)

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
            logger.exception("hn_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name,
                items=[],
                run_id="",
                status="failed",
                items_collected=0,
                error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

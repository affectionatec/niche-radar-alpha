"""Hacker News data collector."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import structlog
import requests
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import (
    BaseCollector,
    CollectorResult,
    CollectorUnavailableError,
)

logger = structlog.get_logger()


class HackerNewsCollector(BaseCollector):
    source_name = "hn"

    def collect(self, settings, dry_run: bool = False) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            from hackernews import HackerNews

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(
                    multiplier=1,
                    exp_base=max(2, int(settings.retry_backoff_base or 2)),
                    min=1,
                    max=15,
                ),
                reraise=True,
            )
            hn = HackerNews()
            cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.freshness_hn_hours)
            items: dict[str, dict] = {}
            errors: list[str] = []
            dropped_stale = 0
            sources = {
                "top": lambda: hn.top_stories(limit=50),
                "best": lambda: self._best_stories(hn, limit=50),
                "ask": lambda: hn.ask_stories(limit=30),
                "show": lambda: hn.show_stories(limit=30),
            }

            for label, fetch in sources.items():
                try:
                    for attempt in retryer:
                        with attempt:
                            stories = fetch()
                    for story in stories or []:
                        source_id = str(getattr(story, "item_id", ""))
                        if not source_id:
                            continue

                        # Freshness filter — drop stories outside the HN window
                        submission_time = getattr(story, "submission_time", None)
                        posted_iso: str | None = None
                        if submission_time is not None:
                            try:
                                posted_dt = submission_time if isinstance(submission_time, datetime) else None
                                if posted_dt is None:
                                    iso = getattr(submission_time, "isoformat", lambda: None)()
                                    if iso:
                                        posted_dt = datetime.fromisoformat(iso)
                                if posted_dt is not None:
                                    if posted_dt.tzinfo is None:
                                        posted_dt = posted_dt.replace(tzinfo=timezone.utc)
                                    if posted_dt < cutoff:
                                        dropped_stale += 1
                                        continue
                                    posted_iso = posted_dt.isoformat()
                            except (ValueError, TypeError, AttributeError):
                                pass
                        if posted_iso is None:
                            # No submission_time → can't verify freshness → drop
                            dropped_stale += 1
                            continue

                        item = items.setdefault(
                            source_id,
                            {
                                "source_id": source_id,
                                "title": getattr(story, "title", None),
                                "body": getattr(story, "text", None),
                                "url": getattr(story, "url", None)
                                or f"https://news.ycombinator.com/item?id={source_id}",
                                "score": getattr(story, "score", 0) or 0,
                                "comment_count": getattr(story, "descendants", 0) or 0,
                                "posted_at": posted_iso,
                                "metadata": {
                                    "categories": [],
                                    "author": getattr(story, "by", None),
                                    "submission_time": posted_iso,
                                    "hn_url": f"https://news.ycombinator.com/item?id={source_id}",
                                },
                            },
                        )
                        if label not in item["metadata"]["categories"]:
                            item["metadata"]["categories"].append(label)
                except Exception as exc:
                    logger.warning("hn_source_failed", source=label, error=str(exc))
                    errors.append(f"{label}: {exc}")

            collected = list(items.values())
            if dropped_stale:
                logger.info("hn_stale_dropped", count=dropped_stale, window_hours=settings.freshness_hn_hours)
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

    def _best_stories(self, hn, limit: int):
        if hasattr(hn, "best_stories"):
            return hn.best_stories(limit=limit)
        response = requests.get(
            "https://hacker-news.firebaseio.com/v0/beststories.json", timeout=15
        )
        if response.status_code != 200:
            raise CollectorUnavailableError(f"beststories failed: {response.status_code}")
        return hn.get_items_by_ids(response.json()[:limit])

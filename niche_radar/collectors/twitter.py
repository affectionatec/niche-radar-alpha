"""Twitter / X collector via Twitter API v2 (tweepy).

⚠️  FREE TIER LIMITATION: Twitter API v2 free tier allows only ~500 posts/month read.
    This collector will exhaust that quota in a single run. Disable it unless you have
    a Basic ($100/mo) or Pro account, which allows 10k-1M reads/month.

Uses configurable search queries from the per-source settings.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import BaseCollector, CollectorResult, CollectorUnavailableError
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

DEFAULT_SEARCH_QUERIES = [
    "someone should build",
    "I wish there was",
    "why doesn't * support",
    "still doing this manually",
    "we do this manually",
    "is there a tool that",
]

_FIELDS = "id,text,created_at,public_metrics,author_id"


class TwitterCollector(BaseCollector):
    source_name = "twitter"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "bearer_token", "label": "Bearer Token (required)", "secret": True, "optional": False,
         "help": "From developer.twitter.com — Basic/Pro account recommended (free = 500 posts/mo)"},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True,
         "help": "Pain-point search phrases"},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        bearer_token = get_source_credential(db, "twitter", "bearer_token", None)
        if not bearer_token:
            return False, "Twitter bearer_token not set"
        try:
            import tweepy
            client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=False)
            # Cheapest call: search for 1 tweet
            resp = client.search_recent_tweets(query="test", max_results=10, tweet_fields=["id"])
            if resp is not None:
                return True, "Twitter API v2 connection OK"
            return False, "Empty response from Twitter API"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            import tweepy

            bearer_token = get_source_credential(db, "twitter", "bearer_token", None) if db else None
            if not bearer_token:
                raise CollectorUnavailableError("Twitter bearer_token not configured")

            raw_queries = (get_source_credential(db, "twitter", "search_queries", None) if db else None)
            search_queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            client = tweepy.Client(bearer_token=bearer_token, wait_on_rate_limit=True)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=getattr(settings, "freshness_twitter_hours", 48))
            items: dict[str, dict] = {}
            errors: list[str] = []

            for query in search_queries:
                try:
                    # Exclude retweets and replies to focus on original pain expressions
                    full_query = f"({query}) -is:retweet -is:reply lang:en"
                    resp = client.search_recent_tweets(
                        query=full_query,
                        max_results=10,  # minimal per query to conserve free quota
                        tweet_fields=["id", "text", "created_at", "public_metrics"],
                    )
                    if not resp or not resp.data:
                        continue

                    for tweet in resp.data:
                        tweet_id = str(tweet.id)
                        if tweet_id in items:
                            continue
                        created = tweet.created_at
                        if created and created.replace(tzinfo=timezone.utc) < cutoff:
                            continue
                        metrics = tweet.public_metrics or {}
                        items[tweet_id] = {
                            "source_id": tweet_id,
                            "title": tweet.text[:140],
                            "body": tweet.text,
                            "url": f"https://twitter.com/i/web/status/{tweet_id}",
                            "score": (metrics.get("like_count") or 0) + (metrics.get("retweet_count") or 0),
                            "comment_count": metrics.get("reply_count") or 0,
                            "posted_at": created.isoformat() if created else None,
                            "metadata": {
                                "matched_query": query,
                                "like_count": metrics.get("like_count"),
                                "retweet_count": metrics.get("retweet_count"),
                                "reply_count": metrics.get("reply_count"),
                                "quote_count": metrics.get("quote_count"),
                            },
                        }
                except tweepy.errors.Forbidden as exc:
                    logger.warning("twitter_quota_exceeded", query=query, error=str(exc))
                    errors.append(f"quota/forbidden: {exc}")
                    break  # stop further queries if we hit plan limits
                except Exception as exc:
                    logger.warning("twitter_query_failed", query=query, error=str(exc))
                    errors.append(f"query '{query}': {exc}")

            collected = list(items.values())
            status = "completed" if not errors else "partial" if collected else "failed"
            return CollectorResult(
                source=self.source_name, items=collected, run_id="",
                status=status, items_collected=len(collected),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            logger.exception("twitter_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

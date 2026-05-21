"""Reddit data collector — search-based pain-point discovery."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import (
    BaseCollector,
    CollectorResult,
    CollectorUnavailableError,
)
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

DEFAULT_SUBREDDITS = [
    "SaaS",
    "selfhosted",
    "webdev",
    "smallbusiness",
    "Entrepreneur",
    "sideproject",
    "macapps",
    "devops",
    "dataengineering",
    "nocode",
    "SideProject",
    "cscareerquestions",
    "artificial",
    "sysadmin",
]

DEFAULT_SEARCH_QUERIES = [
    "I wish there was",
    "is there a tool that",
    "we do this manually",
    "still using spreadsheets",
    "anyone built something",
    "how do you automate",
    "alternative to",
    "pricing is crazy",
    "looking for a tool",
    "frustrated with",
]


class RedditCollector(BaseCollector):
    source_name = "reddit"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "client_id", "label": "Client ID", "secret": False, "optional": False, "help": "From reddit.com/prefs/apps"},
        {"key": "client_secret", "label": "Client Secret", "secret": True, "optional": False, "help": "OAuth2 app secret"},
        {"key": "user_agent", "label": "User Agent", "secret": False, "optional": True, "help": "Default: NicheRadar/0.1"},
        {"key": "subreddits", "label": "Subreddits (JSON array)", "secret": False, "optional": True, "help": "e.g. [\"SaaS\",\"devops\"]"},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True, "help": "Pain-point search phrases"},
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        client_id = get_source_credential(db, "reddit", "client_id", settings.reddit_client_id)
        client_secret = get_source_credential(db, "reddit", "client_secret", settings.reddit_client_secret)
        if not client_id or not client_secret:
            return False, "Reddit credentials not set"
        try:
            import praw
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=get_source_credential(db, "reddit", "user_agent", settings.reddit_user_agent) or "NicheRadar/0.1",
            )
            # Cheapest auth check: read-only request to user identity
            _ = reddit.auth.scopes()
            return True, "Reddit connection OK (read-only)"
        except Exception as exc:
            return False, str(exc)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            client_id = get_source_credential(db, "reddit", "client_id", settings.reddit_client_id) if db else settings.reddit_client_id
            client_secret = get_source_credential(db, "reddit", "client_secret", settings.reddit_client_secret) if db else settings.reddit_client_secret
            user_agent = (get_source_credential(db, "reddit", "user_agent", None) if db else None) or settings.reddit_user_agent

            if not client_id or not client_secret:
                raise CollectorUnavailableError("Reddit credentials not configured")

            # Load configurable lists (DB first, then defaults)
            raw_subs = (get_source_credential(db, "reddit", "subreddits", None) if db else None)
            subreddits: list[str] = json.loads(raw_subs) if raw_subs else DEFAULT_SUBREDDITS

            raw_queries = (get_source_credential(db, "reddit", "search_queries", None) if db else None)
            search_queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            import praw

            retryer = Retrying(
                stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
                wait=wait_exponential(multiplier=1, exp_base=max(2, int(settings.retry_backoff_base or 2)), min=1, max=30),
                reraise=True,
            )
            reddit = praw.Reddit(client_id=client_id, client_secret=client_secret, user_agent=user_agent)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.freshness_reddit_hours)
            subreddit_str = "+".join(subreddits)  # multi-sub search
            items: dict[str, dict] = {}
            errors: list[str] = []

            for query in search_queries:
                try:
                    for attempt in retryer:
                        with attempt:
                            submissions = list(
                                reddit.subreddit(subreddit_str).search(
                                    query, sort="new", time_filter="week", limit=100
                                )
                            )
                    for submission in submissions:
                        if submission.id in items:
                            # Already collected from a prior query — append this query as a match
                            items[submission.id]["metadata"]["matched_queries"].append(query)
                            continue
                        created_at = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                        if created_at < cutoff:
                            continue
                        items[submission.id] = {
                            "source_id": str(submission.id),
                            "title": submission.title,
                            "body": submission.selftext or None,
                            "url": f"https://www.reddit.com{submission.permalink}",
                            "score": int(submission.score or 0),
                            "comment_count": int(submission.num_comments or 0),
                            "posted_at": created_at.isoformat(),
                            "metadata": {
                                "subreddit": submission.subreddit.display_name,
                                "author": str(submission.author) if submission.author else None,
                                "post_flair": submission.link_flair_text,
                                "external_url": submission.url,
                                "matched_queries": [query],
                                "has_pain_point_signal": True,
                            },
                        }
                except Exception as exc:
                    logger.warning("reddit_query_failed", query=query, error=str(exc))
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
            logger.exception("reddit_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name,
                items=[],
                run_id="",
                status="failed",
                items_collected=0,
                error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

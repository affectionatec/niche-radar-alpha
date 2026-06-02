"""Shared plumbing for X capture backends.

Defines the normalized :class:`ParsedTweet`, the credential/cutoff helpers, and
:class:`XBackend` — a :class:`SourceBackend` whose ``fetch`` runs the configured
pain-point search queries through a backend-specific ``search_one`` and
normalizes the results into Niche Radar's raw-item shape.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import structlog

from niche_radar.collectors.multi_backend import SourceBackend
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

# Pain-point search phrases — the same defaults the single-path collector used.
DEFAULT_SEARCH_QUERIES = [
    "someone should build",
    "I wish there was",
    "why doesn't * support",
    "still doing this manually",
    "we do this manually",
    "is there a tool that",
]

# Polite pacing between queries so we never hammer a backend.
INTER_QUERY_DELAY = 0.8


@dataclass
class ParsedTweet:
    """Backend-agnostic tweet, normalized by :meth:`XBackend.fetch`."""

    id: str
    text: str
    author: str | None = None
    created_at: datetime | None = None
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    url: str | None = None
    matched_queries: list[str] = field(default_factory=list)


def parse_twitter_date(date_str: str | None) -> datetime | None:
    """Parse the several date shapes X backends emit, returning aware UTC."""
    if not date_str:
        return None
    # ISO 8601 (Xquik, xAI date field as YYYY-MM-DD)
    try:
        dt = datetime.fromisoformat(str(date_str).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        pass
    # Twitter's legacy format: 'Wed Oct 10 20:19:24 +0000 2018'
    try:
        return datetime.strptime(str(date_str), "%a %b %d %H:%M:%S %z %Y")
    except (ValueError, TypeError):
        return None


def freshness_cutoff(settings) -> datetime:
    """Drop tweets older than ``freshness_twitter_hours`` (default 48h)."""
    hours = getattr(settings, "freshness_twitter_hours", 48)
    return datetime.now(timezone.utc) - timedelta(hours=hours)


def tweet_url(t: ParsedTweet) -> str:
    """Best available permalink for a tweet."""
    if t.url:
        return t.url
    if t.author and t.id:
        return f"https://x.com/{t.author}/status/{t.id}"
    return f"https://x.com/i/web/status/{t.id}"


def read_search_queries(db: sqlite3.Connection | None) -> list[str]:
    """Configured pain-point queries (JSON array) or the defaults."""
    raw = get_source_credential(db, "twitter", "search_queries", None) if db else None
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return [str(q) for q in parsed]
        except (ValueError, TypeError):
            logger.warning("twitter_search_queries_parse_failed")
    return DEFAULT_SEARCH_QUERIES


def resolve_credential(
    db: sqlite3.Connection | None, key: str, *env_names: str, settings=None, settings_attr: str | None = None
) -> str | None:
    """Resolve a credential: per-source DB value → settings attr → env vars.

    Mirrors last30days' layered resolution, adapted to Niche Radar's SQLite
    per-source credential store as the highest-priority source.
    """
    import os

    val = get_source_credential(db, "twitter", key, None) if db else None
    if val:
        return val
    if settings is not None and settings_attr:
        val = getattr(settings, settings_attr, "") or None
        if val:
            return val
    for name in env_names:
        val = os.environ.get(name)
        if val:
            return val
    return None


class XBackend(SourceBackend):
    """A search-X backend. Subclasses implement :meth:`search_one`."""

    name: str = "x"

    def search_one(self, query: str, settings, db: sqlite3.Connection | None) -> list[ParsedTweet]:
        """Return tweets for a single query. Raise to signal backend failure."""
        raise NotImplementedError

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        queries = read_search_queries(db)
        cutoff = freshness_cutoff(settings)
        by_id: dict[str, ParsedTweet] = {}

        for i, query in enumerate(queries):
            tweets = self.search_one(query, settings, db)
            for t in tweets:
                if not t.id:
                    continue
                if t.created_at and t.created_at < cutoff:
                    continue
                if t.id in by_id:
                    if query not in by_id[t.id].matched_queries:
                        by_id[t.id].matched_queries.append(query)
                    continue
                t.matched_queries = [query]
                by_id[t.id] = t
            if i < len(queries) - 1:
                time.sleep(INTER_QUERY_DELAY)

        return [self._to_item(t) for t in by_id.values()]

    def _to_item(self, t: ParsedTweet) -> dict:
        """Normalize a :class:`ParsedTweet` to the raw-item dict the DB expects."""
        return {
            "source_id": t.id,
            "title": t.text[:140],
            "body": t.text,
            "url": tweet_url(t),
            "score": (t.likes or 0) + (t.retweets or 0),
            "comment_count": t.replies or 0,
            "posted_at": t.created_at.isoformat() if t.created_at else None,
            "metadata": {
                "matched_queries": t.matched_queries,
                "author": t.author,
                "like_count": t.likes,
                "retweet_count": t.retweets,
                "reply_count": t.replies,
                "auth_mode": self.name,
            },
        }

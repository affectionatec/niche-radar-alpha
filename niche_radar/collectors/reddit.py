"""Reddit data collector — a resilient multi-backend source (ADR-002, ADR-006).

Capture walks an ordered chain:

    1. praw         — official Reddit API (when client_id/secret are configured)
    2. public_json  — keyless reddit.com/search.json (no credentials)
    3. jina_reader  — opt-in r.jina.ai fallback when the public JSON is blocked
                      (datacenter IPs get HTTP 403 from Reddit); reads the search
                      page through the relay so the source stays alive.

Search-based pain-point discovery over a configurable set of subreddits/queries.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import ClassVar
from urllib.parse import quote

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors import reddit_public
from niche_radar.collectors.backends import JinaReaderBackend
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
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

_JINA_CREDENTIALS: list[dict] = [
    {"key": "jina_fallback", "label": "Enable Jina Reader fallback", "secret": False, "optional": True,
     "help": "When PRAW and the public JSON are both blocked (e.g. HTTP 403 from a datacenter IP), read Reddit search via r.jina.ai. Set to 'true' to enable."},
    {"key": "jina_api_key", "label": "Jina Reader API key (optional)", "secret": True, "optional": True,
     "help": "Optional — raises Jina rate limits and enables the fallback on its own. Get one at jina.ai/reader."},
]


def _config(settings, db: sqlite3.Connection | None) -> tuple[list[str], list[str], datetime]:
    """Resolve subreddits, queries, and the freshness cutoff (DB overrides defaults)."""
    raw_subs = get_source_credential(db, "reddit", "subreddits", None) if db else None
    subreddits = json.loads(raw_subs) if raw_subs else DEFAULT_SUBREDDITS
    raw_queries = get_source_credential(db, "reddit", "search_queries", None) if db else None
    queries = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.freshness_reddit_hours)
    return subreddits, queries, cutoff


def _creds(settings, db: sqlite3.Connection | None) -> tuple[str | None, str | None, str]:
    cid = get_source_credential(db, "reddit", "client_id", settings.reddit_client_id) if db else settings.reddit_client_id
    csecret = get_source_credential(db, "reddit", "client_secret", settings.reddit_client_secret) if db else settings.reddit_client_secret
    user_agent = (get_source_credential(db, "reddit", "user_agent", None) if db else None) or settings.reddit_user_agent
    return cid, csecret, user_agent


def _reddit_search_urls(settings, db: sqlite3.Connection | None) -> list[str]:
    subreddits, queries, _ = _config(settings, db)
    subs = "+".join(subreddits)
    return [
        f"https://www.reddit.com/r/{subs}/search/?q={quote(q)}&restrict_sr=1&sort=new&t=week"
        for q in queries
    ]


class RedditPrawBackend(SourceBackend):
    """Primary path — official Reddit API via PRAW (requires client_id/secret)."""

    name = "praw"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        cid, csecret, _ = _creds(settings, db)
        return bool(cid and csecret)

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        import praw

        cid, csecret, user_agent = _creds(settings, db)
        subreddits, queries, cutoff = _config(settings, db)
        retryer = Retrying(
            stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
            wait=wait_exponential(multiplier=1, exp_base=max(2, int(settings.retry_backoff_base or 2)), min=1, max=30),
            reraise=True,
        )
        reddit = praw.Reddit(client_id=cid, client_secret=csecret, user_agent=user_agent)
        subreddit_str = "+".join(subreddits)
        items: dict[str, dict] = {}
        errors: list[str] = []

        for query in queries:
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
        if not collected and errors:
            # PRAW ran but captured nothing → signal failure so the chain falls
            # through to the public-json / jina tiers.
            raise RuntimeError("; ".join(errors))
        return collected


class RedditPublicJsonBackend(SourceBackend):
    """Keyless path — reddit.com/search.json (no credentials needed)."""

    name = "public_json"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return True

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        subreddits, queries, cutoff = _config(settings, db)
        items, errors = reddit_public.search_public(subreddits, queries, cutoff)
        if not items and errors:
            raise RuntimeError("; ".join(errors))
        return items


class RedditCollector(MultiBackendCollector):
    source_name = "reddit"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "client_id", "label": "Client ID", "secret": False, "optional": False, "help": "From reddit.com/prefs/apps"},
        {"key": "client_secret", "label": "Client Secret", "secret": True, "optional": False, "help": "OAuth2 app secret"},
        {"key": "user_agent", "label": "User Agent", "secret": False, "optional": True, "help": "Default: NicheRadar/0.1"},
        {"key": "subreddits", "label": "Subreddits (JSON array)", "secret": False, "optional": True, "help": "e.g. [\"SaaS\",\"devops\"]"},
        {"key": "search_queries", "label": "Search queries (JSON array)", "secret": False, "optional": True, "help": "Pain-point search phrases"},
        *_JINA_CREDENTIALS,
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [
            RedditPrawBackend(),
            RedditPublicJsonBackend(),
            JinaReaderBackend("reddit", _reddit_search_urls),
        ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        cid, csecret, user_agent = _creds(settings, db)
        if cid and csecret:
            try:
                import praw

                reddit = praw.Reddit(client_id=cid, client_secret=csecret, user_agent=user_agent or "NicheRadar/0.1")
                _ = reddit.auth.scopes()
                return True, "✓ Reddit will use the official API (PRAW)"
            except Exception as exc:
                return False, f"PRAW credentials set but failed: {exc}"
        # Keyless public JSON always available; report it (plus the optional Jina tier).
        from niche_radar.collectors import _jina

        if _jina.is_enabled(settings, db, "reddit"):
            return True, "No API key — using keyless public JSON (Jina Reader fallback enabled)"
        return True, "No API key — using keyless public JSON (enable the Jina Reader fallback for 403-resilience)"

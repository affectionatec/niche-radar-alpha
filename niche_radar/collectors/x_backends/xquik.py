"""Xquik REST-API backend (ported from last30days lib/xquik.py).

Xquik returns tweets with full engagement metrics in a single REST call and
needs only ``XQUIK_API_KEY``. Pure HTTP — no cookies, no scraping — so it sits
just below xAI in the X fallback chain.
"""

from __future__ import annotations

import sqlite3

import structlog

from niche_radar.collectors import _http
from niche_radar.collectors.x_backends.base import ParsedTweet, XBackend, parse_twitter_date, resolve_credential

logger = structlog.get_logger()

_BASE_URL = "https://xquik.com/api/v1/x/tweets/search"
_LIMIT = 20


class XquikBackend(XBackend):
    name = "xquik"

    def _token(self, settings, db) -> str | None:
        return resolve_credential(db, "xquik_api_key", "XQUIK_API_KEY", settings=settings, settings_attr="xquik_api_key")

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return bool(self._token(settings, db))

    def search_one(self, query: str, settings, db: sqlite3.Connection | None) -> list[ParsedTweet]:
        token = self._token(settings, db)
        if not token:
            return []
        resp = _http.get_json(
            _BASE_URL,
            headers={"X-Api-Key": token},
            params={"q": query, "queryType": "Top", "limit": _LIMIT},
            timeout=30,
            retries=2,
        )
        tweets = resp.get("tweets") if isinstance(resp, dict) else None
        if not isinstance(tweets, list):
            return []
        out: list[ParsedTweet] = []
        for tw in tweets:
            parsed = _parse_tweet(tw)
            if parsed:
                out.append(parsed)
        return out


def _parse_tweet(tweet: dict) -> ParsedTweet | None:
    if not isinstance(tweet, dict):
        return None
    tid = str(tweet.get("id", ""))
    if not tid:
        return None
    author = tweet.get("author") or {}
    username = str(author.get("username", "")).lstrip("@") or None
    return ParsedTweet(
        id=tid,
        text=str(tweet.get("text", "")).strip()[:500],
        author=username,
        created_at=parse_twitter_date(tweet.get("createdAt")),
        likes=_int(tweet.get("likeCount")),
        retweets=_int(tweet.get("retweetCount")),
        replies=_int(tweet.get("replyCount")),
        url=f"https://x.com/{username}/status/{tid}" if username else None,
    )


def _int(value) -> int:
    try:
        return int(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0

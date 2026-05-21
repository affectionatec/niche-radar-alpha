"""Twitter / X collector — GraphQL internal API with cookie auth.

Uses Twitter's internal GraphQL SearchTimeline endpoint, identical to what
the twitter.com web app uses. No OAuth application required.

Setup (see Settings → Data Sources → Twitter):
  1. Log into x.com in Chrome
  2. DevTools (F12) → Application → Cookies → x.com
  3. Copy `ct0` value  → paste in ct0 field
  4. Copy `auth_token` value → paste in auth_token field
  5. Click "Test Connection" to verify

If "Test Connection" returns 404: the GraphQL query ID has rotated.
  → Open DevTools → Network → search something → find the SearchTimeline XHR
  → Copy the ID from the URL path and paste it into the "Search Query ID" field.

Error reference:
  400 → features param missing or malformed
  401 → auth_token invalid/expired — re-copy from browser
  403 → x-csrf-token wrong — must equal ct0 value exactly
  404 → query ID stale — get fresh one from DevTools
  429 → rate limited — slow down collection interval
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import requests
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import BaseCollector, CollectorResult, CollectorUnavailableError
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

# Twitter's app-level bearer token — shared by all web browser clients.
# This is NOT a per-user OAuth token; it's embedded in Twitter's JS bundle.
_APP_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Default GraphQL query ID for SearchTimeline.
# This rotates periodically — configure via Settings if it stops working.
_DEFAULT_QUERY_ID = "nLP0wk09iJZPMQhp0orkdg"

# Required features dict for the GraphQL endpoint.
# Missing keys → 400 Bad Request.
_FEATURES = {
    "rweb_lists_timeline_redesign_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "tweetypie_unmention_optimization_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "freedom_of_speech_not_reach_the_tweet_result_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
    "interactive_text_enabled": True,
    "responsive_web_text_underlines_enabled": False,
    "longform_notetweets_richtext_consumption_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_enhance_cards_enabled": False,
}

DEFAULT_SEARCH_QUERIES = [
    "someone should build",
    "I wish there was",
    "why doesn't * support",
    "still doing this manually",
    "we do this manually",
    "is there a tool that",
]


class TwitterCollector(BaseCollector):
    source_name = "twitter"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {
            "key": "ct0",
            "label": "ct0 cookie",
            "secret": True,
            "optional": False,
            "help": "Log into x.com → DevTools (F12) → Application → Cookies → x.com → copy ct0",
        },
        {
            "key": "auth_token",
            "label": "auth_token cookie",
            "secret": True,
            "optional": False,
            "help": "Same Cookies panel → copy auth_token. Both ct0 + auth_token are required.",
        },
        {
            "key": "graphql_query_id",
            "label": "SearchTimeline Query ID (optional — update if you get 404)",
            "secret": False,
            "optional": True,
            "help": (
                f"Default: {_DEFAULT_QUERY_ID}. "
                "If collecting fails with 404, get the fresh ID from DevTools → Network "
                "→ filter 'SearchTimeline' → copy the ID segment from the URL."
            ),
        },
        {
            "key": "proxy_url",
            "label": "Proxy URL (required if Twitter is blocked in your region)",
            "secret": True,
            "optional": True,
            "help": (
                "HTTP/HTTPS/SOCKS5 proxy to reach Twitter/X. "
                "Examples: http://user:pass@host:port  |  socks5://host:port  |  http://host:port. "
                "Required if you see '198.18.x.x' DNS or empty 404 errors."
            ),
        },
        {
            "key": "search_queries",
            "label": "Search queries (JSON array, optional)",
            "secret": False,
            "optional": True,
            "help": 'Pain-point phrases, e.g. ["I wish there was","is there a tool that"]',
        },
    ]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        ct0 = get_source_credential(db, "twitter", "ct0", None)
        auth_token = get_source_credential(db, "twitter", "auth_token", None)
        if not ct0 or not auth_token:
            return False, "ct0 and auth_token are both required. Copy them from your browser's cookie panel."
        query_id = get_source_credential(db, "twitter", "graphql_query_id", _DEFAULT_QUERY_ID) or _DEFAULT_QUERY_ID
        return _test_graphql_auth(ct0, auth_token, query_id)

    def collect(
        self, settings, dry_run: bool = False, db: sqlite3.Connection | None = None
    ) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            ct0 = get_source_credential(db, "twitter", "ct0", None) if db else None
            auth_token = get_source_credential(db, "twitter", "auth_token", None) if db else None
            if not ct0 or not auth_token:
                raise CollectorUnavailableError(
                    "ct0 and auth_token cookies are required. "
                    "Configure them via Settings → Data Sources → Twitter / X."
                )

            query_id = (
                get_source_credential(db, "twitter", "graphql_query_id", _DEFAULT_QUERY_ID)
                or _DEFAULT_QUERY_ID
            ) if db else _DEFAULT_QUERY_ID

            raw_queries = get_source_credential(db, "twitter", "search_queries", None) if db else None
            search_queries: list[str] = json.loads(raw_queries) if raw_queries else DEFAULT_SEARCH_QUERIES

            cutoff = datetime.now(timezone.utc) - timedelta(
                hours=getattr(settings, "freshness_twitter_hours", 48)
            )

            items, errors = _collect_graphql(ct0, auth_token, query_id, search_queries, cutoff)

            status = "completed" if not errors else "partial" if items else "failed"
            return CollectorResult(
                source=self.source_name, items=items, run_id="",
                status=status, items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except CollectorUnavailableError:
            raise
        except Exception as exc:
            logger.exception("twitter_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name, items=[], run_id="", status="failed",
                items_collected=0, error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )


# ── GraphQL implementation ────────────────────────────────────────────────────

def _headers(ct0: str, auth_token: str) -> dict:
    """Headers required by Twitter's internal GraphQL API.

    Key points from x.md:
    - Cookie must be a single header string (not split)
    - x-csrf-token must equal ct0 exactly
    - Authorization uses the shared web app bearer token
    """
    return {
        "Authorization": f"Bearer {_APP_BEARER}",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "x-csrf-token": ct0,
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "content-type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _test_graphql_auth(ct0: str, auth_token: str, query_id: str) -> tuple[bool, str]:
    """Test credentials with a minimal GraphQL search (1 result)."""
    try:
        variables = {"rawQuery": "test", "count": 1, "querySource": "typed_query", "product": "Latest"}
        resp = requests.get(
            f"https://twitter.com/i/api/graphql/{query_id}/SearchTimeline",
            headers=_headers(ct0, auth_token),
            params={"variables": json.dumps(variables), "features": json.dumps(_FEATURES)},
            timeout=12,
        )
        if resp.status_code == 200:
            return True, f"Cookie auth OK (query_id={query_id})"
        if resp.status_code == 401:
            return False, "auth_token invalid or expired — re-copy from browser cookies"
        if resp.status_code == 403:
            return False, "Forbidden: x-csrf-token mismatch — ensure ct0 is copied correctly"
        if resp.status_code == 404:
            return False, (
                f"Query ID '{query_id}' is stale (404). "
                "Open DevTools → Network → search something on x.com → "
                "find the SearchTimeline XHR → copy the ID from the URL → "
                "paste it into the 'SearchTimeline Query ID' field."
            )
        return False, f"HTTP {resp.status_code}: {resp.text[:120]}"
    except Exception as exc:
        return False, f"Connection error: {exc}"


def _parse_tweets(response_json: dict) -> list[dict]:
    """Parse GraphQL SearchTimeline response.

    Path (from x.md §5):
    data.search_by_raw_query.search_timeline.timeline.instructions[]
      → type == "TimelineAddEntries"
      → entries[].content.itemContent.tweet_results.result
    """
    instructions = (
        response_json
        .get("data", {})
        .get("search_by_raw_query", {})
        .get("search_timeline", {})
        .get("timeline", {})
        .get("instructions", [])
    )
    tweets: list[dict] = []
    for instruction in instructions:
        if instruction.get("type") != "TimelineAddEntries":
            continue
        for entry in instruction.get("entries", []):
            try:
                result = entry["content"]["itemContent"]["tweet_results"]["result"]
                legacy = result["legacy"]
                user = result["core"]["user_results"]["result"]["legacy"]
                tweets.append({
                    "id": result["rest_id"],
                    "text": legacy.get("full_text", ""),
                    "created_at": legacy.get("created_at"),
                    "author": user.get("screen_name"),
                    "likes": legacy.get("favorite_count", 0),
                    "retweets": legacy.get("retweet_count", 0),
                    "replies": legacy.get("reply_count", 0),
                    "is_retweet": legacy.get("full_text", "").startswith("RT @"),
                })
            except (KeyError, TypeError):
                continue
    return tweets


def _parse_tweet_date(date_str: str | None) -> datetime | None:
    """Parse Twitter's date format: 'Wed Oct 10 20:19:24 +0000 2018'"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
    except (ValueError, TypeError):
        return None


def _collect_graphql(
    ct0: str,
    auth_token: str,
    query_id: str,
    search_queries: list[str],
    cutoff: datetime,
) -> tuple[list[dict], list[str]]:
    """Search tweets via GraphQL SearchTimeline endpoint."""
    retryer = Retrying(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    )
    headers = _headers(ct0, auth_token)
    items: dict[str, dict] = {}
    errors: list[str] = []

    for query in search_queries:
        try:
            variables = {
                "rawQuery": f"({query}) -filter:retweets lang:en",
                "count": 20,
                "querySource": "typed_query",
                "product": "Latest",
            }
            for attempt in retryer:
                with attempt:
                    resp = requests.get(
                        f"https://twitter.com/i/api/graphql/{query_id}/SearchTimeline",
                        headers=headers,
                        params={
                            "variables": json.dumps(variables),
                            "features": json.dumps(_FEATURES),
                        },
                        timeout=15,
                    )
                    if resp.status_code == 401:
                        raise CollectorUnavailableError(
                            "auth_token expired — re-copy from browser cookies"
                        )
                    if resp.status_code == 403:
                        raise CollectorUnavailableError(
                            "Forbidden: ct0/x-csrf-token mismatch — re-copy cookies"
                        )
                    if resp.status_code == 404:
                        raise CollectorUnavailableError(
                            f"GraphQL query ID '{query_id}' is stale. "
                            "Get the fresh ID from DevTools → Network → SearchTimeline XHR URL, "
                            "then update it in Settings → Data Sources → Twitter / X."
                        )
                    if resp.status_code == 429:
                        raise CollectorUnavailableError("Rate limited — reduce collection frequency")
                    if resp.status_code != 200:
                        raise ConnectionError(f"HTTP {resp.status_code}: {resp.text[:120]}")

            parsed = _parse_tweets(resp.json())
            for t in parsed:
                tid = t["id"]
                if tid in items:
                    items[tid]["metadata"]["matched_queries"].append(query)
                    continue
                if t.get("is_retweet"):
                    continue
                created = _parse_tweet_date(t["created_at"])
                if created and created < cutoff:
                    continue
                text = t["text"]
                items[tid] = {
                    "source_id": tid,
                    "title": text[:140],
                    "body": text,
                    "url": f"https://x.com/i/web/status/{tid}",
                    "score": (t.get("likes") or 0) + (t.get("retweets") or 0),
                    "comment_count": t.get("replies") or 0,
                    "posted_at": created.isoformat() if created else None,
                    "metadata": {
                        "matched_queries": [query],
                        "author": t.get("author"),
                        "like_count": t.get("likes"),
                        "retweet_count": t.get("retweets"),
                        "reply_count": t.get("replies"),
                        "auth_mode": "cookie_graphql",
                    },
                }
            time.sleep(0.8)  # polite pacing
        except CollectorUnavailableError:
            raise
        except Exception as exc:
            logger.warning("twitter_graphql_query_failed", query=query, error=str(exc))
            errors.append(f"query '{query}': {exc}")

    return list(items.values()), errors

"""Twitter / X collector — GraphQL internal API with cookie auth.

Uses Twitter's internal GraphQL SearchTimeline endpoint, identical to what
the x.com web app uses.  No OAuth application required.

Setup (see Settings → Data Sources → Twitter):
  1. Log into x.com in Chrome
  2. DevTools (F12) → Application → Cookies → x.com
  3. Copy ``ct0`` value  → paste in ct0 field
  4. Copy ``auth_token`` value → paste in auth_token field
  5. Click "Test Connection" to verify

The collector automatically discovers the current SearchTimeline query ID
and generates the required ``x-client-transaction-id`` anti-bot header by
scraping x.com's JS bundle — no manual query-ID updates needed.

Error reference:
  400 → features param missing or malformed
  401 → auth_token invalid/expired — re-copy from browser
  403 → x-csrf-token wrong — must equal ct0 value exactly
  404 → transaction-id or query-id invalid (auto-recovery attempted)
  429 → rate limited — slow down collection interval
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar
import bs4
import requests
import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import BaseCollector, CollectorResult, CollectorUnavailableError
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()

# Twitter's app-level bearer token — shared by all web browser clients.
_APP_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)

# Fallback query ID — used only if auto-discovery fails AND user hasn't set one.
_DEFAULT_QUERY_ID = "099UqLkXma7fhT81Jv4n9g"

# Current SearchTimeline features dict — extracted from x.com's main.js bundle.
_FEATURES = {
    "rweb_video_screen_enabled": False,
    "rweb_cashtags_enabled": True,
    "profile_label_improvements_pcf_label_in_post_enabled": True,
    "responsive_web_profile_redirect_enabled": False,
    "rweb_tipjar_consumption_enabled": False,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "premium_content_api_read_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "responsive_web_grok_analyze_button_fetch_trends_enabled": False,
    "responsive_web_grok_analyze_post_followups_enabled": True,
    "rweb_cashtags_composer_attachment_enabled": True,
    "responsive_web_jetfuel_frame": True,
    "responsive_web_grok_share_attachment_enabled": True,
    "responsive_web_grok_annotations_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "rweb_conversational_replies_downvote_enabled": False,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "content_disclosure_indicator_enabled": True,
    "content_disclosure_ai_generated_indicator_enabled": True,
    "responsive_web_grok_show_grok_translated_post": True,
    "responsive_web_grok_analysis_button_from_backend": True,
    "post_ctas_fetch_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": False,
    "responsive_web_grok_image_annotation_enabled": True,
    "responsive_web_grok_imagine_annotation_enabled": True,
    "responsive_web_grok_community_note_auto_translation_is_enabled": True,
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
            "label": "SearchTimeline Query ID (optional — auto-discovered if blank)",
            "secret": False,
            "optional": True,
            "help": (
                "Leave blank for auto-discovery. "
                "If auto-discovery fails, get the ID from DevTools → Network "
                "→ filter 'SearchTimeline' → copy the ID from the URL."
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
        query_id = get_source_credential(db, "twitter", "graphql_query_id", None)
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
                get_source_credential(db, "twitter", "graphql_query_id", None)
                if db else None
            )

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


# ── Anti-bot: x-client-transaction-id generation ──────────────────────────────
#
# X.com requires a cryptographically-valid x-client-transaction-id header on
# certain endpoints (SearchTimeline, etc).  The algorithm is implemented by
# twikit's ClientTransaction class.  We initialise it synchronously by fetching
# x.com's homepage, extracting the verification key / SVG animation data, and
# downloading the ondemand.s chunk to get key-byte indices.

from twikit.x_client_transaction.transaction import ClientTransaction

# Module-level cache: avoids re-scraping x.com on every request.
_transaction_ctx: ClientTransaction | None = None
_transaction_ctx_ts: float = 0.0
_TRANSACTION_TTL = 600  # re-initialise every 10 minutes


def _init_transaction_ctx() -> ClientTransaction:
    """Initialise (or refresh) the ClientTransaction context synchronously."""
    global _transaction_ctx, _transaction_ctx_ts

    if _transaction_ctx and (time.time() - _transaction_ctx_ts < _TRANSACTION_TTL):
        return _transaction_ctx

    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    # 1. Fetch x.com homepage
    home_resp = requests.get("https://x.com/", headers={"User-Agent": ua}, timeout=15)
    home_resp.raise_for_status()
    soup = bs4.BeautifulSoup(home_resp.text, "html.parser")

    # 2. Find the ondemand.s chunk hash from the webpack manifest
    #    Format: 59924:"<hash>" where 59924 is the chunk ID for ondemand.s
    chunk_manifest = home_resp.text
    # First find the chunk ID for "ondemand.s"
    chunk_id_match = re.search(r'(\d+):"ondemand\.s"', chunk_manifest)
    if not chunk_id_match:
        raise RuntimeError("Cannot find ondemand.s chunk ID in x.com homepage")
    chunk_id = chunk_id_match.group(1)
    # Then find the hash for that chunk ID
    hash_match = re.search(rf'{chunk_id}:"([a-f0-9]+)"', chunk_manifest)
    if not hash_match:
        raise RuntimeError(f"Cannot find hash for chunk {chunk_id} in x.com homepage")
    chunk_hash = hash_match.group(1)

    # 3. Fetch the ondemand.s JS file and extract key-byte indices
    ondemand_url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{chunk_hash}a.js"
    od_resp = requests.get(ondemand_url, headers={"User-Agent": ua}, timeout=15)
    od_resp.raise_for_status()

    indices_regex = re.compile(r"\(\w{1}\[(\d{1,2})\],\s*16\)")
    idx_matches = list(indices_regex.finditer(od_resp.text))
    if not idx_matches:
        raise RuntimeError("Cannot extract key-byte indices from ondemand.s")
    key_byte_indices = [int(m.group(1)) for m in idx_matches]

    # 4. Build ClientTransaction with extracted data
    ct = ClientTransaction()
    ct.home_page_response = soup
    ct.DEFAULT_ROW_INDEX = key_byte_indices[0]
    ct.DEFAULT_KEY_BYTES_INDICES = key_byte_indices[1:]
    ct.key = ct.get_key(soup)
    ct.key_bytes = ct.get_key_bytes(ct.key)
    ct.animation_key = ct.get_animation_key(ct.key_bytes, soup)

    _transaction_ctx = ct
    _transaction_ctx_ts = time.time()
    logger.info("twitter_transaction_ctx_init", chunk_hash=chunk_hash)
    return ct


def _generate_transaction_id(method: str, path: str) -> str:
    """Generate a valid x-client-transaction-id for the given request."""
    ct = _init_transaction_ctx()
    return ct.generate_transaction_id(method=method, path=path)


# ── Auto-discovery ────────────────────────────────────────────────────────────

_discovered_query_id: str | None = None
_discovered_query_id_ts: float = 0.0
_QUERY_ID_TTL = 3600  # rediscover hourly


def _discover_query_id() -> str:
    """Scrape x.com's main.js to find the current SearchTimeline query ID."""
    global _discovered_query_id, _discovered_query_id_ts

    if _discovered_query_id and (time.time() - _discovered_query_id_ts < _QUERY_ID_TTL):
        return _discovered_query_id

    ua = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    home_resp = requests.get("https://x.com/", headers={"User-Agent": ua}, timeout=15)
    home_resp.raise_for_status()

    # Find main.js URL
    main_match = re.search(r'src=["\']([^"\' ]+main\.[a-f0-9]+\.js)["\']', home_resp.text)
    if not main_match:
        logger.warning("twitter_query_id_discovery_failed", reason="main.js not found")
        return _DEFAULT_QUERY_ID

    main_js_url = main_match.group(1)
    main_resp = requests.get(main_js_url, headers={"User-Agent": ua}, timeout=30)
    main_resp.raise_for_status()

    qid_match = re.search(
        r'queryId:"([a-zA-Z0-9_-]+)",operationName:"SearchTimeline"', main_resp.text
    )
    if not qid_match:
        logger.warning("twitter_query_id_discovery_failed", reason="SearchTimeline not found in main.js")
        return _DEFAULT_QUERY_ID

    _discovered_query_id = qid_match.group(1)
    _discovered_query_id_ts = time.time()
    logger.info("twitter_query_id_discovered", query_id=_discovered_query_id)
    return _discovered_query_id


def _resolve_query_id(user_query_id: str | None) -> str:
    """Return the query ID to use: user-configured > auto-discovered > default."""
    if user_query_id:
        return user_query_id
    try:
        return _discover_query_id()
    except Exception as exc:
        logger.warning("twitter_query_id_fallback", error=str(exc))
        return _DEFAULT_QUERY_ID


# ── GraphQL implementation ────────────────────────────────────────────────────

def _headers(ct0: str, auth_token: str) -> dict:
    """Headers required by Twitter's internal GraphQL API."""
    return {
        "Authorization": f"Bearer {_APP_BEARER}",
        "Cookie": f"auth_token={auth_token}; ct0={ct0}",
        "x-csrf-token": ct0,
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
        "x-twitter-client-language": "en",
        "Referer": "https://x.com/search",
        "Accept": "*/*",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }


def _test_graphql_auth(ct0: str, auth_token: str, user_query_id: str | None) -> tuple[bool, str]:
    """Test credentials with a minimal GraphQL search (1 result)."""
    try:
        query_id = _resolve_query_id(user_query_id)
        path = f"/i/api/graphql/{query_id}/SearchTimeline"
        tid = _generate_transaction_id("GET", path)
        variables = {"rawQuery": "test", "count": 1, "querySource": "typed_query", "product": "Top"}
        hdrs = _headers(ct0, auth_token)
        hdrs["X-Client-Transaction-Id"] = tid

        resp = requests.get(
            f"https://x.com{path}",
            headers=hdrs,
            params={
                "variables": json.dumps(variables, separators=(",", ":")),
                "features": json.dumps(_FEATURES, separators=(",", ":")),
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return True, f"✓ Cookie auth OK (query_id={query_id}, auto-transaction-id)"
        if resp.status_code == 401:
            return False, "auth_token invalid or expired — re-copy from browser cookies"
        if resp.status_code == 403:
            return False, "Forbidden: x-csrf-token mismatch — ensure ct0 is copied correctly"
        if resp.status_code == 429:
            return True, "Cookie auth OK but rate-limited — wait and retry"
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
    except RuntimeError as exc:
        return False, f"Transaction ID init failed: {exc}"
    except Exception as exc:
        return False, f"Connection error: {exc}"


def _parse_tweets(response_json: dict) -> list[dict]:
    """Parse GraphQL SearchTimeline response.

    Path:
    data.search_by_raw_query.search_timeline.timeline.instructions[]
      → type == "TimelineAddEntries"
      → entries[].content.itemContent.tweet_results.result

    Some results are wrapped in TweetWithVisibilityResults — the actual
    tweet data lives under result.tweet in that case.
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
                # Unwrap TweetWithVisibilityResults
                if result.get("__typename") == "TweetWithVisibilityResults":
                    result = result["tweet"]
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
    user_query_id: str | None,
    search_queries: list[str],
    cutoff: datetime,
) -> tuple[list[dict], list[str]]:
    """Search tweets via GraphQL SearchTimeline endpoint."""
    query_id = _resolve_query_id(user_query_id)
    path = f"/i/api/graphql/{query_id}/SearchTimeline"

    retryer = Retrying(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=15),
        reraise=True,
    )
    hdrs = _headers(ct0, auth_token)
    items: dict[str, dict] = {}
    errors: list[str] = []

    for query in search_queries:
        try:
            variables = {
                "rawQuery": f"({query}) -filter:retweets lang:en",
                "count": 20,
                "querySource": "typed_query",
                "product": "Top",
            }
            for attempt in retryer:
                with attempt:
                    tid = _generate_transaction_id("GET", path)
                    hdrs["X-Client-Transaction-Id"] = tid
                    resp = requests.get(
                        f"https://x.com{path}",
                        headers=hdrs,
                        params={
                            "variables": json.dumps(variables, separators=(",", ":")),
                            "features": json.dumps(_FEATURES, separators=(",", ":")),
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
                            f"GraphQL query ID '{query_id}' returned 404. "
                            "The auto-discovered ID may be stale. Try setting it manually "
                            "via Settings → Data Sources → Twitter / X."
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

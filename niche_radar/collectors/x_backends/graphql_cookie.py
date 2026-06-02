"""Internal-GraphQL X backend with cookie auth — the legacy last-resort path.

This is the original single-path collector, demoted to the bottom of the X
fallback chain. It scrapes x.com's JS bundle for a live ``SearchTimeline``
query ID and a valid ``x-client-transaction-id`` (via twikit), then calls the
same internal GraphQL endpoint the web app uses. Every step here is fragile —
which is exactly why it now runs only when no API-key backend is configured.

``twikit`` is imported lazily so this module (and the collector) load even when
twikit isn't installed.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time

import requests
import structlog

from niche_radar.collectors.x_backends.base import ParsedTweet, XBackend, parse_twitter_date, resolve_credential

logger = structlog.get_logger()

# App-level bearer token shared by all web browser clients.
_APP_BEARER = (
    "AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs"
    "%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
)
_DEFAULT_QUERY_ID = "099UqLkXma7fhT81Jv4n9g"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
_PER_QUERY_COUNT = 20
_MAX_ATTEMPTS = 2

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


class XBackendAuthError(Exception):
    """Bad/expired cookies or query-id — backend cannot proceed."""


class GraphQLCookieBackend(XBackend):
    name = "graphql_cookie"

    def __init__(self) -> None:
        self._tx_ctx = None
        self._tx_ts = 0.0
        self._query_id: str | None = None
        self._query_id_ts = 0.0

    def _creds(self, settings, db) -> tuple[str | None, str | None, str | None]:
        ct0 = resolve_credential(db, "ct0", "CT0", "X_CT0")
        auth_token = resolve_credential(db, "auth_token", "AUTH_TOKEN", "X_AUTH_TOKEN")
        query_id = resolve_credential(db, "graphql_query_id")
        return ct0, auth_token, query_id

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        ct0, auth_token, _ = self._creds(settings, db)
        return bool(ct0 and auth_token)

    def search_one(self, query: str, settings, db: sqlite3.Connection | None) -> list[ParsedTweet]:
        ct0, auth_token, user_query_id = self._creds(settings, db)
        if not (ct0 and auth_token):
            return []
        query_id = self._resolve_query_id(user_query_id)
        path = f"/i/api/graphql/{query_id}/SearchTimeline"
        variables = {
            "rawQuery": f"({query}) -filter:retweets lang:en",
            "count": _PER_QUERY_COUNT,
            "querySource": "typed_query",
            "product": "Top",
        }
        headers = self._headers(ct0, auth_token)

        last_exc: Exception | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                headers["X-Client-Transaction-Id"] = self._transaction_id("GET", path)
                resp = requests.get(
                    f"https://x.com{path}",
                    headers=headers,
                    params={
                        "variables": json.dumps(variables, separators=(",", ":")),
                        "features": json.dumps(_FEATURES, separators=(",", ":")),
                    },
                    timeout=15,
                )
                if resp.status_code in (401, 403):
                    raise XBackendAuthError(
                        f"cookie auth rejected (HTTP {resp.status_code}) — re-copy ct0/auth_token"
                    )
                if resp.status_code == 404:
                    # Stale query ID — force rediscovery once, then retry.
                    self._query_id = None
                    raise ConnectionError("SearchTimeline 404 (stale query id)")
                if resp.status_code == 429:
                    raise ConnectionError("rate limited")
                if resp.status_code != 200:
                    raise ConnectionError(f"HTTP {resp.status_code}: {resp.text[:120]}")
                try:
                    payload = resp.json()
                except json.JSONDecodeError as exc:
                    # Anti-bot HTML interstitial in place of JSON — retry.
                    raise ConnectionError(f"non-JSON response (anti-bot interstitial?): {exc}")
                return _parse_tweets(payload)
            except XBackendAuthError:
                raise
            except Exception as exc:  # noqa: BLE001 — transient; retry then give up
                last_exc = exc
                if attempt < _MAX_ATTEMPTS - 1:
                    time.sleep(2 ** (attempt + 1))
        if last_exc:
            raise last_exc
        return []

    # ── headers ──────────────────────────────────────────────────────────────
    def _headers(self, ct0: str, auth_token: str) -> dict:
        return {
            "Authorization": f"Bearer {_APP_BEARER}",
            "Cookie": f"auth_token={auth_token}; ct0={ct0}",
            "x-csrf-token": ct0,
            "x-twitter-auth-type": "OAuth2Session",
            "x-twitter-active-user": "yes",
            "x-twitter-client-language": "en",
            "Referer": "https://x.com/search",
            "Accept": "*/*",
            "User-Agent": _UA,
        }

    # ── query-id auto-discovery ─────────────────────────────────────────────
    def _resolve_query_id(self, user_query_id: str | None) -> str:
        if user_query_id:
            return user_query_id
        if self._query_id and (time.time() - self._query_id_ts < 3600):
            return self._query_id
        try:
            home = requests.get("https://x.com/", headers={"User-Agent": _UA}, timeout=15)
            home.raise_for_status()
            main_match = re.search(r'src=["\']([^"\' ]+main\.[a-f0-9]+\.js)["\']', home.text)
            if not main_match:
                return _DEFAULT_QUERY_ID
            main_js = requests.get(main_match.group(1), headers={"User-Agent": _UA}, timeout=30)
            main_js.raise_for_status()
            qid = re.search(r'queryId:"([a-zA-Z0-9_-]+)",operationName:"SearchTimeline"', main_js.text)
            if not qid:
                return _DEFAULT_QUERY_ID
            self._query_id = qid.group(1)
            self._query_id_ts = time.time()
            return self._query_id
        except Exception as exc:
            logger.warning("twitter_query_id_fallback", error=str(exc))
            return _DEFAULT_QUERY_ID

    # ── x-client-transaction-id (twikit, lazy) ──────────────────────────────
    def _transaction_id(self, method: str, path: str) -> str:
        ctx = self._init_transaction_ctx()
        return ctx.generate_transaction_id(method=method, path=path)

    def _init_transaction_ctx(self):
        if self._tx_ctx and (time.time() - self._tx_ts < 600):
            return self._tx_ctx
        import bs4  # local imports keep module import light
        from twikit.x_client_transaction.transaction import ClientTransaction

        home = requests.get("https://x.com/", headers={"User-Agent": _UA}, timeout=15)
        home.raise_for_status()
        soup = bs4.BeautifulSoup(home.text, "html.parser")

        chunk_id_match = re.search(r'(\d+):"ondemand\.s"', home.text)
        if not chunk_id_match:
            raise RuntimeError("cannot find ondemand.s chunk ID on x.com homepage")
        chunk_id = chunk_id_match.group(1)
        hash_match = re.search(rf'{chunk_id}:"([a-f0-9]+)"', home.text)
        if not hash_match:
            raise RuntimeError(f"cannot find hash for chunk {chunk_id}")
        chunk_hash = hash_match.group(1)

        ondemand_url = f"https://abs.twimg.com/responsive-web/client-web/ondemand.s.{chunk_hash}a.js"
        od = requests.get(ondemand_url, headers={"User-Agent": _UA}, timeout=15)
        od.raise_for_status()
        idx = [int(m.group(1)) for m in re.finditer(r"\(\w{1}\[(\d{1,2})\],\s*16\)", od.text)]
        if not idx:
            raise RuntimeError("cannot extract key-byte indices from ondemand.s")

        ct = ClientTransaction()
        ct.home_page_response = soup
        ct.DEFAULT_ROW_INDEX = idx[0]
        ct.DEFAULT_KEY_BYTES_INDICES = idx[1:]
        ct.key = ct.get_key(soup)
        ct.key_bytes = ct.get_key_bytes(ct.key)
        ct.animation_key = ct.get_animation_key(ct.key_bytes, soup)
        self._tx_ctx = ct
        self._tx_ts = time.time()
        return ct


def _parse_tweets(response_json: dict) -> list[ParsedTweet]:
    """Walk the SearchTimeline envelope into :class:`ParsedTweet`."""
    instructions = (
        response_json.get("data", {})
        .get("search_by_raw_query", {})
        .get("search_timeline", {})
        .get("timeline", {})
        .get("instructions", [])
    )
    tweets: list[ParsedTweet] = []
    for instruction in instructions:
        if instruction.get("type") != "TimelineAddEntries":
            continue
        for entry in instruction.get("entries", []):
            try:
                result = entry["content"]["itemContent"]["tweet_results"]["result"]
                if result.get("__typename") == "TweetWithVisibilityResults":
                    result = result["tweet"]
                legacy = result["legacy"]
                user = result["core"]["user_results"]["result"]["legacy"]
                full_text = legacy.get("full_text", "")
                if full_text.startswith("RT @"):  # skip retweets
                    continue
                tweets.append(ParsedTweet(
                    id=result["rest_id"],
                    text=full_text,
                    author=user.get("screen_name"),
                    created_at=parse_twitter_date(legacy.get("created_at")),
                    likes=legacy.get("favorite_count", 0),
                    retweets=legacy.get("retweet_count", 0),
                    replies=legacy.get("reply_count", 0),
                ))
            except (KeyError, TypeError):
                continue
    return tweets

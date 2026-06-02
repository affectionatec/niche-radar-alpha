"""xAI live-X-search backend (ported from last30days lib/xai_x.py).

Uses xAI's Agent Tools ``x_search`` tool to pull recent posts with engagement.
Needs only ``XAI_API_KEY`` — no cookies, no scraping — which is why it sits at
the top of the X fallback chain.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone

import structlog

from niche_radar.collectors import _http
from niche_radar.collectors.x_backends.base import ParsedTweet, XBackend, parse_twitter_date, resolve_credential

logger = structlog.get_logger()

XAI_RESPONSES_URL = "https://api.x.ai/v1/responses"
XAI_DEFAULT_MODEL = "grok-4-1-fast"
_PER_QUERY_ITEMS = 20
_TIMEOUT = 120

_PROMPT = """You have access to real-time X (Twitter) data. Search for posts matching: {query}

Find up to {max_items} high-quality, relevant posts from the last few days.

Return ONLY valid JSON in this exact format, no other text:
{{
  "items": [
    {{
      "text": "Post text content",
      "url": "https://x.com/user/status/...",
      "author_handle": "username",
      "date": "YYYY-MM-DD or null",
      "engagement": {{"likes": 100, "reposts": 25, "replies": 15, "quotes": 5}}
    }}
  ]
}}

Rules:
- date must be YYYY-MM-DD or null
- engagement values can be null if unknown
- Prefer substantive posts that express a real need, frustration, or request"""


class XaiBackend(XBackend):
    name = "xai"

    def _api_key(self, settings, db) -> str | None:
        return resolve_credential(db, "xai_api_key", "XAI_API_KEY", settings=settings, settings_attr="xai_api_key")

    def _model(self, settings, db) -> str:
        return resolve_credential(db, "xai_model", "XAI_MODEL", settings=settings) or XAI_DEFAULT_MODEL

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        return bool(self._api_key(settings, db))

    def search_one(self, query: str, settings, db: sqlite3.Connection | None) -> list[ParsedTweet]:
        api_key = self._api_key(settings, db)
        if not api_key:
            return []
        today = datetime.now(timezone.utc).date().isoformat()
        payload = {
            "model": self._model(settings, db),
            "tools": [{"type": "x_search", "to_date": today}],
            "input": [{"role": "user", "content": _PROMPT.format(query=query, max_items=_PER_QUERY_ITEMS)}],
        }
        resp = _http.post_json(
            XAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json_body=payload,
            timeout=_TIMEOUT,
            retries=2,
        )
        return _parse(resp)


def _output_text(response: dict) -> str:
    """Extract the model's text from xAI's Responses-API envelope."""
    output = response.get("output")
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        for item in output:
            if isinstance(item, str):
                return item
            if isinstance(item, dict):
                if item.get("type") == "message":
                    for c in item.get("content", []):
                        if isinstance(c, dict) and c.get("type") == "output_text":
                            return c.get("text", "")
                elif "text" in item:
                    return item["text"]
    # Older chat-completions shape
    for choice in response.get("choices", []):
        msg = choice.get("message") or {}
        if msg.get("content"):
            return msg["content"]
    return ""


def _parse(response: dict) -> list[ParsedTweet]:
    if not isinstance(response, dict):
        return []
    if response.get("error"):
        logger.warning("xai_x_api_error", error=str(response["error"])[:200])
        return []

    text = _output_text(response)
    match = re.search(r'\{[\s\S]*"items"[\s\S]*\}', text)
    if not match:
        return []
    try:
        items = json.loads(match.group()).get("items", [])
    except json.JSONDecodeError:
        return []

    tweets: list[ParsedTweet] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        if not url:
            continue
        tid = _id_from_url(url)
        if not tid:
            continue
        eng = item.get("engagement") if isinstance(item.get("engagement"), dict) else {}
        date = item.get("date")
        if date and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date)):
            date = None
        tweets.append(ParsedTweet(
            id=tid,
            text=str(item.get("text", "")).strip()[:500],
            author=str(item.get("author_handle", "")).strip().lstrip("@") or None,
            created_at=parse_twitter_date(date),
            likes=_int(eng.get("likes")),
            retweets=_int(eng.get("reposts")),
            replies=_int(eng.get("replies")),
            url=url,
        ))
    return tweets


def _id_from_url(url: str) -> str | None:
    m = re.search(r"/status/(\d+)", url)
    return m.group(1) if m else None


def _int(value) -> int:
    try:
        return int(value) if value is not None else 0
    except (ValueError, TypeError):
        return 0

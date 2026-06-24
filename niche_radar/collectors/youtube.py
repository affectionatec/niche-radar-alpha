"""YouTube data collector — a resilient multi-backend source (ADR-002).

Capture walks an ordered chain:

    1. yt_dlp           — keyless, transcript-bearing capture via the yt-dlp CLI
                          (full description + auto-caption transcript, no Data
                          API quota). Used whenever the ``yt-dlp`` binary exists.
    2. youtube_api_scrape — Data API v3 (if a key is set) with a scrapetube
                          fallback. The original capture path, kept as fallback
                          for environments without yt-dlp.
"""

from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import ClassVar

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.backends import YtDlpBackend
from niche_radar.collectors.backends.ytdlp import ytdlp_available
from niche_radar.collectors.base import CollectorUnavailableError
from niche_radar.collectors.multi_backend import MultiBackendCollector, SourceBackend
from niche_radar.storage.repository import get_source_credential

logger = structlog.get_logger()
SEED_KEYWORDS = [
    "AI tools",
    "SaaS alternative",
    "developer tools",
    "automation software",
    "self-hosted",
    "open source",
    "no-code",
    "side project",
    "indie hacker",
    "productivity app",
]


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "simpleText" in value:
            return value["simpleText"]
        runs = value.get("runs") or []
        return "".join(part.get("text", "") for part in runs) or None
    return None


def _to_int(text: str | None) -> int | None:
    digits = re.sub(r"[^\d]", "", text or "")
    return int(digits) if digits else None


class YouTubeApiScrapeBackend(SourceBackend):
    """Fallback path — YouTube Data API v3 (if keyed) with a scrapetube fallback."""

    name = "youtube_api_scrape"

    def is_available(self, settings, db: sqlite3.Connection | None) -> bool:
        try:
            api_key = (
                get_source_credential(db, "youtube", "api_key", settings.youtube_api_key)
                if db else settings.youtube_api_key
            )
            if api_key:
                return True
            import scrapetube  # noqa: F401

            return True
        except Exception:
            return False

    def fetch(self, settings, db: sqlite3.Connection | None) -> list[dict]:
        import requests

        try:
            import scrapetube
        except Exception:
            scrapetube = None
        youtube_api_key = (
            get_source_credential(db, "youtube", "api_key", settings.youtube_api_key)
            if db else settings.youtube_api_key
        )
        if scrapetube is None and not youtube_api_key:
            raise CollectorUnavailableError(
                "scrapetube is not installed and no YouTube API key is configured"
            )

        retryer = Retrying(
            stop=stop_after_attempt(max(1, int(settings.max_retries or 1))),
            wait=wait_exponential(
                multiplier=1,
                exp_base=max(2, int(settings.retry_backoff_base or 2)),
                min=1,
                max=30,
            ),
            reraise=True,
        )
        items: dict[str, dict] = {}
        errors: list[str] = []
        window_hours = settings.freshness_youtube_hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        published_after_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        dropped_stale = 0

        for query in SEED_KEYWORDS:
            try:
                for attempt in retryer:
                    with attempt:
                        if scrapetube is None:
                            raise CollectorUnavailableError("scrapetube unavailable")
                        videos = list(scrapetube.get_search(query, limit=10))
                used_api = False
            except Exception as exc:
                if not youtube_api_key:
                    logger.warning("youtube_search_failed", query=query, error=str(exc))
                    errors.append(f"{query}: {exc}")
                    continue
                logger.warning("youtube_scrapetube_failed", query=query, error=str(exc))
                for attempt in retryer:
                    with attempt:
                        videos = self._search_api(
                            requests, youtube_api_key, query, published_after_iso,
                        )
                used_api = True

            for video in videos[:10]:
                item = self._normalize_video(video, query, used_api)
                if not item:
                    continue
                if not self._is_fresh(item, used_api, cutoff):
                    dropped_stale += 1
                    continue
                existing = items.get(item["source_id"])
                if existing:
                    queries = existing["metadata"].setdefault("queries", [])
                    if query not in queries:
                        queries.append(query)
                else:
                    items[item["source_id"]] = item
            time.sleep(1)

        if dropped_stale:
            logger.info("youtube_stale_dropped", count=dropped_stale, window_hours=window_hours)
        collected = list(items.values())
        if not collected and errors:
            raise CollectorUnavailableError("; ".join(errors))
        return collected

    def _search_api(
        self, requests_module, api_key: str, query: str, published_after: str | None = None,
    ) -> list[dict]:
        params = {
            "part": "snippet",
            "type": "video",
            "maxResults": 10,
            "q": query,
            "order": "date",  # newest first
            "key": api_key,
        }
        if published_after:
            params["publishedAfter"] = published_after
        response = requests_module.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
            timeout=20,
        )
        if response.status_code == 403 and "quota" in response.text.lower():
            raise CollectorUnavailableError("YouTube API quota exhausted")
        if response.status_code != 200:
            raise CollectorUnavailableError(f"YouTube API returned {response.status_code}")
        return response.json().get("items", [])

    def _normalize_video(self, video: dict, query: str, used_api: bool) -> dict | None:
        source_id = video.get("videoId") if not used_api else (video.get("id") or {}).get("videoId")
        if not source_id:
            return None
        snippet = video.get("snippet", {}) if used_api else {}
        title = _text(video.get("title")) if not used_api else snippet.get("title")
        body = _text(video.get("descriptionSnippet")) if not used_api else snippet.get("description")
        view_text = _text(video.get("viewCountText")) if not used_api else None
        published = _text(video.get("publishedTimeText")) if not used_api else snippet.get("publishedAt")

        posted_at = None
        if used_api and published:
            posted_at = published
        elif published:
            relative_dt = _relative_to_datetime(published)
            if relative_dt is not None:
                posted_at = relative_dt.isoformat()

        return {
            "source_id": source_id,
            "title": title or source_id,
            "body": body,
            "url": f"https://www.youtube.com/watch?v={source_id}",
            "score": _to_int(view_text),
            "comment_count": None,
            "posted_at": posted_at,
            "metadata": {
                "queries": [query],
                "channel": _text(video.get("longBylineText")) if not used_api else snippet.get("channelTitle"),
                "published": published,
                "view_count_text": view_text,
                "source": "youtube_api" if used_api else "scrapetube",
            },
        }

    def _is_fresh(self, item: dict, used_api: bool, cutoff: datetime) -> bool:
        """API path: parse ISO. Scrape path: parse relative phrase like '2 days ago'."""
        if used_api:
            posted = item.get("posted_at")
            if not posted:
                return False
            try:
                dt = datetime.fromisoformat(posted.replace("Z", "+00:00"))
                return dt >= cutoff
            except (ValueError, TypeError):
                return False
        published = (item.get("metadata") or {}).get("published") or ""
        return _relative_age_within(published, cutoff)


class YouTubeCollector(MultiBackendCollector):
    source_name = "youtube"

    CREDENTIAL_SCHEMA: ClassVar[list[dict]] = [
        {"key": "api_key", "label": "YouTube Data API v3 Key (optional)", "secret": True, "optional": True,
         "help": "From console.cloud.google.com. Only used as a fallback — when yt-dlp is installed it is preferred (keyless, captures transcripts)."},
    ]

    def build_backends(self) -> list[SourceBackend]:
        return [YtDlpBackend(SEED_KEYWORDS), YouTubeApiScrapeBackend()]

    @classmethod
    def test_connection(cls, db: sqlite3.Connection, settings) -> tuple[bool, str]:
        if ytdlp_available():
            return True, "✓ YouTube capture will use yt-dlp (keyless, transcripts)"
        import requests

        api_key = get_source_credential(db, "youtube", "api_key", settings.youtube_api_key)
        if api_key:
            resp = requests.get(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"part": "id", "chart": "mostPopular", "maxResults": 1, "key": api_key},
                timeout=10,
            )
            if resp.status_code == 200:
                return True, "YouTube API key valid (yt-dlp not installed)"
            return False, f"YouTube API returned {resp.status_code}: {resp.text[:100]}"
        try:
            import scrapetube  # noqa: F401

            return True, "scrapetube available (no API key; install yt-dlp for transcripts)"
        except ImportError:
            return False, "No yt-dlp, no YouTube API key, and scrapetube not installed"


_RELATIVE_PATTERN = re.compile(
    r"(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago", re.IGNORECASE
)


def _relative_to_datetime(phrase: str) -> datetime | None:
    """Parse 'N days ago' / 'N weeks ago' → absolute UTC datetime. Returns None if unparseable."""
    m = _RELATIVE_PATTERN.search(phrase or "")
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    delta_hours = {
        "second": n / 3600,
        "minute": n / 60,
        "hour": n,
        "day": n * 24,
        "week": n * 24 * 7,
        "month": n * 24 * 30,
        "year": n * 24 * 365,
    }[unit]
    return datetime.now(timezone.utc) - timedelta(hours=delta_hours)


def _relative_age_within(phrase: str, cutoff: datetime) -> bool:
    """Returns True if the relative phrase resolves to a time after `cutoff`."""
    posted = _relative_to_datetime(phrase)
    if posted is None:
        return False  # conservative: drop unparseable
    return posted >= cutoff

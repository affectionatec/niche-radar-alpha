"""YouTube data collector."""

from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone

import structlog
from tenacity import Retrying, stop_after_attempt, wait_exponential

from niche_radar.collectors.base import (
    BaseCollector,
    CollectorResult,
    CollectorUnavailableError,
)

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


class YouTubeCollector(BaseCollector):
    source_name = "youtube"

    def collect(self, settings, dry_run: bool = False) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
            import requests

            try:
                import scrapetube
            except Exception:
                scrapetube = None
            if scrapetube is None and not settings.youtube_api_key:
                raise CollectorUnavailableError("scrapetube is not installed and no YouTube API key is configured")

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
                    if not settings.youtube_api_key:
                        logger.warning("youtube_search_failed", query=query, error=str(exc))
                        errors.append(f"{query}: {exc}")
                        continue
                    logger.warning("youtube_scrapetube_failed", query=query, error=str(exc))
                    for attempt in retryer:
                        with attempt:
                            videos = self._search_api(
                                requests, settings.youtube_api_key, query, published_after_iso,
                            )
                    used_api = True

                for video in videos[:10]:
                    item = self._normalize_video(video, query, used_api)
                    if not item:
                        continue
                    # Freshness gate — drop videos older than the window
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

            collected = list(items.values())
            if dropped_stale:
                logger.info("youtube_stale_dropped", count=dropped_stale, window_hours=window_hours)
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
            logger.exception("youtube_collect_failed", error=str(exc))
            return CollectorResult(
                source=self.source_name,
                items=[],
                run_id="",
                status="failed",
                items_collected=0,
                error_message=str(exc),
                duration_seconds=time.perf_counter() - start,
            )

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

        # API returns ISO timestamps; scrapetube returns "2 days ago" — parse both.
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
        # Scrapetube returns relative phrases — parse them
        published = (item.get("metadata") or {}).get("published") or ""
        return _relative_age_within(published, cutoff)


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

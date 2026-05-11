"""Google Trends data collector."""

from __future__ import annotations

import re
import time

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


def _pick_callable(obj, *names):
    return next((getattr(obj, name) for name in names if callable(getattr(obj, name, None))), None)


def _extract_series(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("timeline_data", "interest_over_time", "data", "series", "timeline"):
            if isinstance(payload.get(key), list):
                return payload[key]
    return []


class GoogleTrendsCollector(BaseCollector):
    source_name = "google_trends"

    def collect(self, settings, dry_run: bool = False) -> CollectorResult:
        start = time.perf_counter()
        if dry_run:
            return CollectorResult(self.source_name, [], "", "completed", 0)

        try:
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
            items: list[dict] = []
            errors: list[str] = []
            client = None
            rss_download = None

            try:
                from trendspyg import TrendsPyG  # type: ignore[attr-defined]

                client = TrendsPyG()
            except Exception:
                client = None
            try:
                from trendspyg import download_google_trends_rss  # type: ignore[attr-defined]

                rss_download = download_google_trends_rss
            except Exception:
                rss_download = None
            if not client and not rss_download:
                raise CollectorUnavailableError("trendspyg is not installed")

            for attempt in retryer:
                with attempt:
                    if client:
                        fetch = _pick_callable(client, "trending_searches", "get_trending_searches")
                        if not fetch:
                            raise CollectorUnavailableError("TrendsPyG trending method not available")
                        try:
                            trending = fetch(geo="US")
                        except TypeError:
                            trending = fetch(pn="united_states")
                    else:
                        trending = rss_download(geo="US", include_images=False)
            for trend in trending or []:
                title = trend.get("trend") or trend.get("title") or str(trend)
                news = trend.get("news_articles") or []
                traffic = trend.get("traffic")
                items.append(
                    {
                        "source_id": f"trend:{title.strip().lower()}",
                        "title": title,
                        "body": news[0].get("headline") if news else None,
                        "url": trend.get("explore_link") or trend.get("url"),
                        "score": int(re.sub(r"\D", "", str(traffic or 0)) or 0),
                        "comment_count": None,
                        "metadata": {
                            "kind": "trending_search",
                            "traffic": traffic,
                            "news_articles": news,
                            "published": str(trend.get("published") or ""),
                        },
                    }
                )

            if client:
                for keyword in SEED_KEYWORDS:
                    try:
                        for attempt in retryer:
                            with attempt:
                                fetch = _pick_callable(client, "interest_over_time", "get_interest_over_time")
                                if not fetch:
                                    raise CollectorUnavailableError(
                                        "TrendsPyG interest-over-time method not available"
                                    )
                                try:
                                    payload = fetch(keywords=[keyword], geo="US", timeframe="today 12-m")
                                except TypeError:
                                    payload = fetch(keyword=keyword, geo="US", timeframe="today 12-m")
                        items.append(
                            {
                                "source_id": f"interest:{keyword.lower()}",
                                "title": keyword,
                                "body": None,
                                "url": None,
                                "score": len(_extract_series(payload)),
                                "comment_count": None,
                                "metadata": {
                                    "kind": "interest_over_time",
                                    "keyword": keyword,
                                    "timeframe": "today 12-m",
                                    "series": _extract_series(payload),
                                },
                            }
                        )
                    except Exception as exc:
                        logger.warning("google_trends_keyword_failed", keyword=keyword, error=str(exc))
                        errors.append(f"{keyword}: {exc}")
            else:
                errors.append("Installed trendspyg version does not expose TrendsPyG interest-over-time support")

            status = "completed" if not errors else "partial" if items else "failed"
            return CollectorResult(
                source=self.source_name,
                items=items,
                run_id="",
                status=status,
                items_collected=len(items),
                error_message="; ".join(errors) or None,
                duration_seconds=time.perf_counter() - start,
            )
        except Exception as exc:
            message = str(exc)
            if any(token in message.lower() for token in ("captcha", "blocked", "429", "403")):
                message = f"Google Trends blocked or CAPTCHA triggered: {message}"
            logger.exception("google_trends_collect_failed", error=message)
            return CollectorResult(
                source=self.source_name,
                items=[],
                run_id="",
                status="failed",
                items_collected=0,
                error_message=message,
                duration_seconds=time.perf_counter() - start,
            )

"""Collectors package — data source ingestion."""

from __future__ import annotations

import time

import structlog

from niche_radar.collectors.base import CollectorResult
from niche_radar.storage.database import get_db
from niche_radar.storage.repository import (
    insert_collection_run,
    complete_collection_run,
    upsert_raw_item,
)

logger = structlog.get_logger()

ALL_SOURCES = [
    "reddit", "hn", "google_trends", "github", "youtube",
    # Phase 2 — P1 new sources
    "product_hunt", "stack_overflow", "twitter", "g2_reviews",
    # Phase 4 — P2 new sources
    "indie_hackers", "app_store", "play_store",
    # last30days integration — credential-gated, skipped until configured
    "bluesky",
    "tiktok", "instagram", "threads",
    # M3 new channels — keyless/native first
    "v2ex",          # keyless (v1 API) or token-enhanced (v2 API)
    "xueqiu",        # auto-guest-session; optional explicit cookie
    "exa",           # key-gated semantic search
    "bilibili",      # auto guest buvid3; optional SESSDATA cookie
]


def _get_collector(source: str):
    """Lazy-import and return the collector for a source."""
    if source == "reddit":
        from niche_radar.collectors.reddit import RedditCollector
        return RedditCollector()
    elif source == "hn":
        from niche_radar.collectors.hackernews import HackerNewsCollector
        return HackerNewsCollector()
    elif source == "google_trends":
        from niche_radar.collectors.google_trends import GoogleTrendsCollector
        return GoogleTrendsCollector()
    elif source == "github":
        from niche_radar.collectors.github_trending import GitHubTrendingCollector
        return GitHubTrendingCollector()
    elif source == "youtube":
        from niche_radar.collectors.youtube import YouTubeCollector
        return YouTubeCollector()
    elif source == "product_hunt":
        from niche_radar.collectors.product_hunt import ProductHuntCollector
        return ProductHuntCollector()
    elif source == "stack_overflow":
        from niche_radar.collectors.stack_overflow import StackOverflowCollector
        return StackOverflowCollector()
    elif source == "twitter":
        from niche_radar.collectors.twitter import TwitterCollector
        return TwitterCollector()
    elif source == "g2_reviews":
        from niche_radar.collectors.g2_reviews import G2ReviewsCollector
        return G2ReviewsCollector()
    elif source == "indie_hackers":
        from niche_radar.collectors.indie_hackers import IndieHackersCollector
        return IndieHackersCollector()
    elif source == "app_store":
        from niche_radar.collectors.app_store import AppStoreCollector
        return AppStoreCollector()
    elif source == "play_store":
        from niche_radar.collectors.play_store import PlayStoreCollector
        return PlayStoreCollector()
    elif source == "bluesky":
        from niche_radar.collectors.bluesky import BlueskyCollector
        return BlueskyCollector()
    elif source == "tiktok":
        from niche_radar.collectors.tiktok import TikTokCollector
        return TikTokCollector()
    elif source == "instagram":
        from niche_radar.collectors.instagram import InstagramCollector
        return InstagramCollector()
    elif source == "threads":
        from niche_radar.collectors.threads import ThreadsCollector
        return ThreadsCollector()
    elif source == "v2ex":
        from niche_radar.collectors.v2ex import V2exCollector
        return V2exCollector()
    elif source == "xueqiu":
        from niche_radar.collectors.xueqiu import XueqiuCollector
        return XueqiuCollector()
    elif source == "exa":
        from niche_radar.collectors.exa import ExaCollector
        return ExaCollector()
    elif source == "bilibili":
        from niche_radar.collectors.bilibili import BilibiliCollector
        return BilibiliCollector()
    else:
        raise ValueError(f"Unknown source: {source}")


def run_collectors(
    sources: list[str] | None,
    settings,
    dry_run: bool = False,
) -> list[CollectorResult]:
    """Run specified (or all) collectors and persist results."""
    sources = sources or ALL_SOURCES
    db = get_db(settings.database_url)
    results: list[CollectorResult] = []

    for source in sources:
        try:
            collector = _get_collector(source)
        except Exception as exc:
            logger.error("collector_unknown", source=source, error=str(exc))
            continue

        # Skip credential-gated sources that aren't configured — silently, so
        # they don't litter the dashboard with failed runs until set up.
        if not dry_run:
            try:
                if not type(collector).is_available(db, settings):
                    logger.debug("collector_skipped_unavailable", source=source)
                    continue
            except Exception as exc:
                logger.warning("collector_availability_check_failed", source=source, error=str(exc))

        run_id = insert_collection_run(db, source)
        start = time.time()

        try:
            result = collector.collect(settings=settings, dry_run=dry_run, db=db)
            result.run_id = run_id

            if not dry_run:
                for item in result.items:
                    upsert_raw_item(
                        db=db,
                        collection_run=run_id,
                        source=source,
                        source_id=item.get("source_id", ""),
                        title=item.get("title"),
                        body=item.get("body"),
                        url=item.get("url"),
                        score=item.get("score"),
                        comment_count=item.get("comment_count"),
                        metadata=item.get("metadata"),
                        posted_at=item.get("posted_at"),
                    )

            result.duration_seconds = time.time() - start
            complete_collection_run(
                db, run_id, result.status, result.items_collected
            )
            logger.info(
                "collector_done",
                source=source,
                items=result.items_collected,
                duration_s=round(result.duration_seconds, 2),
            )

        except Exception as exc:
            duration = time.time() - start
            complete_collection_run(db, run_id, "failed", 0, str(exc))
            result = CollectorResult(
                source=source,
                items=[],
                run_id=run_id,
                status="failed",
                items_collected=0,
                error_message=str(exc),
                duration_seconds=duration,
            )
            logger.error("collector_failed", source=source, error=str(exc))

        results.append(result)

    return results

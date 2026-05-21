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
        run_id = insert_collection_run(db, source)
        start = time.time()

        try:
            collector = _get_collector(source)
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

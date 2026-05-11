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

ALL_SOURCES = ["reddit", "hn", "google_trends", "github", "youtube"]


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
            result = collector.collect(settings=settings, dry_run=dry_run)
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

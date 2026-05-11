"""Scheduler for continuous operation using APScheduler."""

from __future__ import annotations

import signal
import sys

import structlog
from apscheduler.schedulers.blocking import BlockingScheduler

logger = structlog.get_logger()


def _collect_job(settings) -> None:
    """Scheduled collection job."""
    from niche_radar.collectors import run_collectors
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    results = run_collectors(sources=None, settings=settings, dry_run=False)
    total = sum(r.items_collected for r in results)
    logger.info("scheduled_collection_complete", total_items=total)


def _score_job(settings) -> None:
    """Scheduled scoring job."""
    from niche_radar.nlp import run_extraction
    from niche_radar.scoring import run_scoring
    from niche_radar.reports.generator import generate_report
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    run_extraction(db=db, settings=settings, dry_run=False)
    run_scoring(db=db, settings=settings, dry_run=False)
    generate_report(db=db, settings=settings, fmt=settings.report_format)
    logger.info("scheduled_scoring_complete")


def _cleanup_job(settings) -> None:
    """Scheduled cleanup job."""
    from niche_radar.storage.cleanup import run_cleanup
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    run_cleanup(db=db, settings=settings)


def start_scheduler(settings) -> None:
    """Start the blocking scheduler with all jobs configured."""
    scheduler = BlockingScheduler()

    scheduler.add_job(
        _collect_job,
        "interval",
        hours=settings.collection_interval_hours,
        args=[settings],
        id="collect",
        name="Data Collection",
    )

    scheduler.add_job(
        _score_job,
        "interval",
        hours=settings.scoring_interval_hours,
        args=[settings],
        id="score",
        name="NLP + Scoring + Report",
    )

    scheduler.add_job(
        _cleanup_job,
        "cron",
        hour=settings.cleanup_hour_utc,
        args=[settings],
        id="cleanup",
        name="Data Retention Cleanup",
    )

    def shutdown(signum, frame):
        logger.info("scheduler_shutting_down")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    logger.info(
        "scheduler_started",
        collect_interval_h=settings.collection_interval_hours,
        score_interval_h=settings.scoring_interval_hours,
        cleanup_hour_utc=settings.cleanup_hour_utc,
    )
    scheduler.start()

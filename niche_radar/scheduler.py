"""Scheduler for continuous operation using APScheduler."""
from __future__ import annotations

import structlog

logger = structlog.get_logger()


def _collect_job(settings) -> None:
    from niche_radar.collectors import run_collectors
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    results = run_collectors(sources=None, settings=settings, dry_run=False)
    total = sum(r.items_collected for r in results)
    logger.info("scheduled_collection_complete", total_items=total)


def _analyze_job(settings) -> None:
    from niche_radar.analysis import run_analysis
    from niche_radar.reports.generator import generate_report
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    count = run_analysis(db=db, settings=settings, dry_run=False)
    generate_report(db=db, settings=settings)
    logger.info("scheduled_analysis_complete", niches=count)


def _cleanup_job(settings) -> None:
    from niche_radar.storage.cleanup import run_cleanup
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    run_cleanup(db=db, settings=settings)


def start_scheduler(settings) -> None:
    """Start BackgroundScheduler + uvicorn API server."""
    import uvicorn
    from apscheduler.schedulers.background import BackgroundScheduler
    from niche_radar.api.server import app

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        _collect_job,
        "interval",
        hours=settings.collection_interval_hours,
        args=[settings],
        id="collect",
        name="Data Collection",
    )
    scheduler.add_job(
        _analyze_job,
        "interval",
        hours=settings.analysis_interval_hours,
        args=[settings],
        id="analyze",
        name="LLM Analysis + Report",
    )
    scheduler.add_job(
        _cleanup_job,
        "cron",
        hour=settings.cleanup_hour_utc,
        args=[settings],
        id="cleanup",
        name="Data Retention Cleanup",
    )

    scheduler.start()
    logger.info(
        "scheduler_started",
        collect_interval_h=settings.collection_interval_hours,
        analysis_interval_h=settings.analysis_interval_hours,
        cleanup_hour_utc=settings.cleanup_hour_utc,
    )

    logger.info("api_starting", host="0.0.0.0", port=8000)
    try:
        # log_level="info" emits HTTP access logs to stdout so they show up in
        # `docker logs` / Docker Dashboard — invaluable for debugging from the UI.
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info", access_log=True)
    finally:
        scheduler.shutdown(wait=False)

"""Scheduler for continuous operation using APScheduler."""
from __future__ import annotations

import structlog

from niche_radar.api.jobs import job_manager

logger = structlog.get_logger()


def _collect_job(settings) -> None:
    from niche_radar.collectors import run_collectors

    job = job_manager.create("collect")
    job_manager.set_status(job.id, "running")
    try:
        results = run_collectors(sources=None, settings=settings, dry_run=False)
        total = sum(r.items_collected for r in results)
        job_manager.append_log(job.id, f"Collected {total} items from {len(results)} sources")
        job_manager.set_status(job.id, "done")
        logger.info("scheduled_collection_complete", total_items=total, job_id=job.id)
    except Exception as exc:
        job_manager.append_log(job.id, f"Error: {exc}")
        job_manager.set_status(job.id, "failed")
        logger.error("scheduled_collection_failed", error=str(exc), job_id=job.id)


def _analyze_job(settings) -> None:
    from niche_radar.analysis import run_analysis
    from niche_radar.reports.generator import generate_report
    from niche_radar.storage.database import get_db

    job = job_manager.create("analyze")
    job_manager.set_status(job.id, "running")
    try:
        db = get_db(settings.database_url)
        count = run_analysis(db=db, settings=settings, dry_run=False)
        job_manager.append_log(job.id, f"Analyzed {count} niches")
        generate_report(db=db, settings=settings)
        job_manager.append_log(job.id, "Report generated")
        job_manager.set_status(job.id, "done")
        logger.info("scheduled_analysis_complete", niches=count, job_id=job.id)
    except Exception as exc:
        job_manager.append_log(job.id, f"Error: {exc}")
        job_manager.set_status(job.id, "failed")
        logger.error("scheduled_analysis_failed", error=str(exc), job_id=job.id)


def _cleanup_job(settings) -> None:
    from niche_radar.storage.cleanup import run_cleanup
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    run_cleanup(db=db, settings=settings)


def _weekly_digest_job(settings) -> None:
    from niche_radar.reports.weekly_digest import generate_weekly_digest
    from niche_radar.storage.database import get_db
    from pathlib import Path

    db = get_db(settings.database_url)
    path = generate_weekly_digest(db=db, output_dir=Path(settings.report_output_dir))
    logger.info("weekly_digest_generated", path=str(path))


def _entity_extraction_job(settings) -> None:
    """Extract entities from recently collected raw items that haven't been processed yet."""
    from niche_radar.entities.service import EntityService
    from niche_radar.storage.database import get_db

    if not settings.llm_api_key:
        logger.info("entity_extraction_skipped_no_llm_key")
        return

    db = get_db(settings.database_url)
    try:
        # Build a lightweight LLM client from settings
        if settings.llm_provider == "anthropic":
            from niche_radar.llm.anthropic_client import AnthropicClient
            llm = AnthropicClient(api_key=settings.llm_api_key, model=settings.llm_model)
        else:
            from niche_radar.llm.openai_compat import OpenAICompatClient
            llm = OpenAICompatClient(
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                base_url=settings.llm_base_url or None,
            )

        service = EntityService(
            llm=llm,
            db=db,
            sample_rate=getattr(settings, "entity_extraction_sample_rate", 0.2),
        )

        # Find raw items that haven't been extracted yet
        rows = db.execute(
            "SELECT ri.id FROM raw_items ri "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM entity_mentions em WHERE em.raw_item_id = ri.id"
            ") "
            "ORDER BY ri.collected_at DESC LIMIT 500"
        ).fetchall()

        processed = 0
        extracted_total = 0
        for row in rows:
            try:
                entity_ids = service.process_item(row["id"])
                if entity_ids:
                    extracted_total += len(entity_ids)
                processed += 1
            except Exception:
                logger.exception("entity_extraction_item_failed", item_id=row["id"])

        logger.info(
            "entity_extraction_complete",
            items_processed=processed,
            entities_extracted=extracted_total,
        )
    finally:
        db.close()


def _entity_velocity_job(settings) -> None:
    """Weekly: compute week-over-week velocity for all tracked entities."""
    from niche_radar.entities.repository import compute_entity_velocity
    from niche_radar.storage.database import get_db

    db = get_db(settings.database_url)
    try:
        before = db.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        compute_entity_velocity(db)
        logger.info("entity_velocity_computed", entity_count=before)
    finally:
        db.close()


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
    scheduler.add_job(
        _weekly_digest_job,
        "cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        args=[settings],
        id="weekly_digest",
        name="Weekly Opportunity Digest",
    )
    scheduler.add_job(
        _entity_extraction_job,
        "interval",
        hours=max(1, settings.collection_interval_hours),
        args=[settings],
        id="entity_extraction",
        name="Entity Extraction",
    )
    scheduler.add_job(
        _entity_velocity_job,
        "cron",
        day_of_week="mon",
        hour=3,
        minute=0,
        args=[settings],
        id="entity_velocity",
        name="Entity Velocity Computation",
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

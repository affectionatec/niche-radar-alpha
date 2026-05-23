"""CLI entry point: python -m niche_radar <command>."""

from __future__ import annotations

import argparse
import sys

import structlog

from niche_radar.config import get_settings


def configure_logging(level: str, fmt: str) -> None:
    import logging

    level_num = getattr(logging, level.upper(), logging.INFO)

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level_num),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="niche_radar",
        description="Niche Radar Alpha — automated trend-intelligence pipeline",
    )
    parser.add_argument("--config", default=".env", help="Path to .env file")
    parser.add_argument("--db", default=None, help="Override DATABASE_URL")
    parser.add_argument("--log-level", default=None, help="Override log level")
    parser.add_argument(
        "--dry-run", action="store_true", help="Run without writing to DB or files"
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # collect
    p_collect = sub.add_parser("collect", help="Collect from data sources")
    p_collect.add_argument(
        "--source",
        choices=["reddit", "hn", "google_trends", "github", "youtube",
                 "product_hunt", "stack_overflow", "twitter", "g2_reviews",
                 "indie_hackers", "app_store", "play_store"],
        help="Collect from a single source",
    )

    # analyze
    p_analyze = sub.add_parser("analyze", help="Run LLM analysis on raw items")
    p_analyze.add_argument(
        "--test", action="store_true",
        help="Run the 8-agent pipeline on a hardcoded test signal (forces dry-run).",
    )
    p_analyze.add_argument(
        "--signal-id", default=None,
        help="Run the pipeline on a single raw_item by ID (forces dry-run unless combined with --commit).",
    )
    p_analyze.add_argument(
        "--no-tui", action="store_true", default=False,
        help="Disable Rich TUI visualization; use plain text output.",
    )

    # report
    sub.add_parser("report", help="Generate niche report")

    # serve
    sub.add_parser("serve", help="Start scheduler for continuous operation")

    # cleanup
    sub.add_parser("cleanup", help="Run data retention cleanup")

    # status
    sub.add_parser("status", help="Show system status")

    return parser


def cmd_collect(args: argparse.Namespace, settings) -> int:
    from niche_radar.collectors import run_collectors

    logger = structlog.get_logger()
    sources = [args.source] if args.source else None
    results = run_collectors(sources=sources, settings=settings, dry_run=args.dry_run)

    total = sum(r.items_collected for r in results)
    failed = [r for r in results if r.status == "failed"]

    logger.info(
        "collection_complete",
        total_items=total,
        sources_ok=len(results) - len(failed),
        sources_failed=len(failed),
    )

    if failed and len(failed) == len(results):
        return 2
    if failed:
        return 1
    return 0


def cmd_analyze(args: argparse.Namespace, settings) -> int:
    """Three modes:
       --test          : run the 8-agent pipeline on a hardcoded signal, dry-run only.
       --signal-id <id>: run the pipeline on one DB raw_item, dry-run only.
       (default)       : run the full pipeline over all unprocessed items.
    """
    from niche_radar.storage.database import get_db

    logger = structlog.get_logger()
    db = get_db(settings.database_url)

    if getattr(args, "test", False):
        from niche_radar.agents.pipeline import run_pipeline_on_signal
        from niche_radar.agents.test_signal import TEST_SIGNAL
        logger.info("analyze_test_mode", signal=TEST_SIGNAL.get("text", "")[:80])
        result = run_pipeline_on_signal(db, settings, TEST_SIGNAL, log_fn=print)
        logger.info(
            "analyze_test_done",
            verdict=result.verdict,
            score=result.opportunity_score,
            failed_agents=result.failed_agents,
            short_circuited_at=result.short_circuited_at,
        )
        return 0

    signal_id = getattr(args, "signal_id", None)
    if signal_id:
        from niche_radar.agents.pipeline import run_pipeline_on_signal
        row = db.execute(
            "SELECT id, source, url, title, body, posted_at, collected_at "
            "FROM raw_items WHERE id=?", (signal_id,)
        ).fetchone()
        if row is None:
            logger.error("signal_not_found", signal_id=signal_id)
            return 2
        raw_signal = {
            "text": ((row[3] or "") + "\n\n" + (row[4] or "")).strip(),
            "source": row[1], "url": row[2],
            "scraped_at": row[5] or row[6],
        }
        result = run_pipeline_on_signal(db, settings, raw_signal, log_fn=print)
        logger.info(
            "analyze_signal_done",
            signal_id=signal_id,
            verdict=result.verdict,
            score=result.opportunity_score,
        )
        return 0

    from niche_radar.analysis import run_analysis

    use_tui = not getattr(args, "no_tui", False) and sys.stdout.isatty()
    if use_tui:
        from niche_radar.ui.pipeline_display import PipelineDisplay

        with PipelineDisplay() as display:
            count = run_analysis(
                db=db, settings=settings, dry_run=args.dry_run, log_fn=display.log
            )
    else:
        count = run_analysis(db=db, settings=settings, dry_run=args.dry_run, log_fn=print)
    logger.info("analysis_complete", niches_produced=count)
    return 0


def cmd_report(args: argparse.Namespace, settings) -> int:
    from niche_radar.reports.generator import generate_report
    from niche_radar.storage.database import get_db

    logger = structlog.get_logger()
    db = get_db(settings.database_url)
    path = generate_report(db=db, settings=settings)
    logger.info("report_generated", file=str(path))
    return 0


def cmd_serve(args: argparse.Namespace, settings) -> int:
    from niche_radar.scheduler import start_scheduler

    logger = structlog.get_logger()
    logger.info("scheduler_starting")
    start_scheduler(settings=settings)
    return 0


def cmd_cleanup(args: argparse.Namespace, settings) -> int:
    from niche_radar.storage.cleanup import run_cleanup
    from niche_radar.storage.database import get_db

    logger = structlog.get_logger()
    db = get_db(settings.database_url)
    deleted = run_cleanup(db=db, settings=settings, dry_run=args.dry_run)
    logger.info("cleanup_complete", rows_deleted=deleted)
    return 0


def cmd_status(args: argparse.Namespace, settings) -> int:
    from niche_radar.storage.database import get_db

    try:
        db = get_db(settings.database_url)
    except Exception:
        print("Database: NOT CONNECTED")
        print(f"Database URL: {settings.database_url}")
        return 0

    print(f"Niche Radar Alpha v{__import__('niche_radar').__version__}")
    print(f"Database: {settings.database_url}")

    stats = db.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM raw_items) as raw_count, "
        "(SELECT COUNT(*) FROM niche_candidates WHERE status='active') as niche_count, "
        "(SELECT MAX(started_at) FROM collection_runs) as last_run"
    ).fetchone()

    print(f"Raw items: {stats[0]}")
    print(f"Active niches: {stats[1]}")
    print(f"Last collection: {stats[2] or 'never'}")

    runs = db.execute(
        "SELECT source, status, started_at, items_collected "
        "FROM collection_runs ORDER BY started_at DESC LIMIT 5"
    ).fetchall()

    if runs:
        print("\nRecent collection runs:")
        for r in runs:
            print(f"  {r[0]:15s}  {r[1]:10s}  {r[2]}  ({r[3]} items)")

    return 0


COMMANDS = {
    "collect": cmd_collect,
    "analyze": cmd_analyze,
    "report": cmd_report,
    "serve": cmd_serve,
    "cleanup": cmd_cleanup,
    "status": cmd_status,
}


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    settings = get_settings()

    if args.log_level:
        settings.log_level = args.log_level
    if args.db:
        settings.database_url = args.db

    configure_logging(settings.log_level, settings.log_format)

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        return 3

    try:
        return handler(args, settings)
    except Exception as exc:
        logger = structlog.get_logger()
        logger.error("command_failed", command=args.command, error=str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())

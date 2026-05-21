"""LLM-powered niche analysis — v3 (8-agent pipeline).

The single-prompt batched analyzer is now replaced by `niche_radar.agents.pipeline`.
This module retains a thin `run_analysis` wrapper (the existing entry point used by
`__main__.py:cmd_analyze` and the scheduler) plus the legacy `_get_llm_client` factory
which `api/server.py:185` still imports for the /api/settings/test endpoint.
"""

from __future__ import annotations

import sqlite3

import structlog

from niche_radar.storage.repository import (
    archive_stale_niches,
    get_app_setting,
)

logger = structlog.get_logger()


def _get_llm_client(db: sqlite3.Connection, settings):
    """Build a generic LLM client from DB-persisted /settings (env-var fallback).

    Used by /api/settings/test and the legacy path. The 8-agent pipeline does its own
    per-agent client resolution via niche_radar.agents.llm_config.
    """
    provider = get_app_setting(db, "llm_provider") or settings.llm_provider
    api_key = get_app_setting(db, "llm_api_key") or settings.llm_api_key
    model = get_app_setting(db, "llm_model") or settings.llm_model
    base_url = get_app_setting(db, "llm_base_url") or settings.llm_base_url

    if not api_key:
        raise ValueError(
            "LLM API key not configured. Set it in Settings or LLM_API_KEY env var."
        )

    if provider == "anthropic":
        from niche_radar.llm.anthropic_client import AnthropicClient
        return AnthropicClient(api_key=api_key, model=model)
    else:
        from niche_radar.llm.openai_compat import OpenAICompatClient
        return OpenAICompatClient(
            api_key=api_key, model=model, base_url=base_url or None
        )


def run_analysis(
    db: sqlite3.Connection,
    settings,
    dry_run: bool = False,
    *,
    log_fn=None,
) -> int:
    """Run the 8-agent pipeline over unprocessed raw items.

    Returns the count of niche_analyses rows persisted (one per cluster). For
    backward compatibility with callers (CLI, scheduler) that read this number as
    "niches produced", a row count of clusters is the closest match.
    """
    # Freshness archiving stays here — orthogonal to verdict, just an age check.
    archived = archive_stale_niches(db, settings.analysis_window_days)
    if archived:
        logger.info(
            "niches_archived_stale",
            count=archived,
            window_days=settings.analysis_window_days,
        )

    # Import locally so a stale install with the agents/ folder missing still loads
    # this module (e.g., for the /api/settings/test endpoint).
    from niche_radar.agents.pipeline import run_pipeline

    try:
        summary = run_pipeline(db, settings, dry_run=dry_run, log_fn=log_fn)
    except ValueError as exc:
        logger.error("llm_not_configured", error=str(exc))
        return 0

    logger.info("analysis_finished", **summary, dry_run=dry_run)
    return summary.get("persisted", 0) or 0

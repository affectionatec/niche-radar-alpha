"""LLM-powered niche analysis: raw items → niche candidates."""

from __future__ import annotations

import sqlite3

import structlog

from niche_radar.storage.repository import (
    get_app_setting,
    get_unprocessed_items,
    link_niche_item,
    upsert_niche_candidate,
)

logger = structlog.get_logger()

_ANALYSIS_PROMPT = """\
You are a niche opportunity analyst for indie hackers and SaaS founders.

Analyze the items below, collected from Reddit, Hacker News, GitHub Trending, \
Google Trends, and YouTube. Identify distinct niche opportunities — specific \
problem spaces where products or services could be built.

For each niche return:
- keyword: 2-5 word lowercase label (e.g. "ai code review", "personal finance automation")
- aliases: 2-4 related phrasings as a list
- reasoning: 1-2 sentences explaining the opportunity and what evidence you see
- score: integer 0-100 (strength of signal: pain level, demand, monetization potential, trend momentum)
- item_ids: list of item IDs from below that support this niche

Focus on: pain points, tool requests, trending tech, underserved markets.
Skip: generic news, opinion pieces, items with no clear product opportunity.

Return ONLY a JSON object:
{{"niches": [{{"keyword": "...", "aliases": [...], "reasoning": "...", "score": 75, "item_ids": [...]}}]}}

Items (ID | SOURCE | TITLE | SCORE):
{items_text}
"""


def _get_llm_client(db: sqlite3.Connection, settings):
    """Build LLM client, preferring DB-persisted settings over env vars."""
    provider = get_app_setting(db, "llm_provider") or settings.llm_provider
    api_key = get_app_setting(db, "llm_api_key") or settings.llm_api_key
    model = get_app_setting(db, "llm_model") or settings.llm_model
    base_url = get_app_setting(db, "llm_base_url") or settings.llm_base_url

    if not api_key:
        raise ValueError("LLM API key not configured. Set it in Settings or LLM_API_KEY env var.")

    if provider == "anthropic":
        from niche_radar.llm.anthropic_client import AnthropicClient
        return AnthropicClient(api_key=api_key, model=model)
    else:
        from niche_radar.llm.openai_compat import OpenAICompatClient
        return OpenAICompatClient(api_key=api_key, model=model, base_url=base_url or None)


def _format_items(items: list[dict]) -> str:
    lines = []
    for item in items:
        title = (item.get("title") or "").replace("\n", " ").strip()[:120]
        score = item.get("score") or 0
        lines.append(f"{item['id']} | {item['source']} | {title} | {score}")
    return "\n".join(lines)


def _process_batch(
    db: sqlite3.Connection,
    client,
    batch: list[dict],
    dry_run: bool,
) -> int:
    """Send one batch to the LLM, persist results. Returns number of niches produced."""
    item_ids = {item["id"] for item in batch}
    items_text = _format_items(batch)
    prompt = _ANALYSIS_PROMPT.format(items_text=items_text)

    try:
        result = client.complete_json(prompt)
    except Exception as exc:
        logger.error("llm_batch_failed", error=str(exc))
        return 0

    niches = result.get("niches", [])
    if not isinstance(niches, list):
        logger.warning("llm_unexpected_response", response_keys=list(result.keys()))
        return 0

    produced = 0
    for niche_data in niches:
        keyword = str(niche_data.get("keyword", "")).strip()
        if not keyword:
            continue
        aliases = niche_data.get("aliases") or []
        reasoning = str(niche_data.get("reasoning", ""))
        score = float(niche_data.get("score", 0))
        score = max(0.0, min(100.0, score))
        supporting_ids = [i for i in (niche_data.get("item_ids") or []) if i in item_ids]

        if not dry_run:
            niche_id = upsert_niche_candidate(db, keyword, aliases, score, reasoning)
            for item_id in supporting_ids:
                link_niche_item(db, niche_id, item_id, keyword, 1.0)

        produced += 1

    return produced


def run_analysis(db: sqlite3.Connection, settings, dry_run: bool = False) -> int:
    """Analyze unprocessed raw items with LLM. Returns number of niches produced."""
    items = get_unprocessed_items(db, limit=500)
    if not items:
        logger.info("analysis_skipped", reason="no_unprocessed_items")
        return 0

    try:
        client = _get_llm_client(db, settings)
    except ValueError as exc:
        logger.error("llm_not_configured", error=str(exc))
        return 0

    batch_size = settings.llm_batch_size
    total_niches = 0

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        produced = _process_batch(db, client, batch, dry_run)
        total_niches += produced
        logger.info("analysis_batch_done", batch=i // batch_size + 1, items=len(batch), niches=produced)

    logger.info("analysis_finished", items=len(items), niches=total_niches, dry_run=dry_run)
    return total_niches

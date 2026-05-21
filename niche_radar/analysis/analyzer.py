"""LLM-powered AI tool opportunity discovery: raw items → buildable tool ideas."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import structlog

from niche_radar.storage.repository import (
    archive_stale_niches,
    get_app_setting,
    get_unprocessed_items,
    link_niche_item,
    upsert_niche_candidate,
)

logger = structlog.get_logger()

# Max concurrent LLM batch requests. DeepSeek's rate limit is generous; 8 is a safe
# default that gives near-perfect speedup for 8-10 batches without throttling.
_MAX_CONCURRENCY = 8

_ANALYSIS_PROMPT = """\
You scout BUILDABLE AI-tool product ideas for a solo indie hacker who wants \
to ship a small AI-powered web tool, attract organic traffic, and monetize via ads.

You are reading raw posts/discussions/searches collected from Reddit, Hacker News, \
GitHub Trending, Google Trends, and YouTube.

For EACH item, mentally ask: "Is someone expressing a pain, wish, frustration, \
unmet need, or 'I'd pay for this' moment that an AI tool could solve in 1-5 days?"

Then CLUSTER similar pain signals into distinct AI-tool opportunities. Aggressively \
filter out: generic tech news, opinion pieces, hot takes, political content, \
already-saturated categories (general chatbots, basic GPT wrappers), and items \
with no clear product implication.

For each opportunity return:
- keyword: short 2-5 word slug, lowercase (e.g. "ai meeting note splitter")
- tool_concept: ONE crisp sentence — "An AI tool that <verb> <object> for <audience>"
- aliases: 2-4 related searches/phrasings users might use
- target_audience: who would pay attention (e.g. "freelance video editors", "Shopify shop owners")
- pain_points: array of 2-4 specific pains, each with a SHORT verbatim or paraphrased \
  quote from the source items. Format: [{{"pain": "...", "quote": "...", "item_id": "..."}}]
- demand_evidence: 1-2 sentence summary of WHY this is hot now (which sources, momentum, \
  how many distinct mentions you saw, any trend direction)
- build_complexity: integer 1-5 (1 = "weekend build, single OpenAI API call wrapper", \
  5 = "needs custom model, scraping, or significant infra")
- monetization: which ad-monetization angle works (e.g. "high-intent search traffic — \
  AdSense", "B2B audience — newsletter sponsor slots", "tutorial videos with affiliate \
  links to AI APIs"). Be specific.
- score: integer 0-100 combining pain intensity + audience size + monetization potential \
  + trend momentum
- item_ids: list of item IDs from below that support this opportunity (at least 1)

Bias toward: narrow audiences with specific repeated complaints; tools that can be \
shipped in under a week; clear ad-monetization paths (high search-intent or B2B niches).

Return ONLY valid JSON:
{{"opportunities": [
  {{"keyword": "...", "tool_concept": "...", "aliases": [...], "target_audience": "...", \
"pain_points": [{{"pain": "...", "quote": "...", "item_id": "..."}}], \
"demand_evidence": "...", "build_complexity": 2, "monetization": "...", "score": 75, \
"item_ids": [...]}}
]}}

CRITICAL: Items include their AGE (hours/days ago). Prioritize signals from the \
last 48-72 hours. Older items in the window are still valid but weight them less. \
Skip ANY opportunity that appears driven entirely by items >5 days old.

Items (ID | SOURCE | AGE | TITLE | SCORE | COMMENTS):
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
    """Format items with age — newer items should carry more weight in the LLM's judgment."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    lines = []
    for item in items:
        title = (item.get("title") or "").replace("\n", " ").strip()[:140]
        score = item.get("score") or 0
        comments = item.get("comment_count") or 0
        age = "?"
        posted = item.get("posted_at")
        if posted:
            try:
                dt = datetime.fromisoformat(str(posted).replace("Z", "+00:00"))
                hours = (now - dt).total_seconds() / 3600
                if hours < 24:
                    age = f"{hours:.0f}h ago"
                else:
                    age = f"{hours / 24:.0f}d ago"
            except (ValueError, TypeError):
                pass
        lines.append(f"{item['id']} | {item['source']} | {age} | {title} | {score} | {comments}")
    return "\n".join(lines)


def _call_llm_for_batch(client, batch: list[dict], batch_idx: int) -> tuple[int, list[dict]]:
    """Pure LLM call — no DB access. Safe to run in a worker thread.

    Returns (batch_idx, raw_opportunities_list). Errors are swallowed and logged.
    """
    items_text = _format_items(batch)
    prompt = _ANALYSIS_PROMPT.format(items_text=items_text)
    try:
        result = client.complete_json(prompt)
    except Exception as exc:
        logger.error("llm_batch_failed", batch=batch_idx, error=str(exc))
        return batch_idx, []

    opps = result.get("opportunities") or result.get("niches") or []
    if not isinstance(opps, list):
        logger.warning("llm_unexpected_response", batch=batch_idx, response_keys=list(result.keys()))
        return batch_idx, []
    return batch_idx, opps


def _persist_batch(
    db: sqlite3.Connection,
    batch: list[dict],
    opps: list[dict],
    dry_run: bool,
) -> int:
    """Write one batch's LLM results to the DB. Runs in the main thread (SQLite single-threaded)."""
    item_ids = {item["id"] for item in batch}
    produced = 0

    for opp in opps:
        keyword = str(opp.get("keyword", "")).strip()
        if not keyword:
            continue

        aliases = opp.get("aliases") or []
        tool_concept = str(opp.get("tool_concept", "")).strip()
        target_audience = str(opp.get("target_audience", "")).strip()
        monetization = str(opp.get("monetization", "")).strip()
        demand_evidence = str(opp.get("demand_evidence", "")).strip()

        try:
            build_complexity = int(opp.get("build_complexity", 3))
            build_complexity = max(1, min(5, build_complexity))
        except (TypeError, ValueError):
            build_complexity = 3

        try:
            score = float(opp.get("score", 0))
        except (TypeError, ValueError):
            score = 0.0
        score = max(0.0, min(100.0, score))

        raw_pains = opp.get("pain_points") or []
        pain_points = []
        if isinstance(raw_pains, list):
            for p in raw_pains:
                if not isinstance(p, dict):
                    continue
                pain_points.append({
                    "pain": str(p.get("pain", "")).strip(),
                    "quote": str(p.get("quote", "")).strip(),
                    "item_id": str(p.get("item_id", "")).strip(),
                })

        supporting_ids = [i for i in (opp.get("item_ids") or []) if i in item_ids]
        if not supporting_ids:
            supporting_ids = [p["item_id"] for p in pain_points if p["item_id"] in item_ids]

        reasoning = demand_evidence or tool_concept

        if not dry_run:
            niche_id = upsert_niche_candidate(
                db, keyword, aliases, score, reasoning,
                tool_concept=tool_concept,
                target_audience=target_audience,
                build_complexity=build_complexity,
                monetization=monetization,
                pain_points=pain_points,
            )
            for item_id in supporting_ids:
                link_niche_item(db, niche_id, item_id, keyword, 1.0)

        produced += 1

    return produced


def run_analysis(db: sqlite3.Connection, settings, dry_run: bool = False) -> int:
    """Analyze unprocessed raw items. LLM batches run in parallel; DB writes serial."""
    # Auto-archive niches that haven't been seen in the analysis window — they're stale.
    archived = archive_stale_niches(db, settings.analysis_window_days)
    if archived:
        logger.info("niches_archived_stale", count=archived, window_days=settings.analysis_window_days)

    items = get_unprocessed_items(db, limit=500, max_age_days=settings.analysis_window_days)
    if not items:
        logger.info(
            "analysis_skipped",
            reason="no_fresh_unprocessed_items",
            window_days=settings.analysis_window_days,
        )
        return 0

    try:
        client = _get_llm_client(db, settings)
    except ValueError as exc:
        logger.error("llm_not_configured", error=str(exc))
        return 0

    batch_size = settings.llm_batch_size
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    workers = min(len(batches), _MAX_CONCURRENCY)

    logger.info(
        "analysis_starting",
        items=len(items),
        batches=len(batches),
        batch_size=batch_size,
        workers=workers,
    )

    # Fire all LLM calls concurrently — they're independent and IO-bound.
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_call_llm_for_batch, client, batch, idx)
            for idx, batch in enumerate(batches)
        ]
        # Preserve batch order so DB writes match the batches list
        results_by_idx: dict[int, list[dict]] = {}
        for f in futures:
            idx, opps = f.result()
            results_by_idx[idx] = opps

    # Persist sequentially — SQLite connections are single-threaded.
    total = 0
    for idx, batch in enumerate(batches):
        opps = results_by_idx.get(idx, [])
        produced = _persist_batch(db, batch, opps, dry_run)
        total += produced
        logger.info("analysis_batch_done", batch=idx + 1, items=len(batch), opps=produced)

    logger.info("analysis_finished", items=len(items), opps=total, dry_run=dry_run)
    return total

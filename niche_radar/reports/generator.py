"""Generate the actionable AI-tool opportunity briefing (markdown)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import structlog

from niche_radar.storage.repository import get_active_niches_with_scores, get_app_setting

logger = structlog.get_logger()

_PROSE_PROMPT = """\
You are briefing an indie hacker on this week's most buildable AI-tool opportunities.

Here are the top opportunities scouted from Reddit, Hacker News, GitHub Trending, \
Google Trends, and YouTube — ranked by (score × quick-build factor):

{opp_list}

Write a tight executive briefing (4-6 sentences, direct, no fluff). Cover:
- Your TOP 1 pick and why (the one to start building today)
- 2 strong alternates and what makes them attractive
- Any cross-cutting pattern you noticed (e.g. "audio tooling is hot this week")
- Anything to AVOID (overcrowded categories that showed up)

Talk like a sharp friend who has skin in the game. No marketing voice, no hedging.
"""


def _build_prose(client, opportunities: list[dict]) -> str:
    lines = []
    for i, o in enumerate(opportunities[:12], 1):
        concept = o.get("tool_concept") or o["keyword"]
        complexity = o.get("build_complexity") or "?"
        score = o.get("llm_score") or 0
        lines.append(f"{i}. [{score:.0f}, build={complexity}/5] {concept}")
    return _call_prose_llm(client, "\n".join(lines))


def _call_prose_llm(client, opp_list: str) -> str:
    prompt = _PROSE_PROMPT.format(opp_list=opp_list)
    try:
        return client.complete(prompt)
    except Exception as exc:
        logger.warning("prose_generation_failed", error=str(exc))
        return ""


def _get_llm_client(db: sqlite3.Connection, settings):
    provider = get_app_setting(db, "llm_provider") or settings.llm_provider
    api_key = get_app_setting(db, "llm_api_key") or settings.llm_api_key
    model = get_app_setting(db, "llm_model") or settings.llm_model
    base_url = get_app_setting(db, "llm_base_url") or settings.llm_base_url

    if not api_key:
        return None

    if provider == "anthropic":
        from niche_radar.llm.anthropic_client import AnthropicClient
        return AnthropicClient(api_key=api_key, model=model)
    else:
        from niche_radar.llm.openai_compat import OpenAICompatClient
        return OpenAICompatClient(api_key=api_key, model=model, base_url=base_url or None)


def generate_report(db: sqlite3.Connection, settings) -> Path:
    opportunities = get_active_niches_with_scores(db)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_dir = Path(settings.report_output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    prose = ""
    client = _get_llm_client(db, settings)
    if client and opportunities:
        prose = _build_prose(client, opportunities)

    md_path = report_dir / f"{date_str}.md"
    md_path.write_text(_build_markdown(date_str, opportunities, prose), encoding="utf-8")
    logger.info("report_written", path=str(md_path), opps=len(opportunities))
    return md_path


def _complexity_label(c: int | None) -> str:
    if c is None:
        return "unknown"
    return {1: "weekend", 2: "2-3 days", 3: "~1 week", 4: "1-2 weeks", 5: "2+ weeks"}.get(c, "unknown")


def _build_markdown(date_str: str, opps: list[dict], prose: str) -> str:
    total = len(opps)
    quick_wins = [o for o in opps if (o.get("build_complexity") or 5) <= 2 and o.get("llm_score", 0) >= 70]

    lines = [
        f"# AI Tool Opportunities — {date_str}",
        "",
        f"_{total} opportunities scouted • {len(quick_wins)} quick-win candidates (build≤2, score≥70)_",
        "",
    ]

    if prose:
        lines += ["## TL;DR", "", prose, ""]

    if quick_wins:
        lines += ["## ⚡ Quick Wins (Start Here)", ""]
        for i, o in enumerate(quick_wins[:5], 1):
            lines.append(_render_opportunity(i, o, compact=True))
        lines.append("")

    lines += ["## Full Opportunity List", ""]
    for i, o in enumerate(opps, 1):
        lines.append(_render_opportunity(i, o, compact=False))

    return "\n".join(lines)


def _render_opportunity(idx: int, o: dict, compact: bool) -> str:
    concept = o.get("tool_concept") or o["keyword"].title()
    score = o.get("llm_score") or 0
    complexity = o.get("build_complexity")
    complexity_str = _complexity_label(complexity)
    audience = o.get("target_audience") or "—"
    monetization = o.get("monetization") or "—"
    aliases = o.get("aliases") or []
    pains = o.get("pain_points") or []
    reasoning = o.get("llm_reasoning") or ""
    mentions = o.get("occurrence_count") or 0

    parts = [
        f"### {idx}. {concept}",
        "",
        f"**Score** `{score:.0f}/100` · **Build** `{complexity_str}` "
        f"({complexity}/5) · **Mentions** `{mentions}`",
        "",
        f"**Audience:** {audience}",
        "",
        f"**Monetization:** {monetization}",
        "",
    ]

    if reasoning and not compact:
        parts += [f"**Why it's hot:** {reasoning}", ""]

    if pains and not compact:
        parts.append("**Pain signals:**")
        for p in pains[:4]:
            pain_text = p.get("pain", "")
            quote = p.get("quote", "")
            if quote:
                parts.append(f"- _{pain_text}_ — \"{quote}\"")
            else:
                parts.append(f"- {pain_text}")
        parts.append("")

    if aliases and not compact:
        parts.append(f"**Related searches:** {', '.join(aliases)}")
        parts.append("")

    parts.append("---")
    parts.append("")
    return "\n".join(parts)

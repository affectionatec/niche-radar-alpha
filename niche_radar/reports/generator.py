"""Generate markdown and JSON niche reports."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import structlog

from niche_radar.storage.repository import get_active_niches_with_scores, get_app_setting

logger = structlog.get_logger()

_PROSE_PROMPT = """\
You are summarizing a niche opportunity report for an indie hacker or SaaS founder.

Here are today's top niche opportunities, identified by analyzing signals from \
Reddit, Hacker News, GitHub Trending, Google Trends, and YouTube:

{niche_list}

Write a concise executive summary (3-5 sentences). Highlight the strongest \
opportunities, notable patterns across niches, and what to watch. Be direct and specific.
"""


def _build_prose(client, niches: list[dict]) -> str:
    lines = []
    for i, n in enumerate(niches[:15], 1):
        lines.append(f"{i}. {n['keyword']} (score: {n['llm_score']:.0f}) — {n['llm_reasoning']}")
    niche_list = "\n".join(lines)
    prompt = _PROSE_PROMPT.format(niche_list=niche_list)
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


def generate_report(db: sqlite3.Connection, settings, fmt: str = "both") -> list[Path]:
    niches = get_active_niches_with_scores(db)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_dir = Path(settings.report_output_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    prose = ""
    client = _get_llm_client(db, settings)
    if client and niches:
        prose = _build_prose(client, niches)

    paths: list[Path] = []

    if fmt in ("markdown", "both"):
        md_path = report_dir / f"{date_str}.md"
        md_path.write_text(_build_markdown(date_str, niches, prose), encoding="utf-8")
        paths.append(md_path)
        logger.info("report_written", path=str(md_path))

    if fmt in ("json", "both"):
        json_path = report_dir / f"{date_str}.json"
        payload = {
            "date": date_str,
            "prose_summary": prose,
            "niches": niches,
        }
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        paths.append(json_path)
        logger.info("report_written", path=str(json_path))

    return paths


def _build_markdown(date_str: str, niches: list[dict], prose: str) -> str:
    lines = [f"# Niche Radar Report — {date_str}", ""]

    if prose:
        lines += [prose, ""]

    lines += ["## Top Niches", ""]
    for i, n in enumerate(niches, 1):
        score = f"{n['llm_score']:.0f}"
        lines.append(f"### {i}. {n['keyword'].title()} (Score: {score})")
        if n["llm_reasoning"]:
            lines.append(f"\n{n['llm_reasoning']}")
        if n["aliases"]:
            lines.append(f"\n**Related:** {', '.join(n['aliases'])}")
        lines.append(
            f"\n**Mentions:** {n['occurrence_count']} | "
            f"**First seen:** {n['first_seen'][:10]} | "
            f"**Last seen:** {n['last_seen'][:10]}"
        )
        lines.append("")

    return "\n".join(lines)

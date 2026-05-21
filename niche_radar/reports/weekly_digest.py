"""Weekly digest report — top 5 niches ranked by weighted_score + momentum.

Generates reports/weekly-YYYY-MM-DD.md. Called by the scheduler on Mondays at 09:00 UTC.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def generate_weekly_digest(db: sqlite3.Connection, output_dir: Path) -> Path:
    """Write a weekly-YYYY-MM-DD.md digest and return the path."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = output_dir / f"weekly-{today}.md"
    output_dir.mkdir(parents=True, exist_ok=True)

    last_week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

    # Top 5 niches by weighted_score with momentum
    top = db.execute(
        """
        SELECT nc.keyword, nc.tool_concept, nc.llm_score, nc.target_audience,
               nc.momentum_label, nc.momentum_ratio, nc.verdict,
               (SELECT COUNT(*) FROM niche_item_links nil
                JOIN raw_items ri ON nil.raw_item_id=ri.id
                WHERE nil.niche_id=nc.id AND ri.posted_at>=?) AS this_week_mentions,
               na.web_validation
        FROM niche_candidates nc
        LEFT JOIN niche_analyses na ON nc.latest_analysis_id = na.id
        WHERE nc.status='active'
        ORDER BY nc.llm_score DESC
        LIMIT 5
        """,
        (last_week,),
    ).fetchall()

    # Previous week digest for comparison (look for previous file)
    prev_file = next(
        (f for f in sorted(output_dir.glob("weekly-*.md"), reverse=True)
         if f.name != path.name),
        None,
    )

    lines = [
        f"# Niche Radar — Weekly Digest ({today})",
        "",
        "_Top opportunities discovered this week, ranked by opportunity score._",
        "",
    ]

    if prev_file:
        lines += [f"> Previous digest: [{prev_file.name}]({prev_file.name})", ""]

    if not top:
        lines += ["> No active niches found. Run `collect` + `analyze` to populate.", ""]
    else:
        for i, row in enumerate(top, 1):
            keyword, concept, score, audience, momentum_label, momentum_ratio, verdict, mentions, web_val = row
            score = round(score or 0, 1)
            momentum_label = momentum_label or "stable"
            verdict = verdict or "—"
            mentions = mentions or 0

            momentum_emoji = {"growing": "📈", "declining": "📉", "stable": "➡️"}.get(momentum_label, "➡️")
            verdict_emoji = {"GO": "🟢", "NO-GO": "🔴", "PIVOT": "🟡"}.get(verdict, "⬜")

            import json
            web_verdict = "—"
            if web_val:
                try:
                    wv = json.loads(web_val)
                    web_verdict = wv.get("verdict", "—").replace("_", " ").title()
                except Exception:
                    pass

            lines += [
                f"## {i}. {keyword}",
                "",
                f"**Score:** {score}/100 &nbsp; {verdict_emoji} **Verdict:** {verdict} &nbsp; {momentum_emoji} **Trend:** {momentum_label} ({momentum_ratio or '—'})",
                "",
                f"**Concept:** {concept or '—'}",
                "",
                f"**Target:** {audience or '—'}",
                "",
                f"**Mentions this week:** {mentions} &nbsp; **Market check:** {web_verdict}",
                "",
                "---",
                "",
            ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path

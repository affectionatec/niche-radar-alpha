"""Hardcoded test signal from refactor_prompt.md §TEST SIGNAL.

Used by `python -m niche_radar analyze --test` to exercise the entire pipeline end-to-end
with a single high-quality input. Roughly 8 LLM calls (A1..A8) for one signal.
"""

from __future__ import annotations

TEST_SIGNAL: dict = {
    "text": (
        "I've been manually copying data from our AWS Cost Explorer into a spreadsheet "
        "every month to generate reports for my manager. There HAS to be a better way. "
        "I've looked at CloudHealth and it's $500/month which is insane for a 20-person "
        "company. Anyone built something simple for this?"
    ),
    "source": "reddit",
    "url": "https://reddit.com/r/sysadmin/...",
    "scraped_at": "2026-05-20T10:00:00Z",
}

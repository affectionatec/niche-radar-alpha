"""8-agent sequential LLM analysis pipeline.

Usage:
    python -m agents.pipeline --test
    python -m agents.pipeline --signal-id <uuid>
    python -m agents.pipeline --signal-id <uuid> --no-save
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys

import structlog

from agents.llm import LLMCaller
from agents.models import PipelineResult
from agents.prompts import AGENT_SYSTEMS, build_user_prompt
from agents.scorer import opportunity_score, tier

logger = structlog.get_logger()

TEST_SIGNAL: dict = {
    "text": (
        "I've been manually copying data from our AWS Cost "
        "Explorer into a spreadsheet every month to generate reports "
        "for my manager. There HAS to be a better way. I've looked "
        "at CloudHealth and it's $500/month which is insane for a "
        "20-person company. Anyone built something simple for this?"
    ),
    "source": "reddit",
    "url": "https://reddit.com/r/sysadmin/...",
    "scraped_at": "2026-05-20T10:00:00Z",
}

# Temperature per agent
_TEMPERATURES: dict[int, float] = {
    1: 0.2,  # Signal Filter — analytical
    2: 0.2,  # Pain Extractor — analytical
    3: 0.4,  # Market Researcher — some creativity
    4: 0.2,  # Opportunity Scorer — analytical
    5: 0.4,  # Feasibility Analyst — creative
    6: 0.4,  # Go/No-Go — decisive, some variation
    7: 0.4,  # PRD Generator — creative
    8: 0.4,  # Opportunity Brief — creative synthesis
}


class PipelineOrchestrator:
    """Runs the 8-agent sequential analysis pipeline."""

    def __init__(self, settings) -> None:
        self.llm = LLMCaller(settings)

    def run(self, raw_signal: dict) -> PipelineResult:
        """Run the full pipeline on a raw signal dict.

        Args:
            raw_signal: dict with keys: text, source, url, scraped_at

        Returns:
            PipelineResult with all agent outputs populated.
        """
        context: dict = {"raw_signal": raw_signal}
        result = PipelineResult(raw_signal=raw_signal)

        # ── A1: Signal Filter ────────────────────────────────────────────
        logger.info("pipeline_agent_start", agent=1, role="signal_filter")
        a1 = self._call_agent(1, context)
        context["a1"] = result.a1 = a1
        logger.info(
            "pipeline_agent_done",
            agent=1,
            is_valid=a1.get("is_valid_signal"),
            confidence=a1.get("confidence"),
        )

        if not a1.get("is_valid_signal"):
            result.verdict = "REJECTED"
            logger.info(
                "pipeline_short_circuit",
                reason=a1.get("rejection_reason"),
                signal_type=a1.get("signal_type"),
            )
            # Still generate the brief for rejected signals
            context["a8"] = result.a8 = self._call_agent(8, context)
            return result

        # ── A2: Pain Extractor ───────────────────────────────────────────
        logger.info("pipeline_agent_start", agent=2, role="pain_extractor")
        context["a2"] = result.a2 = self._call_agent(2, context)
        logger.info("pipeline_agent_done", agent=2)

        # ── A3: Market Researcher ────────────────────────────────────────
        logger.info("pipeline_agent_start", agent=3, role="market_researcher")
        context["a3"] = result.a3 = self._call_agent(3, context)
        logger.info("pipeline_agent_done", agent=3)

        # ── A4: Opportunity Scorer ───────────────────────────────────────
        logger.info("pipeline_agent_start", agent=4, role="opportunity_scorer")
        context["a4"] = result.a4 = self._call_agent(4, context)
        a4 = context["a4"]
        if not a4.get("_error") and "scores" in a4:
            result.opportunity_score = opportunity_score(a4["scores"])
            result.tier = tier(a4.get("total_score", 0))
        logger.info(
            "pipeline_agent_done",
            agent=4,
            total_score=a4.get("total_score"),
            opportunity_score=result.opportunity_score,
            tier=result.tier,
        )

        # ── A5: Feasibility Analyst ──────────────────────────────────────
        logger.info("pipeline_agent_start", agent=5, role="feasibility_analyst")
        context["a5"] = result.a5 = self._call_agent(5, context)
        logger.info("pipeline_agent_done", agent=5)

        # ── A6: Go / No-Go Judge ─────────────────────────────────────────
        logger.info("pipeline_agent_start", agent=6, role="go_nogo_judge")
        context["a6"] = result.a6 = self._call_agent(6, context)
        a6 = context["a6"]
        result.verdict = a6.get("verdict", "NO-GO") if not a6.get("_error") else "FAILED"
        logger.info(
            "pipeline_agent_done",
            agent=6,
            verdict=result.verdict,
            confidence=a6.get("confidence"),
        )

        # ── A7: PRD Generator (only on GO) ───────────────────────────────
        if result.verdict == "GO":
            logger.info("pipeline_agent_start", agent=7, role="prd_generator")
            context["a7"] = result.a7 = self._call_agent(7, context)
            logger.info("pipeline_agent_done", agent=7)
        else:
            logger.info("pipeline_agent_skipped", agent=7, reason=f"verdict={result.verdict}")

        # ── A8: Opportunity Brief (always) ───────────────────────────────
        logger.info("pipeline_agent_start", agent=8, role="opportunity_brief")
        context["a8"] = result.a8 = self._call_agent(8, context)
        logger.info("pipeline_agent_done", agent=8)

        logger.info(
            "pipeline_complete",
            verdict=result.verdict,
            tier=result.tier,
            opportunity_score=result.opportunity_score,
        )
        return result

    def _call_agent(self, agent_id: int, context: dict) -> dict:
        system = AGENT_SYSTEMS[agent_id]
        user = build_user_prompt(agent_id, context)
        return self.llm.call(
            system=system,
            user=user,
            temperature=_TEMPERATURES[agent_id],
            agent_id=agent_id,
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m agents.pipeline",
        description="Run the 8-agent LLM analysis pipeline on a scraped signal.",
    )
    p.add_argument(
        "--signal-id",
        metavar="UUID",
        help="UUID of a raw_item in the database to analyze",
    )
    p.add_argument(
        "--test",
        action="store_true",
        help="Run on the built-in AWS Cost Explorer test signal",
    )
    p.add_argument(
        "--no-save",
        action="store_true",
        help="Do not persist the result to the database",
    )
    p.add_argument("--db", default=None, help="Override DATABASE_URL")
    p.add_argument("--log-level", default="INFO", help="Logging level")
    return p


def _print_summary(result: PipelineResult) -> None:
    """Print a compact human-readable summary of the pipeline result."""
    print("\n" + "=" * 60)
    print("PIPELINE RESULT")
    print("=" * 60)
    print(f"Verdict:           {result.verdict}")
    print(f"Tier:              {result.tier or 'N/A'}")
    print(f"Opportunity Score: {result.opportunity_score or 'N/A'}")
    print(f"Analyzed At:       {result.analyzed_at}")

    if result.a1:
        print(f"\nA1 Signal Filter:  valid={result.a1.get('is_valid_signal')}  "
              f"confidence={result.a1.get('confidence')}")
        if result.a1.get("pain_summary"):
            print(f"  Pain: {result.a1['pain_summary']}")
        if result.a1.get("rejection_reason"):
            print(f"  Rejected: {result.a1['rejection_reason']}")

    if result.a4 and not result.a4.get("_error"):
        print(f"\nA4 Opportunity Score: {result.a4.get('total_score')}/70")
        strengths = result.a4.get("top_3_strengths", [])
        if strengths:
            print(f"  Strengths: {', '.join(strengths)}")

    if result.a6 and not result.a6.get("_error"):
        print(f"\nA6 Verdict: {result.a6.get('verdict')}  "
              f"({result.a6.get('one_line_rationale')})")
        print(f"  Next step: {result.a6.get('recommended_next_step')}")

    if result.a8 and not result.a8.get("_error"):
        print(f"\nA8 Brief: {result.a8.get('verdict_badge')} {result.a8.get('title')}")
        print(f"  {result.a8.get('tldr')}")

    print("=" * 60 + "\n")


def main() -> int:
    import logging

    from dotenv import load_dotenv
    load_dotenv()

    from niche_radar.config import get_settings
    settings = get_settings()

    parser = _build_parser()
    args = parser.parse_args()

    if args.db:
        settings.database_url = args.db

    # Configure logging
    level_num = getattr(logging, args.log_level.upper(), logging.INFO)
    import structlog as sl
    sl.configure(
        processors=[
            sl.contextvars.merge_contextvars,
            sl.processors.add_log_level,
            sl.processors.TimeStamper(fmt="iso"),
            sl.dev.ConsoleRenderer(),
        ],
        wrapper_class=sl.make_filtering_bound_logger(level_num),
        context_class=dict,
        logger_factory=sl.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    if not args.test and not args.signal_id:
        parser.error("One of --test or --signal-id is required.")
        return 1

    raw_item_id: str | None = None

    if args.test:
        raw_signal = TEST_SIGNAL
    else:
        from niche_radar.storage.database import get_db
        from niche_radar.storage.repository import get_raw_item_by_id

        db = get_db(settings.database_url)
        item = get_raw_item_by_id(db, args.signal_id)
        if item is None:
            print(f"Error: no raw_item found with id={args.signal_id}", file=sys.stderr)
            return 1
        raw_item_id = item["id"]
        raw_signal = {
            "text": f"{item['title'] or ''}\n\n{item['body'] or ''}".strip(),
            "source": item["source"],
            "url": item["url"] or "",
            "scraped_at": item["collected_at"],
        }

    orchestrator = PipelineOrchestrator(settings)
    result = orchestrator.run(raw_signal)

    _print_summary(result)

    if not args.no_save:
        from niche_radar.storage.database import get_db
        from niche_radar.storage.repository import insert_pipeline_result

        db = get_db(settings.database_url)
        result_id = insert_pipeline_result(
            db=db,
            raw_item_id=raw_item_id,
            source=raw_signal.get("source", ""),
            scraped_at=raw_signal.get("scraped_at"),
            verdict=result.verdict,
            opportunity_score=result.opportunity_score,
            tier=result.tier,
            full_result=dataclasses.asdict(result),
        )
        print(f"Result saved: {result_id}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""End-to-end tests for the 4-phase pipeline driver — all LLM calls mocked."""

from __future__ import annotations

import pytest

from niche_radar.agents.aggregate import aggregate_cluster_a2
from niche_radar.agents.pipeline import (
    BudgetExceeded,
    BudgetTracker,
    run_pipeline,
    run_pipeline_on_signal,
)
from niche_radar.config import Settings
from niche_radar.storage.repository import (
    insert_collection_run,
    upsert_raw_item,
)


@pytest.fixture
def settings():
    """Minimal Settings instance. The LLM fields can stay default since we pass overrides."""
    return Settings(
        llm_api_key="fake",
        llm_provider="openai_compat",
        llm_model="test-model",
        analysis_window_days=7,
    )


def _seed_raw_item(conn, item_id, title, body, posted_at="2026-05-20T10:00:00+00:00"):
    run_id = insert_collection_run(conn, "reddit", "completed")
    return upsert_raw_item(
        conn, run_id, "reddit", item_id, title, body,
        f"https://reddit.com/r/x/{item_id}", 100, 5, {}, posted_at=posted_at,
    )


def _all_agents(client) -> dict:
    """Build an overrides dict that routes every agent to the same FakeLLMClient."""
    return {f"a{i}": client for i in range(1, 9)}


# ---------- aggregate.py ----------


def test_aggregate_single_item_returns_unchanged():
    extractions = [{"a2": {
        "who": "user", "what": "the problem", "keywords": ["a", "b"],
        "emotional_intensity": 6, "frequency": "weekly",
        "willingness_to_pay_signal": True,
        "pay_signal_evidence": "would pay $20",
        "current_workaround": "manual", "why_current_sucks": "too slow",
        "desired_outcome": "automation",
    }}]
    agg = aggregate_cluster_a2(extractions)
    assert agg.who == "user"
    assert agg.what == "the problem"
    assert agg.emotional_intensity == 6


def test_aggregate_picks_max_intensity_and_unions_keywords():
    extractions = [
        {"a2": {"who": "u1", "what": "short", "keywords": ["aws", "cost"],
                "emotional_intensity": 4, "willingness_to_pay_signal": False}},
        {"a2": {"who": "specific sysadmin at a small SaaS company",
                "what": "a much more detailed problem statement here",
                "keywords": ["aws", "billing", "report"],
                "emotional_intensity": 8, "willingness_to_pay_signal": True,
                "pay_signal_evidence": "I'd pay $50/mo"}},
    ]
    agg = aggregate_cluster_a2(extractions)
    assert agg.who.startswith("specific sysadmin")
    assert "specific sysadmin" in agg.who  # longest by tokens wins
    assert agg.what.startswith("a much more")
    assert agg.emotional_intensity == 8
    assert "aws" in agg.keywords
    assert "billing" in agg.keywords or "report" in agg.keywords
    assert agg.willingness_to_pay_signal is True
    assert agg.pay_signal_evidence == "I'd pay $50/mo"


# ---------- BudgetTracker ----------


def test_budget_tracker_raises_when_exceeded():
    b = BudgetTracker(max_calls=2)
    b("a1")
    b("a2")
    with pytest.raises(BudgetExceeded):
        b("a3")


def test_budget_tracker_none_is_unlimited():
    b = BudgetTracker(None)
    for i in range(1000):
        b("a1")
    assert b.count == 1000


def test_budget_formula():
    # 10 items, 3 clusters → 2*10 + 10*3 + 50 = 100
    assert BudgetTracker.for_run(10, 3) == 100


# ---------- run_pipeline (dry-run mode) ----------


def test_pipeline_skips_when_no_items(db, settings, fake_llm):
    client = fake_llm({})
    summary = run_pipeline(db, settings, overrides=_all_agents(client))
    assert summary["items"] == 0
    assert summary["persisted"] == 0
    assert client.calls == []


def test_pipeline_a1_rejects_all_items_no_clusters(
    db, settings, fake_llm, canned_a1_reject,
):
    _seed_raw_item(db, "x", "test title", "test body")
    client = fake_llm({"a1": canned_a1_reject})

    summary = run_pipeline(db, settings, overrides=_all_agents(client))
    assert summary["items"] == 1
    assert summary["passed"] == 0
    assert summary["clusters"] == 0  # no passed items → no clusters
    assert summary["persisted"] == 0
    # No niche_analyses or niche_candidates created
    assert db.execute("SELECT COUNT(*) FROM niche_analyses").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM niche_candidates").fetchone()[0] == 0
    # Extraction row exists (so we don't reprocess this rejected item)
    assert db.execute("SELECT COUNT(*) FROM item_pain_extractions").fetchone()[0] == 1
    assert db.execute(
        "SELECT a1_is_valid FROM item_pain_extractions"
    ).fetchone()[0] == 0


def test_pipeline_full_go_path_persists_niche_and_analysis(
    db, settings, fake_llm,
    canned_a1_pass, canned_a2, canned_a3, canned_a4, canned_a5,
    canned_a6_go, canned_a7, canned_a8,
):
    _seed_raw_item(db, "x", "AWS cost reporting", "I copy AWS costs every month")
    client = fake_llm({
        "a1": canned_a1_pass, "a2": canned_a2, "a3": canned_a3,
        "a4": canned_a4, "a5": canned_a5, "a6": canned_a6_go,
        "a7": canned_a7, "a8": canned_a8,
    })

    summary = run_pipeline(db, settings, overrides=_all_agents(client))
    assert summary["items"] == 1
    assert summary["passed"] == 1
    assert summary["clusters"] == 1
    assert summary["persisted"] == 1

    # One niche_candidates row
    row = db.execute(
        "SELECT keyword, llm_score, build_complexity, monetization, verdict, latest_analysis_id "
        "FROM niche_candidates"
    ).fetchone()
    assert row is not None
    keyword, llm_score, build_complexity, monetization, verdict, latest_id = row
    assert keyword == "costscribe"  # slug of A7.product_name
    assert llm_score > 0  # weighted_score >= 0
    assert build_complexity in (1, 2, 3)  # feasibility=8 → low complexity
    assert "subscription" in monetization
    assert verdict == "GO"
    assert latest_id is not None

    # One niche_analyses row, full payload
    arow = db.execute(
        "SELECT verdict, opportunity_score, tier, feasibility_score "
        "FROM niche_analyses"
    ).fetchone()
    assert arow == ("GO", 47, "warm", 8)


def test_pipeline_nogo_skips_a7_still_persists(
    db, settings, fake_llm,
    canned_a1_pass, canned_a2, canned_a3, canned_a4, canned_a5,
    canned_a6_nogo, canned_a8,
):
    _seed_raw_item(db, "x", "title", "body")
    client = fake_llm({
        "a1": canned_a1_pass, "a2": canned_a2, "a3": canned_a3,
        "a4": canned_a4, "a5": canned_a5,
        "a6": canned_a6_nogo,
        "a8": canned_a8,
    })
    summary = run_pipeline(db, settings, overrides=_all_agents(client))
    assert summary["persisted"] == 1
    row = db.execute(
        "SELECT verdict, a7_result FROM niche_analyses"
    ).fetchone()
    assert row[0] == "NO-GO"
    assert row[1] is None  # A7 must not have produced output


def test_pipeline_idempotent_on_rerun(
    db, settings, fake_llm,
    canned_a1_pass, canned_a2, canned_a3, canned_a4, canned_a5,
    canned_a6_go, canned_a7, canned_a8,
):
    _seed_raw_item(db, "x", "title", "body")
    canned = {
        "a1": canned_a1_pass, "a2": canned_a2, "a3": canned_a3,
        "a4": canned_a4, "a5": canned_a5, "a6": canned_a6_go,
        "a7": canned_a7, "a8": canned_a8,
    }

    # First run
    client1 = fake_llm(canned)
    s1 = run_pipeline(db, settings, overrides=_all_agents(client1))
    assert s1["items"] == 1 and s1["persisted"] == 1

    # Second run — same DB, same items. No new items needing A1.
    client2 = fake_llm(canned)
    s2 = run_pipeline(db, settings, overrides=_all_agents(client2))
    assert s2["items"] == 0
    # No new LLM calls on the second run
    assert client2.calls == []

    # Still exactly one extraction + one niche.
    assert db.execute("SELECT COUNT(*) FROM item_pain_extractions").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM niche_candidates").fetchone()[0] == 1


def test_pipeline_budget_abort(db, settings, fake_llm, canned_a1_pass, canned_a2):
    _seed_raw_item(db, "x", "title", "body")
    client = fake_llm({"a1": canned_a1_pass, "a2": canned_a2})
    summary = run_pipeline(
        db, settings,
        overrides=_all_agents(client),
        max_calls=1,  # blow up immediately after A1
    )
    assert summary.get("aborted") == "budget_exceeded"
    assert summary["budget_used"] >= 1


# ---------- run_pipeline_on_signal (--test path) ----------


def test_run_pipeline_on_signal_runs_full_go_chain(
    db, settings, fake_llm,
    canned_a1_pass, canned_a2, canned_a3, canned_a4, canned_a5,
    canned_a6_go, canned_a7, canned_a8,
):
    from niche_radar.agents.test_signal import TEST_SIGNAL
    client = fake_llm({
        "a1": canned_a1_pass, "a2": canned_a2, "a3": canned_a3,
        "a4": canned_a4, "a5": canned_a5, "a6": canned_a6_go,
        "a7": canned_a7, "a8": canned_a8,
    })
    result = run_pipeline_on_signal(
        db, settings, TEST_SIGNAL, overrides=_all_agents(client),
    )
    assert result.a1 is not None and result.a1.is_valid_signal is True
    assert result.a2 is not None
    assert result.a3 is not None
    assert result.a4 is not None and result.a4.total_score == 47
    assert result.a5 is not None
    assert result.a6 is not None and result.a6.verdict == "GO"
    assert result.a7 is not None
    assert result.a8 is not None
    # No DB writes happened (this is in-memory)
    assert db.execute("SELECT COUNT(*) FROM niche_candidates").fetchone()[0] == 0


def test_run_pipeline_on_signal_short_circuits_on_a1_reject(
    db, settings, fake_llm, canned_a1_reject,
):
    from niche_radar.agents.test_signal import TEST_SIGNAL
    client = fake_llm({"a1": canned_a1_reject})
    result = run_pipeline_on_signal(
        db, settings, TEST_SIGNAL, overrides=_all_agents(client),
    )
    assert result.short_circuited_at == "a1"
    assert result.a2 is None
    assert result.a3 is None

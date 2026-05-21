"""Tests for the v3 pipeline storage layer: schema migration + new repository helpers."""

from __future__ import annotations

import uuid

import pytest

from niche_radar.storage.database import get_db
from niche_radar.storage.repository import (
    attach_latest_analysis,
    get_items_needing_a1,
    get_unclustered_passed_extractions,
    insert_niche_analysis,
    lookup_niche_by_alias_overlap,
    update_extraction_cluster,
    upsert_item_extraction,
    upsert_niche_candidate,
    upsert_raw_item,
    insert_collection_run,
)


def test_migration_creates_new_tables(tmp_path):
    conn = get_db(f"sqlite:///{tmp_path/'test.db'}")
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "item_pain_extractions" in tables
    assert "niche_analyses" in tables


def test_migration_adds_columns_to_niche_candidates(tmp_path):
    conn = get_db(f"sqlite:///{tmp_path/'test.db'}")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(niche_candidates)").fetchall()}
    assert "verdict" in cols
    assert "latest_analysis_id" in cols


def test_migration_idempotent(tmp_path):
    db_path = tmp_path / "test.db"
    c1 = get_db(f"sqlite:///{db_path}")
    c1.close()
    # Reopen — must not raise.
    c2 = get_db(f"sqlite:///{db_path}")
    tables = {r[0] for r in c2.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    assert "item_pain_extractions" in tables
    assert "niche_analyses" in tables


def _seed_raw_item(conn, item_id, posted_at="2026-05-20T10:00:00+00:00"):
    run_id = insert_collection_run(conn, "reddit", "completed")
    return upsert_raw_item(
        conn, run_id, "reddit", item_id, f"Title {item_id}", "body", "https://x", 100, 5,
        {}, posted_at=posted_at,
    )


def test_get_items_needing_a1_excludes_already_extracted(db):
    a = _seed_raw_item(db, "a")
    b = _seed_raw_item(db, "b")
    # A has an extraction row (was processed), B does not.
    upsert_item_extraction(
        db, raw_item_id=a, pipeline_run="run-1",
        a1_is_valid=True, a1_confidence=0.9, a1_signal_type="pain_point",
        a1_result={"is_valid_signal": True}, a2_result={"who": "user"},
    )
    needing = get_items_needing_a1(db, max_age_days=None)
    ids = {r["id"] for r in needing}
    assert b in ids
    assert a not in ids


def test_get_items_needing_a1_respects_freshness_window(db):
    fresh = _seed_raw_item(db, "fresh", posted_at="2026-05-20T10:00:00+00:00")
    stale = _seed_raw_item(db, "stale", posted_at="2025-01-01T00:00:00+00:00")
    # max_age_days=7 from a 2026-05-21 today → stale should be filtered out
    needing = get_items_needing_a1(db, max_age_days=7)
    ids = {r["id"] for r in needing}
    # The "stale" row must not appear; "fresh" may or may not appear depending on
    # how recent the test runs — but stale definitely is excluded.
    assert stale not in ids


def test_upsert_item_extraction_handles_a1_reject(db):
    a = _seed_raw_item(db, "a")
    upsert_item_extraction(
        db, raw_item_id=a, pipeline_run="run-1",
        a1_is_valid=False, a1_confidence=0.95, a1_signal_type="noise",
        a1_result={"is_valid_signal": False, "rejection_reason": "vague"},
        a2_result=None,
    )
    rows = db.execute(
        "SELECT a1_is_valid, a2_result FROM item_pain_extractions WHERE raw_item_id=?",
        (a,),
    ).fetchone()
    assert rows[0] == 0
    assert rows[1] is None


def test_unclustered_passed_extractions_filters_correctly(db):
    a = _seed_raw_item(db, "a")
    b = _seed_raw_item(db, "b")
    c = _seed_raw_item(db, "c")
    # a: passed, unclustered
    upsert_item_extraction(
        db, raw_item_id=a, pipeline_run="run-1",
        a1_is_valid=True, a1_confidence=0.9, a1_signal_type="pain_point",
        a1_result={"is_valid_signal": True}, a2_result={"who": "u1"},
    )
    # b: passed but in a different run
    upsert_item_extraction(
        db, raw_item_id=b, pipeline_run="run-2",
        a1_is_valid=True, a1_confidence=0.9, a1_signal_type="pain_point",
        a1_result={"is_valid_signal": True}, a2_result={"who": "u2"},
    )
    # c: same run but A1-rejected
    upsert_item_extraction(
        db, raw_item_id=c, pipeline_run="run-1",
        a1_is_valid=False, a1_confidence=0.9, a1_signal_type="noise",
        a1_result={"is_valid_signal": False}, a2_result=None,
    )
    items = get_unclustered_passed_extractions(db, "run-1")
    ids = {i["raw_item_id"] for i in items}
    assert ids == {a}


def test_update_extraction_cluster_assigns_then_excludes(db):
    a = _seed_raw_item(db, "a")
    b = _seed_raw_item(db, "b")
    for rid in (a, b):
        upsert_item_extraction(
            db, raw_item_id=rid, pipeline_run="run-1",
            a1_is_valid=True, a1_confidence=0.9, a1_signal_type="pain_point",
            a1_result={}, a2_result={"who": "x"},
        )
    update_extraction_cluster(db, [a, b], "cluster-1")
    leftover = get_unclustered_passed_extractions(db, "run-1")
    assert leftover == []


def test_insert_niche_analysis_persists_full_payload(db):
    niche_id = upsert_niche_candidate(
        db, "aws cost report", ["aws", "cost"], 75.0, "demand evidence",
        tool_concept="A tool that summarizes AWS costs",
        target_audience="sysadmins", build_complexity=2,
        monetization="subscription: $29/mo team",
        pain_points=[],
    )
    analysis_id = insert_niche_analysis(
        db, niche_id=niche_id, pipeline_run="run-1", cluster_id="cluster-1",
        verdict="GO", confidence=0.8,
        opportunity_score=47, weighted_score=68.5, tier="warm", feasibility_score=8,
        a2_aggregate={"who": "sysadmins"},
        a3_result={"market_leader": "CloudHealth"},
        a4_result={"total_score": 47},
        a5_result={"feasibility_score": 8},
        a6_result={"verdict": "GO"},
        a7_result={"product_name": "CostScribe"},
        a8_result={"title": "AWS Cost Report Tool"},
        failed_agents=[],
    )
    row = db.execute(
        "SELECT verdict, opportunity_score, weighted_score, tier, a7_result "
        "FROM niche_analyses WHERE id=?", (analysis_id,)
    ).fetchone()
    assert row[0] == "GO"
    assert row[1] == 47
    assert row[2] == 68.5
    assert row[3] == "warm"
    assert "CostScribe" in row[4]


def test_attach_latest_analysis_updates_niche_columns(db):
    niche_id = upsert_niche_candidate(
        db, "n", [], 50.0, "x", tool_concept="t", target_audience="a",
        build_complexity=3, monetization="m", pain_points=[],
    )
    fake_aid = str(uuid.uuid4())
    attach_latest_analysis(db, niche_id, fake_aid, verdict="PIVOT")
    row = db.execute(
        "SELECT verdict, latest_analysis_id FROM niche_candidates WHERE id=?",
        (niche_id,),
    ).fetchone()
    assert row[0] == "PIVOT"
    assert row[1] == fake_aid


def test_lookup_by_alias_finds_existing_niche_by_keyword(db):
    upsert_niche_candidate(
        db, "aws cost report", ["aws", "cost"], 70.0, "r",
        tool_concept="t", target_audience="a", build_complexity=2,
        monetization="m", pain_points=[],
    )
    found = lookup_niche_by_alias_overlap(db, ["cloud spending tool", "AWS cost report"])
    assert found == "aws cost report"


def test_lookup_by_alias_finds_existing_niche_by_alias_match(db):
    upsert_niche_candidate(
        db, "spending report", ["aws", "cost"], 70.0, "r",
        tool_concept="t", target_audience="a", build_complexity=2,
        monetization="m", pain_points=[],
    )
    found = lookup_niche_by_alias_overlap(db, ["cost"])
    assert found == "spending report"


def test_lookup_by_alias_returns_none_when_no_match(db):
    upsert_niche_candidate(
        db, "totally unrelated", ["foo", "bar"], 70.0, "r",
        tool_concept="t", target_audience="a", build_complexity=2,
        monetization="m", pain_points=[],
    )
    assert lookup_niche_by_alias_overlap(db, ["pizza", "delivery"]) is None


def test_lookup_by_alias_empty_input_returns_none(db):
    assert lookup_niche_by_alias_overlap(db, []) is None
    assert lookup_niche_by_alias_overlap(db, ["", "  "]) is None

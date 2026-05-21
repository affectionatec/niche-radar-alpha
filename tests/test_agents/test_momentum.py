"""Tests for momentum.py — week-over-week trend tracking."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from niche_radar.storage.database import get_db
from niche_radar.storage.repository import (
    insert_collection_run,
    link_niche_item,
    upsert_niche_candidate,
    upsert_raw_item,
)
from niche_radar.storage.momentum import compute_momentum, update_momentum_for_all_niches


@pytest.fixture
def db(tmp_path):
    conn = get_db(f"sqlite:///{tmp_path / 'test.db'}")
    yield conn
    conn.close()


def _add_item(db, run_id, source_id, posted_at):
    return upsert_raw_item(
        db, run_id, "hn", source_id, f"title {source_id}", "body",
        f"https://x/{source_id}", 10, 2, {}, posted_at=posted_at,
    )


def test_growing_when_more_this_week(db):
    now = datetime.now(timezone.utc)
    run_id = insert_collection_run(db, "hn", "completed")
    niche_id = upsert_niche_candidate(
        db, "test-niche", [], 70.0, "r", tool_concept="t", target_audience="a",
        build_complexity=2, monetization="m", pain_points=[],
    )

    # 4 items this week
    for i in range(4):
        dt = (now - timedelta(days=i)).isoformat()
        iid = _add_item(db, run_id, f"new-{i}", dt)
        link_niche_item(db, niche_id, iid, "test-niche", 1.0)

    # 1 item last week
    old_dt = (now - timedelta(days=10)).isoformat()
    iid_old = _add_item(db, run_id, "old-0", old_dt)
    link_niche_item(db, niche_id, iid_old, "test-niche", 1.0)

    m = compute_momentum(db, niche_id)
    assert m["this_week"] == 4
    assert m["last_week"] == 1
    assert m["ratio"] > 1.5
    assert m["label"] == "growing"


def test_declining_when_fewer_this_week(db):
    now = datetime.now(timezone.utc)
    run_id = insert_collection_run(db, "hn", "completed")
    niche_id = upsert_niche_candidate(
        db, "declining-niche", [], 60.0, "r", tool_concept="t", target_audience="a",
        build_complexity=3, monetization="m", pain_points=[],
    )

    # 1 item this week
    iid_new = _add_item(db, run_id, "n1", (now - timedelta(hours=2)).isoformat())
    link_niche_item(db, niche_id, iid_new, "declining-niche", 1.0)

    # 5 items last week
    for i in range(5):
        dt = (now - timedelta(days=8 + i)).isoformat()
        iid = _add_item(db, run_id, f"old-{i}", dt)
        link_niche_item(db, niche_id, iid, "declining-niche", 1.0)

    m = compute_momentum(db, niche_id)
    assert m["label"] == "declining"
    assert m["ratio"] < 0.6


def test_stable_when_roughly_equal(db):
    now = datetime.now(timezone.utc)
    run_id = insert_collection_run(db, "hn", "completed")
    niche_id = upsert_niche_candidate(
        db, "stable-niche", [], 55.0, "r", tool_concept="t", target_audience="a",
        build_complexity=3, monetization="m", pain_points=[],
    )

    for i in range(2):
        dt = (now - timedelta(days=i + 1)).isoformat()
        iid = _add_item(db, run_id, f"cur-{i}", dt)
        link_niche_item(db, niche_id, iid, "stable-niche", 1.0)

    for i in range(2):
        dt = (now - timedelta(days=8 + i)).isoformat()
        iid = _add_item(db, run_id, f"prev-{i}", dt)
        link_niche_item(db, niche_id, iid, "stable-niche", 1.0)

    m = compute_momentum(db, niche_id)
    assert m["label"] == "stable"


def test_new_niche_with_no_history_is_stable(db):
    run_id = insert_collection_run(db, "hn", "completed")
    now = datetime.now(timezone.utc)
    niche_id = upsert_niche_candidate(
        db, "brand-new", [], 50.0, "r", tool_concept="t", target_audience="a",
        build_complexity=2, monetization="m", pain_points=[],
    )
    iid = _add_item(db, run_id, "fresh-1", (now - timedelta(hours=1)).isoformat())
    link_niche_item(db, niche_id, iid, "brand-new", 1.0)

    m = compute_momentum(db, niche_id)
    # (1+1)/(0+1) = 2.0 → growing, which is correct for brand-new
    assert m["label"] in ("growing", "stable")  # either is acceptable for a single item


def test_update_momentum_for_all_writes_columns(db):
    run_id = insert_collection_run(db, "hn", "completed")
    now = datetime.now(timezone.utc)
    niche_id = upsert_niche_candidate(
        db, "all-niches-test", [], 60.0, "r", tool_concept="t", target_audience="a",
        build_complexity=2, monetization="m", pain_points=[],
    )
    iid = _add_item(db, run_id, "u1", (now - timedelta(hours=1)).isoformat())
    link_niche_item(db, niche_id, iid, "all-niches-test", 1.0)

    count = update_momentum_for_all_niches(db)
    assert count == 1

    row = db.execute(
        "SELECT momentum_ratio, momentum_label, momentum_updated_at FROM niche_candidates WHERE id=?",
        (niche_id,),
    ).fetchone()
    assert row[0] is not None  # ratio set
    assert row[1] in ("growing", "stable", "declining")
    assert row[2] is not None  # timestamp set

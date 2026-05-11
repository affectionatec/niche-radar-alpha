"""Tests for storage repository functions."""

from niche_radar.storage.repository import (
    insert_collection_run,
    complete_collection_run,
    upsert_raw_item,
    get_unprocessed_items,
    upsert_niche_candidate,
    link_niche_item,
    get_active_niches,
    insert_niche_score,
    get_latest_scores,
)


def test_collection_run_lifecycle(db):
    run_id = insert_collection_run(db, "reddit")
    row = db.execute("SELECT status FROM collection_runs WHERE id=?", (run_id,)).fetchone()
    assert row[0] == "running"

    complete_collection_run(db, run_id, "completed", 42)
    row = db.execute("SELECT status, items_collected FROM collection_runs WHERE id=?", (run_id,)).fetchone()
    assert row[0] == "completed"
    assert row[1] == 42


def test_upsert_raw_item_insert_and_dedup(db):
    run_id = insert_collection_run(db, "reddit")

    item_id = upsert_raw_item(
        db, run_id, "reddit", "post_1", "Test Title", "Body text", "https://example.com", 100, 10, {"key": "val"}
    )
    assert item_id

    # Same source+source_id should update, not duplicate
    item_id2 = upsert_raw_item(
        db, run_id, "reddit", "post_1", "Updated Title", "New body", "https://example.com", 200, 20, None
    )
    count = db.execute("SELECT COUNT(*) FROM raw_items WHERE source='reddit' AND source_id='post_1'").fetchone()[0]
    assert count == 1


def test_get_unprocessed_items(db, sample_raw_items):
    run_id = insert_collection_run(db, "test")
    for item in sample_raw_items:
        upsert_raw_item(
            db, run_id, item["source"], item["source_id"],
            item["title"], item["body"], item["url"],
            item["score"], item["comment_count"], item["metadata"],
        )

    items = get_unprocessed_items(db)
    assert len(items) == 3


def test_niche_candidate_lifecycle(db):
    upsert_niche_candidate(db, "niche-1", "self-hosted analytics", ["analytics", "selfhosted"], None)
    niches = get_active_niches(db)
    assert len(niches) == 1
    assert niches[0]["keyword"] == "self-hosted analytics"


def test_niche_score(db):
    upsert_niche_candidate(db, "niche-1", "self-hosted analytics", [], None)
    score_id = insert_niche_score(db, "niche-1", 75.0, 82.0, 68.0, 55.0, 72.5)
    assert score_id

    scores = get_latest_scores(db)
    assert len(scores) == 1
    assert scores[0]["composite_score"] == 72.5

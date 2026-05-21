"""Tests for storage repository functions."""

from niche_radar.storage.repository import (
    insert_collection_run,
    complete_collection_run,
    upsert_raw_item,
    get_unprocessed_items,
    upsert_niche_candidate,
    link_niche_item,
    get_active_niches_with_scores,
    get_niche_by_id,
    get_app_setting,
    set_app_setting,
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
    upsert_raw_item(
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
    niche_id = upsert_niche_candidate(
        db, "self-hosted analytics", ["analytics", "selfhosted"], 75.0, "Strong demand signal.",
        tool_concept="An AI-assisted self-hosted analytics dashboard for indie SaaS.",
        target_audience="indie SaaS founders",
        build_complexity=2,
        monetization="ProductHunt launch + AdSense on docs site",
        pain_points=[{"pain": "GA4 is too complex", "quote": "I just want a count", "item_id": "x1"}],
    )
    niches = get_active_niches_with_scores(db)
    assert len(niches) == 1
    assert niches[0]["keyword"] == "self-hosted analytics"
    assert niches[0]["llm_score"] == 75.0
    assert niches[0]["tool_concept"].startswith("An AI-assisted")
    assert niches[0]["build_complexity"] == 2
    assert niches[0]["target_audience"] == "indie SaaS founders"
    assert len(niches[0]["pain_points"]) == 1
    assert niches[0]["pain_points"][0]["quote"] == "I just want a count"

    niche = get_niche_by_id(db, niche_id)
    assert niche is not None
    assert niche["keyword"] == "self-hosted analytics"
    assert niche["monetization"].startswith("ProductHunt")


def test_niche_dedup_by_keyword(db):
    id1 = upsert_niche_candidate(db, "ai code review", [], 70.0, "First analysis.")
    id2 = upsert_niche_candidate(db, "ai code review", [], 85.0, "Second analysis.")
    assert id1 == id2  # same niche, updated
    niches = get_active_niches_with_scores(db)
    assert len(niches) == 1
    assert niches[0]["llm_score"] == 85.0
    assert niches[0]["occurrence_count"] == 2


def test_app_settings(db):
    assert get_app_setting(db, "llm_api_key") is None
    set_app_setting(db, "llm_api_key", "sk-test")
    assert get_app_setting(db, "llm_api_key") == "sk-test"

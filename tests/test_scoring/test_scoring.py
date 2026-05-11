import json

from niche_radar.scoring import run_scoring
from niche_radar.scoring.composite import compute_composite
from niche_radar.storage.database import get_db


class Settings:
    min_occurrence_threshold = 2


def test_run_scoring_persists_scores(tmp_path):
    db = get_db(f"sqlite:///{tmp_path / 'radar.db'}")
    db.execute("INSERT INTO collection_runs (id, source, status) VALUES ('run-1', 'reddit', 'completed')")
    db.execute("INSERT INTO raw_items (id, collection_run, source, source_id, title, body, score, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("r1", "run-1", "reddit", "1", "Need help", "I wish there was a better tool", 90, json.dumps({})))
    db.execute("INSERT INTO raw_items (id, collection_run, source, source_id, title, body, score, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("r2", "run-1", "youtube", "2", "Video", "Review", 20000, json.dumps({})))
    db.execute("INSERT INTO raw_items (id, collection_run, source, source_id, title, body, score, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("r3", "run-1", "github", "3", "Repo", "Stars", 500, json.dumps({})))
    db.execute("INSERT INTO niche_candidates (id, keyword, aliases, first_seen, last_seen, occurrence_count) VALUES ('n1', 'ai testing', '[]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 2)")
    db.execute("INSERT INTO niche_item_links (niche_id, raw_item_id, keyphrase, relevance_score) VALUES ('n1', 'r1', 'ai testing', 0.9)")
    db.execute("INSERT INTO niche_item_links (niche_id, raw_item_id, keyphrase, relevance_score) VALUES ('n1', 'r2', 'ai testing', 0.8)")
    db.execute("INSERT INTO niche_item_links (niche_id, raw_item_id, keyphrase, relevance_score) VALUES ('n1', 'r3', 'ai testing', 0.7)")
    db.execute("INSERT INTO trend_snapshots (id, niche_id, source, data) VALUES ('t1', 'n1', 'google_trends', ?)", (json.dumps({"interest": [10, 20, 30, 40]}),))
    db.commit()

    assert run_scoring(db, Settings(), dry_run=False) == 1
    row = db.execute("SELECT engagement, search_trend, content_gap, market_traction, composite_score FROM niche_scores WHERE niche_id='n1'").fetchone()
    assert row is not None
    assert 0 <= row[4] <= 100


def test_compute_composite_weights_dimensions():
    assert compute_composite(80, 70, 60, 50) == 66.0

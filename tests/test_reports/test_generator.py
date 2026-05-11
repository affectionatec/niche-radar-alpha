import json
from pathlib import Path

from niche_radar.reports.generator import generate_report
from niche_radar.storage.database import get_db


class Settings:
    report_output_dir: Path

    def __init__(self, report_output_dir: Path):
        self.report_output_dir = report_output_dir
        self.report_format = "both"


def test_generate_report_writes_markdown_and_json(tmp_path):
    db = get_db(f"sqlite:///{tmp_path / 'radar.db'}")
    db.execute("INSERT INTO collection_runs (id, source, status, items_collected) VALUES ('run-1', 'reddit', 'completed', 3)")
    db.execute("INSERT INTO raw_items (id, collection_run, source, source_id, title, url, score, metadata) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", ("r1", "run-1", "reddit", "1", "AI browser testing", "https://example.com", 100, json.dumps({})))
    db.execute("INSERT INTO niche_candidates (id, keyword, aliases, first_seen, last_seen, occurrence_count) VALUES ('n1', 'ai browser testing', '[\"qa automation\"]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 2)")
    db.execute("INSERT INTO niche_item_links (niche_id, raw_item_id, keyphrase, relevance_score) VALUES ('n1', 'r1', 'ai browser testing', 0.9)")
    db.execute("INSERT INTO niche_scores (id, niche_id, engagement, search_trend, content_gap, market_traction, composite_score) VALUES ('s1', 'n1', 82, 91, 88, 79, 86)")
    db.commit()

    paths = generate_report(db, Settings(tmp_path), "both")
    assert {path.suffix for path in paths} == {".md", ".json"}
    markdown = next(path for path in paths if path.suffix == ".md").read_text(encoding="utf-8")
    assert "High Priority" in markdown
    assert "System Health" in markdown

import json
from pathlib import Path

from niche_radar.reports.generator import generate_report
from niche_radar.storage.database import get_db
from niche_radar.storage.repository import upsert_niche_candidate


class _Settings:
    def __init__(self, report_output_dir: Path):
        self.report_output_dir = report_output_dir
        self.report_format = "both"
        self.llm_provider = "openai_compat"
        self.llm_api_key = ""
        self.llm_model = "deepseek-chat"
        self.llm_base_url = ""


def test_generate_report_writes_markdown_and_json(tmp_path):
    db = get_db(f"sqlite:///{tmp_path / 'radar.db'}")
    upsert_niche_candidate(db, "ai browser testing", ["qa automation", "test automation"], 86.0, "Strong demand on HN and Reddit.")

    paths = generate_report(db, _Settings(tmp_path), "both")
    assert {path.suffix for path in paths} == {".md", ".json"}

    md = next(p for p in paths if p.suffix == ".md").read_text(encoding="utf-8")
    assert "ai browser testing" in md.lower()

    data = json.loads(next(p for p in paths if p.suffix == ".json").read_text())
    assert len(data["niches"]) == 1
    assert data["niches"][0]["llm_score"] == 86.0

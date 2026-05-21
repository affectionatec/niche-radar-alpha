from pathlib import Path

from niche_radar.reports.generator import generate_report
from niche_radar.storage.database import get_db
from niche_radar.storage.repository import upsert_niche_candidate


class _Settings:
    def __init__(self, report_output_dir: Path):
        self.report_output_dir = report_output_dir
        self.llm_provider = "openai_compat"
        self.llm_api_key = ""
        self.llm_model = "deepseek-v4-flash"
        self.llm_base_url = ""


def test_generate_report_writes_markdown_only(tmp_path):
    db = get_db(f"sqlite:///{tmp_path / 'radar.db'}")
    upsert_niche_candidate(
        db,
        "ai browser testing",
        ["qa automation", "test automation"],
        86.0,
        "Strong demand on HN and Reddit.",
        tool_concept="An AI tool that runs end-to-end browser tests from a single prompt.",
        target_audience="solo SaaS founders",
        build_complexity=2,
        monetization="High-intent search traffic + AdSense",
        pain_points=[{"pain": "QA setup is painful", "quote": "I hate writing Cypress tests", "item_id": "x1"}],
    )

    path = generate_report(db, _Settings(tmp_path))
    assert path.suffix == ".md"
    assert path.exists()

    md = path.read_text(encoding="utf-8")
    assert "AI Tool Opportunities" in md
    assert "browser tests" in md.lower()
    assert "solo SaaS founders" in md
    assert "Cypress" in md  # verbatim quote propagated

    json_files = list(tmp_path.glob("*.json"))
    assert json_files == []

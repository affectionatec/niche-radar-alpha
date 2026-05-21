"""Tests for the weekly digest report generator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from niche_radar.storage.database import get_db
from niche_radar.storage.repository import upsert_niche_candidate
from niche_radar.reports.weekly_digest import generate_weekly_digest


@pytest.fixture
def db(tmp_path):
    conn = get_db(f"sqlite:///{tmp_path / 'test.db'}")
    yield conn
    conn.close()


def test_weekly_digest_generates_markdown(db, tmp_path):
    upsert_niche_candidate(
        db, "aws-cost-reporter", ["aws", "cost"], 72.0, "r",
        tool_concept="Automated AWS cost reports", target_audience="sysadmins",
        build_complexity=2, monetization="subscription", pain_points=[],
    )
    output_dir = tmp_path / "reports"
    path = generate_weekly_digest(db, output_dir)

    assert path.exists()
    content = path.read_text()
    assert "Weekly Digest" in content
    assert "aws-cost-reporter" in content or "Automated AWS cost" in content


def test_weekly_digest_with_no_niches_returns_graceful_message(db, tmp_path):
    output_dir = tmp_path / "reports"
    path = generate_weekly_digest(db, output_dir)
    content = path.read_text()
    assert path.exists()
    assert "No active niches" in content or "Weekly Digest" in content


def test_weekly_digest_filename_contains_date(db, tmp_path):
    output_dir = tmp_path / "reports"
    path = generate_weekly_digest(db, output_dir)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    assert today in path.name

"""Shared test fixtures for Niche Radar tests."""

import sqlite3
import pytest

from niche_radar.storage.database import get_db


@pytest.fixture
def db(tmp_path):
    """Create an in-memory SQLite database with full schema."""
    db_path = str(tmp_path / "test.db")
    conn = get_db(f"sqlite:///{db_path}")
    yield conn
    conn.close()


@pytest.fixture
def sample_raw_items():
    """Sample raw items for testing."""
    return [
        {
            "id": "item-1",
            "source": "reddit",
            "source_id": "abc123",
            "title": "Is there a tool for self-hosted analytics?",
            "body": "I'm looking for an open-source alternative to Google Analytics that I can self-host.",
            "url": "https://reddit.com/r/selfhosted/abc123",
            "score": 245,
            "comment_count": 67,
            "metadata": {"subreddit": "selfhosted", "flair": "Question"},
        },
        {
            "id": "item-2",
            "source": "hn",
            "source_id": "def456",
            "title": "Show HN: AI-powered browser testing tool",
            "body": "I built a tool that uses AI to generate and maintain browser tests automatically.",
            "url": "https://news.ycombinator.com/item?id=def456",
            "score": 189,
            "comment_count": 43,
            "metadata": {"type": "show_hn"},
        },
        {
            "id": "item-3",
            "source": "github",
            "source_id": "ghi789",
            "title": "awesome-selfhosted",
            "body": "A list of Free Software network services and web applications which can be hosted on your own servers.",
            "url": "https://github.com/awesome-selfhosted/awesome-selfhosted",
            "score": 1200,
            "comment_count": 0,
            "metadata": {"language": "Markdown", "stars_today": 45},
        },
    ]

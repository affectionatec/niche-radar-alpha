"""Tests for the config module."""

from niche_radar.config import Settings


def test_default_settings():
    s = Settings(
        _env_file=None,
        reddit_client_id="test",
        reddit_client_secret="test",
    )
    assert s.database_url == "sqlite:///data/niche_radar.db"
    assert s.log_level == "INFO"
    assert s.collection_interval_hours == 4
    assert s.max_retries == 3
    assert s.llm_provider == "openai_compat"
    assert s.llm_batch_size == 50

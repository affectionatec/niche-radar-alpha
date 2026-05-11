"""Tests for the config module."""

import os
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
    assert s.keybert_model == "all-MiniLM-L6-v2"
    assert s.cluster_distance_threshold == 0.35

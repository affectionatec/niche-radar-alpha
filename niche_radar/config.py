"""Configuration loaded from environment variables via pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "NicheRadar/0.1"

    # GitHub
    github_token: str = ""

    # YouTube
    youtube_api_key: str = ""

    # Database
    database_url: str = "sqlite:///data/niche_radar.db"

    # Scheduler
    collection_interval_hours: int = 4
    scoring_interval_hours: int = 6
    cleanup_hour_utc: int = 3

    # Retry
    max_retries: int = 3
    retry_backoff_base: int = 2

    # Retention (days)
    retention_raw_items: int = 90
    retention_archived_niches: int = 180
    retention_scores: int = 365
    retention_collection_runs: int = 30

    # Reports
    report_output_dir: Path = Path("./reports")
    report_format: str = "both"  # 'markdown' | 'json' | 'both'

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # 'json' | 'text'

    # Notifications
    slack_webhook_url: str = ""
    discord_webhook_url: str = ""

    # NLP
    keybert_model: str = "all-MiniLM-L6-v2"
    min_occurrence_threshold: int = 2
    cluster_distance_threshold: float = 0.35

    # LLM Pipeline
    anthropic_api_key: str = ""
    pipeline_model: str = "claude-sonnet-4-6"
    pipeline_max_tokens: int = 1000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

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
    analysis_interval_hours: int = 6
    cleanup_hour_utc: int = 3

    # Retry
    max_retries: int = 3
    retry_backoff_base: int = 2

    # Retention (days)
    retention_raw_items: int = 90
    retention_archived_niches: int = 180
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

    # LLM — defaults, overridable at runtime via frontend settings page
    llm_provider: str = "openai_compat"  # 'openai_compat' | 'anthropic'
    llm_api_key: str = ""
    llm_base_url: str = ""  # e.g. https://api.deepseek.com for DeepSeek
    llm_model: str = "deepseek-chat"
    llm_batch_size: int = 50  # raw items per LLM call

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

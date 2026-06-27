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

    # X / Twitter capture backends (any one enables X; see TwitterCollector)
    xai_api_key: str = ""
    xquik_api_key: str = ""
    # max item age for X items dropped at collection time (hours)
    freshness_twitter_hours: int = 48

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

    # V2EX (keyless China tech forum)
    v2ex_api_token: str = ""

    # Xueqiu (China finance social)
    xueqiu_cookie: str = ""

    # Bilibili (China video platform)
    bilibili_sessdata: str = ""

    # Exa semantic search (key-gated)
    exa_api_key: str = ""

    # ── Freshness rules ─────────────────────────────────────────────────────
    # max_item_age_hours per source — items posted before this window are DROPPED
    # at collection time and never enter the DB. Tunable from .env if needed.
    freshness_reddit_hours: int = 72       # 3 days — pain threads cool fast
    freshness_hn_hours: int = 72           # 3 days — story relevance drops
    freshness_github_hours: int = 168      # 7 days — repo trends are weekly
    freshness_google_trends_hours: int = 24  # 1 day — trending = today
    freshness_youtube_hours: int = 336     # 14 days — video discovery is slow
    freshness_v2ex_hours: int = 72         # 3 days — forum posts cool fast
    freshness_xueqiu_hours: int = 48       # 2 days — finance discussions move fast
    freshness_bilibili_hours: int = 336    # 14 days — video discovery is slow

    # Analysis-time freshness — only feed the LLM items posted within this window.
    # Niches whose last_seen falls outside this window are auto-archived.
    analysis_window_days: int = 7

    # Entity intelligence
    entity_extraction_sample_rate: float = 0.2

    # Reports
    report_output_dir: Path = Path("./reports")

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
    llm_model: str = "deepseek-v4-flash"
    llm_batch_size: int = 50  # raw items per LLM call

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the singleton settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

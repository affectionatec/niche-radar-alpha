"""Database connection and schema initialization."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import structlog

logger = structlog.get_logger()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS collection_runs (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'running',
    items_collected INTEGER DEFAULT 0,
    error_message   TEXT,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_collection_runs_source ON collection_runs(source);
CREATE INDEX IF NOT EXISTS idx_collection_runs_started ON collection_runs(started_at);

CREATE TABLE IF NOT EXISTS raw_items (
    id              TEXT PRIMARY KEY,
    collection_run  TEXT REFERENCES collection_runs(id),
    source          TEXT NOT NULL,
    source_id       TEXT,
    title           TEXT,
    body            TEXT,
    url             TEXT,
    score           INTEGER,
    comment_count   INTEGER,
    metadata        JSON,
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_raw_items_source ON raw_items(source);
CREATE INDEX IF NOT EXISTS idx_raw_items_source_id ON raw_items(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_items_collected ON raw_items(collected_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_items_dedup ON raw_items(source, source_id);

CREATE TABLE IF NOT EXISTS niche_candidates (
    id              TEXT PRIMARY KEY,
    keyword         TEXT NOT NULL,
    aliases         JSON,
    embedding       BLOB,
    status          TEXT DEFAULT 'active',
    first_seen      TIMESTAMP,
    last_seen       TIMESTAMP,
    occurrence_count INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_niche_candidates_keyword ON niche_candidates(keyword);
CREATE INDEX IF NOT EXISTS idx_niche_candidates_status ON niche_candidates(status);

CREATE TABLE IF NOT EXISTS niche_item_links (
    niche_id        TEXT REFERENCES niche_candidates(id),
    raw_item_id     TEXT REFERENCES raw_items(id),
    keyphrase       TEXT,
    relevance_score REAL,
    PRIMARY KEY (niche_id, raw_item_id)
);

CREATE TABLE IF NOT EXISTS niche_scores (
    id              TEXT PRIMARY KEY,
    niche_id        TEXT REFERENCES niche_candidates(id),
    engagement      REAL,
    search_trend    REAL,
    content_gap     REAL,
    market_traction REAL,
    composite_score REAL,
    scored_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_niche_scores_niche ON niche_scores(niche_id);
CREATE INDEX IF NOT EXISTS idx_niche_scores_composite ON niche_scores(composite_score);
CREATE INDEX IF NOT EXISTS idx_niche_scores_scored ON niche_scores(scored_at);

CREATE TABLE IF NOT EXISTS trend_snapshots (
    id              TEXT PRIMARY KEY,
    niche_id        TEXT REFERENCES niche_candidates(id),
    source          TEXT,
    data            JSON,
    snapshot_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_trend_snapshots_niche ON trend_snapshots(niche_id);

CREATE TABLE IF NOT EXISTS pipeline_results (
    id                TEXT PRIMARY KEY,
    raw_item_id       TEXT REFERENCES raw_items(id),
    source            TEXT,
    scraped_at        TIMESTAMP,
    verdict           TEXT,
    opportunity_score REAL,
    tier              TEXT,
    full_result       JSON,
    analyzed_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pipeline_verdict ON pipeline_results(verdict);
CREATE INDEX IF NOT EXISTS idx_pipeline_tier    ON pipeline_results(tier);
CREATE INDEX IF NOT EXISTS idx_pipeline_source  ON pipeline_results(source);
CREATE INDEX IF NOT EXISTS idx_pipeline_scraped ON pipeline_results(scraped_at);
"""


def get_db(database_url: str) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure schema exists."""
    if database_url.startswith("sqlite:///"):
        db_path = database_url[len("sqlite:///"):]
    else:
        db_path = database_url

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.commit()

    logger.debug("database_ready", path=str(path))
    return conn

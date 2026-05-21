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
    posted_at       TIMESTAMP,
    collected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- posted_at index created in _migrate() so it runs AFTER ALTER TABLE for legacy DBs
CREATE INDEX IF NOT EXISTS idx_raw_items_source ON raw_items(source);
CREATE INDEX IF NOT EXISTS idx_raw_items_source_id ON raw_items(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_items_collected ON raw_items(collected_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_items_dedup ON raw_items(source, source_id);

CREATE TABLE IF NOT EXISTS niche_candidates (
    id              TEXT PRIMARY KEY,
    keyword         TEXT NOT NULL,
    aliases         JSON,
    llm_score       REAL,
    llm_reasoning   TEXT,
    tool_concept    TEXT,
    target_audience TEXT,
    build_complexity INTEGER,
    monetization    TEXT,
    pain_points     JSON,
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

CREATE TABLE IF NOT EXISTS app_settings (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

-- 8-agent pipeline state — added in analyzer v3.
-- One row per raw_item processed in phase A (A1 filter + optional A2 extraction).
-- Items where A1 rejected are persisted with a1_is_valid=0 so we don't re-feed them.
CREATE TABLE IF NOT EXISTS item_pain_extractions (
    raw_item_id    TEXT PRIMARY KEY REFERENCES raw_items(id),
    pipeline_run   TEXT NOT NULL,
    a1_is_valid    INTEGER NOT NULL,
    a1_confidence  REAL,
    a1_signal_type TEXT,
    a1_result      TEXT,                    -- JSON
    a2_result      TEXT,                    -- JSON, NULL if A1 rejected
    cluster_id     TEXT,                    -- NULL until phase B assigns
    processed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error          TEXT
);
CREATE INDEX IF NOT EXISTS idx_extractions_run     ON item_pain_extractions(pipeline_run);
CREATE INDEX IF NOT EXISTS idx_extractions_cluster ON item_pain_extractions(cluster_id);
CREATE INDEX IF NOT EXISTS idx_extractions_valid   ON item_pain_extractions(a1_is_valid);

-- One row per (cluster, pipeline_run) — full A3..A8 outputs and the verdict summary.
CREATE TABLE IF NOT EXISTS niche_analyses (
    id                  TEXT PRIMARY KEY,
    niche_id            TEXT REFERENCES niche_candidates(id),
    pipeline_run        TEXT NOT NULL,
    cluster_id          TEXT NOT NULL,
    analyzed_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    verdict             TEXT,
    confidence          REAL,
    opportunity_score   INTEGER,            -- A4 raw total 0-70
    weighted_score      REAL,               -- normalized 0-100
    tier                TEXT,               -- hot | warm | cold
    feasibility_score   INTEGER,
    a2_aggregate        TEXT,
    a3_result           TEXT,
    a4_result           TEXT,
    a5_result           TEXT,
    a6_result           TEXT,
    a7_result           TEXT,               -- NULL when verdict != GO
    a8_result           TEXT,
    failed_agents       TEXT                -- JSON array of agent_ids
);
CREATE INDEX IF NOT EXISTS idx_analyses_niche   ON niche_analyses(niche_id);
CREATE INDEX IF NOT EXISTS idx_analyses_verdict ON niche_analyses(verdict);
CREATE INDEX IF NOT EXISTS idx_analyses_tier    ON niche_analyses(tier);
CREATE INDEX IF NOT EXISTS idx_analyses_run     ON niche_analyses(pipeline_run);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Add new columns and apply one-shot version-gated data migrations."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(niche_candidates)").fetchall()}
    if "llm_score" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN llm_score REAL")
    if "llm_reasoning" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN llm_reasoning TEXT")
    if "tool_concept" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN tool_concept TEXT")
    if "target_audience" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN target_audience TEXT")
    if "build_complexity" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN build_complexity INTEGER")
    if "monetization" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN monetization TEXT")
    if "pain_points" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN pain_points JSON")

    raw_cols = {r[1] for r in conn.execute("PRAGMA table_info(raw_items)").fetchall()}
    if "posted_at" not in raw_cols:
        conn.execute("ALTER TABLE raw_items ADD COLUMN posted_at TIMESTAMP")
        # Backfill: use collected_at as best-guess posted_at for legacy rows
        conn.execute("UPDATE raw_items SET posted_at = collected_at WHERE posted_at IS NULL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_raw_items_posted ON raw_items(posted_at)")

    # v3 (8-agent pipeline): two new columns on niche_candidates surfacing the latest
    # analysis verdict. Status stays freshness-driven; verdict is quality-driven.
    if "verdict" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN verdict TEXT")
    if "latest_analysis_id" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN latest_analysis_id TEXT")
    conn.commit()

    # One-shot: when upgrading from the old "niche" analyzer to the AI-tool-opportunity
    # analyzer, the existing candidates lack tool_concept/audience/etc. and raw_items are
    # already linked (so analyze would skip them). Wipe analysis state so the next run
    # produces fresh opportunities. Gated by a marker so it never runs twice.
    marker_row = conn.execute(
        "SELECT value FROM app_settings WHERE key='analyzer_version'"
    ).fetchone()
    if marker_row is None or marker_row[0] != "v2_ai_tool_opps":
        old_count = conn.execute("SELECT COUNT(*) FROM niche_candidates").fetchone()[0]
        if old_count > 0:
            conn.execute("DELETE FROM niche_item_links")
            conn.execute("DELETE FROM niche_candidates")
            logger.info("analyzer_v2_migration", cleared_niches=old_count)
        conn.execute(
            "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('analyzer_version', 'v2_ai_tool_opps')"
        )
        conn.commit()


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
    _migrate(conn)
    # Rebuild indexes after every migration to repair any index-level corruption
    # (wrong entry counts, stale pages) that can result from unclean shutdowns.
    conn.execute("REINDEX")
    conn.commit()

    logger.debug("database_ready", path=str(path))
    return conn

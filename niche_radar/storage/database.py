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

CREATE TABLE IF NOT EXISTS pipeline_jobs (
    id              TEXT PRIMARY KEY,
    step            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    logs            TEXT DEFAULT '[]',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_created ON pipeline_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_jobs_status  ON pipeline_jobs(status);

CREATE TABLE IF NOT EXISTS llm_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run    TEXT,
    agent           TEXT NOT NULL,
    model           TEXT NOT NULL,
    prompt_tokens   INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_llm_usage_run ON llm_usage(pipeline_run);
CREATE INDEX IF NOT EXISTS idx_llm_usage_created ON llm_usage(created_at);

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              TEXT PRIMARY KEY,
    prompt_hash     TEXT NOT NULL,
    model           TEXT NOT NULL,
    item_count      INTEGER NOT NULL DEFAULT 0,
    cluster_count   INTEGER NOT NULL DEFAULT 0,
    niche_count     INTEGER NOT NULL DEFAULT 0,
    budget_used     INTEGER NOT NULL DEFAULT 0,
    label           TEXT,
    started_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_hash    ON pipeline_runs(prompt_hash);

CREATE TABLE IF NOT EXISTS entities (
    id              TEXT PRIMARY KEY,
    type            TEXT NOT NULL CHECK(type IN ('company','product','technology','person','category')),
    canonical_name  TEXT NOT NULL,
    aliases         JSON DEFAULT '[]',
    first_seen      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    mention_count   INTEGER DEFAULT 0,
    source_diversity INTEGER DEFAULT 0,
    velocity_score  REAL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_velocity ON entities(velocity_score DESC);
CREATE INDEX IF NOT EXISTS idx_entities_mentions ON entities(mention_count DESC);

CREATE TABLE IF NOT EXISTS entity_mentions (
    entity_id       TEXT REFERENCES entities(id) ON DELETE CASCADE,
    raw_item_id     TEXT REFERENCES raw_items(id) ON DELETE CASCADE,
    sentiment       TEXT CHECK(sentiment IN ('positive','negative','neutral')),
    relevance       REAL DEFAULT 1.0 CHECK(relevance >= 0.0 AND relevance <= 1.0),
    extracted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (entity_id, raw_item_id)
);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_item ON entity_mentions(raw_item_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_extracted ON entity_mentions(extracted_at);

CREATE TABLE IF NOT EXISTS entity_velocity (
    entity_id       TEXT REFERENCES entities(id) ON DELETE CASCADE,
    week_start      DATE NOT NULL,
    mention_count   INTEGER DEFAULT 0,
    source_count    INTEGER DEFAULT 0,
    velocity_label  TEXT CHECK(velocity_label IN ('surging','growing','stable','declining')),
    velocity_score  REAL DEFAULT 0.0,
    PRIMARY KEY (entity_id, week_start)
);
CREATE INDEX IF NOT EXISTS idx_entity_velocity_week ON entity_velocity(week_start);
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

    # v3 (8-agent pipeline): new columns on niche_candidates.
    if "verdict" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN verdict TEXT")
    if "latest_analysis_id" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN latest_analysis_id TEXT")

    # v4 (enhancement): momentum tracking on niche_candidates.
    if "momentum_ratio" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN momentum_ratio REAL")
    if "momentum_label" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN momentum_label TEXT")
    if "momentum_updated_at" not in cols:
        conn.execute("ALTER TABLE niche_candidates ADD COLUMN momentum_updated_at TIMESTAMP")

    # v4: per-item pain score components on item_pain_extractions.
    extraction_cols = {r[1] for r in conn.execute("PRAGMA table_info(item_pain_extractions)").fetchall()}
    if "urgency" not in extraction_cols:
        conn.execute("ALTER TABLE item_pain_extractions ADD COLUMN urgency REAL")
    if "monetization_score" not in extraction_cols:
        conn.execute("ALTER TABLE item_pain_extractions ADD COLUMN monetization_score INTEGER")
    if "frequency_score" not in extraction_cols:
        conn.execute("ALTER TABLE item_pain_extractions ADD COLUMN frequency_score INTEGER")
    if "pain_score_total" not in extraction_cols:
        conn.execute("ALTER TABLE item_pain_extractions ADD COLUMN pain_score_total REAL")

    # v4: web validation result on niche_analyses.
    analysis_cols = {r[1] for r in conn.execute("PRAGMA table_info(niche_analyses)").fetchall()}
    if "web_validation" not in analysis_cols:
        conn.execute("ALTER TABLE niche_analyses ADD COLUMN web_validation TEXT")

    # v4: niche_shortlist table (starred niches).
    conn.execute("""
        CREATE TABLE IF NOT EXISTS niche_shortlist (
            niche_id   TEXT PRIMARY KEY REFERENCES niche_candidates(id),
            added_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            note       TEXT
        )
    """)
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

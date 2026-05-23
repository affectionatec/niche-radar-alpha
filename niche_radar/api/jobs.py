"""Persistent job manager for pipeline operations.

Jobs are persisted to the pipeline_jobs table in SQLite so they
survive container restarts. Running jobs keep an in-memory log
buffer that is flushed to the database on every status change.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Job:
    id: str
    step: str
    status: str  # pending | running | done | failed
    logs: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    completed_at: str | None = None


class JobManager:
    _MAX_LOG_LINES_PER_JOB = 500
    _MAX_JOBS = 100

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # In-memory buffer for running jobs (hot path for log appends)
        self._active: dict[str, Job] = {}

    def _db(self):
        """Get a database connection. Lazy import avoids circular deps."""
        from niche_radar.config import get_settings
        from niche_radar.storage.database import get_db
        return get_db(get_settings().database_url)

    def create(self, step: str) -> Job:
        job = Job(id=str(uuid.uuid4()), step=step, status="pending")
        db = self._db()
        try:
            db.execute(
                "INSERT INTO pipeline_jobs (id, step, status, logs, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (job.id, job.step, job.status, "[]", job.created_at),
            )
            db.execute(
                "DELETE FROM pipeline_jobs WHERE id NOT IN "
                "(SELECT id FROM pipeline_jobs ORDER BY created_at DESC LIMIT ?)",
                (self._MAX_JOBS,),
            )
            db.commit()
        finally:
            db.close()
        with self._lock:
            self._active[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            active = self._active.get(job_id)
            if active:
                return Job(
                    id=active.id, step=active.step, status=active.status,
                    logs=list(active.logs), created_at=active.created_at,
                    completed_at=active.completed_at,
                )
        db = self._db()
        try:
            row = db.execute(
                "SELECT id, step, status, logs, created_at, completed_at "
                "FROM pipeline_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if not row:
                return None
            return Job(
                id=row[0], step=row[1], status=row[2],
                logs=json.loads(row[3]) if row[3] else [],
                created_at=row[4] or "", completed_at=row[5],
            )
        finally:
            db.close()

    def list_recent(self, limit: int = 20) -> list[Job]:
        db = self._db()
        try:
            rows = db.execute(
                "SELECT id, step, status, created_at, completed_at "
                "FROM pipeline_jobs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            db.close()

        result = []
        with self._lock:
            for row in rows:
                job_id = row[0]
                if job_id in self._active:
                    a = self._active[job_id]
                    result.append(Job(
                        id=a.id, step=a.step, status=a.status,
                        logs=[], created_at=a.created_at,
                        completed_at=a.completed_at,
                    ))
                else:
                    result.append(Job(
                        id=row[0], step=row[1], status=row[2],
                        logs=[], created_at=row[3] or "",
                        completed_at=row[4],
                    ))
        return result

    def set_status(self, job_id: str, status: str) -> None:
        completed_at = (
            datetime.now(timezone.utc).isoformat()
            if status in ("done", "failed") else None
        )
        with self._lock:
            if job_id in self._active:
                self._active[job_id].status = status
                self._active[job_id].completed_at = completed_at
                logs_json = json.dumps(
                    self._active[job_id].logs[-self._MAX_LOG_LINES_PER_JOB:]
                )
                db = self._db()
                try:
                    db.execute(
                        "UPDATE pipeline_jobs SET status=?, completed_at=?, logs=? "
                        "WHERE id=?",
                        (status, completed_at, logs_json, job_id),
                    )
                    db.commit()
                finally:
                    db.close()
                if status in ("done", "failed"):
                    del self._active[job_id]

    def append_log(self, job_id: str, line: str) -> None:
        with self._lock:
            if job_id in self._active:
                logs = self._active[job_id].logs
                logs.append(line)
                overflow = len(logs) - self._MAX_LOG_LINES_PER_JOB
                if overflow > 0:
                    del logs[:overflow]


job_manager = JobManager()

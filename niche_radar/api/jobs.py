"""In-memory job manager for pipeline operations."""
from __future__ import annotations

import dataclasses
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
    # FIFO cap on log lines per job. The 8-agent pipeline can emit 600+ structured
    # progress lines per run; without a cap, /api/pipeline/jobs/{id}/logs returns ever-
    # growing JSON payloads.
    _MAX_LOG_LINES_PER_JOB = 500

    def __init__(self, max_jobs: int = 50) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(self, step: str) -> Job:
        job = Job(id=str(uuid.uuid4()), step=step, status="pending")
        with self._lock:
            if len(self._jobs) >= self._max_jobs:
                oldest = min(self._jobs.values(), key=lambda j: j.created_at)
                del self._jobs[oldest.id]
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[Job]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
            return [dataclasses.replace(j) for j in jobs[:limit]]

    def set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = status
                if status in ("done", "failed"):
                    self._jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()

    def append_log(self, job_id: str, line: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                logs = self._jobs[job_id].logs
                logs.append(line)
                # FIFO truncate from the head so the tail (most recent) is preserved.
                overflow = len(logs) - self._MAX_LOG_LINES_PER_JOB
                if overflow > 0:
                    del logs[:overflow]


job_manager = JobManager()

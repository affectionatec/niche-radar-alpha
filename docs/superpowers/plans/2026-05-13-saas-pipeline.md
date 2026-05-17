# SaaS Pipeline Control Panel — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the read-only Niche Radar frontend into a full SaaS control panel where users can trigger collect/extract/score/report from the UI, watch live logs, and browse all data without touching the CLI.

**Architecture:** A `JobManager` singleton in `niche_radar/api/jobs.py` tracks in-memory jobs (id, step, status, logs). FastAPI gains POST pipeline endpoints that spawn background threads running `python -m niche_radar <step>` subprocesses, capturing stdout line-by-line into job logs. The frontend adds a Pipeline control page, Niches list page, and Reports viewer page, all using SWR polling.

**Tech Stack:** FastAPI + subprocess + threading (backend); Next.js 14 App Router, TypeScript, SWR, Tailwind (frontend); pytest + FastAPI TestClient (tests)

---

## File Map

**New files:**
- `niche_radar/api/jobs.py` — JobManager singleton (in-memory job tracking)
- `tests/test_api/__init__.py` — empty, enables pytest discovery
- `tests/test_api/test_jobs.py` — unit tests for JobManager
- `tests/test_api/test_server.py` — integration tests for pipeline endpoints
- `frontend/src/app/pipeline/page.tsx` — pipeline control panel page
- `frontend/src/app/niches/page.tsx` — sortable niches table page
- `frontend/src/app/reports/page.tsx` — reports list + inline viewer page

**Modified files:**
- `niche_radar/api/server.py` — add CORS POST, pipeline endpoints, reports content endpoint
- `frontend/src/lib/types.ts` — add `Job`, `JobDetail`, `JobStatus`, `PipelineStep`
- `frontend/src/lib/api.ts` — add `postPipeline`, new endpoints
- `frontend/src/components/Navigation.tsx` — add nav links (PIPELINE, NICHES, REPORTS)
- `frontend/src/app/page.tsx` — remove CLI instruction empty states, add pipeline CTA button

---

### Task 1: JobManager module

**Files:**
- Create: `niche_radar/api/jobs.py`
- Create: `tests/test_api/__init__.py`
- Create: `tests/test_api/test_jobs.py`

- [ ] **Step 1: Create the empty test module**

```bash
mkdir -p tests/test_api
touch tests/test_api/__init__.py
```

- [ ] **Step 2: Write failing tests for JobManager**

Create `tests/test_api/test_jobs.py`:

```python
"""Tests for the in-memory JobManager."""
import time

import pytest

from niche_radar.api.jobs import JobManager


def test_create_job_returns_pending():
    mgr = JobManager()
    job = mgr.create("collect")
    assert job.id
    assert job.step == "collect"
    assert job.status == "pending"
    assert job.logs == []
    assert job.created_at
    assert job.completed_at is None


def test_get_returns_created_job():
    mgr = JobManager()
    job = mgr.create("extract")
    fetched = mgr.get(job.id)
    assert fetched is not None
    assert fetched.id == job.id


def test_get_unknown_returns_none():
    mgr = JobManager()
    assert mgr.get("nonexistent") is None


def test_set_status_running():
    mgr = JobManager()
    job = mgr.create("score")
    mgr.set_status(job.id, "running")
    assert mgr.get(job.id).status == "running"
    assert mgr.get(job.id).completed_at is None


def test_set_status_done_sets_completed_at():
    mgr = JobManager()
    job = mgr.create("report")
    mgr.set_status(job.id, "done")
    assert mgr.get(job.id).status == "done"
    assert mgr.get(job.id).completed_at is not None


def test_set_status_failed_sets_completed_at():
    mgr = JobManager()
    job = mgr.create("collect")
    mgr.set_status(job.id, "failed")
    assert mgr.get(job.id).status == "failed"
    assert mgr.get(job.id).completed_at is not None


def test_append_log():
    mgr = JobManager()
    job = mgr.create("collect")
    mgr.append_log(job.id, "line 1")
    mgr.append_log(job.id, "line 2")
    assert mgr.get(job.id).logs == ["line 1", "line 2"]


def test_list_recent_newest_first():
    mgr = JobManager()
    a = mgr.create("collect")
    time.sleep(0.01)
    b = mgr.create("extract")
    recent = mgr.list_recent(10)
    assert recent[0].id == b.id
    assert recent[1].id == a.id


def test_list_recent_respects_limit():
    mgr = JobManager()
    for _ in range(5):
        mgr.create("score")
    assert len(mgr.list_recent(3)) == 3


def test_max_jobs_evicts_oldest():
    mgr = JobManager(max_jobs=3)
    ids = [mgr.create("collect").id for _ in range(4)]
    # oldest (ids[0]) should be evicted
    assert mgr.get(ids[0]) is None
    assert mgr.get(ids[3]) is not None
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /app  # or project root
pytest tests/test_api/test_jobs.py -v
```

Expected: All tests fail with `ModuleNotFoundError: No module named 'niche_radar.api.jobs'`

- [ ] **Step 4: Create `niche_radar/api/jobs.py`**

```python
"""In-memory job manager for pipeline operations."""
from __future__ import annotations

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
    def __init__(self, max_jobs: int = 50) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(self, step: str) -> Job:
        job = Job(id=str(uuid.uuid4()), step=step, status="pending")
        with self._lock:
            self._jobs[job.id] = job
            if len(self._jobs) > self._max_jobs:
                oldest = min(self._jobs.values(), key=lambda j: j.created_at)
                del self._jobs[oldest.id]
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list_recent(self, limit: int = 20) -> list[Job]:
        with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].status = status
                if status in ("done", "failed"):
                    self._jobs[job_id].completed_at = datetime.now(timezone.utc).isoformat()

    def append_log(self, job_id: str, line: str) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id].logs.append(line)


job_manager = JobManager()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api/test_jobs.py -v
```

Expected: All 10 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add niche_radar/api/jobs.py tests/test_api/__init__.py tests/test_api/test_jobs.py
git commit -m "feat: add in-memory JobManager for pipeline job tracking"
```

---

### Task 2: Pipeline API endpoints

**Files:**
- Modify: `niche_radar/api/server.py`
- Create: `tests/test_api/test_server.py`

- [ ] **Step 1: Write failing tests for the new endpoints**

Create `tests/test_api/test_server.py`:

```python
"""Tests for pipeline API endpoints."""
import pytest
from fastapi.testclient import TestClient

from niche_radar.api.server import app

client = TestClient(app)


def test_post_collect_returns_job():
    resp = client.post("/api/pipeline/collect")
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "pending"


def test_post_collect_with_source():
    resp = client.post("/api/pipeline/collect?source=reddit")
    assert resp.status_code == 200
    assert "job_id" in resp.json()


def test_post_extract_returns_job():
    resp = client.post("/api/pipeline/extract")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_post_score_returns_job():
    resp = client.post("/api/pipeline/score")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_post_report_returns_job():
    resp = client.post("/api/pipeline/report")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_post_run_all_returns_job():
    resp = client.post("/api/pipeline/run-all")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_get_jobs_returns_list():
    # Trigger one job first so the list is not empty
    client.post("/api/pipeline/score")
    resp = client.get("/api/pipeline/jobs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_get_job_logs_existing():
    r = client.post("/api/pipeline/collect")
    job_id = r.json()["job_id"]
    resp = client.get(f"/api/pipeline/jobs/{job_id}/logs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == job_id
    assert "logs" in data
    assert "status" in data


def test_get_job_logs_missing_returns_404():
    resp = client.get("/api/pipeline/jobs/does-not-exist/logs")
    assert resp.status_code == 404


def test_get_report_missing_returns_404(tmp_path, monkeypatch):
    from niche_radar.config import Settings
    monkeypatch.setattr(
        "niche_radar.api.server.get_settings",
        lambda: Settings(report_output_dir=str(tmp_path)),
    )
    resp = client.get("/api/reports/nonexistent.md")
    assert resp.status_code == 404


def test_get_report_path_traversal_rejected(tmp_path, monkeypatch):
    from niche_radar.config import Settings
    monkeypatch.setattr(
        "niche_radar.api.server.get_settings",
        lambda: Settings(report_output_dir=str(tmp_path)),
    )
    resp = client.get("/api/reports/../../etc/passwd")
    # Either 403 or 404 is acceptable — the key thing is it's not 200
    assert resp.status_code in (403, 404, 422)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api/test_server.py -v
```

Expected: Tests for pipeline endpoints fail with 404/405 (routes don't exist yet).

- [ ] **Step 3: Update `niche_radar/api/server.py`**

Replace the entire file with:

```python
"""FastAPI HTTP server exposing Niche Radar data and pipeline controls."""
from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from niche_radar.api.jobs import job_manager
from niche_radar.config import get_settings
from niche_radar.storage.database import get_db
from niche_radar.storage import repository

app = FastAPI(title="Niche Radar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _db():
    settings = get_settings()
    return get_db(settings.database_url)


# ── Existing read endpoints ────────────────────────────────────────────────

@app.get("/api/status")
def get_status():
    db = _db()
    try:
        stats = db.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM raw_items) as raw_count, "
            "(SELECT COUNT(*) FROM niche_candidates WHERE status='active') as niche_count, "
            "(SELECT COUNT(*) FROM niche_scores) as score_count, "
            "(SELECT MAX(started_at) FROM collection_runs) as last_run, "
            "(SELECT COUNT(*) FROM collection_runs) as cycle_count"
        ).fetchone()
        sources = repository.get_system_health(db)
        return {
            "raw_items": stats[0] or 0,
            "active_niches": stats[1] or 0,
            "scores_recorded": stats[2] or 0,
            "last_collection": stats[3],
            "collection_cycle": stats[4] or 0,
            "sources": sources,
        }
    finally:
        db.close()


def _tier(score: float) -> str:
    if score >= 80:
        return "high_priority"
    if score >= 65:
        return "watchlist"
    return "archive"


@app.get("/api/niches")
def list_niches():
    db = _db()
    try:
        scores = repository.get_latest_scores(db)
        for s in scores:
            s["tier"] = _tier(s["composite_score"])
            row = db.execute(
                "SELECT occurrence_count FROM niche_candidates WHERE id=?",
                (s["niche_id"],),
            ).fetchone()
            s["occurrence_count"] = row[0] if row else 1
        return scores
    finally:
        db.close()


@app.get("/api/niches/{niche_id}")
def get_niche(niche_id: str):
    db = _db()
    try:
        scores = repository.get_latest_scores(db)
        niche = next((s for s in scores if s["niche_id"] == niche_id), None)
        if not niche:
            raise HTTPException(status_code=404, detail="Niche not found")
        niche["tier"] = _tier(niche["composite_score"])
        row = db.execute(
            "SELECT occurrence_count FROM niche_candidates WHERE id=?",
            (niche_id,),
        ).fetchone()
        niche["occurrence_count"] = row[0] if row else 1
        items = repository.get_niche_items(db, niche_id)
        return {"niche": niche, "items": items}
    finally:
        db.close()


@app.get("/api/reports")
def list_reports():
    settings = get_settings()
    report_dir = Path(settings.report_output_dir)
    if not report_dir.exists():
        return []
    files = sorted(
        (f for f in report_dir.iterdir() if f.is_file()),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return [
        {"filename": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
        for f in files
    ]


@app.get("/api/reports/{filename}")
def get_report_content(filename: str):
    settings = get_settings()
    report_dir = Path(settings.report_output_dir).resolve()
    # Prevent path traversal: resolve and confirm it stays inside report_dir
    try:
        file_path = (report_dir / filename).resolve()
        file_path.relative_to(report_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return {"content": file_path.read_text(encoding="utf-8")}


# ── Job runner helpers ─────────────────────────────────────────────────────

def _run_job(job_id: str, cmd: list[str]) -> None:
    """Run a single subprocess command, stream stdout to job logs."""
    job_manager.set_status(job_id, "running")
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            job_manager.append_log(job_id, line.rstrip())
        proc.wait()
        job_manager.set_status(job_id, "done" if proc.returncode == 0 else "failed")
    except Exception as exc:
        job_manager.append_log(job_id, f"ERROR: {exc}")
        job_manager.set_status(job_id, "failed")


def _run_all_steps(job_id: str) -> None:
    """Run collect → extract → score → report sequentially."""
    steps = ["collect", "extract", "score", "report"]
    job_manager.set_status(job_id, "running")
    for step in steps:
        cmd = [sys.executable, "-m", "niche_radar", step]
        job_manager.append_log(job_id, f"=== {step.upper()} ===")
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                job_manager.append_log(job_id, line.rstrip())
            proc.wait()
            if proc.returncode != 0:
                job_manager.append_log(job_id, f"FAILED (exit {proc.returncode})")
                job_manager.set_status(job_id, "failed")
                return
        except Exception as exc:
            job_manager.append_log(job_id, f"ERROR: {exc}")
            job_manager.set_status(job_id, "failed")
            return
    job_manager.set_status(job_id, "done")


# ── Pipeline trigger endpoints ─────────────────────────────────────────────

@app.post("/api/pipeline/collect")
def trigger_collect(source: Optional[str] = None):
    job = job_manager.create("collect")
    cmd = [sys.executable, "-m", "niche_radar", "collect"]
    if source:
        cmd += ["--source", source]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": "pending"}


@app.post("/api/pipeline/extract")
def trigger_extract():
    job = job_manager.create("extract")
    cmd = [sys.executable, "-m", "niche_radar", "extract"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": "pending"}


@app.post("/api/pipeline/score")
def trigger_score():
    job = job_manager.create("score")
    cmd = [sys.executable, "-m", "niche_radar", "score"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": "pending"}


@app.post("/api/pipeline/report")
def trigger_report():
    job = job_manager.create("report")
    cmd = [sys.executable, "-m", "niche_radar", "report"]
    threading.Thread(target=_run_job, args=(job.id, cmd), daemon=True).start()
    return {"job_id": job.id, "status": "pending"}


@app.post("/api/pipeline/run-all")
def trigger_run_all():
    job = job_manager.create("run-all")
    threading.Thread(target=_run_all_steps, args=(job.id,), daemon=True).start()
    return {"job_id": job.id, "status": "pending"}


@app.get("/api/pipeline/jobs")
def list_jobs():
    jobs = job_manager.list_recent(20)
    return [
        {
            "id": j.id,
            "step": j.step,
            "status": j.status,
            "created_at": j.created_at,
            "completed_at": j.completed_at,
        }
        for j in jobs
    ]


@app.get("/api/pipeline/jobs/{job_id}/logs")
def get_job_logs(job_id: str):
    job = job_manager.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "step": job.step,
        "status": job.status,
        "logs": job.logs,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api/test_server.py -v
```

Expected: All tests PASS. The path-traversal test expects 403/404/422 — any of those is fine.

- [ ] **Step 5: Run full test suite to confirm no regressions**

```bash
pytest --tb=short -q
```

Expected: All existing tests continue to pass.

- [ ] **Step 6: Commit**

```bash
git add niche_radar/api/server.py tests/test_api/test_server.py
git commit -m "feat: add pipeline trigger endpoints and reports content API"
```

---

### Task 3: Frontend types and API client

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Update `frontend/src/lib/types.ts`**

Replace the entire file:

```typescript
export interface SourceHealth {
  source: string;
  status: string;
  last_run: string;
  items: number;
}

export interface SystemStatus {
  raw_items: number;
  active_niches: number;
  scores_recorded: number;
  last_collection: string | null;
  collection_cycle: number;
  sources: SourceHealth[];
}

export interface NicheScore {
  score_id: string;
  niche_id: string;
  keyword: string;
  aliases: string[];
  engagement: number;
  search_trend: number;
  content_gap: number;
  market_traction: number;
  composite_score: number;
  scored_at: string;
  first_seen: string;
  last_seen: string;
  occurrence_count: number;
  tier: 'high_priority' | 'watchlist' | 'archive';
}

export interface RawItem {
  id: string;
  source: string;
  source_id: string;
  title: string | null;
  body: string | null;
  url: string | null;
  score: number | null;
  comment_count: number | null;
  collected_at: string;
  keyphrase: string;
  relevance_score: number;
}

export interface NicheDetail {
  niche: NicheScore;
  items: RawItem[];
}

export type JobStatus = 'pending' | 'running' | 'done' | 'failed';

export interface Job {
  id: string;
  step: string;
  status: JobStatus;
  created_at: string;
  completed_at: string | null;
}

export interface JobDetail extends Job {
  logs: string[];
}

export interface ReportFile {
  filename: string;
  size: number;
  modified: number;
}
```

- [ ] **Step 2: Update `frontend/src/lib/api.ts`**

Replace the entire file:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

export async function fetcher<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API ${res.status}: ${url}`);
  return res.json() as Promise<T>;
}

export async function postPipeline(
  step: string,
  params?: Record<string, string>,
): Promise<{ job_id: string; status: string }> {
  const url = new URL(`${API_URL}/api/pipeline/${step}`);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      url.searchParams.set(k, v);
    }
  }
  const res = await fetch(url.toString(), { method: 'POST' });
  if (!res.ok) throw new Error(`Pipeline ${step} failed: ${res.status}`);
  return res.json() as Promise<{ job_id: string; status: string }>;
}

export const endpoints = {
  status: `${API_URL}/api/status`,
  niches: `${API_URL}/api/niches`,
  niche: (id: string) => `${API_URL}/api/niches/${id}`,
  reports: `${API_URL}/api/reports`,
  reportContent: (filename: string) => `${API_URL}/api/reports/${encodeURIComponent(filename)}`,
  jobs: `${API_URL}/api/pipeline/jobs`,
  jobLogs: (id: string) => `${API_URL}/api/pipeline/jobs/${id}/logs`,
};
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 4: Commit**

```bash
cd ..
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat: add Job/JobDetail types and pipeline API client helpers"
```

---

### Task 4: Navigation — add pipeline, niches, reports links

**Files:**
- Modify: `frontend/src/components/Navigation.tsx`

- [ ] **Step 1: Update `frontend/src/components/Navigation.tsx`**

Replace the entire file:

```tsx
import Link from 'next/link';

const NAV_LINKS = [
  { href: '/pipeline', label: 'PIPELINE' },
  { href: '/niches', label: 'NICHES' },
  { href: '/reports', label: 'REPORTS' },
];

export default function Navigation() {
  return (
    <nav
      style={{
        backgroundColor: '#1f2228',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        padding: '0 24px',
        height: '56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '40px' }}>
        <Link
          href="/"
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '14px',
            fontWeight: 400,
            color: '#ffffff',
            textDecoration: 'none',
            letterSpacing: '1.4px',
            textTransform: 'uppercase',
          }}
        >
          NICHE RADAR
        </Link>
        <div style={{ display: 'flex', gap: '28px' }}>
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              style={{
                fontFamily: 'var(--font-inter)',
                fontSize: '11px',
                color: 'rgba(255,255,255,0.45)',
                textDecoration: 'none',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              {link.label}
            </Link>
          ))}
        </div>
      </div>
      <span
        style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '11px',
          color: 'rgba(255, 255, 255, 0.3)',
          letterSpacing: '1px',
          textTransform: 'uppercase',
        }}
      >
        ALPHA
      </span>
    </nav>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/components/Navigation.tsx
git commit -m "feat: add pipeline/niches/reports nav links"
```

---

### Task 5: Pipeline control page

**Files:**
- Create: `frontend/src/app/pipeline/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/pipeline/page.tsx`**

```tsx
'use client';
import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher, postPipeline } from '@/lib/api';
import { Job, JobDetail, JobStatus } from '@/lib/types';

const SOURCES = ['', 'reddit', 'hn', 'google_trends', 'github', 'youtube'] as const;

const STEP_BUTTONS: { label: string; step: string; primary?: boolean }[] = [
  { label: 'COLLECT', step: 'collect' },
  { label: 'EXTRACT', step: 'extract' },
  { label: 'SCORE', step: 'score' },
  { label: 'REPORT', step: 'report' },
  { label: 'RUN ALL', step: 'run-all', primary: true },
];

function statusColor(status: JobStatus): string {
  if (status === 'done') return 'rgba(255,255,255,0.9)';
  if (status === 'failed') return 'rgba(255,80,80,0.85)';
  if (status === 'running') return 'rgba(255,255,255,0.6)';
  return 'rgba(255,255,255,0.3)';
}

export default function PipelinePage() {
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [source, setSource] = useState('');
  const [launching, setLaunching] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const { data: jobs, mutate: mutateJobs } = useSWR<Job[]>(
    endpoints.jobs,
    fetcher,
    { refreshInterval: 5_000 },
  );

  const { data: activeJob } = useSWR<JobDetail>(
    activeJobId ? endpoints.jobLogs(activeJobId) : null,
    fetcher,
    {
      refreshInterval:
        activeJob?.status === 'done' || activeJob?.status === 'failed' ? 0 : 2_000,
      onSuccess: () => {
        if (activeJob?.status === 'done' || activeJob?.status === 'failed') {
          mutateJobs();
        }
      },
    },
  );

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [activeJob?.logs?.length]);

  async function launch(step: string) {
    setError(null);
    setLaunching(step);
    try {
      const params: Record<string, string> = {};
      if (step === 'collect' && source) params.source = source;
      const { job_id } = await postPipeline(step, Object.keys(params).length ? params : undefined);
      setActiveJobId(job_id);
      mutateJobs();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to launch job');
    } finally {
      setLaunching(null);
    }
  }

  return (
    <div>
      <h1
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '30px',
          fontWeight: 400,
          color: '#ffffff',
          marginBottom: '48px',
        }}
      >
        PIPELINE
      </h1>

      {/* Action bar */}
      <section style={{ marginBottom: '48px' }}>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '12px',
            alignItems: 'center',
          }}
        >
          {/* Source selector — shown alongside COLLECT */}
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.15)',
              color: 'rgba(255,255,255,0.7)',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              letterSpacing: '0.8px',
              padding: '10px 14px',
              cursor: 'pointer',
              height: '40px',
            }}
          >
            {SOURCES.map((s) => (
              <option key={s} value={s} style={{ background: '#1f2228' }}>
                {s ? s.toUpperCase() : 'ALL SOURCES'}
              </option>
            ))}
          </select>

          {STEP_BUTTONS.map(({ label, step, primary }) => (
            <button
              key={step}
              disabled={launching !== null}
              onClick={() => launch(step)}
              style={{
                background: primary ? '#ffffff' : 'transparent',
                border: primary ? 'none' : '1px solid rgba(255,255,255,0.25)',
                color: primary ? '#1f2228' : '#ffffff',
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                fontWeight: primary ? 600 : 400,
                letterSpacing: '1px',
                textTransform: 'uppercase',
                padding: '0 20px',
                height: '40px',
                cursor: launching !== null ? 'not-allowed' : 'pointer',
                opacity: launching !== null ? 0.5 : 1,
              }}
            >
              {launching === step ? '...' : label}
            </button>
          ))}
        </div>

        {error && (
          <p
            style={{
              marginTop: '12px',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '12px',
              color: 'rgba(255,80,80,0.85)',
            }}
          >
            {error}
          </p>
        )}
      </section>

      {/* Live log viewer */}
      {activeJobId && activeJob && (
        <section style={{ marginBottom: '48px' }}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: '12px',
            }}
          >
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '12px',
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  color: '#ffffff',
                }}
              >
                {activeJob.step}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '11px',
                  letterSpacing: '0.6px',
                  textTransform: 'uppercase',
                  color: statusColor(activeJob.status),
                }}
              >
                {activeJob.status}
              </span>
            </div>
            <button
              onClick={() => setActiveJobId(null)}
              style={{
                background: 'none',
                border: 'none',
                color: 'rgba(255,255,255,0.3)',
                cursor: 'pointer',
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                letterSpacing: '0.5px',
              }}
            >
              DISMISS
            </button>
          </div>
          <div
            style={{
              backgroundColor: 'rgba(255,255,255,0.04)',
              border: '1px solid rgba(255,255,255,0.1)',
              padding: '16px 20px',
              maxHeight: '420px',
              overflowY: 'auto',
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '12px',
              color: 'rgba(255,255,255,0.7)',
              lineHeight: 1.75,
            }}
          >
            {activeJob.logs.length === 0 ? (
              <span style={{ color: 'rgba(255,255,255,0.25)' }}>
                {activeJob.status === 'pending' ? 'Starting...' : 'Waiting for output...'}
              </span>
            ) : (
              activeJob.logs.map((line, i) => (
                <div key={i}>{line || ' '}</div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        </section>
      )}

      {/* Job history */}
      <section>
        <h2
          style={{
            fontFamily: 'var(--font-inter)',
            fontSize: '20px',
            fontWeight: 400,
            color: '#ffffff',
            marginBottom: '20px',
          }}
        >
          HISTORY
        </h2>

        {!jobs || jobs.length === 0 ? (
          <p
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.3)',
              fontStyle: 'italic',
            }}
          >
            No jobs yet. Use the buttons above to run a pipeline step.
          </p>
        ) : (
          <div
            style={{
              border: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            {/* Header row */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 100px 180px 100px',
                padding: '10px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              {['JOB', 'STEP', 'STARTED', 'STATUS'].map((h) => (
                <span
                  key={h}
                  style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: '10px',
                    color: 'rgba(255,255,255,0.35)',
                    letterSpacing: '0.8px',
                    textTransform: 'uppercase',
                  }}
                >
                  {h}
                </span>
              ))}
            </div>
            {jobs.map((job) => (
              <div
                key={job.id}
                onClick={() => setActiveJobId(job.id)}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 100px 180px 100px',
                  padding: '10px 16px',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  cursor: 'pointer',
                  backgroundColor:
                    job.id === activeJobId ? 'rgba(255,255,255,0.04)' : 'transparent',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.35)',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {job.id.slice(0, 8)}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '11px',
                    color: '#ffffff',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}
                >
                  {job.step}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: '12px',
                    color: 'rgba(255,255,255,0.5)',
                  }}
                >
                  {new Date(job.created_at).toLocaleString()}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '11px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                    color: statusColor(job.status),
                  }}
                >
                  {job.status}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/app/pipeline/page.tsx
git commit -m "feat: add pipeline control panel with live log viewer and job history"
```

---

### Task 6: Dashboard — remove CLI instructions, add pipeline CTA

**Files:**
- Modify: `frontend/src/app/page.tsx`

- [ ] **Step 1: Update `frontend/src/app/page.tsx`**

Replace the `EmptyState` component and the two empty-state usages. Replace the entire file:

```tsx
'use client';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { NicheScore, SystemStatus } from '@/lib/types';
import NicheCard from '@/components/NicheCard';
import SourceHealthTable from '@/components/SourceHealthTable';

export default function Dashboard() {
  const { data: niches, error: nichesError, isLoading: nichesLoading } =
    useSWR<NicheScore[]>(endpoints.niches, fetcher, { refreshInterval: 30_000 });

  const { data: status } =
    useSWR<SystemStatus>(endpoints.status, fetcher, { refreshInterval: 30_000 });

  const highPriority = niches?.filter((n) => n.tier === 'high_priority') ?? [];
  const watchlist = niches?.filter((n) => n.tier === 'watchlist') ?? [];

  if (nichesError) {
    return (
      <div style={{ padding: '96px 0', textAlign: 'center' }}>
        <p
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '13px',
            color: 'rgba(255,255,255,0.35)',
            letterSpacing: '1px',
            textTransform: 'uppercase',
            marginBottom: '24px',
          }}
        >
          CANNOT CONNECT TO API — IS THE BACKEND RUNNING ON PORT 8000?
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Stats strip + pipeline CTA */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          paddingBottom: '48px',
          marginBottom: '48px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          flexWrap: 'wrap',
          gap: '32px',
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '48px' }}>
          {status ? (
            <>
              <Stat label="ACTIVE NICHES" value={status.active_niches} />
              <Stat label="RAW ITEMS" value={status.raw_items.toLocaleString()} />
              <Stat label="CYCLES" value={status.collection_cycle} />
              <Stat
                label="LAST COLLECTION"
                value={
                  status.last_collection
                    ? new Date(status.last_collection).toLocaleString()
                    : 'NEVER'
                }
              />
            </>
          ) : null}
        </div>
        <Link
          href="/pipeline"
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            fontWeight: 600,
            color: '#1f2228',
            backgroundColor: '#ffffff',
            textDecoration: 'none',
            letterSpacing: '1px',
            textTransform: 'uppercase',
            padding: '0 20px',
            height: '40px',
            display: 'inline-flex',
            alignItems: 'center',
            flexShrink: 0,
          }}
        >
          OPEN PIPELINE →
        </Link>
      </div>

      {/* High priority */}
      <section style={{ marginBottom: '64px' }}>
        <SectionHeading label="HIGH PRIORITY" count={highPriority.length} note="SCORE ≥ 80" />
        {nichesLoading ? (
          <LoadingGrid />
        ) : highPriority.length === 0 ? (
          <EmptySection href="/pipeline" cta="RUN PIPELINE" />
        ) : (
          <NicheGrid niches={highPriority} />
        )}
      </section>

      {/* Watchlist */}
      <section style={{ marginBottom: '64px' }}>
        <SectionHeading label="WATCHLIST" count={watchlist.length} note="SCORE 65–79" />
        {nichesLoading ? (
          <LoadingGrid />
        ) : watchlist.length === 0 ? (
          <EmptySection href="/pipeline" cta="RUN PIPELINE" />
        ) : (
          <NicheGrid niches={watchlist} />
        )}
      </section>

      {/* System health */}
      {status && (
        <section>
          <SectionHeading label="SYSTEM HEALTH" count={null} note={null} />
          <SourceHealthTable sources={status.sources} />
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div>
      <div
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.4)',
          marginBottom: '8px',
          textTransform: 'uppercase',
          letterSpacing: '0.6px',
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '28px',
          fontWeight: 300,
          color: '#ffffff',
          lineHeight: 1,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function SectionHeading({
  label,
  count,
  note,
}: {
  label: string;
  count: number | null;
  note: string | null;
}) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'baseline',
        gap: '16px',
        marginBottom: '24px',
      }}
    >
      <h2
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '30px',
          fontWeight: 400,
          color: '#ffffff',
          lineHeight: 1.2,
        }}
      >
        {label}
      </h2>
      {count !== null && (
        <span
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '13px',
            color: 'rgba(255,255,255,0.35)',
          }}
        >
          {count}
        </span>
      )}
      {note && (
        <span
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            color: 'rgba(255,255,255,0.25)',
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}
        >
          {note}
        </span>
      )}
    </div>
  );
}

function NicheGrid({ niches }: { niches: NicheScore[] }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: '1px',
        backgroundColor: 'rgba(255,255,255,0.08)',
      }}
    >
      {niches.map((n) => (
        <NicheCard key={n.niche_id} niche={n} />
      ))}
    </div>
  );
}

function EmptySection({ href, cta }: { href: string; cta: string }) {
  return (
    <div
      style={{
        border: '1px solid rgba(255,255,255,0.08)',
        padding: '48px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '24px',
      }}
    >
      <span
        style={{
          fontFamily: 'var(--font-inter)',
          fontSize: '13px',
          color: 'rgba(255,255,255,0.25)',
        }}
      >
        No data yet.
      </span>
      <Link
        href={href}
        style={{
          fontFamily: 'var(--font-geist-mono)',
          fontSize: '11px',
          color: 'rgba(255,255,255,0.7)',
          textDecoration: 'none',
          border: '1px solid rgba(255,255,255,0.2)',
          padding: '8px 16px',
          letterSpacing: '0.8px',
          textTransform: 'uppercase',
        }}
      >
        {cta} →
      </Link>
    </div>
  );
}

function LoadingGrid() {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
        gap: '1px',
        backgroundColor: 'rgba(255,255,255,0.08)',
      }}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            backgroundColor: 'rgba(255,255,255,0.03)',
            height: '200px',
          }}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/app/page.tsx
git commit -m "feat: remove CLI empty states from dashboard, add pipeline CTA"
```

---

### Task 7: Niches list page

**Files:**
- Create: `frontend/src/app/niches/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/niches/page.tsx`**

```tsx
'use client';
import { useState } from 'react';
import Link from 'next/link';
import useSWR from 'swr';
import { endpoints, fetcher } from '@/lib/api';
import { NicheScore } from '@/lib/types';

type SortKey = 'composite_score' | 'keyword' | 'occurrence_count' | 'last_seen';

const COLUMNS: { key: SortKey; label: string; width: string }[] = [
  { key: 'keyword', label: 'KEYWORD', width: '1fr' },
  { key: 'composite_score', label: 'SCORE', width: '80px' },
  { key: 'occurrence_count', label: 'MENTIONS', width: '90px' },
  { key: 'last_seen', label: 'LAST SEEN', width: '180px' },
];

const TIER_LABELS: Record<NicheScore['tier'], string> = {
  high_priority: 'HIGH',
  watchlist: 'WATCH',
  archive: 'ARCH',
};

export default function NichesPage() {
  const [sortKey, setSortKey] = useState<SortKey>('composite_score');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [filter, setFilter] = useState('');

  const { data: niches, error, isLoading } =
    useSWR<NicheScore[]>(endpoints.niches, fetcher, { refreshInterval: 60_000 });

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir('desc');
    }
  }

  const filtered = (niches ?? []).filter((n) =>
    filter ? n.keyword.toLowerCase().includes(filter.toLowerCase()) : true,
  );

  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    const cmp =
      typeof av === 'string'
        ? (av as string).localeCompare(bv as string)
        : (av as number) - (bv as number);
    return sortDir === 'asc' ? cmp : -cmp;
  });

  if (error) {
    return (
      <div style={{ padding: '96px 0', textAlign: 'center' }}>
        <p
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '12px',
            color: 'rgba(255,255,255,0.3)',
            letterSpacing: '0.8px',
            textTransform: 'uppercase',
          }}
        >
          CANNOT CONNECT TO API
        </p>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '32px',
          gap: '24px',
          flexWrap: 'wrap',
        }}
      >
        <h1
          style={{
            fontFamily: 'var(--font-inter)',
            fontSize: '30px',
            fontWeight: 400,
            color: '#ffffff',
          }}
        >
          NICHES
          {niches && (
            <span
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '13px',
                color: 'rgba(255,255,255,0.35)',
                marginLeft: '16px',
              }}
            >
              {niches.length}
            </span>
          )}
        </h1>
        <input
          type="text"
          placeholder="FILTER BY KEYWORD"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{
            background: 'rgba(255,255,255,0.06)',
            border: '1px solid rgba(255,255,255,0.15)',
            color: '#ffffff',
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            letterSpacing: '0.8px',
            padding: '10px 14px',
            width: '240px',
            outline: 'none',
          }}
        />
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : sorted.length === 0 ? (
        <div
          style={{
            border: '1px solid rgba(255,255,255,0.08)',
            padding: '48px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.25)',
            }}
          >
            {filter ? `No niches matching "${filter}"` : 'No niches yet.'}
          </span>
          {!filter && (
            <Link
              href="/pipeline"
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '11px',
                color: 'rgba(255,255,255,0.7)',
                textDecoration: 'none',
                border: '1px solid rgba(255,255,255,0.2)',
                padding: '8px 16px',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              RUN PIPELINE →
            </Link>
          )}
        </div>
      ) : (
        <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
          {/* Header row */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: `${COLUMNS.map((c) => c.width).join(' ')} 70px`,
              padding: '10px 16px',
              borderBottom: '1px solid rgba(255,255,255,0.08)',
            }}
          >
            {COLUMNS.map((col) => (
              <button
                key={col.key}
                onClick={() => toggleSort(col.key)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  textAlign: 'left',
                  fontFamily: 'var(--font-inter)',
                  fontSize: '10px',
                  color:
                    sortKey === col.key
                      ? 'rgba(255,255,255,0.7)'
                      : 'rgba(255,255,255,0.35)',
                  letterSpacing: '0.8px',
                  textTransform: 'uppercase',
                  display: 'flex',
                  gap: '6px',
                  alignItems: 'center',
                }}
              >
                {col.label}
                {sortKey === col.key && (
                  <span style={{ fontSize: '9px' }}>{sortDir === 'asc' ? '↑' : '↓'}</span>
                )}
              </button>
            ))}
            <span
              style={{
                fontFamily: 'var(--font-inter)',
                fontSize: '10px',
                color: 'rgba(255,255,255,0.35)',
                letterSpacing: '0.8px',
                textTransform: 'uppercase',
              }}
            >
              TIER
            </span>
          </div>

          {/* Data rows */}
          {sorted.map((n) => (
            <Link
              key={n.niche_id}
              href={`/niches/${n.niche_id}`}
              style={{
                display: 'grid',
                gridTemplateColumns: `${COLUMNS.map((c) => c.width).join(' ')} 70px`,
                padding: '12px 16px',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                textDecoration: 'none',
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '13px',
                  color: '#ffffff',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {n.keyword}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '13px',
                  color: '#ffffff',
                }}
              >
                {n.composite_score.toFixed(1)}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '13px',
                  color: 'rgba(255,255,255,0.6)',
                }}
              >
                {n.occurrence_count}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-inter)',
                  fontSize: '12px',
                  color: 'rgba(255,255,255,0.5)',
                }}
              >
                {new Date(n.last_seen).toLocaleDateString()}
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-geist-mono)',
                  fontSize: '10px',
                  color:
                    n.tier === 'high_priority'
                      ? 'rgba(255,255,255,0.85)'
                      : n.tier === 'watchlist'
                        ? 'rgba(255,255,255,0.5)'
                        : 'rgba(255,255,255,0.25)',
                  letterSpacing: '0.5px',
                  textTransform: 'uppercase',
                }}
              >
                {TIER_LABELS[n.tier]}
              </span>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
      {[0, 1, 2, 3, 4].map((i) => (
        <div
          key={i}
          style={{
            height: '48px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            backgroundColor: 'rgba(255,255,255,0.02)',
          }}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/app/niches/page.tsx
git commit -m "feat: add sortable/filterable niches list page"
```

---

### Task 8: Reports viewer page

**Files:**
- Create: `frontend/src/app/reports/page.tsx`

- [ ] **Step 1: Create `frontend/src/app/reports/page.tsx`**

```tsx
'use client';
import { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { endpoints, fetcher } from '@/lib/api';
import { ReportFile } from '@/lib/types';

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export default function ReportsPage() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: reports, error, isLoading } =
    useSWR<ReportFile[]>(endpoints.reports, fetcher, { refreshInterval: 30_000 });

  const { data: content, isLoading: contentLoading } = useSWR<{ content: string }>(
    selected ? endpoints.reportContent(selected) : null,
    fetcher,
  );

  if (error) {
    return (
      <div style={{ padding: '96px 0', textAlign: 'center' }}>
        <p
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '12px',
            color: 'rgba(255,255,255,0.3)',
            letterSpacing: '0.8px',
            textTransform: 'uppercase',
          }}
        >
          CANNOT CONNECT TO API
        </p>
      </div>
    );
  }

  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '32px',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <h1
          style={{
            fontFamily: 'var(--font-inter)',
            fontSize: '30px',
            fontWeight: 400,
            color: '#ffffff',
          }}
        >
          REPORTS
          {reports && (
            <span
              style={{
                fontFamily: 'var(--font-geist-mono)',
                fontSize: '13px',
                color: 'rgba(255,255,255,0.35)',
                marginLeft: '16px',
              }}
            >
              {reports.length}
            </span>
          )}
        </h1>
        <Link
          href="/pipeline"
          style={{
            fontFamily: 'var(--font-geist-mono)',
            fontSize: '11px',
            color: 'rgba(255,255,255,0.5)',
            textDecoration: 'none',
            border: '1px solid rgba(255,255,255,0.15)',
            padding: '8px 14px',
            letterSpacing: '0.8px',
            textTransform: 'uppercase',
          }}
        >
          GENERATE REPORT →
        </Link>
      </div>

      {isLoading ? (
        <LoadingSkeleton />
      ) : !reports || reports.length === 0 ? (
        <div
          style={{
            border: '1px solid rgba(255,255,255,0.08)',
            padding: '48px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '20px',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-inter)',
              fontSize: '13px',
              color: 'rgba(255,255,255,0.25)',
            }}
          >
            No reports yet.
          </span>
          <Link
            href="/pipeline"
            style={{
              fontFamily: 'var(--font-geist-mono)',
              fontSize: '11px',
              color: 'rgba(255,255,255,0.7)',
              textDecoration: 'none',
              border: '1px solid rgba(255,255,255,0.2)',
              padding: '8px 16px',
              letterSpacing: '0.8px',
              textTransform: 'uppercase',
            }}
          >
            GENERATE REPORT →
          </Link>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: selected ? '280px 1fr' : '1fr',
            gap: '1px',
            backgroundColor: 'rgba(255,255,255,0.08)',
            alignItems: 'start',
          }}
        >
          {/* File list */}
          <div style={{ backgroundColor: '#1f2228' }}>
            {reports.map((r) => (
              <button
                key={r.filename}
                onClick={() => setSelected(selected === r.filename ? null : r.filename)}
                style={{
                  width: '100%',
                  background:
                    r.filename === selected
                      ? 'rgba(255,255,255,0.07)'
                      : 'transparent',
                  border: 'none',
                  borderBottom: '1px solid rgba(255,255,255,0.05)',
                  padding: '14px 16px',
                  textAlign: 'left',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}
              >
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '12px',
                    color: r.filename === selected ? '#ffffff' : 'rgba(255,255,255,0.75)',
                    display: 'block',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {r.filename}
                </span>
                <span
                  style={{
                    fontFamily: 'var(--font-inter)',
                    fontSize: '11px',
                    color: 'rgba(255,255,255,0.3)',
                  }}
                >
                  {formatSize(r.size)} ·{' '}
                  {new Date(r.modified * 1000).toLocaleDateString()}
                </span>
              </button>
            ))}
          </div>

          {/* Content pane */}
          {selected && (
            <div
              style={{
                backgroundColor: '#1f2228',
                padding: '24px',
                minHeight: '400px',
              }}
            >
              {contentLoading ? (
                <span
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '12px',
                    color: 'rgba(255,255,255,0.3)',
                  }}
                >
                  Loading...
                </span>
              ) : content ? (
                <pre
                  style={{
                    fontFamily: 'var(--font-geist-mono)',
                    fontSize: '12px',
                    color: 'rgba(255,255,255,0.8)',
                    lineHeight: 1.7,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    margin: 0,
                  }}
                >
                  {content.content}
                </pre>
              ) : null}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ border: '1px solid rgba(255,255,255,0.1)' }}>
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            height: '60px',
            borderBottom: '1px solid rgba(255,255,255,0.05)',
            backgroundColor: 'rgba(255,255,255,0.02)',
          }}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/app/reports/page.tsx
git commit -m "feat: add reports viewer with inline content pane"
```

---

## Self-Review

**Spec coverage check:**
- ✅ JobManager with in-memory tracking → Task 1
- ✅ POST /api/pipeline/collect, /extract, /score, /report, /run-all → Task 2
- ✅ GET /api/pipeline/jobs, GET /api/pipeline/jobs/{id}/logs → Task 2
- ✅ GET /api/reports/{filename} → Task 2
- ✅ CORS updated to allow POST → Task 2
- ✅ Job type + PipelineStep in types.ts → Task 3
- ✅ postPipeline helper + new endpoints in api.ts → Task 3
- ✅ Navigation links (PIPELINE, NICHES, REPORTS) → Task 4
- ✅ Pipeline control page with buttons, source selector, live logs, history → Task 5
- ✅ Dashboard empty states replaced with pipeline CTA link → Task 6
- ✅ Niches sortable/filterable table → Task 7
- ✅ Reports list + inline viewer → Task 8

**Placeholder scan:** None found. All code is complete.

**Type consistency check:**
- `Job` interface uses `step: string` — matched by list_jobs and get_job_logs responses ✅
- `JobDetail extends Job` adds `logs: string[]` — matched by get_job_logs response ✅
- `endpoints.jobLogs(id)` uses `${API_URL}/api/pipeline/jobs/${id}/logs` — matches backend route ✅
- `postPipeline('run-all')` → URL `/api/pipeline/run-all` — matches `@app.post("/api/pipeline/run-all")` ✅
- `ReportFile.modified` is `number` (float from Python st_mtime) — `new Date(r.modified * 1000)` converts correctly ✅

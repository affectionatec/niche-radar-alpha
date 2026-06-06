# P2: Decompose `api/server.py` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 907-line `api/server.py` monolith into 8 focused APIRouter modules under `api/routes/`. Zero endpoint path changes, zero import breakage.

**Architecture:** `server.py` shrinks to a ~25-line assembly module: create `FastAPI` app, add CORS middleware, mount sub-routers, re-export `app` for backward compat. Each sub-router is a self-contained `APIRouter` with its own prefix and tags. Shared helpers (`_db`, `_tier`) move to `routes/_common.py`.

**Tech Stack:** FastAPI, Python 3.11+

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `niche_radar/api/routes/__init__.py` | Create | Empty package init |
| `niche_radar/api/routes/_common.py` | Create | `_db()`, `_tier()`, shared imports |
| `niche_radar/api/routes/status.py` | Create | `GET /api/status` |
| `niche_radar/api/routes/niches.py` | Create | 6 niche endpoints + shortlist + validate + momentum |
| `niche_radar/api/routes/reports.py` | Create | 2 report endpoints |
| `niche_radar/api/routes/settings.py` | Create | 6 settings endpoints (LLM + scoring-weights + models) |
| `niche_radar/api/routes/sources.py` | Create | 4 source endpoints |
| `niche_radar/api/routes/pipeline.py` | Create | 8 pipeline endpoints (trigger + jobs + runs + prompt-packs) |
| `niche_radar/api/routes/entities.py` | Create | 4 entity endpoints |
| `niche_radar/api/routes/cost.py` | Create | 1 cost endpoint |
| `niche_radar/api/server.py` | Rewrite | Shrink to ~25 lines: app + middleware + router mounting |
| `tests/test_api/test_basic.py` | Create | Smoke test: every endpoint returns 200 |

---

### Task 1: Create `routes/_common.py` — shared helpers

**Files:**
- Create: `niche_radar/api/routes/__init__.py`
- Create: `niche_radar/api/routes/_common.py`

Extract `_db()` and `_tier()` from `server.py` into a shared module that every route module imports.

- [ ] **Step 1: Create the files**

```python
# niche_radar/api/routes/__init__.py
```

```python
# niche_radar/api/routes/_common.py
"""Shared helpers imported by all route modules."""
from __future__ import annotations

from niche_radar.config import get_settings
from niche_radar.storage.database import get_db


def _db():
    settings = get_settings()
    return get_db(settings.database_url)


def _tier(score: float) -> str:
    if score >= 80:
        return "high_priority"
    if score >= 65:
        return "watchlist"
    return "archive"
```

- [ ] **Step 2: Verify no import errors**

Run: `python -c "from niche_radar.api.routes._common import _db, _tier; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add niche_radar/api/routes/__init__.py niche_radar/api/routes/_common.py
git commit -m "refactor(api): extract _db and _tier helpers into routes/_common.py"
```

---

### Task 2: Create `routes/status.py`

**Files:**
- Create: `niche_radar/api/routes/status.py`

- [ ] **Step 1: Write the route module**

```python
# niche_radar/api/routes/status.py
"""GET /api/status — system health and data freshness."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from niche_radar.api.routes._common import _db
from niche_radar.config import get_settings
from niche_radar.storage import repository

router = APIRouter(tags=["status"])


@router.get("/api/status")
def get_status():
    db = _db()
    settings = get_settings()
    try:
        stats = db.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM raw_items) as raw_count, "
            "(SELECT COUNT(*) FROM niche_candidates WHERE status='active') as niche_count, "
            "(SELECT MAX(started_at) FROM collection_runs) as last_run, "
            "(SELECT COUNT(*) FROM collection_runs) as cycle_count"
        ).fetchone()
        sources = repository.get_system_health(db)
        freshness = repository.get_freshness_summary(db)
        return {
            "raw_items": stats[0] or 0,
            "active_niches": stats[1] or 0,
            "last_collection": stats[2],
            "collection_cycle": stats[3] or 0,
            "sources": sources,
            "freshness": {
                "analysis_window_days": settings.analysis_window_days,
                "rules": {
                    "reddit_hours": settings.freshness_reddit_hours,
                    "hn_hours": settings.freshness_hn_hours,
                    "github_hours": settings.freshness_github_hours,
                    "google_trends_hours": settings.freshness_google_trends_hours,
                    "youtube_hours": settings.freshness_youtube_hours,
                },
                "per_source": freshness["sources"],
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database error: {exc}") from exc
    finally:
        db.close()
```

- [ ] **Step 2: Run test to confirm no regressions**

Run: `pytest tests/test_api/test_server.py -v -k "status"`
Expected: all status-related tests pass

- [ ] **Step 3: Commit**

```bash
git add niche_radar/api/routes/status.py
git commit -m "refactor(api): extract status route into routes/status.py"
```

---

### Task 3: Create `routes/niches.py`

**Files:**
- Create: `niche_radar/api/routes/niches.py`

Contains: `GET /api/niches`, `GET /api/niches/{niche_id}`, `POST /api/niches/{niche_id}/shortlist`, `DELETE /api/niches/{niche_id}/shortlist`, `GET /api/shortlist`, `POST /api/niches/{niche_id}/validate`, `GET /api/niches/{niche_id}/momentum`

- [ ] **Step 1: Write the route module (full 190 lines from server.py lines 72-274, using `from _common import _db, _tier`)**

Read `niche_radar/api/server.py` lines 72-274. Copy the following pieces into `niche_radar/api/routes/niches.py`:
- `_tier` function (replaced by import from `_common`)
- `ShortlistNote` Pydantic model
- All niche routes: `list_niches`, `get_niche`, `star_niche`, `unstar_niche`, `get_shortlist`, `validate_niche`, `get_momentum`

- [ ] **Step 2: Commit**

```bash
git add niche_radar/api/routes/niches.py
git commit -m "refactor(api): extract niche routes into routes/niches.py"
```

---

### Task 4: Create `routes/reports.py`

**Files:**
- Create: `niche_radar/api/routes/reports.py`

Contains: `GET /api/reports`, `GET /api/reports/{filename}`

Read server.py lines 277-305. Copy the two report endpoints into `niche_radar/api/routes/reports.py`.

- [ ] **Step 1: Write + commit**

```bash
git add niche_radar/api/routes/reports.py
git commit -m "refactor(api): extract report routes into routes/reports.py"
```

---

### Task 5: Create `routes/settings.py`

**Files:**
- Create: `niche_radar/api/routes/settings.py`

Contains: `GET /api/settings`, `POST /api/settings`, `POST /api/settings/test`, `GET /api/settings/models`, `GET /api/settings/scoring-weights`, `PUT /api/settings/scoring-weights`

Read server.py lines 308-455. Copy all settings endpoints + Pydantic models into `niche_radar/api/routes/settings.py`.

- [ ] **Step 1: Write + commit**

```bash
git add niche_radar/api/routes/settings.py
git commit -m "refactor(api): extract settings routes into routes/settings.py"
```

---

### Task 6: Create `routes/sources.py`

**Files:**
- Create: `niche_radar/api/routes/sources.py`

Contains: `GET /api/sources`, `GET /api/sources/{slug}`, `POST /api/sources/{slug}`, `POST /api/sources/{slug}/test`

Read server.py lines 458-580. Copy all source endpoints + `SourceCredentialUpdate` model.

- [ ] **Step 1: Write + commit**

```bash
git add niche_radar/api/routes/sources.py
git commit -m "refactor(api): extract source routes into routes/sources.py"
```

---

### Task 7: Create `routes/pipeline.py`

**Files:**
- Create: `niche_radar/api/routes/pipeline.py`

Contains: pipeline trigger endpoints, job runner functions, jobs listing, pipeline runs A/B, prompt-packs

Read server.py lines 583-826. Copy the `_run_job`, `_run_all_steps` helper functions + all pipeline/jobs/runs/prompt-packs endpoints + `PipelineRunLabel` model.

- [ ] **Step 1: Write + commit**

```bash
git add niche_radar/api/routes/pipeline.py
git commit -m "refactor(api): extract pipeline routes into routes/pipeline.py"
```

---

### Task 8: Create `routes/entities.py`

**Files:**
- Create: `niche_radar/api/routes/entities.py`

Contains: 4 entity endpoints (server.py lines 829-906). Move the entity repository imports from module level into the route functions (they're already at module level in server.py, keep them there for now).

Read server.py lines 829-906. Copy all entity endpoints.

- [ ] **Step 1: Write + commit**

```bash
git add niche_radar/api/routes/entities.py
git commit -m "refactor(api): extract entity routes into routes/entities.py"
```

---

### Task 9: Create `routes/cost.py`

**Files:**
- Create: `niche_radar/api/routes/cost.py`

Contains: `GET /api/cost/summary` (server.py lines 724-736)

- [ ] **Step 1: Write + commit**

```bash
git add niche_radar/api/routes/cost.py
git commit -m "refactor(api): extract cost route into routes/cost.py"
```

---

### Task 10: Rewrite `server.py` — app assembly

**Files:**
- Rewrite: `niche_radar/api/server.py`

Replace the entire file with:

```python
"""FastAPI HTTP server — assembles app from route modules."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from niche_radar.api.routes.status import router as status_router
from niche_radar.api.routes.niches import router as niches_router
from niche_radar.api.routes.reports import router as reports_router
from niche_radar.api.routes.settings import router as settings_router
from niche_radar.api.routes.sources import router as sources_router
from niche_radar.api.routes.pipeline import router as pipeline_router
from niche_radar.api.routes.entities import router as entities_router
from niche_radar.api.routes.cost import router as cost_router

app = FastAPI(title="Niche Radar API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(status_router)
app.include_router(niches_router)
app.include_router(reports_router)
app.include_router(settings_router)
app.include_router(sources_router)
app.include_router(pipeline_router)
app.include_router(entities_router)
app.include_router(cost_router)
```

- [ ] **Step 1: Run full test suite**

Run: `pytest --tb=short -q`
Expected: same 6 pre-existing failures, no new failures, no import errors

- [ ] **Step 2: Verify all endpoint paths are unchanged**

Run: `python -c "from niche_radar.api.server import app; routes = [r.path for r in app.routes]; print('\n'.join(sorted(routes)))"`
Expected: all 35 original paths present

- [ ] **Step 3: Verify `_db` and `_tier` are still importable for backward compat**

The old `server.py` had `_db()` and `_tier()` at module level. Check if any code imports them:

```bash
grep -rn "from niche_radar.api.server import.*_db\|from niche_radar.api.server import.*_tier" niche_radar/ tests/ --include="*.py"
```

If nothing imports them, safe to remove. If something does, add re-exports in server.py.

- [ ] **Step 4: Commit**

```bash
git add niche_radar/api/server.py
git commit -m "refactor(api): rewrite server.py as thin router assembly (~30 lines)"
```

---

### Task 11: Smoke test — every endpoint returns something

**Files:**
- Create: `tests/test_api/test_basic.py`

- [ ] **Step 1: Write smoke test**

```python
# tests/test_api/test_basic.py
"""Smoke test: every API endpoint returns a valid response."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from niche_radar.api.server import app


@pytest.fixture
def client():
    import os
    import tempfile
    test_dir = tempfile.mkdtemp(prefix="niche-radar-test-basic-")
    db_url = f"sqlite:///{test_dir}/test.db"
    os.environ["DATABASE_URL"] = db_url
    os.environ["REPORT_OUTPUT_DIR"] = test_dir

    import niche_radar.config
    niche_radar.config._settings = None

    from niche_radar.storage.database import get_db as raw_get_db
    import niche_radar.api.server as server_mod

    def _test_db():
        return raw_get_db(db_url)

    server_mod._db = _test_db
    yield TestClient(app)
    niche_radar.config._settings = None


GET_ENDPOINTS = [
    "/api/status",
    "/api/niches",
    "/api/shortlist",
    "/api/reports",
    "/api/settings",
    "/api/settings/models",
    "/api/settings/scoring-weights",
    "/api/sources",
    "/api/pipeline/jobs",
    "/api/pipeline/runs",
    "/api/cost/summary",
    "/api/entities",
    "/api/entities/trending",
    "/api/prompt-packs",
]


@pytest.mark.parametrize("path", GET_ENDPOINTS)
def test_get_endpoint_returns_200_or_handles_empty_db(client, path):
    """Every GET endpoint should return 200 (or 404 for detail routes with missing IDs)."""
    resp = client.get(path)
    # All list endpoints should return 200 even with empty DB
    assert resp.status_code == 200, f"{path} returned {resp.status_code}: {resp.text[:200]}"
```

- [ ] **Step 2: Run smoke test**

Run: `pytest tests/test_api/test_basic.py -v`
Expected: all 14 endpoints return 200

- [ ] **Step 3: Commit**

```bash
git add tests/test_api/test_basic.py
git commit -m "test(api): add smoke test covering all 14 GET endpoints"
```

---

### Task 12: Run full test suite and verify

- [ ] **Step 1: Full test run**

Run: `pytest --tb=short -q`
Expected: 345+ tests, same 6 pre-existing failures (test_pipeline.py ×5, test_jobs.py ×1), zero new failures

- [ ] **Step 2: Verify `wc -l server.py` < 50**

Run: `wc -l niche_radar/api/server.py`
Expected: < 50 lines

- [ ] **Step 3: Verify route count**

Run: `python -c "from niche_radar.api.server import app; print(len([r for r in app.routes if hasattr(r, 'methods')]))"`
Expected: 35 route handlers

- [ ] **Step 4: Commit any stragglers, push, create PR**

```bash
git push -u origin enhancement/p2-decompose-server-py
gh pr create ...
```

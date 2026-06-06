"""FastAPI HTTP server — assembles app from route modules."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from niche_radar.api.routes._common import _db, _tier  # re-exported for backward compat
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

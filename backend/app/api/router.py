"""Root API router aggregation."""

from fastapi import APIRouter

from app.api.routes import (
    analysis,
    automation,
    clips,
    dashboard,
    health,
    jobs,
    live,
    media,
    projects,
    settings,
    system,
)
from app.api.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(dashboard.router)
api_router.include_router(settings.router)
api_router.include_router(projects.router)
api_router.include_router(media.router)
api_router.include_router(jobs.router)
api_router.include_router(analysis.router)
api_router.include_router(clips.router)
api_router.include_router(live.router)
api_router.include_router(automation.router)
api_router.include_router(websocket_router)

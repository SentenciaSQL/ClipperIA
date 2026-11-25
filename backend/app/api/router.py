"""Root API router aggregation."""

from fastapi import APIRouter

from app.api.routes import dashboard, health, settings, system
from app.api.websocket import router as websocket_router

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(system.router)
api_router.include_router(dashboard.router)
api_router.include_router(settings.router)
api_router.include_router(websocket_router)

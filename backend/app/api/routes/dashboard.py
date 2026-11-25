"""Dashboard endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.dashboard_service import DashboardService

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/overview")
def dashboard_overview(db: Session = Depends(get_db)) -> dict[str, Any]:
    return DashboardService(db).get_overview()

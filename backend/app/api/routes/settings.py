"""Settings endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import RuntimeConfigResponse, SettingResponse, SettingUpsertRequest
from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.settings_service import SettingsService

router = APIRouter(
    prefix="/settings",
    tags=["settings"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/runtime", response_model=RuntimeConfigResponse)
def get_runtime_config(db: Session = Depends(get_db)) -> RuntimeConfigResponse:
    data = SettingsService(db).get_runtime_config()
    return RuntimeConfigResponse(**data)


@router.put("", response_model=SettingResponse)
def upsert_setting(
    body: SettingUpsertRequest,
    db: Session = Depends(get_db),
) -> SettingResponse:
    data = SettingsService(db).upsert(
        key=body.key,
        value=body.value,
        description=body.description,
    )
    return SettingResponse(**data)

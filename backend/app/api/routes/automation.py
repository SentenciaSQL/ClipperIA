"""Hybrid AI providers, batch automation, profiles, metadata, models, storage."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.ai.providers.registry import ProviderRegistry
from app.core.config import get_settings
from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.services.batch_service import BatchService
from app.services.content_metadata_service import ContentMetadataService
from app.services.model_management_service import ModelManagementService
from app.services.profile_service import ProfileService
from app.services.resource_service import ResourceService
from app.services.storage_service import StorageService

router = APIRouter(tags=["automation"], dependencies=[Depends(require_api_token)])


class ProviderModeRequest(BaseModel):
    mode: str = Field(description="local | cloud | auto")


class MetadataRequest(BaseModel):
    provider: str | None = None
    platform: str = "tiktok"


class BatchRequest(BaseModel):
    media_asset_ids: list[str] = Field(min_length=1)
    profile_id: str | None = None


class ProfileUpsertRequest(BaseModel):
    profile: dict[str, Any]


class ProfileActiveRequest(BaseModel):
    profile_id: str


class WhisperEnsureRequest(BaseModel):
    model_size: str = "base"


class CacheCleanupRequest(BaseModel):
    older_than_hours: float = 72
    max_mb: float | None = None


@router.get("/ai/providers/status")
def provider_status() -> dict[str, Any]:
    return ProviderRegistry(get_settings()).status()


@router.post("/ai/providers/mode")
def set_provider_mode(body: ProviderModeRequest, db: Session = Depends(get_db)) -> dict:
    mode = body.mode.lower().strip()
    if mode not in {"local", "cloud", "auto"}:
        raise HTTPException(status_code=400, detail="mode must be local, cloud, or auto")
    from app.services.settings_service import SettingsService

    SettingsService(db).upsert("ai_provider_override", mode, "Preferred AI provider mode")
    # Reflect in process settings object for subsequent calls in this process
    settings = get_settings()
    object.__setattr__(settings, "ai_provider", mode)
    return {"ai_provider": mode, "status": ProviderRegistry(settings).status()}


@router.post("/clips/{clip_id}/metadata")
def generate_metadata(
    clip_id: str,
    body: MetadataRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        return ContentMetadataService(db).generate_for_clip(
            clip_id,
            provider=body.provider,
            platform=body.platform,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/profiles")
def list_profiles(db: Session = Depends(get_db)) -> dict:
    return ProfileService(db).list_profiles()


@router.put("/profiles/{profile_id}")
def upsert_profile(
    profile_id: str,
    body: ProfileUpsertRequest,
    db: Session = Depends(get_db),
) -> dict:
    return ProfileService(db).upsert_profile(profile_id, body.profile)


@router.post("/profiles/active")
def set_active_profile(body: ProfileActiveRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return ProfileService(db).set_active(body.profile_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/profiles/active")
def get_active_profile(db: Session = Depends(get_db)) -> dict:
    return ProfileService(db).get_active()


@router.post("/batch/process", status_code=status.HTTP_202_ACCEPTED)
def enqueue_batch(body: BatchRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return BatchService(db).enqueue(
            body.media_asset_ids,
            profile_id=body.profile_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/models")
def list_models() -> dict:
    return ModelManagementService().inventory()


@router.post("/models/whisper/ensure")
def ensure_whisper(body: WhisperEnsureRequest) -> dict:
    try:
        return ModelManagementService().ensure_whisper(body.model_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/models/whisper")
def delete_whisper(name: str | None = Query(default=None)) -> dict:
    return ModelManagementService().delete_whisper_cache(name)


@router.get("/storage/usage")
def storage_usage() -> dict:
    return StorageService().usage()


@router.post("/storage/cleanup")
def storage_cleanup(body: CacheCleanupRequest | None = None) -> dict:
    req = body or CacheCleanupRequest()
    return StorageService().cleanup_cache(
        older_than_hours=req.older_than_hours,
        max_mb=req.max_mb,
    )


@router.get("/system/resources")
def system_resources() -> dict:
    return ResourceService().snapshot()

"""System detection endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from app.core.security import require_api_token
from app.services.system_detection import SystemDetectionService

router = APIRouter(
    prefix="/system",
    tags=["system"],
    dependencies=[Depends(require_api_token)],
)


@router.get("/info")
def system_info() -> dict[str, Any]:
    return SystemDetectionService().detect_system_dict()


@router.get("/ffmpeg")
def ffmpeg_info() -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(SystemDetectionService().detect_ffmpeg())


@router.get("/gpu")
def gpu_info() -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(SystemDetectionService().detect_gpu())

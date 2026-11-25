"""Media library endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import require_api_token
from app.infrastructure.database.session import get_db
from app.media.ffprobe import MediaProbeError, SUPPORTED_EXTENSIONS
from app.services.media_service import MediaService

router = APIRouter(
    prefix="/media",
    tags=["media"],
    dependencies=[Depends(require_api_token)],
)


class ImportPathRequest(BaseModel):
    path: str = Field(min_length=1)
    project_id: str | None = None
    manage_original: bool = True
    display_name: str | None = None


@router.get("")
def list_media(
    project_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[dict]:
    return MediaService(db).list_media(
        project_id=project_id,
        query=q,
        status=status_filter,
    )


@router.get("/{asset_id}")
def get_media(asset_id: str, db: Session = Depends(get_db)) -> dict:
    asset = MediaService(db).get_media(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Media asset not found")
    return asset


@router.post("/import-path", status_code=status.HTTP_201_CREATED)
def import_from_path(body: ImportPathRequest, db: Session = Depends(get_db)) -> dict:
    try:
        return MediaService(db).import_local_file(
            body.path,
            project_id=body.project_id,
            manage_original=body.manage_original,
            display_name=body.display_name,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MediaProbeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    project_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    suffix = Path(file.filename or "video.mp4").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported media type '{suffix}'. Allowed: MP4, MKV, MOV.",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        temp_path = Path(tmp.name)
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)

    try:
        return MediaService(db).import_local_file(
            temp_path,
            project_id=project_id,
            manage_original=True,
            display_name=file.filename,
        )
    except MediaProbeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc
    finally:
        temp_path.unlink(missing_ok=True)


@router.post("/{asset_id}/reprocess")
def reprocess_media(asset_id: str, db: Session = Depends(get_db)) -> dict:
    try:
        return MediaService(db).reprocess(asset_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MediaProbeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    asset_id: str,
    delete_files: bool = Query(default=True),
    db: Session = Depends(get_db),
) -> None:
    try:
        MediaService(db).delete_media(asset_id, delete_files=delete_files)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{asset_id}/thumbnail")
def get_thumbnail(asset_id: str, db: Session = Depends(get_db)) -> FileResponse:
    asset = MediaService(db).get_media(asset_id)
    if asset is None or not asset.get("thumbnail_path"):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    path = Path(asset["thumbnail_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail file missing")
    return FileResponse(path, media_type="image/jpeg", filename=path.name)

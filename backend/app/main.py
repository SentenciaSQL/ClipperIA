"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.storage import ensure_storage_layout
from app.infrastructure.database.session import init_database
from app.services.system_detection import SystemDetectionService
from app.workers.handlers import register_handlers
from app.workers.job_manager import job_manager

settings = get_settings()
configure_logging(settings)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    ensure_storage_layout(settings)
    init_database()
    try:
        from app.services.storage_service import StorageService

        cleanup = StorageService(settings).optimize_if_needed()
        if cleanup:
            logger.info("startup_cache_cleanup", **{k: cleanup[k] for k in ("deleted_files", "freed_mb") if k in cleanup})
    except Exception as exc:  # noqa: BLE001
        logger.warning("startup_cache_cleanup_failed", error=str(exc))
    register_handlers(job_manager)
    job_manager.start(asyncio.get_running_loop())
    system = SystemDetectionService().detect_system()
    logger.info(
        "application_started",
        host=settings.host,
        port=settings.port,
        data_root=str(settings.data_root),
        ffmpeg=system.ffmpeg.available,
        gpu=system.gpu.available,
        gpu_name=system.gpu.name,
        whisper_model=settings.whisper_model_size,
        ollama_model=settings.ollama_model,
        ai_provider=settings.ai_provider,
    )
    yield
    job_manager.shutdown()
    logger.info("application_shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.debug or settings.environment == "development" else None,
    redoc_url=None,
)

# Desktop Flutter client on localhost only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1",
        "http://localhost",
        f"http://{settings.host}:{settings.port}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


def run() -> None:
    """Run the ASGI server bound to localhost."""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()

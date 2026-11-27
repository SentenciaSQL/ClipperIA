"""Runtime resource monitoring and concurrency helpers."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.services.system_detection import SystemDetectionService
from app.workers.job_manager import job_manager


class ResourceService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def snapshot(self) -> dict[str, Any]:
        system = SystemDetectionService().detect_system_dict()
        ram_total = float(system.get("ram_total_mb") or 0)
        ram_available = float(system.get("ram_available_mb") or 0)
        gpu = system.get("gpu") or {}
        recommendations = []
        if ram_available and ram_available < 2048:
            recommendations.append(
                "Low free RAM (<2 GB). Prefer Whisper tiny/base and reduce concurrent jobs."
            )
        if not gpu.get("available"):
            recommendations.append(
                "No NVIDIA GPU detected. Encoding falls back to CPU (libx264)."
            )
        elif not (system.get("ffmpeg") or {}).get("has_nvenc"):
            recommendations.append(
                "GPU present but NVENC unavailable in FFmpeg. Install an NVENC-enabled build."
            )
        return {
            "concurrency": {
                "max_concurrent_jobs": self._settings.max_concurrent_jobs,
                "max_gpu_inference_jobs": self._settings.max_gpu_inference_jobs,
                "job_recovery_enabled": self._settings.job_recovery_enabled,
            },
            "host": {
                "cpu_count": system.get("cpu_count"),
                "ram_total_mb": ram_total,
                "ram_available_mb": ram_available,
                "ram_used_pct": round(
                    ((ram_total - ram_available) / ram_total) * 100, 1
                )
                if ram_total
                else None,
            },
            "gpu": gpu,
            "ffmpeg": system.get("ffmpeg"),
            "recommendations": recommendations,
            "gpu_slots": {
                "configured": self._settings.max_gpu_inference_jobs,
            },
            "job_manager_started": getattr(job_manager, "_started", False),
        }

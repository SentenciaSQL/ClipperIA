"""Hardware and dependency detection services."""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from typing import Any

import psutil

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class FFmpegInfo:
    available: bool
    path: str | None
    version: str | None
    has_nvenc: bool
    has_nvdec: bool
    encoders: list[str]
    error: str | None = None


@dataclass
class GpuInfo:
    available: bool
    vendor: str | None
    name: str | None
    driver_version: str | None
    cuda_available: bool
    vram_total_mb: int | None
    vram_used_mb: int | None
    utilization_percent: float | None
    error: str | None = None


@dataclass
class SystemInfo:
    platform: str
    platform_release: str
    architecture: str
    python_version: str
    cpu_count: int
    ram_total_mb: int
    ram_available_mb: int
    ffmpeg: FFmpegInfo
    gpu: GpuInfo


class SystemDetectionService:
    """Detect FFmpeg, GPU/CUDA, and host resource availability."""

    def detect_ffmpeg(self) -> FFmpegInfo:
        path = shutil.which("ffmpeg")
        if path is None:
            return FFmpegInfo(
                available=False,
                path=None,
                version=None,
                has_nvenc=False,
                has_nvdec=False,
                encoders=[],
                error="ffmpeg not found on PATH",
            )

        version: str | None = None
        encoders: list[str] = []
        try:
            version_proc = subprocess.run(
                [path, "-version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            first_line = (version_proc.stdout or "").splitlines()
            version = first_line[0] if first_line else None

            encoders_proc = subprocess.run(
                [path, "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            for line in (encoders_proc.stdout or "").splitlines():
                stripped = line.strip()
                if "nvenc" in stripped.lower() or "h264_nvenc" in stripped or "hevc_nvenc" in stripped:
                    encoders.append(stripped)
                if "libx264" in stripped:
                    encoders.append(stripped)

            # Deduplicate while preserving order
            seen: set[str] = set()
            unique_encoders: list[str] = []
            for item in encoders:
                if item not in seen:
                    seen.add(item)
                    unique_encoders.append(item)
            encoders = unique_encoders

            has_nvenc = any("nvenc" in e.lower() for e in encoders)
            has_nvdec = self._probe_nvdec(path)

            return FFmpegInfo(
                available=True,
                path=path,
                version=version,
                has_nvenc=has_nvenc,
                has_nvdec=has_nvdec,
                encoders=encoders,
            )
        except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
            logger.warning("ffmpeg_detection_failed", error=str(exc))
            return FFmpegInfo(
                available=False,
                path=path,
                version=None,
                has_nvenc=False,
                has_nvdec=False,
                encoders=[],
                error=str(exc),
            )

    def _probe_nvdec(self, ffmpeg_path: str) -> bool:
        try:
            proc = subprocess.run(
                [ffmpeg_path, "-hide_banner", "-decoders"],
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            output = (proc.stdout or "").lower()
            return "cuvid" in output or "nvdec" in output
        except (OSError, subprocess.SubprocessError, TimeoutError):
            return False

    def detect_gpu(self) -> GpuInfo:
        # Prefer nvidia-smi when present (Windows/Linux NVIDIA environments)
        nvidia_smi = shutil.which("nvidia-smi")
        if nvidia_smi:
            try:
                proc = subprocess.run(
                    [
                        nvidia_smi,
                        "--query-gpu=name,driver_version,memory.total,memory.used,utilization.gpu",
                        "--format=csv,noheader,nounits",
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=10,
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    parts = [p.strip() for p in proc.stdout.strip().splitlines()[0].split(",")]
                    if len(parts) >= 5:
                        return GpuInfo(
                            available=True,
                            vendor="NVIDIA",
                            name=parts[0],
                            driver_version=parts[1],
                            cuda_available=True,
                            vram_total_mb=int(float(parts[2])),
                            vram_used_mb=int(float(parts[3])),
                            utilization_percent=float(parts[4]),
                        )
            except (OSError, subprocess.SubprocessError, TimeoutError, ValueError) as exc:
                logger.warning("nvidia_smi_failed", error=str(exc))
                return GpuInfo(
                    available=False,
                    vendor="NVIDIA",
                    name=None,
                    driver_version=None,
                    cuda_available=False,
                    vram_total_mb=None,
                    vram_used_mb=None,
                    utilization_percent=None,
                    error=str(exc),
                )

        return GpuInfo(
            available=False,
            vendor=None,
            name=None,
            driver_version=None,
            cuda_available=False,
            vram_total_mb=None,
            vram_used_mb=None,
            utilization_percent=None,
            error="No NVIDIA GPU detected (nvidia-smi not available)",
        )

    def detect_system(self) -> SystemInfo:
        mem = psutil.virtual_memory()
        return SystemInfo(
            platform=platform.system(),
            platform_release=platform.release(),
            architecture=platform.machine(),
            python_version=platform.python_version(),
            cpu_count=psutil.cpu_count(logical=True) or 1,
            ram_total_mb=int(mem.total / (1024 * 1024)),
            ram_available_mb=int(mem.available / (1024 * 1024)),
            ffmpeg=self.detect_ffmpeg(),
            gpu=self.detect_gpu(),
        )

    def detect_system_dict(self) -> dict[str, Any]:
        info = self.detect_system()
        payload = asdict(info)
        return payload

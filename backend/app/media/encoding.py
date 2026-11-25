"""FFmpeg clip encoding with NVENC/CPU fallback."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

ASPECT_RATIO_SIZES: dict[str, tuple[int, int]] = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
}

DURATION_PRESETS = [12, 15, 20, 30, 45, 60, 90]

EXPORT_PRESETS: dict[str, dict[str, Any]] = {
    "tiktok": {
        "label": "TikTok",
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
    },
    "instagram_reels": {
        "label": "Instagram Reels",
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
    },
    "youtube_shorts": {
        "label": "YouTube Shorts",
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "fps": 30,
        "video_bitrate": "10M",
        "audio_bitrate": "192k",
    },
    "landscape": {
        "label": "Landscape 16:9",
        "aspect_ratio": "16:9",
        "resolution": "1920x1080",
        "fps": 30,
        "video_bitrate": "10M",
        "audio_bitrate": "192k",
    },
    "square": {
        "label": "Square 1:1",
        "aspect_ratio": "1:1",
        "resolution": "1080x1080",
        "fps": 30,
        "video_bitrate": "8M",
        "audio_bitrate": "192k",
    },
}


@dataclass
class EncodeRequest:
    source: Path
    destination: Path
    start_seconds: float
    end_seconds: float
    aspect_ratio: str = "9:16"
    width: int | None = None
    height: int | None = None
    fps: int = 30
    video_bitrate: str = "8M"
    audio_bitrate: str = "192k"
    burn_subtitles: Path | None = None
    crop_box: dict[str, float] | None = None  # x,y,w,h normalized 0-1
    zoom: float = 1.0
    audio_source: Path | None = None
    prefer_nvenc: bool = True


class EncodingError(Exception):
    pass


class MediaEncoder:
    def __init__(self) -> None:
        self._ffmpeg = shutil.which("ffmpeg")
        if self._ffmpeg is None:
            raise EncodingError("ffmpeg not found on PATH")

    def has_nvenc(self) -> bool:
        proc = subprocess.run(
            [self._ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        return "h264_nvenc" in (proc.stdout or "")

    def encode(self, request: EncodeRequest) -> Path:
        if not request.source.is_file():
            raise EncodingError(f"Source missing: {request.source}")
        if request.end_seconds <= request.start_seconds:
            raise EncodingError("Invalid clip range")

        duration = request.end_seconds - request.start_seconds
        width, height = self._resolve_size(request)
        vf = self._build_video_filter(request, width, height)
        use_nvenc = request.prefer_nvenc and self.has_nvenc()

        request.destination.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._ffmpeg,
            "-y",
            "-ss",
            f"{request.start_seconds:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(request.source),
        ]
        if request.audio_source is not None:
            cmd.extend(["-i", str(request.audio_source)])

        cmd.extend(["-vf", vf])

        if use_nvenc:
            cmd.extend(
                [
                    "-c:v",
                    "h264_nvenc",
                    "-preset",
                    "p4",
                    "-rc",
                    "vbr",
                    "-b:v",
                    request.video_bitrate,
                ]
            )
        else:
            cmd.extend(
                [
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-b:v",
                    request.video_bitrate,
                    "-pix_fmt",
                    "yuv420p",
                ]
            )

        audio_map = "1:a:0" if request.audio_source is not None else "0:a:0?"
        cmd.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                audio_map,
                "-c:a",
                "aac",
                "-b:a",
                request.audio_bitrate,
                "-r",
                str(request.fps),
                "-movflags",
                "+faststart",
                str(request.destination),
            ]
        )

        logger.info(
            "encoding_clip",
            destination=str(request.destination),
            nvenc=use_nvenc,
            aspect=request.aspect_ratio,
            duration=duration,
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600)
        if proc.returncode != 0 or not request.destination.is_file():
            # Retry once on CPU if NVENC failed
            if use_nvenc:
                logger.warning("nvenc_failed_retrying_cpu", stderr=proc.stderr[-500:])
                request.prefer_nvenc = False
                return self.encode(request)
            raise EncodingError(proc.stderr.strip() or "ffmpeg encode failed")
        return request.destination

    def _resolve_size(self, request: EncodeRequest) -> tuple[int, int]:
        if request.width and request.height:
            return int(request.width), int(request.height)
        return ASPECT_RATIO_SIZES.get(request.aspect_ratio, (1080, 1920))

    def _build_video_filter(
        self,
        request: EncodeRequest,
        width: int,
        height: int,
    ) -> str:
        filters: list[str] = []
        if request.crop_box:
            # Normalized crop applied before scale; actual crop uses iw/ih expressions
            x = float(request.crop_box.get("x", 0.0))
            y = float(request.crop_box.get("y", 0.0))
            w = float(request.crop_box.get("w", 1.0))
            h = float(request.crop_box.get("h", 1.0))
            filters.append(
                f"crop=w=iw*{w:.4f}:h=ih*{h:.4f}:x=iw*{x:.4f}:y=ih*{y:.4f}"
            )
        zoom = max(1.0, float(request.zoom or 1.0))
        if zoom > 1.01:
            filters.append(
                f"scale=iw*{zoom:.3f}:ih*{zoom:.3f},crop=iw/{zoom:.3f}:ih/{zoom:.3f}"
            )
        # Cover target aspect then center-crop
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
        if request.burn_subtitles is not None and request.burn_subtitles.is_file():
            # Escape path for ffmpeg subtitles filter
            sub = str(request.burn_subtitles).replace("\\", "/").replace(":", "\\:")
            filters.append(f"subtitles='{sub}'")
        return ",".join(filters)

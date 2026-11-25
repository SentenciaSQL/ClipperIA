"""FFmpeg/ffprobe metadata extraction."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".mov"}


@dataclass
class MediaProbeResult:
    duration_seconds: float | None
    width: int | None
    height: int | None
    frame_rate: float | None
    video_codec: str | None
    audio_codec: str | None
    audio_streams: list[dict[str, Any]]
    file_size_bytes: int
    format_name: str | None
    creation_time: str | None
    raw: dict[str, Any]


class MediaProbeError(Exception):
    pass


def _parse_frame_rate(value: str | None) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    if "/" in value:
        num_s, den_s = value.split("/", 1)
        try:
            num = float(num_s)
            den = float(den_s)
            return num / den if den else None
        except ValueError:
            return None
    try:
        return float(value)
    except ValueError:
        return None


class MediaProbeService:
    def __init__(self) -> None:
        self._ffprobe = shutil.which("ffprobe") or shutil.which("ffmpeg")

    def validate_extension(self, path: Path) -> None:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise MediaProbeError(
                f"Unsupported media type '{path.suffix}'. Allowed: MP4, MKV, MOV."
            )

    def probe(self, path: Path) -> MediaProbeResult:
        if not path.is_file():
            raise MediaProbeError(f"File not found: {path}")
        self.validate_extension(path)

        ffprobe = shutil.which("ffprobe")
        if ffprobe is None:
            raise MediaProbeError("ffprobe not found on PATH")

        cmd = [
            ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
        except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
            raise MediaProbeError(f"ffprobe failed: {exc}") from exc

        if proc.returncode != 0:
            raise MediaProbeError(proc.stderr.strip() or "ffprobe returned non-zero")

        try:
            payload = json.loads(proc.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise MediaProbeError("Invalid ffprobe JSON output") from exc

        streams = payload.get("streams") or []
        fmt = payload.get("format") or {}
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        audio = audio_streams[0] if audio_streams else None

        duration = None
        if fmt.get("duration") is not None:
            try:
                duration = float(fmt["duration"])
            except (TypeError, ValueError):
                duration = None
        if duration is None and video and video.get("duration") is not None:
            try:
                duration = float(video["duration"])
            except (TypeError, ValueError):
                duration = None

        tags = fmt.get("tags") or {}
        creation = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")

        return MediaProbeResult(
            duration_seconds=duration,
            width=int(video["width"]) if video and video.get("width") else None,
            height=int(video["height"]) if video and video.get("height") else None,
            frame_rate=_parse_frame_rate(
                (video or {}).get("avg_frame_rate") or (video or {}).get("r_frame_rate")
            ),
            video_codec=(video or {}).get("codec_name"),
            audio_codec=(audio or {}).get("codec_name"),
            audio_streams=[
                {
                    "index": s.get("index"),
                    "codec": s.get("codec_name"),
                    "channels": s.get("channels"),
                    "sample_rate": s.get("sample_rate"),
                    "language": (s.get("tags") or {}).get("language"),
                }
                for s in audio_streams
            ],
            file_size_bytes=path.stat().st_size,
            format_name=fmt.get("format_name"),
            creation_time=creation,
            raw={"format": fmt, "streams": streams},
        )

    def probe_dict(self, path: Path) -> dict[str, Any]:
        return asdict(self.probe(path))

"""FFmpeg clip encoding with NVENC/CPU fallback and layered composition."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
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
class AudioMixInput:
    path: Path
    volume: float = 1.0
    fade_in_seconds: float = 0.0
    fade_out_seconds: float = 0.0
    # Delay on the output timeline (ms) after sync/start
    delay_ms: int = 0
    trim_start_seconds: float = 0.0
    trim_duration_seconds: float | None = None


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
    # Legacy single replacement audio
    audio_source: Path | None = None
    # Advanced multi-track mix (takes precedence when non-empty)
    audio_mix: list[AudioMixInput] = field(default_factory=list)
    # Video layer opacity 0..1 applied BEFORE captions (captions stay full opacity)
    opacity: float = 1.0
    # Optional opacity keyframes: [{"t": 0.0, "opacity": 1.0}, ...] clip-relative seconds
    opacity_keyframes: list[dict[str, float]] = field(default_factory=list)
    master_volume: float = 1.0
    normalize_audio: bool = False
    prefer_nvenc: bool = True
    include_source_audio: bool = True
    source_audio_volume: float = 1.0


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
        use_nvenc = request.prefer_nvenc and self.has_nvenc()
        request.destination.parent.mkdir(parents=True, exist_ok=True)

        mix_inputs = [m for m in request.audio_mix if m.path.is_file()]
        use_complex = (
            bool(mix_inputs)
            or request.opacity < 0.999
            or bool(request.opacity_keyframes)
            or (request.audio_source is not None and request.include_source_audio)
        )

        if use_complex:
            return self._encode_complex(
                request,
                duration=duration,
                width=width,
                height=height,
                use_nvenc=use_nvenc,
                mix_inputs=mix_inputs,
            )
        return self._encode_simple(
            request,
            duration=duration,
            width=width,
            height=height,
            use_nvenc=use_nvenc,
        )

    def _encode_simple(
        self,
        request: EncodeRequest,
        *,
        duration: float,
        width: int,
        height: int,
        use_nvenc: bool,
    ) -> Path:
        vf = self._build_video_filter(request, width, height, apply_opacity=False)
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
        if request.audio_source is not None and request.audio_source.is_file():
            cmd.extend(["-i", str(request.audio_source)])

        cmd.extend(["-vf", vf])
        cmd.extend(self._video_codec_args(use_nvenc, request.video_bitrate))

        audio_map = (
            "1:a:0"
            if request.audio_source is not None and request.audio_source.is_file()
            else "0:a:0?"
        )
        af = []
        if request.source_audio_volume != 1.0 and request.audio_source is None:
            af.append(f"volume={max(0.0, request.source_audio_volume) * request.master_volume:.4f}")
        elif request.master_volume != 1.0:
            af.append(f"volume={max(0.0, request.master_volume):.4f}")
        if request.normalize_audio:
            af.append("dynaudnorm")

        cmd.extend(["-map", "0:v:0", "-map", audio_map, "-c:a", "aac", "-b:a", request.audio_bitrate])
        if af:
            cmd.extend(["-af", ",".join(af)])
        cmd.extend(
            [
                "-r",
                str(request.fps),
                "-movflags",
                "+faststart",
                str(request.destination),
            ]
        )
        return self._run(cmd, request, use_nvenc)

    def _encode_complex(
        self,
        request: EncodeRequest,
        *,
        duration: float,
        width: int,
        height: int,
        use_nvenc: bool,
        mix_inputs: list[AudioMixInput],
    ) -> Path:
        cmd: list[str] = [
            self._ffmpeg,
            "-y",
            "-ss",
            f"{request.start_seconds:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(request.source),
        ]
        # Extra audio inputs after source
        extra_audio: list[AudioMixInput] = []
        if mix_inputs:
            extra_audio = mix_inputs
        elif request.audio_source is not None and request.audio_source.is_file():
            extra_audio = [AudioMixInput(path=request.audio_source, volume=1.0)]

        for item in extra_audio:
            # Each external file may need its own trim/delay; feed whole file and filter
            cmd.extend(["-i", str(item.path)])

        video_chain = self._build_video_filter(request, width, height, apply_opacity=False)
        opacity = max(0.0, min(1.0, float(request.opacity)))
        # Compose opacity on black BEFORE captions so captions stay independent
        if request.opacity_keyframes:
            opacity_expr = self._opacity_expression(request.opacity_keyframes, duration)
            video_filters = (
                f"[0:v]{video_chain},format=yuva420p,"
                f"colorchannelmixer=aa='{opacity_expr}'[vfade];"
                f"color=c=black:s={width}x{height}:d={duration:.3f}[bg];"
                f"[bg][vfade]overlay=format=auto[vbase]"
            )
        elif opacity < 0.999:
            video_filters = (
                f"[0:v]{video_chain},format=yuva420p,colorchannelmixer=aa={opacity:.4f}[vfade];"
                f"color=c=black:s={width}x{height}:d={duration:.3f}[bg];"
                f"[bg][vfade]overlay=format=auto[vbase]"
            )
        else:
            video_filters = f"[0:v]{video_chain}[vbase]"

        if request.burn_subtitles is not None and request.burn_subtitles.is_file():
            sub = str(request.burn_subtitles).replace("\\", "/").replace(":", "\\:")
            video_filters += f";[vbase]subtitles='{sub}'[vout]"
            vmap = "[vout]"
        else:
            vmap = "[vbase]"

        audio_labels: list[str] = []
        filter_parts = [video_filters]
        # Source audio (index 0) if included and no exclusive mix that already replaces it
        if request.include_source_audio and not (
            mix_inputs and all(m.path != request.source for m in mix_inputs)
            and request.source_audio_volume <= 0.001
        ):
            if request.include_source_audio and request.source_audio_volume > 0.001:
                vol = max(0.0, request.source_audio_volume)
                filter_parts.append(f"[0:a]volume={vol:.4f}[a0]")
                audio_labels.append("[a0]")

        for idx, item in enumerate(extra_audio, start=1):
            label_in = f"[{idx}:a]"
            chain = []
            if item.trim_start_seconds > 0 or item.trim_duration_seconds is not None:
                trim = f"atrim=start={item.trim_start_seconds:.3f}"
                if item.trim_duration_seconds is not None:
                    trim += f":duration={item.trim_duration_seconds:.3f}"
                chain.append(trim)
                chain.append("asetpts=PTS-STARTPTS")
            if item.delay_ms > 0:
                chain.append(f"adelay={item.delay_ms}|{item.delay_ms}")
            vol = max(0.0, float(item.volume))
            chain.append(f"volume={vol:.4f}")
            if item.fade_in_seconds > 0:
                chain.append(f"afade=t=in:st=0:d={item.fade_in_seconds:.3f}")
            if item.fade_out_seconds > 0 and item.trim_duration_seconds:
                st = max(0.0, item.trim_duration_seconds - item.fade_out_seconds)
                chain.append(f"afade=t=out:st={st:.3f}:d={item.fade_out_seconds:.3f}")
            out_label = f"[a{idx}]"
            filter_parts.append(f"{label_in}{','.join(chain)}{out_label}")
            audio_labels.append(out_label)

        if audio_labels:
            if len(audio_labels) == 1:
                filter_parts.append(
                    f"{audio_labels[0]}volume={max(0.0, request.master_volume):.4f}"
                    + (",dynaudnorm" if request.normalize_audio else "")
                    + "[aout]"
                )
            else:
                joined = "".join(audio_labels)
                filter_parts.append(
                    f"{joined}amix=inputs={len(audio_labels)}:dropout_transition=0:normalize=0,"
                    f"volume={max(0.0, request.master_volume):.4f}"
                    + (",dynaudnorm" if request.normalize_audio else "")
                    + "[aout]"
                )
            amap = "[aout]"
        else:
            # Silent track
            filter_parts.append(
                f"anullsrc=r=48000:cl=stereo,atrim=0:{duration:.3f}[aout]"
            )
            amap = "[aout]"

        cmd.extend(["-filter_complex", ";".join(filter_parts)])
        cmd.extend(["-map", vmap, "-map", amap])
        cmd.extend(self._video_codec_args(use_nvenc, request.video_bitrate))
        cmd.extend(
            [
                "-c:a",
                "aac",
                "-b:a",
                request.audio_bitrate,
                "-r",
                str(request.fps),
                "-movflags",
                "+faststart",
                "-t",
                f"{duration:.3f}",
                str(request.destination),
            ]
        )
        return self._run(cmd, request, use_nvenc)

    @staticmethod
    def _opacity_expression(keyframes: list[dict[str, float]], duration: float) -> str:
        """Build ffmpeg expression for opacity over clip-relative time `t`."""
        points = sorted(
            (
                (float(k.get("t", 0.0)), max(0.0, min(1.0, float(k.get("opacity", 1.0)))))
                for k in keyframes
            ),
            key=lambda p: p[0],
        )
        if not points:
            return "1"
        if len(points) == 1:
            return f"{points[0][1]:.4f}"
        # Piecewise linear: if(between(t,t0,t1), lerp, ...)
        parts: list[str] = []
        for i in range(len(points) - 1):
            t0, o0 = points[i]
            t1, o1 = points[i + 1]
            if abs(t1 - t0) < 1e-6:
                continue
            lerp = f"{o0:.4f}+({o1:.4f}-{o0:.4f})*(t-{t0:.3f})/({t1:.3f}-{t0:.3f})"
            parts.append(f"if(between(t\\,{t0:.3f}\\,{t1:.3f})\\,{lerp}")
        # Close nested ifs with final opacity
        expr = parts[0] if parts else f"{points[-1][1]:.4f}"
        for _ in range(1, len(parts)):
            expr += ")"
        # Fallback after last keyframe
        if parts:
            expr += f"\\,{points[-1][1]:.4f}" + (")" * (len(parts) - 1 + (1 if parts else 0)))
            # Fix: rebuild more simply
        # Simpler approach: use nested if(lt(t,t1), lerp, ...)
        expr = f"{points[-1][1]:.4f}"
        for i in range(len(points) - 2, -1, -1):
            t0, o0 = points[i]
            t1, o1 = points[i + 1]
            lerp = f"({o0:.4f}+({o1:.4f}-{o0:.4f})*(t-{t0:.3f})/({max(t1 - t0, 0.001):.3f}))"
            expr = f"if(lt(t\\,{t1:.3f})\\,{lerp}\\,{expr})"
        return expr

    def _video_codec_args(self, use_nvenc: bool, bitrate: str) -> list[str]:
        if use_nvenc:
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-rc", "vbr", "-b:v", bitrate]
        return [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-b:v",
            bitrate,
            "-pix_fmt",
            "yuv420p",
        ]

    def _run(self, cmd: list[str], request: EncodeRequest, use_nvenc: bool) -> Path:
        logger.info(
            "encoding_clip",
            destination=str(request.destination),
            nvenc=use_nvenc,
            aspect=request.aspect_ratio,
            opacity=request.opacity,
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=900)
        if proc.returncode != 0 or not request.destination.is_file():
            if use_nvenc:
                logger.warning("nvenc_failed_retrying_cpu", stderr=(proc.stderr or "")[-800:])
                request.prefer_nvenc = False
                return self.encode(request)
            raise EncodingError((proc.stderr or "").strip() or "ffmpeg encode failed")
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
        *,
        apply_opacity: bool,
    ) -> str:
        """
        Build the geometric video chain (crop/zoom/scale).

        When ``apply_opacity`` is False (complex path), captions are burned later
        AFTER the opacity overlay so they remain independent of video opacity.
        When True is unused; simple path burns captions here when opacity is full.
        """
        filters: list[str] = []
        if request.crop_box:
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
        filters.append(
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
        # Simple path: burn captions in the same vf chain (opacity handled by complex path)
        needs_complex_opacity = request.opacity < 0.999 or bool(request.opacity_keyframes)
        if not needs_complex_opacity and request.burn_subtitles is not None:
            if request.burn_subtitles.is_file():
                sub = str(request.burn_subtitles).replace("\\", "/").replace(":", "\\:")
                filters.append(f"subtitles='{sub}'")
        return ",".join(filters)

"""Lightweight visual change detection via OpenCV frame sampling."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from app.core.logging import get_logger

logger = get_logger(__name__)


def detect_visual_changes(
    video_path: Path,
    *,
    sample_fps: float = 1.0,
    threshold: float = 18.0,
) -> list[dict[str, Any]]:
    """
    Detect scene/motion spikes by sampling grayscale frames.

    Uses OpenCV when available; otherwise returns an empty list with a warning.
    """
    try:
        import cv2
    except ImportError:
        logger.warning("opencv_not_installed_skipping_visual_detection")
        return []

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return []

    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, int(fps / max(sample_fps, 0.1)))
    prev = None
    events: list[dict[str, Any]] = []
    frame_idx = 0

    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_idx % step != 0:
            frame_idx += 1
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (160, 90))
        timestamp = frame_idx / fps
        if prev is not None:
            diff = float(np.mean(cv2.absdiff(gray, prev)))
            if diff >= threshold:
                events.append(
                    {
                        "start": max(0.0, timestamp - 0.5),
                        "end": timestamp + 0.5,
                        "score": min(1.0, diff / (threshold * 2)),
                        "kind": "visual_change",
                        "diff": diff,
                    }
                )
        prev = gray
        frame_idx += 1

    capture.release()
    logger.info("visual_events_detected", count=len(events), path=str(video_path))
    return events


def extract_scene_boundaries_with_ffmpeg(video_path: Path) -> list[float]:
    """Optional PySceneDetect-free fallback using ffmpeg scene filter metadata."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return []
    with tempfile.TemporaryDirectory() as tmp:
        # Best-effort; ignore failures
        cmd = [
            ffmpeg,
            "-i",
            str(video_path),
            "-filter:v",
            "select='gt(scene,0.4)',showinfo",
            "-f",
            "null",
            "-",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=180)
        times: list[float] = []
        for line in (proc.stderr or "").splitlines():
            if "pts_time:" in line:
                try:
                    part = line.split("pts_time:")[1].split()[0]
                    times.append(float(part))
                except (IndexError, ValueError):
                    continue
        return times

"""Face/person tracking for vertical reframing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class FaceTracker:
    """OpenCV Haar-cascade based subject tracker (CPU-friendly fallback)."""

    def analyze_window(
        self,
        video_path: Path,
        *,
        start_seconds: float,
        end_seconds: float,
        sample_fps: float = 4.0,
        target_aspect: str = "9:16",
    ) -> dict[str, Any]:
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("OpenCV is required for face tracking") from exc

        capture = cv2.VideoCapture(str(video_path))
        if not capture.isOpened():
            raise RuntimeError("Unable to open video for face tracking")

        fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        start_frame = int(start_seconds * fps)
        end_frame = int(end_seconds * fps)
        step = max(1, int(fps / max(sample_fps, 0.1)))

        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        detector = cv2.CascadeClassifier(cascade_path)

        centers: list[tuple[float, float]] = []
        capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_idx = start_frame
        while frame_idx <= end_frame:
            ok, frame = capture.read()
            if not ok:
                break
            if (frame_idx - start_frame) % step == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = detector.detectMultiScale(gray, 1.1, 4, minSize=(40, 40))
                if len(faces):
                    # Prefer largest face
                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
                    centers.append(((x + w / 2) / width, (y + h / 2) / height))
            frame_idx += 1
        capture.release()

        if not centers:
            # Center crop fallback
            crop = self._center_crop(target_aspect)
            return {
                "detected_faces": 0,
                "crop_box": crop,
                "zoom": 1.15,
                "method": "center_fallback",
            }

        xs = [c[0] for c in centers]
        ys = [c[1] for c in centers]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)
        crop = self._subject_crop(cx, cy, target_aspect)
        return {
            "detected_faces": len(centers),
            "subject_center": {"x": cx, "y": cy},
            "crop_box": crop,
            "zoom": 1.25,
            "method": "haar_face",
            "samples": len(centers),
        }

    @staticmethod
    def _center_crop(aspect: str) -> dict[str, float]:
        if aspect == "9:16":
            # Assume source is wider; keep full height, crop width
            target = 9 / 16
            # crop width relative to frame assuming 16:9 source (~0.5625 of width)
            w = min(1.0, target / (16 / 9))
            return {"x": (1 - w) / 2, "y": 0.0, "w": w, "h": 1.0}
        if aspect == "1:1":
            return {"x": 0.125, "y": 0.0, "w": 0.75, "h": 1.0}
        return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}

    @staticmethod
    def _subject_crop(cx: float, cy: float, aspect: str) -> dict[str, float]:
        if aspect == "9:16":
            w = 0.45
            h = 1.0
            x = min(max(cx - w / 2, 0.0), 1.0 - w)
            return {"x": x, "y": 0.0, "w": w, "h": h}
        if aspect == "1:1":
            size = 0.7
            x = min(max(cx - size / 2, 0.0), 1.0 - size)
            y = min(max(cy - size / 2, 0.0), 1.0 - size)
            return {"x": x, "y": y, "w": size, "h": size}
        return {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0}

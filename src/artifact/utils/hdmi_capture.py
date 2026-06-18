"""HDMI capture-card access for the second photobooth camera.

The external camera is expected to arrive through a USB HDMI capture card, which
Linux exposes as a UVC `/dev/video*` device. When the CRT video-wall service is
running, that process owns the capture card and publishes a fresh shared JPEG;
the photobooth reads that shared frame instead of opening the device itself.
"""

from __future__ import annotations

import io
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from numpy.typing import NDArray
from PIL import Image

logger = logging.getLogger(__name__)


def _data_dir() -> Path:
    return Path(os.environ.get("ARCADE_DATA_DIR", "/home/kirniy/modular-arcade/data"))


def _default_shared_frame_path() -> Path:
    return _data_dir() / "video_wall" / "hdmi_capture_latest.jpg"


def _default_heartbeat_path() -> Path:
    return _data_dir() / "video_wall" / "heartbeat"


class HDMICaptureService:
    """Read frames from the HDMI capture card or video-wall shared frame."""

    def __init__(self, preview_resolution: Tuple[int, int] = (128, 128)):
        self._preview_resolution = preview_resolution
        self._device = os.environ.get("VNVNC_HDMI_CAPTURE_DEVICE", "/dev/video0")
        self._direct_enabled = os.environ.get(
            "VNVNC_HDMI_CAPTURE_DIRECT_ENABLED", "true"
        ).lower() not in {"0", "false", "no", "off"}
        self._shared_frame_path = Path(
            os.environ.get("VNVNC_HDMI_CAPTURE_SHARED_FRAME", str(_default_shared_frame_path()))
        )
        self._heartbeat_path = Path(
            os.environ.get("VNVNC_VIDEO_WALL_HEARTBEAT", str(_default_heartbeat_path()))
        )
        self._shared_max_age = float(os.environ.get("VNVNC_HDMI_CAPTURE_SHARED_MAX_AGE", "1.5"))
        self._heartbeat_max_age = float(os.environ.get("VNVNC_VIDEO_WALL_HEARTBEAT_MAX_AGE", "2.5"))
        self._lock = threading.Lock()
        self._capture = None
        self._last_open_attempt = 0.0
        self._open_retry_seconds = 2.0

    @property
    def shared_frame_path(self) -> Path:
        return self._shared_frame_path

    @property
    def heartbeat_path(self) -> Path:
        return self._heartbeat_path

    def wall_is_owner(self) -> bool:
        """Return True when the video-wall service is actively owning the card."""
        try:
            age = time.time() - self._heartbeat_path.stat().st_mtime
            return age <= self._heartbeat_max_age
        except OSError:
            return False

    def has_fresh_shared_frame(self) -> bool:
        try:
            age = time.time() - self._shared_frame_path.stat().st_mtime
            return age <= self._shared_max_age
        except OSError:
            return False

    def get_frame(self, timeout: float = 0.0) -> Optional[NDArray[np.uint8]]:
        """Return a 128x128 RGB preview frame for the selected camera UI."""
        deadline = time.time() + max(0.0, timeout)
        while True:
            frame = self._read_shared_frame()
            if frame is not None:
                return self._resize_frame(frame, self._preview_resolution)

            if not self.wall_is_owner():
                frame = self._read_direct_frame()
                if frame is not None:
                    return self._resize_frame(frame, self._preview_resolution)

            if time.time() >= deadline:
                return self._placeholder()
            time.sleep(0.03)

    def capture_jpeg(self, quality: int = 90) -> Optional[bytes]:
        """Capture a JPEG from the HDMI capture source without disturbing the wall."""
        shared = self._read_shared_bytes_if_fresh()
        if shared is not None:
            return shared

        if self.wall_is_owner():
            logger.warning("HDMI capture unavailable: video wall owns the card but shared frame is stale")
            return None

        frame = self._read_direct_frame()
        if frame is None:
            return None
        return self._encode_jpeg(frame, quality=quality)

    def close(self) -> None:
        with self._lock:
            if self._capture is not None:
                try:
                    self._capture.release()
                except Exception:
                    pass
                self._capture = None

    def _read_shared_bytes_if_fresh(self) -> Optional[bytes]:
        if not self.has_fresh_shared_frame():
            return None
        try:
            return self._shared_frame_path.read_bytes()
        except OSError as e:
            logger.debug("Failed to read shared HDMI capture frame bytes: %s", e)
            return None

    def _read_shared_frame(self) -> Optional[NDArray[np.uint8]]:
        shared = self._read_shared_bytes_if_fresh()
        if shared is None:
            return None
        try:
            image = Image.open(io.BytesIO(shared)).convert("RGB")
            return np.array(image, dtype=np.uint8)
        except Exception as e:
            logger.debug("Failed to decode shared HDMI capture frame: %s", e)
            return None

    def _open_direct_capture(self):
        if not self._direct_enabled:
            return None
        now = time.time()
        if now - self._last_open_attempt < self._open_retry_seconds:
            return self._capture
        self._last_open_attempt = now

        try:
            import cv2
        except Exception as e:
            logger.warning("OpenCV unavailable for direct HDMI capture: %s", e)
            self._direct_enabled = False
            return None

        if self._capture is not None:
            return self._capture

        capture = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        if not capture.isOpened():
            logger.warning("Failed to open HDMI capture device: %s", self._device)
            capture.release()
            return None

        width = int(os.environ.get("VNVNC_HDMI_CAPTURE_WIDTH", "1280"))
        height = int(os.environ.get("VNVNC_HDMI_CAPTURE_HEIGHT", "720"))
        fps = int(os.environ.get("VNVNC_HDMI_CAPTURE_FPS", "30"))
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        capture.set(cv2.CAP_PROP_FPS, fps)
        self._capture = capture
        logger.info("Opened HDMI capture device %s at %sx%s@%s", self._device, width, height, fps)
        return self._capture

    def _read_direct_frame(self) -> Optional[NDArray[np.uint8]]:
        with self._lock:
            capture = self._open_direct_capture()
            if capture is None:
                return None
            try:
                import cv2

                ok, frame_bgr = capture.read()
                if not ok or frame_bgr is None:
                    return None
                return cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            except Exception as e:
                logger.debug("Direct HDMI capture frame read failed: %s", e)
                return None

    def _resize_frame(self, frame: NDArray[np.uint8], size: Tuple[int, int]) -> NDArray[np.uint8]:
        target_w, target_h = size
        h, w = frame.shape[:2]
        if w == target_w and h == target_h:
            return frame.copy()

        scale = max(target_w / max(1, w), target_h / max(1, h))
        new_w = max(target_w, int(w * scale))
        new_h = max(target_h, int(h * scale))
        image = Image.fromarray(frame)
        image = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
        crop_x = (new_w - target_w) // 2
        crop_y = (new_h - target_h) // 2
        image = image.crop((crop_x, crop_y, crop_x + target_w, crop_y + target_h))
        return np.array(image, dtype=np.uint8)

    def _encode_jpeg(self, frame: NDArray[np.uint8], quality: int) -> Optional[bytes]:
        try:
            image = Image.fromarray(frame)
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=quality)
            return output.getvalue()
        except Exception as e:
            logger.debug("Failed to encode HDMI capture JPEG: %s", e)
            return None

    def _placeholder(self) -> NDArray[np.uint8]:
        w, h = self._preview_resolution
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = (12, 12, 16)
        frame[0:2, :, :] = (255, 224, 23)
        frame[-2:, :, :] = (255, 28, 0)
        frame[:, 0:2, :] = (255, 224, 23)
        frame[:, -2:, :] = (255, 28, 0)
        return frame


hdmi_capture_service = HDMICaptureService()


def get_hdmi_capture_service() -> HDMICaptureService:
    return hdmi_capture_service

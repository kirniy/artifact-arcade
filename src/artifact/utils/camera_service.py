"""Shared Camera Service - Always-on camera for the arcade machine.

The camera runs continuously in a background thread, providing instant
frame access to any mode that needs it. No more startup delays!

Usage:
    from artifact.utils.camera_service import camera_service

    # Get latest frame (instant - no waiting)
    frame = camera_service.get_frame()

    # Get full-res frame for AI analysis
    frame = camera_service.get_full_frame()

    # Capture JPEG for AI/printing
    jpeg = camera_service.capture_jpeg()
"""

import os
import time
import logging
import threading
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Environment detection
IS_HARDWARE = os.getenv("ARTIFACT_ENV") == "hardware"


class CameraService:
    """Singleton camera service that runs continuously.

    Captures frames in background thread at ~15fps, providing instant
    access to the latest frame for any mode that needs it.
    """

    _instance: Optional['CameraService'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'CameraService':
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True

        # Camera state
        self._camera = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._camera_lock = threading.Lock()

        # Frame buffers (protected by lock)
        self._frame_lock = threading.Lock()
        self._latest_frame: Optional[NDArray[np.uint8]] = None
        self._latest_full_frame: Optional[NDArray[np.uint8]] = None
        self._frame_time: float = 0
        self._full_frame_time: float = 0
        self._frame_count: int = 0

        # Resolution settings
        self._preview_resolution = (128, 128)  # For display
        self._full_resolution = (640, 480)     # For AI/printing

        # Performance tracking
        self._fps: float = 0
        self._last_fps_time: float = 0
        self._fps_frame_count: int = 0

        logger.info("CameraService initialized")

    @property
    def is_running(self) -> bool:
        """Check if camera service is running."""
        return self._running

    @property
    def has_camera(self) -> bool:
        """Check if a real camera is available."""
        return self._camera is not None and hasattr(self._camera, '_use_opencv') and self._camera._use_opencv

    @property
    def fps(self) -> float:
        """Get current capture FPS."""
        return self._fps

    def start(self) -> bool:
        """Start the camera service.

        Should be called once at application startup.
        Returns True if camera opened successfully.
        """
        if self._running:
            logger.warning("CameraService already running")
            return True

        # Create camera
        try:
            if IS_HARDWARE:
                from artifact.hardware.camera import create_camera, is_pi_camera_available
                if is_pi_camera_available():
                    self._camera = create_camera(preview_resolution=self._preview_resolution)
                else:
                    logger.warning("Pi camera not available")
                    return False
            else:
                from artifact.simulator.mock_hardware.camera import create_camera
                self._camera = create_camera(resolution=self._full_resolution)

            if not self._camera.open():
                logger.error("Failed to open camera")
                return False

        except Exception as e:
            logger.error(f"Failed to create camera: {e}")
            return False

        # Start capture thread
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

        logger.info("CameraService started")
        return True

    def stop(self) -> None:
        """Stop the camera service.

        Should be called at application shutdown.
        """
        if not self._running:
            return

        self._running = False

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        if self._camera:
            try:
                self._camera.close()
            except:
                pass
            self._camera = None

        logger.info("CameraService stopped")

    def _capture_loop(self) -> None:
        """Background capture loop - runs at ~15fps."""
        target_interval = 1.0 / 15  # 15 fps target

        while self._running:
            start_time = time.time()

            try:
                if self._camera and self._camera.is_open:
                    with self._camera_lock:
                        frame = self._camera.capture_frame()

                    if frame is not None:
                        # Create preview-sized version
                        preview = self._resize_frame(frame, self._preview_resolution)

                        with self._frame_lock:
                            self._latest_frame = preview
                            self._frame_time = time.time()
                            self._frame_count += 1

                        # Update FPS
                        self._fps_frame_count += 1
                        now = time.time()
                        if now - self._last_fps_time >= 1.0:
                            self._fps = self._fps_frame_count / (now - self._last_fps_time)
                            self._fps_frame_count = 0
                            self._last_fps_time = now

            except Exception as e:
                logger.debug(f"Capture error: {e}")

            # Sleep to maintain target framerate
            elapsed = time.time() - start_time
            sleep_time = target_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _resize_frame(self, frame: NDArray[np.uint8],
                      size: Tuple[int, int]) -> NDArray[np.uint8]:
        """Resize frame using crop-to-fill (no black bars)."""
        target_w, target_h = size
        h, w = frame.shape[:2]

        if w == target_w and h == target_h:
            return frame

        try:
            import cv2
            # Calculate scale to fill (may crop)
            scale = max(target_w / w, target_h / h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            # Resize
            resized = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Crop center
            crop_x = (new_w - target_w) // 2
            crop_y = (new_h - target_h) // 2
            return resized[crop_y:crop_y+target_h, crop_x:crop_x+target_w]

        except ImportError:
            # Fallback: simple nearest-neighbor resize
            result = np.zeros((target_h, target_w, 3), dtype=np.uint8)
            for y in range(target_h):
                for x in range(target_w):
                    src_x = int(x * w / target_w)
                    src_y = int(y * h / target_h)
                    result[y, x] = frame[src_y, src_x]
            return result

    def get_frame(self, timeout: float = 0.1) -> Optional[NDArray[np.uint8]]:
        """Get latest preview frame (128x128).

        Returns instantly if frame available, otherwise waits up to timeout.

        Args:
            timeout: Max time to wait for frame (seconds)

        Returns:
            RGB image (128, 128, 3) or None if no camera
        """
        with self._frame_lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()

        # No frame yet - wait briefly
        if timeout > 0:
            deadline = time.time() + timeout
            while time.time() < deadline:
                with self._frame_lock:
                    if self._latest_frame is not None:
                        return self._latest_frame.copy()
                time.sleep(0.01)

        # Return placeholder
        return self._generate_placeholder()

    def get_full_frame(self) -> Optional[NDArray[np.uint8]]:
        """Get latest full-resolution frame (640x480).

        Use this for AI analysis, face detection, etc.

        Returns:
            RGB image (480, 640, 3) or None if no camera
        """
        now = time.time()
        with self._frame_lock:
            if self._latest_full_frame is not None and (now - self._full_frame_time) < 0.5:
                return self._latest_full_frame.copy()

        if not self._camera or not self._camera.is_open:
            return None

        try:
            with self._camera_lock:
                if hasattr(self._camera, "capture_full"):
                    frame = self._camera.capture_full()
                else:
                    frame = self._camera.capture_frame()
            if frame is None:
                return None
            with self._frame_lock:
                self._latest_full_frame = frame
                self._full_frame_time = time.time()
            return frame.copy()
        except Exception as e:
            logger.debug(f"Full frame capture error: {e}")
            return None

    def capture_jpeg(self, quality: int = 85) -> Optional[bytes]:
        """Capture full-res frame as JPEG.

        Use this for AI API calls and printing.

        Args:
            quality: JPEG quality (1-100)

        Returns:
            JPEG bytes or None
        """
        if not self._camera or not self._camera.is_open:
            return None

        try:
            with self._camera_lock:
                if hasattr(self._camera, "capture_jpeg"):
                    jpeg = self._camera.capture_jpeg(quality=quality)
                else:
                    jpeg = None
            if jpeg is not None:
                return jpeg
        except Exception as e:
            logger.debug(f"JPEG capture error: {e}")

        frame = self.get_full_frame()
        if frame is None:
            return None
        try:
            import cv2
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', frame_bgr,
                                     [cv2.IMWRITE_JPEG_QUALITY, quality])
            return buffer.tobytes()
        except ImportError:
            try:
                from PIL import Image
                import io
                img = Image.fromarray(frame)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                return buffer.getvalue()
            except:
                return None

    def get_motion_x(self) -> float:
        """Get horizontal motion position (0.0-1.0).

        Uses column intensity to estimate where the subject is.
        Useful for paddle-style games.

        Returns:
            Normalized X position (0=left, 1=right)
        """
        with self._frame_lock:
            frame = self._latest_frame

        if frame is None:
            return 0.5

        # Convert to grayscale
        gray = np.mean(frame, axis=2)

        # Column intensity
        col_intensity = np.mean(gray, axis=0)

        # Weighted centroid
        total = np.sum(col_intensity) + 1e-6
        positions = np.arange(len(col_intensity))
        centroid = np.sum(positions * col_intensity) / total

        # Normalize and flip for natural control
        return 1.0 - (centroid / len(col_intensity))

    def _generate_placeholder(self) -> NDArray[np.uint8]:
        """Generate placeholder frame when no camera."""
        import math

        w, h = self._preview_resolution
        frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Purple gradient
        for y in range(h):
            factor = y / h
            frame[y, :, 0] = int(60 + 40 * factor)
            frame[y, :, 1] = int(40 + 30 * factor)
            frame[y, :, 2] = int(100 + 50 * factor)

        # Face outline
        cx, cy = w // 2, h // 2
        r = min(w, h) // 4

        for angle in range(360):
            rad = math.radians(angle)
            x = int(cx + r * math.cos(rad))
            y = int(cy + r * math.sin(rad))
            if 0 <= x < w and 0 <= y < h:
                frame[y, x] = [200, 200, 200]

        return frame


# Global singleton instance
camera_service = CameraService()


def get_camera_service() -> CameraService:
    """Get the global camera service instance."""
    return camera_service

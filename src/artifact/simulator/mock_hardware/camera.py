"""Camera implementation for simulator.

Uses OpenCV to access Mac's webcam for real photos.
Falls back to placeholder images if camera unavailable.
"""

import logging
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class SimulatorCamera:
    """Camera that uses Mac's webcam via OpenCV.

    Falls back to placeholder if webcam unavailable.
    """

    def __init__(
        self,
        resolution: Tuple[int, int] = (640, 480),
        device_id: int = 0
    ):
        """Initialize camera.

        Args:
            resolution: Camera resolution (width, height)
            device_id: Camera device ID (0 = default webcam)
        """
        self._width, self._height = resolution
        self._device_id = device_id
        self._cap = None
        self._is_open = False
        self._use_opencv = False

        logger.info(f"SimulatorCamera created: {self._width}x{self._height}")

    @property
    def resolution(self) -> Tuple[int, int]:
        """Get camera resolution."""
        return (self._width, self._height)

    @property
    def is_open(self) -> bool:
        """Check if camera is open."""
        return self._is_open

    def open(self) -> bool:
        """Open the camera (tries OpenCV webcam first)."""
        try:
            import cv2
            self._cap = cv2.VideoCapture(self._device_id)

            if self._cap.isOpened():
                # Set resolution
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
                self._use_opencv = True
                self._is_open = True
                logger.info("Webcam opened successfully via OpenCV")
                return True
            else:
                logger.warning("Could not open webcam, using placeholder")
                self._cap = None

        except ImportError:
            logger.warning("OpenCV not available, using placeholder camera")
        except Exception as e:
            logger.warning(f"Failed to open webcam: {e}, using placeholder")

        # Fallback to placeholder mode
        self._use_opencv = False
        self._is_open = True
        logger.info("Camera opened in placeholder mode")
        return True

    def close(self) -> None:
        """Close the camera."""
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        self._is_open = False
        self._use_opencv = False
        logger.info("Camera closed")

    def capture_frame(self) -> Optional[NDArray[np.uint8]]:
        """Capture a single frame from webcam.

        Returns:
            RGB image array (height, width, 3) or None
        """
        if not self._is_open:
            logger.warning("Camera not open")
            return None

        if self._use_opencv and self._cap is not None:
            try:
                import cv2
                ret, frame = self._cap.read()
                if ret:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    # Resize if needed
                    if frame_rgb.shape[1] != self._width or frame_rgb.shape[0] != self._height:
                        frame_rgb = cv2.resize(frame_rgb, (self._width, self._height))
                    return frame_rgb
            except Exception as e:
                logger.error(f"Failed to capture frame: {e}")

        # Return placeholder
        return self._generate_placeholder()

    def capture_jpeg(self, quality: int = 85) -> Optional[bytes]:
        """Capture frame and encode as JPEG.

        Args:
            quality: JPEG quality (1-100)

        Returns:
            JPEG bytes or None
        """
        frame = self.capture_frame()
        if frame is None:
            return None

        try:
            import cv2
            # Convert RGB to BGR for OpenCV
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, quality])
            return buffer.tobytes()

        except ImportError:
            # Try PIL as fallback
            try:
                from PIL import Image
                import io

                img = Image.fromarray(frame)
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                return buffer.getvalue()
            except ImportError:
                logger.error("Neither OpenCV nor PIL available for JPEG encoding")
                return None
        except Exception as e:
            logger.error(f"Failed to encode JPEG: {e}")
            return None

    def _generate_placeholder(self) -> NDArray[np.uint8]:
        """Generate a placeholder image with face outline."""
        import math

        # Create gradient background
        frame = np.zeros((self._height, self._width, 3), dtype=np.uint8)

        # Purple gradient
        for y in range(self._height):
            factor = y / self._height
            frame[y, :, 0] = int(60 + 40 * factor)   # R
            frame[y, :, 1] = int(40 + 30 * factor)   # G
            frame[y, :, 2] = int(100 + 50 * factor)  # B

        # Draw face outline
        cx, cy = self._width // 2, self._height // 2
        face_radius = min(self._width, self._height) // 4

        # Draw circle for face
        for angle in range(360):
            rad = math.radians(angle)
            x = int(cx + face_radius * math.cos(rad))
            y = int(cy + face_radius * math.sin(rad))
            if 0 <= x < self._width and 0 <= y < self._height:
                frame[y, x] = [200, 200, 200]

        # Draw eyes
        eye_y = cy - face_radius // 3
        for eye_x in [cx - face_radius // 3, cx + face_radius // 3]:
            for dy in range(-5, 6):
                for dx in range(-5, 6):
                    if dx*dx + dy*dy <= 25:
                        y, x = eye_y + dy, eye_x + dx
                        if 0 <= x < self._width and 0 <= y < self._height:
                            frame[y, x] = [255, 255, 255]

        # Draw smile
        smile_y = cy + face_radius // 4
        for angle in range(200, 341):
            rad = math.radians(angle)
            x = int(cx + face_radius // 2 * math.cos(rad))
            y = int(smile_y + face_radius // 4 * math.sin(rad))
            if 0 <= x < self._width and 0 <= y < self._height:
                frame[y, x] = [200, 200, 200]

        # Add text "НЕТ КАМЕРЫ" (NO CAMERA)
        text_y = self._height - 40
        # Simple pattern for "NO CAM"
        pattern = [
            "# # ###  #   ###  #  # #",
            "## # #   #  # # # ## # #",
            "# ## ### #  ##### # ## #",
            "#  # #   #  # # # #  #  ",
            "#  # ### ## # # # #  # #",
        ]
        start_x = (self._width - len(pattern[0]) * 3) // 2
        for row_idx, row in enumerate(pattern):
            for col_idx, char in enumerate(row):
                if char == '#':
                    x = start_x + col_idx * 3
                    y = text_y + row_idx * 3
                    if 0 <= x < self._width - 2 and 0 <= y < self._height - 2:
                        frame[y:y+2, x:x+2] = [255, 200, 100]

        return frame

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


def create_camera(
    resolution: Tuple[int, int] = (640, 480),
    device_id: int = 0
) -> SimulatorCamera:
    """Create a camera instance.

    Args:
        resolution: Camera resolution
        device_id: Webcam device ID

    Returns:
        SimulatorCamera instance
    """
    return SimulatorCamera(resolution, device_id)

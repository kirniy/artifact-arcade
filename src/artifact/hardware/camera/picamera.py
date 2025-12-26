"""Pi Camera Module 3 driver using picamera2.

Uses the Raspberry Pi Camera Module 3 NoIR via picamera2 library.
Provides real-time camera capture for the ARTIFACT arcade machine.
"""

import logging
from typing import Optional, Tuple
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)

# Try to import picamera2
_picamera2 = None
_PICAMERA2_AVAILABLE = False

try:
    from picamera2 import Picamera2
    _picamera2 = Picamera2
    _PICAMERA2_AVAILABLE = True
    logger.info("picamera2 library available")
except ImportError:
    logger.warning("picamera2 not available - Pi camera won't work")


class PiCamera:
    """Raspberry Pi Camera Module 3 driver.

    Uses picamera2 for camera access. Provides live preview frames
    and high-resolution capture for the AI modes.

    Usage:
        camera = PiCamera(resolution=(640, 480))
        camera.open()

        # Get live frame
        frame = camera.capture_frame()  # Returns RGB numpy array

        # Get JPEG for AI processing
        jpeg_bytes = camera.capture_jpeg(quality=85)

        camera.close()
    """

    def __init__(
        self,
        resolution: Tuple[int, int] = (640, 480),
        preview_resolution: Tuple[int, int] = (128, 128)
    ):
        """Initialize camera.

        Args:
            resolution: Full capture resolution (width, height)
            preview_resolution: Preview/live frame resolution
        """
        self._width, self._height = resolution
        self._preview_width, self._preview_height = preview_resolution
        self._camera = None
        self._is_open = False
        self._is_streaming = False

        logger.info(f"PiCamera created: capture={self._width}x{self._height}, "
                   f"preview={self._preview_width}x{self._preview_height}")

    @property
    def resolution(self) -> Tuple[int, int]:
        """Get camera resolution."""
        return (self._width, self._height)

    @property
    def is_open(self) -> bool:
        """Check if camera is open."""
        return self._is_open

    def open(self) -> bool:
        """Open and configure the camera.

        Returns:
            True if camera opened successfully
        """
        if not _PICAMERA2_AVAILABLE:
            logger.error("picamera2 not available - cannot open camera")
            self._is_open = True  # Return placeholder mode
            return True

        if self._is_open:
            return True

        try:
            self._camera = _picamera2()

            # Configure camera
            # Use main stream for full resolution capture (RGB888)
            # Use lores stream for preview (must be YUV420, we convert to RGB later)
            config = self._camera.create_still_configuration(
                main={"size": (self._width, self._height), "format": "RGB888"},
                lores={"size": (self._preview_width, self._preview_height), "format": "YUV420"},
                display="lores"
            )
            self._camera.configure(config)

            # Start camera
            self._camera.start()
            self._is_streaming = True
            self._is_open = True

            logger.info("Pi Camera opened successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to open Pi Camera: {e}")
            self._camera = None
            self._is_open = True  # Fallback to placeholder mode
            return True

    def close(self) -> None:
        """Close the camera."""
        if self._camera is not None:
            try:
                if self._is_streaming:
                    self._camera.stop()
                self._camera.close()
            except Exception as e:
                logger.warning(f"Error closing camera: {e}")
            self._camera = None

        self._is_open = False
        self._is_streaming = False
        logger.info("Pi Camera closed")

    def capture_frame(self) -> Optional[NDArray[np.uint8]]:
        """Capture a single preview frame.

        Returns:
            RGB image array (preview_height, preview_width, 3) or None
        """
        if not self._is_open:
            logger.warning("Camera not open")
            return None

        if self._camera is not None and self._is_streaming:
            try:
                # Get the lores (preview) array - it's YUV420
                yuv_frame = self._camera.capture_array("lores")

                # Convert YUV420 to RGB
                # YUV420 has Y plane at full resolution, then U and V at half resolution
                # We'll just use the Y (luminance) channel for grayscale preview
                # This is much simpler and works well for silhouette display
                h, w = self._preview_height, self._preview_width

                # YUV420 layout: Y plane is first h*w bytes
                # Just extract Y channel and make grayscale RGB
                y_plane = yuv_frame[:h, :w]

                # Convert grayscale to RGB
                frame = np.stack([y_plane, y_plane, y_plane], axis=-1)
                return frame

            except Exception as e:
                logger.error(f"Failed to capture frame: {e}")

        # Return placeholder
        return self._generate_placeholder(self._preview_width, self._preview_height)

    def capture_full(self) -> Optional[NDArray[np.uint8]]:
        """Capture a full resolution frame.

        Returns:
            RGB image array (height, width, 3) or None
        """
        if not self._is_open:
            logger.warning("Camera not open")
            return None

        if self._camera is not None and self._is_streaming:
            try:
                # Get the main (full resolution) array
                frame = self._camera.capture_array("main")
                return frame
            except Exception as e:
                logger.error(f"Failed to capture full frame: {e}")

        # Return placeholder
        return self._generate_placeholder(self._width, self._height)

    def capture_jpeg(self, quality: int = 85) -> Optional[bytes]:
        """Capture frame and encode as JPEG.

        Args:
            quality: JPEG quality (1-100)

        Returns:
            JPEG bytes or None
        """
        frame = self.capture_full()
        if frame is None:
            return None

        try:
            # Try using PIL for JPEG encoding
            from PIL import Image
            import io

            img = Image.fromarray(frame)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=quality)
            return buffer.getvalue()

        except ImportError:
            logger.error("PIL not available for JPEG encoding")
            return None
        except Exception as e:
            logger.error(f"Failed to encode JPEG: {e}")
            return None

    def _generate_placeholder(self, width: int, height: int) -> NDArray[np.uint8]:
        """Generate a placeholder image when camera unavailable."""
        import math

        # Create gradient background
        frame = np.zeros((height, width, 3), dtype=np.uint8)

        # Purple gradient
        for y in range(height):
            factor = y / height
            frame[y, :, 0] = int(60 + 40 * factor)   # R
            frame[y, :, 1] = int(40 + 30 * factor)   # G
            frame[y, :, 2] = int(100 + 50 * factor)  # B

        # Draw face outline
        cx, cy = width // 2, height // 2
        face_radius = min(width, height) // 4

        # Draw circle for face
        for angle in range(360):
            rad = math.radians(angle)
            x = int(cx + face_radius * math.cos(rad))
            y = int(cy + face_radius * math.sin(rad))
            if 0 <= x < width and 0 <= y < height:
                frame[y, x] = [200, 200, 200]

        # Draw eyes
        eye_y = cy - face_radius // 3
        for eye_x in [cx - face_radius // 3, cx + face_radius // 3]:
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    if dx*dx + dy*dy <= 9:
                        y, x = eye_y + dy, eye_x + dx
                        if 0 <= x < width and 0 <= y < height:
                            frame[y, x] = [255, 255, 255]

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
    preview_resolution: Tuple[int, int] = (128, 128)
) -> PiCamera:
    """Create a Pi camera instance.

    Args:
        resolution: Full capture resolution
        preview_resolution: Preview frame resolution

    Returns:
        PiCamera instance
    """
    return PiCamera(resolution, preview_resolution)


def is_pi_camera_available() -> bool:
    """Check if Pi camera is available."""
    return _PICAMERA2_AVAILABLE

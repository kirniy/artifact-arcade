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
        """Open the camera (tries OpenCV webcam first).

        On macOS: Make sure Terminal/IDE has Camera permission in
        System Settings > Privacy & Security > Camera
        """
        try:
            import cv2
            import time

            logger.info(f"Attempting to open camera device {self._device_id}...")

            # Try to open camera - macOS may prompt for permission
            self._cap = cv2.VideoCapture(self._device_id)

            # Give macOS time to show permission dialog and user to respond
            # The first open attempt may trigger the dialog
            time.sleep(0.5)

            # Try reading a frame to verify camera actually works
            if self._cap.isOpened():
                ret, test_frame = self._cap.read()
                if ret and test_frame is not None:
                    # Set resolution
                    self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
                    self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
                    self._use_opencv = True
                    self._is_open = True
                    logger.info("✓ Webcam opened successfully via OpenCV")
                    return True
                else:
                    logger.warning("Camera opened but cannot read frames - permission may be denied")
                    logger.warning("On macOS: Go to System Settings > Privacy & Security > Camera")
                    logger.warning("and enable camera access for Terminal or your IDE")
                    self._cap.release()
                    self._cap = None
            else:
                logger.warning("Could not open webcam - camera may be in use or permission denied")

        except ImportError:
            logger.warning("OpenCV not available, using placeholder camera")
        except Exception as e:
            logger.warning(f"Failed to open webcam: {e}, using placeholder")

        # Fallback to placeholder mode
        self._use_opencv = False
        self._is_open = True
        logger.info("Camera opened in placeholder mode (no live webcam)")
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


def floyd_steinberg_dither(
    frame: NDArray[np.uint8],
    target_size: Tuple[int, int] = (128, 128),
    threshold: int = 128
) -> NDArray[np.uint8]:
    """Apply Floyd-Steinberg dithering to create a pixel art style preview.

    Perfect for the 128x128 main display - creates a stylized silhouette
    effect that looks great on LED matrices.

    Args:
        frame: Input RGB image (height, width, 3)
        target_size: Output size (width, height)
        threshold: B/W threshold (0-255)

    Returns:
        Dithered RGB image sized for display
    """
    import cv2

    # Resize to target
    resized = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

    # Convert to grayscale
    gray = cv2.cvtColor(resized, cv2.COLOR_RGB2GRAY).astype(np.float32)

    height, width = gray.shape

    # Floyd-Steinberg dithering
    for y in range(height):
        for x in range(width):
            old_pixel = gray[y, x]
            new_pixel = 255.0 if old_pixel > threshold else 0.0
            gray[y, x] = new_pixel
            error = old_pixel - new_pixel

            # Distribute error to neighbors
            if x + 1 < width:
                gray[y, x + 1] += error * 7 / 16
            if y + 1 < height:
                if x > 0:
                    gray[y + 1, x - 1] += error * 3 / 16
                gray[y + 1, x] += error * 5 / 16
                if x + 1 < width:
                    gray[y + 1, x + 1] += error * 1 / 16

    # Convert back to RGB with a cool color scheme
    output = np.zeros((height, width, 3), dtype=np.uint8)
    mask = gray > threshold

    # Foreground color (person silhouette) - cyan/teal
    output[mask, 0] = 100  # R
    output[mask, 1] = 200  # G
    output[mask, 2] = 220  # B

    # Background stays black for cool contrast

    return output


def create_viewfinder_overlay(
    dithered: NDArray[np.uint8],
    time_ms: float = 0
) -> NDArray[np.uint8]:
    """Add viewfinder overlay effects to dithered image.

    Adds scan lines, corner brackets, and center crosshair
    for that authentic camera viewfinder feel.

    Args:
        dithered: Dithered image (128x128)
        time_ms: Current time for animations

    Returns:
        Image with viewfinder overlay
    """
    output = dithered.copy()
    h, w = output.shape[:2]

    # Scan line effect (subtle)
    scan_y = int((time_ms / 50) % h)
    output[scan_y, :] = np.clip(output[scan_y, :].astype(np.int16) + 30, 0, 255).astype(np.uint8)

    # Corner brackets (viewfinder style)
    bracket_size = 15
    bracket_color = (150, 200, 255)  # Light blue

    # Top-left
    output[2:2+bracket_size, 2:4] = bracket_color
    output[2:4, 2:2+bracket_size] = bracket_color

    # Top-right
    output[2:2+bracket_size, w-4:w-2] = bracket_color
    output[2:4, w-2-bracket_size:w-2] = bracket_color

    # Bottom-left
    output[h-2-bracket_size:h-2, 2:4] = bracket_color
    output[h-4:h-2, 2:2+bracket_size] = bracket_color

    # Bottom-right
    output[h-2-bracket_size:h-2, w-4:w-2] = bracket_color
    output[h-4:h-2, w-2-bracket_size:w-2] = bracket_color

    # Center crosshair (small)
    cx, cy = w // 2, h // 2
    cross_size = 5
    output[cy-cross_size:cy+cross_size, cx-1:cx+1] = bracket_color
    output[cy-1:cy+1, cx-cross_size:cx+cross_size] = bracket_color

    return output

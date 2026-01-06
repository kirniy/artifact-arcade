"""
HDMI Display driver for NovaStar T50 + DH418 LED panel system.

The T50 receives HDMI input and forwards it to the DH418 receiver card,
which drives the HUB75E LED panels. From the Pi's perspective, we just
output standard video via HDMI - the T50/DH418 handle all panel driving.

IMPORTANT: On Raspberry Pi with kmsdrm, we output 720x480 via HDMI.
The T50 is configured to crop the top-left 128x128 pixels for the LED panels.
This approach works because kmsdrm needs a standard resolution, not 128x128.
"""

import logging
import os
import numpy as np
from numpy.typing import NDArray

from ..base import Display

logger = logging.getLogger(__name__)

# Pygame import is deferred to avoid issues on non-Pi systems
_pygame = None


def _get_pygame():
    """Lazy import pygame - let it auto-detect video driver."""
    global _pygame
    if _pygame is None:
        # NOTE: Do NOT set SDL_VIDEODRIVER=kmsdrm explicitly on Debian Trixie!
        # Let pygame auto-detect the driver - explicit setting breaks initialization.
        import pygame
        _pygame = pygame
    return _pygame


# HDMI output resolution (standard resolution for T50 compatibility)
HDMI_OUTPUT_WIDTH = 720
HDMI_OUTPUT_HEIGHT = 480


class HDMIDisplay(Display):
    """
    HDMI display driver for T50 + DH418 LED matrix system.

    Outputs 720x480 via HDMI with the 128x128 content in the top-left corner.
    The NovaStar T50 is configured to crop the top-left 128x128 pixels,
    which then get sent to the DH418 receiver card driving the LED panels.

    This approach is needed because kmsdrm requires standard video resolutions,
    and 128x128 is not a valid HDMI mode.

    Usage:
        display = HDMIDisplay()
        display.init()

        # Draw something
        display.clear(255, 0, 0)  # Red
        display.show()

        # Or use buffer
        buffer = np.zeros((128, 128, 3), dtype=np.uint8)
        buffer[:, :] = [0, 255, 0]  # Green
        display.set_buffer(buffer)
        display.show()

        # Flip display 180° if mounted upside down
        display = HDMIDisplay(rotate_180=True)
    """

    def __init__(self, width: int = 128, height: int = 128, rotate_180: bool = True):
        self._width = width
        self._height = height
        self._rotate_180 = rotate_180
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self._screen = None
        self._led_surface = None  # The 128x128 surface for LED content
        self._initialized = False

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def init(self) -> bool:
        """
        Initialize the HDMI display.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        try:
            pygame = _get_pygame()

            # Initialize pygame display
            pygame.init()
            pygame.display.init()

            # Set up fullscreen display FIRST - required for kmsdrm driver
            self._screen = pygame.display.set_mode(
                (HDMI_OUTPUT_WIDTH, HDMI_OUTPUT_HEIGHT),
                pygame.FULLSCREEN
            )

            # Hide mouse cursor AFTER set_mode (kmsdrm requirement)
            pygame.mouse.set_visible(False)

            # Create surface for the 128x128 LED content
            self._led_surface = pygame.Surface((self._width, self._height))

            pygame.display.set_caption("ARTIFACT")

            logger.info(f"Video driver: {pygame.display.get_driver()}")

            # Clear to black initially
            self._screen.fill((0, 0, 0))
            pygame.display.flip()

            self._initialized = True
            logger.info(
                f"HDMI display initialized: {HDMI_OUTPUT_WIDTH}x{HDMI_OUTPUT_HEIGHT} "
                f"(LED area: {self._width}x{self._height} in top-left)"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize HDMI display: {e}")
            return False

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        """Set a single pixel color."""
        if 0 <= x < self._width and 0 <= y < self._height:
            self._buffer[y, x] = [r, g, b]

    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        """Set entire display buffer."""
        if buffer.shape == self._buffer.shape:
            np.copyto(self._buffer, buffer)
        else:
            # Handle size mismatch
            h = min(buffer.shape[0], self._height)
            w = min(buffer.shape[1], self._width)
            self._buffer[:h, :w] = buffer[:h, :w]

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        """Clear display to specified color."""
        self._buffer[:, :] = [r, g, b]

    _show_count = 0  # Class variable for counting calls

    def show(self) -> None:
        """Update physical display with buffer contents."""
        if not self._initialized or self._screen is None:
            return

        pygame = _get_pygame()
        try:
            pygame.mouse.set_visible(False)
        except Exception:
            pass

        # Convert numpy buffer to pygame surface
        # pygame expects (width, height) but numpy is (height, width)
        surface = pygame.surfarray.make_surface(
            self._buffer.swapaxes(0, 1)
        )

        # Rotate 180° if display is mounted upside down
        if self._rotate_180:
            surface = pygame.transform.rotate(surface, 180)

        # Clear screen to black first
        self._screen.fill((0, 0, 0))

        # Blit LED content to top-left corner (T50 crops this region)
        self._screen.blit(surface, (0, 0))

        # DEBUG: Log every 60 frames (1 second at 60fps)
        HDMIDisplay._show_count += 1
        if HDMIDisplay._show_count % 60 == 0:
            logger.info(f"pygame.display.flip() called (frame {HDMIDisplay._show_count})")

        pygame.display.flip()

    def get_buffer(self) -> NDArray[np.uint8]:
        """Get copy of current display buffer."""
        return self._buffer.copy()

    def cleanup(self) -> None:
        """Clean up pygame resources."""
        if self._initialized:
            pygame = _get_pygame()
            pygame.display.quit()
            pygame.quit()
            self._initialized = False
            logger.info("HDMI display cleaned up")

    def __del__(self):
        self.cleanup()


class HDMIDisplayScaled(HDMIDisplay):
    """
    HDMI display with upscaling for better visibility on standard monitors.

    Use this if T50 doesn't receive 128x128 properly and needs a larger
    resolution. The content is scaled up with nearest-neighbor filtering
    to maintain the pixel-art look.
    """

    def __init__(
        self,
        width: int = 128,
        height: int = 128,
        scale: int = 4,
        rotate_180: bool = True
    ):
        super().__init__(width, height, rotate_180=rotate_180)
        self._scale = scale
        self._output_width = width * scale
        self._output_height = height * scale

    def init(self) -> bool:
        """Initialize with scaled output resolution."""
        if self._initialized:
            return True

        try:
            pygame = _get_pygame()

            pygame.init()
            pygame.display.init()
            pygame.mouse.set_visible(False)

            # Use scaled resolution
            self._screen = pygame.display.set_mode(
                (self._output_width, self._output_height),
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            )

            pygame.display.set_caption("ARTIFACT")
            self._screen.fill((0, 0, 0))
            pygame.display.flip()

            self._initialized = True
            logger.info(
                f"HDMI display initialized: {self._width}x{self._height} "
                f"scaled to {self._output_width}x{self._output_height}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize HDMI display: {e}")
            return False

    def show(self) -> None:
        """Update display with scaled buffer."""
        if not self._initialized or self._screen is None:
            return

        pygame = _get_pygame()

        # Create surface from buffer
        surface = pygame.surfarray.make_surface(
            self._buffer.swapaxes(0, 1)
        )

        # Rotate 180° if display is mounted upside down
        if self._rotate_180:
            surface = pygame.transform.rotate(surface, 180)

        # Scale up with nearest-neighbor (preserves pixel-art look)
        scaled = pygame.transform.scale(
            surface,
            (self._output_width, self._output_height)
        )

        self._screen.blit(scaled, (0, 0))
        pygame.display.flip()

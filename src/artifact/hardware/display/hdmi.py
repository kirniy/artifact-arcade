"""
HDMI Display driver for NovaStar T50 + DH418 LED panel system.

The T50 receives HDMI input and forwards it to the DH418 receiver card,
which drives the HUB75E LED panels. From the Pi's perspective, we just
output standard video via HDMI - the T50/DH418 handle all panel driving.

This driver uses pygame to render to the HDMI output at 128x128 resolution.
"""

import logging
import numpy as np
from numpy.typing import NDArray

from ..base import Display

logger = logging.getLogger(__name__)

# Pygame import is deferred to avoid issues on non-Pi systems
_pygame = None


def _get_pygame():
    """Lazy import pygame."""
    global _pygame
    if _pygame is None:
        import pygame
        _pygame = pygame
    return _pygame


class HDMIDisplay(Display):
    """
    HDMI display driver for T50 + DH418 LED matrix system.

    Outputs 128x128 pixels via HDMI. The NovaStar T50 receives this
    signal and forwards it to the DH418, which drives the panels.

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
    """

    def __init__(self, width: int = 128, height: int = 128):
        self._width = width
        self._height = height
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self._screen = None
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

            # Hide mouse cursor
            pygame.mouse.set_visible(False)

            # Set up fullscreen display at native resolution
            # The T50 will receive whatever we output
            self._screen = pygame.display.set_mode(
                (self._width, self._height),
                pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
            )

            pygame.display.set_caption("ARTIFACT")

            # Clear to black initially
            self._screen.fill((0, 0, 0))
            pygame.display.flip()

            self._initialized = True
            logger.info(f"HDMI display initialized: {self._width}x{self._height}")
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

    def show(self) -> None:
        """Update physical display with buffer contents."""
        if not self._initialized or self._screen is None:
            return

        pygame = _get_pygame()

        # Convert numpy buffer to pygame surface
        # pygame expects (width, height) but numpy is (height, width)
        # Also pygame uses RGB while we store RGB, so just swap axes
        surface = pygame.surfarray.make_surface(
            self._buffer.swapaxes(0, 1)
        )

        # Blit to screen
        self._screen.blit(surface, (0, 0))
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
        scale: int = 4
    ):
        super().__init__(width, height)
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

        # Scale up with nearest-neighbor (preserves pixel-art look)
        scaled = pygame.transform.scale(
            surface,
            (self._output_width, self._output_height)
        )

        self._screen.blit(scaled, (0, 0))
        pygame.display.flip()

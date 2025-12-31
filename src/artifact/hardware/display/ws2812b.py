"""
WS2812B LED strip driver for the ticker display.

Controls 384 WS2812B LEDs arranged as:
- 1x 8x8 matrix (64 LEDs) - LEFT
- 1x 32x8 matrix (256 LEDs) - MIDDLE
- 1x 8x8 matrix (64 LEDs) - RIGHT
Total: 48x8 = 384 LEDs

Physical daisy chain order: 8x8 → 32x8 → 8x8
Each matrix has its own serpentine pattern.

Uses GPIO 21 (not GPIO 18) to avoid conflict with audio PWM.
"""

import logging
import numpy as np
from numpy.typing import NDArray

from ..base import Display

logger = logging.getLogger(__name__)

# Hardware imports are deferred
_rpi_ws281x = None


def _get_rpi_ws281x():
    """Lazy import rpi_ws281x."""
    global _rpi_ws281x
    if _rpi_ws281x is None:
        try:
            import rpi_ws281x
            _rpi_ws281x = rpi_ws281x
        except ImportError:
            logger.warning("rpi_ws281x not available - using mock")
            _rpi_ws281x = None
    return _rpi_ws281x


class WS2812BDisplay(Display):
    """
    WS2812B LED strip driver for 48x8 ticker display.

    Hardware configuration:
    - GPIO Pin: 21 (PWM, avoids audio conflict on GPIO 18)
    - LED Count: 384 (48 columns x 8 rows)
    - LED Type: WS2812B (GRB color order)
    - Brightness: Configurable (default 50%)

    The LEDs are arranged in a serpentine pattern:
    Row 0: LED 0-47 (left to right)
    Row 1: LED 95-48 (right to left)
    Row 2: LED 96-143 (left to right)
    ... and so on

    Usage:
        ticker = WS2812BDisplay()
        ticker.init()

        ticker.clear(255, 0, 0)  # Red
        ticker.show()
    """

    # Hardware configuration
    LED_PIN = 21          # GPIO 21 (not 18, to avoid audio conflict)
    LED_FREQ_HZ = 800000  # 800kHz signal frequency
    LED_DMA = 10          # DMA channel
    LED_INVERT = False    # Don't invert signal
    LED_CHANNEL = 0       # PWM channel

    def __init__(
        self,
        width: int = 48,
        height: int = 8,
        brightness: int = 128,
        gpio_pin: int = 21
    ):
        self._width = width
        self._height = height
        self._led_count = width * height
        self._brightness = brightness
        self._gpio_pin = gpio_pin
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self._strip = None
        self._initialized = False

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def init(self) -> bool:
        """
        Initialize the WS2812B strip.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        rpi_ws281x = _get_rpi_ws281x()
        if rpi_ws281x is None:
            logger.error("rpi_ws281x library not available")
            return False

        try:
            # Create NeoPixel strip
            self._strip = rpi_ws281x.PixelStrip(
                self._led_count,
                self._gpio_pin,
                self.LED_FREQ_HZ,
                self.LED_DMA,
                self.LED_INVERT,
                self._brightness,
                self.LED_CHANNEL
            )

            # Initialize the strip
            self._strip.begin()

            # Try to clear all LEDs - this may fail if hardware not connected
            try:
                for i in range(self._led_count):
                    self._strip.setPixelColor(i, 0)
                self._strip.show()
            except Exception as clear_err:
                logger.warning(f"WS2812B clear failed (hardware not connected?): {clear_err}")
                # Hardware likely not connected - return False
                self._strip = None
                return False

            self._initialized = True
            logger.info(
                f"WS2812B initialized: {self._width}x{self._height} "
                f"({self._led_count} LEDs) on GPIO {self._gpio_pin}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WS2812B: {e}")
            self._strip = None
            return False

    def _xy_to_index(self, x: int, y: int) -> int:
        """
        Convert (x, y) coordinates to LED index.

        Physical layout - SERPENTINE, COLUMN-MAJOR, RIGHT to LEFT:
        - Pixels 0-63: rightmost 8x8 (x=40-47 visually)
        - Pixels 64-319: middle 32x8 (x=8-39 visually)
        - Pixels 320-383: leftmost 8x8 (x=0-7 visually)

        Within each matrix, columns go right to left.
        Even columns (0,2,4...): top to bottom (y=0 at top)
        Odd columns (1,3,5...): bottom to top (y=0 at bottom)
        """
        # Map visual x coordinate to physical matrix and local position
        # Visual: x=0 is LEFT, x=47 is RIGHT
        # Physical: pixels start from RIGHT within each matrix

        if x >= 40:
            # Rightmost 8x8 (pixels 0-63)
            # x=47 -> local_col=0, x=40 -> local_col=7
            local_col = 47 - x
            matrix_offset = 0
        elif x >= 8:
            # Middle 32x8 (pixels 64-319)
            # x=39 -> local_col=0, x=8 -> local_col=31
            local_col = 39 - x
            matrix_offset = 64
        else:
            # Leftmost 8x8 (pixels 320-383)
            # x=7 -> local_col=0, x=0 -> local_col=7
            local_col = 7 - x
            matrix_offset = 320

        # Serpentine: even columns top-to-bottom, odd columns bottom-to-top
        if local_col % 2 == 0:
            # Even column: y=0 is first pixel
            pixel_in_col = y
        else:
            # Odd column: y=7 is first pixel (reversed)
            pixel_in_col = 7 - y

        return matrix_offset + local_col * 8 + pixel_in_col

    def _rgb_to_color(self, r: int, g: int, b: int) -> int:
        """Convert RGB to 24-bit color value (RGB order for this strip)."""
        # This strip uses RGB order (not GRB like standard WS2812B)
        # Cast to int to avoid numpy type issues with C extension
        return (int(r) << 16) | (int(g) << 8) | int(b)

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        """Set a single pixel color."""
        if 0 <= x < self._width and 0 <= y < self._height:
            self._buffer[y, x] = [r, g, b]

    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        """Set entire display buffer."""
        if buffer.shape == self._buffer.shape:
            np.copyto(self._buffer, buffer)
        else:
            h = min(buffer.shape[0], self._height)
            w = min(buffer.shape[1], self._width)
            self._buffer[:h, :w] = buffer[:h, :w]

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        """Clear display to specified color."""
        self._buffer[:, :] = [r, g, b]

    def show(self) -> None:
        """Update physical LEDs with buffer contents."""
        if not self._initialized or self._strip is None:
            return

        try:
            # Transfer buffer to LED strip
            for y in range(self._height):
                for x in range(self._width):
                    idx = self._xy_to_index(x, y)
                    r, g, b = self._buffer[y, x]
                    color = self._rgb_to_color(r, g, b)
                    self._strip.setPixelColor(idx, color)

            # Update physical LEDs
            self._strip.show()
        except Exception as e:
            # Hardware might not be connected - disable further attempts
            logger.warning(f"WS2812B show() failed (hardware not connected?): {e}")
            self._initialized = False
            self._strip = None

    def get_buffer(self) -> NDArray[np.uint8]:
        """Get copy of current display buffer."""
        return self._buffer.copy()

    def set_brightness(self, brightness: int) -> None:
        """
        Set overall brightness (0-255).

        Args:
            brightness: Brightness level (0=off, 255=full)
        """
        self._brightness = max(0, min(255, brightness))
        if self._strip:
            self._strip.setBrightness(self._brightness)

    def cleanup(self) -> None:
        """Clean up and turn off all LEDs."""
        if self._initialized and self._strip:
            try:
                # Turn off all LEDs
                for i in range(self._led_count):
                    self._strip.setPixelColor(i, 0)
                self._strip.show()
                logger.info("WS2812B cleaned up")
            except Exception as e:
                logger.warning(f"WS2812B cleanup failed: {e}")
            finally:
                self._initialized = False
                self._strip = None

    def __del__(self):
        self.cleanup()


class WS2812BDisplayMock(Display):
    """
    Mock WS2812B display for testing without hardware.

    Provides the same interface but just stores values in a buffer.
    """

    def __init__(self, width: int = 48, height: int = 8):
        self._width = width
        self._height = height
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)
        logger.info(f"WS2812B mock initialized: {width}x{height}")

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def init(self) -> bool:
        return True

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < self._width and 0 <= y < self._height:
            self._buffer[y, x] = [r, g, b]

    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        if buffer.shape == self._buffer.shape:
            np.copyto(self._buffer, buffer)

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        self._buffer[:, :] = [r, g, b]

    def show(self) -> None:
        pass  # No-op for mock

    def get_buffer(self) -> NDArray[np.uint8]:
        return self._buffer.copy()

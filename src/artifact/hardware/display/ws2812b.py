"""
WS2812B LED strip driver for the ticker display.

Controls 384 WS2812B LEDs arranged as:
- 1x 32x8 matrix (256 LEDs)
- 2x 8x8 matrices (64 LEDs each)
Total: 48x8 = 384 LEDs

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

            # Clear all LEDs
            for i in range(self._led_count):
                self._strip.setPixelColor(i, 0)
            self._strip.show()

            self._initialized = True
            logger.info(
                f"WS2812B initialized: {self._width}x{self._height} "
                f"({self._led_count} LEDs) on GPIO {self._gpio_pin}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WS2812B: {e}")
            return False

    def _xy_to_index(self, x: int, y: int) -> int:
        """
        Convert (x, y) coordinates to LED index.

        Accounts for serpentine wiring pattern:
        - Even rows: left to right
        - Odd rows: right to left
        """
        if y % 2 == 0:
            # Even row: left to right
            return y * self._width + x
        else:
            # Odd row: right to left (serpentine)
            return y * self._width + (self._width - 1 - x)

    def _rgb_to_color(self, r: int, g: int, b: int) -> int:
        """Convert RGB to 24-bit color value (GRB order for WS2812B)."""
        # WS2812B uses GRB order
        return (g << 16) | (r << 8) | b

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

        # Transfer buffer to LED strip
        for y in range(self._height):
            for x in range(self._width):
                idx = self._xy_to_index(x, y)
                r, g, b = self._buffer[y, x]
                color = self._rgb_to_color(r, g, b)
                self._strip.setPixelColor(idx, color)

        # Update physical LEDs
        self._strip.show()

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
            # Turn off all LEDs
            for i in range(self._led_count):
                self._strip.setPixelColor(i, 0)
            self._strip.show()
            self._initialized = False
            logger.info("WS2812B cleaned up")

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

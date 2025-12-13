"""
Simulated display devices for the simulator.

These classes simulate the LED matrix, ticker, and LCD displays
using pygame surfaces.
"""

import pygame
import numpy as np
from numpy.typing import NDArray

from ...hardware.base import Display, TextDisplay


class SimulatedHUB75(Display):
    """
    Simulates 128x128 P3 LED matrix display.

    Uses a numpy buffer and renders to a pygame surface
    with configurable scaling.
    """

    def __init__(self, width: int = 128, height: int = 128) -> None:
        self._width = width
        self._height = height
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < self._width and 0 <= y < self._height:
            self._buffer[y, x] = [r, g, b]

    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        if buffer.shape == self._buffer.shape:
            np.copyto(self._buffer, buffer)
        else:
            # Resize if needed
            resized = np.zeros_like(self._buffer)
            h = min(buffer.shape[0], self._height)
            w = min(buffer.shape[1], self._width)
            resized[:h, :w] = buffer[:h, :w]
            np.copyto(self._buffer, resized)

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        self._buffer.fill(0)
        if r or g or b:
            self._buffer[:, :] = [r, g, b]

    def show(self) -> None:
        # In simulator, show is handled by render()
        pass

    def get_buffer(self) -> NDArray[np.uint8]:
        return self._buffer.copy()

    def render(self, scale: int = 1) -> pygame.Surface:
        """
        Render buffer to a pygame surface.

        Args:
            scale: Pixel scale factor

        Returns:
            pygame.Surface with rendered display
        """
        if scale == 1:
            # Direct render
            surface = pygame.surfarray.make_surface(
                self._buffer.swapaxes(0, 1)
            )
        else:
            # Scaled render with visible pixels
            size = (self._width * scale, self._height * scale)
            surface = pygame.Surface(size)

            # Draw each pixel as a rectangle
            for y in range(self._height):
                for x in range(self._width):
                    color = tuple(self._buffer[y, x])
                    rect = pygame.Rect(
                        x * scale + 1,
                        y * scale + 1,
                        scale - 1,
                        scale - 1
                    )
                    pygame.draw.rect(surface, color, rect)

        return surface


class SimulatedWS2812B(Display):
    """
    Simulates 48x8 WS2812B LED ticker display.

    The ticker consists of:
    - 8x8 left module
    - 32x8 center module
    - 8x8 right module
    """

    def __init__(self, width: int = 48, height: int = 8) -> None:
        self._width = width
        self._height = height
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        if 0 <= x < self._width and 0 <= y < self._height:
            self._buffer[y, x] = [r, g, b]

    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        if buffer.shape == self._buffer.shape:
            np.copyto(self._buffer, buffer)

    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        self._buffer.fill(0)
        if r or g or b:
            self._buffer[:, :] = [r, g, b]

    def show(self) -> None:
        pass

    def get_buffer(self) -> NDArray[np.uint8]:
        return self._buffer.copy()

    def render(self, scale: int = 4) -> pygame.Surface:
        """Render ticker to pygame surface."""
        size = (self._width * scale, self._height * scale)
        surface = pygame.Surface(size)
        surface.fill((10, 10, 15))  # Dark background

        # Draw each LED as a circle for authentic look
        radius = scale // 2 - 1

        for y in range(self._height):
            for x in range(self._width):
                color = tuple(self._buffer[y, x])
                center = (
                    x * scale + scale // 2,
                    y * scale + scale // 2
                )

                # LED glow effect
                if any(c > 20 for c in color):
                    # Outer glow
                    glow_color = tuple(c // 3 for c in color)
                    pygame.draw.circle(surface, glow_color, center, radius + 2)

                # Main LED
                pygame.draw.circle(surface, color, center, radius)

        # Draw module separators
        sep_color = (40, 40, 50)
        # Left module separator (after 8 LEDs)
        pygame.draw.line(
            surface, sep_color,
            (8 * scale, 0),
            (8 * scale, self._height * scale),
            2
        )
        # Right module separator (before last 8 LEDs)
        pygame.draw.line(
            surface, sep_color,
            (40 * scale, 0),
            (40 * scale, self._height * scale),
            2
        )

        return surface


class SimulatedLCD(TextDisplay):
    """
    Simulates LCD1601 16x1 character display.

    Uses a text buffer that can be rendered to the simulator.
    """

    def __init__(self, cols: int = 16, rows: int = 1) -> None:
        self._cols = cols
        self._rows = rows
        self._text = " " * cols
        self._cursor_col = 0
        self._cursor_row = 0

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    def write(self, text: str, row: int = 0, col: int = 0) -> None:
        """Write text at specified position."""
        if row >= self._rows:
            return

        # Convert to list for easier manipulation
        chars = list(self._text)

        # Write characters
        for i, char in enumerate(text):
            pos = col + i
            if pos < self._cols:
                chars[pos] = char

        self._text = "".join(chars)

    def clear(self) -> None:
        """Clear the display."""
        self._text = " " * self._cols
        self._cursor_col = 0
        self._cursor_row = 0

    def set_cursor(self, col: int, row: int) -> None:
        """Set cursor position."""
        self._cursor_col = max(0, min(col, self._cols - 1))
        self._cursor_row = max(0, min(row, self._rows - 1))

    def get_text(self) -> str:
        """Get current display text."""
        return self._text

    def render(self, font: pygame.font.Font) -> pygame.Surface:
        """Render LCD to pygame surface."""
        # Calculate size based on font
        char_width = font.size("W")[0]
        char_height = font.get_height()

        width = char_width * self._cols + 20
        height = char_height + 10

        surface = pygame.Surface((width, height))
        surface.fill((30, 50, 30))  # LCD green background

        # Render text
        text_surface = font.render(self._text, True, (150, 255, 150))
        surface.blit(text_surface, (10, 5))

        return surface

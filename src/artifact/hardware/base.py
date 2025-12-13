"""
Abstract base classes for hardware interfaces.

These interfaces define the contract that both real hardware drivers
and simulator mock implementations must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable
import numpy as np
from numpy.typing import NDArray


class Display(ABC):
    """Abstract base class for display devices."""

    @property
    @abstractmethod
    def width(self) -> int:
        """Display width in pixels."""
        ...

    @property
    @abstractmethod
    def height(self) -> int:
        """Display height in pixels."""
        ...

    @abstractmethod
    def set_pixel(self, x: int, y: int, r: int, g: int, b: int) -> None:
        """Set a single pixel color."""
        ...

    @abstractmethod
    def set_buffer(self, buffer: NDArray[np.uint8]) -> None:
        """
        Set entire display buffer.

        Args:
            buffer: numpy array of shape (height, width, 3) with RGB values
        """
        ...

    @abstractmethod
    def clear(self, r: int = 0, g: int = 0, b: int = 0) -> None:
        """Clear display to specified color."""
        ...

    @abstractmethod
    def show(self) -> None:
        """Update physical display with buffer contents."""
        ...

    @abstractmethod
    def get_buffer(self) -> NDArray[np.uint8]:
        """Get copy of current display buffer."""
        ...

    def fill_rect(
        self, x: int, y: int, w: int, h: int,
        r: int, g: int, b: int
    ) -> None:
        """Fill a rectangle with color."""
        for py in range(y, min(y + h, self.height)):
            for px in range(x, min(x + w, self.width)):
                self.set_pixel(px, py, r, g, b)


class TextDisplay(ABC):
    """Abstract base class for character-based displays (LCD)."""

    @property
    @abstractmethod
    def cols(self) -> int:
        """Number of character columns."""
        ...

    @property
    @abstractmethod
    def rows(self) -> int:
        """Number of character rows."""
        ...

    @abstractmethod
    def write(self, text: str, row: int = 0, col: int = 0) -> None:
        """Write text at position."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear the display."""
        ...

    @abstractmethod
    def set_cursor(self, col: int, row: int) -> None:
        """Set cursor position."""
        ...


class InputDevice(ABC):
    """Abstract base class for input devices."""

    @abstractmethod
    def is_pressed(self) -> bool:
        """Check if input is currently pressed."""
        ...

    @abstractmethod
    def on_press(self, callback: Callable[[], None]) -> Callable[[], None]:
        """
        Register press callback.

        Returns:
            Function to unregister callback
        """
        ...

    @abstractmethod
    def on_release(self, callback: Callable[[], None]) -> Callable[[], None]:
        """
        Register release callback.

        Returns:
            Function to unregister callback
        """
        ...


class KeypadInput(ABC):
    """Abstract base class for matrix keypad."""

    @abstractmethod
    def get_key(self) -> str | None:
        """Get currently pressed key, or None if no key pressed."""
        ...

    @abstractmethod
    def on_key(self, callback: Callable[[str], None]) -> Callable[[], None]:
        """
        Register key press callback.

        Returns:
            Function to unregister callback
        """
        ...


class Camera(ABC):
    """Abstract base class for camera."""

    @abstractmethod
    async def capture(self) -> bytes:
        """
        Capture a photo.

        Returns:
            JPEG image bytes
        """
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if camera is ready."""
        ...

    @abstractmethod
    def start_preview(self) -> None:
        """Start camera preview (if supported)."""
        ...

    @abstractmethod
    def stop_preview(self) -> None:
        """Stop camera preview."""
        ...


class Printer(ABC):
    """Abstract base class for thermal printer."""

    @abstractmethod
    def print_text(self, text: str, **options: Any) -> None:
        """
        Print text.

        Options may include: bold, underline, align, size
        """
        ...

    @abstractmethod
    def print_image(self, image_data: bytes) -> None:
        """Print image (will be dithered for thermal printing)."""
        ...

    @abstractmethod
    def feed(self, lines: int = 1) -> None:
        """Feed paper by specified lines."""
        ...

    @abstractmethod
    def cut(self) -> None:
        """Cut paper (if cutter available)."""
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if printer is ready."""
        ...


class AudioPlayer(ABC):
    """Abstract base class for audio playback."""

    @abstractmethod
    def play(self, sound_id: str, loop: bool = False) -> int:
        """
        Play a sound.

        Args:
            sound_id: Sound identifier or file path
            loop: Whether to loop the sound

        Returns:
            Channel ID for the playing sound
        """
        ...

    @abstractmethod
    def stop(self, channel: int | None = None) -> None:
        """
        Stop playing sound(s).

        Args:
            channel: Specific channel to stop, or None to stop all
        """
        ...

    @abstractmethod
    def set_volume(self, volume: float, channel: int | None = None) -> None:
        """
        Set volume.

        Args:
            volume: Volume level 0.0 to 1.0
            channel: Specific channel, or None for master volume
        """
        ...

    @abstractmethod
    def is_playing(self, channel: int | None = None) -> bool:
        """Check if sound is playing."""
        ...

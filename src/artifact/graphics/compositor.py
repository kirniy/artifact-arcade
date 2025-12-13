"""Multi-display compositor for synchronized rendering."""

from typing import Optional, Dict, Callable, Any
from dataclasses import dataclass
import time

from artifact.hardware.base import Display, TextDisplay
from artifact.graphics.renderer import Renderer


@dataclass
class DisplayConfig:
    """Configuration for a display in the compositor."""

    name: str
    display: Display
    width: int
    height: int
    role: str  # "main", "ticker", "secondary"


class DisplayCompositor:
    """Coordinates rendering across multiple displays.

    Ensures synchronized updates and manages display-specific content routing.
    """

    def __init__(self, target_fps: int = 60):
        self.renderer = Renderer()
        self.displays: Dict[str, DisplayConfig] = {}
        self.lcd: Optional[TextDisplay] = None
        self.target_fps = target_fps
        self.frame_time = 1.0 / target_fps
        self._last_frame_time = 0.0
        self._frame_count = 0
        self._fps_sample_time = 0.0
        self._current_fps = 0.0

        # Content state
        self._ticker_text = ""
        self._ticker_scroll_offset = 0
        self._ticker_scroll_speed = 2  # pixels per frame
        self._lcd_text = ""

        # Callbacks for each display
        self._render_callbacks: Dict[str, Callable[[], None]] = {}

    def add_display(
        self,
        name: str,
        display: Display,
        width: int,
        height: int,
        role: str = "secondary",
    ) -> None:
        """Add a display to the compositor.

        Args:
            name: Unique identifier for the display
            display: Display hardware instance
            width: Display width in pixels
            height: Display height in pixels
            role: Display role ("main", "ticker", "secondary")
        """
        config = DisplayConfig(
            name=name,
            display=display,
            width=width,
            height=height,
            role=role,
        )
        self.displays[name] = config
        self.renderer.add_target(name, display, width, height)

    def set_lcd(self, display: TextDisplay) -> None:
        """Set the LCD text display."""
        self.lcd = display
        self.renderer.set_lcd(display)

    def set_render_callback(
        self,
        display_name: str,
        callback: Callable[[], None],
    ) -> None:
        """Set a custom render callback for a display.

        The callback is called each frame before rendering.
        """
        self._render_callbacks[display_name] = callback

    # High-level content API
    def set_main_content(
        self,
        draw_func: Callable[[Any], None],
        layer: str = "content",
    ) -> None:
        """Set a drawing function for the main display.

        Args:
            draw_func: Function that receives the layer buffer
            layer: Target layer name
        """
        main_display = self._get_display_by_role("main")
        if main_display:
            layer_obj = self.renderer.get_layer(main_display.name, layer)
            if layer_obj:
                draw_func(layer_obj.buffer)

    def set_ticker_text(self, text: str, scroll: bool = True) -> None:
        """Set scrolling text for the ticker display.

        Args:
            text: Text to display
            scroll: If True, scroll text; if False, static display
        """
        self._ticker_text = text
        if not scroll:
            self._ticker_scroll_offset = 0

    def set_lcd_text(self, text: str) -> None:
        """Set text for the LCD display."""
        self._lcd_text = text[:16]
        self.renderer.set_lcd_text(self._lcd_text)

    def clear_display(self, display_name: str) -> None:
        """Clear all layers on a display."""
        target = self.renderer.get_target(display_name)
        if target:
            for layer in target.layers:
                from artifact.graphics.primitives import clear
                clear(layer.buffer)

    def clear_all(self) -> None:
        """Clear all displays."""
        self.renderer.clear_all()
        if self.lcd:
            self.lcd.clear()

    # Frame rendering
    def render_frame(self, delta_time: float = 0.0) -> None:
        """Render a single frame to all displays.

        Args:
            delta_time: Time since last frame in seconds
        """
        # Update ticker scroll
        self._update_ticker_scroll()

        # Run display-specific callbacks
        for name, callback in self._render_callbacks.items():
            callback()

        # Render all displays
        self.renderer.render_frame()

        self._frame_count += 1

    def update(self) -> float:
        """Update compositor and return delta time.

        Handles frame timing and returns time since last frame.

        Returns:
            Delta time in seconds
        """
        current_time = time.perf_counter()

        if self._last_frame_time == 0:
            self._last_frame_time = current_time
            self._fps_sample_time = current_time
            return 0.0

        delta = current_time - self._last_frame_time
        self._last_frame_time = current_time

        # Update FPS calculation
        if current_time - self._fps_sample_time >= 1.0:
            self._current_fps = self._frame_count / (current_time - self._fps_sample_time)
            self._frame_count = 0
            self._fps_sample_time = current_time

        return delta

    def should_render(self) -> bool:
        """Check if enough time has passed for next frame.

        Returns:
            True if a frame should be rendered
        """
        current_time = time.perf_counter()
        elapsed = current_time - self._last_frame_time
        return elapsed >= self.frame_time

    @property
    def fps(self) -> float:
        """Get current FPS."""
        return self._current_fps

    # Internal methods
    def _get_display_by_role(self, role: str) -> Optional[DisplayConfig]:
        """Find a display by its role."""
        for config in self.displays.values():
            if config.role == role:
                return config
        return None

    def _update_ticker_scroll(self) -> None:
        """Update ticker text scrolling."""
        if not self._ticker_text:
            return

        ticker = self._get_display_by_role("ticker")
        if not ticker:
            return

        target = self.renderer.get_target(ticker.name)
        if not target:
            return

        layer = target.get_layer("content")
        if not layer:
            return

        # Clear and redraw ticker
        from artifact.graphics.primitives import clear, draw_text

        clear(layer.buffer)

        # Calculate text width (rough estimate: 4 pixels per char)
        text_width = len(self._ticker_text) * 4 * 2  # scale=2

        # Draw scrolling text
        x_pos = ticker.width - self._ticker_scroll_offset

        # Draw text at scroll position
        draw_text(
            layer.buffer,
            self._ticker_text,
            x_pos,
            0,
            color=(255, 200, 0),  # Gold color
            scale=1,
        )

        # Update scroll offset
        self._ticker_scroll_offset += self._ticker_scroll_speed

        # Reset when text fully scrolled off
        if self._ticker_scroll_offset > ticker.width + text_width:
            self._ticker_scroll_offset = 0

    # Convenience accessors
    def get_renderer(self) -> Renderer:
        """Get the underlying renderer."""
        return self.renderer

    def get_display_names(self) -> list:
        """Get list of registered display names."""
        return list(self.displays.keys())

    def get_display_info(self, name: str) -> Optional[Dict]:
        """Get information about a display."""
        config = self.displays.get(name)
        if config:
            return {
                "name": config.name,
                "width": config.width,
                "height": config.height,
                "role": config.role,
            }
        return None

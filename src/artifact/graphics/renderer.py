"""Main renderer for ARTIFACT displays."""

from typing import Optional, Callable, List
from dataclasses import dataclass, field
import numpy as np
from numpy.typing import NDArray

from artifact.hardware.base import Display, TextDisplay
from artifact.graphics.primitives import (
    clear, fill, draw_rect, draw_circle, draw_line, draw_text, draw_image
)


@dataclass
class Layer:
    """A renderable layer with its own buffer and properties."""

    name: str
    buffer: NDArray[np.uint8]
    visible: bool = True
    alpha: float = 1.0
    x: int = 0
    y: int = 0
    z_order: int = 0


@dataclass
class RenderTarget:
    """Represents a display target for rendering."""

    name: str
    display: Display
    width: int
    height: int
    buffer: NDArray[np.uint8] = field(init=False)
    layers: List[Layer] = field(default_factory=list)
    dirty: bool = True

    def __post_init__(self):
        self.buffer = np.zeros((self.height, self.width, 3), dtype=np.uint8)

    def add_layer(self, name: str, z_order: int = 0) -> Layer:
        """Create and add a new layer to this target."""
        layer_buffer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        layer = Layer(name=name, buffer=layer_buffer, z_order=z_order)
        self.layers.append(layer)
        self.layers.sort(key=lambda l: l.z_order)
        return layer

    def get_layer(self, name: str) -> Optional[Layer]:
        """Get a layer by name."""
        for layer in self.layers:
            if layer.name == name:
                return layer
        return None

    def remove_layer(self, name: str) -> bool:
        """Remove a layer by name."""
        for i, layer in enumerate(self.layers):
            if layer.name == name:
                self.layers.pop(i)
                return True
        return False

    def composite(self) -> NDArray[np.uint8]:
        """Composite all layers into the final buffer."""
        clear(self.buffer)

        for layer in self.layers:
            if not layer.visible:
                continue

            # Get the region of the layer that overlaps with buffer
            lh, lw = layer.buffer.shape[:2]

            # Source coordinates in layer buffer
            src_x1 = max(0, -layer.x)
            src_y1 = max(0, -layer.y)
            src_x2 = min(lw, self.width - layer.x)
            src_y2 = min(lh, self.height - layer.y)

            # Destination coordinates in main buffer
            dst_x1 = max(0, layer.x)
            dst_y1 = max(0, layer.y)
            dst_x2 = dst_x1 + (src_x2 - src_x1)
            dst_y2 = dst_y1 + (src_y2 - src_y1)

            if src_x2 <= src_x1 or src_y2 <= src_y1:
                continue

            src_region = layer.buffer[src_y1:src_y2, src_x1:src_x2]
            dst_region = self.buffer[dst_y1:dst_y2, dst_x1:dst_x2]

            if layer.alpha >= 1.0:
                # Only copy non-black pixels (simple transparency)
                mask = np.any(src_region > 0, axis=2)
                dst_region[mask] = src_region[mask]
            else:
                # Alpha blending
                mask = np.any(src_region > 0, axis=2)
                dst_region[mask] = (
                    src_region[mask] * layer.alpha +
                    dst_region[mask] * (1 - layer.alpha)
                ).astype(np.uint8)

        return self.buffer


class Renderer:
    """Main rendering pipeline for ARTIFACT.

    Manages multiple render targets (displays) and provides a unified
    drawing interface with layer support.
    """

    def __init__(self):
        self.targets: dict[str, RenderTarget] = {}
        self._lcd_display: Optional[TextDisplay] = None
        self._lcd_text: str = ""
        self._frame_callbacks: List[Callable[[], None]] = []

    def add_target(
        self,
        name: str,
        display: Display,
        width: int,
        height: int,
    ) -> RenderTarget:
        """Register a display as a render target.

        Args:
            name: Unique identifier for this target
            display: The Display instance to render to
            width: Display width in pixels
            height: Display height in pixels

        Returns:
            The created RenderTarget
        """
        target = RenderTarget(
            name=name,
            display=display,
            width=width,
            height=height,
        )
        # Create default background layer
        target.add_layer("background", z_order=0)
        # Create default content layer
        target.add_layer("content", z_order=10)
        # Create default overlay layer
        target.add_layer("overlay", z_order=100)

        self.targets[name] = target
        return target

    def set_lcd(self, display: TextDisplay) -> None:
        """Set the LCD text display."""
        self._lcd_display = display

    def get_target(self, name: str) -> Optional[RenderTarget]:
        """Get a render target by name."""
        return self.targets.get(name)

    def get_layer(self, target_name: str, layer_name: str) -> Optional[Layer]:
        """Get a specific layer from a target."""
        target = self.targets.get(target_name)
        if target:
            return target.get_layer(layer_name)
        return None

    # Drawing API for main display
    def clear_target(self, target_name: str, layer_name: str = "content") -> None:
        """Clear a layer on a target."""
        layer = self.get_layer(target_name, layer_name)
        if layer:
            clear(layer.buffer)

    def clear_all(self) -> None:
        """Clear all layers on all targets."""
        for target in self.targets.values():
            for layer in target.layers:
                clear(layer.buffer)

    def draw_rect(
        self,
        target_name: str,
        x: int,
        y: int,
        width: int,
        height: int,
        color: tuple,
        layer_name: str = "content",
        filled: bool = True,
    ) -> None:
        """Draw a rectangle on a target's layer."""
        layer = self.get_layer(target_name, layer_name)
        if layer:
            draw_rect(layer.buffer, x, y, width, height, color, filled)

    def draw_circle(
        self,
        target_name: str,
        cx: int,
        cy: int,
        radius: int,
        color: tuple,
        layer_name: str = "content",
        filled: bool = True,
    ) -> None:
        """Draw a circle on a target's layer."""
        layer = self.get_layer(target_name, layer_name)
        if layer:
            draw_circle(layer.buffer, cx, cy, radius, color, filled)

    def draw_line(
        self,
        target_name: str,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        color: tuple,
        layer_name: str = "content",
        thickness: int = 1,
    ) -> None:
        """Draw a line on a target's layer."""
        layer = self.get_layer(target_name, layer_name)
        if layer:
            draw_line(layer.buffer, x1, y1, x2, y2, color, thickness)

    def draw_text(
        self,
        target_name: str,
        text: str,
        x: int,
        y: int,
        color: tuple,
        layer_name: str = "content",
        scale: int = 1,
    ) -> tuple:
        """Draw text on a target's layer."""
        layer = self.get_layer(target_name, layer_name)
        if layer:
            return draw_text(layer.buffer, text, x, y, color, scale=scale)
        return (0, 0)

    def draw_image(
        self,
        target_name: str,
        image: NDArray[np.uint8],
        x: int,
        y: int,
        layer_name: str = "content",
        alpha: float = 1.0,
    ) -> None:
        """Draw an image on a target's layer."""
        layer = self.get_layer(target_name, layer_name)
        if layer:
            draw_image(layer.buffer, image, x, y, alpha)

    def fill_layer(
        self,
        target_name: str,
        color: tuple,
        layer_name: str = "background",
    ) -> None:
        """Fill a layer with a solid color."""
        layer = self.get_layer(target_name, layer_name)
        if layer:
            fill(layer.buffer, color)

    # LCD text display
    def set_lcd_text(self, text: str) -> None:
        """Set the LCD display text."""
        self._lcd_text = text[:16]  # Truncate to 16 chars
        if self._lcd_display:
            self._lcd_display.set_text(self._lcd_text)

    def get_lcd_text(self) -> str:
        """Get current LCD text."""
        return self._lcd_text

    # Frame management
    def add_frame_callback(self, callback: Callable[[], None]) -> None:
        """Add a callback to be called each frame before rendering."""
        self._frame_callbacks.append(callback)

    def remove_frame_callback(self, callback: Callable[[], None]) -> None:
        """Remove a frame callback."""
        if callback in self._frame_callbacks:
            self._frame_callbacks.remove(callback)

    def render_frame(self) -> None:
        """Render a single frame to all displays.

        1. Call all frame callbacks (for animations)
        2. Composite all layers for each target
        3. Push buffers to displays
        """
        # Run frame callbacks
        for callback in self._frame_callbacks:
            callback()

        # Composite and render each target
        for target in self.targets.values():
            buffer = target.composite()
            target.display.show(buffer)

    def get_buffer(self, target_name: str) -> Optional[NDArray[np.uint8]]:
        """Get the raw buffer for a target (after compositing)."""
        target = self.targets.get(target_name)
        if target:
            return target.composite()
        return None

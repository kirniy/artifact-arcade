"""Graphics module for ARTIFACT rendering pipeline."""

from artifact.graphics.renderer import Renderer
from artifact.graphics.primitives import (
    draw_rect,
    draw_circle,
    draw_line,
    draw_text,
    draw_image,
    fill,
    clear,
)
from artifact.graphics.compositor import DisplayCompositor
from artifact.graphics.fonts import (
    PixelFont,
    load_font,
    get_default_font,
    get_cyrillic_font,
    draw_text_bitmap,
)

__all__ = [
    # Renderer
    "Renderer",
    "DisplayCompositor",
    # Primitives
    "draw_rect",
    "draw_circle",
    "draw_line",
    "draw_text",
    "draw_image",
    "fill",
    "clear",
    # Fonts
    "PixelFont",
    "load_font",
    "get_default_font",
    "get_cyrillic_font",
    "draw_text_bitmap",
]

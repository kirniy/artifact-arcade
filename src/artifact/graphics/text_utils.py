"""Strategic text rendering utilities for ARTIFACT displays.

This module provides a comprehensive text layout system that ensures:
- Text NEVER gets cut off or overlaps
- Automatic centering with proper measurements
- Smart word wrapping that respects word boundaries
- Multi-line text blocks with proper spacing
- Animated text effects (typing, wave, glow, etc.)
- Automatic scaling to fit available space

Display specifications:
- Main display: 128x128 pixels
- Ticker display: 48x8 pixels
- LCD display: 16 characters

Font specifications (Cyrillic 5x7 font):
- Character width: 5 pixels
- Character height: 7 pixels
- Character spacing: 1 pixel
- Effective char width with spacing: 6 pixels
"""

from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import math

import numpy as np
from numpy.typing import NDArray

from artifact.graphics.fonts import PixelFont, load_font, draw_text_bitmap


# Display constants
MAIN_DISPLAY_WIDTH = 128
MAIN_DISPLAY_HEIGHT = 128
TICKER_WIDTH = 48
TICKER_HEIGHT = 8
LCD_CHARS = 16

# Font constants (Cyrillic 5x7)
CHAR_WIDTH = 5
CHAR_HEIGHT = 7
CHAR_SPACING = 1
CHAR_TOTAL_WIDTH = CHAR_WIDTH + CHAR_SPACING  # 6 pixels per char

# =============================================================================
# SAFE ZONE CONSTANTS - Prevent text cutoff at display edges
# =============================================================================
# Main display is 128x128 pixels. Font height is 7px at scale=1, 14px at scale=2.
# These constants define maximum Y positions to ensure text remains fully visible.

MAIN_SAFE_TOP = 2           # Minimum Y for any text (leave margin at top)
MAIN_SAFE_BOTTOM_S1 = 116   # Max Y for scale=1 text (128 - 7 - 5 margin)
MAIN_SAFE_BOTTOM_S2 = 108   # Max Y for scale=2 text (128 - 14 - 6 margin)
MAIN_HINT_ZONE_Y = 114      # Y for bottom hints at scale=1 (safe, visible)
MAIN_BUTTON_HINT_Y = 116    # Y for button hints like "< NO  > YES"

# Safe margins
MAIN_SIDE_MARGIN = 4        # Left/right margin for text

# Helper function to clamp Y position to safe zone
def clamp_text_y(y: int, scale: int = 1) -> int:
    """Clamp Y position to safe zone based on scale.

    Args:
        y: Desired Y position
        scale: Text scale (1 or 2)

    Returns:
        Clamped Y position within safe zone
    """
    max_y = MAIN_SAFE_BOTTOM_S2 if scale >= 2 else MAIN_SAFE_BOTTOM_S1
    return max(MAIN_SAFE_TOP, min(y, max_y))


def _safe_bottom(scale: int) -> int:
    """Bottom Y that keeps text visible based on scale."""
    return MAIN_SAFE_BOTTOM_S2 if scale >= 2 else MAIN_SAFE_BOTTOM_S1


def draw_text(
    buffer: NDArray[np.uint8],
    text: str,
    x: int,
    y: int,
    color: Tuple[int, int, int],
    scale: int = 1,
    font: Optional[PixelFont] = None,
) -> Tuple[int, int]:
    """Draw text at specific position (not centered).

    Simple wrapper for draw_text_bitmap with default font.

    Args:
        buffer: Target buffer
        text: Text to draw
        x: X position
        y: Y position
        color: RGB color
        scale: Scale factor
        font: Font (defaults to cyrillic)

    Returns:
        Tuple of (width, height) of rendered text
    """
    if font is None:
        font = load_font("cyrillic")
    return draw_text_bitmap(buffer, text, x, y, color, font, scale)


def _clamp_x_within_margin(
    x: int,
    text_width: int,
    display_width: int,
    margin: int = MAIN_SIDE_MARGIN,
) -> int:
    """Clamp X position so text stays inside horizontal margins."""
    max_x = max(margin, display_width - text_width - margin)
    return max(margin, min(x, max_x))


class TextAlign(Enum):
    """Text alignment options."""
    LEFT = auto()
    CENTER = auto()
    RIGHT = auto()


class TextEffect(Enum):
    """Text animation effects."""
    NONE = auto()
    TYPING = auto()      # Characters appear one by one
    WAVE = auto()        # Characters wave up and down
    GLOW = auto()        # Pulsing glow effect
    SHAKE = auto()       # Subtle shake effect
    FADE_IN = auto()     # Fade in from transparent
    SLIDE_IN = auto()    # Slide in from side
    # New dramatic effects
    RAINBOW = auto()     # Rainbow color cycling
    MATRIX = auto()      # Matrix-style rain effect
    GLITCH = auto()      # CRT glitch effect
    PULSE = auto()       # Size pulsing
    SCANLINE = auto()    # CRT scanline effect
    CHROMATIC = auto()   # Chromatic aberration
    FLICKER = auto()     # Old TV flicker
    SPARKLE = auto()     # Sparkling text
    STAR_WARS = auto()   # Star Wars crawl effect


@dataclass
class TextStyle:
    """Text styling configuration."""
    color: Tuple[int, int, int] = (255, 255, 255)
    scale: int = 1
    align: TextAlign = TextAlign.CENTER
    effect: TextEffect = TextEffect.NONE
    effect_speed: float = 1.0
    shadow: bool = False
    shadow_color: Tuple[int, int, int] = (30, 30, 30)
    shadow_offset: Tuple[int, int] = (1, 1)


@dataclass
class TextBlock:
    """A block of text to render with automatic layout."""
    text: str
    y: int  # Y position
    style: TextStyle = field(default_factory=TextStyle)
    max_width: int = MAIN_DISPLAY_WIDTH
    line_spacing: int = 2  # Pixels between lines


def measure_text(text: str, scale: int = 1) -> Tuple[int, int]:
    """Measure text dimensions in pixels.

    Args:
        text: Text to measure
        scale: Scale factor

    Returns:
        Tuple of (width, height) in pixels
    """
    if not text:
        return (0, 0)

    # Each character is CHAR_WIDTH pixels + CHAR_SPACING
    # Last character doesn't need spacing
    char_count = len(text)
    width = (char_count * CHAR_TOTAL_WIDTH - CHAR_SPACING) * scale
    height = CHAR_HEIGHT * scale

    return (width, height)


def measure_text_exact(text: str, font: PixelFont, scale: int = 1) -> Tuple[int, int]:
    """Measure text dimensions exactly using font metrics.

    Args:
        text: Text to measure
        font: PixelFont to use
        scale: Scale factor

    Returns:
        Tuple of (width, height) in pixels
    """
    text_w, text_h = font.measure_text(text)
    return (text_w * scale, text_h * scale)


def calc_centered_x(text_width: int, display_width: int = MAIN_DISPLAY_WIDTH) -> int:
    """Calculate X position for centered text.

    Args:
        text_width: Width of text in pixels
        display_width: Width of display

    Returns:
        X coordinate for centered text
    """
    return max(0, (display_width - text_width) // 2)


def calc_text_x(
    text: str,
    font: PixelFont,
    scale: int = 1,
    align: TextAlign = TextAlign.CENTER,
    display_width: int = MAIN_DISPLAY_WIDTH,
    margin: int = 2,
) -> int:
    """Calculate X position for text with alignment.

    Args:
        text: Text to position
        font: Font to use
        scale: Scale factor
        align: Text alignment
        display_width: Display width
        margin: Margin from edges

    Returns:
        X coordinate for text
    """
    text_w, _ = font.measure_text(text)
    text_w *= scale

    if align == TextAlign.LEFT:
        return margin
    elif align == TextAlign.RIGHT:
        return max(margin, display_width - text_w - margin)
    else:  # CENTER
        return max(margin, (display_width - text_w) // 2)


def smart_wrap_text(
    text: str,
    max_width_pixels: int,
    font: PixelFont,
    scale: int = 1,
) -> List[str]:
    """Smart word-wrap text to fit within pixel width.

    Unlike character-based wrapping, this:
    - Measures actual pixel widths
    - Respects word boundaries
    - Handles long words gracefully

    Args:
        text: Text to wrap
        max_width_pixels: Maximum width in pixels
        font: Font to use for measurement
        scale: Scale factor

    Returns:
        List of wrapped lines
    """
    if not text:
        return []

    words = text.split()
    lines: List[str] = []
    current_line = ""

    for word in words:
        # Try adding word to current line
        test_line = current_line + " " + word if current_line else word
        test_width, _ = font.measure_text(test_line)
        test_width *= scale

        if test_width <= max_width_pixels:
            current_line = test_line
        else:
            # Word doesn't fit, start new line
            if current_line:
                lines.append(current_line)

            # Check if single word is too long
            word_width, _ = font.measure_text(word)
            word_width *= scale

            if word_width > max_width_pixels:
                # Word too long, need to break it
                current_line = ""
                for char in word:
                    test_line = current_line + char
                    test_width, _ = font.measure_text(test_line)
                    test_width *= scale
                    if test_width <= max_width_pixels:
                        current_line = test_line
                    else:
                        if current_line:
                            lines.append(current_line)
                        current_line = char
            else:
                current_line = word

    if current_line:
        lines.append(current_line)

    return lines


def calc_max_chars_per_line(scale: int = 1, display_width: int = MAIN_DISPLAY_WIDTH, margin: int = 4) -> int:
    """Calculate maximum characters that fit on a line.

    Args:
        scale: Text scale
        display_width: Display width
        margin: Total margin (left + right)

    Returns:
        Maximum character count
    """
    available_width = display_width - margin
    char_width = CHAR_TOTAL_WIDTH * scale
    return max(1, available_width // char_width)


def calc_scale_to_fit(text: str, max_width: int = MAIN_DISPLAY_WIDTH - 4, max_scale: int = 3) -> int:
    """Calculate the largest scale that fits text in width.

    Args:
        text: Text to fit
        max_width: Maximum width in pixels
        max_scale: Maximum allowed scale

    Returns:
        Optimal scale factor (1-max_scale)
    """
    for scale in range(max_scale, 0, -1):
        width, _ = measure_text(text, scale)
        if width <= max_width:
            return scale
    return 1


def render_text_block(
    buffer: NDArray[np.uint8],
    block: TextBlock,
    font: PixelFont,
    time_ms: float = 0.0,
) -> int:
    """Render a text block with automatic layout and effects.

    Args:
        buffer: Target buffer
        block: TextBlock configuration
        font: Font to use
        time_ms: Current time for animations

    Returns:
        Y position after the block (for stacking)
    """
    # Calculate available width with margin
    margin = MAIN_SIDE_MARGIN if block.max_width == MAIN_DISPLAY_WIDTH else 4
    available_width = block.max_width - margin * 2

    # Wrap text
    lines = smart_wrap_text(block.text, available_width, font, block.style.scale)

    if not lines:
        return block.y

    # Calculate line height
    line_height = CHAR_HEIGHT * block.style.scale + block.line_spacing
    y = clamp_text_y(block.y, block.style.scale)

    if block.max_width >= MAIN_DISPLAY_WIDTH:
        safe_bottom = _safe_bottom(block.style.scale)
        max_lines = max(1, (safe_bottom - y) // line_height)
    else:
        max_lines = len(lines)

    # Render each line
    for i, line in enumerate(lines[:max_lines]):
        # Calculate X position based on alignment
        x = calc_text_x(
            line, font, block.style.scale,
            block.style.align, block.max_width, margin
        )

        # Apply effects
        if block.style.effect == TextEffect.WAVE:
            y_offset = int(2 * math.sin(time_ms / 200 + i * 0.5))
            y += y_offset

        elif block.style.effect == TextEffect.SHAKE:
            x_offset = int(1 * math.sin(time_ms / 50 + i))
            y_offset = int(1 * math.cos(time_ms / 50 + i))
            x += x_offset
            y += y_offset

        # Draw shadow if enabled
        if block.style.shadow:
            sx = x + block.style.shadow_offset[0]
            sy = y + block.style.shadow_offset[1]
            draw_text_bitmap(buffer, line, sx, sy, block.style.shadow_color, font, block.style.scale)

        # Calculate color with effects
        color = block.style.color
        if block.style.effect == TextEffect.GLOW:
            # Pulsing brightness
            pulse = 0.7 + 0.3 * math.sin(time_ms / 300)
            color = tuple(int(c * pulse) for c in color)

        elif block.style.effect == TextEffect.FADE_IN:
            # Fade in over 1 second
            alpha = min(1.0, time_ms / 1000)
            color = tuple(int(c * alpha) for c in color)

        # Handle typing effect
        if block.style.effect == TextEffect.TYPING:
            chars_visible = int(time_ms / (100 / block.style.effect_speed))
            total_chars = sum(len(l) for l in lines[:i]) + len(line)
            if chars_visible < total_chars:
                # Partial line
                start_chars = sum(len(l) for l in lines[:i])
                visible_in_line = max(0, chars_visible - start_chars)
                line = line[:visible_in_line]
                if not line:
                    break

        # Draw text
        draw_text_bitmap(buffer, line, x, y, color, font, block.style.scale)
        y += line_height

    return y


def draw_centered_text(
    buffer: NDArray[np.uint8],
    text: str,
    y: int,
    color: Tuple[int, int, int],
    scale: int = 1,
    font: Optional[PixelFont] = None,
) -> Tuple[int, int]:
    """Draw perfectly centered text.

    This is the PRIMARY function for drawing centered text.
    Always use this instead of manual positioning.

    Args:
        buffer: Target buffer
        text: Text to draw
        y: Y position
        color: RGB color
        scale: Scale factor
        font: Font (defaults to cyrillic)

    Returns:
        Tuple of (width, height) of rendered text
    """
    if font is None:
        font = load_font("cyrillic")

    display_width = buffer.shape[1] if buffer is not None else MAIN_DISPLAY_WIDTH
    margin = MAIN_SIDE_MARGIN if display_width == MAIN_DISPLAY_WIDTH else 1

    text_w, text_h = font.measure_text(text)
    total_width = text_w * scale

    if display_width == MAIN_DISPLAY_WIDTH:
        y = clamp_text_y(y, scale)

    x = calc_centered_x(total_width, display_width)
    x = _clamp_x_within_margin(x, total_width, display_width, margin)

    return draw_text_bitmap(buffer, text, x, y, color, font, scale)


def draw_wrapped_text(
    buffer: NDArray[np.uint8],
    text: str,
    y: int,
    color: Tuple[int, int, int],
    scale: int = 1,
    max_lines: int = 5,
    line_spacing: int = 2,
    font: Optional[PixelFont] = None,
    max_width: int = MAIN_DISPLAY_WIDTH,
) -> int:
    """Draw word-wrapped centered text.

    Args:
        buffer: Target buffer
        text: Text to wrap and draw
        y: Starting Y position
        color: RGB color
        scale: Scale factor
        max_lines: Maximum lines to render
        line_spacing: Pixels between lines
        font: Font (defaults to cyrillic)
        max_width: Maximum width in pixels

    Returns:
        Y position after last line
    """
    if font is None:
        font = load_font("cyrillic")

    display_width = buffer.shape[1] if buffer is not None else max_width
    target_width = min(max_width, display_width)
    margin = MAIN_SIDE_MARGIN if target_width == MAIN_DISPLAY_WIDTH else 4
    available_width = target_width - margin * 2
    lines = smart_wrap_text(text, available_width, font, scale)

    line_height = CHAR_HEIGHT * scale + line_spacing
    y = clamp_text_y(y, scale) if target_width == MAIN_DISPLAY_WIDTH else y

    if target_width == MAIN_DISPLAY_WIDTH:
        safe_bottom = _safe_bottom(scale)
        max_visible = max(1, (safe_bottom - y) // line_height)
    else:
        max_visible = max_lines

    for i, line in enumerate(lines[:min(max_lines, max_visible)]):
        text_w, _ = font.measure_text(line)
        x = calc_centered_x(text_w * scale, target_width)
        x = _clamp_x_within_margin(x, text_w * scale, target_width, margin)
        draw_text_bitmap(buffer, line, x, y, color, font, scale)
        y += line_height

    return y


def fit_text_in_rect(
    buffer: NDArray[np.uint8],
    text: str,
    rect: Tuple[int, int, int, int],  # (x, y, width, height)
    color: Tuple[int, int, int],
    font: Optional[PixelFont] = None,
    max_scale: int = 3,
    padding: int = 2,
) -> None:
    """Fit text within a rectangle, auto-scaling and wrapping.

    Args:
        buffer: Target buffer
        text: Text to render
        rect: (x, y, width, height) of bounding rectangle
        color: RGB color
        font: Font to use
        max_scale: Maximum scale to try
        padding: Padding inside rectangle
    """
    if font is None:
        font = load_font("cyrillic")

    x, y, width, height = rect
    available_width = width - padding * 2
    available_height = height - padding * 2

    # Find best scale
    best_scale = 1
    for scale in range(max_scale, 0, -1):
        lines = smart_wrap_text(text, available_width, font, scale)
        total_height = len(lines) * (CHAR_HEIGHT * scale + 2)
        if total_height <= available_height:
            best_scale = scale
            break

    # Render with best scale
    lines = smart_wrap_text(text, available_width, font, best_scale)
    line_height = CHAR_HEIGHT * best_scale + 2

    # Center vertically
    total_height = len(lines) * line_height
    start_y = y + padding + (available_height - total_height) // 2

    for i, line in enumerate(lines):
        text_w, _ = font.measure_text(line)
        text_x = x + padding + (available_width - text_w * best_scale) // 2
        draw_text_bitmap(buffer, line, text_x, start_y + i * line_height, color, font, best_scale)


def calculate_scroll_duration(
    text: str,
    rect: Tuple[int, int, int, int],
    font: Optional[PixelFont] = None,
    scale: int = 1,
    line_spacing: int = 2,
    scroll_interval_ms: int = 1800,
) -> float:
    """Calculate how long text will take to fully scroll through.

    Returns the time in milliseconds when the last line becomes visible.
    If text fits without scrolling, returns 0.

    Args:
        text: Text to measure
        rect: (x, y, width, height) bounding box
        font: Font to use
        scale: Scale factor
        line_spacing: Pixels between lines
        scroll_interval_ms: Time per scroll step

    Returns:
        Duration in milliseconds to complete one full scroll cycle
    """
    if font is None:
        font = load_font("cyrillic")

    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return 0

    available_width = width - 2
    lines = smart_wrap_text(text, available_width, font, scale)

    if not lines:
        return 0

    line_height = CHAR_HEIGHT * scale + line_spacing
    max_lines = max(1, height // line_height)

    if len(lines) <= max_lines:
        # No scrolling needed - text fits
        return 0

    # Number of scroll steps to show all lines
    scroll_steps = len(lines) - max_lines + 1
    # Total duration = steps * interval (plus a bit extra for reading last view)
    return scroll_steps * scroll_interval_ms


def render_scrolling_text_area(
    buffer: NDArray[np.uint8],
    text: str,
    rect: Tuple[int, int, int, int],
    color: Tuple[int, int, int],
    time_ms: float,
    font: Optional[PixelFont] = None,
    scale: int = 1,
    line_spacing: int = 2,
    scroll_interval_ms: int = 1800,
) -> None:
    """Render wrapped text inside a rectangle with line-by-line scrolling when overflow.

    Args:
        buffer: Target buffer
        text: Text to render
        rect: (x, y, width, height) bounding box
        color: RGB color
        time_ms: Current time for scroll timing
        font: Font to use (defaults to cyrillic)
        scale: Scale factor
        line_spacing: Pixels between lines
        scroll_interval_ms: Time before scrolling to next line
    """
    if font is None:
        font = load_font("cyrillic")

    x, y, width, height = rect
    if width <= 0 or height <= 0:
        return

    available_width = width - 2
    lines = smart_wrap_text(text, available_width, font, scale)

    if not lines:
        return

    line_height = CHAR_HEIGHT * scale + line_spacing
    max_lines = max(1, height // line_height)

    if len(lines) <= max_lines:
        start_line = 0
    else:
        cycle = len(lines) - max_lines + 1
        step = int((time_ms / scroll_interval_ms) % cycle)
        start_line = step

    for i, line in enumerate(lines[start_line:start_line + max_lines]):
        text_w, _ = font.measure_text(line)
        text_x = x + max(0, (width - text_w * scale) // 2)
        text_y = y + i * line_height
        draw_text_bitmap(buffer, line, text_x, text_y, color, font, scale)


# Convenience functions for common display areas

def draw_title(
    buffer: NDArray[np.uint8],
    text: str,
    color: Tuple[int, int, int],
    y: int = 8,
    scale: int = 2,
) -> None:
    """Draw a title at the top of the screen."""
    draw_centered_text(buffer, text, y, color, scale)


def draw_subtitle(
    buffer: NDArray[np.uint8],
    text: str,
    color: Tuple[int, int, int],
    y: int = 28,
    scale: int = 1,
) -> None:
    """Draw a subtitle below the title."""
    draw_centered_text(buffer, text, y, color, scale)


def draw_prompt(
    buffer: NDArray[np.uint8],
    text: str,
    color: Tuple[int, int, int],
    y: int = 112,
    scale: int = 1,
) -> None:
    """Draw a prompt at the bottom of the screen."""
    draw_centered_text(buffer, text, y, color, scale)


def draw_main_text(
    buffer: NDArray[np.uint8],
    text: str,
    color: Tuple[int, int, int],
    y_start: int = 40,
    scale: int = 2,
    max_lines: int = 4,
) -> int:
    """Draw main content text in the center area."""
    return draw_wrapped_text(buffer, text, y_start, color, scale, max_lines)


# LCD text utilities

def format_lcd_text(text: str, width: int = LCD_CHARS) -> str:
    """Format text for LCD display (center and truncate).

    Args:
        text: Text to format
        width: LCD width in characters

    Returns:
        Formatted string
    """
    if len(text) > width:
        text = text[:width]
    return text.center(width)


def truncate_lcd_text(text: str, width: int = LCD_CHARS) -> str:
    """Truncate text for LCD display.

    Args:
        text: Text to truncate
        width: LCD width in characters

    Returns:
        Truncated string
    """
    if len(text) > width:
        return text[:width-1] + "."
    return text


# Ticker text utilities

def calc_ticker_scroll(text: str, time_ms: float, speed: float = 0.1) -> int:
    """Calculate scroll offset for ticker text.

    Args:
        text: Text being scrolled
        time_ms: Current time
        speed: Scroll speed (pixels per ms)

    Returns:
        X offset for scrolling
    """
    text_width = len(text) * CHAR_TOTAL_WIDTH
    scroll_range = text_width + TICKER_WIDTH
    return int(time_ms * speed) % scroll_range


# =============================================================================
# DRAMATIC ANIMATED TEXT EFFECTS
# =============================================================================
# These functions provide eye-catching visual effects for the main display.
# Every text on screen should use these instead of plain draw_text_bitmap!


def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """Convert HSV to RGB color.

    Args:
        h: Hue (0-360)
        s: Saturation (0-1)
        v: Value (0-1)

    Returns:
        RGB tuple (0-255 each)
    """
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = v - c

    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x

    return (int((r + m) * 255), int((g + m) * 255), int((b + m) * 255))


def draw_animated_text(
    buffer: NDArray[np.uint8],
    text: str,
    y: int,
    base_color: Tuple[int, int, int],
    time_ms: float,
    effect: TextEffect = TextEffect.GLOW,
    scale: int = 2,
    font: Optional[PixelFont] = None,
) -> Tuple[int, int]:
    """Draw text with dramatic animated effects.

    This is the PRIMARY function for animated text on the main display.
    ALWAYS use this instead of plain draw_text_bitmap for visual impact!

    Args:
        buffer: Target buffer
        text: Text to draw
        y: Y position
        base_color: Base RGB color
        time_ms: Current time in milliseconds
        effect: Animation effect to apply
        scale: Scale factor
        font: Font (defaults to cyrillic)

    Returns:
        Tuple of (width, height) of rendered text
    """
    if font is None:
        font = load_font("cyrillic")

    text_w, text_h = font.measure_text(text)
    x = calc_centered_x(text_w * scale, MAIN_DISPLAY_WIDTH)

    if effect == TextEffect.RAINBOW:
        # Rainbow cycling - draw each character with shifted hue
        char_x = x
        for i, char in enumerate(text):
            hue = (time_ms / 10 + i * 30) % 360
            color = hsv_to_rgb(hue, 1.0, 1.0)
            draw_text_bitmap(buffer, char, char_x, y, color, font, scale)
            char_w, _ = font.measure_text(char)
            char_x += char_w * scale
        return (text_w * scale, text_h * scale)

    elif effect == TextEffect.GLOW:
        # Pulsing glow with shadow
        pulse = 0.6 + 0.4 * math.sin(time_ms / 200)
        color = tuple(int(c * pulse) for c in base_color)
        # Draw shadow/glow
        shadow_color = tuple(int(c * 0.3) for c in base_color)
        draw_text_bitmap(buffer, text, x + 1, y + 1, shadow_color, font, scale)
        return draw_text_bitmap(buffer, text, x, y, color, font, scale)

    elif effect == TextEffect.WAVE:
        # Wavy text - each character has different Y offset
        char_x = x
        for i, char in enumerate(text):
            wave_y = y + int(3 * math.sin(time_ms / 150 + i * 0.5))
            draw_text_bitmap(buffer, char, char_x, wave_y, base_color, font, scale)
            char_w, _ = font.measure_text(char)
            char_x += char_w * scale
        return (text_w * scale, text_h * scale)

    elif effect == TextEffect.GLITCH:
        # CRT glitch effect - random offsets and color splits
        import random
        glitch_intensity = 0.3 + 0.7 * abs(math.sin(time_ms / 500))

        # Occasional strong glitch
        if random.random() < 0.1 * glitch_intensity:
            offset_x = random.randint(-3, 3)
            offset_y = random.randint(-2, 2)
        else:
            offset_x = 0
            offset_y = 0

        # Chromatic split
        r_color = (base_color[0], 0, 0)
        b_color = (0, 0, base_color[2])
        draw_text_bitmap(buffer, text, x - 1 + offset_x, y + offset_y, r_color, font, scale)
        draw_text_bitmap(buffer, text, x + 1 + offset_x, y + offset_y, b_color, font, scale)
        return draw_text_bitmap(buffer, text, x + offset_x, y + offset_y, base_color, font, scale)

    elif effect == TextEffect.CHROMATIC:
        # Chromatic aberration - RGB split
        offset = int(2 * math.sin(time_ms / 300))
        r_color = (base_color[0], 0, 0)
        g_color = (0, base_color[1], 0)
        b_color = (0, 0, base_color[2])
        draw_text_bitmap(buffer, text, x - offset, y, r_color, font, scale)
        draw_text_bitmap(buffer, text, x, y, g_color, font, scale)
        draw_text_bitmap(buffer, text, x + offset, y, b_color, font, scale)
        return (text_w * scale, text_h * scale)

    elif effect == TextEffect.FLICKER:
        # Old TV flicker effect
        flicker = 0.7 + 0.3 * math.sin(time_ms / 30)
        if math.sin(time_ms / 100) > 0.9:
            flicker *= 0.5  # Random brightness drop
        color = tuple(int(c * flicker) for c in base_color)
        return draw_text_bitmap(buffer, text, x, y, color, font, scale)

    elif effect == TextEffect.PULSE:
        # Size pulsing (simulated with brightness)
        pulse = 0.5 + 0.5 * math.sin(time_ms / 250)
        # Draw shadow for depth
        shadow = tuple(int(c * 0.2) for c in base_color)
        draw_text_bitmap(buffer, text, x + 2, y + 2, shadow, font, scale)
        # Main text with pulse
        color = tuple(int(c * (0.6 + 0.4 * pulse)) for c in base_color)
        return draw_text_bitmap(buffer, text, x, y, color, font, scale)

    elif effect == TextEffect.SPARKLE:
        # Sparkling text - random characters get bright
        import random
        char_x = x
        for i, char in enumerate(text):
            # Each character has a chance to sparkle
            sparkle = random.random() < 0.1
            if sparkle:
                color = (255, 255, 255)  # Bright white sparkle
            else:
                brightness = 0.7 + 0.3 * math.sin(time_ms / 200 + i * 0.3)
                color = tuple(int(c * brightness) for c in base_color)
            draw_text_bitmap(buffer, char, char_x, y, color, font, scale)
            char_w, _ = font.measure_text(char)
            char_x += char_w * scale
        return (text_w * scale, text_h * scale)

    elif effect == TextEffect.SCANLINE:
        # CRT scanline effect
        # Draw text normally first
        draw_text_bitmap(buffer, text, x, y, base_color, font, scale)
        # Add scanline sweep
        scan_y = int((time_ms / 20) % (text_h * scale + 10))
        for sy in range(y, y + text_h * scale):
            if (sy - y) == scan_y:
                # Brighten this line
                for sx in range(max(0, x - 2), min(128, x + text_w * scale + 2)):
                    if sy < 128 and sx < 128:
                        buffer[sy, sx] = np.clip(buffer[sy, sx].astype(np.int16) + 40, 0, 255).astype(np.uint8)
        return (text_w * scale, text_h * scale)

    elif effect == TextEffect.MATRIX:
        # Matrix rain effect - characters fade in from top
        progress = (time_ms / 50) % (len(text) + 5)
        char_x = x
        for i, char in enumerate(text):
            if i < progress:
                alpha = min(1.0, (progress - i) / 3)
                color = tuple(int(c * alpha) for c in base_color)
                draw_text_bitmap(buffer, char, char_x, y, color, font, scale)
            char_w, _ = font.measure_text(char)
            char_x += char_w * scale
        return (text_w * scale, text_h * scale)

    elif effect == TextEffect.TYPING:
        # Typing effect with cursor
        chars_visible = int(time_ms / 80)
        visible_text = text[:chars_visible]
        draw_text_bitmap(buffer, visible_text, x, y, base_color, font, scale)
        # Blinking cursor
        if chars_visible < len(text) and int(time_ms / 300) % 2 == 0:
            cursor_x = x + len(visible_text) * CHAR_TOTAL_WIDTH * scale
            draw_text_bitmap(buffer, "_", cursor_x, y, base_color, font, scale)
        return (text_w * scale, text_h * scale)

    else:  # NONE or FADE_IN or SLIDE_IN
        return draw_text_bitmap(buffer, text, x, y, base_color, font, scale)


def draw_dramatic_title(
    buffer: NDArray[np.uint8],
    text: str,
    time_ms: float,
    color: Tuple[int, int, int] = (255, 200, 100),
    y: int = 10,
) -> None:
    """Draw a dramatic animated title at the top of the screen.

    Uses rainbow effect for maximum visual impact.
    """
    draw_animated_text(buffer, text, y, color, time_ms, TextEffect.RAINBOW, scale=2)


def draw_dramatic_subtitle(
    buffer: NDArray[np.uint8],
    text: str,
    time_ms: float,
    color: Tuple[int, int, int] = (150, 200, 255),
    y: int = 35,
) -> None:
    """Draw an animated subtitle below the title.

    Uses glow effect for emphasis.
    """
    draw_animated_text(buffer, text, y, color, time_ms, TextEffect.GLOW, scale=1)


def draw_dramatic_result(
    buffer: NDArray[np.uint8],
    text: str,
    time_ms: float,
    color: Tuple[int, int, int] = (255, 255, 255),
    y: int = 50,
    scale: int = 2,
) -> int:
    """Draw dramatic result text with word wrapping and effects.

    Returns the Y position after the last line.
    """
    font = load_font("cyrillic")
    margin = 4
    available_width = MAIN_DISPLAY_WIDTH - margin * 2
    lines = smart_wrap_text(text, available_width, font, scale)

    line_height = CHAR_HEIGHT * scale + 2

    for i, line in enumerate(lines[:5]):
        # Staggered wave effect
        wave_offset = int(2 * math.sin(time_ms / 200 + i * 0.5))
        line_y = y + wave_offset

        # Brightness pulse
        pulse = 0.7 + 0.3 * math.sin(time_ms / 300 + i * 0.3)
        line_color = tuple(int(c * pulse) for c in color)

        draw_centered_text(buffer, line, line_y, line_color, scale, font)
        y += line_height

    return y


def draw_processing_animation(
    buffer: NDArray[np.uint8],
    text: str,
    time_ms: float,
    color: Tuple[int, int, int] = (100, 200, 255),
) -> None:
    """Draw an animated processing/loading text.

    Centered on screen with dramatic effects.
    """
    # Add animated dots
    dots_count = int(time_ms / 300) % 4
    full_text = text + "." * dots_count

    # Draw with glitch effect
    draw_animated_text(buffer, full_text, 55, color, time_ms, TextEffect.GLITCH, scale=2)

    # Add scanning bar below
    bar_y = 75
    bar_width = 80
    bar_x = (128 - bar_width) // 2
    progress = (time_ms / 20) % bar_width

    # Background bar
    for bx in range(bar_x, bar_x + bar_width):
        if bx < 128:
            buffer[bar_y:bar_y+3, bx] = [30, 30, 40]

    # Progress indicator
    indicator_x = bar_x + int(progress)
    for ix in range(max(0, indicator_x - 5), min(128, indicator_x + 5)):
        brightness = 1.0 - abs(ix - indicator_x) / 5
        c = tuple(int(v * brightness) for v in color)
        buffer[bar_y:bar_y+3, ix] = c


def draw_button_labels(
    buffer: NDArray[np.uint8],
    left_text: str,
    right_text: str,
    time_ms: float,
    y: int = 110,
    color: Tuple[int, int, int] = (255, 255, 255),
) -> None:
    """Draw animated button labels at the bottom of screen.

    Left and right labels with pulsing effect.
    """
    font = load_font("cyrillic")

    # Alternating pulse for left/right
    left_pulse = 0.6 + 0.4 * math.sin(time_ms / 300)
    right_pulse = 0.6 + 0.4 * math.sin(time_ms / 300 + math.pi)

    left_color = tuple(int(c * left_pulse) for c in color)
    right_color = tuple(int(c * right_pulse) for c in color)

    # Left label (with arrow)
    left_full = f"< {left_text}"
    draw_text_bitmap(buffer, left_full, 5, y, left_color, font, scale=1)

    # Right label (with arrow)
    right_full = f"{right_text} >"
    right_w, _ = font.measure_text(right_full)
    draw_text_bitmap(buffer, right_full, 128 - right_w - 5, y, right_color, font, scale=1)


# =============================================================================
# ENHANCED TICKER ANIMATIONS
# =============================================================================
# Dramatic, smooth, endless ticker effects for the 48x8 display


class TickerEffect(Enum):
    """Ticker animation effects."""
    SCROLL = auto()           # Simple smooth scroll
    SCROLL_BOUNCE = auto()    # Scroll with bounce at ends
    WAVE_SCROLL = auto()      # Scrolling with wave effect
    RAINBOW_SCROLL = auto()   # Rainbow colored scroll
    GLITCH_SCROLL = auto()    # Glitchy scroll effect
    FADE_SCROLL = auto()      # Fade in/out at edges
    PULSE_SCROLL = auto()     # Pulsing brightness scroll
    SPARKLE_SCROLL = auto()   # Sparkling text scroll


def render_ticker_animated(
    buffer: NDArray[np.uint8],
    text: str,
    time_ms: float,
    color: Tuple[int, int, int],
    effect: TickerEffect = TickerEffect.SCROLL,
    speed: float = 0.015,
    font: Optional[PixelFont] = None,
) -> None:
    """Render dramatically animated ticker text with SEAMLESS endless looping.

    This is the PRIMARY function for ticker display - use instead of
    manual draw_text_bitmap for smooth, professional animations!

    The text scrolls smoothly from right to left in an endless loop.
    When the text reaches the end, it seamlessly wraps around with no gaps.

    SMOOTH SCROLLING TECHNIQUE:
    - Integer-based scroll position prevents sub-pixel jitter
    - Consistent rounding ensures smooth, steady movement
    - Seamless looping with visual separator for continuous flow

    RECOMMENDED SPEED VALUES:
    - 0.015: Very slow, leisurely reading pace
    - 0.025: Default - smooth, comfortable reading (RECOMMENDED)
    - 0.035: Medium pace, still readable
    - 0.050: Fast scrolling, harder to read

    Args:
        buffer: Ticker buffer (48x8)
        text: Text to display (will be repeated for seamless loop)
        time_ms: Current time in ms
        color: Base RGB color
        effect: Animation effect
        speed: Scroll speed in pixels per millisecond (default 0.025)
        font: Font (defaults to cyrillic)
    """
    if font is None:
        font = load_font("cyrillic")

    # Create seamless looping text with visual separator
    separator = "   ★   "
    loop_text = text.rstrip() + separator

    # Measure the single loop unit width
    loop_w, _ = font.measure_text(loop_text)

    # Ensure minimum width for scrolling
    scroll_range = max(loop_w, TICKER_WIDTH)

    # Smooth scrolling: integer-based position for crisp movement
    total_scroll = int(time_ms * speed)
    scroll = total_scroll % scroll_range

    # Text enters from right edge and scrolls left
    base_x = TICKER_WIDTH - scroll

    # Helper function to draw text at two positions for seamless wrap
    def draw_seamless(text_to_draw: str, x_offset: int, draw_color: Tuple[int, int, int], y_offset: int = 0):
        """Draw text twice for seamless looping."""
        # First instance
        if x_offset < TICKER_WIDTH and x_offset + loop_w > 0:
            draw_text_bitmap(buffer, text_to_draw, x_offset, y_offset, draw_color, font, scale=1)
        # Second instance (for seamless wrap)
        x2 = x_offset + loop_w
        if x2 < TICKER_WIDTH and x2 + loop_w > 0:
            draw_text_bitmap(buffer, text_to_draw, x2, y_offset, draw_color, font, scale=1)

    if effect == TickerEffect.SCROLL:
        # Simple smooth scroll with seamless loop
        draw_seamless(loop_text, base_x, color)

    elif effect == TickerEffect.RAINBOW_SCROLL:
        # Rainbow colored scroll - each character different color
        # Pre-calculate character positions to avoid float accumulation
        char_positions = []
        pos = 0
        for char in loop_text:
            char_positions.append(pos)
            char_w, _ = font.measure_text(char)
            pos += char_w

        # Draw twice for seamless wrap
        for offset in [0, loop_w]:
            for i, char in enumerate(loop_text):
                char_x = base_x + offset + char_positions[i]
                if -10 < char_x < TICKER_WIDTH + 10:
                    hue = (time_ms / 8 + i * 25) % 360
                    char_color = hsv_to_rgb(hue, 1.0, 1.0)
                    draw_text_bitmap(buffer, char, char_x, 0, char_color, font, scale=1)

    elif effect == TickerEffect.WAVE_SCROLL:
        # Pre-calculate character positions
        char_positions = []
        pos = 0
        for char in loop_text:
            char_positions.append(pos)
            char_w, _ = font.measure_text(char)
            pos += char_w

        # Scroll with vertical wave
        for offset in [0, loop_w]:
            for i, char in enumerate(loop_text):
                char_x = base_x + offset + char_positions[i]
                if -10 < char_x < TICKER_WIDTH + 10:
                    # Subtle Y offset for wave (clamped to fit in 8px height)
                    wave_y = int(1 * math.sin(time_ms / 200 + i * 0.4))
                    char_y = max(0, min(1, wave_y))
                    draw_text_bitmap(buffer, char, char_x, char_y, color, font, scale=1)

    elif effect == TickerEffect.GLITCH_SCROLL:
        # Glitchy scroll with occasional distortion
        draw_seamless(loop_text, base_x, color)

        # Deterministic glitch based on time to avoid random jitter
        glitch_phase = int(time_ms / 150) % 13
        if glitch_phase == 0:
            glitch_x = (int(time_ms / 50) % (TICKER_WIDTH - 8)) + 2
            shift = ((int(time_ms / 30) % 5) - 2)
            if 2 <= glitch_x < TICKER_WIDTH - 8:
                buffer[:, glitch_x:glitch_x + 6] = np.roll(
                    buffer[:, glitch_x:glitch_x + 6], shift, axis=1
                )

    elif effect == TickerEffect.FADE_SCROLL:
        # Fade at edges for professional look
        draw_seamless(loop_text, base_x, color)

        # Smooth edge fading
        fade_width = 6
        for fx in range(fade_width):
            alpha = fx / fade_width
            buffer[:, fx] = (buffer[:, fx].astype(float) * alpha).astype(np.uint8)
            buffer[:, TICKER_WIDTH - 1 - fx] = (buffer[:, TICKER_WIDTH - 1 - fx].astype(float) * alpha).astype(np.uint8)

    elif effect == TickerEffect.PULSE_SCROLL:
        # Pulsing brightness
        pulse = 0.6 + 0.4 * math.sin(time_ms / 250)
        pulse_color = tuple(int(c * pulse) for c in color)
        draw_seamless(loop_text, base_x, pulse_color)

    elif effect == TickerEffect.SPARKLE_SCROLL:
        # Pre-calculate character positions
        char_positions = []
        pos = 0
        for char in loop_text:
            char_positions.append(pos)
            char_w, _ = font.measure_text(char)
            pos += char_w

        # Sparkling text with seamless wrap
        for offset in [0, loop_w]:
            for i, char in enumerate(loop_text):
                char_x = base_x + offset + char_positions[i]
                if -10 < char_x < TICKER_WIDTH + 10:
                    # Deterministic sparkle based on time and position
                    sparkle_seed = (int(time_ms / 100) + i) % 17
                    if sparkle_seed == 0:
                        char_color = (255, 255, 255)
                    else:
                        brightness = 0.7 + 0.3 * math.sin(time_ms / 180 + i * 0.4)
                        char_color = tuple(int(c * brightness) for c in color)
                    draw_text_bitmap(buffer, char, char_x, 0, char_color, font, scale=1)

    else:  # Default SCROLL_BOUNCE or fallback
        draw_seamless(loop_text, base_x, color)


def render_ticker_static(
    buffer: NDArray[np.uint8],
    text: str,
    time_ms: float,
    color: Tuple[int, int, int],
    effect: TextEffect = TextEffect.GLOW,
    font: Optional[PixelFont] = None,
) -> None:
    """Render static (non-scrolling) ticker text with effects.

    For short text that fits on the ticker without scrolling.
    """
    if font is None:
        font = load_font("cyrillic")

    text_w, _ = font.measure_text(text)
    x = (TICKER_WIDTH - text_w) // 2  # Center

    if effect == TextEffect.GLOW:
        pulse = 0.6 + 0.4 * math.sin(time_ms / 200)
        glow_color = tuple(int(c * pulse) for c in color)
        draw_text_bitmap(buffer, text, x, 0, glow_color, font, scale=1)

    elif effect == TextEffect.RAINBOW:
        char_x = x
        for i, char in enumerate(text):
            hue = (time_ms / 10 + i * 30) % 360
            char_color = hsv_to_rgb(hue, 1.0, 1.0)
            draw_text_bitmap(buffer, char, char_x, 0, char_color, font, scale=1)
            char_w, _ = font.measure_text(char)
            char_x += char_w

    elif effect == TextEffect.FLICKER:
        flicker = 0.7 + 0.3 * math.sin(time_ms / 30)
        if math.sin(time_ms / 80) > 0.9:
            flicker *= 0.5
        flicker_color = tuple(int(c * flicker) for c in color)
        draw_text_bitmap(buffer, text, x, 0, flicker_color, font, scale=1)

    else:
        draw_text_bitmap(buffer, text, x, 0, color, font, scale=1)


# =============================================================================
# STAR WARS CRAWL EFFECT
# =============================================================================
# Classic text crawl that scrolls from bottom to top with perspective fade


def render_star_wars_crawl(
    buffer: NDArray[np.uint8],
    text: str,
    time_ms: float,
    color: Tuple[int, int, int] = (255, 200, 100),
    speed: float = 0.015,
    font: Optional[PixelFont] = None,
    scale: int = 1,
    loop: bool = True,
) -> bool:
    """Render Star Wars-style text crawl effect.

    Text scrolls from bottom to top with perspective fade effect.
    Inspired by the classic Star Wars opening crawl.

    Args:
        buffer: Target buffer (128x128)
        text: Long text to display (will be wrapped)
        time_ms: Current time in milliseconds
        color: Base text color (yellow/gold recommended)
        speed: Scroll speed in pixels per millisecond
        font: Font to use (defaults to cyrillic)
        scale: Text scale (1 or 2)
        loop: Whether to loop the crawl

    Returns:
        True if the crawl is complete (all text has scrolled off top)
    """
    if font is None:
        font = load_font("cyrillic")

    # Wrap text to fit display
    margin = 8
    available_width = MAIN_DISPLAY_WIDTH - margin * 2
    lines = smart_wrap_text(text, available_width, font, scale)

    if not lines:
        return True

    # Calculate total height of all text
    line_height = CHAR_HEIGHT * scale + 4
    total_height = len(lines) * line_height

    # Calculate scroll position
    scroll = int(time_ms * speed)

    # Total scroll range: from bottom of screen to all text off top
    start_y = MAIN_DISPLAY_HEIGHT
    end_scroll = start_y + total_height + 20

    if loop:
        scroll = scroll % end_scroll
    else:
        if scroll > end_scroll:
            return True  # Crawl complete

    # Render each line with perspective effect
    for i, line in enumerate(lines):
        # Calculate Y position for this line
        line_y = start_y + (i * line_height) - scroll

        # Skip lines that are off screen
        if line_y < -line_height or line_y > MAIN_DISPLAY_HEIGHT:
            continue

        # Calculate perspective fade based on Y position
        # Lines at top are dimmer (farther away in perspective)
        if line_y < 0:
            alpha = 0.0
        elif line_y < 40:
            # Fade zone at top (perspective effect)
            alpha = line_y / 40.0
        elif line_y > MAIN_DISPLAY_HEIGHT - 20:
            # Fade in at bottom
            alpha = (MAIN_DISPLAY_HEIGHT - line_y) / 20.0
        else:
            alpha = 1.0

        alpha = max(0.0, min(1.0, alpha))

        if alpha < 0.05:
            continue

        # Apply perspective scale (optional: lines at top are slightly smaller)
        # For simplicity, we just use alpha for now
        line_color = tuple(int(c * alpha) for c in color)

        # Center the line
        text_w, _ = font.measure_text(line)
        x = (MAIN_DISPLAY_WIDTH - text_w * scale) // 2

        # Draw the line
        draw_text_bitmap(buffer, line, x, int(line_y), line_color, font, scale)

    return False


def wrap_text(text: str, width_chars: int = 18) -> List[str]:
    """Simple character-based word wrap.

    Args:
        text: Text to wrap
        width_chars: Maximum characters per line

    Returns:
        List of wrapped lines
    """
    if not text:
        return []

    words = text.split()
    lines: List[str] = []
    current_line = ""

    for word in words:
        if len(current_line) + len(word) + 1 <= width_chars:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
        else:
            if current_line:
                lines.append(current_line)
            # Handle words longer than width
            while len(word) > width_chars:
                lines.append(word[:width_chars])
                word = word[width_chars:]
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines

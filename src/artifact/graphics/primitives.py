"""Basic drawing primitives for ARTIFACT displays."""

from typing import Tuple, Optional
import numpy as np
from numpy.typing import NDArray

# Type aliases
Color = Tuple[int, int, int]
Point = Tuple[int, int]
Buffer = NDArray[np.uint8]


def clear(buffer: Buffer, color: Color = (0, 0, 0)) -> None:
    """Clear buffer to a solid color."""
    buffer[:, :] = color


def fill(buffer: Buffer, color: Color) -> None:
    """Fill entire buffer with color."""
    buffer[:, :] = color


def draw_rect(
    buffer: Buffer,
    x: int,
    y: int,
    width: int,
    height: int,
    color: Color,
    filled: bool = True,
    thickness: int = 1,
) -> None:
    """Draw a rectangle on the buffer.

    Args:
        buffer: Target numpy array (height, width, 3)
        x: Left edge x coordinate
        y: Top edge y coordinate
        width: Rectangle width
        height: Rectangle height
        color: RGB color tuple
        filled: If True, fill rectangle; if False, draw outline only
        thickness: Line thickness for outline (when filled=False)
    """
    h, w = buffer.shape[:2]

    # Clamp to buffer bounds
    x1 = max(0, min(x, w))
    y1 = max(0, min(y, h))
    x2 = max(0, min(x + width, w))
    y2 = max(0, min(y + height, h))

    if filled:
        buffer[y1:y2, x1:x2] = color
    else:
        # Draw outline
        for t in range(thickness):
            # Top edge
            if y1 + t < h:
                buffer[y1 + t, x1:x2] = color
            # Bottom edge
            if y2 - 1 - t >= 0:
                buffer[y2 - 1 - t, x1:x2] = color
            # Left edge
            if x1 + t < w:
                buffer[y1:y2, x1 + t] = color
            # Right edge
            if x2 - 1 - t >= 0:
                buffer[y1:y2, x2 - 1 - t] = color


def draw_circle(
    buffer: Buffer,
    cx: int,
    cy: int,
    radius: int,
    color: Color,
    filled: bool = True,
) -> None:
    """Draw a circle on the buffer using Bresenham's algorithm.

    Args:
        buffer: Target numpy array (height, width, 3)
        cx: Center x coordinate
        cy: Center y coordinate
        radius: Circle radius in pixels
        color: RGB color tuple
        filled: If True, fill circle; if False, draw outline only
    """
    h, w = buffer.shape[:2]

    if filled:
        # Use numpy for filled circle (distance-based)
        y_indices, x_indices = np.ogrid[:h, :w]
        dist_sq = (x_indices - cx) ** 2 + (y_indices - cy) ** 2
        mask = dist_sq <= radius ** 2
        buffer[mask] = color
    else:
        # Bresenham's circle algorithm for outline
        x = 0
        y = radius
        d = 3 - 2 * radius

        def plot_circle_points(px: int, py: int) -> None:
            points = [
                (cx + px, cy + py), (cx - px, cy + py),
                (cx + px, cy - py), (cx - px, cy - py),
                (cx + py, cy + px), (cx - py, cy + px),
                (cx + py, cy - px), (cx - py, cy - px),
            ]
            for point_x, point_y in points:
                if 0 <= point_x < w and 0 <= point_y < h:
                    buffer[point_y, point_x] = color

        while y >= x:
            plot_circle_points(x, y)
            x += 1
            if d > 0:
                y -= 1
                d = d + 4 * (x - y) + 10
            else:
                d = d + 4 * x + 6


def draw_line(
    buffer: Buffer,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    color: Color,
    thickness: int = 1,
) -> None:
    """Draw a line using Bresenham's algorithm.

    Args:
        buffer: Target numpy array (height, width, 3)
        x1, y1: Start point
        x2, y2: End point
        color: RGB color tuple
        thickness: Line thickness in pixels
    """
    h, w = buffer.shape[:2]

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    sx = 1 if x1 < x2 else -1
    sy = 1 if y1 < y2 else -1
    err = dx - dy

    x, y = x1, y1

    while True:
        # Draw point with thickness
        for tx in range(-thickness // 2, (thickness + 1) // 2):
            for ty in range(-thickness // 2, (thickness + 1) // 2):
                px, py = x + tx, y + ty
                if 0 <= px < w and 0 <= py < h:
                    buffer[py, px] = color

        if x == x2 and y == y2:
            break

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def draw_text(
    buffer: Buffer,
    text: str,
    x: int,
    y: int,
    color: Color,
    font: Optional[dict] = None,
    scale: int = 1,
) -> Tuple[int, int]:
    """Draw text using a bitmap font.

    Args:
        buffer: Target numpy array (height, width, 3)
        text: Text string to draw
        x: Starting x coordinate
        y: Starting y coordinate
        color: RGB color tuple
        font: Bitmap font dictionary (char -> 2D array). Uses built-in if None.
        scale: Scale factor for font size

    Returns:
        Tuple of (width, height) of rendered text in pixels
    """
    if font is None:
        font = _get_default_font()

    h, w = buffer.shape[:2]
    cursor_x = x
    char_height = 5 * scale  # Default font is 5 pixels tall
    max_height = char_height

    for char in text:
        if char == ' ':
            cursor_x += 4 * scale
            continue

        char_data = font.get(char.upper(), font.get('?', []))
        if not char_data:
            cursor_x += 4 * scale
            continue

        char_width = len(char_data[0]) if char_data else 0

        for row_idx, row in enumerate(char_data):
            for col_idx, pixel in enumerate(row):
                if pixel:
                    for sy in range(scale):
                        for sx in range(scale):
                            px = cursor_x + col_idx * scale + sx
                            py = y + row_idx * scale + sy
                            if 0 <= px < w and 0 <= py < h:
                                buffer[py, px] = color

        cursor_x += (char_width + 1) * scale

    return cursor_x - x, max_height


def draw_image(
    buffer: Buffer,
    image: Buffer,
    x: int,
    y: int,
    alpha: float = 1.0,
) -> None:
    """Draw an image onto the buffer with optional alpha blending.

    Args:
        buffer: Target numpy array (height, width, 3)
        image: Source image array (height, width, 3 or 4)
        x: Top-left x coordinate
        y: Top-left y coordinate
        alpha: Global alpha multiplier (0.0 to 1.0)
    """
    buf_h, buf_w = buffer.shape[:2]
    img_h, img_w = image.shape[:2]

    # Calculate visible region
    src_x1 = max(0, -x)
    src_y1 = max(0, -y)
    src_x2 = min(img_w, buf_w - x)
    src_y2 = min(img_h, buf_h - y)

    dst_x1 = max(0, x)
    dst_y1 = max(0, y)
    dst_x2 = dst_x1 + (src_x2 - src_x1)
    dst_y2 = dst_y1 + (src_y2 - src_y1)

    if src_x2 <= src_x1 or src_y2 <= src_y1:
        return  # Nothing to draw

    src_region = image[src_y1:src_y2, src_x1:src_x2]

    if alpha >= 1.0 and image.shape[2] == 3:
        # Fast path: direct copy
        buffer[dst_y1:dst_y2, dst_x1:dst_x2] = src_region
    else:
        # Alpha blending
        dst_region = buffer[dst_y1:dst_y2, dst_x1:dst_x2]

        if image.shape[2] == 4:
            # RGBA image with per-pixel alpha
            img_alpha = (src_region[:, :, 3:4] / 255.0) * alpha
            src_rgb = src_region[:, :, :3]
        else:
            # RGB image with global alpha only
            img_alpha = alpha
            src_rgb = src_region

        blended = (src_rgb * img_alpha + dst_region * (1 - img_alpha)).astype(np.uint8)
        buffer[dst_y1:dst_y2, dst_x1:dst_x2] = blended


def _get_default_font() -> dict:
    """Return a simple 3x5 bitmap font for basic characters."""
    # Each character is a list of rows, each row is a list of 0/1 pixels
    return {
        'A': [[0,1,0], [1,0,1], [1,1,1], [1,0,1], [1,0,1]],
        'B': [[1,1,0], [1,0,1], [1,1,0], [1,0,1], [1,1,0]],
        'C': [[0,1,1], [1,0,0], [1,0,0], [1,0,0], [0,1,1]],
        'D': [[1,1,0], [1,0,1], [1,0,1], [1,0,1], [1,1,0]],
        'E': [[1,1,1], [1,0,0], [1,1,0], [1,0,0], [1,1,1]],
        'F': [[1,1,1], [1,0,0], [1,1,0], [1,0,0], [1,0,0]],
        'G': [[0,1,1], [1,0,0], [1,0,1], [1,0,1], [0,1,1]],
        'H': [[1,0,1], [1,0,1], [1,1,1], [1,0,1], [1,0,1]],
        'I': [[1,1,1], [0,1,0], [0,1,0], [0,1,0], [1,1,1]],
        'J': [[0,0,1], [0,0,1], [0,0,1], [1,0,1], [0,1,0]],
        'K': [[1,0,1], [1,0,1], [1,1,0], [1,0,1], [1,0,1]],
        'L': [[1,0,0], [1,0,0], [1,0,0], [1,0,0], [1,1,1]],
        'M': [[1,0,1], [1,1,1], [1,0,1], [1,0,1], [1,0,1]],
        'N': [[1,0,1], [1,1,1], [1,1,1], [1,0,1], [1,0,1]],
        'O': [[0,1,0], [1,0,1], [1,0,1], [1,0,1], [0,1,0]],
        'P': [[1,1,0], [1,0,1], [1,1,0], [1,0,0], [1,0,0]],
        'Q': [[0,1,0], [1,0,1], [1,0,1], [1,1,1], [0,1,1]],
        'R': [[1,1,0], [1,0,1], [1,1,0], [1,0,1], [1,0,1]],
        'S': [[0,1,1], [1,0,0], [0,1,0], [0,0,1], [1,1,0]],
        'T': [[1,1,1], [0,1,0], [0,1,0], [0,1,0], [0,1,0]],
        'U': [[1,0,1], [1,0,1], [1,0,1], [1,0,1], [0,1,0]],
        'V': [[1,0,1], [1,0,1], [1,0,1], [0,1,0], [0,1,0]],
        'W': [[1,0,1], [1,0,1], [1,0,1], [1,1,1], [1,0,1]],
        'X': [[1,0,1], [1,0,1], [0,1,0], [1,0,1], [1,0,1]],
        'Y': [[1,0,1], [1,0,1], [0,1,0], [0,1,0], [0,1,0]],
        'Z': [[1,1,1], [0,0,1], [0,1,0], [1,0,0], [1,1,1]],
        '0': [[0,1,0], [1,0,1], [1,0,1], [1,0,1], [0,1,0]],
        '1': [[0,1,0], [1,1,0], [0,1,0], [0,1,0], [1,1,1]],
        '2': [[0,1,0], [1,0,1], [0,0,1], [0,1,0], [1,1,1]],
        '3': [[1,1,0], [0,0,1], [0,1,0], [0,0,1], [1,1,0]],
        '4': [[1,0,1], [1,0,1], [1,1,1], [0,0,1], [0,0,1]],
        '5': [[1,1,1], [1,0,0], [1,1,0], [0,0,1], [1,1,0]],
        '6': [[0,1,1], [1,0,0], [1,1,0], [1,0,1], [0,1,0]],
        '7': [[1,1,1], [0,0,1], [0,1,0], [0,1,0], [0,1,0]],
        '8': [[0,1,0], [1,0,1], [0,1,0], [1,0,1], [0,1,0]],
        '9': [[0,1,0], [1,0,1], [0,1,1], [0,0,1], [1,1,0]],
        '?': [[0,1,0], [1,0,1], [0,0,1], [0,0,0], [0,1,0]],
        '!': [[0,1,0], [0,1,0], [0,1,0], [0,0,0], [0,1,0]],
        '.': [[0,0,0], [0,0,0], [0,0,0], [0,0,0], [0,1,0]],
        ',': [[0,0,0], [0,0,0], [0,0,0], [0,1,0], [1,0,0]],
        ':': [[0,0,0], [0,1,0], [0,0,0], [0,1,0], [0,0,0]],
        '-': [[0,0,0], [0,0,0], [1,1,1], [0,0,0], [0,0,0]],
        '+': [[0,0,0], [0,1,0], [1,1,1], [0,1,0], [0,0,0]],
        '*': [[0,0,0], [1,0,1], [0,1,0], [1,0,1], [0,0,0]],
        '#': [[1,0,1], [1,1,1], [1,0,1], [1,1,1], [1,0,1]],
    }

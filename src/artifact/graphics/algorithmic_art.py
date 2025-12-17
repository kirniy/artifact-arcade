"""Algorithmic Art Engine - Creative visual effects for ARTIFACT.

This module provides stunning visual effects inspired by:
- Flow fields and Perlin noise
- Dithering algorithms (Floyd-Steinberg, Bayer, Atkinson, etc.)
- Halftone patterns
- Pixel sorting
- Glitch aesthetics
- Particle systems
- ASCII/character rendering

All effects are optimized for 128x128 pixel displays.
"""

import math
import random
from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass, field
import numpy as np
from numpy.typing import NDArray


# =============================================================================
# PERLIN NOISE IMPLEMENTATION
# =============================================================================

class PerlinNoise:
    """Fast Perlin noise implementation for flow fields."""

    def __init__(self, seed: int = None):
        self.seed = seed or random.randint(0, 65535)
        self._perm = self._generate_permutation()

    def _generate_permutation(self) -> List[int]:
        """Generate permutation table."""
        random.seed(self.seed)
        perm = list(range(256))
        random.shuffle(perm)
        return perm + perm  # Double for overflow handling

    def _fade(self, t: float) -> float:
        """Fade function for smooth interpolation."""
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation."""
        return a + t * (b - a)

    def _grad(self, hash_val: int, x: float, y: float) -> float:
        """Calculate gradient."""
        h = hash_val & 3
        if h == 0:
            return x + y
        elif h == 1:
            return -x + y
        elif h == 2:
            return x - y
        else:
            return -x - y

    def noise2d(self, x: float, y: float) -> float:
        """Generate 2D Perlin noise value."""
        # Grid cell coordinates
        xi = int(math.floor(x)) & 255
        yi = int(math.floor(y)) & 255

        # Relative position in cell
        xf = x - math.floor(x)
        yf = y - math.floor(y)

        # Fade curves
        u = self._fade(xf)
        v = self._fade(yf)

        # Hash coordinates
        aa = self._perm[self._perm[xi] + yi]
        ab = self._perm[self._perm[xi] + yi + 1]
        ba = self._perm[self._perm[xi + 1] + yi]
        bb = self._perm[self._perm[xi + 1] + yi + 1]

        # Blend results
        x1 = self._lerp(self._grad(aa, xf, yf), self._grad(ba, xf - 1, yf), u)
        x2 = self._lerp(self._grad(ab, xf, yf - 1), self._grad(bb, xf - 1, yf - 1), u)

        return (self._lerp(x1, x2, v) + 1) / 2  # Normalize to 0-1

    def fbm(self, x: float, y: float, octaves: int = 4) -> float:
        """Fractal Brownian Motion - layered noise."""
        value = 0.0
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0

        for _ in range(octaves):
            value += amplitude * self.noise2d(x * frequency, y * frequency)
            max_value += amplitude
            amplitude *= 0.5
            frequency *= 2.0

        return value / max_value


# =============================================================================
# FLOW FIELD
# =============================================================================

@dataclass
class FlowParticle:
    """A particle in a flow field."""
    x: float
    y: float
    prev_x: float = 0.0
    prev_y: float = 0.0
    speed: float = 1.0
    color: Tuple[int, int, int] = (255, 255, 255)
    life: float = 1.0
    age: int = 0
    max_age: int = 100


class FlowField:
    """Perlin noise-based flow field for stunning particle effects."""

    def __init__(self, width: int = 128, height: int = 128,
                 scale: float = 0.05, seed: int = None):
        self.width = width
        self.height = height
        self.scale = scale
        self.noise = PerlinNoise(seed)
        self.time_offset = 0.0
        self.particles: List[FlowParticle] = []

        # Precompute flow field
        self.field = np.zeros((height, width), dtype=np.float32)
        self._compute_field()

    def _compute_field(self):
        """Compute the flow field angles."""
        for y in range(self.height):
            for x in range(self.width):
                noise_val = self.noise.fbm(
                    x * self.scale + self.time_offset,
                    y * self.scale + self.time_offset,
                    octaves=3
                )
                self.field[y, x] = noise_val * math.pi * 4  # Map to angle

    def update(self, delta_ms: float, evolve: bool = True):
        """Update flow field and particles."""
        if evolve:
            self.time_offset += delta_ms / 5000
            self._compute_field()

        # Update particles
        for particle in self.particles:
            particle.prev_x = particle.x
            particle.prev_y = particle.y

            # Get flow angle at particle position
            px = int(particle.x) % self.width
            py = int(particle.y) % self.height
            angle = self.field[py, px]

            # Move particle
            particle.x += math.cos(angle) * particle.speed
            particle.y += math.sin(angle) * particle.speed
            particle.age += 1

            # Wrap around
            if particle.x < 0:
                particle.x = self.width - 1
                particle.prev_x = particle.x
            elif particle.x >= self.width:
                particle.x = 0
                particle.prev_x = particle.x

            if particle.y < 0:
                particle.y = self.height - 1
                particle.prev_y = particle.y
            elif particle.y >= self.height:
                particle.y = 0
                particle.prev_y = particle.y

            # Age and fade
            particle.life = 1 - (particle.age / particle.max_age)

        # Remove dead particles
        self.particles = [p for p in self.particles if p.age < p.max_age]

    def spawn_particle(self, x: float = None, y: float = None,
                       color: Tuple[int, int, int] = None):
        """Spawn a new particle."""
        if x is None:
            x = random.uniform(0, self.width)
        if y is None:
            y = random.uniform(0, self.height)
        if color is None:
            # Rainbow based on position
            hue = (x / self.width) * 360
            color = hsv_to_rgb(hue, 0.8, 1.0)

        self.particles.append(FlowParticle(
            x=x, y=y, prev_x=x, prev_y=y,
            speed=random.uniform(0.5, 2.0),
            color=color,
            max_age=random.randint(50, 150)
        ))

    def spawn_from_image(self, image: NDArray[np.uint8], count: int = 500,
                         brightness_threshold: int = 50):
        """Spawn particles from bright areas of an image."""
        if image.shape[:2] != (self.height, self.width):
            return

        # Find bright pixels
        if len(image.shape) == 3:
            brightness = np.mean(image, axis=2)
        else:
            brightness = image

        bright_coords = np.argwhere(brightness > brightness_threshold)

        if len(bright_coords) > 0:
            for _ in range(min(count, len(bright_coords))):
                idx = random.randint(0, len(bright_coords) - 1)
                y, x = bright_coords[idx]
                color = tuple(int(c) for c in image[y, x])
                self.spawn_particle(x, y, color)

    def render(self, buffer: NDArray[np.uint8],
               draw_lines: bool = True,
               fade_trails: bool = True):
        """Render particles to buffer."""
        if fade_trails:
            # Fade existing content
            buffer[:] = (buffer.astype(np.float32) * 0.95).astype(np.uint8)

        for particle in self.particles:
            alpha = particle.life
            color = (
                int(particle.color[0] * alpha),
                int(particle.color[1] * alpha),
                int(particle.color[2] * alpha),
            )

            px, py = int(particle.x), int(particle.y)
            if 0 <= px < self.width and 0 <= py < self.height:
                if draw_lines and particle.age > 0:
                    # Draw line from previous position
                    self._draw_line(buffer,
                                    int(particle.prev_x), int(particle.prev_y),
                                    px, py, color)
                else:
                    buffer[py, px] = color

    def _draw_line(self, buffer: NDArray[np.uint8],
                   x1: int, y1: int, x2: int, y2: int,
                   color: Tuple[int, int, int]):
        """Draw a line using Bresenham's algorithm."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            if 0 <= x1 < self.width and 0 <= y1 < self.height:
                buffer[y1, x1] = color

            if x1 == x2 and y1 == y2:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy


# =============================================================================
# DITHERING ALGORITHMS
# =============================================================================

class Dithering:
    """Various dithering algorithms for artistic effects."""

    # Bayer matrix 4x4
    BAYER_4X4 = np.array([
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
    ], dtype=np.float32) / 16.0

    # Bayer matrix 8x8
    BAYER_8X8 = np.array([
        [0, 32, 8, 40, 2, 34, 10, 42],
        [48, 16, 56, 24, 50, 18, 58, 26],
        [12, 44, 4, 36, 14, 46, 6, 38],
        [60, 28, 52, 20, 62, 30, 54, 22],
        [3, 35, 11, 43, 1, 33, 9, 41],
        [51, 19, 59, 27, 49, 17, 57, 25],
        [15, 47, 7, 39, 13, 45, 5, 37],
        [63, 31, 55, 23, 61, 29, 53, 21]
    ], dtype=np.float32) / 64.0

    @staticmethod
    def floyd_steinberg(image: NDArray[np.uint8],
                        levels: int = 2) -> NDArray[np.uint8]:
        """Floyd-Steinberg error diffusion dithering."""
        if len(image.shape) == 3:
            # Process each channel
            result = np.zeros_like(image)
            for c in range(3):
                result[:, :, c] = Dithering.floyd_steinberg(image[:, :, c], levels)
            return result

        img = image.astype(np.float32)
        height, width = img.shape

        for y in range(height):
            for x in range(width):
                old_pixel = img[y, x]
                # Quantize
                new_pixel = round(old_pixel / 255 * (levels - 1)) * 255 / (levels - 1)
                img[y, x] = new_pixel
                error = old_pixel - new_pixel

                # Distribute error
                if x + 1 < width:
                    img[y, x + 1] += error * 7 / 16
                if y + 1 < height:
                    if x > 0:
                        img[y + 1, x - 1] += error * 3 / 16
                    img[y + 1, x] += error * 5 / 16
                    if x + 1 < width:
                        img[y + 1, x + 1] += error * 1 / 16

        return np.clip(img, 0, 255).astype(np.uint8)

    @staticmethod
    def atkinson(image: NDArray[np.uint8],
                 levels: int = 2) -> NDArray[np.uint8]:
        """Atkinson dithering - more aggressive, classic Mac look."""
        if len(image.shape) == 3:
            result = np.zeros_like(image)
            for c in range(3):
                result[:, :, c] = Dithering.atkinson(image[:, :, c], levels)
            return result

        img = image.astype(np.float32)
        height, width = img.shape

        for y in range(height):
            for x in range(width):
                old_pixel = img[y, x]
                new_pixel = round(old_pixel / 255 * (levels - 1)) * 255 / (levels - 1)
                img[y, x] = new_pixel
                error = (old_pixel - new_pixel) / 8  # Atkinson divides by 8

                # Distribute error (1/8 each, total 6/8)
                if x + 1 < width:
                    img[y, x + 1] += error
                if x + 2 < width:
                    img[y, x + 2] += error
                if y + 1 < height:
                    if x > 0:
                        img[y + 1, x - 1] += error
                    img[y + 1, x] += error
                    if x + 1 < width:
                        img[y + 1, x + 1] += error
                if y + 2 < height:
                    img[y + 2, x] += error

        return np.clip(img, 0, 255).astype(np.uint8)

    @staticmethod
    def ordered_bayer(image: NDArray[np.uint8],
                      matrix_size: int = 4,
                      levels: int = 2) -> NDArray[np.uint8]:
        """Ordered dithering using Bayer matrix."""
        if len(image.shape) == 3:
            result = np.zeros_like(image)
            for c in range(3):
                result[:, :, c] = Dithering.ordered_bayer(image[:, :, c], matrix_size, levels)
            return result

        matrix = Dithering.BAYER_4X4 if matrix_size == 4 else Dithering.BAYER_8X8
        height, width = image.shape

        # Tile the matrix
        tiled = np.tile(matrix, (height // matrix.shape[0] + 1,
                                  width // matrix.shape[1] + 1))[:height, :width]

        # Apply threshold
        normalized = image.astype(np.float32) / 255
        threshold = tiled

        # Multi-level dithering
        result = np.floor(normalized * (levels - 1) + 0.5 + threshold - 0.5)
        result = np.clip(result / (levels - 1) * 255, 0, 255)

        return result.astype(np.uint8)

    @staticmethod
    def halftone(image: NDArray[np.uint8],
                 dot_size: int = 4,
                 angle: float = 45) -> NDArray[np.uint8]:
        """Halftone effect with circular dots."""
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image.astype(np.float32)

        height, width = gray.shape
        result = np.zeros((height, width, 3), dtype=np.uint8)

        # Process in grid cells
        for cy in range(0, height, dot_size):
            for cx in range(0, width, dot_size):
                # Sample center of cell
                sample_y = min(cy + dot_size // 2, height - 1)
                sample_x = min(cx + dot_size // 2, width - 1)
                brightness = gray[sample_y, sample_x] / 255

                # Calculate dot radius based on brightness
                max_radius = dot_size * 0.7
                radius = max_radius * (1 - brightness)

                # Draw dot
                center_y = cy + dot_size // 2
                center_x = cx + dot_size // 2

                for dy in range(-dot_size, dot_size + 1):
                    for dx in range(-dot_size, dot_size + 1):
                        py = center_y + dy
                        px = center_x + dx
                        if 0 <= py < height and 0 <= px < width:
                            dist = math.sqrt(dx * dx + dy * dy)
                            if dist <= radius:
                                result[py, px] = (0, 0, 0)
                            else:
                                result[py, px] = (255, 255, 255)

        return result


# =============================================================================
# GLITCH EFFECTS
# =============================================================================

class GlitchEffects:
    """Real-time glitch art effects."""

    @staticmethod
    def pixel_sort(image: NDArray[np.uint8],
                   threshold: int = 100,
                   direction: str = "horizontal") -> NDArray[np.uint8]:
        """Pixel sorting effect."""
        result = image.copy()

        if direction == "horizontal":
            for y in range(result.shape[0]):
                row = result[y]
                # Find brightness
                if len(row.shape) == 2:
                    brightness = np.mean(row, axis=1)
                else:
                    brightness = row

                # Find segments to sort
                mask = brightness > threshold
                segments = []
                start = None

                for x in range(len(mask)):
                    if mask[x] and start is None:
                        start = x
                    elif not mask[x] and start is not None:
                        segments.append((start, x))
                        start = None
                if start is not None:
                    segments.append((start, len(mask)))

                # Sort each segment by brightness
                for start, end in segments:
                    if end - start > 1:
                        segment = row[start:end]
                        if len(segment.shape) == 2:
                            indices = np.argsort(np.mean(segment, axis=1))
                        else:
                            indices = np.argsort(segment)
                        result[y, start:end] = segment[indices]

        return result

    @staticmethod
    def channel_shift(image: NDArray[np.uint8],
                      r_offset: Tuple[int, int] = (5, 0),
                      g_offset: Tuple[int, int] = (0, 0),
                      b_offset: Tuple[int, int] = (-5, 0)) -> NDArray[np.uint8]:
        """RGB channel separation/shift effect."""
        if len(image.shape) != 3:
            return image

        result = np.zeros_like(image)
        height, width = image.shape[:2]

        for c, offset in enumerate([r_offset, g_offset, b_offset]):
            dx, dy = offset
            # Shift channel
            if dx >= 0:
                src_x_start, src_x_end = 0, width - dx
                dst_x_start, dst_x_end = dx, width
            else:
                src_x_start, src_x_end = -dx, width
                dst_x_start, dst_x_end = 0, width + dx

            if dy >= 0:
                src_y_start, src_y_end = 0, height - dy
                dst_y_start, dst_y_end = dy, height
            else:
                src_y_start, src_y_end = -dy, height
                dst_y_start, dst_y_end = 0, height + dy

            result[dst_y_start:dst_y_end, dst_x_start:dst_x_end, c] = \
                image[src_y_start:src_y_end, src_x_start:src_x_end, c]

        return result

    @staticmethod
    def scanline_glitch(image: NDArray[np.uint8],
                        intensity: float = 0.3) -> NDArray[np.uint8]:
        """Random scanline displacement glitch."""
        result = image.copy()
        height = result.shape[0]

        num_glitches = int(height * intensity * 0.3)

        for _ in range(num_glitches):
            y = random.randint(0, height - 1)
            shift = random.randint(-20, 20)
            result[y] = np.roll(result[y], shift, axis=0)

        return result

    @staticmethod
    def block_glitch(image: NDArray[np.uint8],
                     num_blocks: int = 5,
                     max_offset: int = 20) -> NDArray[np.uint8]:
        """Random block displacement."""
        result = image.copy()
        height, width = result.shape[:2]

        for _ in range(num_blocks):
            # Random block
            bx = random.randint(0, width - 20)
            by = random.randint(0, height - 20)
            bw = random.randint(10, 40)
            bh = random.randint(5, 20)

            # Clip to bounds
            bw = min(bw, width - bx)
            bh = min(bh, height - by)

            # Random offset
            ox = random.randint(-max_offset, max_offset)
            oy = random.randint(-max_offset // 2, max_offset // 2)

            # Copy block
            block = result[by:by+bh, bx:bx+bw].copy()

            # Paste at offset
            nx = max(0, min(bx + ox, width - bw))
            ny = max(0, min(by + oy, height - bh))
            result[ny:ny+bh, nx:nx+bw] = block

        return result

    @staticmethod
    def data_mosh(image: NDArray[np.uint8],
                  corruption: float = 0.1) -> NDArray[np.uint8]:
        """Simulate data corruption/moshing."""
        result = image.copy()
        flat = result.flatten()

        num_corruptions = int(len(flat) * corruption)

        for _ in range(num_corruptions):
            idx = random.randint(0, len(flat) - 1)
            flat[idx] = random.randint(0, 255)

        return flat.reshape(result.shape)


# =============================================================================
# ASCII ART RENDERER
# =============================================================================

class ASCIIRenderer:
    """Render images as ASCII/character art."""

    # Character sets from darkest to lightest
    CHARSET_STANDARD = " .:-=+*#%@"
    CHARSET_BLOCKS = " ░▒▓█"
    CHARSET_DENSE = " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
    CHARSET_SIMPLE = " .oO@"
    CHARSET_DOTS = " ·•●"

    def __init__(self, charset: str = None, cell_size: int = 4):
        self.charset = charset or self.CHARSET_BLOCKS
        self.cell_size = cell_size

    def render(self, image: NDArray[np.uint8]) -> List[List[str]]:
        """Convert image to character grid."""
        if len(image.shape) == 3:
            gray = np.mean(image, axis=2)
        else:
            gray = image.astype(np.float32)

        height, width = gray.shape
        rows = height // self.cell_size
        cols = width // self.cell_size

        result = []
        for row in range(rows):
            line = []
            for col in range(cols):
                # Sample cell
                y = row * self.cell_size
                x = col * self.cell_size
                cell = gray[y:y+self.cell_size, x:x+self.cell_size]
                avg_brightness = np.mean(cell) / 255

                # Map to character
                char_idx = int(avg_brightness * (len(self.charset) - 1))
                line.append(self.charset[char_idx])
            result.append(line)

        return result

    def render_to_buffer(self, image: NDArray[np.uint8],
                         buffer: NDArray[np.uint8],
                         fg_color: Tuple[int, int, int] = (0, 255, 0),
                         bg_color: Tuple[int, int, int] = (0, 0, 0)):
        """Render ASCII art directly to pixel buffer."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        chars = self.render(image)
        font = load_font("cyrillic")

        # Clear buffer
        buffer[:] = bg_color

        for row_idx, row in enumerate(chars):
            y = row_idx * 8  # Assuming 8px font height
            if y >= buffer.shape[0]:
                break
            for col_idx, char in enumerate(row):
                x = col_idx * 6  # Assuming ~6px font width
                if x >= buffer.shape[1]:
                    break
                # Vary color by character intensity
                intensity = self.charset.index(char) / len(self.charset)
                color = (
                    int(fg_color[0] * intensity),
                    int(fg_color[1] * intensity),
                    int(fg_color[2] * intensity),
                )
                draw_text_bitmap(buffer, char, x, y, color, font, scale=1)


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def hsv_to_rgb(h: float, s: float, v: float) -> Tuple[int, int, int]:
    """Convert HSV to RGB."""
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


def pixelate(image: NDArray[np.uint8], block_size: int = 8) -> NDArray[np.uint8]:
    """Pixelate an image."""
    height, width = image.shape[:2]
    result = image.copy()

    for y in range(0, height, block_size):
        for x in range(0, width, block_size):
            block = result[y:y+block_size, x:x+block_size]
            avg_color = block.mean(axis=(0, 1)).astype(np.uint8)
            result[y:y+block_size, x:x+block_size] = avg_color

    return result


def posterize(image: NDArray[np.uint8], levels: int = 4) -> NDArray[np.uint8]:
    """Reduce color levels (posterization)."""
    factor = 255 / (levels - 1)
    return (np.round(image / factor) * factor).astype(np.uint8)


def edge_detect(image: NDArray[np.uint8], threshold: int = 30) -> NDArray[np.uint8]:
    """Simple edge detection."""
    if len(image.shape) == 3:
        gray = np.mean(image, axis=2)
    else:
        gray = image.astype(np.float32)

    # Sobel-like edge detection
    edges_h = np.abs(np.diff(gray, axis=0, prepend=0))
    edges_v = np.abs(np.diff(gray, axis=1, prepend=0))
    edges = np.clip(edges_h + edges_v, 0, 255)

    # Threshold
    edges = np.where(edges > threshold, 255, 0).astype(np.uint8)

    # Convert to RGB
    if len(image.shape) == 3:
        return np.stack([edges, edges, edges], axis=2)
    return edges


def color_quantize(image: NDArray[np.uint8],
                   palette: List[Tuple[int, int, int]]) -> NDArray[np.uint8]:
    """Quantize image to a specific color palette."""
    result = np.zeros_like(image)
    palette_array = np.array(palette)

    for y in range(image.shape[0]):
        for x in range(image.shape[1]):
            pixel = image[y, x]
            # Find closest palette color
            distances = np.sum((palette_array - pixel) ** 2, axis=1)
            closest_idx = np.argmin(distances)
            result[y, x] = palette_array[closest_idx]

    return result


# Classic palettes
PALETTE_GAMEBOY = [(15, 56, 15), (48, 98, 48), (139, 172, 15), (155, 188, 15)]
PALETTE_CGA = [(0, 0, 0), (85, 255, 255), (255, 85, 255), (255, 255, 255)]
PALETTE_PICO8 = [
    (0, 0, 0), (29, 43, 83), (126, 37, 83), (0, 135, 81),
    (171, 82, 54), (95, 87, 79), (194, 195, 199), (255, 241, 232),
    (255, 0, 77), (255, 163, 0), (255, 236, 39), (0, 228, 54),
    (41, 173, 255), (131, 118, 156), (255, 119, 168), (255, 204, 170)
]

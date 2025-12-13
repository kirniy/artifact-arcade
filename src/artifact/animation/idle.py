"""Idle animations for different visual styles."""

from typing import Callable, Dict, Optional, Tuple
from dataclasses import dataclass
import math
import random
import numpy as np
from numpy.typing import NDArray

from artifact.animation.engine import AnimationEngine, AnimationPriority
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, EmitterConfig, ParticlePresets
from artifact.graphics.primitives import clear, draw_circle, draw_rect, fill
from artifact.graphics.fonts import load_font, draw_text_bitmap


@dataclass
class IdleAnimationConfig:
    """Configuration for idle animations."""

    style: str = "mystical"  # mystical, arcade, modern
    main_width: int = 128
    main_height: int = 128
    ticker_width: int = 48
    ticker_height: int = 8


class IdleAnimation:
    """Base class for style-specific idle animations."""

    def __init__(self, config: IdleAnimationConfig):
        self.config = config
        self.engine = AnimationEngine()
        self.particles = ParticleSystem()
        self._time = 0.0
        self._frame = 0

    def update(self, delta_ms: float) -> None:
        """Update animation state."""
        self._time += delta_ms
        self._frame += 1
        self.engine.update(delta_ms)
        self.particles.update(delta_ms)

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render to main display buffer."""
        raise NotImplementedError

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render to ticker display buffer."""
        raise NotImplementedError

    def get_lcd_text(self) -> str:
        """Get current LCD text."""
        return "ARTIFACT"

    def reset(self) -> None:
        """Reset animation to initial state."""
        self._time = 0.0
        self._frame = 0
        self.engine.stop_all()
        self.particles.clear_all()


class MysticalIdleAnimation(IdleAnimation):
    """Mystical/fortune-teller style idle animation.

    Features:
    - Crystal ball glow effect
    - Floating star particles
    - Mist/fog overlay
    - Pulsing mystical colors
    """

    def __init__(self, config: IdleAnimationConfig):
        super().__init__(config)

        # Colors
        self.primary = (107, 33, 168)    # Deep purple
        self.secondary = (245, 158, 11)  # Gold
        self.accent = (20, 184, 166)     # Teal
        self.bg = (30, 27, 75)           # Dark blue

        # Crystal ball properties
        self.ball_center = (config.main_width // 2, config.main_height // 2 + 10)
        self.ball_radius = 35
        self.glow_radius = 45

        # Mystical eye properties
        self.eye_offset_x = 0.0  # Current eye position offset
        self.eye_offset_y = 0.0
        self.eye_target_x = 0.0  # Target eye position
        self.eye_target_y = 0.0
        self.eye_change_time = 0.0  # When to change target
        self.blink_time = 0.0
        self.is_blinking = False

        # Setup particle effects
        self._setup_particles()

        # Setup animations
        self._setup_animations()

    def _setup_particles(self) -> None:
        """Initialize particle emitters."""
        # Floating stars
        star_config = ParticlePresets.stars(
            x=self.config.main_width // 2,
            y=self.config.main_height // 2
        )
        star_config.color = self.secondary
        star_config.color_end = self.accent
        self.particles.add_emitter("stars", star_config)

        # Mist effect
        mist_config = ParticlePresets.mist(
            x=self.config.main_width // 2,
            y=self.config.main_height - 10
        )
        mist_config.color = (100, 80, 150)
        self.particles.add_emitter("mist", mist_config)

    def _setup_animations(self) -> None:
        """Initialize timeline animations."""
        # Glow pulse animation
        glow_timeline = Timeline.color_pulse(
            color1=(80, 40, 120),
            color2=(120, 60, 180),
            duration=2000,
            name="glow_pulse"
        )
        self.engine.play(glow_timeline, group="idle")

    def update(self, delta_ms: float) -> None:
        """Update mystical animation including eye movement."""
        super().update(delta_ms)

        # Update eye target position every 2-4 seconds
        if self._time > self.eye_change_time:
            self.eye_target_x = random.uniform(-8, 8)
            self.eye_target_y = random.uniform(-5, 5)
            self.eye_change_time = self._time + random.uniform(1500, 3500)

        # Smoothly move eye toward target
        lerp_speed = 0.03
        self.eye_offset_x += (self.eye_target_x - self.eye_offset_x) * lerp_speed
        self.eye_offset_y += (self.eye_target_y - self.eye_offset_y) * lerp_speed

        # Handle blinking
        if not self.is_blinking and self._time > self.blink_time:
            self.is_blinking = True
            self.blink_time = self._time + 150  # Blink duration

        if self.is_blinking and self._time > self.blink_time:
            self.is_blinking = False
            self.blink_time = self._time + random.uniform(3000, 6000)  # Time until next blink

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render mystical idle animation to main display."""
        # Background
        fill(buffer, self.bg)

        # Glow effect (pulsing)
        glow_phase = math.sin(self._time / 500) * 0.5 + 0.5
        glow_color = self._interpolate_color(
            (60, 30, 100), (100, 50, 160), glow_phase
        )

        # Draw outer glow
        for r in range(self.glow_radius, self.ball_radius, -2):
            alpha = (r - self.ball_radius) / (self.glow_radius - self.ball_radius)
            color = tuple(int(c * (1 - alpha) * 0.5) for c in glow_color)
            draw_circle(buffer, self.ball_center[0], self.ball_center[1], r, color, filled=False)

        # Crystal ball
        cx, cy = self.ball_center
        for r in range(self.ball_radius, 0, -1):
            factor = r / self.ball_radius
            color = tuple(int(c * factor + 20) for c in self.primary)
            draw_circle(buffer, cx, cy, r, color)

        # Mystical eye inside the crystal ball
        self._render_mystical_eye(buffer, cx, cy)

        # Ball highlight (glass reflection)
        highlight_x = cx - self.ball_radius // 3
        highlight_y = cy - self.ball_radius // 3
        draw_circle(buffer, highlight_x, highlight_y, 6, (120, 100, 150))
        draw_circle(buffer, highlight_x, highlight_y, 3, (180, 160, 200))

        # Render particles on top
        self.particles.render(buffer)

        # Draw title text
        font = load_font("cyrillic")
        text = "АРТЕФАКТ"
        text_width, text_height = font.measure_text(text)
        text_x = (self.config.main_width - text_width * 2) // 2
        draw_text_bitmap(buffer, text, text_x, 15, self.secondary, font, scale=2)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        clear(buffer)

        # Scrolling mystical message
        messages = ["УЗНАЙ СВОЮ СУДЬБУ", "ТАЙНЫ ЗВЁЗД", "ТВОЁ БУДУЩЕЕ"]
        msg_idx = int(self._time / 5000) % len(messages)
        message = messages[msg_idx]

        # Simple scroll
        scroll_offset = int(self._time / 50) % (len(message) * 6 + self.config.ticker_width)
        x_pos = self.config.ticker_width - scroll_offset

        font = load_font("cyrillic")
        draw_text_bitmap(buffer, message, x_pos, 1, self.secondary, font, scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        texts = ["НАЖМИ СТАРТ", "АРТЕФАКТ", "ТВОЯ СУДЬБА?"]
        idx = int(self._time / 2000) % len(texts)
        return texts[idx].center(16)

    def _render_mystical_eye(self, buffer: NDArray[np.uint8], cx: int, cy: int) -> None:
        """Render an animated mystical eye inside the crystal ball."""
        # Eye dimensions
        eye_width = 24
        eye_height = 14

        # Don't render if blinking
        if self.is_blinking:
            # Draw closed eye (horizontal line)
            for x in range(-eye_width // 2, eye_width // 2 + 1):
                px = cx + x
                if 0 <= px < buffer.shape[1]:
                    buffer[cy, px] = self.secondary
            return

        # Eye shape (almond) - top arc
        for angle in range(-90, 91, 5):
            rad = math.radians(angle)
            x = int(cx + eye_width // 2 * math.cos(rad))
            y = int(cy - eye_height // 2 * math.sin(rad) * (1 if angle != 0 else 0.5))
            if 0 <= x < buffer.shape[1] and 0 <= y < buffer.shape[0]:
                buffer[y, x] = self.secondary

        # Bottom arc
        for angle in range(-90, 91, 5):
            rad = math.radians(angle)
            x = int(cx + eye_width // 2 * math.cos(rad))
            y = int(cy + eye_height // 2 * math.sin(rad) * (1 if angle != 0 else 0.5))
            if 0 <= x < buffer.shape[1] and 0 <= y < buffer.shape[0]:
                buffer[y, x] = self.secondary

        # Eyeball (white) - smaller than eye shape
        iris_radius = 8
        for r in range(iris_radius, 0, -1):
            brightness = 0.5 + 0.5 * (r / iris_radius)
            color = tuple(int(200 * brightness) for _ in range(3))
            draw_circle(buffer, cx, cy, r, color)

        # Iris (colored) with movement
        iris_x = int(cx + self.eye_offset_x)
        iris_y = int(cy + self.eye_offset_y)
        iris_size = 6

        # Iris gradient (golden to purple)
        for r in range(iris_size, 0, -1):
            factor = r / iris_size
            color = self._interpolate_color(self.primary, self.secondary, factor)
            draw_circle(buffer, iris_x, iris_y, r, color)

        # Pupil (black with glow)
        pupil_x = int(iris_x + self.eye_offset_x * 0.3)
        pupil_y = int(iris_y + self.eye_offset_y * 0.3)
        draw_circle(buffer, pupil_x, pupil_y, 3, (10, 10, 20))

        # Pupil highlight (makes it look alive)
        highlight_x = pupil_x - 1
        highlight_y = pupil_y - 1
        if 0 <= highlight_x < buffer.shape[1] and 0 <= highlight_y < buffer.shape[0]:
            buffer[highlight_y, highlight_x] = (255, 255, 255)

    def _interpolate_color(
        self,
        c1: Tuple[int, int, int],
        c2: Tuple[int, int, int],
        t: float
    ) -> Tuple[int, int, int]:
        """Interpolate between two colors."""
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


class ArcadeIdleAnimation(IdleAnimation):
    """Arcade/retro game style idle animation.

    Features:
    - Flashing border chase lights
    - Bouncing logo
    - Scanline effect
    - High score display
    """

    def __init__(self, config: IdleAnimationConfig):
        super().__init__(config)

        # Colors
        self.primary = (236, 72, 153)    # Neon pink
        self.secondary = (6, 182, 212)   # Cyan
        self.accent = (251, 191, 36)     # Yellow
        self.bg = (0, 0, 0)              # Black

        # Logo position
        self.logo_x = config.main_width // 2
        self.logo_y = 40
        self.logo_vy = 0.0
        self.logo_bounce_y = 40

        # Border light positions
        self.border_lights = self._generate_border_lights()
        self.light_index = 0

    def _generate_border_lights(self) -> list:
        """Generate positions for border chase lights."""
        lights = []
        w, h = self.config.main_width, self.config.main_height
        spacing = 8

        # Top edge
        for x in range(0, w, spacing):
            lights.append((x, 0))
        # Right edge
        for y in range(0, h, spacing):
            lights.append((w - 1, y))
        # Bottom edge (reversed)
        for x in range(w - 1, -1, -spacing):
            lights.append((x, h - 1))
        # Left edge (reversed)
        for y in range(h - 1, -1, -spacing):
            lights.append((0, y))

        return lights

    def update(self, delta_ms: float) -> None:
        """Update arcade animation."""
        super().update(delta_ms)

        # Update border light chase
        if self._frame % 3 == 0:
            self.light_index = (self.light_index + 1) % len(self.border_lights)

        # Update logo bounce
        self.logo_vy += 0.1  # Gravity
        self.logo_bounce_y += self.logo_vy

        if self.logo_bounce_y > 60:
            self.logo_bounce_y = 60
            self.logo_vy = -3  # Bounce!

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render arcade idle animation."""
        fill(buffer, self.bg)

        # Scanlines
        for y in range(0, self.config.main_height, 2):
            buffer[y, :] = tuple(max(0, c - 20) for c in buffer[y, 0])

        # Border chase lights
        for i, (x, y) in enumerate(self.border_lights):
            dist = (i - self.light_index) % len(self.border_lights)
            if dist < 5:
                brightness = 1.0 - dist / 5
                color = tuple(int(c * brightness) for c in self.primary)
                draw_rect(buffer, x - 2, y - 2, 4, 4, color)

        # Flashing "ARTIFACT" logo
        if self._frame % 60 < 40:
            font = load_font("cyrillic")
            text = "АРТЕФАКТ"
            text_width, _ = font.measure_text(text)
            x = (self.config.main_width - text_width * 3) // 2
            y = int(self.logo_bounce_y)

            # Shadow
            draw_text_bitmap(buffer, text, x + 2, y + 2, (50, 50, 50), font, scale=3)
            # Main text
            draw_text_bitmap(buffer, text, x, y, self.accent, font, scale=3)

        # High score display
        font = load_font("cyrillic")
        draw_text_bitmap(buffer, "РЕКОРД", 35, 90, self.secondary, font, scale=1)
        draw_text_bitmap(buffer, "999999", 35, 100, self.primary, font, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker with chase effect."""
        clear(buffer)

        # Chasing color blocks
        block_width = 6
        for i in range(self.config.ticker_width // block_width + 1):
            x = i * block_width
            phase = (i + int(self._time / 100)) % 3
            colors = [self.primary, self.secondary, self.accent]
            color = colors[phase]
            draw_rect(buffer, x, 0, block_width - 1, self.config.ticker_height, color)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self._frame % 120 < 60:
            return "АРТЕФАКТ".center(16)
        else:
            return "НАЖМИ СТАРТ".center(16)


class ModernIdleAnimation(IdleAnimation):
    """Modern/minimalist style idle animation.

    Features:
    - Smooth gradient shifts
    - Minimal particle accents
    - Clean geometric patterns
    - Neural network-like connections
    """

    def __init__(self, config: IdleAnimationConfig):
        super().__init__(config)

        # Colors
        self.primary = (59, 130, 246)    # Blue
        self.secondary = (100, 116, 139)  # Slate
        self.accent = (34, 197, 94)      # Green
        self.bg = (24, 24, 27)           # Dark gray

        # Geometric pattern points
        self.nodes = self._generate_nodes(12)
        self.connections = self._generate_connections()

    def _generate_nodes(self, count: int) -> list:
        """Generate random node positions."""
        nodes = []
        for _ in range(count):
            x = random.randint(20, self.config.main_width - 20)
            y = random.randint(20, self.config.main_height - 20)
            vx = random.uniform(-0.2, 0.2)
            vy = random.uniform(-0.2, 0.2)
            nodes.append([x, y, vx, vy])
        return nodes

    def _generate_connections(self) -> list:
        """Generate node connections based on proximity."""
        connections = []
        for i in range(len(self.nodes)):
            for j in range(i + 1, len(self.nodes)):
                dist = self._distance(self.nodes[i], self.nodes[j])
                if dist < 50:
                    connections.append((i, j))
        return connections

    def _distance(self, n1: list, n2: list) -> float:
        """Calculate distance between two nodes."""
        return math.sqrt((n1[0] - n2[0]) ** 2 + (n1[1] - n2[1]) ** 2)

    def update(self, delta_ms: float) -> None:
        """Update modern animation."""
        super().update(delta_ms)

        # Move nodes slowly
        for node in self.nodes:
            node[0] += node[2] * delta_ms / 16
            node[1] += node[3] * delta_ms / 16

            # Bounce off edges
            if node[0] < 10 or node[0] > self.config.main_width - 10:
                node[2] *= -1
            if node[1] < 10 or node[1] > self.config.main_height - 10:
                node[3] *= -1

        # Recalculate connections periodically
        if self._frame % 60 == 0:
            self.connections = self._generate_connections()

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render modern idle animation."""
        fill(buffer, self.bg)

        # Draw connections
        for i, j in self.connections:
            n1, n2 = self.nodes[i], self.nodes[j]
            dist = self._distance(n1, n2)
            alpha = max(0, 1 - dist / 50)
            color = tuple(int(c * alpha * 0.5) for c in self.primary)
            self._draw_line(buffer, int(n1[0]), int(n1[1]), int(n2[0]), int(n2[1]), color)

        # Draw nodes
        for node in self.nodes:
            x, y = int(node[0]), int(node[1])
            draw_circle(buffer, x, y, 3, self.primary)
            draw_circle(buffer, x, y, 2, self.accent)

        # Central text
        font = load_font("cyrillic")
        text = "АРТЕФАКТ"
        text_width, _ = font.measure_text(text)
        x = (self.config.main_width - text_width * 2) // 2
        draw_text_bitmap(buffer, text, x, 55, self.primary, font, scale=2)

        # Subtitle
        sub = "ИИ ПРОРОК"
        sub_width, _ = font.measure_text(sub)
        x = (self.config.main_width - sub_width) // 2
        draw_text_bitmap(buffer, sub, x, 75, self.secondary, font, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker with gradient."""
        # Gradient background
        for x in range(self.config.ticker_width):
            phase = (x + int(self._time / 20)) % 48
            intensity = abs(24 - phase) / 24
            color = tuple(int(c * intensity * 0.3) for c in self.primary)
            buffer[:, x] = color

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        return "НАЖМИ СТАРТ".center(16)[:16]

    def _draw_line(
        self,
        buffer: NDArray[np.uint8],
        x1: int, y1: int,
        x2: int, y2: int,
        color: tuple
    ) -> None:
        """Draw a line using basic Bresenham."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        h, w = buffer.shape[:2]
        x, y = x1, y1

        while True:
            if 0 <= x < w and 0 <= y < h:
                buffer[y, x] = color

            if x == x2 and y == y2:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy


# Factory function
def create_idle_animation(style: str, config: IdleAnimationConfig = None) -> IdleAnimation:
    """Create an idle animation for the specified style.

    Args:
        style: Animation style ("mystical", "arcade", "modern")
        config: Optional configuration

    Returns:
        IdleAnimation instance
    """
    if config is None:
        config = IdleAnimationConfig(style=style)
    else:
        config.style = style

    animations = {
        "mystical": MysticalIdleAnimation,
        "arcade": ArcadeIdleAnimation,
        "modern": ModernIdleAnimation,
    }

    cls = animations.get(style, MysticalIdleAnimation)
    return cls(config)

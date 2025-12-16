"""Reveal effects for dramatic result presentations.

This module provides stunning reveal animations for result screens:
- Confetti explosion
- Light burst effect
- Sparkle shower
- Radial reveal (circle expanding)
- Scanline reveal (retro style)
- Particle celebration
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import random
import numpy as np
from numpy.typing import NDArray

from artifact.graphics.primitives import draw_circle, draw_rect, draw_line
from artifact.graphics.text_utils import hsv_to_rgb


class RevealStyle(Enum):
    """Available reveal animation styles."""
    CONFETTI = auto()
    LIGHT_BURST = auto()
    SPARKLE_SHOWER = auto()
    RADIAL_WIPE = auto()
    SCANLINE = auto()
    CELEBRATION = auto()
    MYSTICAL = auto()


@dataclass
class Particle:
    """A single particle for effects."""
    x: float
    y: float
    vx: float
    vy: float
    size: float
    color: Tuple[int, int, int]
    life: float = 1.0
    rotation: float = 0.0
    angular_velocity: float = 0.0
    gravity: float = 0.0
    fade_rate: float = 0.001


@dataclass
class Sparkle:
    """A sparkle effect point."""
    x: int
    y: int
    phase: float
    size: int
    color: Tuple[int, int, int]
    duration: float


class RevealAnimator:
    """Handles dramatic reveal animations for result screens.

    Usage:
        animator = RevealAnimator()
        animator.start_reveal(RevealStyle.CONFETTI)

        # In update loop:
        animator.update(delta_ms)

        # In render:
        animator.render_overlay(buffer)

        # Check if reveal is complete:
        if animator.is_complete:
            # Show actual content
    """

    def __init__(self):
        self.style = RevealStyle.CONFETTI
        self.active = False
        self.progress = 0.0  # 0 to 1
        self.duration = 1500.0  # ms
        self.time_elapsed = 0.0

        # Particles for various effects
        self.particles: List[Particle] = []
        self.sparkles: List[Sparkle] = []

        # Effect-specific state
        self._burst_rings: List[dict] = []
        self._scanline_y = 0.0
        self._radial_radius = 0.0
        self._mystical_symbols: List[dict] = []

        # Colors
        self.celebration_colors = [
            (255, 215, 0),   # Gold
            (255, 100, 100), # Pink
            (100, 255, 100), # Green
            (100, 200, 255), # Cyan
            (255, 150, 50),  # Orange
            (200, 100, 255), # Purple
        ]

        self.mystical_colors = [
            (147, 51, 234),  # Purple
            (251, 191, 36),  # Gold
            (59, 130, 246),  # Blue
            (236, 72, 153),  # Pink
        ]

    @property
    def is_complete(self) -> bool:
        """Check if reveal animation is complete."""
        return self.progress >= 1.0

    @property
    def is_active(self) -> bool:
        """Check if reveal is currently animating."""
        return self.active and not self.is_complete

    def start_reveal(self, style: RevealStyle = RevealStyle.CONFETTI,
                     duration: float = 1500.0) -> None:
        """Start a new reveal animation.

        Args:
            style: The reveal animation style to use
            duration: How long the reveal should take in milliseconds
        """
        self.style = style
        self.duration = duration
        self.active = True
        self.progress = 0.0
        self.time_elapsed = 0.0
        self.particles = []
        self.sparkles = []
        self._burst_rings = []
        self._mystical_symbols = []

        # Initialize style-specific elements
        if style == RevealStyle.CONFETTI:
            self._spawn_confetti(100)
        elif style == RevealStyle.LIGHT_BURST:
            self._init_light_burst()
        elif style == RevealStyle.SPARKLE_SHOWER:
            self._spawn_sparkles(50)
        elif style == RevealStyle.RADIAL_WIPE:
            self._radial_radius = 0.0
        elif style == RevealStyle.SCANLINE:
            self._scanline_y = 0.0
        elif style == RevealStyle.CELEBRATION:
            self._spawn_confetti(60)
            self._spawn_sparkles(30)
        elif style == RevealStyle.MYSTICAL:
            self._init_mystical()

    def update(self, delta_ms: float) -> None:
        """Update the reveal animation state."""
        if not self.active:
            return

        self.time_elapsed += delta_ms
        self.progress = min(1.0, self.time_elapsed / self.duration)

        # Update particles
        for particle in self.particles:
            particle.x += particle.vx * delta_ms / 16
            particle.y += particle.vy * delta_ms / 16
            particle.vy += particle.gravity * delta_ms / 16
            particle.rotation += particle.angular_velocity * delta_ms / 16
            particle.life -= particle.fade_rate * delta_ms

        # Remove dead particles
        self.particles = [p for p in self.particles if p.life > 0 and p.y < 140]

        # Update sparkles
        for sparkle in self.sparkles:
            sparkle.phase += delta_ms / 100
            sparkle.duration -= delta_ms

        # Remove expired sparkles
        self.sparkles = [s for s in self.sparkles if s.duration > 0]

        # Style-specific updates
        if self.style == RevealStyle.LIGHT_BURST:
            self._update_light_burst(delta_ms)
        elif self.style == RevealStyle.RADIAL_WIPE:
            self._radial_radius = self.progress * 100
        elif self.style == RevealStyle.SCANLINE:
            self._scanline_y = self.progress * 128
        elif self.style == RevealStyle.MYSTICAL:
            self._update_mystical(delta_ms)

        # Spawn more particles during animation
        if self.style in (RevealStyle.CONFETTI, RevealStyle.CELEBRATION):
            if random.random() < 0.3 and self.progress < 0.7:
                self._spawn_confetti(5)

        if self.style in (RevealStyle.SPARKLE_SHOWER, RevealStyle.CELEBRATION):
            if random.random() < 0.4 and self.progress < 0.8:
                self._spawn_sparkles(3)

    def render_overlay(self, buffer: NDArray[np.uint8]) -> None:
        """Render the reveal effect overlay on top of the buffer."""
        if not self.active:
            return

        if self.style == RevealStyle.CONFETTI:
            self._render_confetti(buffer)
        elif self.style == RevealStyle.LIGHT_BURST:
            self._render_light_burst(buffer)
        elif self.style == RevealStyle.SPARKLE_SHOWER:
            self._render_sparkles(buffer)
        elif self.style == RevealStyle.RADIAL_WIPE:
            self._render_radial_wipe(buffer)
        elif self.style == RevealStyle.SCANLINE:
            self._render_scanline(buffer)
        elif self.style == RevealStyle.CELEBRATION:
            self._render_confetti(buffer)
            self._render_sparkles(buffer)
        elif self.style == RevealStyle.MYSTICAL:
            self._render_mystical(buffer)

    def render_mask(self, buffer: NDArray[np.uint8],
                    content_buffer: NDArray[np.uint8]) -> None:
        """Render with a reveal mask (for radial/scanline reveals).

        Args:
            buffer: The output buffer
            content_buffer: The content to reveal
        """
        if self.style == RevealStyle.RADIAL_WIPE:
            cx, cy = 64, 64
            for y in range(128):
                for x in range(128):
                    dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    if dist <= self._radial_radius:
                        buffer[y, x] = content_buffer[y, x]

        elif self.style == RevealStyle.SCANLINE:
            reveal_y = int(self._scanline_y)
            buffer[:reveal_y, :] = content_buffer[:reveal_y, :]

    # =========================================================================
    # CONFETTI EFFECT
    # =========================================================================

    def _spawn_confetti(self, count: int) -> None:
        """Spawn confetti particles."""
        for _ in range(count):
            # Start from top/center
            x = random.uniform(30, 98)
            y = random.uniform(-20, 20)

            # Random velocities - mostly outward and down
            angle = random.uniform(math.pi * 0.1, math.pi * 0.9)
            speed = random.uniform(2, 6)
            vx = math.cos(angle) * speed * random.choice([-1, 1])
            vy = math.sin(angle) * speed

            color = random.choice(self.celebration_colors)

            self.particles.append(Particle(
                x=x, y=y, vx=vx, vy=vy,
                size=random.uniform(2, 5),
                color=color,
                life=1.0,
                rotation=random.uniform(0, math.pi * 2),
                angular_velocity=random.uniform(-0.2, 0.2),
                gravity=0.15,
                fade_rate=0.0008
            ))

    def _render_confetti(self, buffer: NDArray[np.uint8]) -> None:
        """Render confetti particles."""
        for particle in self.particles:
            px, py = int(particle.x), int(particle.y)
            if 0 <= px < 128 and 0 <= py < 128:
                size = int(particle.size * particle.life)
                alpha = particle.life
                color = (
                    int(particle.color[0] * alpha),
                    int(particle.color[1] * alpha),
                    int(particle.color[2] * alpha),
                )

                # Draw rotated rectangle (confetti piece)
                if size >= 2:
                    # Simple rectangle representation
                    for dy in range(-size // 2, size // 2 + 1):
                        for dx in range(-size // 2, size // 2 + 1):
                            # Apply rotation
                            rx = int(dx * math.cos(particle.rotation) - dy * math.sin(particle.rotation))
                            ry = int(dx * math.sin(particle.rotation) + dy * math.cos(particle.rotation))
                            fx, fy = px + rx, py + ry
                            if 0 <= fx < 128 and 0 <= fy < 128:
                                buffer[fy, fx] = color
                else:
                    buffer[py, px] = color

    # =========================================================================
    # LIGHT BURST EFFECT
    # =========================================================================

    def _init_light_burst(self) -> None:
        """Initialize light burst rings."""
        self._burst_rings = [
            {"radius": 0, "max_radius": 80, "speed": 3.0, "color": (255, 255, 255)},
            {"radius": 0, "max_radius": 70, "speed": 2.5, "color": (255, 215, 0)},
            {"radius": 0, "max_radius": 60, "speed": 2.0, "color": (255, 150, 50)},
        ]

    def _update_light_burst(self, delta_ms: float) -> None:
        """Update light burst rings."""
        for i, ring in enumerate(self._burst_rings):
            delay = i * 100  # Stagger ring expansion
            if self.time_elapsed > delay:
                ring["radius"] += ring["speed"] * delta_ms / 16
                ring["radius"] = min(ring["radius"], ring["max_radius"])

    def _render_light_burst(self, buffer: NDArray[np.uint8]) -> None:
        """Render expanding light burst rings."""
        cx, cy = 64, 64

        # Central flash (fades out)
        flash_alpha = max(0, 1 - self.progress * 2)
        if flash_alpha > 0:
            for r in range(20, 0, -2):
                alpha = flash_alpha * (1 - r / 20)
                color = (int(255 * alpha), int(255 * alpha), int(200 * alpha))
                draw_circle(buffer, cx, cy, r, color)

        # Expanding rings
        for ring in self._burst_rings:
            radius = int(ring["radius"])
            if radius > 0:
                alpha = 1 - (radius / ring["max_radius"])
                color = ring["color"]
                ring_color = (
                    int(color[0] * alpha),
                    int(color[1] * alpha),
                    int(color[2] * alpha),
                )

                # Draw ring as circle outline
                for angle in range(0, 360, 3):
                    rad = math.radians(angle)
                    px = int(cx + radius * math.cos(rad))
                    py = int(cy + radius * math.sin(rad))
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = ring_color

    # =========================================================================
    # SPARKLE SHOWER EFFECT
    # =========================================================================

    def _spawn_sparkles(self, count: int) -> None:
        """Spawn sparkle effects."""
        for _ in range(count):
            self.sparkles.append(Sparkle(
                x=random.randint(5, 122),
                y=random.randint(5, 122),
                phase=random.uniform(0, math.pi * 2),
                size=random.randint(1, 3),
                color=random.choice(self.celebration_colors),
                duration=random.uniform(300, 800)
            ))

    def _render_sparkles(self, buffer: NDArray[np.uint8]) -> None:
        """Render sparkle effects."""
        for sparkle in self.sparkles:
            # Pulsing brightness
            brightness = 0.5 + 0.5 * math.sin(sparkle.phase)
            alpha = min(1.0, sparkle.duration / 200)  # Fade out

            color = (
                int(sparkle.color[0] * brightness * alpha),
                int(sparkle.color[1] * brightness * alpha),
                int(sparkle.color[2] * brightness * alpha),
            )

            x, y = sparkle.x, sparkle.y
            size = sparkle.size

            # Draw star shape
            if 0 <= x < 128 and 0 <= y < 128:
                buffer[y, x] = color
                # Cross pattern
                for d in range(1, size + 1):
                    for dx, dy in [(d, 0), (-d, 0), (0, d), (0, -d)]:
                        px, py = x + dx, y + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            fade = 1 - d / (size + 1)
                            buffer[py, px] = (
                                int(color[0] * fade),
                                int(color[1] * fade),
                                int(color[2] * fade),
                            )

    # =========================================================================
    # RADIAL WIPE EFFECT
    # =========================================================================

    def _render_radial_wipe(self, buffer: NDArray[np.uint8]) -> None:
        """Render radial wipe edge glow."""
        cx, cy = 64, 64
        radius = self._radial_radius

        # Draw glowing edge at current radius
        for angle in range(0, 360, 2):
            rad = math.radians(angle)
            # Multiple rings for glow effect
            for offset in range(-3, 4):
                r = radius + offset
                if r > 0:
                    px = int(cx + r * math.cos(rad))
                    py = int(cy + r * math.sin(rad))
                    if 0 <= px < 128 and 0 <= py < 128:
                        glow = 1 - abs(offset) / 4
                        color = (
                            int(255 * glow),
                            int(200 * glow),
                            int(100 * glow),
                        )
                        # Additive blend
                        existing = buffer[py, px]
                        buffer[py, px] = (
                            min(255, existing[0] + color[0] // 2),
                            min(255, existing[1] + color[1] // 2),
                            min(255, existing[2] + color[2] // 2),
                        )

    # =========================================================================
    # SCANLINE EFFECT
    # =========================================================================

    def _render_scanline(self, buffer: NDArray[np.uint8]) -> None:
        """Render scanline reveal effect."""
        reveal_y = int(self._scanline_y)

        # Glowing scanline
        for y_offset in range(-4, 5):
            line_y = reveal_y + y_offset
            if 0 <= line_y < 128:
                glow = 1 - abs(y_offset) / 5
                for x in range(128):
                    existing = buffer[line_y, x]
                    color = (
                        min(255, existing[0] + int(100 * glow)),
                        min(255, existing[1] + int(255 * glow)),
                        min(255, existing[2] + int(100 * glow)),
                    )
                    buffer[line_y, x] = color

    # =========================================================================
    # MYSTICAL EFFECT
    # =========================================================================

    def _init_mystical(self) -> None:
        """Initialize mystical reveal effect."""
        # Orbiting symbols
        symbols = ["★", "◆", "●", "✦", "❖"]
        for i in range(8):
            angle = (i / 8) * math.pi * 2
            self._mystical_symbols.append({
                "angle": angle,
                "radius": 40,
                "symbol": random.choice(symbols),
                "color": random.choice(self.mystical_colors),
                "pulse_phase": random.uniform(0, math.pi * 2),
            })

        # Spawn mystical particles
        for _ in range(30):
            angle = random.uniform(0, math.pi * 2)
            radius = random.uniform(10, 60)
            self.particles.append(Particle(
                x=64 + radius * math.cos(angle),
                y=64 + radius * math.sin(angle),
                vx=random.uniform(-0.5, 0.5),
                vy=random.uniform(-1, -0.3),
                size=random.uniform(1, 3),
                color=random.choice(self.mystical_colors),
                life=1.0,
                gravity=-0.02,  # Float upward
                fade_rate=0.001
            ))

    def _update_mystical(self, delta_ms: float) -> None:
        """Update mystical effect."""
        for symbol in self._mystical_symbols:
            symbol["angle"] += delta_ms / 2000
            symbol["radius"] = 40 + 10 * math.sin(self.time_elapsed / 300)
            symbol["pulse_phase"] += delta_ms / 150

        # Spawn more particles
        if random.random() < 0.15 and self.progress < 0.8:
            angle = random.uniform(0, math.pi * 2)
            self.particles.append(Particle(
                x=64 + 50 * math.cos(angle),
                y=64 + 50 * math.sin(angle),
                vx=random.uniform(-0.3, 0.3),
                vy=random.uniform(-0.8, -0.2),
                size=random.uniform(1, 2),
                color=random.choice(self.mystical_colors),
                life=1.0,
                gravity=-0.01,
                fade_rate=0.002
            ))

    def _render_mystical(self, buffer: NDArray[np.uint8]) -> None:
        """Render mystical reveal effect."""
        cx, cy = 64, 64
        t = self.time_elapsed

        # Central glow pulse
        pulse = 0.5 + 0.5 * math.sin(t / 200)
        for r in range(30, 5, -2):
            alpha = (1 - r / 30) * pulse * (1 - self.progress * 0.5)
            color = (
                int(147 * alpha),
                int(51 * alpha),
                int(234 * alpha),
            )
            draw_circle(buffer, cx, cy, r, color)

        # Orbiting symbols (render as colored dots since we can't render unicode)
        for symbol in self._mystical_symbols:
            angle = symbol["angle"]
            radius = symbol["radius"]
            px = int(cx + radius * math.cos(angle))
            py = int(cy + radius * math.sin(angle))

            if 0 <= px < 128 and 0 <= py < 128:
                pulse_brightness = 0.5 + 0.5 * math.sin(symbol["pulse_phase"])
                color = symbol["color"]
                bright_color = (
                    int(color[0] * pulse_brightness),
                    int(color[1] * pulse_brightness),
                    int(color[2] * pulse_brightness),
                )
                # Draw as small glowing dot
                draw_circle(buffer, px, py, 3, bright_color)
                buffer[py, px] = (255, 255, 255)

        # Render mystical particles (floating upward)
        for particle in self.particles:
            px, py = int(particle.x), int(particle.y)
            if 0 <= px < 128 and 0 <= py < 128:
                alpha = particle.life
                color = (
                    int(particle.color[0] * alpha),
                    int(particle.color[1] * alpha),
                    int(particle.color[2] * alpha),
                )
                size = int(particle.size)
                if size >= 2:
                    draw_circle(buffer, px, py, size, color)
                else:
                    buffer[py, px] = color


# Convenience function for quick reveals
def create_reveal(style: str = "confetti", duration: float = 1500.0) -> RevealAnimator:
    """Create a reveal animator with the specified style.

    Args:
        style: One of "confetti", "burst", "sparkle", "radial", "scanline",
               "celebration", "mystical"
        duration: Animation duration in milliseconds

    Returns:
        A configured RevealAnimator ready to start
    """
    style_map = {
        "confetti": RevealStyle.CONFETTI,
        "burst": RevealStyle.LIGHT_BURST,
        "sparkle": RevealStyle.SPARKLE_SHOWER,
        "radial": RevealStyle.RADIAL_WIPE,
        "scanline": RevealStyle.SCANLINE,
        "celebration": RevealStyle.CELEBRATION,
        "mystical": RevealStyle.MYSTICAL,
    }

    animator = RevealAnimator()
    reveal_style = style_map.get(style.lower(), RevealStyle.CONFETTI)
    animator.start_reveal(reveal_style, duration)
    return animator

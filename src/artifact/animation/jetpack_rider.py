"""Neon Pulse - Stylish animated loading screen for BOILING ROOM.

Full-screen BOILING ROOM logo with subtle warping distortion,
ambient particles, and burst effects on button press.
"""

import math
import os
import random
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

try:
    from PIL import Image as PILImage
except ImportError:
    PILImage = None


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    color: tuple


@dataclass
class Ring:
    cx: float
    cy: float
    radius: float
    life: float


@dataclass
class PulseState:
    time: float = 0.0
    sparks: List[Spark] = field(default_factory=list)
    rings: List[Ring] = field(default_factory=list)
    press_count: int = 0
    last_press_time: float = -9999.0
    ambient: List[Spark] = field(default_factory=list)
    score: int = 0
    high_score: int = 0
    has_interacted: bool = False
    game_over: bool = False


class JetpackRider:
    """Neon pulse loading animation with BOILING ROOM logo."""

    CYAN = (0, 255, 220)
    MAGENTA = (255, 0, 180)
    ORANGE = (255, 140, 0)
    WHITE = (240, 240, 255)
    BG = (6, 3, 15)

    def __init__(self):
        self._state = PulseState()
        self._logo: Optional[NDArray] = None  # RGBA 128x128
        self._logo_rgb: Optional[NDArray] = None
        self._logo_alpha: Optional[NDArray] = None
        self._load_logo()
        self._init_ambient()

    def _load_logo(self):
        if PILImage is None:
            return
        # Get logo filename from current theme
        from artifact.modes.photobooth_themes import get_current_theme
        theme = get_current_theme()
        logo_filename = theme.logo_filename  # e.g., "tripvenice.png" or "boilingroom.png"
        
        # Try multiple paths
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "images", logo_filename),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", logo_filename),
        ]
        for path in candidates:
            path = os.path.normpath(path)
            if os.path.exists(path):
                img = PILImage.open(path).convert("RGBA")
                img = img.resize((128, 128), PILImage.Resampling.LANCZOS)
                arr = np.array(img, dtype=np.uint8)
                self._logo = arr
                self._logo_rgb = arr[:, :, :3].astype(np.float32)
                self._logo_alpha = arr[:, :, 3].astype(np.float32) / 255.0
                break

    def _init_ambient(self):
        for _ in range(15):
            self._state.ambient.append(Spark(
                x=random.uniform(0, 128),
                y=random.uniform(0, 128),
                vx=random.uniform(-3, 3),
                vy=random.uniform(-8, -2),
                life=random.uniform(0.3, 1.0),
                color=self.CYAN if random.random() > 0.3 else self.MAGENTA,
            ))

    def reset(self) -> None:
        old_hs = self._state.high_score
        self._state = PulseState()
        self._state.high_score = old_hs
        self._init_ambient()

    @property
    def is_game_over(self) -> bool:
        return False

    @property
    def score(self) -> int:
        return self._state.score

    @property
    def high_score(self) -> int:
        return self._state.high_score

    def handle_jump(self) -> bool:
        s = self._state
        s.has_interacted = True
        s.press_count += 1
        s.last_press_time = s.time

        cx, cy = 64.0, 64.0
        for _ in range(25):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(30, 120)
            self._state.sparks.append(Spark(
                x=cx + random.uniform(-4, 4),
                y=cy + random.uniform(-4, 4),
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=1.0,
                color=random.choice([self.CYAN, self.MAGENTA, self.ORANGE, self.WHITE]),
            ))
        s.rings.append(Ring(cx=cx, cy=cy, radius=5.0, life=1.0))
        return True

    def handle_shoot(self) -> bool:
        return self.handle_jump()

    def update(self, delta_ms: float) -> None:
        s = self._state
        dt = delta_ms / 1000.0
        s.time += delta_ms
        s.score = int(s.time / 50)
        if s.score > s.high_score:
            s.high_score = s.score

        for p in s.sparks:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 40 * dt
            p.life -= dt * 1.8
        s.sparks = [p for p in s.sparks if p.life > 0]

        for r in s.rings:
            r.radius += 80 * dt
            r.life -= dt * 1.5
        s.rings = [r for r in s.rings if r.life > 0]

        for p in s.ambient:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.life -= dt * 0.3
        s.ambient = [p for p in s.ambient if p.life > 0]
        while len(s.ambient) < 15:
            s.ambient.append(Spark(
                x=random.uniform(0, 128),
                y=128 + random.uniform(0, 10),
                vx=random.uniform(-3, 3),
                vy=random.uniform(-12, -4),
                life=random.uniform(0.6, 1.0),
                color=self.CYAN if random.random() > 0.3 else self.MAGENTA,
            ))

    def render(self, buffer: NDArray[np.uint8], background: Optional[NDArray[np.uint8]] = None) -> None:
        s = self._state
        h, w = buffer.shape[:2]

        # Dark background
        buffer[:] = self.BG

        # Draw logo with subtle warp distortion
        if self._logo_rgb is not None:
            self._render_warped_logo(buffer, s.time)

        # Ambient particles
        for p in s.ambient:
            px, py = int(p.x), int(p.y)
            if 0 <= px < w and 0 <= py < h:
                a = min(1.0, p.life) * 0.5
                buffer[py, px] = (
                    min(255, int(buffer[py, px, 0] + p.color[0] * a)),
                    min(255, int(buffer[py, px, 1] + p.color[1] * a)),
                    min(255, int(buffer[py, px, 2] + p.color[2] * a)),
                )

        # Expanding rings
        for ring in s.rings:
            a = ring.life
            r_int = int(ring.radius)
            color = (int(self.MAGENTA[0] * a), int(self.MAGENTA[1] * a), int(self.MAGENTA[2] * a))
            cx_i, cy_i = int(ring.cx), int(ring.cy)
            steps = max(20, r_int * 4)
            for i in range(steps):
                angle = 2 * math.pi * i / steps
                rx = int(cx_i + math.cos(angle) * r_int)
                ry = int(cy_i + math.sin(angle) * r_int)
                if 0 <= rx < w and 0 <= ry < h:
                    buffer[ry, rx] = (
                        min(255, int(buffer[ry, rx, 0]) + color[0]),
                        min(255, int(buffer[ry, rx, 1]) + color[1]),
                        min(255, int(buffer[ry, rx, 2]) + color[2]),
                    )

        # Burst sparks
        for p in s.sparks:
            px, py = int(p.x), int(p.y)
            if 0 <= px < w and 0 <= py < h:
                a = min(1.0, p.life)
                buffer[py, px] = (int(p.color[0] * a), int(p.color[1] * a), int(p.color[2] * a))
                if a > 0.5:
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < w and 0 <= ny < h:
                            buffer[ny, nx] = (
                                min(255, int(buffer[ny, nx, 0] + p.color[0] * a * 0.4)),
                                min(255, int(buffer[ny, nx, 1] + p.color[1] * a * 0.4)),
                                min(255, int(buffer[ny, nx, 2] + p.color[2] * a * 0.4)),
                            )

    def _render_warped_logo(self, buffer: NDArray[np.uint8], time_ms: float) -> None:
        """Render the logo full-screen with subtle organic warp distortion (vectorized)."""
        h, w = 128, 128
        t = time_ms / 1000.0

        pulse = 0.85 + 0.15 * math.sin(t * 0.8)
        press_flash = max(0.0, 1.0 - (time_ms - self._state.last_press_time) / 300)
        brightness = min(1.0, pulse + press_flash * 0.4)

        # Build coordinate grids once (could cache but 128x128 is tiny)
        ys = np.arange(h, dtype=np.float32)
        xs = np.arange(w, dtype=np.float32)
        yy, xx = np.meshgrid(ys, xs, indexing='ij')

        # Warp displacement - two slow sine waves
        dx = np.sin(yy * 0.08 + t * 1.2) * 1.5 + np.sin(yy * 0.15 + t * 0.7) * 0.8
        dy = np.cos(xx * 0.08 + t * 0.9) * 1.5 + np.cos(xx * 0.12 + t * 1.1) * 0.8

        sx = np.clip((xx + dx).astype(np.int32), 0, 127)
        sy = np.clip((yy + dy).astype(np.int32), 0, 127)

        # Sample logo at warped coords
        warped_rgb = self._logo_rgb[sy, sx]  # (128,128,3)
        warped_alpha = self._logo_alpha[sy, sx]  # (128,128)

        # Alpha blend: out = bg * (1-a) + logo * a * brightness
        alpha3 = warped_alpha[:, :, np.newaxis]  # (128,128,1)
        blended = buffer.astype(np.float32) * (1.0 - alpha3) + warped_rgb * alpha3 * brightness
        np.clip(blended, 0, 255, out=blended)
        np.copyto(buffer, blended.astype(np.uint8))

    def render_ticker(self, buffer: NDArray, progress: float = 0.0, time_ms: float = 0.0) -> None:
        from artifact.graphics.primitives import fill, draw_rect

        fill(buffer, (0, 0, 0))
        draw_rect(buffer, 2, 2, 44, 4, (15, 10, 30))

        if progress >= 1.0:
            display_progress = 1.0
        else:
            cycle = (time_ms % 3000.0) / 3000.0
            if cycle < 0.5:
                eased = 2 * cycle * cycle
            else:
                t = cycle - 0.5
                eased = 0.5 + (1 - (1 - 2 * t) * (1 - 2 * t)) * 0.5
            display_progress = eased

        bar_w = int(44 * display_progress)
        if bar_w > 0:
            for x in range(bar_w):
                ratio = x / 44
                r = int(0 + 255 * ratio)
                g = int(255 - 75 * ratio)
                b = int(220 - 200 * ratio)
                buffer[2:6, 2 + x] = (r, g, b)


SantaRunner = JetpackRider

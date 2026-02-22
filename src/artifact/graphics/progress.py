"""Smart progress tracking system for ARTIFACT arcade.

This module provides phase-based progress tracking that reflects actual
API call stages rather than fake time-based increments.

Phases for AI modes (Fortune, AI Prophet, Roast):
- INITIALIZING: 0-10% (setup, camera warmup)
- ANALYZING: 10-40% (photo analysis, face detection)
- GENERATING_TEXT: 40-70% (prediction text generation)
- GENERATING_IMAGE: 70-95% (caricature/image generation)
- FINALIZING: 95-100% (cleanup, result preparation)
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Tuple, List, Callable, Dict
import math
import random

import numpy as np
from numpy.typing import NDArray


class ProgressPhase(Enum):
    """Progress phases for AI modes."""
    INITIALIZING = auto()      # 0-10%
    ANALYZING = auto()         # 10-40%
    GENERATING_TEXT = auto()   # 40-70%
    GENERATING_IMAGE = auto()  # 70-95%
    FINALIZING = auto()        # 95-100%
    COMPLETE = auto()          # 100%


# Phase ranges (min%, max%)
PHASE_RANGES = {
    ProgressPhase.INITIALIZING: (0.0, 0.10),
    ProgressPhase.ANALYZING: (0.10, 0.40),
    ProgressPhase.GENERATING_TEXT: (0.40, 0.70),
    ProgressPhase.GENERATING_IMAGE: (0.70, 0.95),
    ProgressPhase.FINALIZING: (0.95, 1.0),
    ProgressPhase.COMPLETE: (1.0, 1.0),
}

# Status messages per phase (Russian) - Clear instructions for users
# More varied and fun messages to keep people engaged
PHASE_MESSAGES = {
    ProgressPhase.INITIALIZING: [
        "Подготовка...",
        "Сейчас начнётся!",
        "Секунду...",
        "Запускаем магию...",
    ],
    ProgressPhase.ANALYZING: [
        "Жди, не уходи!",
        "Ожидание ~1 мин",
        "Не уходи, фотка топ!",
        "ИИ думает...",
        "Почти...",
        "Создаём шедевр!",
        "Это стоит ждать!",
        "Будет огонь!",
    ],
    ProgressPhase.GENERATING_TEXT: [
        "Скоро будет!",
        "Не уходи!",
        "Терпение...",
        "Магия работает!",
        "Фотка будет топ!",
        "Ещё чуть-чуть!",
        "Почти готово!",
        "Уже скоро!",
    ],
    ProgressPhase.GENERATING_IMAGE: [
        "Создаём фото...",
        "Скоро всё будет!",
        "Ещё немного...",
        "Последний штрих!",
        "Уже скоро!",
        "Дорисовываем...",
        "Почти готово!",
        "Это того стоит!",
    ],
    ProgressPhase.FINALIZING: [
        "Готовим к показу...",
        "Финишная прямая!",
        "Пара секунд...",
    ],
    ProgressPhase.COMPLETE: [
        "Готово! Смотри!",
        "Вуаля!",
    ],
}


@dataclass
class ProgressState:
    """Current progress state."""
    phase: ProgressPhase
    phase_progress: float  # 0.0-1.0 within current phase
    total_progress: float  # 0.0-1.0 overall
    message: str
    time_in_phase: float  # ms


class SmartProgressTracker:
    """Phase-based progress tracker with smooth animations.

    Instead of fake linear progress, this tracks actual API phases:
    - Each phase has a defined percentage range
    - Progress within phases can be set explicitly or animated
    - Provides entertaining status messages
    - Smooth interpolation for visual polish

    Usage:
        tracker = SmartProgressTracker()
        tracker.start()

        # When API call for text generation starts:
        tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)

        # In update loop:
        tracker.update(delta_ms)
        progress = tracker.get_progress()  # 0.0-1.0
        message = tracker.get_message()
    """

    def __init__(self, mode_theme: str = "default"):
        self.mode_theme = mode_theme
        self._phase = ProgressPhase.INITIALIZING
        self._phase_progress = 0.0
        self._target_progress = 0.0
        self._display_progress = 0.0  # Smoothed for display
        self._time_in_phase = 0.0
        self._total_time = 0.0
        self._message_index = 0
        self._message_change_time = 0.0
        self._started = False
        self._custom_messages: Optional[dict] = None  # Override default messages

        # Animation state for loading visuals
        self._particles: List[dict] = []
        self._pulse_phase = 0.0
        self._scan_position = 0.0
        self._shimmer_offset = 0.0  # For progress bar shimmer effect
        self._phase_transition_anim = 0.0  # Celebration animation on phase change

    def start(self) -> None:
        """Start progress tracking."""
        self._started = True
        self._phase = ProgressPhase.INITIALIZING
        self._phase_progress = 0.0
        self._target_progress = 0.0
        self._display_progress = 0.0
        self._time_in_phase = 0.0
        self._total_time = 0.0
        self._message_index = 0
        self._generate_particles()

    def reset(self) -> None:
        """Reset progress tracker."""
        self._started = False
        self._phase = ProgressPhase.INITIALIZING
        self._phase_progress = 0.0
        self._target_progress = 0.0
        self._display_progress = 0.0
        self._time_in_phase = 0.0
        self._total_time = 0.0

    def advance_to_phase(self, phase: ProgressPhase) -> None:
        """Advance to a specific phase.

        This should be called when actual API work transitions
        between stages.

        Args:
            phase: The new phase to enter
        """
        if phase.value > self._phase.value:
            self._phase = phase
            self._phase_progress = 0.0
            self._time_in_phase = 0.0
            self._message_index = 0
            self._phase_transition_anim = 1.0  # Trigger celebration animation

            # Set target to the start of this phase
            phase_min, _ = PHASE_RANGES[phase]
            self._target_progress = phase_min

    def set_phase_progress(self, progress: float) -> None:
        """Set progress within current phase.

        Args:
            progress: Progress within phase (0.0-1.0)
        """
        self._phase_progress = max(0.0, min(1.0, progress))

        # Calculate total progress
        phase_min, phase_max = PHASE_RANGES[self._phase]
        self._target_progress = phase_min + (phase_max - phase_min) * self._phase_progress

    def complete(self) -> None:
        """Mark progress as complete."""
        self._phase = ProgressPhase.COMPLETE
        self._phase_progress = 1.0
        self._target_progress = 1.0

    def update(self, delta_ms: float) -> None:
        """Update progress state.

        Args:
            delta_ms: Time since last update in milliseconds
        """
        if not self._started:
            return

        self._total_time += delta_ms
        self._time_in_phase += delta_ms

        # Smooth progress interpolation with easing
        # Use faster interpolation for a more responsive feel
        lerp_speed = 0.005 * delta_ms  # Increased from 0.003 for snappier response
        self._display_progress += (self._target_progress - self._display_progress) * lerp_speed

        # Auto-advance within phase (slow crawl to simulate work)
        if self._phase != ProgressPhase.COMPLETE:
            phase_min, phase_max = PHASE_RANGES[self._phase]
            max_auto = phase_max - 0.02  # Don't auto-complete phases

            # Slow time-based crawl (but won't exceed phase boundary)
            auto_increment = delta_ms / 30000  # Very slow
            self._target_progress = min(max_auto, self._target_progress + auto_increment)

        # Cycle through messages with smooth fading
        self._message_change_time += delta_ms
        if self._message_change_time > 2500:  # Increased to 2.5s for better readability
            messages = PHASE_MESSAGES.get(self._phase, ["..."])
            self._message_index = (self._message_index + 1) % len(messages)
            self._message_change_time = 0.0

        # Update animation state
        self._pulse_phase += delta_ms / 250  # Slightly slower pulse for premium feel
        self._scan_position = (self._scan_position + delta_ms / 12) % 128
        self._shimmer_offset = (self._shimmer_offset + delta_ms / 20) % 200

        # Decay phase transition animation
        if self._phase_transition_anim > 0:
            self._phase_transition_anim = max(0, self._phase_transition_anim - delta_ms / 500)

        # Update particles
        self._update_particles(delta_ms)

    def get_progress(self) -> float:
        """Get current display progress (0.0-1.0)."""
        return self._display_progress

    def get_raw_progress(self) -> float:
        """Get raw target progress without smoothing."""
        return self._target_progress

    def get_phase(self) -> ProgressPhase:
        """Get current phase."""
        return self._phase

    def set_custom_messages(self, custom_messages: Dict[ProgressPhase, List[str]]) -> None:
        """Set custom messages to override defaults for specific phases.

        Args:
            custom_messages: Dict mapping ProgressPhase to list of message strings
        """
        self._custom_messages = custom_messages

    def get_message(self) -> str:
        """Get current status message."""
        # Check custom messages first, then fall back to defaults
        if self._custom_messages and self._phase in self._custom_messages:
            messages = self._custom_messages[self._phase]
        else:
            messages = PHASE_MESSAGES.get(self._phase, ["..."])
        return messages[self._message_index % len(messages)]

    def get_state(self) -> ProgressState:
        """Get full progress state."""
        return ProgressState(
            phase=self._phase,
            phase_progress=self._phase_progress,
            total_progress=self._display_progress,
            message=self.get_message(),
            time_in_phase=self._time_in_phase,
        )

    def is_complete(self) -> bool:
        """Check if progress is complete."""
        return self._phase == ProgressPhase.COMPLETE

    # =========================================================================
    # VISUAL RENDERING
    # =========================================================================

    def _generate_particles(self) -> None:
        """Generate particles for loading animation."""
        self._particles = []
        for _ in range(20):
            self._particles.append({
                "x": random.uniform(0, 128),
                "y": random.uniform(0, 128),
                "vx": random.uniform(-0.5, 0.5),
                "vy": random.uniform(-1, 1),
                "size": random.randint(1, 3),
                "hue": random.uniform(0, 360),
                "life": random.uniform(0.5, 1.0),
            })

    def _update_particles(self, delta_ms: float) -> None:
        """Update particle positions."""
        for p in self._particles:
            p["x"] += p["vx"] * delta_ms / 16
            p["y"] += p["vy"] * delta_ms / 16
            p["hue"] = (p["hue"] + delta_ms / 50) % 360

            # Respawn off-screen particles
            if p["y"] < 0 or p["y"] > 128 or p["x"] < 0 or p["x"] > 128:
                p["x"] = random.uniform(0, 128)
                p["y"] = random.uniform(0, 128)
                p["life"] = random.uniform(0.5, 1.0)

    def render_progress_bar(
        self,
        buffer: NDArray[np.uint8],
        x: int,
        y: int,
        width: int,
        height: int,
        bar_color: Tuple[int, int, int] = (100, 200, 255),
        bg_color: Tuple[int, int, int] = (30, 30, 40),
        time_ms: float = 0.0,
    ) -> None:
        """Render an animated progress bar.

        Args:
            buffer: Target buffer
            x, y: Top-left position
            width, height: Bar dimensions
            bar_color: Progress bar color
            bg_color: Background color
            time_ms: Current time for animations
        """
        from artifact.graphics.primitives import draw_rect

        # Background
        draw_rect(buffer, x, y, width, height, bg_color)

        # Use looping animation instead of actual progress (unless complete)
        progress = self.get_progress()
        if progress < 1.0:
            cycle = (time_ms % 3000.0) / 3000.0
            if cycle < 0.5:
                progress = 2 * cycle * cycle
            else:
                t2 = cycle - 0.5
                progress = 0.5 + (1 - (1 - 2 * t2) * (1 - 2 * t2)) * 0.5
        fill_width = int(width * progress)

        if fill_width > 0:
            # Pulsing brightness
            pulse = 0.8 + 0.2 * math.sin(self._pulse_phase)
            pulsed_color = tuple(int(c * pulse) for c in bar_color)
            draw_rect(buffer, x, y, fill_width, height, pulsed_color)

            # Highlight at leading edge
            if fill_width > 2:
                highlight_x = x + fill_width - 2
                highlight_color = tuple(min(255, int(c * 1.5)) for c in bar_color)
                draw_rect(buffer, highlight_x, y, 2, height, highlight_color)

        # Border
        border_color = (80, 80, 100)
        # Top and bottom
        for bx in range(x, x + width):
            if 0 <= bx < 128:
                if 0 <= y < 128:
                    buffer[y, bx] = border_color
                if 0 <= y + height - 1 < 128:
                    buffer[y + height - 1, bx] = border_color
        # Left and right
        for by in range(y, y + height):
            if 0 <= by < 128:
                if 0 <= x < 128:
                    buffer[by, x] = border_color
                if 0 <= x + width - 1 < 128:
                    buffer[by, x + width - 1] = border_color

    def render_loading_animation(
        self,
        buffer: NDArray[np.uint8],
        style: str = "tech",
        time_ms: float = 0.0,
    ) -> None:
        """Render entertaining loading animation with LED demo-style effects.

        Args:
            buffer: Target buffer
            style: Animation style - supports new LED styles:
                   "plasma_vortex", "matrix_rain", "neon_grid", "quantum_field",
                   "aurora", "electric_storm", "kaleidoscope"
                   Also supports legacy: "tech", "mystical", "flames"
            time_ms: Current time
        """
        from artifact.graphics.text_utils import hsv_to_rgb
        from artifact.graphics.primitives import draw_circle

        # Check for new LED demo-style effects
        led_styles = ['plasma_vortex', 'matrix_rain', 'neon_grid', 'quantum_field',
                      'aurora', 'electric_storm', 'kaleidoscope']

        if style in led_styles:
            # Use new LED demo-style effect
            effect = get_loading_effect(style, 128)
            effect.update(16)  # ~60fps
            effect.render(buffer)
            return

        # Legacy styles for backward compatibility
        if style == "tech":
            # Scanning line effect
            scan_y = int(self._scan_position) % 128
            for x in range(128):
                if 0 <= scan_y < 128:
                    brightness = 0.3 + 0.7 * (1 - abs(x - 64) / 64)
                    color = (0, int(100 * brightness), int(150 * brightness))
                    buffer[scan_y, x] = np.clip(
                        buffer[scan_y, x].astype(np.int16) + np.array(color),
                        0, 255
                    ).astype(np.uint8)

            # Data stream particles
            for p in self._particles[:10]:
                px, py = int(p["x"]), int(p["y"])
                if 0 <= px < 128 and 0 <= py < 128:
                    color = hsv_to_rgb(180 + p["hue"] * 0.2, 0.8, p["life"])
                    buffer[py, px] = color

        elif style == "mystical":
            # Orbiting magical particles
            cx, cy = 64, 64
            for i, p in enumerate(self._particles[:12]):
                angle = self._pulse_phase * 2 + i * (math.pi * 2 / 12)
                radius = 30 + 10 * math.sin(self._pulse_phase + i)
                px = int(cx + radius * math.cos(angle))
                py = int(cy + radius * math.sin(angle))
                if 0 <= px < 128 and 0 <= py < 128:
                    color = hsv_to_rgb(280 + i * 10, 0.7, p["life"])
                    draw_circle(buffer, px, py, p["size"], color)

        elif style == "flames":
            # Rising fire particles
            for p in self._particles:
                p["vy"] = -abs(p["vy"]) - 0.5  # Always rise
                px, py = int(p["x"]), int(p["y"])
                if 0 <= px < 128 and 0 <= py < 128:
                    # Fire gradient (red -> orange -> yellow)
                    heat = 1 - py / 128
                    hue = 30 * heat  # 0=red, 30=orange
                    color = hsv_to_rgb(hue, 1.0, p["life"])
                    draw_circle(buffer, px, py, p["size"], color)


# =============================================================================
# LED DEMO-STYLE LOADING EFFECTS
# =============================================================================

class LoadingEffect:
    """Base class for LED demo-style loading effects."""

    def __init__(self, size: int = 128):
        self.size = size
        self.time = 0.0

    def update(self, delta_ms: float) -> None:
        """Update effect state."""
        self.time += delta_ms / 1000.0

    def render(self, buffer: NDArray[np.uint8]) -> None:
        """Render effect to buffer. Override in subclasses."""
        pass


class PlasmaVortexEffect(LoadingEffect):
    """Hypnotic swirling plasma vortex - great for mystical modes."""

    def render(self, buffer: NDArray[np.uint8]) -> None:
        from artifact.graphics.text_utils import hsv_to_rgb

        cx, cy = self.size // 2, self.size // 2

        # Vectorized rendering for performance
        y_coords, x_coords = np.mgrid[0:self.size, 0:self.size]
        dx = x_coords - cx
        dy = y_coords - cy
        dist = np.sqrt(dx * dx + dy * dy)
        angle = np.arctan2(dy, dx)

        # Vortex twist
        twist = angle + dist / 15 + self.time * 2
        v = np.sin(twist * 5) * 0.5 + 0.5

        # Radial pulse
        pulse = np.sin(dist / 10 - self.time * 3) * 0.3 + 0.7

        # Calculate brightness with edge fade
        brightness = v * pulse * np.clip((self.size / 2 - dist + 20) / 20, 0, 1)

        # Hue varies by angle, distance, and time
        hue = (angle * (180 / np.pi) * 0.5 + dist * 2 + self.time * 50) % 360

        # Convert to RGB for each pixel
        for y in range(self.size):
            for x in range(self.size):
                if brightness[y, x] > 0.05:
                    color = hsv_to_rgb(hue[y, x], 0.9, brightness[y, x])
                    buffer[y, x] = color


class MatrixRainEffect(LoadingEffect):
    """Classic matrix rain effect - great for tech/AI modes."""

    def __init__(self, size: int = 128):
        super().__init__(size)
        # Initialize rain columns
        self.columns = []
        for x in range(0, size, 4):
            self.columns.append({
                'x': x,
                'y': random.uniform(-size, 0),
                'speed': random.uniform(40, 80),
                'length': random.randint(5, 15),
                'chars': [random.randint(0, 255) for _ in range(20)]
            })

    def render(self, buffer: NDArray[np.uint8]) -> None:
        # Dark green background
        buffer[:, :] = (0, 10, 0)

        for col in self.columns:
            col['y'] += col['speed'] * 0.016

            # Reset column when it goes off screen
            if col['y'] - col['length'] * 6 > self.size:
                col['y'] = random.uniform(-30, 0)
                col['speed'] = random.uniform(40, 80)
                col['length'] = random.randint(5, 15)

            # Draw characters in column
            for i in range(col['length']):
                cy = int(col['y'] - i * 6)
                if 0 <= cy < self.size:
                    x = col['x']
                    # Brightness fades toward tail
                    if i == 0:
                        # Head is bright white-green
                        color = (180, 255, 180)
                    else:
                        fade = 1.0 - (i / col['length'])
                        green = int(100 + 155 * fade)
                        color = (0, green, 0)

                    # Draw a small character block
                    for dx in range(3):
                        for dy in range(4):
                            px, py = x + dx, cy + dy
                            if 0 <= px < self.size and 0 <= py < self.size:
                                buffer[py, px] = color


class NeonGridEffect(LoadingEffect):
    """Synthwave neon grid - great for retro/quiz modes."""

    def render(self, buffer: NDArray[np.uint8]) -> None:
        from artifact.graphics.text_utils import hsv_to_rgb

        # Dark purple background gradient
        for y in range(self.size):
            darkness = 10 + y // 10
            buffer[y, :] = (darkness // 3, 0, darkness)

        horizon = self.size // 2 + 10

        # Neon sun
        sun_y = horizon - 25
        cx = self.size // 2
        for r in range(20, 0, -1):
            brightness = (20 - r) * 12
            for angle in range(0, 360, 5):
                rad = angle * 3.14159 / 180
                x = int(cx + r * math.cos(rad))
                y = int(sun_y + r * math.sin(rad) * 0.5)  # Squashed circle
                if 0 <= x < self.size and 0 <= y < self.size:
                    buffer[y, x] = (brightness, brightness // 3, brightness // 2)

        # Horizontal grid lines with perspective
        for i in range(1, 12):
            progress = i / 12
            y = horizon + int(progress * progress * (self.size - horizon))
            if 0 <= y < self.size:
                intensity = int(180 * (1 - progress * 0.5))
                hue = (self.time * 30 + i * 20) % 360
                color = hsv_to_rgb(hue, 0.8, intensity / 255)
                buffer[y, :] = color

        # Vertical lines with perspective
        for i in range(-8, 9, 2):
            x1 = self.size // 2 + i * 3
            x2 = self.size // 2 + i * 16
            hue = (self.time * 30 + abs(i) * 15) % 360
            color = hsv_to_rgb(hue, 0.7, 0.6)

            # Draw line from horizon to bottom
            for y in range(horizon, self.size):
                t = (y - horizon) / (self.size - horizon) if self.size > horizon else 0
                x = int(x1 + (x2 - x1) * t)
                if 0 <= x < self.size:
                    buffer[y, x] = color


class QuantumFieldEffect(LoadingEffect):
    """Quantum particle field - great for AI/sci-fi modes."""

    def __init__(self, size: int = 128):
        super().__init__(size)
        self.particles = [
            {'x': random.random(), 'y': random.random(), 'vx': 0, 'vy': 0}
            for _ in range(60)
        ]

    def render(self, buffer: NDArray[np.uint8]) -> None:
        from artifact.graphics.text_utils import hsv_to_rgb
        from artifact.graphics.primitives import draw_circle

        # Deep blue background
        buffer[:, :] = (0, 5, 15)

        # Update and draw particles with wave function behavior
        for p in self.particles:
            # Quantum tunneling / wave behavior
            p['vx'] += (random.random() - 0.5) * 0.02 + math.sin(self.time + p['y'] * 10) * 0.01
            p['vy'] += (random.random() - 0.5) * 0.02 + math.cos(self.time + p['x'] * 10) * 0.01
            p['x'] = (p['x'] + p['vx']) % 1.0
            p['y'] = (p['y'] + p['vy']) % 1.0

            px = int(p['x'] * self.size)
            py = int(p['y'] * self.size)

            if 0 <= px < self.size and 0 <= py < self.size:
                # Color based on position
                hue = (p['x'] * 180 + p['y'] * 180 + self.time * 30) % 360
                color = hsv_to_rgb(hue, 0.8, 0.9)
                draw_circle(buffer, px, py, 2, color)

                # Draw connections to nearby particles
                for other in self.particles[:20]:
                    ox = int(other['x'] * self.size)
                    oy = int(other['y'] * self.size)
                    dist = math.sqrt((px - ox)**2 + (py - oy)**2)
                    if 10 < dist < 30:
                        # Draw faint connection line
                        brightness = 0.3 * (1 - dist / 30)
                        conn_color = tuple(int(c * brightness) for c in color)
                        # Simple line drawing
                        steps = int(dist / 2)
                        for s in range(steps):
                            t = s / max(1, steps)
                            lx = int(px + (ox - px) * t)
                            ly = int(py + (oy - py) * t)
                            if 0 <= lx < self.size and 0 <= ly < self.size:
                                buffer[ly, lx] = np.clip(
                                    buffer[ly, lx].astype(np.int16) + np.array(conn_color),
                                    0, 255
                                ).astype(np.uint8)


class AuroraEffect(LoadingEffect):
    """Northern lights aurora - great for calming/mystical modes."""

    def __init__(self, size: int = 128):
        super().__init__(size)
        self.curtains = [{'x': random.randint(0, size), 'phase': random.uniform(0, 6.28)}
                        for _ in range(6)]

    def render(self, buffer: NDArray[np.uint8]) -> None:
        from artifact.graphics.text_utils import hsv_to_rgb

        # Dark night sky gradient
        for y in range(self.size):
            darkness = 5 + int(y / self.size * 15)
            buffer[y, :] = (0, max(0, darkness // 4), max(0, darkness))

        # Twinkling stars
        for i in range(25):
            sx = (i * 73 + int(self.time * 3)) % self.size
            sy = (i * 41) % (self.size // 2)
            twinkle = max(0, min(255, 120 + int(50 * math.sin(self.time * 3 + i))))
            if 0 <= sx < self.size and 0 <= sy < self.size:
                buffer[sy, sx] = (twinkle, twinkle, twinkle)

        # Aurora curtains
        for curtain in self.curtains:
            for y in range(20, 75):
                # Wave motion
                wave = math.sin(y / 15 + self.time * 2 + curtain['phase']) * 15
                wave += math.sin(y / 8 + self.time * 3) * 5
                x = int(curtain['x'] + wave)

                # Vertical fade
                intensity = max(0, 1.0 - abs(y - 47) / 35)
                intensity *= 0.5 + 0.5 * math.sin(self.time + curtain['phase'])

                if intensity > 0 and 0 <= x < self.size:
                    # Green to blue gradient
                    hue = 120 + (y - 20) * 1.5 + math.sin(self.time) * 30
                    color = hsv_to_rgb(hue, 0.8, max(0, min(1, intensity * 0.7)))

                    # Glow spread
                    for gx in range(-2, 3):
                        px = x + gx
                        if 0 <= px < self.size and 0 <= y < self.size:
                            glow = max(0, 1 - abs(gx) / 3)
                            old = buffer[y, px]
                            new = tuple(max(0, min(255, int(old[i] + color[i] * glow))) for i in range(3))
                            buffer[y, px] = new

            curtain['x'] += math.sin(self.time * 0.5 + curtain['phase']) * 0.3


class ElectricStormEffect(LoadingEffect):
    """Electric storm with lightning - great for dramatic modes."""

    def __init__(self, size: int = 128):
        super().__init__(size)
        self.lightning = []
        self.flash_time = 0

    def render(self, buffer: NDArray[np.uint8]) -> None:
        # Dark stormy background
        for y in range(self.size):
            darkness = max(0, min(255, 10 + y // 10))
            buffer[y, :] = (max(0, darkness // 3), max(0, darkness // 3), darkness)

        # Generate new lightning occasionally
        if random.random() < 0.03 and len(self.lightning) == 0:
            x = random.randint(20, self.size - 20)
            self.lightning = [(x, 0)]
            ly = 0
            while ly < self.size:
                ly += random.randint(5, 15)
                x += random.randint(-10, 10)
                x = max(5, min(self.size - 5, x))
                self.lightning.append((x, ly))
            self.flash_time = 8  # Flash duration in frames

        # Draw lightning
        if self.lightning and self.flash_time > 0:
            # Screen flash
            flash_intensity = min(50, self.flash_time * 8)
            buffer[:, :] = np.clip(
                buffer.astype(np.int16) + flash_intensity,
                0, 255
            ).astype(np.uint8)

            # Lightning bolt
            for i in range(len(self.lightning) - 1):
                x1, y1 = self.lightning[i]
                x2, y2 = self.lightning[i + 1]

                # Draw thick white line
                steps = max(1, max(abs(x2 - x1), abs(y2 - y1)) + 1)
                for s in range(steps):
                    t = s / max(1, steps)
                    lx = int(x1 + (x2 - x1) * t)
                    ly = int(y1 + (y2 - y1) * t)
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            px, py = lx + dx, ly + dy
                            if 0 <= px < self.size and 0 <= py < self.size:
                                buffer[py, px] = (255, 255, 255)

            # Branches
            for i, point in enumerate(self.lightning[::3]):
                if random.random() < 0.5:
                    ex = point[0] + random.randint(-15, 15)
                    ey = point[1] + random.randint(5, 20)
                    # Draw branch
                    steps = 10
                    for s in range(steps):
                        t = s / steps
                        bx = int(point[0] + (ex - point[0]) * t)
                        by = int(point[1] + (ey - point[1]) * t)
                        if 0 <= bx < self.size and 0 <= by < self.size:
                            buffer[by, bx] = (150, 150, 255)

            self.flash_time -= 1
            if self.flash_time <= 0:
                self.lightning = []

        # Rain
        for _ in range(20):
            rx = random.randint(0, self.size - 1)
            ry = random.randint(0, self.size - 1)
            for i in range(6):
                py = ry + i
                if 0 <= py < self.size:
                    buffer[py, rx] = (70, 70, 100)


class KaleidoscopeEffect(LoadingEffect):
    """Mesmerizing kaleidoscope patterns - great for any mode."""

    def render(self, buffer: NDArray[np.uint8]) -> None:
        from artifact.graphics.text_utils import hsv_to_rgb

        cx, cy = self.size // 2, self.size // 2

        for y in range(self.size):
            for x in range(self.size):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)

                # Mirror into 6 segments (6-fold symmetry)
                segments = 6
                angle = abs((angle + math.pi) % (2 * math.pi / segments) - math.pi / segments)

                # Rotating pattern
                rot_angle = angle + self.time * 0.5
                pattern = math.sin(dist / 10 + rot_angle * 3 + self.time)
                pattern += math.sin(dist / 5 - self.time * 2)
                pattern /= 2

                # Color based on position and time
                hue = (dist * 3 + self.time * 50 + angle * 60) % 360
                brightness = 0.3 + 0.7 * (pattern + 1) / 2

                buffer[y, x] = hsv_to_rgb(hue, 0.9, max(0, brightness))


# Effect instances cache
_effect_cache: Dict[str, LoadingEffect] = {}

def get_loading_effect(style: str, size: int = 128) -> LoadingEffect:
    """Get or create a loading effect instance."""
    if style not in _effect_cache:
        effect_classes = {
            'plasma_vortex': PlasmaVortexEffect,
            'matrix_rain': MatrixRainEffect,
            'neon_grid': NeonGridEffect,
            'quantum_field': QuantumFieldEffect,
            'aurora': AuroraEffect,
            'electric_storm': ElectricStormEffect,
            'kaleidoscope': KaleidoscopeEffect,
        }
        effect_class = effect_classes.get(style, PlasmaVortexEffect)
        _effect_cache[style] = effect_class(size)
    return _effect_cache[style]


# =============================================================================
# THEMED PROGRESS STYLES
# =============================================================================

# Mode-specific progress bar colors and new LED demo-style effects
MODE_PROGRESS_COLORS = {
    "fortune": ((200, 100, 255), "plasma_vortex"),  # Purple plasma vortex
    "ai_prophet": ((100, 200, 255), "quantum_field"),  # Blue quantum particles
    "roast": ((255, 150, 50), "electric_storm"),  # Orange with lightning
    "zodiac": ((255, 215, 0), "aurora"),  # Gold with aurora
    "quiz": ((0, 200, 100), "neon_grid"),  # Green synthwave grid
    "roulette": ((255, 50, 50), "kaleidoscope"),  # Red kaleidoscope
    "guess_me": ((150, 100, 255), "plasma_vortex"),  # Purple plasma
    "autopsy": ((0, 255, 200), "matrix_rain"),  # Cyan matrix rain
    "rapgod": ((255, 50, 150), "neon_grid"),  # Pink synthwave
    "default": ((150, 150, 200), "matrix_rain"),  # Gray-blue matrix rain
}


def get_mode_progress_style(mode_name: str) -> Tuple[Tuple[int, int, int], str]:
    """Get progress bar color and animation style for a mode.

    Args:
        mode_name: Name of the mode

    Returns:
        Tuple of (bar_color, animation_style)
    """
    return MODE_PROGRESS_COLORS.get(mode_name, MODE_PROGRESS_COLORS["default"])

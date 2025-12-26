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

# Status messages per phase (Russian)
PHASE_MESSAGES = {
    ProgressPhase.INITIALIZING: [
        "Подготовка...",
        "Запуск...",
        "Инициализация...",
    ],
    ProgressPhase.ANALYZING: [
        "Анализ фото...",
        "Сканирование...",
        "Изучаю черты...",
        "Вижу тебя...",
    ],
    ProgressPhase.GENERATING_TEXT: [
        "Создаю текст...",
        "Пишу судьбу...",
        "Формирую послание...",
        "Думаю...",
    ],
    ProgressPhase.GENERATING_IMAGE: [
        "Рисую шарж...",
        "Создаю образ...",
        "Творю...",
        "Почти готово...",
    ],
    ProgressPhase.FINALIZING: [
        "Финальные штрихи...",
        "Заканчиваю...",
        "Последняя проверка...",
    ],
    ProgressPhase.COMPLETE: [
        "Готово!",
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

        # Progress fill with pulse effect
        progress = self.get_progress()
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
        """Render entertaining loading animation.

        Args:
            buffer: Target buffer
            style: Animation style ("tech", "mystical", "flames")
            time_ms: Current time
        """
        from artifact.graphics.text_utils import hsv_to_rgb
        from artifact.graphics.primitives import draw_circle

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
# THEMED PROGRESS STYLES
# =============================================================================

# Mode-specific progress bar colors
MODE_PROGRESS_COLORS = {
    "fortune": ((200, 100, 255), "mystical"),   # Purple, mystical particles
    "ai_prophet": ((100, 200, 255), "tech"),    # Blue, tech scan lines
    "roast": ((255, 150, 50), "flames"),        # Orange, fire particles
    "zodiac": ((255, 215, 0), "mystical"),      # Gold, mystical
    "quiz": ((0, 200, 100), "tech"),            # Green, tech
    "default": ((150, 150, 200), "tech"),       # Gray-blue, tech
}


def get_mode_progress_style(mode_name: str) -> Tuple[Tuple[int, int, int], str]:
    """Get progress bar color and animation style for a mode.

    Args:
        mode_name: Name of the mode

    Returns:
        Tuple of (bar_color, animation_style)
    """
    return MODE_PROGRESS_COLORS.get(mode_name, MODE_PROGRESS_COLORS["default"])

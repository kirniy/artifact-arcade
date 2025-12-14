"""Squid Game mode - Red Light, Green Light with camera motion detection.

The iconic game from Squid Game (오징어 게임):
1. Camera captures initial frame
2. "무궁화 꽃이 피었습니다" (Green Light) - you can move
3. Doll turns around (Red Light) - FREEZE or you're eliminated!
4. Survive until the timer ends to win a prize coupon

Uses camera frame differencing for motion detection.
"""

import asyncio
import logging
from typing import Optional, List, Tuple
from datetime import datetime
import random
import math
import numpy as np
import hashlib

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.simulator.mock_hardware.camera import (
    SimulatorCamera, create_camera, floyd_steinberg_dither
)

logger = logging.getLogger(__name__)


class SquidPhase:
    """Sub-phases within Squid Game mode."""

    INTRO = "intro"              # Dramatic intro with music cue
    RULES = "rules"              # Explain the rules
    COUNTDOWN = "countdown"      # 3-2-1 countdown
    GREEN_LIGHT = "green"        # Can move - "무궁화 꽃이 피었습니다"
    RED_LIGHT = "red"            # FREEZE - doll is watching
    ELIMINATED = "eliminated"    # Player moved during red light
    VICTORY = "victory"          # Player survived!


# Squid Game iconic colors
SQUID_PINK = (237, 27, 118)      # Guard uniform pink
SQUID_TEAL = (0, 135, 131)       # Player tracksuit teal
SQUID_BLACK = (10, 10, 10)       # Dark background
SQUID_WHITE = (255, 255, 255)
SQUID_RED = (200, 30, 30)        # Elimination red
SQUID_GOLD = (255, 200, 50)      # Victory gold

# Korean phrases (romanized for display)
KOREAN_GREEN = "무궁화 꽃이 피었습니다"  # Mugunghwa kkoci pieossseubnida
RUSSIAN_GREEN = "БЕГИ!"
RUSSIAN_RED = "ЗАМРИ!"
RUSSIAN_ELIMINATED = "ВЫБЫЛ!"
RUSSIAN_VICTORY = "ПОБЕДА!"


def generate_coupon_code() -> str:
    """Generate a unique coupon code for winners."""
    # Use timestamp + random for uniqueness
    timestamp = datetime.now().strftime("%H%M%S")
    random_part = hashlib.md5(str(random.random()).encode()).hexdigest()[:4].upper()
    return f"SG-{timestamp}-{random_part}"


class SquidGameMode(BaseMode):
    """Squid Game - Red Light, Green Light survival game.

    The viral game from the Netflix series:
    - Camera detects motion during "Red Light" phase
    - Players must freeze completely when the doll turns
    - Survive the full round to win a coupon code
    - Creepy doll animation + iconic sounds

    Flow:
    1. INTRO: Dramatic Squid Game intro
    2. RULES: Quick explanation
    3. COUNTDOWN: 3-2-1 START
    4. GREEN_LIGHT/RED_LIGHT: Alternating phases
    5. ELIMINATED or VICTORY: Result
    """

    name = "squid_game"
    display_name = "ИГРА"
    description = "Красный свет - Зелёный свет"
    icon = "☠"
    style = "squid"
    requires_camera = True
    requires_ai = False
    estimated_duration = 45

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Sub-phase tracking
        self._sub_phase = SquidPhase.INTRO

        # Game state
        self._total_time: float = 20000  # 20 seconds total game time
        self._remaining_time: float = 0
        self._green_duration: float = 0   # Current green light duration
        self._red_duration: float = 0     # Current red light duration
        self._phase_time: float = 0       # Time in current green/red phase

        # Motion detection
        self._camera: Optional[SimulatorCamera] = None
        self._reference_frame: Optional[np.ndarray] = None
        self._current_frame: Optional[np.ndarray] = None
        self._motion_level: float = 0.0
        self._motion_threshold: float = 0.08  # Sensitivity (0-1)
        self._motion_history: List[float] = []

        # Doll animation
        self._doll_rotation: float = 0.0  # 0 = facing away, 180 = facing player
        self._doll_target_rotation: float = 0.0
        self._doll_blink: float = 0.0
        self._doll_eye_glow: float = 0.0

        # Visual effects
        self._flash_alpha: float = 0.0
        self._shake_amount: float = 0.0
        self._scan_line: float = 0.0
        self._warning_pulse: float = 0.0
        self._elimination_progress: float = 0.0

        # Result
        self._coupon_code: str = ""
        self._survived_time: float = 0.0

        # Particles
        self._particles = ParticleSystem()

    def on_enter(self) -> None:
        """Initialize Squid Game mode."""
        self._sub_phase = SquidPhase.INTRO
        self._remaining_time = self._total_time
        self._motion_level = 0.0
        self._motion_history = []
        self._reference_frame = None
        self._current_frame = None
        self._doll_rotation = 0.0
        self._doll_target_rotation = 0.0
        self._flash_alpha = 0.0
        self._shake_amount = 0.0
        self._coupon_code = ""
        self._survived_time = 0.0
        self._elimination_progress = 0.0

        # Initialize camera
        self._camera = create_camera(resolution=(320, 240))
        if self._camera.open():
            logger.info("Camera opened for Squid Game mode")
        else:
            logger.warning("Could not open camera")

        # Setup particles
        blood_config = ParticlePresets.fire(x=64, y=64)
        blood_config.color = SQUID_RED
        blood_config.emission_rate = 0.0
        self._particles.add_emitter("blood", blood_config)

        confetti_config = ParticlePresets.sparkle(x=64, y=64)
        confetti_config.color = SQUID_GOLD
        confetti_config.emission_rate = 0.0
        self._particles.add_emitter("confetti", confetti_config)

        self.change_phase(ModePhase.INTRO)
        logger.info("Squid Game mode entered")

    def on_update(self, delta_ms: float) -> None:
        """Update Squid Game mode."""
        self._particles.update(delta_ms)

        # Decay effects
        self._flash_alpha = max(0, self._flash_alpha - delta_ms / 300)
        self._shake_amount = max(0, self._shake_amount - delta_ms / 200)
        self._scan_line = (self._scan_line + delta_ms * 0.2) % 128

        # Update camera frame
        self._update_camera_frame()

        if self.phase == ModePhase.INTRO:
            if self._sub_phase == SquidPhase.INTRO:
                # Dramatic intro - 3 seconds
                if self._time_in_phase > 3000:
                    self._sub_phase = SquidPhase.RULES
                    self._time_in_phase = 0

            elif self._sub_phase == SquidPhase.RULES:
                # Rules display - 3 seconds
                if self._time_in_phase > 3000:
                    self._sub_phase = SquidPhase.COUNTDOWN
                    self._time_in_phase = 0

            elif self._sub_phase == SquidPhase.COUNTDOWN:
                # 3-2-1 countdown
                if self._time_in_phase > 3000:
                    self._start_game()

        elif self.phase == ModePhase.ACTIVE:
            # Update remaining time
            self._remaining_time -= delta_ms
            self._phase_time += delta_ms

            if self._remaining_time <= 0:
                # Time's up - VICTORY!
                self._on_victory()
                return

            # Animate doll rotation
            rotation_speed = 15.0  # degrees per frame
            if abs(self._doll_rotation - self._doll_target_rotation) > 1:
                if self._doll_rotation < self._doll_target_rotation:
                    self._doll_rotation = min(self._doll_rotation + rotation_speed, self._doll_target_rotation)
                else:
                    self._doll_rotation = max(self._doll_rotation - rotation_speed, self._doll_target_rotation)

            if self._sub_phase == SquidPhase.GREEN_LIGHT:
                # Green light - doll facing away
                self._doll_target_rotation = 0

                # Check if green phase is over
                if self._phase_time >= self._green_duration:
                    self._start_red_light()

            elif self._sub_phase == SquidPhase.RED_LIGHT:
                # Red light - doll facing player
                self._doll_target_rotation = 180
                self._doll_eye_glow = 0.5 + 0.5 * math.sin(self._time_in_phase / 100)

                # Check motion only when doll has fully turned
                if self._doll_rotation >= 170:
                    self._check_motion()

                    # Warning pulse when motion detected
                    if self._motion_level > self._motion_threshold * 0.5:
                        self._warning_pulse = min(1.0, self._warning_pulse + delta_ms / 200)
                    else:
                        self._warning_pulse = max(0, self._warning_pulse - delta_ms / 300)

                # Check if red phase is over
                if self._phase_time >= self._red_duration:
                    self._start_green_light()

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == SquidPhase.ELIMINATED:
                # Elimination animation
                self._elimination_progress = min(1.0, self._time_in_phase / 2000)

                # Auto-exit after 8 seconds
                if self._time_in_phase > 8000:
                    self._finish()

            elif self._sub_phase == SquidPhase.VICTORY:
                # Victory celebration
                if int(self._time_in_phase / 500) > int((self._time_in_phase - delta_ms) / 500):
                    confetti = self._particles.get_emitter("confetti")
                    if confetti:
                        confetti.burst(20)

                # Auto-exit after 10 seconds
                if self._time_in_phase > 10000:
                    self._finish()

    def _update_camera_frame(self) -> None:
        """Update camera frame for motion detection."""
        if not self._camera or not self._camera.is_open:
            return

        try:
            frame = self._camera.capture_frame()
            if frame is not None and frame.size > 0:
                # Convert to grayscale for motion detection
                gray = np.mean(frame, axis=2).astype(np.uint8)
                # Downsample for faster processing
                small = gray[::4, ::4]
                self._current_frame = small

                # Also create dithered preview
                self._camera_preview = floyd_steinberg_dither(frame, target_size=(128, 128), threshold=100)

        except Exception as e:
            logger.warning(f"Camera frame error: {e}")

    def _check_motion(self) -> None:
        """Check for motion between frames."""
        if self._reference_frame is None or self._current_frame is None:
            return

        try:
            # Calculate frame difference
            diff = np.abs(self._current_frame.astype(np.float32) - self._reference_frame.astype(np.float32))
            motion = np.mean(diff) / 255.0

            # Smooth motion detection
            self._motion_history.append(motion)
            if len(self._motion_history) > 5:
                self._motion_history.pop(0)

            self._motion_level = np.mean(self._motion_history)

            # Check if eliminated
            if self._motion_level > self._motion_threshold:
                logger.info(f"Motion detected: {self._motion_level:.3f} > {self._motion_threshold}")
                self._on_eliminated()

        except Exception as e:
            logger.warning(f"Motion detection error: {e}")

    def _start_game(self) -> None:
        """Start the actual game."""
        self.change_phase(ModePhase.ACTIVE)
        self._remaining_time = self._total_time
        self._start_green_light()
        logger.info("Game started!")

    def _start_green_light(self) -> None:
        """Start green light phase (can move)."""
        self._sub_phase = SquidPhase.GREEN_LIGHT
        self._phase_time = 0
        self._doll_target_rotation = 0  # Face away

        # Random duration (2-4 seconds)
        self._green_duration = random.uniform(2000, 4000)

        # Capture reference frame at end of green light
        self._reference_frame = None

        logger.info(f"GREEN LIGHT for {self._green_duration/1000:.1f}s")

    def _start_red_light(self) -> None:
        """Start red light phase (FREEZE!)."""
        self._sub_phase = SquidPhase.RED_LIGHT
        self._phase_time = 0
        self._doll_target_rotation = 180  # Face player

        # Random duration (2-4 seconds)
        self._red_duration = random.uniform(2000, 4000)

        # Capture reference frame NOW
        if self._current_frame is not None:
            self._reference_frame = self._current_frame.copy()

        # Clear motion history
        self._motion_history = []
        self._motion_level = 0.0
        self._warning_pulse = 0.0

        # Flash effect
        self._flash_alpha = 0.8

        logger.info(f"RED LIGHT for {self._red_duration/1000:.1f}s")

    def _on_eliminated(self) -> None:
        """Player eliminated for moving."""
        self._sub_phase = SquidPhase.ELIMINATED
        self.change_phase(ModePhase.RESULT)
        self._survived_time = self._total_time - self._remaining_time

        # Dramatic effects
        self._flash_alpha = 1.0
        self._shake_amount = 3.0

        # Blood particles
        blood = self._particles.get_emitter("blood")
        if blood:
            blood.burst(50)

        logger.info("ELIMINATED!")

    def _on_victory(self) -> None:
        """Player survived - VICTORY!"""
        self._sub_phase = SquidPhase.VICTORY
        self.change_phase(ModePhase.RESULT)
        self._survived_time = self._total_time
        self._coupon_code = generate_coupon_code()

        # Celebration effects
        self._flash_alpha = 1.0

        # Confetti burst
        confetti = self._particles.get_emitter("confetti")
        if confetti:
            confetti.burst(100)

        logger.info(f"VICTORY! Coupon: {self._coupon_code}")

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT:
                self._finish()
                return True

        return False

    def on_exit(self) -> None:
        """Cleanup."""
        if self._camera:
            self._camera.close()
            self._camera = None

        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        if self._sub_phase == SquidPhase.VICTORY:
            result = ModeResult(
                mode_name=self.name,
                success=True,
                display_text=f"ПОБЕДА! Код: {self._coupon_code}",
                ticker_text=f"ПОБЕДИТЕЛЬ! {self._coupon_code}",
                lcd_text=" ПОБЕДА! ".center(16),
                should_print=True,
                print_data={
                    "coupon_code": self._coupon_code,
                    "survived_time": f"{self._survived_time/1000:.1f}s",
                    "game": "Squid Game",
                    "result": "VICTORY",
                    "timestamp": datetime.now().isoformat(),
                    "type": "squid_game",
                }
            )
        else:
            result = ModeResult(
                mode_name=self.name,
                success=False,
                display_text="ВЫБЫЛ!",
                ticker_text=f"Продержался {self._survived_time/1000:.1f}с",
                lcd_text=" ВЫБЫЛ! ".center(16),
                should_print=False,
                print_data={
                    "survived_time": f"{self._survived_time/1000:.1f}s",
                    "game": "Squid Game",
                    "result": "ELIMINATED",
                    "timestamp": datetime.now().isoformat(),
                    "type": "squid_game",
                }
            )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display with Squid Game aesthetics."""
        from artifact.graphics.primitives import fill, draw_circle, draw_rect, draw_line
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

        # Add shake
        shake_x = int(random.uniform(-1, 1) * self._shake_amount * 3) if self._shake_amount > 0 else 0
        shake_y = int(random.uniform(-1, 1) * self._shake_amount * 3) if self._shake_amount > 0 else 0

        font = load_font("cyrillic")

        if self._sub_phase == SquidPhase.INTRO:
            self._render_intro(buffer, font)

        elif self._sub_phase == SquidPhase.RULES:
            self._render_rules(buffer, font)

        elif self._sub_phase == SquidPhase.COUNTDOWN:
            self._render_countdown(buffer, font)

        elif self._sub_phase in (SquidPhase.GREEN_LIGHT, SquidPhase.RED_LIGHT):
            self._render_game(buffer, font, shake_x, shake_y)

        elif self._sub_phase == SquidPhase.ELIMINATED:
            self._render_eliminated(buffer, font, shake_x, shake_y)

        elif self._sub_phase == SquidPhase.VICTORY:
            self._render_victory(buffer, font)

        # Render particles
        self._particles.render(buffer)

        # Flash overlay
        if self._flash_alpha > 0:
            flash_color = SQUID_RED if self._sub_phase == SquidPhase.RED_LIGHT else SQUID_WHITE
            for y in range(128):
                for x in range(128):
                    buffer[y, x] = tuple(
                        int(buffer[y, x][c] * (1 - self._flash_alpha) + flash_color[c] * self._flash_alpha)
                        for c in range(3)
                    )

    def _render_intro(self, buffer, font) -> None:
        """Render dramatic Squid Game intro."""
        from artifact.graphics.primitives import fill, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

        fill(buffer, SQUID_BLACK)

        # Squid Game shapes (circle, triangle, square)
        cx, cy = 64, 50
        t = self._time_in_phase

        # Animate shapes appearing
        if t > 500:
            # Circle (pink)
            self._draw_squid_circle(buffer, cx - 35, cy, 12, SQUID_PINK)

        if t > 1000:
            # Triangle (pink)
            self._draw_squid_triangle(buffer, cx, cy, 14, SQUID_PINK)

        if t > 1500:
            # Square (pink)
            self._draw_squid_square(buffer, cx + 35, cy, 12, SQUID_PINK)

        # Title with glitch effect
        if t > 2000:
            draw_animated_text(buffer, "ИГРА", 85, SQUID_PINK, t, TextEffect.GLITCH, scale=2)
            draw_centered_text(buffer, "В КАЛЬМАРА", 105, SQUID_WHITE, scale=1)

    def _render_rules(self, buffer, font) -> None:
        """Render game rules."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        fill(buffer, SQUID_BLACK)

        # Draw small doll at top
        self._draw_doll(buffer, 64, 30, 0.4, facing_player=True)

        # Rules text
        draw_centered_text(buffer, "ПРАВИЛА", 60, SQUID_PINK, scale=2)
        draw_centered_text(buffer, "ЗЕЛЁНЫЙ: ДВИГАЙСЯ", 80, SQUID_TEAL, scale=1)
        draw_centered_text(buffer, "КРАСНЫЙ: ЗАМРИ!", 92, SQUID_RED, scale=1)
        draw_centered_text(buffer, "НЕ ШЕВЕЛИСЬ!", 104, SQUID_WHITE, scale=1)

    def _render_countdown(self, buffer, font) -> None:
        """Render 3-2-1 countdown."""
        from artifact.graphics.primitives import fill, draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        fill(buffer, SQUID_BLACK)

        # Countdown number
        countdown = 3 - int(self._time_in_phase / 1000)
        if countdown > 0:
            # Pulsing number
            pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 100)
            scale = int(4 * pulse)
            draw_centered_text(buffer, str(countdown), 40, SQUID_PINK, scale=scale)

            # Progress ring
            progress = (self._time_in_phase % 1000) / 1000
            for angle in range(0, int(360 * progress), 10):
                rad = math.radians(angle - 90)
                px = int(64 + 50 * math.cos(rad))
                py = int(64 + 50 * math.sin(rad))
                draw_circle(buffer, px, py, 3, SQUID_PINK)
        else:
            draw_centered_text(buffer, "СТАРТ!", 50, SQUID_TEAL, scale=2)

    def _render_game(self, buffer, font, shake_x: int, shake_y: int) -> None:
        """Render main game screen with doll and timer."""
        from artifact.graphics.primitives import fill, draw_rect
        from artifact.graphics.text_utils import draw_centered_text

        # Background color based on phase
        if self._sub_phase == SquidPhase.GREEN_LIGHT:
            bg_color = (0, 40, 30)  # Dark teal
        else:
            bg_color = (40, 10, 10)  # Dark red
        fill(buffer, bg_color)

        # Draw the doll (centered, large)
        doll_y = 55 + shake_y
        facing = self._doll_rotation >= 90
        self._draw_doll(buffer, 64 + shake_x, doll_y, 1.0, facing_player=facing)

        # Timer bar at top
        timer_y = 5
        bar_width = 118
        bar_x = 5
        remaining_ratio = max(0, self._remaining_time / self._total_time)

        # Background
        draw_rect(buffer, bar_x, timer_y, bar_width, 8, (40, 40, 40))
        # Fill
        fill_width = int(bar_width * remaining_ratio)
        fill_color = SQUID_TEAL if remaining_ratio > 0.3 else SQUID_RED
        if fill_width > 0:
            draw_rect(buffer, bar_x, timer_y, fill_width, 8, fill_color)

        # Status text at bottom
        if self._sub_phase == SquidPhase.GREEN_LIGHT:
            draw_centered_text(buffer, RUSSIAN_GREEN, 110, SQUID_TEAL, scale=2)
        else:
            # Red light with warning pulse
            color = SQUID_RED
            if self._warning_pulse > 0:
                # Flash more red when motion detected
                intensity = int(255 * self._warning_pulse)
                color = (255, intensity, intensity)
            draw_centered_text(buffer, RUSSIAN_RED, 110, color, scale=2)

            # Motion indicator
            if self._motion_level > 0:
                motion_bar_width = int(100 * min(1.0, self._motion_level / self._motion_threshold))
                bar_color = SQUID_RED if self._motion_level > self._motion_threshold * 0.5 else (100, 100, 100)
                draw_rect(buffer, 14, 100, motion_bar_width, 4, bar_color)

    def _render_eliminated(self, buffer, font, shake_x: int, shake_y: int) -> None:
        """Render elimination screen."""
        from artifact.graphics.primitives import fill, draw_line
        from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

        # Red background fade in
        red_intensity = int(40 * self._elimination_progress)
        fill(buffer, (red_intensity, 5, 5))

        # Crosshair/target effect
        cx, cy = 64, 50
        target_size = int(40 * (1 - self._elimination_progress * 0.5))

        # Draw targeting lines
        line_color = SQUID_RED
        draw_line(buffer, cx - target_size, cy, cx + target_size, cy, line_color)
        draw_line(buffer, cx, cy - target_size, cx, cy + target_size, line_color)

        # X marks
        if self._elimination_progress > 0.5:
            x_size = int(20 * (self._elimination_progress - 0.5) * 2)
            draw_line(buffer, cx - x_size, cy - x_size, cx + x_size, cy + x_size, SQUID_RED)
            draw_line(buffer, cx + x_size, cy - x_size, cx - x_size, cy + x_size, SQUID_RED)

        # ELIMINATED text with glitch
        draw_animated_text(buffer, RUSSIAN_ELIMINATED, 85, SQUID_RED, self._time_in_phase, TextEffect.GLITCH, scale=2)

        # Survival time
        time_str = f"{self._survived_time/1000:.1f} СЕК"
        draw_centered_text(buffer, time_str, 105, SQUID_WHITE, scale=1)

    def _render_victory(self, buffer, font) -> None:
        """Render victory screen with coupon code."""
        from artifact.graphics.primitives import fill, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

        # Gold/teal celebration background
        fill(buffer, (10, 30, 30))

        # Victory text with rainbow
        draw_animated_text(buffer, RUSSIAN_VICTORY, 15, SQUID_GOLD, self._time_in_phase, TextEffect.RAINBOW, scale=2)

        # Coupon code box
        draw_rect(buffer, 10, 40, 108, 35, SQUID_BLACK)
        draw_rect(buffer, 10, 40, 108, 35, SQUID_GOLD, filled=False)

        # "FREE SHOT" label
        draw_centered_text(buffer, "БЕСПЛАТНЫЙ ШОТ", 45, SQUID_TEAL, scale=1)

        # Coupon code (large)
        draw_centered_text(buffer, self._coupon_code, 60, SQUID_GOLD, scale=1)

        # Instructions
        draw_centered_text(buffer, "ПОКАЖИ БАРМЕНУ", 85, SQUID_WHITE, scale=1)
        draw_centered_text(buffer, "НАЖМИ ДЛЯ ПЕЧАТИ", 105, SQUID_PINK, scale=1)

    def _draw_doll(self, buffer, cx: int, cy: int, scale: float, facing_player: bool) -> None:
        """Draw the iconic Squid Game doll."""
        from artifact.graphics.primitives import draw_circle, draw_rect, draw_line

        # Scale factor
        s = scale

        # Dress (orange/yellow)
        dress_color = (255, 150, 50)
        dress_top = int(cy - 5 * s)
        dress_bottom = int(cy + 25 * s)
        dress_width = int(20 * s)

        # Trapezoid dress
        for y in range(dress_top, dress_bottom):
            progress = (y - dress_top) / (dress_bottom - dress_top)
            width = int(dress_width * (0.5 + 0.5 * progress))
            draw_line(buffer, cx - width, y, cx + width, y, dress_color)

        # Collar
        draw_rect(buffer, int(cx - 8 * s), int(cy - 8 * s), int(16 * s), int(5 * s), (255, 200, 100))

        # Head
        head_radius = int(12 * s)
        head_y = int(cy - 18 * s)
        draw_circle(buffer, cx, head_y, head_radius, (60, 50, 40))  # Dark brown

        # Hair buns
        bun_y = int(head_y - 8 * s)
        draw_circle(buffer, int(cx - 12 * s), bun_y, int(6 * s), (30, 25, 20))
        draw_circle(buffer, int(cx + 12 * s), bun_y, int(6 * s), (30, 25, 20))

        if facing_player:
            # Face (front view) - SCARY!
            face_color = (240, 220, 200)
            draw_circle(buffer, cx, head_y, int(10 * s), face_color)

            # Eyes (glowing red when watching)
            eye_y = int(head_y - 2 * s)
            eye_color = (255, int(50 + 200 * self._doll_eye_glow), int(50 + 100 * self._doll_eye_glow))
            draw_circle(buffer, int(cx - 4 * s), eye_y, int(2 * s), eye_color)
            draw_circle(buffer, int(cx + 4 * s), eye_y, int(2 * s), eye_color)

            # Eyebrows (angry)
            draw_line(buffer, int(cx - 6 * s), int(eye_y - 3 * s), int(cx - 2 * s), int(eye_y - 2 * s), (50, 30, 20))
            draw_line(buffer, int(cx + 6 * s), int(eye_y - 3 * s), int(cx + 2 * s), int(eye_y - 2 * s), (50, 30, 20))

            # Cheeks (pink circles)
            cheek_y = int(head_y + 2 * s)
            draw_circle(buffer, int(cx - 6 * s), cheek_y, int(2 * s), (255, 150, 150))
            draw_circle(buffer, int(cx + 6 * s), cheek_y, int(2 * s), (255, 150, 150))

            # Mouth (small)
            draw_circle(buffer, cx, int(head_y + 5 * s), int(1 * s), (200, 100, 100))
        else:
            # Back of head (hair)
            draw_circle(buffer, cx, head_y, int(10 * s), (30, 25, 20))

        # Arms
        arm_color = dress_color
        # Left arm
        draw_line(buffer, int(cx - 15 * s), int(cy), int(cx - 20 * s), int(cy + 15 * s), arm_color)
        # Right arm
        draw_line(buffer, int(cx + 15 * s), int(cy), int(cx + 20 * s), int(cy + 15 * s), arm_color)

    def _draw_squid_circle(self, buffer, cx: int, cy: int, radius: int, color) -> None:
        """Draw Squid Game circle symbol."""
        from artifact.graphics.primitives import draw_circle
        draw_circle(buffer, cx, cy, radius, color, filled=False)
        draw_circle(buffer, cx, cy, radius - 2, color, filled=False)

    def _draw_squid_triangle(self, buffer, cx: int, cy: int, size: int, color) -> None:
        """Draw Squid Game triangle symbol."""
        from artifact.graphics.primitives import draw_line
        # Equilateral triangle pointing up
        h = int(size * 0.866)  # height = size * sqrt(3)/2
        top = (cx, cy - h // 2)
        left = (cx - size // 2, cy + h // 2)
        right = (cx + size // 2, cy + h // 2)
        draw_line(buffer, top[0], top[1], left[0], left[1], color)
        draw_line(buffer, left[0], left[1], right[0], right[1], color)
        draw_line(buffer, right[0], right[1], top[0], top[1], color)

    def _draw_squid_square(self, buffer, cx: int, cy: int, size: int, color) -> None:
        """Draw Squid Game square symbol."""
        from artifact.graphics.primitives import draw_rect
        half = size // 2
        draw_rect(buffer, cx - half, cy - half, size, size, color, filled=False)

    def render_ticker(self, buffer) -> None:
        """Render ticker - static text with arrows for camera."""
        from artifact.graphics.primitives import clear, fill
        from artifact.graphics.text_utils import render_ticker_static, TextEffect

        clear(buffer)

        if self._sub_phase == SquidPhase.GREEN_LIGHT:
            # Green background
            fill(buffer, (0, 50, 30))
            render_ticker_static(buffer, "БЕГИ", self._time_in_phase, SQUID_TEAL, TextEffect.GLOW)

        elif self._sub_phase == SquidPhase.RED_LIGHT:
            # Red background with pulse
            intensity = int(50 + 30 * self._warning_pulse)
            fill(buffer, (intensity, 0, 0))
            render_ticker_static(buffer, "ЗАМРИ", self._time_in_phase, SQUID_RED, TextEffect.PULSE)

        elif self._sub_phase == SquidPhase.ELIMINATED:
            fill(buffer, (50, 0, 0))
            render_ticker_static(buffer, "ВЫБЫЛ", self._time_in_phase, SQUID_RED, TextEffect.GLITCH)

        elif self._sub_phase == SquidPhase.VICTORY:
            render_ticker_static(buffer, "ПОБЕДА", self._time_in_phase, SQUID_GOLD, TextEffect.RAINBOW)

        else:
            render_ticker_static(buffer, "ИГРА", self._time_in_phase, SQUID_PINK, TextEffect.GLOW)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self._sub_phase == SquidPhase.GREEN_LIGHT:
            return " ► БЕГИ! ► ".center(16)[:16]
        elif self._sub_phase == SquidPhase.RED_LIGHT:
            # Warning symbols
            if self._warning_pulse > 0.5:
                return " !! ЗАМРИ !! ".center(16)[:16]
            return " ■ ЗАМРИ! ■ ".center(16)[:16]
        elif self._sub_phase == SquidPhase.ELIMINATED:
            return " ☠ ВЫБЫЛ ☠ ".center(16)[:16]
        elif self._sub_phase == SquidPhase.VICTORY:
            return " ★ ПОБЕДА! ★ ".center(16)[:16]
        elif self._sub_phase == SquidPhase.COUNTDOWN:
            countdown = 3 - int(self._time_in_phase / 1000)
            if countdown > 0:
                return f"     {countdown}     ".center(16)[:16]
            return " СТАРТ! ".center(16)[:16]
        return " ◆ ИГРА ◆ ".center(16)

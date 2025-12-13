"""Roulette mode - Spinning wheel of fortune.

A classic arcade-style spinning wheel with various outcomes.
Uses arcade visual style with flashing lights and dramatic spin animation.
"""

from typing import List, Tuple
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets


# Wheel segments with Russian and English text
WHEEL_SEGMENTS = [
    ("УДАЧА", "LUCK", (46, 204, 113)),      # Green
    ("ЛЮБОВЬ", "LOVE", (231, 76, 60)),       # Red
    ("БОГАТСТВО", "WEALTH", (241, 196, 15)), # Yellow
    ("ЗДОРОВЬЕ", "HEALTH", (52, 152, 219)),  # Blue
    ("УСПЕХ", "SUCCESS", (155, 89, 182)),    # Purple
    ("ПРИКЛЮЧЕНИЕ", "ADVENTURE", (230, 126, 34)),  # Orange
    ("МУДРОСТЬ", "WISDOM", (149, 165, 166)), # Gray
    ("СЧАСТЬЕ", "HAPPINESS", (241, 148, 138)), # Pink
]

# Detailed outcomes for each segment
OUTCOMES_RU = {
    "УДАЧА": [
        "Удача улыбнётся тебе сегодня",
        "Фортуна на твоей стороне",
        "Жди счастливого случая",
    ],
    "ЛЮБОВЬ": [
        "Любовь уже близко",
        "Сердце найдёт свой путь",
        "Романтика в воздухе",
    ],
    "БОГАТСТВО": [
        "Финансовый успех впереди",
        "Деньги придут неожиданно",
        "Инвестиции окупятся",
    ],
    "ЗДОРОВЬЕ": [
        "Здоровье укрепится",
        "Энергия наполнит тебя",
        "Тело и дух в гармонии",
    ],
    "УСПЕХ": [
        "Успех уже на горизонте",
        "Твои усилия вознаградятся",
        "Победа будет твоей",
    ],
    "ПРИКЛЮЧЕНИЕ": [
        "Приключение ждёт тебя",
        "Новые горизонты откроются",
        "Путешествие изменит всё",
    ],
    "МУДРОСТЬ": [
        "Мудрость придёт к тебе",
        "Ответы станут ясными",
        "Знание - твоя сила",
    ],
    "СЧАСТЬЕ": [
        "Счастье уже здесь",
        "Радость наполнит дни",
        "Улыбка не сойдёт с лица",
    ],
}


class RouletteMode(BaseMode):
    """Roulette mode - Spin the wheel of fortune.

    Flow:
    1. Intro: Wheel appears with lights animation
    2. Active: "Press to spin" prompt
    3. Processing: Wheel spinning animation
    4. Result: Display winning segment
    """

    name = "roulette"
    display_name = "ROULETTE"
    description = "Spin the wheel of fortune"
    icon = "O"
    style = "arcade"
    requires_camera = False
    requires_ai = False
    estimated_duration = 20

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Wheel state
        self._wheel_angle: float = 0.0
        self._wheel_velocity: float = 0.0
        self._target_segment: int = 0
        self._spinning: bool = False

        # Result
        self._result_segment: str = ""
        self._result_outcome: str = ""

        # Animation
        self._light_phase: float = 0.0
        self._flash_alpha: float = 0.0

        # Particles
        self._particles = ParticleSystem()

        # Colors
        self._primary = (255, 215, 0)     # Gold
        self._secondary = (255, 100, 100) # Red
        self._background = (20, 20, 40)

    def on_enter(self) -> None:
        """Initialize roulette mode."""
        self._wheel_angle = random.random() * 360
        self._wheel_velocity = 0.0
        self._spinning = False
        self._result_segment = ""
        self._result_outcome = ""
        self._flash_alpha = 0.0

        # Setup particles
        sparkle_config = ParticlePresets.sparkle(x=64, y=64)
        sparkle_config.color = self._primary
        self._particles.add_emitter("sparkles", sparkle_config)

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        """Update roulette mode."""
        self._particles.update(delta_ms)

        # Animate lights
        self._light_phase += delta_ms * 0.01

        if self.phase == ModePhase.INTRO:
            # Intro for 2 seconds
            if self._time_in_phase > 2000:
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.PROCESSING:
            # Update wheel spin
            if self._spinning:
                self._update_spin(delta_ms)

        elif self.phase == ModePhase.RESULT:
            # Flash animation decay
            self._flash_alpha = max(0, self._flash_alpha - delta_ms / 500)

            # Auto-complete after 10 seconds
            if self._time_in_phase > 10000:
                self._finish()

    def _update_spin(self, delta_ms: float) -> None:
        """Update spinning wheel physics."""
        # Apply velocity
        self._wheel_angle += self._wheel_velocity * delta_ms / 1000

        # Apply friction (exponential decay)
        friction = 0.985
        self._wheel_velocity *= friction

        # Check if stopped
        if abs(self._wheel_velocity) < 5:
            self._spinning = False
            self._on_spin_complete()

    def _on_spin_complete(self) -> None:
        """Handle spin completion."""
        # Normalize angle
        self._wheel_angle = self._wheel_angle % 360

        # Calculate winning segment
        segment_angle = 360 / len(WHEEL_SEGMENTS)
        # Adjust for pointer at top (90 degrees)
        adjusted_angle = (self._wheel_angle + 90) % 360
        segment_idx = int(adjusted_angle / segment_angle)
        segment_idx = len(WHEEL_SEGMENTS) - 1 - segment_idx  # Reverse direction

        segment = WHEEL_SEGMENTS[segment_idx % len(WHEEL_SEGMENTS)]
        self._result_segment = segment[0]  # Russian name
        self._result_outcome = random.choice(OUTCOMES_RU.get(self._result_segment, ["Удача!"]))

        # Trigger effects
        self._flash_alpha = 1.0
        sparkles = self._particles.get_emitter("sparkles")
        if sparkles:
            sparkles.burst(50)

        self.change_phase(ModePhase.RESULT)

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.event_type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.ACTIVE:
                self._start_spin()
                return True
            elif self.phase == ModePhase.RESULT:
                self._finish()
                return True

        return False

    def _start_spin(self) -> None:
        """Start the wheel spinning."""
        # Random initial velocity (fast enough for drama)
        self._wheel_velocity = random.uniform(800, 1200)
        self._spinning = True

        # Burst particles
        sparkles = self._particles.get_emitter("sparkles")
        if sparkles:
            sparkles.burst(30)

        self.change_phase(ModePhase.PROCESSING)

    def on_exit(self) -> None:
        """Cleanup."""
        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=f"{self._result_segment}: {self._result_outcome}",
            ticker_text=self._result_outcome,
            lcd_text=self._result_segment.center(16)[:16],
            should_print=True,
            print_data={
                "result": self._result_segment,
                "outcome": self._result_outcome,
                "category": "fortune_wheel",
                "type": "roulette"
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_circle, draw_line, draw_rect
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        # Background
        fill(buffer, self._background)

        font = load_font("default")
        cx, cy = 64, 64
        wheel_radius = 50

        # Draw animated border lights
        self._draw_border_lights(buffer)

        if self.phase == ModePhase.INTRO:
            # Wheel fade in
            alpha = min(1.0, self._time_in_phase / 1000)
            self._draw_wheel(buffer, cx, cy, wheel_radius, alpha)

            # Title
            draw_text_bitmap(buffer, "ROULETTE", 30, 8, self._primary, font, scale=2)

        elif self.phase == ModePhase.ACTIVE:
            self._draw_wheel(buffer, cx, cy, wheel_radius, 1.0)

            # Prompt
            if int(self._time_in_phase / 400) % 2 == 0:
                draw_text_bitmap(buffer, "SPIN!", 48, 118, self._primary, font, scale=2)

        elif self.phase == ModePhase.PROCESSING:
            self._draw_wheel(buffer, cx, cy, wheel_radius, 1.0)

            # "Spinning" text
            draw_text_bitmap(buffer, "SPINNING...", 30, 118, self._secondary, font, scale=1)

        elif self.phase == ModePhase.RESULT:
            self._draw_wheel(buffer, cx, cy, wheel_radius, 1.0)

            # Flash effect
            if self._flash_alpha > 0:
                flash_color = tuple(int(c * self._flash_alpha) for c in self._primary)
                for r in range(wheel_radius + 10, wheel_radius, -2):
                    draw_circle(buffer, cx, cy, r, flash_color, filled=False)

            # Result text
            segment_color = self._get_segment_color(self._result_segment)
            draw_text_bitmap(buffer, self._result_segment, 10, 118, segment_color, font, scale=2)

        # Draw pointer
        self._draw_pointer(buffer, cx, cy - wheel_radius - 5)

        # Render particles
        self._particles.render(buffer)

    def _draw_wheel(self, buffer, cx: int, cy: int, radius: int, alpha: float) -> None:
        """Draw the roulette wheel."""
        from artifact.graphics.primitives import draw_circle, draw_line

        segment_count = len(WHEEL_SEGMENTS)
        segment_angle = 360 / segment_count

        # Draw segments
        for i, (name_ru, name_en, color) in enumerate(WHEEL_SEGMENTS):
            start_angle = i * segment_angle + self._wheel_angle
            end_angle = start_angle + segment_angle

            # Draw segment as filled pie (simplified as triangular sections)
            adjusted_color = tuple(int(c * alpha) for c in color)

            # Draw segment outline
            for angle in range(int(start_angle), int(end_angle) + 1, 5):
                rad = math.radians(angle)
                x = int(cx + radius * math.cos(rad))
                y = int(cy + radius * math.sin(rad))
                draw_circle(buffer, x, y, 2, adjusted_color)

            # Draw segment line
            rad1 = math.radians(start_angle)
            rad2 = math.radians(end_angle)
            x1 = int(cx + radius * math.cos(rad1))
            y1 = int(cy + radius * math.sin(rad1))
            x2 = int(cx + radius * math.cos(rad2))
            y2 = int(cy + radius * math.sin(rad2))
            draw_line(buffer, cx, cy, x1, y1, adjusted_color)
            draw_line(buffer, cx, cy, x2, y2, adjusted_color)

        # Center hub
        draw_circle(buffer, cx, cy, 12, (40, 40, 60))
        draw_circle(buffer, cx, cy, 8, (60, 60, 80))

    def _draw_pointer(self, buffer, x: int, y: int) -> None:
        """Draw the wheel pointer."""
        from artifact.graphics.primitives import draw_line

        # Triangle pointer pointing down
        draw_line(buffer, x, y, x - 8, y - 12, self._primary)
        draw_line(buffer, x, y, x + 8, y - 12, self._primary)
        draw_line(buffer, x - 8, y - 12, x + 8, y - 12, self._primary)

    def _draw_border_lights(self, buffer) -> None:
        """Draw animated border lights."""
        from artifact.graphics.primitives import draw_circle

        light_count = 16
        for i in range(light_count):
            # Calculate position along border
            t = i / light_count
            if t < 0.25:  # Top
                x = int(t * 4 * 128)
                y = 2
            elif t < 0.5:  # Right
                x = 126
                y = int((t - 0.25) * 4 * 128)
            elif t < 0.75:  # Bottom
                x = int((1 - (t - 0.5) * 4) * 128)
                y = 126
            else:  # Left
                x = 2
                y = int((1 - (t - 0.75) * 4) * 128)

            # Animated brightness
            phase = (self._light_phase + i * 0.5) % (math.pi * 2)
            brightness = 0.3 + 0.7 * max(0, math.sin(phase))

            # Alternate colors
            if i % 2 == 0:
                color = tuple(int(c * brightness) for c in self._primary)
            else:
                color = tuple(int(c * brightness) for c in self._secondary)

            draw_circle(buffer, x, y, 3, color)

    def _get_segment_color(self, segment_name: str) -> Tuple[int, int, int]:
        """Get the color for a segment name."""
        for name_ru, name_en, color in WHEEL_SEGMENTS:
            if name_ru == segment_name:
                return color
        return (255, 255, 255)

    def render_ticker(self, buffer) -> None:
        """Render ticker."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        clear(buffer)
        font = load_font("default")

        if self.phase == ModePhase.ACTIVE:
            text = "PRESS TO SPIN THE WHEEL! "
            scroll = int(self._time_in_phase / 80) % (len(text) * 4 + 48)
            draw_text_bitmap(buffer, text * 2, 48 - scroll, 1, self._primary, font, scale=1)

        elif self.phase == ModePhase.PROCESSING:
            # Spinning indicator
            bars = "|/-\\"
            bar_idx = int(self._time_in_phase / 100) % 4
            draw_text_bitmap(buffer, f"SPINNING {bars[bar_idx]}", 2, 1, self._secondary, font, scale=1)

        elif self.phase == ModePhase.RESULT:
            text = self._result_outcome + " "
            scroll = int(self._time_in_phase / 100) % (len(text) * 4 + 48)
            color = self._get_segment_color(self._result_segment)
            draw_text_bitmap(buffer, text, 48 - scroll, 1, color, font, scale=1)

        else:
            draw_text_bitmap(buffer, "ROULETTE", 8, 1, self._primary, font, scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self.phase == ModePhase.ACTIVE:
            return "PRESS TO SPIN!".center(16)
        elif self.phase == ModePhase.PROCESSING:
            return "SPINNING...".center(16)
        elif self.phase == ModePhase.RESULT:
            return self._result_segment.center(16)[:16]
        return "ROULETTE".center(16)

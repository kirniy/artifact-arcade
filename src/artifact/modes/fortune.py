"""Fortune Teller mode - Random mystical predictions."""

from typing import List, Optional
import random

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, ParticlePresets


# Russian fortunes database
FORTUNES_RU = [
    "Удача уже в пути к тебе",
    "Скоро исполнится заветное желание",
    "Звёзды говорят о большой любви",
    "Ждёт неожиданная радость",
    "Впереди важная встреча",
    "Деньги придут откуда не ждёшь",
    "Твоя интуиция тебя не подведёт",
    "Смелость откроет новые двери",
    "Старый друг напомнит о себе",
    "Путешествие изменит всё",
    "Тайна скоро раскроется",
    "Здоровье улучшится",
    "Творчество принесёт плоды",
    "Новое знакомство важнее чем кажется",
    "Терпение будет вознаграждено",
    "Мечта ближе чем думаешь",
    "Судьба готовит сюрприз",
    "Все препятствия временны",
    "Верь в себя - и победишь",
    "Счастье уже рядом",
]

FORTUNES_EN = [
    "Luck is already on its way",
    "A wish will soon come true",
    "Stars speak of great love",
    "Unexpected joy awaits",
    "An important meeting ahead",
    "Money from unexpected source",
    "Trust your intuition",
    "Courage opens new doors",
    "An old friend will appear",
    "A journey will change everything",
    "A secret will be revealed",
    "Health will improve",
    "Creativity brings rewards",
    "New acquaintance is important",
    "Patience will be rewarded",
    "Dream is closer than you think",
    "Fate prepares a surprise",
    "All obstacles are temporary",
    "Believe in yourself and win",
    "Happiness is already near",
]


class FortuneMode(BaseMode):
    """Fortune Teller mode - mystical random predictions.

    Flow:
    1. Intro: Crystal ball animation
    2. Active: "Press button to reveal fate"
    3. Processing: Mystical reveal animation
    4. Result: Display fortune
    """

    name = "fortune"
    display_name = "ГАДАЛКА"
    description = "Узнай свою судьбу"
    icon = "*"
    style = "mystical"
    requires_camera = False
    requires_ai = False
    estimated_duration = 15

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # State
        self._fortune: str = ""
        self._reveal_progress: float = 0.0
        self._ball_glow: float = 0.0
        self._waiting_for_reveal: bool = False

        # Particles
        self._particles = ParticleSystem()

        # Colors
        self._primary = (107, 33, 168)   # Purple
        self._secondary = (245, 158, 11)  # Gold
        self._accent = (20, 184, 166)     # Teal

    def on_enter(self) -> None:
        """Initialize fortune mode."""
        self._fortune = ""
        self._reveal_progress = 0.0
        self._waiting_for_reveal = False

        # Setup particles
        star_config = ParticlePresets.stars(x=64, y=64)
        star_config.color = self._secondary
        self._particles.add_emitter("stars", star_config)

        magic_config = ParticlePresets.magic(x=64, y=70)
        magic_config.color = self._primary
        self._particles.add_emitter("magic", magic_config)

        # Start intro animation
        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        """Update fortune mode."""
        self._particles.update(delta_ms)

        # Animate ball glow
        import math
        self._ball_glow = 0.5 + 0.5 * math.sin(self._time_in_mode / 500)

        if self.phase == ModePhase.INTRO:
            # Intro lasts 2 seconds
            if self._time_in_phase > 2000:
                self.change_phase(ModePhase.ACTIVE)
                self._waiting_for_reveal = True

        elif self.phase == ModePhase.PROCESSING:
            # Reveal animation
            self._reveal_progress = min(1.0, self._time_in_phase / 2000)

            if self._reveal_progress >= 1.0:
                self.change_phase(ModePhase.RESULT)

        elif self.phase == ModePhase.RESULT:
            # Auto-complete after 10 seconds
            if self._time_in_phase > 10000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.event_type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.ACTIVE and self._waiting_for_reveal:
                self._reveal_fortune()
                return True
            elif self.phase == ModePhase.RESULT:
                self._finish()
                return True

        return False

    def on_exit(self) -> None:
        """Cleanup."""
        self._particles.clear_all()
        self.stop_animations()

    def _reveal_fortune(self) -> None:
        """Start fortune reveal."""
        self._waiting_for_reveal = False

        # Pick random fortune
        fortunes = FORTUNES_RU  # Use Russian by default
        self._fortune = random.choice(fortunes)

        # Burst particles
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(30)

        self.change_phase(ModePhase.PROCESSING)

    def _finish(self) -> None:
        """Complete the mode."""
        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=self._fortune,
            ticker_text=self._fortune,
            lcd_text="YOUR FORTUNE",
            should_print=True,
            print_data={
                "fortune": self._fortune,
                "type": "fortune_teller"
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_circle, draw_rect
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        import math

        # Background
        fill(buffer, (30, 27, 75))

        # Crystal ball
        cx, cy = 64, 60
        ball_radius = 35

        # Outer glow
        glow_intensity = 0.3 + 0.2 * self._ball_glow
        for r in range(ball_radius + 15, ball_radius, -2):
            alpha = (r - ball_radius) / 15 * glow_intensity
            color = tuple(int(c * alpha) for c in self._primary)
            draw_circle(buffer, cx, cy, r, color, filled=False)

        # Ball gradient
        for r in range(ball_radius, 0, -1):
            factor = r / ball_radius
            color = tuple(int(c * factor * 0.8 + 30) for c in self._primary)
            draw_circle(buffer, cx, cy, r, color)

        # Highlight
        draw_circle(buffer, cx - 10, cy - 10, 8, (150, 120, 180))
        draw_circle(buffer, cx - 8, cy - 8, 4, (200, 180, 220))

        # Render particles
        self._particles.render(buffer)

        font = load_font("cyrillic")

        if self.phase == ModePhase.INTRO:
            # Title
            draw_text_bitmap(buffer, "ГАДАЛКА", 30, 10, self._secondary, font, scale=2)

        elif self.phase == ModePhase.ACTIVE:
            # Prompt
            if int(self._time_in_phase / 500) % 2 == 0:
                draw_text_bitmap(buffer, "НАЖМИ", 40, 100, self._secondary, font, scale=1)
                draw_text_bitmap(buffer, "КНОПКУ", 40, 112, self._secondary, font, scale=1)

        elif self.phase == ModePhase.PROCESSING:
            # Swirling animation inside ball
            angle = self._time_in_phase / 100
            for i in range(5):
                a = angle + i * 72
                r = 20 * self._reveal_progress
                x = int(cx + r * math.cos(math.radians(a)))
                y = int(cy + r * math.sin(math.radians(a)))
                draw_circle(buffer, x, y, 3, self._secondary)

        elif self.phase == ModePhase.RESULT:
            # Display fortune text
            words = self._fortune.split()
            lines = []
            current_line = ""

            for word in words:
                test_line = current_line + " " + word if current_line else word
                if len(test_line) <= 12:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            y = 15
            for line in lines[:5]:
                line_w, _ = font.measure_text(line)
                x = (128 - line_w * 2) // 2
                draw_text_bitmap(buffer, line, x, y, self._secondary, font, scale=2)
                y += 18

    def render_ticker(self, buffer) -> None:
        """Render ticker."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        clear(buffer)
        font = load_font("cyrillic")

        if self.phase in (ModePhase.INTRO, ModePhase.ACTIVE):
            # Scrolling mystical text
            text = "УЗНАЙ СВОЮ СУДЬБУ... "
            scroll = int(self._time_in_phase / 80) % (len(text) * 4 + 48)
            draw_text_bitmap(buffer, text * 2, 48 - scroll, 1, self._secondary, font, scale=1)

        elif self.phase == ModePhase.RESULT:
            # Show fortune
            scroll = int(self._time_in_phase / 100) % (len(self._fortune) * 4 + 48)
            draw_text_bitmap(buffer, self._fortune, 48 - scroll, 1, self._secondary, font, scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self.phase == ModePhase.ACTIVE:
            return "НАЖМИ КНОПКУ".center(16)
        elif self.phase == ModePhase.PROCESSING:
            return "ГАДАЮ...".center(16)
        elif self.phase == ModePhase.RESULT:
            return "ТВОЯ СУДЬБА".center(16)
        return "ГАДАЛКА".center(16)[:16]

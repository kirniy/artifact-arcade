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


# Party wheel segments - more exciting prizes and dares!
# Each has: (Russian text, symbol for wheel, color, rarity)
# Rarity: 1=common, 2=uncommon, 3=rare, 4=legendary
WHEEL_SEGMENTS = [
    ("ШОТИК!", "🥃", (46, 204, 113), 1),          # Shot - Green
    ("ТАНЦУЙ!", "💃", (241, 196, 15), 1),          # Dance - Yellow
    ("ОБНИМИ!", "🤗", (52, 152, 219), 1),          # Hug dare - Blue
    ("СКИДКА 15%", "💰", (155, 89, 182), 2),       # Discount - Purple
    ("ПОЦЕЛУЙ!", "💋", (231, 76, 60), 2),          # Kiss dare - Red
    ("КОКТЕЙЛЬ!", "🍹", (230, 126, 34), 2),        # Free cocktail - Orange
    ("ФОТО+ШАРЖ", "📸", (149, 165, 200), 3),       # Photo + caricature - Blue-gray
    ("ДЖЕКПОТ!", "⭐", (255, 215, 0), 4),          # Jackpot - Gold!
    ("КОМПЛИМЕНТ", "💝", (255, 150, 200), 1),      # Give compliment - Pink
    ("СЕЛФИ!", "🤳", (100, 200, 255), 1),          # Selfie - Light blue
    ("ЕЩЁ РАЗ!", "🔄", (200, 200, 200), 2),        # Spin again - Silver
    ("ЖЕЛАНИЕ!", "✨", (255, 180, 100), 3),        # Make a wish - Orange-gold
]

# Fun outcomes for each segment (what gets printed on receipt)
OUTCOMES_RU = {
    "ШОТИК!": [
        "Бармен ждёт тебя!",
        "Один шот за счёт колеса!",
        "Выпей за фортуну!",
        "Шот-шот-шот!",
    ],
    "ТАНЦУЙ!": [
        "Покажи свои движения!",
        "Танцуй как никто не смотрит!",
        "На танцпол, звезда!",
        "Твой момент славы!",
    ],
    "ОБНИМИ!": [
        "Обними того, кто рядом!",
        "Тёплые обнимашки!",
        "Раздай обнимашки!",
        "Мир нуждается в объятиях!",
    ],
    "СКИДКА 15%": [
        "Скидка 15% в баре!",
        "Покажи этот чек бармену!",
        "VIP статус активирован!",
        "Экономия = ещё один коктейль!",
    ],
    "ПОЦЕЛУЙ!": [
        "Поцелуй того, кто рядом!",
        "Найди кого-то милого!",
        "Романтика в воздухе!",
        "Чмок-чмок!",
    ],
    "КОКТЕЙЛЬ!": [
        "Бесплатный коктейль!",
        "Покажи бармену этот чек!",
        "Колесо угощает!",
        "Твой напиток ждёт!",
    ],
    "ФОТО+ШАРЖ": [
        "Бесплатное фото и шарж!",
        "Ты выиграл портрет!",
        "ИИ нарисует тебя!",
        "Попозируй на камеру!",
    ],
    "ДЖЕКПОТ!": [
        "★ ДЖЕКПОТ! ★",
        "ТЫ ВЫИГРАЛ ГЛАВНЫЙ ПРИЗ!",
        "Покажи бармену СЕЙЧАС!",
        "Сегодня твой день!",
    ],
    "КОМПЛИМЕНТ": [
        "Скажи комплимент незнакомцу!",
        "Сделай чей-то вечер лучше!",
        "Добрые слова = добрая карма!",
        "Подари улыбку!",
    ],
    "СЕЛФИ!": [
        "Сделай селфи с машиной!",
        "Запости в сторис!",
        "Поза для Instagram!",
        "Улыбочку! 📸",
    ],
    "ЕЩЁ РАЗ!": [
        "Крути ещё раз БЕСПЛАТНО!",
        "Удача дала второй шанс!",
        "Ещё одна попытка!",
        "Фортуна улыбается!",
    ],
    "ЖЕЛАНИЕ!": [
        "Загадай желание!",
        "Шепни вселенной мечту!",
        "Желание исполнится!",
        "Магия уже работает!",
    ],
}

# Legacy compatibility - map old segments
LEGACY_OUTCOMES = {
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
    display_name = "РУЛЕТКА"
    description = "Крути колесо судьбы"
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
        self._click_cooldown: float = 0.0  # For click sound timing

        # Result
        self._result_segment: str = ""
        self._result_outcome: str = ""
        self._result_rarity: int = 1

        # Animation
        self._light_phase: float = 0.0
        self._flash_alpha: float = 0.0
        self._pulse_phase: float = 0.0
        self._shake_amount: float = 0.0
        self._glow_intensity: float = 0.0
        self._celebration_time: float = 0.0

        # Particles
        self._particles = ParticleSystem()

        # Colors - more vibrant
        self._primary = (255, 215, 0)      # Gold
        self._secondary = (255, 50, 80)    # Vibrant red
        self._background = (15, 15, 35)    # Darker for contrast
        self._glow_color = (255, 200, 100) # Warm glow

    def on_enter(self) -> None:
        """Initialize roulette mode."""
        self._wheel_angle = random.random() * 360
        self._wheel_velocity = 0.0
        self._spinning = False
        self._result_segment = ""
        self._result_outcome = ""
        self._result_rarity = 1
        self._flash_alpha = 0.0
        self._pulse_phase = 0.0
        self._shake_amount = 0.0
        self._glow_intensity = 0.0
        self._celebration_time = 0.0
        self._click_cooldown = 0.0

        # Setup particles - multiple emitters for layered effects
        sparkle_config = ParticlePresets.sparkle(x=64, y=64)
        sparkle_config.color = self._primary
        sparkle_config.emission_rate = 2.0
        self._particles.add_emitter("sparkles", sparkle_config)

        # Fire/celebration particles
        fire_config = ParticlePresets.fire(x=64, y=100)
        fire_config.color = (255, 150, 50)
        fire_config.emission_rate = 0.0  # Only burst on win
        self._particles.add_emitter("fire", fire_config)

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        """Update roulette mode."""
        self._particles.update(delta_ms)

        # Animate lights (faster when spinning)
        light_speed = 0.03 if self._spinning else 0.01
        self._light_phase += delta_ms * light_speed

        # Pulse animation
        self._pulse_phase += delta_ms * 0.005

        # Decay shake
        self._shake_amount = max(0, self._shake_amount - delta_ms / 200)

        # Click cooldown
        self._click_cooldown = max(0, self._click_cooldown - delta_ms)

        if self.phase == ModePhase.INTRO:
            # Longer intro with glow fade-in - 2.5 seconds
            self._glow_intensity = min(1.0, self._time_in_phase / 1500)
            if self._time_in_phase > 2500:
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.ACTIVE:
            # Pulsing glow effect to attract attention
            self._glow_intensity = 0.5 + 0.5 * math.sin(self._pulse_phase)

        elif self.phase == ModePhase.PROCESSING:
            # Update wheel spin
            if self._spinning:
                self._update_spin(delta_ms)
                # Increase glow based on speed
                self._glow_intensity = min(1.0, abs(self._wheel_velocity) / 800)

        elif self.phase == ModePhase.RESULT:
            # Flash animation decay
            self._flash_alpha = max(0, self._flash_alpha - delta_ms / 800)

            # Celebration time for rare wins
            self._celebration_time += delta_ms
            if self._result_rarity >= 3:  # Rare or legendary
                # Continuous particle bursts
                if int(self._celebration_time / 300) > int((self._celebration_time - delta_ms) / 300):
                    fire = self._particles.get_emitter("fire")
                    if fire:
                        fire.burst(15)

            # Auto-complete after 15 seconds (more time to celebrate)
            if self._time_in_phase > 15000:
                self._finish()

    def _update_spin(self, delta_ms: float) -> None:
        """Update spinning wheel physics with click effects."""
        # Track segment changes for "click" effect
        old_segment = int((self._wheel_angle % 360) / (360 / len(WHEEL_SEGMENTS)))

        # Apply velocity
        self._wheel_angle += self._wheel_velocity * delta_ms / 1000

        # New segment check
        new_segment = int((self._wheel_angle % 360) / (360 / len(WHEEL_SEGMENTS)))
        if old_segment != new_segment and self._click_cooldown <= 0:
            # "Click" effect - small shake
            self._shake_amount = 0.5
            self._click_cooldown = 50  # 50ms between clicks

        # Apply friction (exponential decay) - slower for more drama
        friction = 0.988 if self._wheel_velocity > 200 else 0.975
        self._wheel_velocity *= friction

        # Check if stopped
        if abs(self._wheel_velocity) < 8:
            self._spinning = False
            self._on_spin_complete()

    def _on_spin_complete(self) -> None:
        """Handle spin completion with rarity-based celebration."""
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
        self._result_rarity = segment[3]   # Rarity level
        self._result_outcome = random.choice(OUTCOMES_RU.get(self._result_segment, ["Удача!"]))

        # Trigger effects based on rarity
        self._flash_alpha = 1.0
        self._celebration_time = 0.0

        sparkles = self._particles.get_emitter("sparkles")
        fire = self._particles.get_emitter("fire")

        if self._result_rarity >= 4:  # Legendary (Jackpot)
            # MASSIVE celebration
            if sparkles:
                sparkles.burst(100)
            if fire:
                fire.burst(50)
            self._shake_amount = 2.0
        elif self._result_rarity >= 3:  # Rare
            if sparkles:
                sparkles.burst(70)
            if fire:
                fire.burst(30)
            self._shake_amount = 1.5
        elif self._result_rarity >= 2:  # Uncommon
            if sparkles:
                sparkles.burst(50)
            self._shake_amount = 1.0
        else:  # Common
            if sparkles:
                sparkles.burst(30)
            self._shake_amount = 0.5

        self.change_phase(ModePhase.RESULT)

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
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
        """Render main display with enhanced effects."""
        from artifact.graphics.primitives import fill, draw_circle, draw_line, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

        # Background with subtle gradient effect
        fill(buffer, self._background)

        # Add shake offset
        shake_x = int(random.uniform(-1, 1) * self._shake_amount * 3) if self._shake_amount > 0 else 0
        shake_y = int(random.uniform(-1, 1) * self._shake_amount * 3) if self._shake_amount > 0 else 0

        # Position wheel in center but leave room for text
        cx, cy = 64 + shake_x, 55 + shake_y
        wheel_radius = 42

        # Draw animated border lights
        self._draw_border_lights(buffer)

        # Draw outer glow around wheel
        if self._glow_intensity > 0:
            for r in range(wheel_radius + 12, wheel_radius + 3, -2):
                glow_alpha = self._glow_intensity * (wheel_radius + 12 - r) / 9 * 0.5
                glow_color = tuple(int(c * glow_alpha) for c in self._glow_color)
                draw_circle(buffer, cx, cy, r, glow_color, filled=False)

        if self.phase == ModePhase.INTRO:
            # Wheel fade in with glow
            alpha = min(1.0, self._time_in_phase / 1000)
            self._draw_wheel(buffer, cx, cy, wheel_radius, alpha)

            # Animated title
            draw_animated_text(buffer, "РУЛЕТКА", 3, self._primary, self._time_in_phase, TextEffect.GLOW, scale=2)

        elif self.phase == ModePhase.ACTIVE:
            self._draw_wheel(buffer, cx, cy, wheel_radius, 1.0)

            # Pulsing prompt
            pulse = 0.7 + 0.3 * math.sin(self._pulse_phase * 2)
            prompt_color = tuple(int(c * pulse) for c in self._primary)

            if int(self._time_in_phase / 500) % 2 == 0:
                draw_centered_text(buffer, "КРУТИ!", 108, prompt_color, scale=2)
            else:
                draw_centered_text(buffer, "ЖМИКНОПКУ", 108, (150, 150, 150), scale=1)

        elif self.phase == ModePhase.PROCESSING:
            self._draw_wheel(buffer, cx, cy, wheel_radius, 1.0)

            # Animated spinning text with glitch
            draw_animated_text(buffer, "КРУЧУ", 108, self._secondary, self._time_in_phase, TextEffect.GLITCH, scale=2)

        elif self.phase == ModePhase.RESULT:
            self._draw_wheel(buffer, cx, cy, wheel_radius, 1.0)

            # Flash effect with rarity-based color
            if self._flash_alpha > 0:
                segment_color = self._get_segment_color(self._result_segment)
                flash_color = tuple(int(c * self._flash_alpha) for c in segment_color)
                for r in range(wheel_radius + 15, wheel_radius, -2):
                    draw_circle(buffer, cx, cy, r, flash_color, filled=False)

            # Result text with rarity-based effects
            segment_color = self._get_segment_color(self._result_segment)

            if self._result_rarity >= 4:  # Legendary - rainbow effect
                draw_animated_text(buffer, self._result_segment, 108, segment_color, self._time_in_phase, TextEffect.RAINBOW, scale=2)
            elif self._result_rarity >= 3:  # Rare - glow effect
                draw_animated_text(buffer, self._result_segment, 108, segment_color, self._time_in_phase, TextEffect.GLOW, scale=2)
            else:
                draw_centered_text(buffer, self._result_segment, 108, segment_color, scale=2)

        # Draw pointer (above wheel)
        self._draw_pointer(buffer, 64, 55 - wheel_radius - 3)

        # Render particles
        self._particles.render(buffer)

    def _draw_wheel(self, buffer, cx: int, cy: int, radius: int, alpha: float) -> None:
        """Draw an improved roulette wheel with filled segments."""
        from artifact.graphics.primitives import draw_circle, draw_line

        segment_count = len(WHEEL_SEGMENTS)
        segment_angle = 360 / segment_count

        # Draw filled segments using radial fill technique
        for i, (name_ru, symbol, color, rarity) in enumerate(WHEEL_SEGMENTS):
            start_angle = i * segment_angle + self._wheel_angle
            end_angle = start_angle + segment_angle

            adjusted_color = tuple(int(c * alpha) for c in color)
            darker_color = tuple(int(c * alpha * 0.6) for c in color)

            # Fill segment with concentric arcs
            for r in range(radius, 15, -2):
                # Gradient from edge to center
                gradient = r / radius
                fill_color = tuple(int(c * gradient + darker_color[j] * (1 - gradient))
                                 for j, c in enumerate(adjusted_color))

                for angle in range(int(start_angle), int(end_angle) + 1, 3):
                    rad = math.radians(angle)
                    x = int(cx + r * math.cos(rad))
                    y = int(cy + r * math.sin(rad))
                    if 0 <= x < 128 and 0 <= y < 128:
                        buffer[y, x] = fill_color

            # Draw segment divider lines
            rad1 = math.radians(start_angle)
            x1 = int(cx + radius * math.cos(rad1))
            y1 = int(cy + radius * math.sin(rad1))
            draw_line(buffer, cx, cy, x1, y1, (30, 30, 50))

        # Draw outer rim
        for angle in range(0, 360, 2):
            rad = math.radians(angle + self._wheel_angle)
            x = int(cx + radius * math.cos(rad))
            y = int(cy + radius * math.sin(rad))
            # Alternating colors on rim
            if int(angle / (360 / segment_count)) % 2 == 0:
                rim_color = (200, 180, 100)
            else:
                rim_color = (150, 130, 80)
            draw_circle(buffer, x, y, 2, tuple(int(c * alpha) for c in rim_color))

        # Draw inner rim with pegs/notches
        inner_radius = radius - 5
        for i in range(segment_count):
            angle = i * segment_angle + self._wheel_angle + segment_angle / 2
            rad = math.radians(angle)
            peg_x = int(cx + inner_radius * math.cos(rad))
            peg_y = int(cy + inner_radius * math.sin(rad))
            draw_circle(buffer, peg_x, peg_y, 2, (255, 215, 0))  # Gold pegs

        # Center hub with gradient
        for r in range(16, 0, -1):
            hub_brightness = 40 + int(60 * (1 - r / 16))
            hub_color = (hub_brightness, hub_brightness, hub_brightness + 20)
            draw_circle(buffer, cx, cy, r, tuple(int(c * alpha) for c in hub_color), filled=False)

        # Hub shine effect
        draw_circle(buffer, cx - 3, cy - 3, 4, tuple(int(c * alpha) for c in (120, 120, 140)))
        draw_circle(buffer, cx, cy, 5, tuple(int(c * alpha) for c in (80, 80, 100)))

    def _draw_pointer(self, buffer, x: int, y: int) -> None:
        """Draw an improved wheel pointer."""
        from artifact.graphics.primitives import draw_line, draw_circle

        # Larger, more visible pointer
        pointer_size = 10

        # Outer glow
        for offset in range(3, 0, -1):
            glow_color = tuple(int(c * (0.3 / offset)) for c in self._primary)
            draw_line(buffer, x, y + pointer_size + offset, x - 6 - offset, y - 2, glow_color)
            draw_line(buffer, x, y + pointer_size + offset, x + 6 + offset, y - 2, glow_color)

        # Main pointer body - filled triangle pointing down
        for py in range(pointer_size):
            width = int((pointer_size - py) * 0.6)
            for px in range(-width, width + 1):
                bx = x + px
                by = y + py
                if 0 <= bx < 128 and 0 <= by < 128:
                    buffer[by, bx] = self._primary

        # Highlight
        draw_line(buffer, x - 2, y + 2, x, y + pointer_size - 2, (255, 255, 200))

        # Bottom tip accent
        draw_circle(buffer, x, y + pointer_size, 2, self._secondary)

    def _draw_border_lights(self, buffer) -> None:
        """Draw animated border lights - casino style."""
        from artifact.graphics.primitives import draw_circle

        # More lights for better effect
        light_count = 24
        for i in range(light_count):
            # Calculate position along border
            t = i / light_count
            if t < 0.25:  # Top
                lx = int(t * 4 * 124) + 2
                ly = 2
            elif t < 0.5:  # Right
                lx = 125
                ly = int((t - 0.25) * 4 * 124) + 2
            elif t < 0.75:  # Bottom
                lx = int((1 - (t - 0.5) * 4) * 124) + 2
                ly = 125
            else:  # Left
                lx = 2
                ly = int((1 - (t - 0.75) * 4) * 124) + 2

            # Chase pattern when spinning, alternate when not
            if self._spinning:
                # Chase light effect
                chase_pos = int(self._light_phase * 3) % light_count
                distance = min(abs(i - chase_pos), light_count - abs(i - chase_pos))
                brightness = max(0.2, 1.0 - distance * 0.15)
            else:
                # Gentle pulse
                phase = (self._light_phase * 2 + i * 0.4) % (math.pi * 2)
                brightness = 0.4 + 0.6 * max(0, math.sin(phase))

            # Color based on position and phase
            if i % 3 == 0:
                color = tuple(int(c * brightness) for c in self._primary)
            elif i % 3 == 1:
                color = tuple(int(c * brightness) for c in self._secondary)
            else:
                color = tuple(int(c * brightness) for c in (100, 200, 255))  # Cyan

            draw_circle(buffer, lx, ly, 3, color)
            # Inner bright spot
            if brightness > 0.7:
                draw_circle(buffer, lx, ly, 1, (255, 255, 255))

    def _get_segment_color(self, segment_name: str) -> Tuple[int, int, int]:
        """Get the color for a segment name."""
        for name_ru, symbol, color, rarity in WHEEL_SEGMENTS:
            if name_ru == segment_name:
                return color
        return (255, 255, 255)

    def render_ticker(self, buffer) -> None:
        """Render ticker with smooth seamless scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, render_ticker_static, TickerEffect, TextEffect

        clear(buffer)

        if self.phase == ModePhase.INTRO:
            # Intro scrolling text
            render_ticker_animated(
                buffer, "КОЛЕСО ФОРТУНЫ",
                self._time_in_phase, self._primary,
                TickerEffect.RAINBOW_SCROLL, speed=0.025
            )

        elif self.phase == ModePhase.ACTIVE:
            # Action prompt with sparkle
            render_ticker_animated(
                buffer, "НАЖМИ ЧТОБЫ КРУТИТЬ",
                self._time_in_phase, self._primary,
                TickerEffect.SPARKLE_SCROLL, speed=0.028
            )

        elif self.phase == ModePhase.PROCESSING:
            # Spinning animation with glitch effect
            render_ticker_animated(
                buffer, "КРУЧУ КОЛЕСО",
                self._time_in_phase, self._secondary,
                TickerEffect.GLITCH_SCROLL, speed=0.04
            )

        elif self.phase == ModePhase.RESULT:
            # Result with wave effect
            color = self._get_segment_color(self._result_segment)
            render_ticker_animated(
                buffer, self._result_outcome,
                self._time_in_phase, color,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )

    def get_lcd_text(self) -> str:
        """Get LCD text with spinning animation."""
        if self.phase == ModePhase.ACTIVE:
            # Animated prompt
            frame = int(self._time_in_phase / 300) % 4
            arrows = ["◄►", "◄►", "►◄", "►◄"]
            return f" {arrows[frame]} КРУТИ {arrows[frame]} "[:16]
        elif self.phase == ModePhase.PROCESSING:
            # Spinning animation
            spinner = "◐◓◑◒"
            spin = spinner[int(self._time_in_phase / 100) % 4]
            return f" {spin} КРУЧУ {spin} "[:16]
        elif self.phase == ModePhase.RESULT:
            # Show prize with emoji
            segment_info = None
            for name_ru, symbol, _ in WHEEL_SEGMENTS:
                if name_ru == self._result_segment:
                    segment_info = (name_ru, symbol)
                    break
            if segment_info:
                return f"►{segment_info[0][:10]}◄".center(16)[:16]
            return f"►{self._result_segment[:10]}◄".center(16)[:16]
        return " ◆ РУЛЕТКА ◆ ".center(16)

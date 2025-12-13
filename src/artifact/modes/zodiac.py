"""Zodiac mode - Birthday to horoscope predictions."""

from typing import List, Optional, Tuple
from datetime import date
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, ParticlePresets


# Zodiac signs with date ranges and symbols
ZODIAC_SIGNS = [
    ("Aries", "Овен", (3, 21), (4, 19), "♈"),
    ("Taurus", "Телец", (4, 20), (5, 20), "♉"),
    ("Gemini", "Близнецы", (5, 21), (6, 20), "♊"),
    ("Cancer", "Рак", (6, 21), (7, 22), "♋"),
    ("Leo", "Лев", (7, 23), (8, 22), "♌"),
    ("Virgo", "Дева", (8, 23), (9, 22), "♍"),
    ("Libra", "Весы", (9, 23), (10, 22), "♎"),
    ("Scorpio", "Скорпион", (10, 23), (11, 21), "♏"),
    ("Sagittarius", "Стрелец", (11, 22), (12, 21), "♐"),
    ("Capricorn", "Козерог", (12, 22), (1, 19), "♑"),
    ("Aquarius", "Водолей", (1, 20), (2, 18), "♒"),
    ("Pisces", "Рыбы", (2, 19), (3, 20), "♓"),
]

# Russian horoscope predictions by zodiac sign
HOROSCOPES_RU = {
    "Aries": [
        "Сегодня звёзды на твоей стороне",
        "Смелость принесёт успех",
        "Время действовать решительно",
        "Энергия бьёт ключом",
    ],
    "Taurus": [
        "Стабильность укрепится",
        "Финансовая удача близко",
        "Терпение вознаградится",
        "Комфорт и уют ждут тебя",
    ],
    "Gemini": [
        "Новые знакомства изменят всё",
        "Общение принесёт радость",
        "Двойственность станет силой",
        "Идеи получат признание",
    ],
    "Cancer": [
        "Семья подарит счастье",
        "Интуиция не подведёт",
        "Дом станет крепостью",
        "Забота вернётся сторицей",
    ],
    "Leo": [
        "Время сиять ярче всех",
        "Творчество принесёт успех",
        "Лидерство откроет двери",
        "Признание уже в пути",
    ],
    "Virgo": [
        "Внимание к деталям спасёт",
        "Порядок принесёт покой",
        "Анализ даст ответы",
        "Здоровье укрепится",
    ],
    "Libra": [
        "Гармония восстановится",
        "Партнёрство принесёт плоды",
        "Красота спасёт мир",
        "Справедливость восторжествует",
    ],
    "Scorpio": [
        "Тайны раскроются",
        "Трансформация неизбежна",
        "Страсть укажет путь",
        "Глубина станет силой",
    ],
    "Sagittarius": [
        "Путешествие изменит жизнь",
        "Оптимизм притянет удачу",
        "Свобода станет ключом",
        "Философия откроет истину",
    ],
    "Capricorn": [
        "Карьера пойдёт в гору",
        "Амбиции реализуются",
        "Дисциплина окупится",
        "Статус укрепится",
    ],
    "Aquarius": [
        "Оригинальность победит",
        "Будущее в твоих руках",
        "Дружба станет опорой",
        "Инновации принесут успех",
    ],
    "Pisces": [
        "Мечты начнут сбываться",
        "Творчество исцелит душу",
        "Интуиция укажет путь",
        "Сострадание вернётся",
    ],
}

# English horoscopes
HOROSCOPES_EN = {
    "Aries": [
        "Stars align in your favor today",
        "Courage will bring success",
        "Time to act decisively",
        "Energy is at its peak",
    ],
    "Taurus": [
        "Stability will strengthen",
        "Financial luck approaches",
        "Patience will be rewarded",
        "Comfort and coziness await",
    ],
    "Gemini": [
        "New connections will change everything",
        "Communication brings joy",
        "Duality becomes strength",
        "Ideas will gain recognition",
    ],
    "Cancer": [
        "Family will bring happiness",
        "Intuition won't fail you",
        "Home becomes a fortress",
        "Care returns tenfold",
    ],
    "Leo": [
        "Time to shine brightest",
        "Creativity brings success",
        "Leadership opens doors",
        "Recognition is on its way",
    ],
    "Virgo": [
        "Attention to detail saves the day",
        "Order brings peace",
        "Analysis provides answers",
        "Health will strengthen",
    ],
    "Libra": [
        "Harmony will be restored",
        "Partnership bears fruit",
        "Beauty saves the world",
        "Justice will prevail",
    ],
    "Scorpio": [
        "Secrets will be revealed",
        "Transformation is inevitable",
        "Passion shows the way",
        "Depth becomes strength",
    ],
    "Sagittarius": [
        "Journey will change your life",
        "Optimism attracts luck",
        "Freedom becomes the key",
        "Philosophy reveals truth",
    ],
    "Capricorn": [
        "Career will soar",
        "Ambitions will be realized",
        "Discipline will pay off",
        "Status will strengthen",
    ],
    "Aquarius": [
        "Originality will win",
        "Future is in your hands",
        "Friendship becomes support",
        "Innovation brings success",
    ],
    "Pisces": [
        "Dreams begin to come true",
        "Creativity heals the soul",
        "Intuition shows the path",
        "Compassion will return",
    ],
}


def get_zodiac_sign(month: int, day: int) -> Tuple[str, str, str]:
    """Get zodiac sign for given date.

    Returns:
        Tuple of (english_name, russian_name, symbol)
    """
    for name_en, name_ru, start, end, symbol in ZODIAC_SIGNS:
        start_month, start_day = start
        end_month, end_day = end

        # Handle Capricorn which spans year boundary
        if start_month > end_month:
            if (month == start_month and day >= start_day) or \
               (month == end_month and day <= end_day) or \
               (month == 12 and month > start_month) or \
               (month == 1 and month < end_month):
                return (name_en, name_ru, symbol)
        else:
            if (month == start_month and day >= start_day) or \
               (month == end_month and day <= end_day) or \
               (start_month < month < end_month):
                return (name_en, name_ru, symbol)

    return ("Aries", "Овен", "♈")  # Default fallback


class ZodiacMode(BaseMode):
    """Zodiac mode - enter birthday, get horoscope.

    Flow:
    1. Intro: Constellation animation
    2. Active: Enter birthday (DD.MM format)
    3. Processing: Zodiac calculation animation
    4. Result: Display zodiac sign and horoscope
    """

    name = "zodiac"
    display_name = "ГОРОСКОП"
    description = "Узнай свой гороскоп"
    icon = "*"
    style = "mystical"
    requires_camera = False
    requires_ai = False
    estimated_duration = 20

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Date input state
        self._input_buffer: str = ""
        self._input_position: int = 0  # 0-3 for DD.MM
        self._input_valid: bool = False

        # Result state
        self._zodiac_en: str = ""
        self._zodiac_ru: str = ""
        self._zodiac_symbol: str = ""
        self._horoscope: str = ""
        self._reveal_progress: float = 0.0

        # Animation state
        self._constellation_angle: float = 0.0
        self._star_twinkle: List[float] = []
        self._glow_phase: float = 0.0
        self._orbit_angle: float = 0.0
        self._symbol_pulse: float = 0.0
        self._input_glow: float = 0.0  # Glow effect for valid input

        # Particles
        self._particles = ParticleSystem()

        # Colors - richer mystical palette
        self._primary = (138, 43, 226)    # Purple (BlueViolet)
        self._secondary = (100, 149, 237)  # Cornflower blue
        self._accent = (255, 215, 0)       # Gold
        self._star_color = (255, 250, 205) # Lemon chiffon (stars)

    def on_enter(self) -> None:
        """Initialize zodiac mode."""
        self._input_buffer = ""
        self._input_position = 0
        self._input_valid = False
        self._zodiac_en = ""
        self._zodiac_ru = ""
        self._zodiac_symbol = ""
        self._horoscope = ""
        self._reveal_progress = 0.0
        self._glow_phase = 0.0
        self._orbit_angle = 0.0
        self._symbol_pulse = 0.0
        self._input_glow = 0.0

        # Initialize star twinkle phases - more stars for richer effect
        self._star_twinkle = [random.random() * 6.28 for _ in range(30)]

        # Setup particles - multiple emitters for layered effect
        star_config = ParticlePresets.stars(x=64, y=64)
        star_config.color = self._star_color
        star_config.emission_rate = 3.0
        self._particles.add_emitter("stars", star_config)

        # Add magic sparkles
        magic_config = ParticlePresets.sparkle(x=64, y=64)
        magic_config.color = self._accent
        magic_config.emission_rate = 0.5
        self._particles.add_emitter("magic", magic_config)

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        """Update zodiac mode."""
        self._particles.update(delta_ms)

        # Animation updates
        self._constellation_angle += delta_ms * 0.008  # Slower rotation
        self._glow_phase += delta_ms * 0.005
        self._orbit_angle += delta_ms * 0.003
        self._symbol_pulse += delta_ms * 0.01

        # Input glow animation (fades out when invalid)
        if self._input_valid:
            self._input_glow = min(1.0, self._input_glow + delta_ms / 200)
        else:
            self._input_glow = max(0.0, self._input_glow - delta_ms / 300)

        if self.phase == ModePhase.INTRO:
            # Longer, more dramatic intro - 3 seconds
            if self._time_in_phase > 3000:
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.PROCESSING:
            # Slower reveal for more drama - 3 seconds
            self._reveal_progress = min(1.0, self._time_in_phase / 3000)

            # Burst more particles during reveal
            if int(self._time_in_phase / 500) > int((self._time_in_phase - delta_ms) / 500):
                magic = self._particles.get_emitter("magic")
                if magic:
                    magic.burst(10)

            if self._reveal_progress >= 1.0:
                self.change_phase(ModePhase.RESULT)
                # Final burst
                stars = self._particles.get_emitter("stars")
                if stars:
                    stars.burst(50)

        elif self.phase == ModePhase.RESULT:
            # Auto-complete after 20 seconds (longer to admire)
            if self._time_in_phase > 20000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input.

        Accepts:
        - BUTTON_PRESS (center button): Confirm date / finish result
        - ARCADE_LEFT: Navigate left in date (if implemented) or clear
        - ARCADE_RIGHT: Navigate right in date (if implemented)
        - KEYPAD_INPUT: Direct digit entry
        """
        if event.type == EventType.BUTTON_PRESS:
            # Center button - confirm action
            if self.phase == ModePhase.ACTIVE:
                # Confirm date entry with center button
                if self._validate_date():
                    self._process_date()
                    return True
            elif self.phase == ModePhase.RESULT:
                self._finish()
                return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.ACTIVE:
                # Backspace - delete last digit
                if self._input_buffer:
                    self._input_buffer = self._input_buffer[:-1]
                    self._input_position = len(self._input_buffer)
                    self._input_valid = False
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.ACTIVE:
                # Right arrow - confirm when valid
                if self._validate_date():
                    self._process_date()
                return True

        elif event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")

            if self.phase == ModePhase.ACTIVE:
                return self._handle_date_input(key)

        return False

    def _handle_date_input(self, key: str) -> bool:
        """Handle date input from keypad.

        Format: DD.MM (day and month)
        """
        if key == "*":
            # Backspace
            if self._input_buffer:
                self._input_buffer = self._input_buffer[:-1]
                self._input_position = len(self._input_buffer)
            return True

        elif key == "#":
            # Confirm input
            if self._validate_date():
                self._process_date()
            return True

        elif key.isdigit() and len(self._input_buffer) < 4:
            # Add digit
            self._input_buffer += key
            self._input_position = len(self._input_buffer)

            # Auto-validate when complete
            if len(self._input_buffer) == 4:
                if self._validate_date():
                    self._input_valid = True

            return True

        return False

    def _validate_date(self) -> bool:
        """Validate the entered date."""
        if len(self._input_buffer) != 4:
            return False

        try:
            day = int(self._input_buffer[:2])
            month = int(self._input_buffer[2:])

            if 1 <= month <= 12 and 1 <= day <= 31:
                # Basic validation (not checking month-specific days)
                return True
        except ValueError:
            pass

        return False

    def _process_date(self) -> None:
        """Process the entered date and generate horoscope."""
        day = int(self._input_buffer[:2])
        month = int(self._input_buffer[2:])

        # Get zodiac sign
        self._zodiac_en, self._zodiac_ru, self._zodiac_symbol = get_zodiac_sign(month, day)

        # Get random horoscope
        horoscopes = HOROSCOPES_RU.get(self._zodiac_en, ["Звёзды благосклонны"])
        self._horoscope = random.choice(horoscopes)

        # Burst particles
        stars = self._particles.get_emitter("stars")
        if stars:
            stars.burst(40)

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
            display_text=f"{self._zodiac_ru}: {self._horoscope}",
            ticker_text=f"{self._zodiac_symbol} {self._horoscope}",
            lcd_text=self._zodiac_ru[:16].center(16),
            should_print=True,
            print_data={
                "zodiac_en": self._zodiac_en,
                "zodiac_ru": self._zodiac_ru,
                "zodiac_symbol": self._zodiac_symbol,
                "horoscope": self._horoscope,
                "birthday": f"{self._input_buffer[:2]}.{self._input_buffer[2:]}",
                "type": "zodiac_horoscope"
            }
        )
        self.complete(result)

    def _draw_constellation(self, buffer, cx: int, cy: int, radius: int) -> None:
        """Draw a rotating constellation pattern with orbiting elements."""
        from artifact.graphics.primitives import draw_circle, draw_line

        # Star positions in constellation (normalized -1 to 1)
        constellation = [
            (0.0, -0.8), (0.3, -0.4), (0.7, -0.2),
            (0.4, 0.2), (0.6, 0.6), (0.2, 0.4),
            (-0.2, 0.5), (-0.5, 0.3), (-0.7, 0.0),
            (-0.4, -0.3), (-0.1, -0.1)
        ]

        # Connections between stars
        connections = [
            (0, 1), (1, 2), (1, 3), (3, 4), (3, 5),
            (5, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 0)
        ]

        angle = self._constellation_angle
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Transform star positions
        transformed = []
        for x, y in constellation:
            rx = x * cos_a - y * sin_a
            ry = x * sin_a + y * cos_a
            sx = int(cx + rx * radius)
            sy = int(cy + ry * radius)
            transformed.append((sx, sy))

        # Draw glowing connections with gradient
        for i, j in connections:
            x1, y1 = transformed[i]
            x2, y2 = transformed[j]
            # Outer glow
            glow_intensity = int(30 + 20 * math.sin(self._glow_phase + i * 0.5))
            draw_line(buffer, x1, y1, x2, y2, (glow_intensity, glow_intensity, glow_intensity + 40))
            # Inner line
            draw_line(buffer, x1, y1, x2, y2, (80, 80, 140))

        # Draw stars with enhanced twinkle
        for i, (sx, sy) in enumerate(transformed):
            twinkle = 0.5 + 0.5 * math.sin(self._time_in_mode / 200 + self._star_twinkle[i % len(self._star_twinkle)])
            brightness = int(150 + 105 * twinkle)

            # Outer glow for each star
            glow_size = 3 + int(twinkle * 2)
            for r in range(glow_size, 1, -1):
                glow_alpha = (glow_size - r) / glow_size * 0.4
                glow_color = (int(brightness * glow_alpha), int(brightness * glow_alpha), int(brightness * 0.9 * glow_alpha))
                draw_circle(buffer, sx, sy, r, glow_color, filled=False)

            # Core star
            color = (brightness, brightness, int(brightness * 0.9))
            draw_circle(buffer, sx, sy, 2, color)

        # Draw orbiting planets/moons
        for i in range(3):
            orbit_radius = radius + 8 + i * 6
            orbit_angle = self._orbit_angle + i * 2.1
            ox = int(cx + orbit_radius * math.cos(orbit_angle))
            oy = int(cy + orbit_radius * math.sin(orbit_angle))

            # Small orbiting dot with trail
            planet_brightness = int(100 + 50 * math.sin(self._glow_phase + i))
            draw_circle(buffer, ox, oy, 1, (planet_brightness, planet_brightness, int(planet_brightness * 0.7)))

    def render_main(self, buffer) -> None:
        """Render main display with enhanced animations."""
        from artifact.graphics.primitives import fill, draw_circle, draw_rect
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.text_utils import draw_centered_text, draw_wrapped_text, draw_animated_text, TextEffect

        # Background - deep space with gradient
        fill(buffer, (5, 5, 20))

        # Add some background stars
        for i in range(10):
            star_x = (i * 17 + int(self._time_in_mode / 100)) % 128
            star_y = (i * 23) % 128
            twinkle = 0.5 + 0.5 * math.sin(self._time_in_mode / 300 + i)
            brightness = int(40 + 30 * twinkle)
            draw_circle(buffer, star_x, star_y, 1, (brightness, brightness, brightness + 10))

        # Draw constellation - adjust position based on phase
        if self.phase == ModePhase.ACTIVE:
            self._draw_constellation(buffer, 64, 45, 30)
        else:
            self._draw_constellation(buffer, 64, 50, 38)

        # Render particles
        self._particles.render(buffer)

        font = load_font("cyrillic")

        if self.phase == ModePhase.INTRO:
            # Animated title with glow effect
            pulse = 0.8 + 0.2 * math.sin(self._time_in_phase / 200)
            title_color = tuple(int(c * pulse) for c in self._accent)

            draw_animated_text(buffer, "ЗОДИАК", 8, title_color, self._time_in_phase, TextEffect.GLOW, scale=2)
            draw_animated_text(buffer, "ОРАКУЛ", 28, self._secondary, self._time_in_phase, TextEffect.WAVE, scale=2)

            # Subtitle fading in
            if self._time_in_phase > 1500:
                fade = min(1.0, (self._time_in_phase - 1500) / 500)
                sub_color = tuple(int(150 * fade) for _ in range(3))
                draw_centered_text(buffer, "Введи дату рождения", 100, sub_color, scale=1)

        elif self.phase == ModePhase.ACTIVE:
            # Date input prompt - with animation
            draw_animated_text(buffer, "ДАТА РОЖДЕНИЯ", 4, self._accent, self._time_in_phase, TextEffect.GLOW, scale=1)

            # Format: DD.MM
            display_date = ""
            for i in range(4):
                if len(self._input_buffer) > i:
                    display_date += self._input_buffer[i]
                else:
                    display_date += "_"
                if i == 1:
                    display_date += "."

            # Draw date input box - centered with glow effect when valid
            box_w, box_h = 70, 24
            box_x = (128 - box_w) // 2
            box_y = 88

            # Glow effect when input is valid
            if self._input_glow > 0:
                glow_color = tuple(int(c * self._input_glow * 0.3) for c in (0, 255, 100))
                for offset in range(3, 0, -1):
                    draw_rect(buffer, box_x - offset, box_y - offset,
                             box_w + offset * 2, box_h + offset * 2,
                             glow_color, filled=False)

            # Box border
            border_color = (0, 255, 100) if self._input_valid else (60, 60, 100)
            draw_rect(buffer, box_x, box_y, box_w, box_h, border_color, filled=False)

            # Draw date text - centered within box
            text_x = box_x + (box_w - 60) // 2
            draw_text_bitmap(buffer, display_date, text_x, box_y + 5, (255, 255, 255), font, scale=2)

            # Cursor blink
            if int(self._time_in_phase / 400) % 2 == 0 and not self._input_valid:
                cursor_pos = len(self._input_buffer)
                cursor_x = text_x + cursor_pos * 12
                if cursor_pos >= 2:
                    cursor_x += 6  # Account for dot
                draw_rect(buffer, cursor_x, box_y + 5, 2, 14, self._accent)

            # Instructions - clear and helpful
            if self._input_valid:
                # Pulsing confirmation prompt
                pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 150)
                confirm_color = tuple(int(c * pulse) for c in (0, 255, 100))
                draw_centered_text(buffer, "ЖМИSPACE/→ОК", 118, confirm_color, scale=1)
            else:
                draw_centered_text(buffer, "← УД   →/SPACE ОК", 118, (120, 120, 140), scale=1)

        elif self.phase == ModePhase.PROCESSING:
            # Dramatic zodiac symbol reveal
            progress = self._reveal_progress

            # Rotating glow rings during reveal
            for ring in range(3):
                ring_radius = 20 + ring * 15 + int(progress * 10)
                ring_alpha = int(60 * (1 - progress) * (1 - ring / 3))
                ring_angle = self._constellation_angle * (2 - ring * 0.3)
                for angle_deg in range(0, 360, 30):
                    angle = math.radians(angle_deg) + ring_angle
                    rx = int(64 + ring_radius * math.cos(angle))
                    ry = int(55 + ring_radius * math.sin(angle))
                    draw_circle(buffer, rx, ry, 2, (ring_alpha, ring_alpha, ring_alpha + 30))

            # Draw symbol with growing size and glow
            symbol_scale = int(2 + progress * 3)
            symbol_alpha = int(255 * min(1.0, progress * 1.5))

            # Symbol glow
            glow_intensity = int(50 * progress)
            for glow_offset in range(5, 0, -1):
                glow_color = (glow_intensity // glow_offset, glow_intensity // glow_offset, glow_intensity // glow_offset)
                # Note: glow effect approximation

            draw_centered_text(
                buffer, self._zodiac_symbol, 35,
                (symbol_alpha, int(symbol_alpha * 0.9), int(symbol_alpha * 0.7)),
                scale=symbol_scale
            )

            # Sign name fading in with effect
            if progress > 0.5:
                name_progress = (progress - 0.5) * 2
                name_alpha = int(255 * name_progress)
                draw_animated_text(
                    buffer, self._zodiac_ru, 90,
                    (name_alpha, name_alpha, name_alpha),
                    self._time_in_phase, TextEffect.TYPING, scale=2
                )

        elif self.phase == ModePhase.RESULT:
            # Display zodiac sign and horoscope with pulsing effects

            # Symbol with glow - pulsing
            pulse = 0.85 + 0.15 * math.sin(self._symbol_pulse)
            symbol_color = tuple(int(c * pulse) for c in self._accent)
            draw_centered_text(buffer, self._zodiac_symbol, 3, symbol_color, scale=3)

            # Sign name with wave effect
            draw_animated_text(buffer, self._zodiac_ru, 28, self._secondary, self._time_in_phase, TextEffect.WAVE, scale=2)

            # Horoscope text - smart wrapped and centered
            draw_wrapped_text(
                buffer, self._horoscope, 52, (255, 255, 255),
                scale=1, max_lines=4, line_spacing=4
            )

            # Footer hint
            if int(self._time_in_phase / 500) % 2 == 0:
                draw_centered_text(buffer, "НАЖМИ ДЛЯ ВЫХОДА", 118, (80, 80, 100), scale=1)

    def render_ticker(self, buffer) -> None:
        """Render ticker with smooth seamless scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)

        if self.phase in (ModePhase.INTRO, ModePhase.ACTIVE):
            # Scrolling mystical text with rainbow effect
            render_ticker_animated(
                buffer, "ЗОДИАК ОРАКУЛ - ВВЕДИ ДАТУ РОЖДЕНИЯ",
                self._time_in_phase, self._secondary,
                TickerEffect.RAINBOW_SCROLL, speed=0.025
            )

        elif self.phase == ModePhase.PROCESSING:
            # Processing animation
            render_ticker_animated(
                buffer, "ЧИТАЮ ЗВЁЗДЫ",
                self._time_in_phase, self._primary,
                TickerEffect.PULSE_SCROLL, speed=0.03
            )

        elif self.phase == ModePhase.RESULT:
            # Show zodiac and horoscope with wave effect
            text = f"{self._zodiac_symbol} {self._zodiac_ru}: {self._horoscope}"
            render_ticker_animated(
                buffer, text,
                self._time_in_phase, self._accent,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )

    def get_lcd_text(self) -> str:
        """Get LCD text with zodiac symbols."""
        if self.phase == ModePhase.ACTIVE:
            if self._input_buffer:
                # Format date input nicely
                dd = self._input_buffer[:2] if len(self._input_buffer) >= 2 else self._input_buffer + "_" * (2 - len(self._input_buffer))
                mm = self._input_buffer[2:4] if len(self._input_buffer) >= 4 else self._input_buffer[2:] + "_" * (4 - len(self._input_buffer))
                return f" ☆ {dd}.{mm} ☆ ".center(16)[:16]
            return " ☆ ДД.ММ ☆ ".center(16)
        elif self.phase == ModePhase.PROCESSING:
            # Animated star reading
            stars = "★☆★☆★☆"
            offset = int(self._time_in_phase / 200) % 3
            return f" {stars[offset:offset+3]} ЧИТАЮ {stars[offset:offset+3]} "[:16]
        elif self.phase == ModePhase.RESULT:
            # Show zodiac symbol + name
            return f" {self._zodiac_symbol} {self._zodiac_ru} {self._zodiac_symbol} ".center(16)[:16]
        return " ☆ ЗОДИАК ☆ ".center(16)[:16]

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

        # Particles
        self._particles = ParticleSystem()

        # Colors
        self._primary = (107, 33, 168)   # Purple
        self._secondary = (59, 130, 246)  # Blue
        self._accent = (245, 158, 11)     # Gold

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

        # Initialize star twinkle phases
        self._star_twinkle = [random.random() * 6.28 for _ in range(20)]

        # Setup particles
        star_config = ParticlePresets.stars(x=64, y=64)
        star_config.color = self._secondary
        self._particles.add_emitter("stars", star_config)

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        """Update zodiac mode."""
        self._particles.update(delta_ms)

        # Rotate constellation
        self._constellation_angle += delta_ms * 0.01

        if self.phase == ModePhase.INTRO:
            # Intro lasts 2 seconds
            if self._time_in_phase > 2000:
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.PROCESSING:
            # Calculation animation
            self._reveal_progress = min(1.0, self._time_in_phase / 2000)

            if self._reveal_progress >= 1.0:
                self.change_phase(ModePhase.RESULT)

        elif self.phase == ModePhase.RESULT:
            # Auto-complete after 15 seconds
            if self._time_in_phase > 15000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT:
                self._finish()
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
        """Draw a rotating constellation pattern."""
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

        # Draw connections
        for i, j in connections:
            x1, y1 = transformed[i]
            x2, y2 = transformed[j]
            draw_line(buffer, x1, y1, x2, y2, (60, 60, 120))

        # Draw stars with twinkle
        for i, (sx, sy) in enumerate(transformed):
            twinkle = 0.5 + 0.5 * math.sin(self._time_in_mode / 200 + self._star_twinkle[i % len(self._star_twinkle)])
            brightness = int(150 + 105 * twinkle)
            color = (brightness, brightness, int(brightness * 0.9))
            draw_circle(buffer, sx, sy, 2, color)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_circle, draw_rect
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        # Background - deep space
        fill(buffer, (10, 10, 30))

        # Draw constellation
        self._draw_constellation(buffer, 64, 60, 40)

        # Render particles
        self._particles.render(buffer)

        font = load_font("cyrillic")

        if self.phase == ModePhase.INTRO:
            # Title - Russian
            draw_text_bitmap(buffer, "ЗОДИАК", 40, 10, self._accent, font, scale=2)
            draw_text_bitmap(buffer, "ОРАКУЛ", 40, 28, self._accent, font, scale=2)

        elif self.phase == ModePhase.ACTIVE:
            # Date input prompt - Russian
            draw_text_bitmap(buffer, "ВВЕДИ ДАТУ", 30, 8, self._accent, font, scale=1)

            # Format: DD.MM
            display_date = ""
            if len(self._input_buffer) >= 1:
                display_date += self._input_buffer[0]
            else:
                display_date += "_"

            if len(self._input_buffer) >= 2:
                display_date += self._input_buffer[1]
            else:
                display_date += "_"

            display_date += "."

            if len(self._input_buffer) >= 3:
                display_date += self._input_buffer[2]
            else:
                display_date += "_"

            if len(self._input_buffer) >= 4:
                display_date += self._input_buffer[3]
            else:
                display_date += "_"

            # Draw date input box
            box_x, box_y = 34, 100
            box_w, box_h = 60, 20
            draw_rect(buffer, box_x, box_y, box_w, box_h, (40, 40, 80), filled=False)

            # Draw date text
            draw_text_bitmap(buffer, display_date, box_x + 8, box_y + 6, (255, 255, 255), font, scale=2)

            # Cursor blink
            if int(self._time_in_phase / 400) % 2 == 0:
                cursor_x = box_x + 8 + len(self._input_buffer.replace(".", "")) * 12
                if len(self._input_buffer) >= 2:
                    cursor_x += 6  # Account for dot
                draw_rect(buffer, cursor_x, box_y + 6, 2, 12, self._accent)

            # Instructions - Russian
            if self._input_valid:
                draw_text_bitmap(buffer, "НАЖМИ # ОК", 35, 122, (0, 255, 0), font, scale=1)
            else:
                draw_text_bitmap(buffer, "* УД  # ОК", 35, 122, (150, 150, 150), font, scale=1)

        elif self.phase == ModePhase.PROCESSING:
            # Zodiac symbol reveal
            progress = self._reveal_progress

            # Draw symbol with growing size
            symbol_scale = int(3 + progress * 2)
            symbol_alpha = int(255 * progress)
            draw_text_bitmap(
                buffer, self._zodiac_symbol,
                64 - symbol_scale * 3, 40,
                (symbol_alpha, symbol_alpha, int(symbol_alpha * 0.8)),
                font, scale=symbol_scale
            )

            # Sign name fading in
            if progress > 0.5:
                name_alpha = int(255 * (progress - 0.5) * 2)
                draw_text_bitmap(
                    buffer, self._zodiac_ru,
                    64 - len(self._zodiac_ru) * 4, 90,
                    (name_alpha, name_alpha, name_alpha),
                    font, scale=2
                )

        elif self.phase == ModePhase.RESULT:
            # Display zodiac sign and horoscope

            # Symbol
            draw_text_bitmap(buffer, self._zodiac_symbol, 54, 5, self._accent, font, scale=3)

            # Sign name
            name_x = 64 - len(self._zodiac_ru) * 4
            draw_text_bitmap(buffer, self._zodiac_ru, name_x, 35, self._secondary, font, scale=2)

            # Horoscope text (word wrap)
            words = self._horoscope.split()
            lines = []
            current_line = ""

            for word in words:
                test_line = current_line + " " + word if current_line else word
                if len(test_line) <= 14:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)

            y = 60
            for line in lines[:4]:
                line_w, _ = font.measure_text(line)
                x = (128 - line_w * 2) // 2
                draw_text_bitmap(buffer, line, x, y, (255, 255, 255), font, scale=2)
                y += 16

    def render_ticker(self, buffer) -> None:
        """Render ticker."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        clear(buffer)
        font = load_font("cyrillic")

        if self.phase in (ModePhase.INTRO, ModePhase.ACTIVE):
            # Scrolling mystical text - Russian
            text = "ЗОДИАК ОРАКУЛ... ВВЕДИ ДАТУ... "
            scroll = int(self._time_in_phase / 80) % (len(text) * 4 + 48)
            draw_text_bitmap(buffer, text, 48 - scroll, 1, self._secondary, font, scale=1)

        elif self.phase == ModePhase.RESULT:
            # Show zodiac and horoscope
            text = f"{self._zodiac_symbol} {self._zodiac_ru}: {self._horoscope} "
            scroll = int(self._time_in_phase / 100) % (len(text) * 4 + 48)
            draw_text_bitmap(buffer, text, 48 - scroll, 1, self._accent, font, scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self.phase == ModePhase.ACTIVE:
            if self._input_buffer:
                display = self._input_buffer[:2]
                if len(self._input_buffer) > 2:
                    display += "." + self._input_buffer[2:]
                return f"DATE: {display}".center(16)[:16]
            return "ENTER BIRTHDAY".center(16)
        elif self.phase == ModePhase.PROCESSING:
            return "READING STARS...".center(16)
        elif self.phase == ModePhase.RESULT:
            return self._zodiac_ru.center(16)[:16]
        return "ZODIAC ORACLE".center(16)[:16]

"""Fortune Teller mode - AI-powered predictions based on birthdate + photo.

This is the mystical fortune-telling mode of VNVNC:
1. User enters their full birthdate (DD.MM.YYYY)
2. Camera captures user photo
3. AI analyzes photo + birthdate for personalized astro-prediction
4. AI generates a caricature of the user
5. Combined receipt prints with caricature + prediction + date

Uses Gemini 2.5 Flash for predictions and Imagen 3 for caricatures.
"""

import asyncio
import logging
from typing import Optional, List, Tuple
from datetime import datetime, date
import random
import math
import numpy as np

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.simulator.mock_hardware.camera import (
    SimulatorCamera, create_camera, floyd_steinberg_dither, create_viewfinder_overlay
)

logger = logging.getLogger(__name__)


class FortunePhase:
    """Sub-phases within the Fortune mode."""

    INTRO = "intro"                  # Welcome animation
    BIRTHDATE_INPUT = "birthdate"    # Enter DD.MM.YYYY
    CAMERA_PREP = "camera_prep"      # "Look at camera" prompt
    CAMERA_CAPTURE = "capture"       # Capturing photo
    PROCESSING = "processing"        # AI generation
    REVEAL = "reveal"                # Dramatic reveal
    RESULT = "result"                # Final display


# =============================================================================
# ZODIAC SIGNS & ASTRO DATA
# =============================================================================

ZODIAC_SIGNS = [
    ("Козерог", "♑", (12, 22), (1, 19), "earth"),
    ("Водолей", "♒", (1, 20), (2, 18), "air"),
    ("Рыбы", "♓", (2, 19), (3, 20), "water"),
    ("Овен", "♈", (3, 21), (4, 19), "fire"),
    ("Телец", "♉", (4, 20), (5, 20), "earth"),
    ("Близнецы", "♊", (5, 21), (6, 20), "air"),
    ("Рак", "♋", (6, 21), (7, 22), "water"),
    ("Лев", "♌", (7, 23), (8, 22), "fire"),
    ("Дева", "♍", (8, 23), (9, 22), "earth"),
    ("Весы", "♎", (9, 23), (10, 22), "air"),
    ("Скорпион", "♏", (10, 23), (11, 21), "water"),
    ("Стрелец", "♐", (11, 22), (12, 21), "fire"),
]

CHINESE_ZODIAC = [
    ("Крыса", "🐀", "хитрость и обаяние"),
    ("Бык", "🐂", "упорство и надежность"),
    ("Тигр", "🐅", "смелость и страсть"),
    ("Кролик", "🐇", "доброта и элегантность"),
    ("Дракон", "🐉", "сила и удача"),
    ("Змея", "🐍", "мудрость и загадочность"),
    ("Лошадь", "🐎", "свобода и энергия"),
    ("Коза", "🐐", "творчество и мягкость"),
    ("Обезьяна", "🐒", "изобретательность и веселье"),
    ("Петух", "🐓", "уверенность и точность"),
    ("Собака", "🐕", "верность и честность"),
    ("Свинья", "🐷", "щедрость и искренность"),
]


def get_zodiac_sign(day: int, month: int) -> Tuple[str, str, str]:
    """Get Western zodiac sign for a date.

    Returns:
        Tuple of (name, symbol, element)
    """
    for name, symbol, (start_m, start_d), (end_m, end_d), element in ZODIAC_SIGNS:
        if (month == start_m and day >= start_d) or (month == end_m and day <= end_d):
            return name, symbol, element
    return "Козерог", "♑", "earth"  # Default


def get_chinese_zodiac(year: int) -> Tuple[str, str, str]:
    """Get Chinese zodiac animal for a year.

    Returns:
        Tuple of (name, emoji, trait)
    """
    index = (year - 1900) % 12
    return CHINESE_ZODIAC[index]


def calculate_life_path_number(day: int, month: int, year: int) -> int:
    """Calculate numerology life path number."""
    # Sum all digits until single digit
    total = sum(int(d) for d in f"{day:02d}{month:02d}{year}")
    while total > 9:
        total = sum(int(d) for d in str(total))
    return total


def calculate_age(day: int, month: int, year: int) -> int:
    """Calculate current age from birthdate."""
    today = date.today()
    age = today.year - year
    if (today.month, today.day) < (month, day):
        age -= 1
    return age


# =============================================================================
# AI PROMPTS FOR FORTUNE TELLING
# =============================================================================

# The key insight: AI is smart enough to figure out zodiac, Chinese zodiac,
# numerology, and everything else from just the birthdate. We delegate!

FORTUNE_TELLER_SYSTEM_PROMPT = """Ты - мистическая гадалка-астролог в аркадном автомате VNVNC на вечеринке.
Тебе дают ДАТУ РОЖДЕНИЯ и ФОТО человека. Твоя задача - создать прикольное персональное предсказание!

ЧТО ТЫ ДОЛЖЕН СДЕЛАТЬ (ты это умеешь!):
1. По дате рождения определи знак зодиака (Овен, Телец, Близнецы и т.д.)
2. По году рождения определи китайский гороскоп (Крыса, Бык, Тигр и т.д.)
3. Посчитай нумерологическое число судьбы (сумма всех цифр даты до однозначного)
4. Вычисли возраст человека (сегодня декабрь 2024)
5. По фото определи вайб человека - его энергию, стиль, характер

ЗАТЕМ создай ОДНО персональное предсказание, которое:
- Упоминает знак зодиака или китайский гороскоп
- Связано с внешностью или вайбом человека
- Смешное, дерзкое, но не обидное
- Использует молодёжный сленг (не перебарщивай)
- Отсылки к соцсетям, мемам, современной жизни - ДА!
- 2-3 предложения максимум!

Примеры хороших предсказаний:
- "Типичный Лев с лицом победителя! В 23 года твоя харизма уже должна захватывать мир"
- "Крыса + Водолей + этот уверенный взгляд = комбо для успеха. Ретроградный Меркурий? Не твоя проблема"
- "Число судьбы 7 плюс такие глаза - вижу, как люди сами к тебе тянутся. Пользуйся!"

ВСЕГДА пиши на русском.

Format your response as:
PREDICTION: [предсказание]
ZODIAC: [знак зодиака]
CHINESE: [китайский зодиак]
LUCKY_COLOR: [счастливый цвет]
"""

# Combined prompt that includes both photo analysis and prediction
COMBINED_FORTUNE_PROMPT = """Перед тобой фото человека. Его дата рождения: {birthdate}

1. Сначала кратко опиши человека на фото (вайб, выражение лица, стиль)
2. Затем создай персональное предсказание на основе даты рождения И внешности

Помни:
- Определи знак зодиака и китайский гороскоп по дате
- Свяжи внешность с предсказанием
- Будь смешным и дерзким, но не обидным
- Молодёжный сленг ОК
- 2-3 предложения для предсказания!

Format:
PHOTO_ANALYSIS: [краткое описание человека]
PREDICTION: [твоё прикольное предсказание]
ZODIAC: [знак зодиака]
CHINESE: [китайский зодиак]
LUCKY_COLOR: [счастливый цвет]
"""


class FortuneMode(BaseMode):
    """Fortune Teller mode - AI-powered birthdate + photo predictions.

    The mystical mode of VNVNC that combines:
    - Full birthdate input (DD.MM.YYYY)
    - Live camera capture
    - AI-powered prediction generation (AI interprets zodiac/numerology)
    - AI-generated caricature
    - Combined thermal receipt printing

    Flow:
    1. INTRO: Mystical welcome animation
    2. BIRTHDATE_INPUT: Enter full birthdate with keypad
    3. CAMERA_PREP: "Look at the camera" prompt
    4. CAMERA_CAPTURE: Take photo with countdown
    5. PROCESSING: AI generates prediction + caricature
    6. REVEAL: Dramatic reveal animation
    7. RESULT: Display prediction, offer print
    """

    name = "fortune"
    display_name = "ГАДАЛКА"
    description = "Астро-предсказание по дате"
    icon = "*"
    style = "mystical"
    requires_camera = True
    requires_ai = True
    estimated_duration = 60

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._gemini_client = get_gemini_client()
        self._caricature_service = CaricatureService()

        # Sub-phase tracking
        self._sub_phase = FortunePhase.INTRO

        # Birthdate input state
        self._input_digits: List[str] = []  # User-entered digits
        self._cursor_pos: int = 0           # Current input position (0-7)
        self._input_complete: bool = False
        self._birthdate: Optional[Tuple[int, int, int]] = None  # (day, month, year)

        # AI results
        self._zodiac_sign: str = ""
        self._chinese_zodiac: str = ""
        self._photo_analysis: str = ""
        self._prediction: str = ""
        self._lucky_color: str = ""
        self._caricature: Optional[Caricature] = None
        self._ai_task: Optional[asyncio.Task] = None
        self._processing_progress: float = 0.0

        # Camera state
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0

        # Animation state
        self._reveal_progress: float = 0.0
        self._glow_phase: float = 0.0
        self._ball_glow: float = 0.0

        # Particles
        self._particles = ParticleSystem()

        # Colors (mystical style)
        self._primary = (107, 33, 168)    # Purple
        self._secondary = (245, 158, 11)   # Gold
        self._accent = (20, 184, 166)      # Teal

    @property
    def is_ai_available(self) -> bool:
        """Check if AI services are available."""
        return self._gemini_client.is_available

    def on_enter(self) -> None:
        """Initialize Fortune mode."""
        self._sub_phase = FortunePhase.INTRO
        self._input_digits = []
        self._cursor_pos = 0
        self._input_complete = False
        self._birthdate = None
        self._photo_data = None
        self._camera_frame = None
        self._photo_analysis = ""
        self._prediction = ""
        self._lucky_color = ""
        self._zodiac_sign = ""
        self._chinese_zodiac = ""
        self._caricature = None
        self._ai_task = None
        self._processing_progress = 0.0
        self._reveal_progress = 0.0

        # Initialize camera for live preview
        self._camera = create_camera(resolution=(640, 480))
        if self._camera.open():
            logger.info("Camera opened for Fortune mode")
        else:
            logger.warning("Could not open camera, using placeholder")

        # Setup particles (mystical style)
        star_config = ParticlePresets.stars(x=64, y=64)
        star_config.color = self._secondary
        self._particles.add_emitter("stars", star_config)

        magic_config = ParticlePresets.magic(x=64, y=70)
        magic_config.color = self._primary
        self._particles.add_emitter("magic", magic_config)

        self.change_phase(ModePhase.INTRO)
        logger.info("Fortune mode entered")

    def on_update(self, delta_ms: float) -> None:
        """Update Fortune mode."""
        self._particles.update(delta_ms)

        # Animation updates
        self._glow_phase += delta_ms * 0.003
        self._ball_glow = 0.5 + 0.5 * math.sin(self._time_in_mode / 500)

        # Update live camera preview during camera phases
        if self._sub_phase in (FortunePhase.CAMERA_PREP, FortunePhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            if self._sub_phase == FortunePhase.INTRO:
                # Intro lasts 2.5 seconds
                if self._time_in_phase > 2500:
                    self._sub_phase = FortunePhase.BIRTHDATE_INPUT
                    self.change_phase(ModePhase.ACTIVE)
                    self._time_in_phase = 0

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                # Waiting for user to enter birthdate
                pass

            elif self._sub_phase == FortunePhase.CAMERA_PREP:
                # Camera prep for 2 seconds
                if self._time_in_phase > 2000:
                    self._start_camera_capture()

            elif self._sub_phase == FortunePhase.CAMERA_CAPTURE:
                # Countdown animation
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                # Capture when countdown reaches 0
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._flash_alpha = 1.0

                # Flash effect after capture
                if self._time_in_phase > 3000:
                    self._flash_alpha = max(0, 1.0 - (self._time_in_phase - 3000) / 500)

                    if self._time_in_phase > 3500:
                        self._start_processing()

        elif self.phase == ModePhase.PROCESSING:
            # Check AI task progress
            if self._ai_task:
                if self._ai_task.done():
                    self._on_ai_complete()
                else:
                    # Fake progress for visual feedback
                    self._processing_progress = min(0.9, self._processing_progress + delta_ms / 8000)

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == FortunePhase.REVEAL:
                self._reveal_progress = min(1.0, self._time_in_phase / 2000)

                if self._reveal_progress >= 1.0:
                    self._sub_phase = FortunePhase.RESULT

            elif self._sub_phase == FortunePhase.RESULT:
                # Auto-complete after 30 seconds
                if self._time_in_phase > 30000:
                    self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        # Keypad input for birthdate
        if event.type == EventType.KEYPAD_INPUT:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                key = event.data.get("key", "")
                if key.isdigit():
                    self._add_digit(key)
                    return True
                elif key == "*":
                    # Backspace
                    self._remove_digit()
                    return True
                elif key == "#":
                    # Confirm (if complete)
                    if self._input_complete:
                        self._confirm_birthdate()
                    return True

        elif event.type == EventType.BUTTON_PRESS:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                if self._input_complete:
                    self._confirm_birthdate()
                    return True
            elif self.phase == ModePhase.RESULT:
                self._finish()
                return True

        elif event.type == EventType.ARCADE_LEFT:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                self._remove_digit()
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT and self._input_complete:
                self._confirm_birthdate()
                return True

        return False

    def _add_digit(self, digit: str) -> None:
        """Add a digit to birthdate input."""
        if len(self._input_digits) >= 8:
            return

        self._input_digits.append(digit)
        self._cursor_pos = len(self._input_digits)

        # Check if complete (8 digits = DD.MM.YYYY)
        if len(self._input_digits) == 8:
            self._validate_birthdate()

    def _remove_digit(self) -> None:
        """Remove last digit from input."""
        if self._input_digits:
            self._input_digits.pop()
            self._cursor_pos = len(self._input_digits)
            self._input_complete = False

    def _validate_birthdate(self) -> None:
        """Validate the entered birthdate."""
        if len(self._input_digits) != 8:
            return

        try:
            digits = "".join(self._input_digits)
            day = int(digits[0:2])
            month = int(digits[2:4])
            year = int(digits[4:8])

            # Basic validation
            if not (1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2024):
                self._input_complete = False
                return

            # Try to create date to verify
            test_date = date(year, month, day)

            # Valid!
            self._birthdate = (day, month, year)
            self._input_complete = True

            logger.info(f"Birthdate valid: {day}.{month}.{year}")

        except (ValueError, IndexError):
            self._input_complete = False

    def _confirm_birthdate(self) -> None:
        """Confirm birthdate and proceed to camera."""
        if not self._input_complete or not self._birthdate:
            return

        self._sub_phase = FortunePhase.CAMERA_PREP
        self._time_in_phase = 0

        # Burst particles for transition
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(30)

        logger.info("Birthdate confirmed, moving to camera prep")

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = FortunePhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0
        logger.info("Camera capture started - countdown begins")

    def _do_camera_capture(self) -> None:
        """Actually capture the photo from camera."""
        if self._camera and self._camera.is_open:
            self._photo_data = self._camera.capture_jpeg(quality=90)
            if self._photo_data:
                logger.info(f"Captured photo: {len(self._photo_data)} bytes")
            else:
                logger.warning("Failed to capture photo")
        else:
            logger.warning("Camera not available for capture")
            self._photo_data = None

    def _update_camera_preview(self) -> None:
        """Update the live camera preview frame with dithering."""
        if not self._camera or not self._camera.is_open:
            return

        try:
            frame = self._camera.capture_frame()
            if frame is not None and frame.size > 0:
                dithered = floyd_steinberg_dither(frame, target_size=(128, 128), threshold=120)
                self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()
        except Exception as e:
            logger.warning(f"Camera preview update error: {e}")
            self._camera_frame = None

    def _start_processing(self) -> None:
        """Start AI processing (prediction + caricature in parallel)."""
        self._sub_phase = FortunePhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        # Start async AI task
        self._ai_task = asyncio.create_task(self._run_ai_generation())

        # Burst particles
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(50)

        logger.info("AI processing started")

    async def _run_ai_generation(self) -> None:
        """Run AI generation - send photo + birthdate together, let AI do all the work."""
        try:
            if not self._birthdate:
                raise ValueError("No birthdate")

            day, month, year = self._birthdate
            birthdate_str = f"{day:02d}.{month:02d}.{year}"

            # Generate prediction - send photo + birthdate together in ONE call
            async def generate_prediction():
                if not self._gemini_client.is_available:
                    return self._fallback_prediction()

                # Format the combined prompt with birthdate
                prompt = COMBINED_FORTUNE_PROMPT.format(birthdate=birthdate_str)

                # If we have photo, use vision model with photo + prompt
                if self._photo_data:
                    response = await self._gemini_client.generate_with_image(
                        prompt=prompt,
                        image_data=self._photo_data,
                        mime_type="image/jpeg",
                        model=GeminiModel.FLASH_VISION,
                        system_instruction=FORTUNE_TELLER_SYSTEM_PROMPT,
                    )
                else:
                    # No photo - text only
                    response = await self._gemini_client.generate_text(
                        prompt=f"Дата рождения: {birthdate_str}\n\nСоздай предсказание!",
                        model=GeminiModel.FLASH,
                        system_instruction=FORTUNE_TELLER_SYSTEM_PROMPT,
                        temperature=0.9,
                    )

                if response:
                    return self._parse_prediction_response(response)
                return self._fallback_prediction()

            # Generate caricature
            async def generate_caricature():
                if self._photo_data:
                    return await self._caricature_service.generate_caricature(
                        reference_photo=self._photo_data,
                        style=CaricatureStyle.MYSTICAL,
                        personality_context=f"Дата рождения: {birthdate_str}",
                    )
                return None

            # Run in parallel
            prediction_task = asyncio.create_task(generate_prediction())
            caricature_task = asyncio.create_task(generate_caricature())

            # Wait for prediction
            try:
                result = await asyncio.wait_for(prediction_task, timeout=60.0)
                self._prediction = result[0]
                self._lucky_color = result[1]
                # Also extract zodiac info from AI response if available
                if len(result) > 2:
                    self._zodiac_sign = result[2]
                if len(result) > 3:
                    self._chinese_zodiac = result[3]
            except asyncio.TimeoutError:
                logger.warning("Prediction generation timed out")
                fallback = self._fallback_prediction()
                self._prediction = fallback[0]
                self._lucky_color = fallback[1]

            # Wait for caricature
            try:
                self._caricature = await asyncio.wait_for(caricature_task, timeout=120.0)
            except asyncio.TimeoutError:
                logger.warning("Caricature generation timed out")
                self._caricature = None

            logger.info("AI generation complete")

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            fallback = self._fallback_prediction()
            self._prediction = fallback[0]
            self._lucky_color = fallback[1]

    def _parse_prediction_response(self, response: str) -> Tuple[str, str, str, str]:
        """Parse the AI response into components."""
        prediction_text = ""
        lucky_color = "золотой"
        zodiac = ""
        chinese = ""

        try:
            for line in response.strip().split("\n"):
                line = line.strip()
                if line.startswith("PREDICTION:"):
                    prediction_text = line[11:].strip()
                elif line.startswith("LUCKY_COLOR:"):
                    lucky_color = line[12:].strip()
                elif line.startswith("ZODIAC:"):
                    zodiac = line[7:].strip()
                elif line.startswith("CHINESE:"):
                    chinese = line[8:].strip()

            if not prediction_text:
                prediction_text = response.strip()[:100]  # Fallback
        except Exception as e:
            logger.warning(f"Error parsing prediction: {e}")
            prediction_text = response[:100]

        return prediction_text, lucky_color, zodiac, chinese

    def _fallback_prediction(self) -> Tuple[str, str, str, str]:
        """Generate fallback prediction when AI unavailable."""
        import time
        random.seed(time.time())

        fallback_texts = [
            "Твоя энергия сегодня на максимуме, используй это!",
            "Звёзды говорят, что удача уже в пути.",
            "Сегодня отличный день для новых начинаний.",
            "Прислушайся к своей интуиции, она не подведёт.",
            "Случайная встреча изменит всё к лучшему.",
        ]

        colors = ["золотой", "синий", "зелёный", "фиолетовый", "серебряный"]
        
        return random.choice(fallback_texts), random.choice(colors), "Тайна", "Дракон?"

    def _on_ai_complete(self) -> None:
        """Handle completion of AI processing."""
        self._processing_progress = 1.0
        self._sub_phase = FortunePhase.REVEAL
        self.change_phase(ModePhase.RESULT)
        self._reveal_progress = 0.0

        # Burst particles for reveal
        stars = self._particles.get_emitter("stars")
        if stars:
            stars.burst(100)

        logger.info("Starting reveal phase")

    def on_exit(self) -> None:
        """Cleanup."""
        # Cancel any pending AI task
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

        # Close camera
        if self._camera:
            self._camera.close()
            self._camera = None

        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        day, month, year = self._birthdate if self._birthdate else (1, 1, 2000)

        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=self._prediction,
            ticker_text=self._prediction,
            lcd_text=" ГАДАЛКА ".center(16),
            should_print=True,
            print_data={
                "prediction": self._prediction,
                "caricature": self._caricature.image_data if self._caricature else None,
                "zodiac_sign": self._zodiac_sign,
                "chinese_zodiac": self._chinese_zodiac,
                "birthdate": f"{day:02d}.{month:02d}.{year}",
                "lucky_color": self._lucky_color,
                "timestamp": datetime.now().isoformat(),
                "type": "fortune",
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_circle, draw_rect, draw_line
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        # Dark mystical background
        fill(buffer, (20, 15, 35))

        font = load_font("cyrillic")

        if self._sub_phase == FortunePhase.INTRO:
            self._render_intro(buffer, font)

        elif self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
            self._render_birthdate_input(buffer, font)

        elif self._sub_phase == FortunePhase.CAMERA_PREP:
            self._render_camera_prep(buffer, font)

        elif self._sub_phase == FortunePhase.CAMERA_CAPTURE:
            self._render_camera_capture(buffer, font)

        elif self._sub_phase == FortunePhase.PROCESSING:
            self._render_processing(buffer, font)

        elif self._sub_phase in (FortunePhase.REVEAL, FortunePhase.RESULT):
            self._render_result(buffer, font)

        # Render particles on top
        self._particles.render(buffer)

        # Flash effect
        if self._flash_alpha > 0:
            alpha = int(255 * self._flash_alpha)
            fill(buffer, (alpha, alpha, alpha))

    def _render_intro(self, buffer, font) -> None:
        """Render intro animation with crystal ball."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        cx, cy = 64, 45
        ball_radius = 30

        # Outer glow with pulsing effect
        glow_intensity = 0.3 + 0.3 * self._ball_glow
        for r in range(ball_radius + 20, ball_radius, -2):
            alpha = (r - ball_radius) / 20 * glow_intensity
            color = tuple(int(c * alpha) for c in self._primary)
            draw_circle(buffer, cx, cy, r, color, filled=False)

        # Ball gradient
        for r in range(ball_radius, 0, -1):
            factor = r / ball_radius
            color = tuple(int(c * factor + 30) for c in self._primary)
            draw_circle(buffer, cx, cy, r, color)

        # Highlight
        draw_circle(buffer, cx - 10, cy - 10, 8, (150, 120, 180))
        draw_circle(buffer, cx - 8, cy - 8, 4, (200, 180, 220))

        # Title
        draw_centered_text(buffer, "ГАДАЛКА", 85, self._secondary, scale=2)
        draw_centered_text(buffer, "Введи дату рождения", 105, (150, 150, 170), scale=1)

    def _render_birthdate_input(self, buffer, font) -> None:
        """Render birthdate input screen."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.fonts import draw_text_bitmap

        # Title
        draw_centered_text(buffer, "ДАТА РОЖДЕНИЯ", 5, self._secondary, scale=1)

        # Build display string: DD.MM.YYYY with cursor
        display = ""
        for i in range(8):
            if i < len(self._input_digits):
                display += self._input_digits[i]
            else:
                display += "_"
            # Add dots
            if i == 1 or i == 3:
                display += "."

        # Draw input field background
        field_y = 35
        draw_rect(buffer, 14, field_y - 5, 100, 30, (40, 35, 60))
        draw_rect(buffer, 14, field_y - 5, 100, 30, self._primary, filled=False)

        # Draw date text - large and centered
        draw_centered_text(buffer, display, field_y, (255, 255, 255), scale=2)

        # Blinking cursor effect
        if int(self._time_in_phase / 400) % 2 == 0 and len(self._input_digits) < 8:
            cursor_x = 24 + len(self._input_digits) * 10
            # Adjust for dots
            if len(self._input_digits) > 1:
                cursor_x += 8
            if len(self._input_digits) > 3:
                cursor_x += 8
            
            draw_rect(buffer, 14 + 8, field_y + 18, 10, 2, self._accent)

        # Keypad hint
        if len(self._input_digits) == 8:
            # Valid date?
            try:
                digits = "".join(self._input_digits)
                day = int(digits[0:2])
                month = int(digits[2:4])
                year = int(digits[4:8])
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2024:
                    draw_centered_text(buffer, "НАЖМИ #", 80, (100, 255, 100), scale=1)
                else:
                    draw_centered_text(buffer, "НЕВЕРНАЯ ДАТА", 80, (255, 100, 100), scale=1)
            except:
                pass
        else:
            draw_centered_text(buffer, "Используй цифры", 80, (100, 100, 120), scale=1)

    def _render_camera_prep(self, buffer, font) -> None:
        """Render camera preparation instructions."""
        from artifact.graphics.text_utils import draw_centered_text

        # Update preview background
        if self._camera_frame is not None:
            # Copy frame to buffer centered
            y_offset = (128 - self._camera_frame.shape[0]) // 2
            x_offset = (128 - self._camera_frame.shape[1]) // 2
            
            # Simple blit if sizes match 128x128 approx
            if self._camera_frame.shape == (128, 128, 3):
                import numpy as np
                np.copyto(buffer, self._camera_frame)
            else:
                # Basic fill if not
                pass

        # Overlay text
        draw_centered_text(buffer, "ПОСМОТРИ", 20, (255, 255, 255), scale=2)
        draw_centered_text(buffer, "В КАМЕРУ", 40, (255, 255, 255), scale=2)
        
        # Face frame
        from artifact.graphics.primitives import draw_rect
        draw_rect(buffer, 32, 32, 64, 64, self._accent, filled=False)
        
        draw_centered_text(buffer, "Сейчас сделаем фото...", 110, self._secondary, scale=1)

    def _render_camera_capture(self, buffer, font) -> None:
        """Render camera capture countdown."""
        from artifact.graphics.text_utils import draw_centered_text
        
        # Show camera feed
        if self._camera_frame is not None:
             if self._camera_frame.shape == (128, 128, 3):
                import numpy as np
                np.copyto(buffer, self._camera_frame)

        # Large countdown number
        count = math.ceil(self._camera_countdown)
        if count > 0:
            scale = 4 + int(math.sin(self._time_in_phase / 100) * 1)
            color = self._secondary
            draw_centered_text(buffer, str(count), 40, color, scale=scale)

    def _render_processing(self, buffer, font) -> None:
        """Render processing animation."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        # Crystal ball processing
        cx, cy = 64, 50
        radius = 25
        
        # Swirling colors in ball
        time = self._time_in_phase
        for i in range(5):
            angle = (time / 500) + (i * 2 * math.pi / 5)
            px = int(cx + math.cos(angle) * (radius - 5))
            py = int(cy + math.sin(angle) * (radius - 5))
            draw_circle(buffer, px, py, 4, self._primary)
            
        draw_circle(buffer, cx, cy, radius, self._secondary, filled=False)

        # Progress text
        dots = "." * (int(time / 500) % 4)
        draw_centered_text(buffer, f"ГАДАЮ{dots}", 85, (200, 200, 255), scale=1)
        
        # Random mystical symbols
        if int(time / 200) % 10 == 0:
            draw_centered_text(buffer, random.choice(["★", "☾", "☀", "⚡"]), 110, self._accent, scale=2)

    def _render_result(self, buffer, font) -> None:
        """Render the prediction result."""
        from artifact.graphics.text_utils import draw_centered_text, wrap_text
        from artifact.graphics.fonts import draw_text_bitmap

        # Result background
        if self._sub_phase == FortunePhase.REVEAL:
            # Fade in
            alpha = self._reveal_progress
            # (Logic handled by particles mostly)
        
        # Display Header
        draw_centered_text(buffer, "СУДЬБА", 5, self._secondary, scale=1)
        
        # Zodiac info
        if self._zodiac_sign:
            draw_centered_text(buffer, f"{self._zodiac_sign} • {self._chinese_zodiac}", 20, self._accent, scale=1)
            
        # Prediction text - scroll or wrap
        # Using a simple wrapped text display for now
        lines = wrap_text(self._prediction, width_chars=18)
        y = 40
        for line in lines[:5]:  # Show first 5 lines
            draw_centered_text(buffer, line, y, (255, 255, 255), scale=1)
            y += 12
            
        # Print prompt
        if int(self._time_in_phase / 500) % 2 == 0:
            draw_centered_text(buffer, "ПЕЧАТЬ...", 110, self._primary, scale=1)

    def _render_camera_prep(self, buffer, font) -> None:
        """Render camera preparation screen with live preview."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text

        # Show live camera preview if available
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

        # Overlay text
        draw_centered_text(buffer, "СМОТРИ В КАМЕРУ", 95, self._accent, scale=1)
        draw_centered_text(buffer, f"{self._zodiac_symbol} {self._zodiac_sign}", 110, self._secondary, scale=1)

    def _render_camera_capture(self, buffer, font) -> None:
        """Render camera capture with countdown."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        # Show live camera preview
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

        # Countdown number
        if self._camera_countdown > 0:
            countdown_num = str(int(self._camera_countdown) + 1)
            scale = 4 + int((self._camera_countdown % 1) * 2)
            draw_centered_text(buffer, countdown_num, 45, (255, 255, 255), scale=scale)

            # Progress ring
            progress = 1.0 - (self._camera_countdown % 1)
            for angle in range(0, int(360 * progress), 10):
                rad = math.radians(angle - 90)
                px = int(64 + 45 * math.cos(rad))
                py = int(64 + 45 * math.sin(rad))
                draw_circle(buffer, px, py, 2, self._secondary)

        # Flash effect
        if self._flash_alpha > 0:
            buffer[:, :] = np.clip(
                buffer.astype(np.int16) + int(255 * self._flash_alpha),
                0, 255
            ).astype(np.uint8)
            draw_centered_text(buffer, "ФОТО!", 60, (50, 50, 50), scale=2)

    def _render_processing(self, buffer, font) -> None:
        """Render AI processing animation."""
        from artifact.graphics.primitives import draw_rect, draw_line, draw_circle
        from artifact.graphics.text_utils import draw_animated_text, draw_centered_text, TextEffect

        # Animated mystical background
        cx, cy = 64, 50
        for i in range(5):
            angle = self._time_in_phase / 500 + i * 72
            r = 30 + 10 * math.sin(self._time_in_phase / 300 + i)
            x = int(cx + r * math.cos(math.radians(angle)))
            y = int(cy + r * math.sin(math.radians(angle)))
            size = int(3 + 2 * math.sin(self._time_in_phase / 200 + i))
            draw_circle(buffer, x, y, size, self._secondary)

        # Processing text
        draw_animated_text(
            buffer, "ГАДАЮ", 25,
            self._accent, self._time_in_phase,
            TextEffect.GLOW, scale=2
        )

        # Show zodiac info
        draw_centered_text(buffer, f"{self._zodiac_symbol} {self._zodiac_sign}", 55, (150, 150, 170), scale=1)
        draw_centered_text(buffer, f"{self._chinese_emoji} {self._chinese_zodiac}", 68, (150, 150, 170), scale=1)

        # Progress bar
        bar_w, bar_h = 100, 6
        bar_x = (128 - bar_w) // 2
        bar_y = 90

        draw_rect(buffer, bar_x, bar_y, bar_w, bar_h, (40, 40, 60))

        progress_w = int(bar_w * self._processing_progress)
        if progress_w > 0:
            for px in range(progress_w):
                pulse = 0.8 + 0.2 * math.sin(self._time_in_phase / 100 + px * 0.1)
                color = tuple(int(c * pulse) for c in self._accent)
                buffer[bar_y:bar_y + bar_h, bar_x + px] = color

        # Status
        dots = "." * (int(self._time_in_phase / 300) % 4)
        draw_centered_text(buffer, f"Читаю судьбу{dots}", 105, (120, 120, 150), scale=1)

    def _render_result(self, buffer, font) -> None:
        """Render prediction result with cycling views."""
        from artifact.graphics.primitives import draw_rect, fill
        from artifact.graphics.text_utils import (
            draw_centered_text, smart_wrap_text, TextEffect, MAIN_DISPLAY_WIDTH
        )
        from io import BytesIO

        # Cycle through views every 5 seconds: zodiac, prediction, caricature
        cycle_time = 5000
        has_caricature = self._caricature is not None
        num_views = 3 if has_caricature else 2
        view = int(self._time_in_phase / cycle_time) % num_views

        if self._sub_phase == FortunePhase.REVEAL:
            # During reveal, show prediction text with fade-in
            self._render_prediction_text(buffer, font)
        elif view == 0:
            # Zodiac info view
            self._render_zodiac_view(buffer, font)
        elif view == 1:
            # Prediction text view
            self._render_prediction_text(buffer, font)
        elif view == 2 and has_caricature:
            # Caricature view
            self._render_caricature(buffer, font)

    def _render_zodiac_view(self, buffer, font) -> None:
        """Render zodiac information view."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        # Large zodiac symbol
        draw_centered_text(buffer, self._zodiac_symbol, 10, self._secondary, scale=3)
        draw_centered_text(buffer, self._zodiac_sign, 42, (255, 255, 255), scale=2)

        # Chinese zodiac
        draw_centered_text(buffer, self._chinese_emoji, 62, self._secondary, scale=2)
        draw_centered_text(buffer, self._chinese_zodiac, 82, (200, 200, 220), scale=1)

        # Life path number
        draw_centered_text(buffer, f"Число судьбы: {self._life_path}", 98, self._accent, scale=1)

        # Hint
        if int(self._time_in_phase / 600) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ", 118, (100, 100, 120), scale=1)

    def _render_prediction_text(self, buffer, font) -> None:
        """Render the prediction text with auto-scaling."""
        from artifact.graphics.text_utils import (
            draw_centered_text, smart_wrap_text, MAIN_DISPLAY_WIDTH
        )

        if not self._prediction:
            return

        # Try scale=2 first, fall back to scale=1
        margin = 4
        available_width = MAIN_DISPLAY_WIDTH - margin * 2

        lines_s2 = smart_wrap_text(self._prediction, available_width, font, scale=2)

        if len(lines_s2) <= 6:
            scale = 2
            lines = lines_s2
            line_height = 18
            max_lines = 6
            start_y = 8
        else:
            scale = 1
            lines = smart_wrap_text(self._prediction, available_width, font, scale=1)
            line_height = 10
            max_lines = 11
            start_y = 5

        y = start_y
        for i, line in enumerate(lines[:max_lines]):
            if self._sub_phase == FortunePhase.REVEAL:
                # Fade-in animation
                line_alpha = min(1.0, self._reveal_progress * (max_lines / 2) - i * 0.5)
                if line_alpha <= 0:
                    continue
                color = tuple(int(255 * line_alpha) for _ in range(3))
            else:
                # Wave effect
                wave_y = y + int(1.5 * math.sin(self._time_in_phase / 200 + i * 0.4))
                pulse = 0.85 + 0.15 * math.sin(self._time_in_phase / 300 + i * 0.3)
                color = tuple(int(255 * pulse) for _ in range(3))
                y = wave_y

            draw_centered_text(buffer, line, y, color, scale=scale)
            y += line_height

        # Hint at bottom
        if self._sub_phase == FortunePhase.RESULT:
            if int(self._time_in_phase / 600) % 2 == 0:
                draw_centered_text(buffer, "НАЖМИ", 118, (100, 100, 120), scale=1)

    def _render_caricature(self, buffer, font) -> None:
        """Render the AI-generated caricature."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from io import BytesIO

        if not self._caricature:
            return

        try:
            from PIL import Image

            img = Image.open(BytesIO(self._caricature.image_data))
            img = img.convert("RGB")

            display_size = 100
            img = img.resize((display_size, display_size), Image.Resampling.NEAREST)

            x_offset = (128 - display_size) // 2
            y_offset = 5

            for y in range(display_size):
                for x in range(display_size):
                    bx = x_offset + x
                    by = y_offset + y
                    if 0 <= bx < 128 and 0 <= by < 128:
                        pixel = img.getpixel((x, y))
                        buffer[by, bx] = pixel

            # Border
            draw_rect(buffer, x_offset - 2, y_offset - 2, display_size + 4, display_size + 4, self._secondary, filled=False)

            # Label
            draw_centered_text(buffer, "ТВОЙ ПОРТРЕТ", 112, self._accent, scale=1)

        except Exception as e:
            logger.warning(f"Failed to render caricature: {e}")
            self._render_prediction_text(buffer, font)

    def render_ticker(self, buffer) -> None:
        """Render ticker with smooth seamless scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, render_ticker_static, TickerEffect, TextEffect

        clear(buffer)

        if self._sub_phase == FortunePhase.INTRO:
            render_ticker_animated(
                buffer, "ВВЕДИ ДАТУ РОЖДЕНИЯ",
                self._time_in_phase, self._secondary,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

        elif self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
            # Show current input
            display = "".join(self._input_digits) if self._input_digits else "ДД.ММ.ГГГГ"
            render_ticker_static(
                buffer, display,
                self._time_in_phase, self._accent,
                TextEffect.GLOW
            )

        elif self._sub_phase in (FortunePhase.CAMERA_PREP, FortunePhase.CAMERA_CAPTURE):
            render_ticker_animated(
                buffer, "СМОТРИ В КАМЕРУ",
                self._time_in_phase, self._accent,
                TickerEffect.PULSE_SCROLL, speed=0.028
            )

        elif self._sub_phase == FortunePhase.PROCESSING:
            render_ticker_animated(
                buffer, f"ГАДАЮ ДЛЯ {self._zodiac_sign}",
                self._time_in_phase, self._secondary,
                TickerEffect.WAVE_SCROLL, speed=0.025
            )

        elif self._sub_phase == FortunePhase.RESULT and self._prediction:
            render_ticker_animated(
                buffer, self._prediction,
                self._time_in_phase, self._accent,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )

        else:
            render_ticker_animated(
                buffer, "ГАДАЛКА",
                self._time_in_phase, self._primary,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

    def get_lcd_text(self) -> str:
        """Get LCD text with mystical symbols."""
        if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
            frame = int(self._time_in_phase / 400) % 2
            symbol = "◆" if frame == 0 else "◇"
            return f" {symbol} ДАТА {symbol} ".center(16)[:16]
        elif self._sub_phase == FortunePhase.CAMERA_PREP:
            eye = "◉" if int(self._time_in_phase / 300) % 2 == 0 else "◎"
            return f" {eye} КАМЕРА {eye} ".center(16)[:16]
        elif self._sub_phase == FortunePhase.CAMERA_CAPTURE:
            countdown = int(self._camera_countdown) + 1
            return f" ★ ФОТО: {countdown} ★ ".center(16)[:16]
        elif self._sub_phase == FortunePhase.PROCESSING:
            dots = "◐◓◑◒"
            dot = dots[int(self._time_in_phase / 200) % 4]
            return f" {dot} ГАДАЮ {dot} ".center(16)[:16]
        elif self._sub_phase == FortunePhase.RESULT:
            return f" {self._zodiac_symbol} СУДЬБА {self._zodiac_symbol} ".center(16)[:16]
        return " ◆ ГАДАЛКА ◆ ".center(16)

"""Zodiac mode - Birthday to horoscope predictions with photo + constellation portrait."""

import asyncio
import logging
from typing import List, Optional, Tuple
from datetime import date, datetime
import random
import math
import numpy as np

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.utils.camera import create_viewfinder_overlay
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult
from artifact.audio.engine import get_audio_engine

logger = logging.getLogger(__name__)


class ZodiacPhase:
    """Sub-phases within Zodiac mode."""
    INTRO = "intro"
    DATE_INPUT = "date_input"
    CAMERA_PREP = "camera_prep"
    CAMERA_CAPTURE = "capture"
    PROCESSING = "processing"
    GENERATING = "generating"
    RESULT = "result"


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
    """Zodiac mode - enter birthday, get horoscope with constellation portrait.

    Flow:
    1. Intro: Constellation animation
    2. Active: Enter birthday (DD.MM format)
    3. Camera: Take photo for constellation portrait
    4. Processing: AI generates zodiac-themed portrait
    5. Result: Display zodiac sign, horoscope, and portrait
    """

    name = "zodiac"
    display_name = "ГОРОСКОП"
    description = "Узнай свой гороскоп"
    icon = "*"
    style = "mystical"
    requires_camera = True
    requires_ai = True
    estimated_duration = 35

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Sub-phase tracking
        self._sub_phase = ZodiacPhase.INTRO

        # AI services
        self._gemini_client = get_gemini_client()
        self._caricature_service = CaricatureService()

        # Camera state
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0

        # AI results
        self._constellation_portrait: Optional[Caricature] = None
        self._ai_task: Optional[asyncio.Task] = None
        self._progress_tracker = SmartProgressTracker(mode_theme="zodiac")

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

        # Result view state
        self._result_view: str = "text"  # "text" or "image"
        self._text_scroll_complete: bool = False
        self._text_view_time: float = 0.0
        self._scroll_duration: float = 0.0

        # Particles
        self._particles = ParticleSystem()

        # Colors - richer mystical palette
        self._primary = (138, 43, 226)    # Purple (BlueViolet)
        self._secondary = (100, 149, 237)  # Cornflower blue
        self._accent = (255, 215, 0)       # Gold
        self._star_color = (255, 250, 205) # Lemon chiffon (stars)

        # S3 upload for QR sharing
        self._uploader = AsyncUploader()
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None

        # Audio engine
        self._audio = get_audio_engine()
        self._last_countdown_tick: int = 0

    def on_enter(self) -> None:
        """Initialize zodiac mode."""
        self._sub_phase = ZodiacPhase.INTRO
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
        self._result_view = "text"
        self._text_scroll_complete = False
        self._text_view_time = 0.0
        self._scroll_duration = 0.0

        # Reset camera state
        self._photo_data = None
        self._camera_frame = None
        self._camera_countdown = 0.0
        self._flash_alpha = 0.0

        # Reset AI state
        self._constellation_portrait = None
        self._ai_task = None
        self._progress_tracker.reset()
        self._qr_url = None
        self._qr_image = None

        # Use shared camera service (always running)
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera service ready for Zodiac mode")
        else:
            logger.warning("Could not open camera, using placeholder")

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
        logger.info("Zodiac mode entered")

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

        # Update live camera preview during camera phases
        if self._sub_phase in (ZodiacPhase.CAMERA_PREP, ZodiacPhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            # Longer, more dramatic intro - 3 seconds
            if self._time_in_phase > 3000:
                self._sub_phase = ZodiacPhase.DATE_INPUT
                self.change_phase(ModePhase.ACTIVE)
                self._time_in_phase = 0

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == ZodiacPhase.DATE_INPUT:
                # Waiting for user input
                pass

            elif self._sub_phase == ZodiacPhase.CAMERA_PREP:
                # Camera prep for 2 seconds
                if self._time_in_phase > 2000:
                    self._start_camera_capture()

            elif self._sub_phase == ZodiacPhase.CAMERA_CAPTURE:
                # Countdown animation
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                # Countdown tick sounds
                current_tick = int(self._camera_countdown) + 1
                if current_tick != self._last_countdown_tick and current_tick >= 1 and current_tick <= 3:
                    self._audio.play_countdown_tick()
                    self._last_countdown_tick = current_tick

                # Capture when countdown reaches 0
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._audio.play_camera_shutter()
                    self._flash_alpha = 1.0

                # Flash effect after capture
                if self._time_in_phase > 3000:
                    self._flash_alpha = max(0, 1.0 - (self._time_in_phase - 3000) / 500)

                    if self._time_in_phase > 3500:
                        self._start_processing()

        elif self.phase == ModePhase.PROCESSING:
            if self._sub_phase == ZodiacPhase.GENERATING:
                # Check AI task progress
                if self._ai_task:
                    if self._ai_task.done():
                        self._on_ai_complete()
                    else:
                        # Continue with reveal while waiting
                        self._reveal_progress = min(0.5, self._time_in_phase / 2000)
            else:
                # Standard processing phase
                self._reveal_progress = min(1.0, self._time_in_phase / 3000)

                # Burst more particles during reveal
                if int(self._time_in_phase / 500) > int((self._time_in_phase - delta_ms) / 500):
                    magic = self._particles.get_emitter("magic")
                    if magic:
                        magic.burst(10)

                if self._reveal_progress >= 1.0:
                    self._sub_phase = ZodiacPhase.RESULT
                    self.change_phase(ModePhase.RESULT)
                    self._audio.play_success()
                    # Final burst
                    stars = self._particles.get_emitter("stars")
                    if stars:
                        stars.burst(50)

        elif self.phase == ModePhase.RESULT:
            # Calculate scroll duration on first entry
            if self._horoscope and self._scroll_duration == 0:
                from artifact.graphics.text_utils import calculate_scroll_duration, MAIN_DISPLAY_WIDTH
                from artifact.graphics.fonts import load_font
                # Horoscope uses wrap_text with max 4 lines, so estimate conservatively
                self._scroll_duration = 3000  # Short horoscopes usually fit, give base time

            # Track time in text view
            if self._result_view == "text":
                self._text_view_time += delta_ms
                if not self._text_scroll_complete and self._text_view_time >= self._scroll_duration:
                    self._text_scroll_complete = True
                    if self._constellation_portrait:
                        self._result_view = "image"

            # Auto-complete after 45 seconds
            if self._time_in_phase > 45000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input.

        Accepts:
        - BUTTON_PRESS (center button): Confirm date / toggle display / finish result
        - ARCADE_LEFT: Navigate left in date (if implemented) or clear / toggle display
        - ARCADE_RIGHT: Navigate right in date (if implemented) / toggle display
        - KEYPAD_INPUT: Direct digit entry
        """
        if event.type == EventType.BUTTON_PRESS:
            # Center button - confirm action
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ZodiacPhase.DATE_INPUT:
                # Confirm date entry with center button
                if self._validate_date():
                    self._audio.play_ui_confirm()
                    self._process_date()
                    return True
                else:
                    self._audio.play_ui_error()
            elif self.phase == ModePhase.RESULT:
                if self._result_view == "text" and self._constellation_portrait:
                    self._audio.play_ui_move()
                    self._result_view = "image"
                    self._text_scroll_complete = True
                else:
                    self._finish()
                return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ZodiacPhase.DATE_INPUT:
                # Ignore navigation from numpad during date input (numpad 4/6 send both nav + digit)
                if event.source == "numpad":
                    return False
                # Backspace - delete last digit
                if self._input_buffer:
                    self._audio.play_ui_back()
                    self._input_buffer = self._input_buffer[:-1]
                    self._input_position = len(self._input_buffer)
                    self._input_valid = False
                return True
            elif self.phase == ModePhase.RESULT:
                # Toggle view
                self._audio.play_ui_move()
                self._cycle_result_view(-1)
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ZodiacPhase.DATE_INPUT:
                # Ignore navigation from numpad during date input (numpad 4/6 send both nav + digit)
                if event.source == "numpad":
                    return False
                # Right arrow - confirm when valid
                if self._validate_date():
                    self._audio.play_ui_confirm()
                    self._process_date()
                return True
            elif self.phase == ModePhase.RESULT:
                # Toggle view
                self._audio.play_ui_move()
                self._cycle_result_view(1)
                return True

        elif event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")

            if self.phase == ModePhase.ACTIVE and self._sub_phase == ZodiacPhase.DATE_INPUT:
                return self._handle_date_input(key)

        return False

    def _handle_date_input(self, key: str) -> bool:
        """Handle date input from keypad.

        Format: DD.MM (day and month)
        """
        if key == "*":
            # Backspace
            if self._input_buffer:
                self._audio.play_ui_back()
                self._input_buffer = self._input_buffer[:-1]
                self._input_position = len(self._input_buffer)
            return True

        elif key == "#":
            # Confirm input
            if self._validate_date():
                self._audio.play_ui_confirm()
                self._process_date()
            else:
                self._audio.play_ui_error()
            return True

        elif key.isdigit() and len(self._input_buffer) < 4:
            # Add digit
            self._audio.play_ui_click()
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
        """Process the entered date and move to camera phase."""
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

        # Move to camera phase
        self._sub_phase = ZodiacPhase.CAMERA_PREP
        self._time_in_phase = 0

        logger.info(f"Zodiac sign determined: {self._zodiac_ru} ({self._zodiac_symbol}), moving to camera")

    def on_exit(self) -> None:
        """Cleanup."""
        # Cancel any pending AI task
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

        # Clear camera reference (shared service, don't close)
        self._camera = None
        self._camera_frame = None

        self._particles.clear_all()
        self.stop_animations()

    def _update_camera_preview(self) -> None:
        """Update the live camera preview frame - clean B&W grayscale (no dithering)."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.size > 0:
                # Simple B&W grayscale conversion - cleaner than dithering
                if len(frame.shape) == 3:
                    gray = (0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1] + 0.114 * frame[:, :, 2]).astype(np.uint8)
                else:
                    gray = frame
                # Resize if needed
                if gray.shape != (128, 128):
                    from PIL import Image
                    img = Image.fromarray(gray)
                    img = img.resize((128, 128), Image.Resampling.BILINEAR)
                    gray = np.array(img, dtype=np.uint8)
                # Convert to RGB (grayscale in all 3 channels)
                bw_frame = np.stack([gray, gray, gray], axis=-1)
                self._camera_frame = create_viewfinder_overlay(bw_frame, self._time_in_phase).copy()
                self._camera = True
        except Exception as e:
            logger.warning(f"Camera preview update error: {e}")

    def _get_result_views(self) -> List[str]:
        views = ["text"]
        if self._constellation_portrait:
            views.append("image")
            if self._qr_image is not None or self._uploader.is_uploading:
                views.append("qr")
        return views

    def _cycle_result_view(self, direction: int) -> None:
        views = self._get_result_views()
        if not views:
            return
        try:
            idx = views.index(self._result_view)
        except ValueError:
            idx = 0
        self._result_view = views[(idx + direction) % len(views)]

    def _result_nav_hint(self) -> Optional[str]:
        views = self._get_result_views()
        if len(views) < 2:
            return None
        try:
            idx = views.index(self._result_view)
        except ValueError:
            idx = 0
        labels = {"text": "ТЕКСТ", "image": "ФОТО", "qr": "QR"}
        left_view = views[(idx - 1) % len(views)]
        right_view = views[(idx + 1) % len(views)]
        return f"◄ {labels[left_view]}  ► {labels[right_view]}"

    def _render_qr_view(self, buffer) -> None:
        """Render full-screen QR view."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        fill(buffer, (255, 255, 255))

        if self._qr_image is not None:
            qr_h, qr_w = self._qr_image.shape[:2]
            target_size = 120
            if qr_h != target_size or qr_w != target_size:
                from PIL import Image
                qr_img = Image.fromarray(self._qr_image)
                qr_img = qr_img.resize((target_size, target_size), Image.Resampling.NEAREST)
                qr_scaled = np.array(qr_img, dtype=np.uint8)
            else:
                qr_scaled = self._qr_image

            qr_h, qr_w = qr_scaled.shape[:2]
            x_offset = (128 - qr_w) // 2
            y_offset = (128 - qr_h) // 2
            buffer[y_offset:y_offset + qr_h, x_offset:x_offset + qr_w] = qr_scaled
        elif self._uploader.is_uploading:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "ЗАГРУЗКА", 50, (200, 200, 100), scale=1)
            draw_centered_text(buffer, "QR...", 65, (200, 200, 100), scale=1)
        else:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "QR", 50, (100, 100, 100), scale=2)
            draw_centered_text(buffer, "НЕ ГОТОВ", 75, (100, 100, 100), scale=1)

        # Hint stays on ticker/LCD for full-screen QR

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = ZodiacPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0
        logger.info("Zodiac camera capture started - countdown begins")

    def _do_camera_capture(self) -> None:
        """Actually capture the photo from camera."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            logger.info(f"Zodiac captured photo: {len(self._photo_data)} bytes")
        else:
            logger.warning("Failed to capture photo in Zodiac mode")

    def _start_processing(self) -> None:
        """Start AI processing for constellation portrait."""
        self._sub_phase = ZodiacPhase.GENERATING
        self.change_phase(ModePhase.PROCESSING)
        self._reveal_progress = 0.0

        # Start progress tracker
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        # Start async AI task for portrait generation
        self._ai_task = asyncio.create_task(self._generate_constellation_portrait())

        # Burst particles
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(50)

        logger.info("Zodiac AI portrait generation started")

    async def _generate_constellation_portrait(self) -> None:
        """Generate constellation-themed portrait using AI."""
        try:
            # Advance to image generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            if self._photo_data:
                self._constellation_portrait = await self._caricature_service.generate_caricature(
                    reference_photo=self._photo_data,
                    style=CaricatureStyle.ZODIAC,
                    personality_context=f"Знак зодиака: {self._zodiac_ru} ({self._zodiac_symbol})",
                )
                if self._constellation_portrait:
                    logger.info("Zodiac constellation portrait generated successfully")

                    # Upload portrait for QR sharing
                    if self._constellation_portrait.image_data:
                        logger.info("Starting zodiac portrait upload for QR sharing")
                        self._uploader.upload_bytes(
                            self._constellation_portrait.image_data,
                            prefix="zodiac",
                            extension="png",
                            content_type="image/png",
                            callback=self._on_upload_complete
                        )
                else:
                    logger.warning("Zodiac constellation portrait generation returned None")
            else:
                logger.warning("No photo data for Zodiac portrait generation")
                self._constellation_portrait = None

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)
        except Exception as e:
            logger.error(f"Zodiac portrait generation failed: {e}")
            self._constellation_portrait = None

    def _on_ai_complete(self) -> None:
        """Handle completion of AI processing."""
        self._progress_tracker.complete()
        self._audio.play_success()
        logger.info("AI complete, finishing mode - manager handles result display")
        # Skip mode's result phase - manager's result view is cleaner
        self._finish()

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle completion of S3 upload for QR sharing."""
        if result.success:
            self._qr_url = result.url
            self._qr_image = result.qr_image
            logger.info(f"Zodiac portrait uploaded successfully: {self._qr_url}")
        else:
            logger.error(f"Zodiac portrait upload failed: {result.error}")

    def _render_camera_preview(self, buffer) -> None:
        """Render the camera preview to buffer."""
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

    def _render_portrait(self, buffer) -> None:
        """Render the AI-generated constellation portrait."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from io import BytesIO

        if not self._constellation_portrait:
            return

        try:
            from PIL import Image

            img = Image.open(BytesIO(self._constellation_portrait.image_data))
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

            # Border with zodiac color
            draw_rect(buffer, x_offset - 2, y_offset - 2, display_size + 4, display_size + 4, self._secondary, filled=False)

            # Label
            draw_centered_text(buffer, f"{self._zodiac_symbol} {self._zodiac_ru}", 112, self._accent, scale=1)

        except Exception as e:
            logger.warning(f"Failed to render zodiac portrait: {e}")

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
                "portrait": self._constellation_portrait.image_data if self._constellation_portrait else None,
                "type": "zodiac_horoscope",
                "qr_url": self._qr_url,
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
            if self._sub_phase == ZodiacPhase.DATE_INPUT:
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

            elif self._sub_phase == ZodiacPhase.CAMERA_PREP:
                # Show live camera preview
                self._render_camera_preview(buffer)
                # Overlay text
                draw_centered_text(buffer, "СМОТРИ В КАМЕРУ", 10, self._accent, scale=1)
                draw_centered_text(buffer, self._zodiac_ru.upper(), 110, self._secondary, scale=2)

            elif self._sub_phase == ZodiacPhase.CAMERA_CAPTURE:
                # Show live camera preview with countdown
                self._render_camera_preview(buffer)

                # Countdown number
                if self._camera_countdown > 0:
                    countdown_num = str(int(self._camera_countdown) + 1)
                    scale = 4 + int((self._camera_countdown % 1) * 2)
                    draw_centered_text(buffer, countdown_num, 45, (255, 255, 255), scale=scale)

                    # Progress ring
                    progress = 1.0 - (self._camera_countdown % 1)
                    for angle_deg in range(0, int(360 * progress), 10):
                        rad = math.radians(angle_deg - 90)
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

        elif self.phase == ModePhase.PROCESSING:
            # Update progress tracker
            self._progress_tracker.update(delta_ms=16)  # Approximate frame time
            progress = self._progress_tracker.get_progress()

            # Mystical loading animation at top
            self._progress_tracker.render_loading_animation(
                buffer, style="mystical", time_ms=self._time_in_phase
            )

            # Rotating glow rings during reveal
            for ring in range(3):
                ring_radius = 20 + ring * 15 + int(progress * 10)
                ring_alpha = int(60 * (1 - progress * 0.5) * (1 - ring / 3))
                ring_angle = self._constellation_angle * (2 - ring * 0.3)
                for angle_deg in range(0, 360, 30):
                    angle = math.radians(angle_deg) + ring_angle
                    rx = int(64 + ring_radius * math.cos(angle))
                    ry = int(55 + ring_radius * math.sin(angle))
                    draw_circle(buffer, rx, ry, 2, (ring_alpha, ring_alpha, ring_alpha + 30))

            # Draw symbol with growing size and glow
            symbol_scale = int(2 + progress * 3)
            symbol_alpha = int(255 * min(1.0, progress * 1.5))

            draw_centered_text(
                buffer, self._zodiac_symbol, 35,
                (symbol_alpha, int(symbol_alpha * 0.9), int(symbol_alpha * 0.7)),
                scale=symbol_scale
            )

            # Sign name fading in with effect
            if progress > 0.3:
                name_progress = min(1.0, (progress - 0.3) * 1.5)
                name_alpha = int(255 * name_progress)
                draw_animated_text(
                    buffer, self._zodiac_ru, 70,
                    (name_alpha, name_alpha, name_alpha),
                    self._time_in_phase, TextEffect.TYPING, scale=2
                )

            # Progress bar at bottom
            bar_x, bar_y, bar_w, bar_h = 14, 94, 100, 8
            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=self._primary,
                bg_color=(20, 20, 40),
                border_color=(80, 80, 140)
            )

            # Status message below progress bar
            status_message = self._progress_tracker.get_message()
            draw_centered_text(buffer, status_message, 108, (140, 140, 180), scale=1)

        elif self.phase == ModePhase.RESULT:
            # Display portrait, QR, or horoscope based on result_view
            if self._result_view == "qr":
                self._render_qr_view(buffer)
            elif self._result_view == "image" and self._constellation_portrait:
                # Portrait view
                self._render_portrait(buffer)

                nav_hint = self._result_nav_hint()
                if nav_hint and int(self._time_in_phase / 500) % 2 != 0:
                    draw_centered_text(buffer, nav_hint, 118, (100, 100, 120), scale=1)
                else:
                    draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 118, (100, 200, 100), scale=1)
            else:
                # Text view - Display zodiac sign and horoscope with pulsing effects

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

                nav_hint = self._result_nav_hint()
                if nav_hint:
                    draw_centered_text(buffer, nav_hint, 118, (100, 150, 200), scale=1)
                elif int(self._time_in_phase / 500) % 2 == 0:
                    draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 118, (100, 200, 100), scale=1)

    def render_ticker(self, buffer) -> None:
        """Render ticker with smooth seamless scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)

        if self.phase == ModePhase.INTRO:
            render_ticker_animated(
                buffer, "ЗОДИАК ОРАКУЛ",
                self._time_in_phase, self._secondary,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == ZodiacPhase.DATE_INPUT:
                render_ticker_animated(
                    buffer, "ВВЕДИ ДАТУ РОЖДЕНИЯ",
                    self._time_in_phase, self._secondary,
                    TickerEffect.SPARKLE_SCROLL, speed=0.025
                )
            elif self._sub_phase == ZodiacPhase.CAMERA_PREP:
                render_ticker_animated(
                    buffer, f"КАМЕРА - {self._zodiac_ru}",
                    self._time_in_phase, self._accent,
                    TickerEffect.PULSE_SCROLL, speed=0.028
                )
            elif self._sub_phase == ZodiacPhase.CAMERA_CAPTURE:
                render_ticker_animated(
                    buffer, "ФОТО!",
                    self._time_in_phase, self._accent,
                    TickerEffect.PULSE_SCROLL, speed=0.03
                )

        elif self.phase == ModePhase.PROCESSING:
            # Processing animation
            render_ticker_animated(
                buffer, f"СОЗДАЮ ПОРТРЕТ - {self._zodiac_ru}",
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
            if self._sub_phase == ZodiacPhase.DATE_INPUT:
                if self._input_buffer:
                    # Format date input nicely
                    dd = self._input_buffer[:2] if len(self._input_buffer) >= 2 else self._input_buffer + "_" * (2 - len(self._input_buffer))
                    mm = self._input_buffer[2:4] if len(self._input_buffer) >= 4 else self._input_buffer[2:] + "_" * (4 - len(self._input_buffer))
                    return f" * {dd}.{mm} * ".center(16)[:16]
                return " * ДД.ММ * ".center(16)
            elif self._sub_phase == ZodiacPhase.CAMERA_PREP:
                eye = "*" if int(self._time_in_phase / 300) % 2 == 0 else "o"
                return f" {eye} КАМЕРА {eye} ".center(16)[:16]
            elif self._sub_phase == ZodiacPhase.CAMERA_CAPTURE:
                countdown = int(self._camera_countdown) + 1
                return f" * ФОТО: {countdown} * ".center(16)[:16]
        elif self.phase == ModePhase.PROCESSING:
            # Animated star reading
            dots = "-\\|/"
            dot = dots[int(self._time_in_phase / 200) % 4]
            return f" {dot} ПОРТРЕТ {dot} ".center(16)[:16]
        elif self.phase == ModePhase.RESULT:
            # Show zodiac symbol + name
            return f" {self._zodiac_symbol} {self._zodiac_ru} {self._zodiac_symbol} ".center(16)[:16]
        return " * ЗОДИАК * ".center(16)[:16]

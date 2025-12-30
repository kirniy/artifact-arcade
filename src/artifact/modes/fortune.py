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
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.audio.engine import get_audio_engine
from artifact.utils.camera import create_viewfinder_overlay
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult
from artifact.animation.santa_runner import SantaRunner, reset_santa_runner

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

# Multiple creative approaches for variety - randomly selected each time
import random

# APPROACH 1: BUREAUCRATIC ORACLE - Soviet DMV meets cosmic fate office
BUREAUCRATIC_ORACLE_SYSTEM = """Ты уставший клерк межпространственной канцелярии судеб. Обрабатываешь человеческие судьбы как бюрократические дела. Советская канцелярия встречает космический МФЦ.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!
ДЛИНА ТЕКСТА: СТРОГО 65-70 слов. Не меньше, не больше!

=== ГОЛОС И СТИЛЬ ===
Официальный, уставший, канцелярский тон. Говоришь о судьбе как о формальности. Штампуешь вердикты. Удивительно конкретные наблюдения поданы сухим языком. Черный юмор через бюрократический абсурд.

=== ОБЯЗАТЕЛЬНО ВКЛЮЧИ ===
1. КОНКРЕТНОЕ наблюдение о ВНЕШНОСТИ с фото: глаза, брови, улыбка, одежда, поза, выражение лица
2. Астрологический диагноз по дате рождения (западный и восточный знак)
3. Последствия или назначения что произойдет как результат того кто они есть
4. Одна рекомендация или предписание
Начни с номера дела (рандомный 6 значный номер). Закончи штампом: ОБРАБОТАНО / ОДОБРЕНО / ОТКАЗАНО / ДЕЛО ЗАКРЫТО

=== ПРИМЕРЫ ===
Дело номер 847291. Субъект демонстрирует признаки хронического оптимизма несмотря на конфигурацию бровей указывающую на скрытую тревогу. По дате рождения 15.03.1995 установлен статус Рыбы/Свинья, что объясняет патологическую доброту и неспособность говорить нет. Зафиксировано: свитер нейтрального цвета как попытка слиться с фоном, неуспешная. Одобрено для получения: неожиданный комплимент от незнакомца в течение 9 дней. В выдаче отказано: покой и тишина в ближайший месяц. Рекомендовано: прекратить читать рабочие чаты после 20:00. Форма 27/Б о пересмотре судьбы должна быть подана лично. ОБРАБОТАНО.

Format:
PREDICTION: [СТРОГО 65-70 слов в бюрократическом стиле с номером дела и штампом]
ZODIAC: [западный знак]
CHINESE: [восточный знак]
LUCKY_COLOR: [цвет]
"""

# APPROACH 2: COSMIC VERDICT - Tribunal has reviewed your case
COSMIC_VERDICT_SYSTEM = """Ты глас невидимого трибунала. Человек был рассмотрен. Выноси приговор. Преступления это черты личности видимые по внешности и дате рождения. Приговоры это последствия.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!
ДЛИНА ТЕКСТА: СТРОГО 65-70 слов. Не меньше, не больше!

=== ГОЛОС И СТИЛЬ ===
Формальный, судебный тон. Драматичный но не напыщенный. Преступления и приговоры абсурдно конкретные. Никогда не жестокий, просто официальный.

=== ОБЯЗАТЕЛЬНО ВКЛЮЧИ ===
1. КОНКРЕТНЫЕ детали ВНЕШНОСТИ с фото в обвинениях: глаза, брови, поза, одежда, выражение
2. Дата рождения и знаки зодиака (западный/восточный)
3. 2 обвинения основанных на том что ВИДНО на фото
4. Приговор как предсказание

=== СТРУКТУРА ОТВЕТА ===
ТРИБУНАЛ РАССМОТРЕЛ ДЕЛО.
Дата рождения: [дата]. Астрологический статус: [западный знак]/[восточный знак].
Обвинение: [черта видимая по внешности как преступление]
Обвинение: [еще одна черта как преступление]
ПРИГОВОР: [последствие]
ДЕЛО ЗАКРЫТО.

=== ПРИМЕРЫ ОБВИНЕНИЙ ===
Обвинение: систематическое произнесение фразы у меня все нормально когда все не нормально, о чем свидетельствует напряжение в уголках глаз
Обвинение: оставание на вечеринке когда надо было уйти, подтверждается выражением хронического недосыпа
Обвинение: чрезмерная забота о других при полном игнорировании себя, видно по теплому но усталому взгляду

Format:
PREDICTION: [СТРОГО 65-70 слов в формате ТРИБУНАЛ РАССМОТРЕЛ ДЕЛО с обвинениями и приговором]
ZODIAC: [западный знак]
CHINESE: [восточный знак]
LUCKY_COLOR: [цвет]
"""

# APPROACH 3: DRUNK PROPHET - Your wasted friend who gets profound at 3am
DRUNK_PROPHET_SYSTEM = """Ты мистическое существо которое перебрало и теперь выдает неудобную правду. Энергия пьяного друга который внезапно становится философом в 3 часа ночи.

=== ТЕХНИЧЕСКИЕ ОГРАНИЧЕНИЯ ===
Символы: А-Яа-я A-Za-z 0-9 . , ! ? : ( ) / %
НЕЛЬЗЯ: эмодзи, кавычки, тире, дефис, многоточие, любые другие символы!
ДЛИНА ТЕКСТА: СТРОГО 65-70 слов. Не меньше, не больше!

=== ГОЛОС И СТИЛЬ ===
Сбивчивая речь, перебиваешь сам себя. Внезапные переходы между темами. Искренняя забота под хаосом. Нет реально послушай энергия. Пугающе точные наблюдения поданы как пьяный бред.

=== ОБЯЗАТЕЛЬНО ВКЛЮЧИ ===
1. КОНКРЕТНОЕ наблюдение о ВНЕШНОСТИ с фото: глаза, выражение, одежда, поза (подано эмоционально!)
2. Дату рождения и знаки зодиака (западный/восточный) но хаотично
3. Конкретный совет или предсказание
4. Внезапное признание в любви или заботе
Можешь перебивать себя, менять тему, начать с Слушай... или Так... или Окей окей окей

=== ПРИМЕРЫ ===
Слушай... СЛУШАЙ. Я тебя вижу. Нет, реально вижу. Ты же Телец по западному, да? И еще какая то восточная штука, Обезьяна кажется, 1992 год. Короче неважно. Важно что у тебя на лице написано что ты устал притворяться что тебе все равно. Эти глаза которые типа спокойные но внутри там пожар. И я сейчас максимально серьезно говорю: через неделю тебе напишет человек о котором ты думал что все кончено. Не игнорь. И воды выпей. Я тебя люблю.

Format:
PREDICTION: [СТРОГО 65-70 слов в пьяном но мудром стиле]
ZODIAC: [западный знак]
CHINESE: [восточный знак]
LUCKY_COLOR: [цвет]
"""

# List of all approaches for random selection
FORTUNE_APPROACHES = [
    BUREAUCRATIC_ORACLE_SYSTEM,
    COSMIC_VERDICT_SYSTEM,
    DRUNK_PROPHET_SYSTEM,
]

def get_fortune_system_prompt() -> str:
    """Get a randomly selected fortune telling approach."""
    return random.choice(FORTUNE_APPROACHES)

# Legacy alias for compatibility
FORTUNE_TELLER_SYSTEM_PROMPT = BUREAUCRATIC_ORACLE_SYSTEM

# Combined prompt - simplified, main instructions are in system prompt
COMBINED_FORTUNE_PROMPT = """Дата рождения человека на фото: {birthdate}

Изучи фото внимательно:
1. Выражение лица и глаз
2. Поза и язык тела
3. Стиль одежды и аксессуары
4. Общая энергия и вайб

Используй ВСЕ эти наблюдения в своем ответе. Определи западный и восточный знак зодиака по дате.

Format:
PREDICTION: [твое предсказание в стиле указанном в системном промпте]
ZODIAC: [западный знак]
CHINESE: [восточный знак]
LUCKY_COLOR: [цвет на русском]
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
    display_name = "ГАДАТЕЛЬ"
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
        self._audio = get_audio_engine()

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
        self._progress_tracker = SmartProgressTracker(mode_theme="fortune")

        # Camera state
        self._camera: bool = False  # Whether camera is available
        self._camera_frame: Optional[np.ndarray] = None  # Dithered preview frame
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._last_countdown_tick: int = 0  # Track countdown ticks for sound
        self._flash_alpha: float = 0.0

        # Animation state
        self._reveal_progress: float = 0.0
        self._glow_phase: float = 0.0
        self._ball_glow: float = 0.0

        # Result view state - PAGE-BASED navigation (no scrolling!)
        # Flow: text pages -> image -> QR
        self._current_page: int = 0
        self._text_pages: List[List[str]] = []  # Lines per text page
        self._total_pages: int = 0
        self._lines_per_page: int = 5  # Lines at scale 2 that fit on screen

        # Particles
        self._particles = ParticleSystem()

        # Colors (mystical style)
        self._primary = (107, 33, 168)    # Purple
        self._secondary = (245, 158, 11)   # Gold
        self._accent = (20, 184, 166)      # Teal

        # S3 upload for QR sharing
        self._uploader = AsyncUploader()
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None

        # Santa runner minigame for waiting screen
        self._santa_runner: Optional[SantaRunner] = None

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
        self._zodiac_symbol = ""
        self._chinese_zodiac = ""
        self._chinese_emoji = ""
        self._caricature = None
        self._ai_task = None
        self._processing_progress = 0.0
        self._progress_tracker.reset()
        self._qr_url = None
        self._qr_image = None
        self._reveal_progress = 0.0

        # Reset pagination state
        self._current_page = 0
        self._text_pages = []
        self._total_pages = 0

        # Use shared camera service (always running)
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera service ready for Fortune mode")
        else:
            logger.warning("Camera service not running, using placeholder")

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

                # Play countdown tick sounds (3, 2, 1)
                current_tick = int(self._camera_countdown) + 1
                if current_tick != self._last_countdown_tick and current_tick >= 1 and current_tick <= 3:
                    self._audio.play_countdown_tick()
                    self._last_countdown_tick = current_tick

                # Capture when countdown reaches 0
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._audio.play_camera_shutter()  # Shutter sound
                    self._flash_alpha = 1.0

                # Flash effect after capture
                if self._time_in_phase > 3000:
                    self._flash_alpha = max(0, 1.0 - (self._time_in_phase - 3000) / 500)

                    if self._time_in_phase > 3500:
                        self._start_processing()

        elif self.phase == ModePhase.PROCESSING:
            # Update smart progress tracker
            self._progress_tracker.update(delta_ms)

            # Update Santa runner minigame
            if self._santa_runner:
                self._santa_runner.update(delta_ms)

            # Check AI task progress
            if self._ai_task:
                if self._ai_task.done():
                    self._on_ai_complete()
                else:
                    # Use smart progress tracker for visual feedback
                    self._processing_progress = self._progress_tracker.get_progress()

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == FortunePhase.REVEAL:
                self._reveal_progress = min(1.0, self._time_in_phase / 2000)

                if self._reveal_progress >= 1.0:
                    self._sub_phase = FortunePhase.RESULT
                    # Paginate prediction text when entering result phase
                    if self._prediction and not self._text_pages:
                        self._paginate_prediction()
                    self._current_page = 0  # Start at first text page (if available)

            elif self._sub_phase == FortunePhase.RESULT:
                # Auto-complete after 60 seconds
                if self._time_in_phase > 60000:
                    self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        # Keypad input for birthdate
        if event.type == EventType.KEYPAD_INPUT:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                key = event.data.get("key", "")
                if key.isdigit():
                    self._add_digit(key)
                    self._audio.play_ui_click()
                    return True
                elif key == "*":
                    # Backspace
                    self._remove_digit()
                    self._audio.play_ui_back()
                    return True
                elif key == "#":
                    # Confirm (if complete)
                    if self._input_complete:
                        self._confirm_birthdate()
                    else:
                        self._audio.play_ui_error()
                    return True

        elif event.type == EventType.BUTTON_PRESS:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                if self._input_complete:
                    self._confirm_birthdate()
                    return True
            elif self._sub_phase == FortunePhase.PROCESSING:
                # Play Santa runner minigame while waiting - JUMP!
                if self._santa_runner:
                    self._santa_runner.handle_jump()
                    self._audio.play_ui_click()
                return True
            elif self.phase == ModePhase.RESULT and self._sub_phase == FortunePhase.RESULT:
                # Main button = print and finish
                self._finish()
                return True

        elif event.type == EventType.ARCADE_LEFT:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                # Ignore navigation from numpad during date input (numpad 4/6 send both nav + digit)
                if event.source == "numpad":
                    return False
                self._remove_digit()
                self._audio.play_ui_back()
                return True
            if self.phase == ModePhase.RESULT and self._sub_phase == FortunePhase.RESULT:
                # Previous page
                if self._current_page > 0:
                    self._current_page -= 1
                    self._audio.play_ui_move()
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self._sub_phase == FortunePhase.BIRTHDATE_INPUT:
                # Ignore navigation from numpad during date input (numpad 4/6 send both nav + digit)
                if event.source == "numpad":
                    return False
                if self._input_complete:
                    self._confirm_birthdate()
                return True
            if self.phase == ModePhase.RESULT and self._sub_phase == FortunePhase.RESULT:
                # Next page
                if self._current_page < self._total_pages - 1:
                    self._current_page += 1
                    self._audio.play_ui_move()
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

        # Calculate zodiac from birthdate
        day, month, year = self._birthdate
        sign_name, sign_symbol, element = get_zodiac_sign(day, month)
        self._zodiac_sign = sign_name
        self._zodiac_symbol = sign_symbol

        # Calculate Chinese zodiac
        chinese_name, chinese_emoji, chinese_trait = get_chinese_zodiac(year)
        self._chinese_zodiac = chinese_name
        self._chinese_emoji = chinese_emoji

        self._sub_phase = FortunePhase.CAMERA_PREP
        self._time_in_phase = 0

        # Sound effect for confirmation
        self._audio.play_ui_confirm()

        # Burst particles for transition
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(30)

        logger.info(f"Birthdate confirmed ({self._zodiac_sign} {self._zodiac_symbol}), moving to camera prep")

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = FortunePhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0
        logger.info("Camera capture started - countdown begins")

    def _do_camera_capture(self) -> None:
        """Actually capture the photo from camera."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            logger.info(f"Captured photo: {len(self._photo_data)} bytes")
        else:
            logger.warning("Failed to capture photo")

    def _update_camera_preview(self) -> None:
        """Update the live camera preview frame - clean B&W grayscale (no heavy dithering)."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.size > 0:
                # Simple B&W grayscale conversion - much cleaner than dithering
                # Weighted average of RGB channels for proper luminance
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

                # Convert back to RGB (grayscale in all 3 channels)
                bw_frame = np.stack([gray, gray, gray], axis=-1)

                # Add viewfinder overlay for visual feedback
                self._camera_frame = create_viewfinder_overlay(bw_frame, self._time_in_phase).copy()
                self._camera = True
        except Exception as e:
            logger.warning(f"Camera preview update error: {e}")

    def _start_processing(self) -> None:
        """Start AI processing (prediction + caricature in parallel)."""
        self._sub_phase = FortunePhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        # Start smart progress tracker
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        # Initialize Santa runner minigame for the waiting screen
        self._santa_runner = SantaRunner()
        self._santa_runner.reset()

        # Play mystical ambient sound
        self._audio.play("fortune_mystical", volume=0.5)

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

                # Get a random approach for variety each time
                system_prompt = get_fortune_system_prompt()

                # If we have photo, use vision model with photo + prompt
                if self._photo_data:
                    response = await self._gemini_client.generate_with_image(
                        prompt=prompt,
                        image_data=self._photo_data,
                        mime_type="image/jpeg",
                        model=GeminiModel.FLASH_VISION,
                        system_instruction=system_prompt,
                    )
                else:
                    # No photo - text only
                    response = await self._gemini_client.generate_text(
                        prompt=f"Дата рождения: {birthdate_str}\n\nСоздай предсказание!",
                        model=GeminiModel.FLASH,
                        system_instruction=system_prompt,
                        temperature=0.9,
                    )

                if response:
                    return self._parse_prediction_response(response)
                return self._fallback_prediction()

            # Generate caricature (tarot card style portrait)
            async def generate_caricature():
                if self._photo_data:
                    return await self._caricature_service.generate_caricature(
                        reference_photo=self._photo_data,
                        style=CaricatureStyle.TAROT,  # Tarot card style portrait
                        personality_context=f"Дата рождения: {birthdate_str}",
                    )
                return None

            # Run in parallel
            prediction_task = asyncio.create_task(generate_prediction())
            caricature_task = asyncio.create_task(generate_caricature())

            # Advance to text generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)

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
                # Prediction done, advance to image generation
                self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)
            except asyncio.TimeoutError:
                logger.warning("Prediction generation timed out")
                fallback = self._fallback_prediction()
                self._prediction = fallback[0]
                self._lucky_color = fallback[1]
                self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            # Wait for caricature
            try:
                self._caricature = await asyncio.wait_for(caricature_task, timeout=120.0)
                # Image done, advance to finalizing
                self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

                # Upload caricature for QR sharing
                if self._caricature and self._caricature.image_data:
                    logger.info("Starting caricature upload for QR sharing")
                    self._uploader.upload_bytes(
                        self._caricature.image_data,
                        prefix="fortune",
                        extension="png",
                        content_type="image/png",
                        callback=self._on_upload_complete
                    )
            except asyncio.TimeoutError:
                logger.warning("Caricature generation timed out")
                self._caricature = None
                self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

            logger.info("AI generation complete")

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            fallback = self._fallback_prediction()
            self._prediction = fallback[0]
            self._lucky_color = fallback[1]

    def _parse_prediction_response(self, response: str) -> Tuple[str, str, str, str]:
        """Parse the AI response into components.

        Handles multi-line PREDICTION content by collecting all text until the next
        field marker (ZODIAC:, CHINESE:, LUCKY_COLOR:, PHOTO_ANALYSIS:).
        """
        prediction_text = ""
        lucky_color = "золотой"
        zodiac = ""
        chinese = ""

        try:
            lines = response.strip().split("\n")
            current_field = None
            prediction_lines = []

            for line in lines:
                line_stripped = line.strip()

                # Check for field markers
                if line_stripped.startswith("PREDICTION:"):
                    current_field = "prediction"
                    # Get text after the marker on same line
                    text_after = line_stripped[11:].strip()
                    if text_after:
                        prediction_lines.append(text_after)
                elif line_stripped.startswith("LUCKY_COLOR:"):
                    current_field = None
                    lucky_color = line_stripped[12:].strip()
                elif line_stripped.startswith("ZODIAC:"):
                    current_field = None
                    zodiac = line_stripped[7:].strip()
                elif line_stripped.startswith("CHINESE:"):
                    current_field = None
                    chinese = line_stripped[8:].strip()
                elif line_stripped.startswith("PHOTO_ANALYSIS:"):
                    current_field = None  # Skip photo analysis field
                elif current_field == "prediction" and line_stripped:
                    # Continue collecting prediction text
                    prediction_lines.append(line_stripped)

            # Join all prediction lines with spaces
            prediction_text = " ".join(prediction_lines)

            # If parsing failed, use the whole response
            if not prediction_text:
                # Try to extract just the text, removing known markers
                clean_response = response.strip()
                for marker in ["PREDICTION:", "ZODIAC:", "CHINESE:", "LUCKY_COLOR:", "PHOTO_ANALYSIS:"]:
                    if marker in clean_response:
                        clean_response = clean_response.split(marker)[0]
                prediction_text = clean_response.strip() if clean_response.strip() else response[:500]

        except Exception as e:
            logger.warning(f"Error parsing prediction: {e}")
            prediction_text = response[:500]

        logger.info(f"Parsed prediction: {len(prediction_text)} chars, zodiac={zodiac}, chinese={chinese}")
        return prediction_text, lucky_color, zodiac, chinese

    def _fallback_prediction(self) -> Tuple[str, str, str, str]:
        """Generate fallback prediction when AI unavailable - Russian Gen Z style!"""
        import time
        random.seed(time.time())

        # Fun, quirky, ironic predictions - Russian Gen Z style
        fallback_texts = [
            "Короче, следующие две недели будут максимально рандомные. Кто то из твоего прошлого напишет тебе в три часа ночи что то странное. Не игнорь, там может быть инфа которая тебе реально нужна. А ещё перестань откладывать ту штуку которую давно хотел сделать. Ты знаешь какую!",
            "Вижу что ты тот ещё хаотик нейтрал. Но это база! В ближайшее время кто то попытается тебя триггернуть на рофл. Не ведись, это проверка на стрессоустойчивость. Зато потом будет жирный вайб и возможность которую ты не ждал.",
            "Окей, слушай сюда. Скоро тебе предложат что то от чего захочется отмазаться. Не отмазывайся! Это твой шанс выйти из зоны комфорта и наконец сделать что то крутое. Да, будет кринж. Но потом будет гордость. Доверься процессу!",
            "Ладно, буду честной. Следующий месяц будет как американские горки, только без ремня безопасности. Но ты справишься потому что ты уже справлялся с вещами и похуже. Жди сообщение от человека которого давно не видел. Там будет что то важное.",
            "Слушай, у тебя всё получится. Серьёзно. Та штука которая не даёт тебе спать, она разрулится. Не завтра, но скоро. А пока перестань скроллить ленту в три часа ночи и выспись нормально. Вселенная любит отдохнувших людей!",
            "Чую что ты устал от всей этой дичи вокруг. Понимаю, 2024 это вообще отдельный квест. Но именно сейчас тебе нужно не сдаваться. Через пару недель появится человек который поможет разобраться с тем что бесит. Просто будь открыт к новому!",
            "Короче, хватит сомневаться в себе. Ты реально можешь больше чем думаешь. В ближайшее время придётся принять решение, и ты уже знаешь какое оно должно быть. Доверяй себе, ты не дурак!",
            "Окей, карты говорят что пора перестать притворяться что всё норм когда всё не норм. Выскажи наконец то что думаешь. Да, будет неловко. Но потом станет легче. И кто то тебя удивит своей реакцией. В хорошем смысле!",
        ]

        colors = ["золотой", "неоновый", "чёрный матовый", "хромированный", "кислотный", "космический"]
        # Use actual zodiac signs based on current date as fallback
        zodiacs = ["Овен", "Телец", "Близнецы", "Рак", "Лев", "Дева", "Весы", "Скорпион", "Стрелец", "Козерог", "Водолей", "Рыбы"]
        animals = ["Дракон", "Змея", "Лошадь", "Коза", "Обезьяна", "Петух", "Собака", "Свинья", "Крыса", "Бык", "Тигр", "Кролик"]

        return (
            random.choice(fallback_texts),
            random.choice(colors),
            random.choice(zodiacs),
            random.choice(animals)
        )

    def _on_ai_complete(self) -> None:
        """Handle completion of AI processing."""
        self._processing_progress = 1.0
        self._progress_tracker.complete()

        # Play success/reveal sound
        self._audio.play_success()

        # Burst particles for reveal
        stars = self._particles.get_emitter("stars")
        if stars:
            stars.burst(100)

        logger.info("AI complete, finishing mode - manager handles result display")

        # Skip mode's result phase - manager's result view is cleaner
        self._finish()

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle completion of S3 upload for QR sharing."""
        if result.success:
            self._qr_url = result.url
            self._qr_image = result.qr_image
            # Recalculate total pages to include QR
            self._recalculate_total_pages()
            logger.info(f"Fortune caricature uploaded successfully: {self._qr_url}")
        else:
            logger.error(f"Fortune caricature upload failed: {result.error}")

    def _has_image(self) -> bool:
        return bool(self._caricature and self._caricature.image_data)

    def _has_qr(self) -> bool:
        return self._qr_image is not None or self._uploader.is_uploading

    def _recalculate_total_pages(self) -> None:
        pages = len(self._text_pages)
        if self._has_image():
            pages += 1
        if self._has_qr():
            pages += 1
        self._total_pages = max(1, pages)

    def _paginate_prediction(self) -> None:
        """Split prediction text into static pages for display.

        Page structure:
        - Pages 0 to N-1: Text pages
        - Next page: Image (caricature) if available
        - Last page: QR code (if available)
        """
        from artifact.graphics.text_utils import smart_wrap_text, MAIN_DISPLAY_WIDTH
        from artifact.graphics.fonts import load_font

        if not self._prediction:
            self._text_pages = []
            self._recalculate_total_pages()
            return

        font = load_font("cyrillic")
        margin = 6
        available_width = MAIN_DISPLAY_WIDTH - margin * 2

        # Wrap text at scale 2 (larger, more readable)
        all_lines = smart_wrap_text(self._prediction, available_width, font, scale=2)

        # Split into pages of N lines each
        self._text_pages = []
        for i in range(0, len(all_lines), self._lines_per_page):
            page_lines = all_lines[i:i + self._lines_per_page]
            self._text_pages.append(page_lines)

        # Total pages: text pages + image (if available) + QR (if available)
        self._recalculate_total_pages()

        logger.info(f"Paginated prediction: {len(all_lines)} lines -> {len(self._text_pages)} text pages, total {self._total_pages} pages")

    def on_exit(self) -> None:
        """Cleanup."""
        # Cancel any pending AI task
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

        # Clear camera state (shared service, don't close)
        self._camera = False
        self._camera_frame = None

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
            lcd_text=" ГАДАТЕЛЬ ".center(16),
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
                "qr_url": self._qr_url,
                "qr_image": self._qr_image,
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
        draw_centered_text(buffer, "ГАДАТЕЛЬ", 85, self._secondary, scale=2)
        draw_centered_text(buffer, "Введи дату рождения", 105, (150, 150, 170), scale=1)

    def _render_birthdate_input(self, buffer, font) -> None:
        """Render birthdate input screen."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.fonts import draw_text_bitmap

        # Title at top
        draw_centered_text(buffer, "ДАТА РОЖДЕНИЯ", 8, self._secondary, scale=1)

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

        # Draw input field background - wide box to fit date at scale 2
        box_width = 124
        box_height = 28
        box_x = (128 - box_width) // 2
        box_y = 40
        draw_rect(buffer, box_x, box_y, box_width, box_height, (40, 35, 60))
        draw_rect(buffer, box_x, box_y, box_width, box_height, self._primary, filled=False)

        # Draw date text - centered inside the box
        text_y = box_y + (box_height - 14) // 2
        draw_centered_text(buffer, display, text_y, (255, 255, 255), scale=2)

        # Button hint when date is complete
        if len(self._input_digits) == 8:
            try:
                digits = "".join(self._input_digits)
                day = int(digits[0:2])
                month = int(digits[2:4])
                year = int(digits[4:8])
                if 1 <= day <= 31 and 1 <= month <= 12 and 1900 <= year <= 2024:
                    draw_centered_text(buffer, "ЖМИ КНОПКУ", 80, (100, 255, 100), scale=1)
                else:
                    draw_centered_text(buffer, "НЕВЕРНАЯ ДАТА", 80, (255, 100, 100), scale=1)
            except:
                pass
        else:
            draw_centered_text(buffer, "Используй цифры", 80, (100, 100, 120), scale=1)

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
        draw_centered_text(buffer, self._zodiac_sign.upper(), 110, self._secondary, scale=1)

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
        """Render Santa runner minigame while AI is processing, with camera as background."""
        from artifact.graphics.primitives import draw_rect, fill
        from artifact.graphics.text_utils import draw_centered_text

        # Get live camera frame for background
        camera_bg = camera_service.get_frame(timeout=0)

        # Render the Santa runner game with camera background
        if self._santa_runner:
            self._santa_runner.render(buffer, background=camera_bg)

            # Add compact progress bar at the top
            bar_w, bar_h = 100, 4
            bar_x = (128 - bar_w) // 2
            bar_y = 2

            # Semi-transparent dark background for progress bar
            draw_rect(buffer, bar_x - 2, bar_y - 1, bar_w + 4, bar_h + 2, (20, 20, 40))

            # Use the SmartProgressTracker's render method for the progress bar
            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=self._accent,
                bg_color=(40, 40, 60),
                time_ms=self._time_in_phase
            )

            # Show compact status at bottom
            status_message = self._progress_tracker.get_message()
            # Semi-transparent dark strip for text
            draw_rect(buffer, 0, 118, 128, 10, (20, 15, 35))
            draw_centered_text(buffer, status_message, 119, (150, 150, 170), scale=1)

        else:
            # Fallback to simple processing screen if no game
            fill(buffer, (20, 15, 35))
            draw_centered_text(buffer, "ГАДАЮ...", 55, self._accent, scale=2)

    def _get_page_type(self, page_num: int) -> str:
        """Determine what type of content is on a given page number.

        Page structure:
        - Pages 0 to len(text_pages)-1: Text pages
        - Next page: Image (if available)
        - Last page (if QR available): QR code
        """
        if page_num < len(self._text_pages):
            return "text"

        cursor = len(self._text_pages)
        if self._has_image():
            if page_num == cursor:
                return "image"
            cursor += 1

        if self._has_qr() and page_num == cursor:
            return "qr"

        return "text"  # Fallback

    def _get_nav_hint(self) -> str:
        """Get navigation hint showing current page and arrows."""
        if self._total_pages <= 1:
            return "КНОПКА = ПЕЧАТЬ"

        # Show compact page indicator with arrows
        page_num = self._current_page + 1
        total = self._total_pages

        left_arrow = "◄" if self._current_page > 0 else " "
        right_arrow = "►" if self._current_page < self._total_pages - 1 else " "

        return f"{left_arrow} {page_num}/{total} {right_arrow} ПЕЧАТЬ"

    def _render_result(self, buffer, font) -> None:
        """Render prediction result with PAGE-BASED navigation.

        Page structure:
        - Pages 0-N: Static text pages (no scrolling!)
        - Next page: Image (caricature) if available
        - Last page: Full-screen QR code if available
        """
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        if self._sub_phase == FortunePhase.REVEAL:
            # During reveal, show image with fade-in
            self._render_page_image(buffer, font)
            return

        # Determine what to render based on current page
        page_type = self._get_page_type(self._current_page)

        if page_type == "image":
            self._render_page_image(buffer, font)
        elif page_type == "text":
            text_page_idx = self._current_page
            self._render_page_text(buffer, font, text_page_idx)
        elif page_type == "qr":
            self._render_page_qr(buffer, font)

    def _render_page_text(self, buffer, font, text_page_idx: int) -> None:
        """Render a static text page - FULL SCREEN, maximum space usage.

        Displays pre-paginated lines at scale 2, filling entire display.
        No navigation hints - ticker/LCD shows navigation info.
        """
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        # Dark mystical background
        fill(buffer, (20, 15, 35))

        if text_page_idx < 0 or text_page_idx >= len(self._text_pages):
            draw_centered_text(buffer, "НЕТ ТЕКСТА", 55, (100, 100, 100), scale=2)
            return

        lines = self._text_pages[text_page_idx]
        scale = 2
        line_height = 18  # Tighter spacing for scale 2 to fit more text

        # FULL SCREEN - use all 128 pixels of height
        total_height = len(lines) * line_height
        # Center text block in full 128px height
        start_y = max(4, (128 - total_height) // 2)

        # Render each line with subtle wave animation
        for i, line in enumerate(lines):
            # Subtle wave effect
            wave_offset = int(1.5 * math.sin(self._time_in_phase / 300 + i * 0.5))
            y = start_y + i * line_height + wave_offset

            # Subtle pulse
            pulse = 0.9 + 0.1 * math.sin(self._time_in_phase / 400 + i * 0.3)
            color = tuple(int(255 * pulse) for _ in range(3))

            draw_centered_text(buffer, line, y, color, scale=scale)

        # NO bottom navigation hint - ticker/LCD shows "ЛИСТАТЬ" etc.

    def _render_page_image(self, buffer, font) -> None:
        """Render the caricature/image page - FULLSCREEN."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text
        from io import BytesIO

        # Dark background
        fill(buffer, (20, 15, 35))

        if not self._caricature:
            # No image - show placeholder
            draw_centered_text(buffer, "НЕТ ФОТО", 55, (100, 100, 100), scale=2)
            return

        try:
            from PIL import Image

            img = Image.open(BytesIO(self._caricature.image_data))
            img = img.convert("RGB")

            # FULLSCREEN - fill entire 128x128 display
            display_size = 128
            img = img.resize((display_size, display_size), Image.Resampling.LANCZOS)

            x_offset = 0
            y_offset = 0

            # Fade-in during reveal phase
            if self._sub_phase == FortunePhase.REVEAL:
                alpha = min(1.0, self._reveal_progress)
            else:
                alpha = 1.0

            # Copy image to buffer
            img_array = np.array(img, dtype=np.uint8)
            if alpha < 1.0:
                img_array = (img_array.astype(np.float32) * alpha).astype(np.uint8)

            buffer[:display_size, :display_size] = img_array

        except Exception as e:
            logger.warning(f"Failed to render caricature: {e}")
            draw_centered_text(buffer, "ОШИБКА", 55, (255, 100, 100), scale=2)

    def _render_page_qr(self, buffer, font) -> None:
        """Render full-screen QR code page (last page)."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        if self._qr_image is not None:
            # White background for QR visibility
            fill(buffer, (255, 255, 255))

            qr_h, qr_w = self._qr_image.shape[:2]

            # Scale QR to fill most of the screen
            target_size = 120
            if qr_h != target_size or qr_w != target_size:
                from PIL import Image
                qr_pil = Image.fromarray(self._qr_image)
                qr_pil = qr_pil.resize((target_size, target_size), Image.Resampling.NEAREST)
                qr_scaled = np.array(qr_pil)
            else:
                qr_scaled = self._qr_image

            qr_h, qr_w = qr_scaled.shape[:2]
            x_offset = (128 - qr_w) // 2
            y_offset = (128 - qr_h) // 2

            buffer[y_offset:y_offset + qr_h, x_offset:x_offset + qr_w] = qr_scaled

        elif self._uploader.is_uploading:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "ЗАГРУЗКА", 45, (200, 200, 100), scale=2)
            draw_centered_text(buffer, "QR КОДА...", 70, (150, 150, 150), scale=1)
        else:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "QR", 45, (100, 100, 100), scale=2)
            draw_centered_text(buffer, "НЕ ГОТОВ", 70, (100, 100, 100), scale=1)

        # Hint stays on ticker/LCD for full-screen QR

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
            # Show mode name on ticker, not the date input
            render_ticker_animated(
                buffer, "ГАДАТЕЛЬ",
                self._time_in_phase, self._secondary,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

        elif self._sub_phase == FortunePhase.CAMERA_PREP:
            render_ticker_animated(
                buffer, "КАМЕРА",
                self._time_in_phase, self._accent,
                TickerEffect.PULSE_SCROLL, speed=0.028
            )

        elif self._sub_phase == FortunePhase.CAMERA_CAPTURE:
            render_ticker_animated(
                buffer, "ФОТО",
                self._time_in_phase, self._accent,
                TickerEffect.PULSE_SCROLL, speed=0.03
            )

        elif self._sub_phase == FortunePhase.PROCESSING:
            render_ticker_animated(
                buffer, f"ГАДАЮ ДЛЯ {self._zodiac_sign}",
                self._time_in_phase, self._secondary,
                TickerEffect.WAVE_SCROLL, speed=0.025
            )

        elif self._sub_phase == FortunePhase.RESULT:
            # Show page type on ticker
            page_type = self._get_page_type(self._current_page)
            if page_type == "image":
                ticker_text = "ТВОЙ ПОРТРЕТ"
            elif page_type == "qr":
                ticker_text = "СКАЧАЙ ФОТО"
            else:
                text_total = max(1, len(self._text_pages))
                text_page = min(self._current_page + 1, text_total)
                ticker_text = f"СТРАНИЦА {text_page}/{text_total}"
            render_ticker_animated(
                buffer, ticker_text,
                self._time_in_phase, self._accent,
                TickerEffect.WAVE_SCROLL, speed=0.025
            )

        else:
            render_ticker_animated(
                buffer, "ГАДАТЕЛЬ",
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
            return f" * ФОТО: {countdown} * ".center(16)[:16]
        elif self._sub_phase == FortunePhase.PROCESSING:
            dots = "-\\|/"
            dot = dots[int(self._time_in_phase / 200) % 4]
            return f" {dot} ГАДАЮ {dot} ".center(16)[:16]
        elif self._sub_phase == FortunePhase.RESULT:
            page_type = self._get_page_type(self._current_page)
            if page_type == "image":
                return " * ПОРТРЕТ * ".center(16)[:16]
            elif page_type == "qr":
                return " * СКАЧАТЬ * ".center(16)[:16]
            else:
                text_total = max(1, len(self._text_pages))
                text_page = min(self._current_page + 1, text_total)
                return f" {text_page}/{text_total} ".center(16)[:16]
        return " * ГАДАТЕЛЬ * ".center(16)

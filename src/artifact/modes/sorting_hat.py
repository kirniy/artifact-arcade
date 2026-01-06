"""Sorting Hat mode - Harry Potter house sorting with photo + questions + AI portrait.

The Sorting Hat takes your photo, asks you 6 personality questions,
then magically sorts you into one of the four Hogwarts houses:
- Гриффиндор (Gryffindor) - Brave, daring, chivalrous
- Слизерин (Slytherin) - Ambitious, cunning, resourceful
- Когтевран (Ravenclaw) - Wise, creative, intellectual
- Пуффендуй (Hufflepuff) - Loyal, patient, hardworking

Features:
- Photo capture with magical effects
- 6 random questions from a bank of 30+ Sorting Hat style questions
- Golden Snitch mini-game while AI generates portrait
- Dramatic house reveal animation
- AI-generated portrait in Hogwarts robe with house colors
- Thermal receipt printing with house crest
- QR code for sharing
"""

import asyncio
import logging
import math
import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

from artifact.animation.easing import Easing
from artifact.animation.particles import ParticlePresets, ParticleSystem
from artifact.animation.snitch_catcher import SnitchCatcher
from artifact.animation.timeline import Timeline
from artifact.ai.caricature import CaricatureService, CaricatureStyle
from artifact.ai.client import get_gemini_client
from artifact.audio.engine import get_audio_engine
from artifact.core.events import Event, EventType
from artifact.graphics.progress import ProgressPhase, SmartProgressTracker
from artifact.modes.base import BaseMode, ModeContext, ModePhase, ModeResult
from artifact.utils.camera import create_viewfinder_overlay
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult

logger = logging.getLogger(__name__)


# =============================================================================
# HOGWARTS HOUSES
# =============================================================================

class HogwartsHouse(Enum):
    """The four Hogwarts houses."""
    GRYFFINDOR = "gryffindor"
    SLYTHERIN = "slytherin"
    RAVENCLAW = "ravenclaw"
    HUFFLEPUFF = "hufflepuff"


@dataclass
class House:
    """House definition with Russian name and colors."""
    name_ru: str
    name_en: str
    primary_color: Tuple[int, int, int]
    secondary_color: Tuple[int, int, int]
    traits: List[str]
    animal: str
    animal_ru: str
    founder: str


HOUSES: Dict[HogwartsHouse, House] = {
    HogwartsHouse.GRYFFINDOR: House(
        name_ru="ГРИФФИНДОР",
        name_en="Gryffindor",
        primary_color=(174, 0, 1),      # Scarlet red
        secondary_color=(238, 186, 48),  # Gold
        traits=["храбрость", "отвага", "рыцарство", "решительность"],
        animal="Lion",
        animal_ru="Лев",
        founder="Годрик Гриффиндор",
    ),
    HogwartsHouse.SLYTHERIN: House(
        name_ru="СЛИЗЕРИН",
        name_en="Slytherin",
        primary_color=(26, 71, 42),      # Dark green
        secondary_color=(170, 170, 170),  # Silver
        traits=["амбиции", "хитрость", "находчивость", "лидерство"],
        animal="Serpent",
        animal_ru="Змея",
        founder="Салазар Слизерин",
    ),
    HogwartsHouse.RAVENCLAW: House(
        name_ru="КОГТЕВРАН",
        name_en="Ravenclaw",
        primary_color=(34, 47, 91),       # Dark blue
        secondary_color=(148, 107, 45),   # Bronze
        traits=["мудрость", "творчество", "интеллект", "оригинальность"],
        animal="Eagle",
        animal_ru="Орёл",
        founder="Кандида Когтевран",
    ),
    HogwartsHouse.HUFFLEPUFF: House(
        name_ru="ПУФФЕНДУЙ",
        name_en="Hufflepuff",
        primary_color=(255, 219, 0),      # Yellow
        secondary_color=(0, 0, 0),        # Black
        traits=["верность", "терпение", "трудолюбие", "справедливость"],
        animal="Badger",
        animal_ru="Барсук",
        founder="Пенелопа Пуффендуй",
    ),
}


# =============================================================================
# SORTING HAT QUESTIONS DATABASE
# Each question: (text_ru, trait_key, left_label, right_label, left_house_points, right_house_points)
# House points: Dict[HogwartsHouse, int] - points added for choosing that option
# =============================================================================

@dataclass
class SortingQuestion:
    """A Sorting Hat question."""
    text_ru: str
    left_label: str
    right_label: str
    left_points: Dict[HogwartsHouse, int]
    right_points: Dict[HogwartsHouse, int]
    category: str  # "dilemma", "scenario", "preference"


# Personality Dilemmas - moral/value choices
DILEMMA_QUESTIONS = [
    SortingQuestion(
        text_ru="Что важнее: слава или мудрость?",
        left_label="СЛАВА",
        right_label="МУДРОСТЬ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 1},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Что ценнее: власть или дружба?",
        left_label="ВЛАСТЬ",
        right_label="ДРУЖБА",
        left_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.GRYFFINDOR: 1},
        right_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.RAVENCLAW: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Лучше быть любимым или уважаемым?",
        left_label="ЛЮБИМЫМ",
        right_label="УВАЖАЕМЫМ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.GRYFFINDOR: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Победа или честная игра?",
        left_label="ПОБЕДА",
        right_label="ЧЕСТНОСТЬ",
        left_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.GRYFFINDOR: 1},
        right_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.RAVENCLAW: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Рискнуть или подождать?",
        left_label="РИСКНУТЬ",
        right_label="ПОДОЖДАТЬ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 1},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Следовать сердцу или разуму?",
        left_label="СЕРДЦУ",
        right_label="РАЗУМУ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.HUFFLEPUFF: 1},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.SLYTHERIN: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Быть лидером или советником?",
        left_label="ЛИДЕРОМ",
        right_label="СОВЕТНИКОМ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 2},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Простить или отомстить?",
        left_label="ПРОСТИТЬ",
        right_label="ОТОМСТИТЬ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.GRYFFINDOR: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Традиции или перемены?",
        left_label="ТРАДИЦИИ",
        right_label="ПЕРЕМЕНЫ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.SLYTHERIN: 1},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.GRYFFINDOR: 1},
        category="dilemma",
    ),
    SortingQuestion(
        text_ru="Правда или тактичность?",
        left_label="ПРАВДА",
        right_label="ТАКТИЧНОСТЬ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.RAVENCLAW: 1},
        right_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.SLYTHERIN: 1},
        category="dilemma",
    ),
]

# Situational Scenarios - what would you do
SCENARIO_QUESTIONS = [
    SortingQuestion(
        text_ru="Друг списывает. Что делаешь?",
        left_label="МОЛЧУ",
        right_label="ГОВОРЮ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.SLYTHERIN: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.RAVENCLAW: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Нашёл чужой кошелёк с деньгами.",
        left_label="ОТДАМ",
        right_label="ОСТАВЛЮ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.GRYFFINDOR: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Тебя несправедливо обвинили.",
        left_label="МОЛЧАТЬ",
        right_label="СПОРИТЬ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.RAVENCLAW: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Обижают слабого. Твои действия?",
        left_label="ВСТУПЛЮСЬ",
        right_label="ЗА ПОМОЩЬЮ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.HUFFLEPUFF: 1},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.SLYTHERIN: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Тебе предложили нечестную сделку.",
        left_label="ОТКАЖУСЬ",
        right_label="СОГЛАШУСЬ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.HUFFLEPUFF: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Тебя позвали на две вечеринки.",
        left_label="ОДНА",
        right_label="ОБЕ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.RAVENCLAW: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.GRYFFINDOR: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Нужно выступить публично.",
        left_label="ГОТОВЛЮСЬ",
        right_label="ЭКСПРОМТ",
        left_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.HUFFLEPUFF: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Кто-то раскрыл твой секрет.",
        left_label="ПРОСТИТЬ",
        right_label="ОТОМСТИТЬ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.GRYFFINDOR: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Предлагают возглавить проект.",
        left_label="ДА",
        right_label="НЕТ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 2},
        right_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.RAVENCLAW: 1},
        category="scenario",
    ),
    SortingQuestion(
        text_ru="Узнал секрет друга. Расскажешь?",
        left_label="НИКОМУ",
        right_label="БЛИЗКИМ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.SLYTHERIN: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 1, HogwartsHouse.RAVENCLAW: 1},
        category="scenario",
    ),
]

# Abstract Preferences - symbolic choices
PREFERENCE_QUESTIONS = [
    SortingQuestion(
        text_ru="Рассвет или закат?",
        left_label="РАССВЕТ",
        right_label="ЗАКАТ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.HUFFLEPUFF: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Лес или море?",
        left_label="ЛЕС",
        right_label="МОРЕ",
        left_points={HogwartsHouse.HUFFLEPUFF: 2, HogwartsHouse.RAVENCLAW: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Луна или солнце?",
        left_label="ЛУНА",
        right_label="СОЛНЦЕ",
        left_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.SLYTHERIN: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Огонь или вода?",
        left_label="ОГОНЬ",
        right_label="ВОДА",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 1},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Башня или подземелье?",
        left_label="БАШНЯ",
        right_label="ПОДЗЕМЕЛЬЕ",
        left_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.GRYFFINDOR: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Книга или меч?",
        left_label="КНИГА",
        right_label="МЕЧ",
        left_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.HUFFLEPUFF: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.SLYTHERIN: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Дракон или феникс?",
        left_label="ДРАКОН",
        right_label="ФЕНИКС",
        left_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Старая магия или новые заклинания?",
        left_label="СТАРАЯ",
        right_label="НОВЫЕ",
        left_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.HUFFLEPUFF: 1},
        right_points={HogwartsHouse.RAVENCLAW: 2, HogwartsHouse.GRYFFINDOR: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Чары или зелья?",
        left_label="ЧАРЫ",
        right_label="ЗЕЛЬЯ",
        left_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.RAVENCLAW: 1},
        right_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="preference",
    ),
    SortingQuestion(
        text_ru="Невидимость или полёт?",
        left_label="НЕВИДИМОСТЬ",
        right_label="ПОЛЁТ",
        left_points={HogwartsHouse.SLYTHERIN: 2, HogwartsHouse.RAVENCLAW: 1},
        right_points={HogwartsHouse.GRYFFINDOR: 2, HogwartsHouse.HUFFLEPUFF: 1},
        category="preference",
    ),
]

ALL_QUESTIONS = DILEMMA_QUESTIONS + SCENARIO_QUESTIONS + PREFERENCE_QUESTIONS
QUESTIONS_PER_SESSION = 6


def get_sorting_questions(count: int = QUESTIONS_PER_SESSION) -> List[SortingQuestion]:
    """Get random questions ensuring variety from all categories."""
    import os
    import time

    rng = random.Random()
    seed = int(time.time() * 1_000_000) ^ int.from_bytes(os.urandom(4), 'big')
    rng.seed(seed)

    # Get 2 from each category for variety
    dilemmas = rng.sample(DILEMMA_QUESTIONS, min(2, len(DILEMMA_QUESTIONS)))
    scenarios = rng.sample(SCENARIO_QUESTIONS, min(2, len(SCENARIO_QUESTIONS)))
    preferences = rng.sample(PREFERENCE_QUESTIONS, min(2, len(PREFERENCE_QUESTIONS)))

    questions = dilemmas + scenarios + preferences
    rng.shuffle(questions)

    return questions[:count]


# =============================================================================
# SORTING HAT SUB-PHASES
# =============================================================================

class SortingPhase:
    """Sub-phases within the Sorting Hat mode."""
    INTRO = "intro"              # Welcome animation with Sorting Hat
    CAMERA_PREP = "camera_prep"  # "Look at camera" prompt
    CAMERA_CAPTURE = "capture"   # Photo capture with countdown
    QUESTIONS = "questions"      # 6 binary questions
    PROCESSING = "processing"    # AI generation with Snitch game
    REVEAL = "reveal"            # Dramatic house reveal
    RESULT = "result"            # Show result with caricature


# =============================================================================
# SORTING HAT MODE
# =============================================================================

class SortingHatMode(BaseMode):
    """Sorting Hat - Hogwarts house sorting experience.

    Flow:
    1. INTRO: Sorting Hat welcomes you
    2. CAMERA_PREP: "Look at the camera" prompt
    3. CAMERA_CAPTURE: Take photo with magical countdown
    4. QUESTIONS: 6 binary questions (LEFT/RIGHT)
    5. PROCESSING: Golden Snitch mini-game while AI works
    6. REVEAL: Dramatic Sorting Hat announces house
    7. RESULT: Display house portrait with colors
    """

    name = "sorting_hat"
    display_name = "ШЛЯПА"
    description = "Распределение по факультетам"
    icon = "^"
    style = "magical"
    requires_camera = True
    requires_ai = True
    estimated_duration = 90

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._caricature_service = CaricatureService()
        self._gemini_client = get_gemini_client()
        self._audio = get_audio_engine()

        # Sub-phase tracking
        self._sub_phase = SortingPhase.INTRO

        # Camera state
        self._camera: bool = False
        self._camera_frame: Optional[np.ndarray] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._last_countdown_tick: int = 0
        self._flash_alpha: float = 0.0

        # Questions state
        self._questions: List[SortingQuestion] = []
        self._current_question: int = 0
        self._answers: List[bool] = []  # True = right, False = left
        self._house_scores: Dict[HogwartsHouse, int] = {h: 0 for h in HogwartsHouse}
        self._answer_animation: float = 0.0

        # AI results
        self._sorted_house: Optional[HogwartsHouse] = None
        self._caricature_data: Optional[bytes] = None
        self._ai_task: Optional[asyncio.Task] = None
        self._appearance_task: Optional[asyncio.Task] = None  # Async appearance analysis
        self._appearance_scores: Dict[HogwartsHouse, int] = {}  # Scores from appearance
        self._processing_progress: float = 0.0
        self._progress_tracker = SmartProgressTracker(mode_theme="sorting_hat")

        # Animation state
        self._reveal_progress: float = 0.0
        self._glow_phase: float = 0.0
        self._hat_bob: float = 0.0
        
        # Hat facial animation state
        self._mouth_open: float = 0.0  # 0.0 = closed, 1.0 = open
        self._eye_squint: float = 0.0  # 0.0 = wide, 1.0 = squinted
        self._brow_raise: float = 0.0  # 0.0 = normal, 1.0 = raised

        # Result view state
        self._current_page: int = 0
        self._total_pages: int = 3  # Portrait, House info, QR

        # Particles
        self._particles = ParticleSystem()

        # Colors (magical gold/purple theme)
        self._primary = (148, 107, 45)    # Bronze/gold
        self._secondary = (139, 92, 246)   # Purple
        self._accent = (255, 215, 0)       # Bright gold

        # S3 upload
        self._uploader = AsyncUploader()
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None
        self._short_url: Optional[str] = None

        # Snitch catcher minigame
        self._snitch_game: Optional[SnitchCatcher] = None

    @property
    def is_ai_available(self) -> bool:
        """Check if AI services are available."""
        return self._caricature_service.is_available

    def on_enter(self) -> None:
        """Initialize Sorting Hat mode."""
        self._sub_phase = SortingPhase.INTRO
        self._photo_data = None
        self._camera_frame = None
        self._current_question = 0
        self._answers = []
        self._house_scores = {h: 0 for h in HogwartsHouse}
        self._sorted_house = None
        self._caricature_data = None
        self._ai_task = None
        self._appearance_task = None
        self._appearance_scores = {}
        self._processing_progress = 0.0
        self._progress_tracker.reset()
        self._reveal_progress = 0.0

        # Reset pagination
        self._current_page = 0
        self._qr_url = None
        self._qr_image = None
        self._short_url = None

        # Camera setup
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera ready for Sorting Hat mode")
        else:
            logger.warning("Camera not available")

        # Get random questions
        self._questions = get_sorting_questions(QUESTIONS_PER_SESSION)
        logger.info(f"Selected {len(self._questions)} sorting questions")

        # Setup magical particles
        magic_config = ParticlePresets.magic(x=64, y=64)
        magic_config.color = self._accent
        self._particles.add_emitter("magic", magic_config)

        spark_config = ParticlePresets.sparkle(x=64, y=64)
        spark_config.color = self._secondary
        self._particles.add_emitter("sparks", spark_config)

        self.change_phase(ModePhase.INTRO)

        # Start Hedwig's Theme background music
        self._audio.play_sorting_hat_theme()

        logger.info("Sorting Hat mode entered")

    def on_update(self, delta_ms: float) -> None:
        """Update Sorting Hat mode."""
        self._particles.update(delta_ms)

        # Animation updates
        self._glow_phase += delta_ms * 0.003
        self._hat_bob = math.sin(self._time_in_phase / 500) * 3

        # Facial animations based on state
        target_mouth = 0.0
        target_squint = 0.0
        target_brow = 0.0

        if self._sub_phase == SortingPhase.INTRO:
            # Gentle bobbing, neutral face
            pass
        elif self._sub_phase == SortingPhase.QUESTIONS:
            # Listening intently
            target_brow = 0.3
        elif self._sub_phase == SortingPhase.PROCESSING:
            # Thinking deeply
            target_squint = 0.8
            target_brow = 1.0
            # Thinking mumble
            if math.sin(self._time_in_phase / 100) > 0.5:
                target_mouth = 0.2
        elif self._sub_phase == SortingPhase.REVEAL:
            # Talking/Announcing
            if self._reveal_progress < 0.5:
                # "Hmm..." phase
                target_squint = 0.5
                target_mouth = 0.3 + 0.2 * math.sin(self._time_in_phase / 80)  # Mumbling
            else:
                # "GRYFFINDOR!" phase
                target_mouth = 0.8 + 0.2 * math.sin(self._time_in_phase / 100)  # Shouting
                target_brow = 1.0
                target_squint = 0.0

        # Smooth transitions
        lerp = lambda start, end, t: start + (end - start) * t
        dt = delta_ms / 1000.0 * 5.0  # Transition speed
        
        self._mouth_open = lerp(self._mouth_open, target_mouth, dt)
        self._eye_squint = lerp(self._eye_squint, target_squint, dt)
        self._brow_raise = lerp(self._brow_raise, target_brow, dt)

        # Update camera preview during camera phases
        if self._sub_phase in (SortingPhase.CAMERA_PREP, SortingPhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            if self._sub_phase == SortingPhase.INTRO:
                if self._time_in_phase > 3000:
                    self._sub_phase = SortingPhase.CAMERA_PREP
                    self._time_in_phase = 0

            elif self._sub_phase == SortingPhase.CAMERA_PREP:
                if self._time_in_phase > 2500:
                    self._start_camera_capture()

            elif self._sub_phase == SortingPhase.CAMERA_CAPTURE:
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                # Countdown tick sounds
                current_tick = int(self._camera_countdown) + 1
                if current_tick != self._last_countdown_tick and 1 <= current_tick <= 3:
                    self._audio.play_countdown_tick()
                    self._last_countdown_tick = current_tick

                # Capture photo at countdown end
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._audio.play_camera_shutter()
                    self._flash_alpha = 1.0

                # Flash decay and transition
                if self._time_in_phase > 3000:
                    self._flash_alpha = max(0, 1.0 - (self._time_in_phase - 3000) / 500)
                    if self._time_in_phase > 3500:
                        self._start_questions()

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == SortingPhase.QUESTIONS:
                self._answer_animation = max(0, self._answer_animation - delta_ms / 300)

        elif self.phase == ModePhase.PROCESSING:
            self._progress_tracker.update(delta_ms)

            # Update Snitch game
            if self._snitch_game:
                self._snitch_game.update(delta_ms)

            # Check AI task
            if self._ai_task:
                if self._ai_task.done():
                    self._on_ai_complete()
                else:
                    self._processing_progress = self._progress_tracker.get_progress()

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == SortingPhase.REVEAL:
                self._reveal_progress = min(1.0, self._time_in_phase / 3000)
                if self._reveal_progress >= 1.0:
                    self._sub_phase = SortingPhase.RESULT
                    self._current_page = 0

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self._sub_phase == SortingPhase.PROCESSING:
                # Jump in Snitch game
                if self._snitch_game:
                    self._snitch_game.handle_jump()
                    self._audio.play_ui_click()
                return True
            elif self.phase == ModePhase.RESULT and self._sub_phase == SortingPhase.RESULT:
                self._finish()
                return True

        elif event.type in (EventType.ARCADE_LEFT, EventType.ARCADE_RIGHT):
            if self._sub_phase == SortingPhase.PROCESSING:
                # Move player in Snitch game
                if self._snitch_game:
                    if event.type == EventType.ARCADE_LEFT:
                        self._snitch_game.move_left()
                    else:
                        self._snitch_game.move_right()
                    # Also try to catch any nearby snitch
                    if self._snitch_game.handle_catch():
                        self._audio.play_success()
                return True

        if event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == SortingPhase.QUESTIONS:
                self._answer_question(False)  # Left option
                self._audio.play_ui_click()
                return True
            if self.phase == ModePhase.RESULT and self._sub_phase == SortingPhase.RESULT:
                if self._current_page > 0:
                    self._current_page -= 1
                    self._audio.play_ui_move()
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == SortingPhase.QUESTIONS:
                self._answer_question(True)  # Right option
                self._audio.play_ui_click()
                return True
            if self.phase == ModePhase.RESULT and self._sub_phase == SortingPhase.RESULT:
                if self._current_page < self._total_pages - 1:
                    self._current_page += 1
                    self._audio.play_ui_move()
                return True

        return False

    def _start_camera_capture(self) -> None:
        """Start camera capture sequence."""
        self._sub_phase = SortingPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0
        self._last_countdown_tick = 0
        logger.info("Camera capture started")

    def _do_camera_capture(self) -> None:
        """Capture photo."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            logger.info(f"Photo captured: {len(self._photo_data)} bytes")
            # Start appearance analysis in background
            self._appearance_task = asyncio.create_task(self._analyze_appearance())
        else:
            logger.warning("Photo capture failed")

    async def _analyze_appearance(self) -> None:
        """Analyze photo to determine house traits from appearance.

        Uses Gemini to look at the person's appearance and assign
        house points based on their vibe, style, and energy.
        """
        if not self._photo_data:
            return

        try:
            prompt = """Look at this person's photo and determine which Hogwarts house they LOOK like they belong to based on their appearance, style, expression, and overall vibe.

Consider:
- Gryffindor: Bold, confident stance, warm colors, adventurous look, brave expression
- Slytherin: Sharp features, cool demeanor, sophisticated style, ambitious eyes, cunning smile
- Ravenclaw: Thoughtful expression, intellectual look, quirky style, curious eyes, creative vibe
- Hufflepuff: Warm smile, friendly face, approachable look, loyal expression, cozy style

Respond with ONLY a JSON object with house scores from 0-3 based on how much their appearance matches each house:
{"gryffindor": X, "slytherin": X, "ravenclaw": X, "hufflepuff": X}"""

            response = await self._gemini_client.generate_with_image(
                prompt=prompt,
                image_data=self._photo_data,
                system_instruction="You are a Sorting Hat analyzing appearances. Return ONLY valid JSON."
            )

            if response:
                # Parse JSON response
                import json
                import re
                # Extract JSON from response
                json_match = re.search(r'\{[^}]+\}', response)
                if json_match:
                    scores = json.loads(json_match.group())
                    self._appearance_scores = {
                        HogwartsHouse.GRYFFINDOR: int(scores.get("gryffindor", 0)),
                        HogwartsHouse.SLYTHERIN: int(scores.get("slytherin", 0)),
                        HogwartsHouse.RAVENCLAW: int(scores.get("ravenclaw", 0)),
                        HogwartsHouse.HUFFLEPUFF: int(scores.get("hufflepuff", 0)),
                    }
                    logger.info(f"Appearance analysis: {self._appearance_scores}")

        except Exception as e:
            logger.warning(f"Appearance analysis failed: {e}")
            self._appearance_scores = {}

    def _update_camera_preview(self) -> None:
        """Update live camera preview."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.size > 0:
                # Convert to grayscale
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
                # Convert to RGB
                bw_frame = np.stack([gray, gray, gray], axis=-1)
                self._camera_frame = create_viewfinder_overlay(bw_frame, self._time_in_phase).copy()
                self._camera = True
        except Exception as e:
            logger.warning(f"Camera preview error: {e}")

    def _start_questions(self) -> None:
        """Start questions sequence."""
        self._sub_phase = SortingPhase.QUESTIONS
        self._current_question = 0
        self._answers = []
        self._house_scores = {h: 0 for h in HogwartsHouse}
        self.change_phase(ModePhase.ACTIVE)
        logger.info("Questions phase started")

    def _answer_question(self, answer: bool) -> None:
        """Record answer and update house scores."""
        if self._current_question >= len(self._questions):
            return

        q = self._questions[self._current_question]
        self._answers.append(answer)

        # Add house points based on answer
        points = q.right_points if answer else q.left_points
        for house, pts in points.items():
            self._house_scores[house] += pts

        label = q.right_label if answer else q.left_label
        logger.debug(f"Q: {q.text_ru} -> {label}")

        self._answer_animation = 1.0
        self._current_question += 1

        if self._current_question >= len(self._questions):
            self._determine_house()
            self._start_processing()
        else:
            logger.debug(f"Question {self._current_question}/{len(self._questions)}")

    def _determine_house(self) -> None:
        """Determine the sorted house based on question + appearance scores."""
        # Add appearance scores if available (from async analysis)
        if self._appearance_task and self._appearance_task.done():
            for house, pts in self._appearance_scores.items():
                self._house_scores[house] += pts
            logger.info(f"Added appearance scores: {self._appearance_scores}")

        logger.info(f"Final scores (questions + appearance): {self._house_scores}")

        # Find house(s) with max score
        max_score = max(self._house_scores.values())
        top_houses = [h for h, s in self._house_scores.items() if s == max_score]

        # If tie, randomly pick
        self._sorted_house = random.choice(top_houses)

        house = HOUSES[self._sorted_house]
        logger.info(f"Sorted into: {house.name_ru}")

    def _start_processing(self) -> None:
        """Start AI processing."""
        self._sub_phase = SortingPhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        # Initialize Snitch catcher game
        self._snitch_game = SnitchCatcher()
        self._snitch_game.reset()

        # Start AI task
        self._ai_task = asyncio.create_task(self._run_ai_generation())

        # Burst particles
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(50)

        logger.info("AI processing started")

    def _build_house_context(self) -> str:
        """Build context string for AI generation."""
        if not self._sorted_house:
            return ""

        house = HOUSES[self._sorted_house]
        traits = ", ".join(house.traits)

        return f"""Факультет: {house.name_ru} ({house.name_en})
Животное: {house.animal_ru}
Черты: {traits}
Основатель: {house.founder}"""

    async def _run_ai_generation(self) -> None:
        """Run AI generation for house portrait."""
        try:
            house = HOUSES[self._sorted_house] if self._sorted_house else HOUSES[HogwartsHouse.GRYFFINDOR]
            house_context = self._build_house_context()

            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            # Generate Hogwarts portrait with house uniform
            prompt = f"""Create a BLACK AND WHITE portrait of THIS EXACT PERSON from the reference photo as a Hogwarts student.

CRITICAL REQUIREMENTS:
- This must capture THE PERSON IN THE PHOTO - their likeness is essential
- They are wearing a Hogwarts school robe with {house.name_en} house colors
- House tie and crest clearly visible: {house.name_en} ({house.animal})
- Confident, proud expression - they just got sorted!
- BLACK AND WHITE ONLY - pure black ink on white background, high contrast
- NO colors, NO grayscale shading - thermal print style
- Slight caricature - emphasize distinctive features playfully

House Information:
{house_context}

Style: Harry Potter book illustration, magical ink drawing, detailed robes.
Add small magical sparkles or house animal silhouette in background.
Square aspect ratio. Make it feel like a magical yearbook photo!"""

            if self._photo_data:
                image_data = await self._gemini_client.generate_image(
                    prompt=prompt,
                    reference_photo=self._photo_data,
                    photo_mime_type="image/jpeg",
                    aspect_ratio="1:1",
                    image_size="1K",
                    style="Black and white ink illustration, Harry Potter style, magical portrait",
                )

                if image_data:
                    # Process for display
                    from io import BytesIO
                    from PIL import Image

                    img = Image.open(BytesIO(image_data))
                    img = img.convert("L").convert("RGB")
                    img.thumbnail((384, 384), Image.Resampling.LANCZOS)

                    output = BytesIO()
                    img.save(output, format="PNG", optimize=True)
                    self._caricature_data = output.getvalue()

                    self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

                    # Upload for QR
                    logger.info("Starting portrait upload for QR sharing")
                    self._uploader.upload_bytes(
                        self._caricature_data,
                        prefix="sorting_hat",
                        extension="png",
                        content_type="image/png",
                        callback=self._on_upload_complete,
                    )

            logger.info("AI generation complete")

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            self._caricature_data = None

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle S3 upload completion."""
        if result.success:
            self._qr_url = result.url
            self._qr_image = result.qr_image
            self._short_url = result.short_url
            logger.info(f"Portrait uploaded: {self._qr_url} (short: {self._short_url})")
        else:
            logger.error(f"Upload failed: {result.error}")

    def _on_ai_complete(self) -> None:
        """Handle AI completion."""
        self._processing_progress = 1.0
        self._progress_tracker.complete()

        # Transition to reveal
        self._sub_phase = SortingPhase.REVEAL
        self.change_phase(ModePhase.RESULT)
        self._reveal_progress = 0.0
        self._time_in_phase = 0

        # Stop Hedwig's Theme and play house-specific reveal sound
        self._audio.stop_music(fade_out_ms=200)

        if self._sorted_house:
            self._audio.play_sorting_house_reveal(self._sorted_house.value)
        else:
            self._audio.play_success()

        logger.info("AI complete, starting reveal")

    def on_exit(self) -> None:
        """Cleanup."""
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

        # Stop Hedwig's Theme
        self._audio.stop_music(fade_out_ms=500)

        self._camera = False
        self._camera_frame = None
        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        house = HOUSES.get(self._sorted_house, HOUSES[HogwartsHouse.GRYFFINDOR])

        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=house.name_ru,
            ticker_text=f"{house.name_ru} - {house.animal_ru}",
            lcd_text=house.name_ru.center(16)[:16],
            should_print=True,
            skip_manager_result=True,  # Sorting Hat handles its own result display
            print_data={
                "house": self._sorted_house.value if self._sorted_house else "gryffindor",
                "house_name_ru": house.name_ru,
                "house_name_en": house.name_en,
                "traits": house.traits,
                "animal_ru": house.animal_ru,
                "caricature": self._caricature_data,
                "qr_url": self._qr_url,
                "qr_image": self._qr_image,
                "short_url": self._short_url,
                "scores": {h.value: s for h, s in self._house_scores.items()},
                "timestamp": datetime.now().isoformat(),
                "type": "sorting_hat",
            },
        )
        self.complete(result)

    # =========================================================================
    # RENDERING
    # =========================================================================

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.fonts import draw_text_bitmap, load_font
        from artifact.graphics.primitives import draw_circle, draw_rect, fill

        # Dark magical background
        fill(buffer, (10, 5, 20))

        font = load_font("cyrillic")

        if self._sub_phase == SortingPhase.INTRO:
            self._render_intro(buffer, font)
        elif self._sub_phase == SortingPhase.CAMERA_PREP:
            self._render_camera_prep(buffer, font)
        elif self._sub_phase == SortingPhase.CAMERA_CAPTURE:
            self._render_camera_capture(buffer, font)
        elif self._sub_phase == SortingPhase.QUESTIONS:
            self._render_questions(buffer, font)
        elif self._sub_phase == SortingPhase.PROCESSING:
            self._render_processing(buffer, font)
        elif self._sub_phase == SortingPhase.REVEAL:
            self._render_reveal(buffer, font)
        elif self._sub_phase == SortingPhase.RESULT:
            self._render_result(buffer, font)

        # Particles on top
        self._particles.render(buffer)

        # Flash effect
        if self._flash_alpha > 0:
            alpha = int(255 * self._flash_alpha)
            fill(buffer, (alpha, alpha, alpha))

    def _render_intro(self, buffer, font) -> None:
        """Render intro with Sorting Hat."""
        from artifact.graphics.text_utils import draw_centered_text

        # Animated glow
        pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)

        # Draw Sorting Hat (simplified pixel art)
        hat_y = 20 + int(self._hat_bob)
        self._draw_sorting_hat(buffer, 64, hat_y, pulse)

        # Title
        draw_centered_text(buffer, "РАСПРЕДЕЛЯЮЩАЯ", 85, self._accent, scale=1)
        draw_centered_text(buffer, "ШЛЯПА", 98, self._accent, scale=2)

        # Subtitle
        draw_centered_text(buffer, "Узнай свой факультет", 118, (100, 100, 120), scale=1)

    def _draw_sorting_hat(self, buffer, cx: int, cy: int, pulse: float) -> None:
        """Draw a complex, expressive Sorting Hat using primitives."""
        from artifact.graphics.primitives import draw_circle, draw_line, draw_rect
        
        # Colors adjusted by pulse
        base_brown = tuple(int(c * pulse) for c in (100, 70, 40))
        dark_brown = tuple(int(c * pulse) for c in (60, 40, 20))
        shadow = tuple(int(c * pulse) for c in (40, 25, 10))
        highlight = tuple(int(c * pulse) for c in (130, 90, 50))
        
        # 1. BRIM - Wide irregular ellipse
        # Draw as multiple overlapping circles/rects
        for i in range(3):
            w = 50 - i * 2
            h = 10 - i
            y = cy + 40 - i
            # Draw ellipse manually
            for ex in range(-w, w + 1):
                for ey in range(-h, h + 1):
                    if (ex/w)**2 + (ey/h)**2 <= 1.0:
                        px, py = cx + ex, y + ey
                        if 0 <= px < 128 and 0 <= py < 128:
                             if abs(ex) > w - 4 or abs(ey) > h - 2:
                                 buffer[py, px] = shadow
                             else:
                                 buffer[py, px] = base_brown

        # 2. BASE OF CONE (The Face Area)
        # Main bulk
        for y in range(cy + 10, cy + 35):
            width = 25 - (y - (cy + 10)) * 0.4
            x_off = int(math.sin(y / 5) * 2) # Irregularity
            
            for x in range(int(-width), int(width)):
                px = cx + x + x_off
                py = y
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = base_brown
                    
                    # shading sides
                    if x < -width + 4: buffer[py, px] = shadow
                    if x > width - 4: buffer[py, px] = highlight

        # 3. CONE TIP (Bent)
        # Draw as stacked circles moving sideways
        tip_x = cx
        for i in range(30):
            y = cy + 10 - i
            radius = max(2, 18 - i * 0.6)
            
            # Bend the hat tip to the right
            bend = int((i * i) / 40)
            center_x = cx + bend
            
            draw_circle(buffer, center_x, y, int(radius), base_brown)
            # Add fold lines
            if i % 8 == 0:
                draw_line(buffer, center_x - int(radius), y, center_x + int(radius), y + 1, shadow)

        # 4. FACE FEATURES
        
        # Eyes (Cavities formed by folds)
        eye_y = cy + 15
        eye_spacing = 9
        
        # Left Eye
        left_eye_h = int(4 * (1.0 - self._eye_squint))
        draw_line(buffer, cx - eye_spacing - 6, eye_y - 2, cx - eye_spacing + 2, eye_y, shadow, thickness=2) # Brow
        draw_rect(buffer, cx - eye_spacing - 4, eye_y, 6, max(1, left_eye_h), (20, 10, 5)) # Cavity
        
        # Right Eye
        right_eye_h = int(4 * (1.0 - self._eye_squint))
        draw_line(buffer, cx + eye_spacing - 2, eye_y, cx + eye_spacing + 6, eye_y - 2, shadow, thickness=2)
        draw_rect(buffer, cx + eye_spacing - 2, eye_y, 6, max(1, right_eye_h), (20, 10, 5))

        # Brow raise (move brows up)
        brow_off = int(self._brow_raise * 3)
        if brow_off > 0:
             draw_line(buffer, cx - eye_spacing - 6, eye_y - 4 - brow_off, cx - eye_spacing + 2, eye_y - 2 - brow_off, shadow, thickness=1)
             draw_line(buffer, cx + eye_spacing - 2, eye_y - 2 - brow_off, cx + eye_spacing + 6, eye_y - 4 - brow_off, shadow, thickness=1)

        # Mouth (A fold that opens)
        mouth_y = cy + 28
        mouth_w = 16
        open_h = int(self._mouth_open * 8)
        
        # Upper lip fold
        draw_line(buffer, cx - mouth_w//2, mouth_y - 1 - open_h//2, cx + mouth_w//2, mouth_y - 1 - open_h//2, shadow, thickness=2)
        
        # Mouth interior (visible only when open)
        if open_h > 0:
            draw_rect(buffer, cx - mouth_w//2 + 2, mouth_y - open_h//2, mouth_w - 4, open_h, (10, 5, 0))
            
        # Lower lip fold
        draw_line(buffer, cx - mouth_w//2 + 1, mouth_y + 1 + open_h//2, cx + mouth_w//2 - 1, mouth_y + 1 + open_h//2, shadow, thickness=2)

    def _render_camera_prep(self, buffer, font) -> None:
        """Render camera prep screen."""
        from artifact.graphics.text_utils import draw_centered_text

        # Show camera preview
        if self._camera_frame is not None:
            np.copyto(buffer, self._camera_frame)

        draw_centered_text(buffer, "СМОТРИ В КАМЕРУ", 100, self._accent, scale=1)
        draw_centered_text(buffer, "ШЛЯПА ГОТОВА...", 112, (255, 200, 100), scale=1)

    def _render_camera_capture(self, buffer, font) -> None:
        """Render camera capture with countdown."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        # Camera preview
        if self._camera_frame is not None:
            np.copyto(buffer, self._camera_frame)

        # Countdown
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
                draw_circle(buffer, px, py, 2, self._accent)

        # Flash effect
        if self._flash_alpha > 0:
            buffer[:, :] = np.clip(
                buffer.astype(np.int16) + int(255 * self._flash_alpha),
                0, 255
            ).astype(np.uint8)
            draw_centered_text(buffer, "ФОТО!", 60, (50, 50, 50), scale=2)

    def _render_questions(self, buffer, font) -> None:
        """Render question screen with B/W camera background."""
        from artifact.graphics.fonts import draw_text_bitmap
        from artifact.graphics.primitives import draw_rect, fill
        from artifact.graphics.text_utils import (
            MAIN_DISPLAY_WIDTH,
            TextEffect,
            draw_animated_text,
            draw_centered_text,
            smart_wrap_text,
        )

        if self._current_question >= len(self._questions):
            return

        # Get camera frame as background
        camera_bg = camera_service.get_frame(timeout=0)
        if camera_bg is not None:
            # Resize to 128x128
            from PIL import Image
            img = Image.fromarray(camera_bg)
            img = img.resize((128, 128), Image.Resampling.LANCZOS)
            frame = np.array(img)

            # Convert to grayscale
            gray = (0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1] + 0.114 * frame[:, :, 2]).astype(np.uint8)

            # Apply dark tint (reduce brightness) for contrast with UI
            gray = (gray * 0.25).astype(np.uint8)

            # Set as background (grayscale to RGB)
            buffer[:, :, 0] = gray
            buffer[:, :, 1] = gray
            buffer[:, :, 2] = gray
        else:
            # Dark fallback if no camera
            fill(buffer, (10, 10, 15))

        q = self._questions[self._current_question]

        # Question number
        q_num = f"{self._current_question + 1}/{len(self._questions)}"
        draw_animated_text(buffer, q_num, 2, self._accent, self._time_in_phase, TextEffect.GLOW, scale=1)

        # Question text
        margin = 4
        available_width = MAIN_DISPLAY_WIDTH - margin * 2
        lines_s2 = smart_wrap_text(q.text_ru, available_width, font, scale=2)

        if len(lines_s2) <= 4:
            lines = lines_s2
            scale = 2
            line_height = 16
            start_y = 14
        else:
            lines = smart_wrap_text(q.text_ru, available_width, font, scale=1)
            scale = 1
            line_height = 10
            start_y = 14

        y = start_y
        max_lines = 4 if scale == 2 else 6
        for i, line in enumerate(lines[:max_lines]):
            pulse = 0.85 + 0.15 * math.sin(self._time_in_phase / 300 + i * 0.3)
            color = tuple(int(255 * pulse) for _ in range(3))
            draw_centered_text(buffer, line, y, color, scale=scale)
            y += line_height

        # Answer buttons - stacked vertically to prevent overlap
        btn_w = 120  # Full width
        btn_h = 14
        btn_x = 4

        # Truncate labels to max 14 chars for display (fits 120px button with arrows)
        def truncate_label(label: str, max_len: int = 14) -> str:
            return label[:max_len] if len(label) > max_len else label

        left_label = truncate_label(q.left_label)
        right_label = truncate_label(q.right_label)

        left_active = self._answer_animation > 0 and len(self._answers) > 0 and not self._answers[-1]
        right_active = self._answer_animation > 0 and len(self._answers) > 0 and self._answers[-1]

        left_pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 200) if left_active else 1.0
        right_pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 200) if right_active else 1.0

        def _clamp_color(values, pulse):
            return tuple(min(255, int(c * pulse)) for c in values)

        left_color = _clamp_color((174, 0, 1) if left_active else (80, 40, 40), left_pulse)
        right_color = _clamp_color((26, 71, 42) if right_active else (40, 60, 40), right_pulse)

        # Left button (top)
        left_btn_y = 86
        draw_rect(buffer, btn_x, left_btn_y, btn_w, btn_h, left_color)

        # Right button (bottom)
        right_btn_y = 102
        draw_rect(buffer, btn_x, right_btn_y, btn_w, btn_h, right_color)

        # Button labels - centered with arrows
        left_text = f"<  {left_label}"
        left_w, _ = font.measure_text(left_text)
        left_x = btn_x + (btn_w - left_w) // 2
        left_text_pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)
        left_text_color = tuple(int(255 * left_text_pulse) for _ in range(3))
        draw_text_bitmap(buffer, left_text, left_x, left_btn_y + 3, left_text_color, font, scale=1)

        right_text = f"{right_label}  >"
        right_w, _ = font.measure_text(right_text)
        right_x = btn_x + (btn_w - right_w) // 2
        right_text_pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300 + math.pi)
        right_text_color = tuple(int(255 * right_text_pulse) for _ in range(3))
        draw_text_bitmap(buffer, right_text, right_x, right_btn_y + 3, right_text_color, font, scale=1)

    def _render_processing(self, buffer, font) -> None:
        """Render Snitch catcher game while AI works."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text

        # Get camera background
        camera_bg = camera_service.get_frame(timeout=0)

        # Render Snitch game
        if self._snitch_game:
            self._snitch_game.render(buffer, background=camera_bg)

            # Progress bar at top
            bar_w, bar_h = 100, 4
            bar_x = (128 - bar_w) // 2
            bar_y = 2

            draw_rect(buffer, bar_x - 2, bar_y - 1, bar_w + 4, bar_h + 2, (20, 20, 40))
            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=self._accent,
                bg_color=(40, 40, 60),
                time_ms=self._time_in_phase,
            )

            # Status at bottom
            status = self._progress_tracker.get_message()
            draw_rect(buffer, 0, 118, 128, 10, (20, 20, 40))
            draw_centered_text(buffer, status, 119, (150, 150, 170), scale=1)

    def _render_reveal(self, buffer, font) -> None:
        """Render dramatic house reveal."""
        from artifact.graphics.primitives import draw_circle, fill
        from artifact.graphics.text_utils import draw_centered_text

        if not self._sorted_house:
            return

        house = HOUSES[self._sorted_house]

        # Background fades to house color
        t = Easing.ease_out(self._reveal_progress)

        # Dark to house color
        bg_r = int(10 + (house.primary_color[0] * 0.3 - 10) * t)
        bg_g = int(5 + (house.primary_color[1] * 0.3 - 5) * t)
        bg_b = int(20 + (house.primary_color[2] * 0.3 - 20) * t)
        fill(buffer, (bg_r, bg_g, bg_b))

        # Hat speaks first half
        if self._reveal_progress < 0.5:
            hat_y = 20 + int(self._hat_bob)
            pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 150)
            self._draw_sorting_hat(buffer, 64, hat_y, pulse)

            # "Хмм..." thinking text - visible from start
            think_alpha = max(0.3, min(1.0, self._reveal_progress * 4))  # Min 0.3 so always visible
            think_color = tuple(int(200 * think_alpha) for _ in range(3))
            draw_centered_text(buffer, "Хмм...", 90, think_color, scale=2)
            draw_centered_text(buffer, "Вижу в тебе...", 108, (120, 120, 140), scale=1)
        else:
            # House reveal!
            reveal_t = (self._reveal_progress - 0.5) * 2
            reveal_t = Easing.ease_out(reveal_t)

            # House name grows in
            scale = 1 + int(reveal_t * 1.5)
            name_alpha = min(1.0, reveal_t * 2)
            name_color = tuple(int(c * name_alpha) for c in house.secondary_color)

            draw_centered_text(buffer, house.name_ru, 50 + int((1 - reveal_t) * 20), name_color, scale=scale)

            # House animal
            if reveal_t > 0.3:
                animal_alpha = min(1.0, (reveal_t - 0.3) * 3)
                animal_color = tuple(int(c * animal_alpha) for c in house.primary_color)
                draw_centered_text(buffer, house.animal_ru, 90, animal_color, scale=2)

            # Sparkle ring
            for i in range(12):
                angle = i * 30 + self._time_in_phase / 10
                rad = math.radians(angle)
                dist = 45 * reveal_t
                px = int(64 + dist * math.cos(rad))
                py = int(64 + dist * math.sin(rad))
                if 0 <= px < 128 and 0 <= py < 128:
                    draw_circle(buffer, px, py, 2, house.secondary_color)

    def _render_result(self, buffer, font) -> None:
        """Render result pages."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        if self._current_page == 0:
            self._render_portrait_page(buffer, font)
        elif self._current_page == 1:
            self._render_house_info_page(buffer, font)
        else:
            self._render_qr_page(buffer, font)

    def _render_portrait_page(self, buffer, font) -> None:
        """Render the portrait/caricature page with house colors."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text
        from io import BytesIO

        if not self._sorted_house:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "ОШИБКА", 60, (255, 100, 100), scale=2)
            return

        house = HOUSES[self._sorted_house]

        # House color background
        fill(buffer, tuple(int(c * 0.3) for c in house.primary_color))

        if self._caricature_data:
            try:
                from PIL import Image

                img = Image.open(BytesIO(self._caricature_data))
                img = img.convert("RGB")

                # Display size (leave room for house name)
                display_size = 90
                img = img.resize((display_size, display_size), Image.Resampling.LANCZOS)

                x_offset = (128 - display_size) // 2
                y_offset = 2

                img_array = np.array(img, dtype=np.uint8)
                buffer[y_offset:y_offset + display_size, x_offset:x_offset + display_size] = img_array

            except Exception as e:
                logger.warning(f"Portrait render failed: {e}")
                draw_centered_text(buffer, "ПОРТРЕТ", 40, (255, 255, 255), scale=2)

        # House name at bottom
        draw_centered_text(buffer, house.name_ru, 100, house.secondary_color, scale=2)

        # Navigation hint
        self._render_nav_hint(buffer, font)

    def _render_house_info_page(self, buffer, font) -> None:
        """Render house information page."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        if not self._sorted_house:
            return

        house = HOUSES[self._sorted_house]

        # House color background
        fill(buffer, tuple(int(c * 0.2) for c in house.primary_color))

        # House name
        draw_centered_text(buffer, house.name_ru, 5, house.secondary_color, scale=2)

        # Animal
        draw_centered_text(buffer, house.animal_ru, 25, house.primary_color, scale=2)

        # Traits (use "-" instead of "•" which isn't in font)
        y = 45
        for trait in house.traits[:4]:
            draw_centered_text(buffer, f"- {trait}", y, (200, 200, 200), scale=1)
            y += 11

        # Bracelet message instead of founder
        draw_centered_text(buffer, "ПОЛУЧИ СВОЙ", 95, (255, 215, 0), scale=1)
        draw_centered_text(buffer, "БРАСЛЕТ!", 107, (255, 215, 0), scale=1)

        self._render_nav_hint(buffer, font)

    def _render_qr_page(self, buffer, font) -> None:
        """Render QR code page."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        if self._qr_image is not None:
            fill(buffer, (255, 255, 255))

            qr_h, qr_w = self._qr_image.shape[:2]
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

    def _render_nav_hint(self, buffer, font) -> None:
        """Render navigation hint."""
        from artifact.graphics.text_utils import draw_centered_text

        left = "<" if self._current_page > 0 else " "
        right = ">" if self._current_page < self._total_pages - 1 else " "
        page = f"{self._current_page + 1}/{self._total_pages}"

        hint = f"{left} {page} {right} ПЕЧАТЬ"
        draw_centered_text(buffer, hint, 118, (100, 150, 200), scale=1)

    def render_ticker(self, buffer) -> None:
        """Render Harry Potter themed ticker display with beautiful visual animations.

        No scrolling text - pure visual effects:
        - Magical golden waves
        - House-colored gradients
        - Sparkling particles
        - Animated progress bars
        """
        import numpy as np
        from artifact.graphics.primitives import clear

        clear(buffer)
        t = self._time_in_phase
        h, w = buffer.shape[:2]  # 8x48

        # --- VISUAL ANIMATION HELPERS ---

        def render_magical_wave(buf, time, base_color, secondary_color):
            """Render beautiful animated golden magical wave."""
            for x in range(w):
                for y in range(h):
                    # Multi-layer wave animation
                    wave1 = math.sin(x * 0.15 + time / 200 + y * 0.4) * 0.3 + 0.7
                    wave2 = math.sin(x * 0.25 - time / 150 + y * 0.3) * 0.2 + 0.8
                    combined = wave1 * wave2

                    # Gradient blend between colors
                    grad = x / w
                    r = int((base_color[0] * (1 - grad) + secondary_color[0] * grad) * combined)
                    g = int((base_color[1] * (1 - grad) + secondary_color[1] * grad) * combined)
                    b = int((base_color[2] * (1 - grad) + secondary_color[2] * grad) * combined)

                    buf[y, x] = (min(255, r), min(255, g), min(255, b))

        def render_golden_magic(buf, time):
            """Render golden magical shimmer effect."""
            gold = (255, 200, 50)
            amber = (200, 140, 20)

            for x in range(w):
                for y in range(h):
                    # Magical shimmer
                    wave = math.sin(x * 0.2 + time / 150 + y * 0.5) * 0.3 + 0.7
                    sparkle = math.sin(x * 0.6 + time / 80 - y * 0.8)

                    grad = x / w
                    r = int((gold[0] * (1 - grad) + amber[0] * grad) * wave)
                    g = int((gold[1] * (1 - grad) + amber[1] * grad) * wave)
                    b = int((gold[2] * (1 - grad) + amber[2] * grad) * wave)

                    # Add sparkle highlights
                    if sparkle > 0.85:
                        r = min(255, r + 100)
                        g = min(255, g + 100)
                        b = min(255, b + 60)

                    buf[y, x] = (r, g, b)

            # Floating particles
            for i in range(5):
                px = int((math.sin(time / 300 + i * 1.5) * 0.4 + 0.5) * w)
                py = int((math.sin(time / 250 + i * 2.1) * 0.4 + 0.5) * h)
                if 0 <= px < w and 0 <= py < h:
                    buf[py, px] = (255, 255, 200)

        def render_camera_pulse(buf, time):
            """Render pulsing camera ready effect."""
            pulse = math.sin(time / 200) * 0.3 + 0.7

            for x in range(w):
                for y in range(h):
                    # Cyan/white pulse from center
                    center_x = w // 2
                    dist = abs(x - center_x) / (w // 2)
                    intensity = (1 - dist) * pulse

                    r = int(100 * intensity)
                    g = int(220 * intensity)
                    b = int(255 * intensity)

                    # Add scan line effect
                    scan_pos = int((time / 50) % h)
                    if y == scan_pos:
                        r = min(255, r + 100)
                        g = min(255, g + 50)
                        b = min(255, b + 50)

                    buf[y, x] = (r, g, b)

        def render_question_bar(buf, time, question_num, total):
            """Render question progress bar with magical style."""
            progress = question_num / total

            for x in range(w):
                for y in range(h):
                    bar_progress = x / w
                    if bar_progress <= progress:
                        # Filled - golden gradient with wave
                        wave = math.sin(x * 0.3 + time / 100 + y * 0.4) * 0.2 + 0.8
                        grad = x / max(int(progress * w), 1)
                        r = int((180 + 75 * grad) * wave)
                        g = int((130 + 60 * grad) * wave)
                        b = int(40 * wave)

                        # Bright leading edge
                        if x >= int(progress * w) - 3:
                            edge = 1 - (int(progress * w) - 1 - x) / 3
                            r = min(255, int(r + 75 * edge))
                            g = min(255, int(g + 75 * edge))
                            b = min(255, int(b + 40 * edge))

                        buf[y, x] = (r, g, b)
                    else:
                        # Unfilled - dark with subtle shimmer
                        shimmer = math.sin(x * 0.5 + time / 200 + y * 0.6) * 0.5 + 0.5
                        if shimmer > 0.9:
                            buf[y, x] = (30, 25, 15)
                        else:
                            buf[y, x] = (15, 12, 8)

        def render_processing_magic(buf, time, progress):
            """Render processing animation with Snitch-inspired colors."""
            for x in range(w):
                for y in range(h):
                    bar_pos = x / w
                    if bar_pos <= progress:
                        # Filled - golden with wave
                        wave = math.sin(x * 0.2 + time / 80 + y * 0.3) * 0.25 + 0.75
                        grad = x / max(int(progress * w), 1)
                        r = int((200 + 55 * grad) * wave)
                        g = int((160 + 55 * grad) * wave)
                        b = int((20 + 30 * grad) * wave)

                        # Bright leading edge
                        if x >= int(progress * w) - 4:
                            edge = 1 - (int(progress * w) - 1 - x) / 4
                            r = min(255, int(r + 55 * edge))
                            g = min(255, int(g + 55 * edge))
                            b = min(255, int(b + 30 * edge))

                        buf[y, x] = (r, g, b)
                    else:
                        # Unfilled - dark amber background
                        shimmer = math.sin(x * 0.4 + time / 150 + y * 0.5) * 0.5 + 0.5
                        if shimmer > 0.92:
                            buf[y, x] = (40, 30, 10)
                        else:
                            buf[y, x] = (20, 15, 5)

            # Golden snitch particles
            for i in range(4):
                if progress > 0.1:
                    px = int((math.sin(time / 200 + i * 1.7) * 0.4 + 0.5) * progress * w)
                    py = int((math.sin(time / 170 + i * 2.5) * 0.5 + 0.5) * (h - 1))
                    if 0 <= px < w and 0 <= py < h:
                        buf[py, px] = (255, 230, 100)

        def render_reveal_magic(buf, time):
            """Render dramatic reveal animation."""
            pulse = math.sin(time / 100) * 0.3 + 0.7

            for x in range(w):
                for y in range(h):
                    # Intense magical pulse
                    wave = math.sin(x * 0.25 + time / 80 + y * 0.5) * 0.3 + 0.7
                    center_pulse = math.sin(time / 150) * 0.3 + 0.7

                    r = int(200 * wave * center_pulse)
                    g = int(150 * wave * center_pulse)
                    b = int(50 * wave * center_pulse)

                    # Sparkle explosions
                    sparkle = math.sin(x * 0.8 + time / 50 - y * 1.2)
                    if sparkle > 0.88:
                        r = min(255, r + 150)
                        g = min(255, g + 130)
                        b = min(255, b + 80)

                    buf[y, x] = (r, g, b)

        def render_house_celebration(buf, time, house):
            """Render house-colored celebration animation."""
            house_data = HOUSES[house]
            primary = house_data.primary_color
            secondary = house_data.secondary_color

            for x in range(w):
                for y in range(h):
                    # Wave animation with house colors
                    wave1 = math.sin(x * 0.2 + time / 120 + y * 0.4) * 0.3 + 0.7
                    wave2 = math.sin(x * 0.15 - time / 180 + y * 0.3) * 0.2 + 0.8

                    # Alternate between primary and secondary
                    blend = (math.sin(x * 0.3 + time / 200) + 1) / 2
                    r = int((primary[0] * blend + secondary[0] * (1 - blend)) * wave1 * wave2)
                    g = int((primary[1] * blend + secondary[1] * (1 - blend)) * wave1 * wave2)
                    b = int((primary[2] * blend + secondary[2] * (1 - blend)) * wave1 * wave2)

                    buf[y, x] = (min(255, r), min(255, g), min(255, b))

            # Sparkle particles in secondary color
            for i in range(6):
                px = int((math.sin(time / 180 + i * 1.3) * 0.45 + 0.5) * w)
                py = int((math.sin(time / 220 + i * 2.7) * 0.45 + 0.5) * h)
                if 0 <= px < w and 0 <= py < h:
                    buf[py, px] = (min(255, secondary[0] + 100),
                                   min(255, secondary[1] + 100),
                                   min(255, secondary[2] + 100))

        # --- PHASE-SPECIFIC RENDERING ---

        if self._sub_phase == SortingPhase.INTRO:
            render_golden_magic(buffer, t)

        elif self._sub_phase in (SortingPhase.CAMERA_PREP, SortingPhase.CAMERA_CAPTURE):
            render_camera_pulse(buffer, t)

        elif self._sub_phase == SortingPhase.QUESTIONS:
            q_num = self._current_question + 1
            total = len(self._questions)
            render_question_bar(buffer, t, q_num, total)

        elif self._sub_phase == SortingPhase.PROCESSING:
            progress = self._progress_tracker.get_progress()
            render_processing_magic(buffer, t, progress)

        elif self._sub_phase == SortingPhase.REVEAL and self._sorted_house:
            # Show house colors during reveal - dramatic moment!
            render_house_celebration(buffer, t, self._sorted_house)

        elif self._sub_phase == SortingPhase.RESULT and self._sorted_house:
            render_house_celebration(buffer, t, self._sorted_house)

        else:
            # Default - golden magic
            render_golden_magic(buffer, t)

    def get_lcd_text(self) -> str:
        """Get LCD text.

        Uses ONLY Latin/ASCII characters - no Cyrillic!
        The LCD has only 8 CGRAM slots which are needed for
        custom symbols, not Cyrillic letters.
        """
        if self._sub_phase == SortingPhase.CAMERA_PREP:
            # Blinking eye effect
            frame = int(self._time_in_phase / 300) % 2
            eye = "O" if frame == 0 else "o"
            return f" {eye} LOOK HERE {eye} ".center(16)[:16]
        elif self._sub_phase == SortingPhase.CAMERA_CAPTURE:
            countdown = int(self._camera_countdown) + 1
            return f"  * PHOTO: {countdown} *  ".center(16)[:16]
        elif self._sub_phase == SortingPhase.QUESTIONS:
            return "< / > CHOOSE".center(16)[:16]
        elif self._sub_phase == SortingPhase.PROCESSING:
            # Rotating ASCII animation
            dots = "-\\|/"
            dot = dots[int(self._time_in_phase / 150) % 4]
            return f" {dot} SORTING {dot} ".center(16)[:16]
        elif self._sub_phase == SortingPhase.REVEAL:
            return "* DECIDING... *".center(16)[:16]
        elif self._sub_phase == SortingPhase.RESULT and self._sorted_house:
            # House names in English for LCD
            house_names_en = {
                HogwartsHouse.GRYFFINDOR: "GRYFFINDOR",
                HogwartsHouse.SLYTHERIN: "SLYTHERIN",
                HogwartsHouse.RAVENCLAW: "RAVENCLAW",
                HogwartsHouse.HUFFLEPUFF: "HUFFLEPUFF",
            }
            return house_names_en[self._sorted_house].center(16)[:16]
        return "# SORTING HAT #".center(16)[:16]

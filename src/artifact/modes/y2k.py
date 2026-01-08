"""Y2K Mode - 2000s Nostalgia Trivia with AI Character Portrait.

Take a photo, answer trivia about the 2000s era (Russian and international),
and get transformed into a 2000s character based on your personality.
"""

from typing import List, Tuple, Optional, Dict, Any
import random
import math
import asyncio
import logging
from dataclasses import dataclass
from enum import Enum

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.utils.camera import create_viewfinder_overlay
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult
from artifact.audio.engine import get_audio_engine
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# QUESTION DATABASE - 2000s TRIVIA (Russian and International)
# Format: (question, [option_A, option_B, option_C, option_D], correct_index 0-3, trait_tags)
# trait_tags: list of personality traits this question reveals based on knowledge
# =============================================================================

@dataclass
class Y2KQuestion:
    """A 2000s trivia question."""
    text: str
    options: List[str]
    correct: int
    category: str  # music, movies, tech, fashion, events


# Question bank - 50+ questions about 2000s
Y2K_QUESTIONS: List[Y2KQuestion] = [
    # ===========================================================================
    # RUSSIAN MUSIC 2000s
    # ===========================================================================
    Y2KQuestion("Какая группа спела 'Нас не догонят'?", ["t.A.T.u.", "ВИА Гра", "Блестящие", "Фабрика"], 0, "music"),
    Y2KQuestion("'Я сошла с ума' - хит какой группы?", ["t.A.T.u.", "Руки Вверх", "Демо", "Стрелки"], 0, "music"),
    Y2KQuestion("Кто пел 'Крошка моя'?", ["Руки Вверх", "Отпетые мошенники", "Иванушки", "Дискотека Авария"], 0, "music"),
    Y2KQuestion("'18 мне уже' - чей хит?", ["Руки Вверх", "Hi-Fi", "Отпетые мошенники", "Демо"], 0, "music"),
    Y2KQuestion("Кто выиграл Фабрику Звёзд-1?", ["Юлия Савичева", "Полина Гагарина", "Ирина Дубцова", "Зара"], 0, "music"),
    Y2KQuestion("Группа 'Дискотека Авария' хит?", ["Небо", "Тучи", "Дождь", "Солнце"], 0, "music"),
    Y2KQuestion("'Девочка моя' пели?", ["Отпетые мошенники", "Руки Вверх", "Иванушки", "На-На"], 0, "music"),
    Y2KQuestion("Кто такой Дима Билан?", ["Певец", "Актёр", "DJ", "Продюсер"], 0, "music"),
    Y2KQuestion("Билан победил на Евровидении в?", ["2008", "2006", "2007", "2009"], 0, "music"),
    Y2KQuestion("Группа 'Звери' хит?", ["Районы-кварталы", "Улицы-дома", "Дворы-подъезды", "Парки-скверы"], 0, "music"),
    Y2KQuestion("'Ты узнаешь её' - хит группы?", ["Корни", "Звери", "Uma2rmaH", "Танцы Минус"], 0, "music"),
    Y2KQuestion("Группа 'Серебро' дебют?", ["2006", "2005", "2007", "2004"], 0, "music"),
    Y2KQuestion("Кто пел 'Song #1'?", ["Серебро", "ВИА Гра", "Блестящие", "Фабрика"], 0, "music"),

    # ===========================================================================
    # INTERNATIONAL MUSIC 2000s
    # ===========================================================================
    Y2KQuestion("'...Baby One More Time' - чей дебют?", ["Britney Spears", "Christina Aguilera", "Jessica Simpson", "Mandy Moore"], 0, "music"),
    Y2KQuestion("Группа NSYNC солист?", ["Justin Timberlake", "Nick Carter", "AJ McLean", "Howie D"], 0, "music"),
    Y2KQuestion("Backstreet Boys хит?", ["I Want It That Way", "Bye Bye Bye", "It's Gonna Be Me", "Pop"], 0, "music"),
    Y2KQuestion("'Lose Yourself' исполнитель?", ["Eminem", "50 Cent", "Dr. Dre", "Jay-Z"], 0, "music"),
    Y2KQuestion("Альбом Eminem 'The Eminem Show' год?", ["2002", "2000", "2003", "2001"], 0, "music"),
    Y2KQuestion("'Crazy in Love' - дуэт с?", ["Jay-Z", "Usher", "Nelly", "Ludacris"], 0, "music"),
    Y2KQuestion("Linkin Park дебютный альбом?", ["Hybrid Theory", "Meteora", "Minutes to Midnight", "Reanimation"], 0, "music"),
    Y2KQuestion("'In the End' группа?", ["Linkin Park", "Limp Bizkit", "Korn", "System of a Down"], 0, "music"),
    Y2KQuestion("Green Day 'American Idiot' год?", ["2004", "2003", "2005", "2002"], 0, "music"),
    Y2KQuestion("'Hey Ya!' исполнитель?", ["Outkast", "Black Eyed Peas", "Nelly", "Usher"], 0, "music"),
    Y2KQuestion("50 Cent дебютный альбом?", ["Get Rich or Die Tryin'", "The Massacre", "Curtis", "Before I Self Destruct"], 0, "music"),

    # ===========================================================================
    # MOVIES & TV 2000s
    # ===========================================================================
    Y2KQuestion("'Матрица' вышла в?", ["1999", "2000", "2001", "1998"], 0, "movies"),
    Y2KQuestion("Кто сыграл Нео?", ["Keanu Reeves", "Brad Pitt", "Tom Cruise", "Nicolas Cage"], 0, "movies"),
    Y2KQuestion("'Бригада' количество серий?", ["15", "12", "10", "20"], 0, "movies"),
    Y2KQuestion("Кто сыграл Сашу Белого?", ["Сергей Безруков", "Дмитрий Дюжев", "Павел Майков", "Владимир Вдовиченков"], 0, "movies"),
    Y2KQuestion("'Брат 2' год выхода?", ["2000", "1999", "2001", "2002"], 0, "movies"),
    Y2KQuestion("Режиссёр 'Брата'?", ["Алексей Балабанов", "Никита Михалков", "Фёдор Бондарчук", "Тимур Бекмамбетов"], 0, "movies"),
    Y2KQuestion("Сериал 'Friends' закончился в?", ["2004", "2003", "2005", "2002"], 0, "movies"),
    Y2KQuestion("'Властелин колец' режиссёр?", ["Peter Jackson", "Steven Spielberg", "James Cameron", "Ridley Scott"], 0, "movies"),
    Y2KQuestion("'Пираты Карибского моря' первый фильм год?", ["2003", "2002", "2004", "2001"], 0, "movies"),
    Y2KQuestion("Кто играет Джека Воробья?", ["Johnny Depp", "Orlando Bloom", "Keira Knightley", "Geoffrey Rush"], 0, "movies"),
    Y2KQuestion("'Гарри Поттер' первый фильм?", ["2001", "2000", "2002", "1999"], 0, "movies"),
    Y2KQuestion("Актёр Гарри Поттера?", ["Daniel Radcliffe", "Rupert Grint", "Tom Felton", "Matthew Lewis"], 0, "movies"),
    Y2KQuestion("'Титаник' Оскаров?", ["11", "9", "10", "12"], 0, "movies"),
    Y2KQuestion("Сериал 'Lost' дебют?", ["2004", "2003", "2005", "2006"], 0, "movies"),

    # ===========================================================================
    # TECH & INTERNET 2000s
    # ===========================================================================
    Y2KQuestion("ICQ логотип - какой цветок?", ["Зелёный", "Синий", "Красный", "Жёлтый"], 0, "tech"),
    Y2KQuestion("Nokia 3310 год выпуска?", ["2000", "1999", "2001", "2002"], 0, "tech"),
    Y2KQuestion("Игра Snake была на?", ["Nokia", "Motorola", "Samsung", "Sony Ericsson"], 0, "tech"),
    Y2KQuestion("Windows XP год выхода?", ["2001", "2000", "2002", "1999"], 0, "tech"),
    Y2KQuestion("iPod дебют?", ["2001", "2000", "2002", "2003"], 0, "tech"),
    Y2KQuestion("YouTube основан в?", ["2005", "2004", "2006", "2003"], 0, "tech"),
    Y2KQuestion("Facebook (изначально) год?", ["2004", "2003", "2005", "2006"], 0, "tech"),
    Y2KQuestion("MySpace пик популярности?", ["2005-2008", "2002-2005", "2008-2010", "2000-2003"], 0, "tech"),
    Y2KQuestion("Первый iPhone год?", ["2007", "2006", "2008", "2005"], 0, "tech"),
    Y2KQuestion("Google основан в?", ["1998", "1999", "2000", "1997"], 0, "tech"),
    Y2KQuestion("LiveJournal в России популярен с?", ["2001", "2000", "2002", "2003"], 0, "tech"),
    Y2KQuestion("Что такое dial-up?", ["Интернет по телефону", "Вид телефона", "Программа", "Игра"], 0, "tech"),
    Y2KQuestion("MP3-плеер популярен с?", ["Конец 90-х", "Середина 2000-х", "Конец 2000-х", "Начало 90-х"], 0, "tech"),

    # ===========================================================================
    # FASHION 2000s
    # ===========================================================================
    Y2KQuestion("Популярные джинсы 2000-х?", ["Low-rise (заниженная талия)", "High-rise", "Straight", "Skinny"], 0, "fashion"),
    Y2KQuestion("Frosted tips это?", ["Осветлённые кончики волос", "Тип обуви", "Вид макияжа", "Аксессуар"], 0, "fashion"),
    Y2KQuestion("Butterfly clips носили на?", ["Волосах", "Одежде", "Сумках", "Обуви"], 0, "fashion"),
    Y2KQuestion("Trucker hat - это?", ["Кепка с сеткой", "Шляпа", "Бандана", "Повязка"], 0, "fashion"),
    Y2KQuestion("Velour tracksuit бренд?", ["Juicy Couture", "Nike", "Adidas", "Puma"], 0, "fashion"),
    Y2KQuestion("Von Dutch - это?", ["Бренд кепок", "Обувь", "Джинсы", "Очки"], 0, "fashion"),
    Y2KQuestion("Популярная обувь 2000-х?", ["Platform shoes", "Loafers", "Oxfords", "Brogues"], 0, "fashion"),
    Y2KQuestion("UGG boots популярны с?", ["Начало 2000-х", "Конец 90-х", "Середина 2000-х", "Конец 2000-х"], 0, "fashion"),
    Y2KQuestion("Popped collar - это?", ["Поднятый воротник поло", "Вид причёски", "Тип джинсов", "Аксессуар"], 0, "fashion"),
    Y2KQuestion("Bedazzled - это когда на одежде?", ["Стразы", "Вышивка", "Принты", "Заплатки"], 0, "fashion"),

    # ===========================================================================
    # EVENTS & CULTURE 2000s
    # ===========================================================================
    Y2KQuestion("Y2K bug (проблема 2000) была в?", ["Компьютерах", "Телевизорах", "Радио", "Телефонах"], 0, "events"),
    Y2KQuestion("Евро-2000 выиграла?", ["Франция", "Италия", "Голландия", "Португалия"], 0, "events"),
    Y2KQuestion("ЧМ-2002 по футболу где?", ["Корея/Япония", "Германия", "ЮАР", "Бразилия"], 0, "events"),
    Y2KQuestion("Олимпиада 2004 город?", ["Афины", "Сидней", "Пекин", "Лондон"], 0, "events"),
    Y2KQuestion("Евро-2008 выиграла?", ["Испания", "Германия", "Россия", "Турция"], 0, "events"),
    Y2KQuestion("Россия на Евро-2008 место?", ["3-е (бронза)", "4-е", "2-е", "1-е"], 0, "events"),
    Y2KQuestion("Первый iPhone продали в?", ["США", "Европе", "Азии", "Везде одновременно"], 0, "events"),
    Y2KQuestion("Кризис 2008 начался с?", ["Ипотеки США", "Нефти", "Криптовалют", "Золота"], 0, "events"),
]


class Y2KPhase(Enum):
    """Internal phases for Y2K mode."""
    INTRO = "intro"
    CAMERA_PREP = "camera_prep"
    CAMERA_CAPTURE = "camera_capture"
    QUESTIONS = "questions"
    PROCESSING = "processing"
    RESULT = "result"


class Y2KMode(BaseMode):
    """2000s nostalgia trivia with AI character transformation."""

    name = "y2k"
    display_name = "НУЛЕВЫЕ"
    description = "Тест на знание нулевых"
    icon = "0"
    style = "retro"
    requires_camera = True
    requires_ai = True
    estimated_duration = 90

    # Number of questions to ask
    NUM_QUESTIONS = 6

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._caricature_service = CaricatureService()
        self._audio = get_audio_engine()
        self._uploader = AsyncUploader()

        # Animation
        self._particles = ParticleSystem()
        self._progress_tracker = SmartProgressTracker()

        # State
        self._phase = Y2KPhase.INTRO
        self._phase_timer: float = 0

        # Camera state
        self._photo_data: Optional[bytes] = None
        self._camera_frame: Optional[np.ndarray] = None
        self._countdown: int = 3
        self._countdown_timer: float = 0
        self._flash_alpha: float = 0

        # Questions state
        self._questions: List[Y2KQuestion] = []
        self._shuffled_options: List[List[str]] = []  # Shuffled options for each question
        self._shuffled_correct: List[int] = []  # New correct index after shuffle
        self._current_question: int = 0
        self._selected_option: Optional[int] = None  # None = no selection yet
        self._score: int = 0
        self._answers: List[int] = []  # Track what user answered
        self._category_scores: Dict[str, int] = {
            "music": 0,
            "movies": 0,
            "tech": 0,
            "fashion": 0,
            "events": 0,
        }

        # Result state
        self._ai_task: Optional[asyncio.Task] = None
        self._caricature_data: Optional[bytes] = None
        self._persona_text: str = ""
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None
        self._result_view: int = 0  # 0=portrait, 1=text, 2=qr

        # Visual state
        self._scanlines_offset: float = 0
        self._crt_flicker: float = 0

    def on_enter(self) -> None:
        """Initialize the mode."""
        logger.info("Y2K mode entered")

        # Select random questions
        self._questions = random.sample(Y2K_QUESTIONS, min(self.NUM_QUESTIONS, len(Y2K_QUESTIONS)))
        self._current_question = 0
        self._selected_option = 0
        self._score = 0
        self._answers = []

        # Reset category scores
        for cat in self._category_scores:
            self._category_scores[cat] = 0

        # Start intro
        self._phase = Y2KPhase.INTRO
        self._phase_timer = 0

        # Initialize particles with retro theme
        self._particles.clear_all()

        self.change_phase(ModePhase.INTRO)

    def on_exit(self) -> None:
        """Clean up."""
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()
        self._particles.clear_all()

    def on_update(self, delta_ms: float) -> None:
        """Update mode state."""
        self._phase_timer += delta_ms
        self._particles.update(delta_ms)

        # CRT effect animation
        self._scanlines_offset = (self._scanlines_offset + delta_ms * 0.05) % 4
        self._crt_flicker = 0.95 + random.random() * 0.05

        # Flash fade
        if self._flash_alpha > 0:
            self._flash_alpha = max(0, self._flash_alpha - delta_ms / 300)

        # Phase-specific updates
        if self._phase == Y2KPhase.INTRO:
            self._update_intro(delta_ms)
        elif self._phase == Y2KPhase.CAMERA_PREP:
            self._update_camera_prep(delta_ms)
        elif self._phase == Y2KPhase.CAMERA_CAPTURE:
            self._update_camera_capture(delta_ms)
        elif self._phase == Y2KPhase.QUESTIONS:
            self._update_questions(delta_ms)
        elif self._phase == Y2KPhase.PROCESSING:
            self._update_processing(delta_ms)
        elif self._phase == Y2KPhase.RESULT:
            self._update_result(delta_ms)

    def _update_intro(self, delta_ms: float) -> None:
        """Update intro animation."""
        if self._phase_timer > 3000:
            self._phase = Y2KPhase.CAMERA_PREP
            self._phase_timer = 0
            self.change_phase(ModePhase.ACTIVE)

    def _update_camera_prep(self, delta_ms: float) -> None:
        """Update camera preparation."""
        # Get live camera frame
        if camera_service.is_running:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None:
                self._camera_frame = frame

        if self._phase_timer > 2000:
            self._phase = Y2KPhase.CAMERA_CAPTURE
            self._phase_timer = 0
            self._countdown = 3
            self._countdown_timer = 0

    def _update_camera_capture(self, delta_ms: float) -> None:
        """Update camera capture with countdown."""
        # Get live camera frame
        if camera_service.is_running:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None:
                self._camera_frame = frame

        self._countdown_timer += delta_ms

        if self._countdown_timer >= 1000:
            self._countdown_timer = 0
            self._countdown -= 1

            if self._countdown <= 0:
                # Capture photo
                self._capture_photo()
                self._flash_alpha = 1.0
                self._phase = Y2KPhase.QUESTIONS
                self._phase_timer = 0

    def _capture_photo(self) -> None:
        """Capture the photo."""
        if camera_service.is_running:
            self._photo_data = camera_service.capture_jpeg(quality=90)
            logger.info(f"Photo captured: {len(self._photo_data) if self._photo_data else 0} bytes")

    def _update_questions(self, delta_ms: float) -> None:
        """Update question display."""
        pass  # Questions handled via input

    def _update_processing(self, delta_ms: float) -> None:
        """Update AI processing."""
        self._progress_tracker.update(delta_ms)

        if self._ai_task and self._ai_task.done():
            try:
                result = self._ai_task.result()
                if result:
                    self._caricature_data = result.image_data
                    logger.info("Y2K portrait generated successfully")
            except Exception as e:
                logger.error(f"Portrait generation failed: {e}")

            # Upload to S3
            if self._caricature_data:
                self._uploader.upload_bytes(
                    self._caricature_data,
                    prefix="y2k",
                    extension="png",
                    content_type="image/png",
                    callback=self._on_upload_complete
                )

            self._phase = Y2KPhase.RESULT
            self._phase_timer = 0
            self.change_phase(ModePhase.RESULT)

    def _update_result(self, delta_ms: float) -> None:
        """Update result display."""
        if self._phase_timer > 15000:
            self._finish()

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle upload completion."""
        if result.success:
            self._qr_url = result.url
            self._qr_image = result.qr_image
            logger.info(f"Y2K portrait uploaded: {result.url}")
        else:
            logger.error(f"Upload failed: {result.error}")

    def on_input(self, event: Event) -> bool:
        """Handle input events."""
        if event.type == EventType.BACK:
            self.request_exit()
            return True

        if self._phase == Y2KPhase.QUESTIONS:
            return self._handle_question_input(event)
        elif self._phase == Y2KPhase.RESULT:
            return self._handle_result_input(event)

        return False

    def _handle_question_input(self, event: Event) -> bool:
        """Handle input during questions - keypad 1-4 for direct selection."""
        # Direct answer selection via keypad 1-4
        if event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "1":
                self._selected_option = 0
                self._submit_answer()
                return True
            elif key == "2":
                self._selected_option = 1
                self._submit_answer()
                return True
            elif key == "3":
                self._selected_option = 2
                self._submit_answer()
                return True
            elif key == "4":
                self._selected_option = 3
                self._submit_answer()
                return True

        # Navigation via arrows (backup method)
        if event.type == EventType.ARCADE_LEFT:
            self._selected_option = (self._selected_option - 1) % 4
            return True
        elif event.type == EventType.ARCADE_RIGHT:
            self._selected_option = (self._selected_option + 1) % 4
            return True
        elif event.type == EventType.BUTTON_PRESS:
            self._submit_answer()
            return True
        return False

    def _submit_answer(self) -> None:
        """Submit the current answer."""
        question = self._questions[self._current_question]
        is_correct = self._selected_option == question.correct

        self._answers.append(self._selected_option)

        if is_correct:
            self._score += 1
            self._category_scores[question.category] += 1

        logger.info(f"Q{self._current_question + 1}: {is_correct}, Score: {self._score}")

        # Next question or finish
        self._current_question += 1
        self._selected_option = 0

        if self._current_question >= len(self._questions):
            self._start_processing()

    def _start_processing(self) -> None:
        """Start AI portrait generation."""
        self._phase = Y2KPhase.PROCESSING
        self._phase_timer = 0
        self.change_phase(ModePhase.PROCESSING)

        # Generate personality description from answers
        self._persona_text = self._generate_persona_text()

        # Initialize progress tracker
        self._progress_tracker.start([
            ProgressPhase("analyze", "Анализ ответов...", 2000),
            ProgressPhase("style", "Подбор стиля 2000-х...", 3000),
            ProgressPhase("generate", "Генерация портрета...", 8000),
            ProgressPhase("finish", "Финализация...", 2000),
        ])

        # Start AI generation
        self._ai_task = asyncio.create_task(self._generate_portrait())

    def _generate_persona_text(self) -> str:
        """Generate persona description based on answers."""
        # Find strongest category
        best_cat = max(self._category_scores, key=self._category_scores.get)
        score_pct = (self._score / len(self._questions)) * 100

        if score_pct >= 80:
            level = "ЭКСПЕРТ НУЛЕВЫХ"
        elif score_pct >= 60:
            level = "ЗНАТОК ЭПОХИ"
        elif score_pct >= 40:
            level = "ПОМНИШЬ НЕМНОГО"
        else:
            level = "НУЛЕВЫЕ МИМО ТЕБЯ"

        category_names = {
            "music": "музыку",
            "movies": "кино",
            "tech": "технологии",
            "fashion": "моду",
            "events": "события"
        }

        return f"{level}\nЛучше всего помнишь {category_names.get(best_cat, 'всё')}\nСчёт: {self._score}/{len(self._questions)}"

    async def _generate_portrait(self) -> Optional[Caricature]:
        """Generate the 2000s character portrait."""
        if not self._photo_data:
            logger.error("No photo data for portrait generation")
            return None

        try:
            # Build personality traits from answers
            traits = []

            # Add category-based traits
            if self._category_scores["music"] >= 2:
                traits.append("музыкальный фанат")
            if self._category_scores["movies"] >= 2:
                traits.append("киноман")
            if self._category_scores["tech"] >= 2:
                traits.append("техногик")
            if self._category_scores["fashion"] >= 2:
                traits.append("модник")

            # Score-based energy
            score_pct = (self._score / len(self._questions)) * 100
            if score_pct >= 80:
                traits.append("настоящий знаток эпохи")
            elif score_pct >= 50:
                traits.append("ностальгирующий по 2000-м")
            else:
                traits.append("открывающий для себя нулевые")

            trait_str = ", ".join(traits) if traits else "обычный человек из 2000-х"

            # Let AI be creative with the style
            prompt = f"""Transform THIS EXACT PERSON from the reference photo into a 2000s (Y2K era) character.

PERSONALITY INSIGHT from quiz: {trait_str}

The AI should CREATIVELY choose what kind of 2000s character they become based on their appearance and personality:
- Could be: emo kid, raver, hip-hop fan, pop princess, gamer nerd, scene kid, skater, club rat, etc.
- Let their face and vibe guide the choice - don't force a specific archetype

2000s VISUAL ELEMENTS to include (pick what fits):
- Fashion: low-rise jeans, frosted tips, butterfly clips, platform shoes, velour tracksuit, trucker hat, bedazzled everything
- Tech props: Nokia 3310, iPod, flip phone, CD player, chunky headphones
- Background hints: ICQ flower, Windows XP hills, early YouTube, MySpace profile, AIM buddy list
- Accessories: chunky plastic jewelry, mood rings, wallet chains, arm warmers

STYLE: Black and white ink illustration, high contrast, bold lines, thermal printer friendly
TEXT: Include a short label describing their 2000s persona in Russian (AI decides the text - could be funny, could be nostalgic)
BRAND: Include "VNVNC 2000s" somewhere in the design

CRITICAL: Capture their ACTUAL FACE from the photo - this must look like THEM, just styled as a 2000s character."""

            return await self._caricature_service.generate(
                photo_bytes=self._photo_data,
                prompt=prompt,
                style=CaricatureStyle.PROPHET,  # Will be replaced with Y2K style
                width=384,
                height=384,
            )

        except Exception as e:
            logger.exception(f"Portrait generation error: {e}")
            return None

    def _handle_result_input(self, event: Event) -> bool:
        """Handle input during result."""
        if event.type in (EventType.ARCADE_LEFT, EventType.ARCADE_RIGHT):
            # Cycle through views
            self._result_view = (self._result_view + 1) % 3
            self._phase_timer = 0  # Reset timer on interaction
            return True
        elif event.type in (EventType.ARCADE_CONFIRM, EventType.BUTTON_PRESS):
            self._finish()
            return True
        return False

    def _finish(self) -> None:
        """Finish the mode."""
        result = ModeResult(
            mode_name=self.name,
            success=True,
            data={
                "score": self._score,
                "total": len(self._questions),
                "category_scores": self._category_scores,
            },
            display_text=self._persona_text,
            ticker_text=f"НУЛЕВЫЕ {self._score}/{len(self._questions)}",
            lcd_text="VNVNC 2000s",
            should_print=True,
            print_data={
                "caricature": self._caricature_data,
                "score": self._score,
                "total": len(self._questions),
                "persona": self._persona_text,
                "qr_url": self._qr_url,
            }
        )
        self.complete(result)

    def render_main(self, buffer: np.ndarray) -> None:
        """Render to main 128x128 display."""
        # Clear buffer
        buffer[:] = 0

        # Apply CRT flicker effect
        flicker = self._crt_flicker

        if self._phase == Y2KPhase.INTRO:
            self._render_intro(buffer)
        elif self._phase in (Y2KPhase.CAMERA_PREP, Y2KPhase.CAMERA_CAPTURE):
            self._render_camera(buffer)
        elif self._phase == Y2KPhase.QUESTIONS:
            self._render_questions(buffer)
        elif self._phase == Y2KPhase.PROCESSING:
            self._render_processing(buffer)
        elif self._phase == Y2KPhase.RESULT:
            self._render_result(buffer)

        # Add scanlines effect
        self._add_scanlines(buffer)

        # Add flash effect
        if self._flash_alpha > 0:
            flash = int(255 * self._flash_alpha)
            buffer[:, :, :] = np.minimum(buffer.astype(np.int16) + flash, 255).astype(np.uint8)

        # Render particles on top
        self._particles.render(buffer)

    def _add_scanlines(self, buffer: np.ndarray) -> None:
        """Add CRT scanlines effect."""
        offset = int(self._scanlines_offset)
        for y in range(0, 128, 4):
            row = (y + offset) % 128
            buffer[row, :] = (buffer[row, :].astype(np.float32) * 0.7).astype(np.uint8)

    def _render_intro(self, buffer: np.ndarray) -> None:
        """Render intro screen."""
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import draw_rect

        # Dark background
        draw_rect(buffer, 0, 0, 128, 128, (20, 30, 40))

        # Title with retro colors
        draw_centered_text(buffer, "НУЛЕВЫЕ", 30, (0, 255, 200), scale=2)

        # Subtitle
        draw_centered_text(buffer, "2000s QUIZ", 55, (255, 100, 200), scale=1)

        # Prompt
        t = self._phase_timer / 1000
        pulse = 0.5 + 0.5 * math.sin(t * 3)
        alpha = int(255 * pulse)
        draw_centered_text(buffer, "НАЖМИ ЧТОБЫ НАЧАТЬ", 100, (alpha, alpha, alpha), scale=1)

        # Retro border
        border_pulse = int(128 + 127 * math.sin(t * 3))
        buffer[0:2, :] = [0, border_pulse, 200]
        buffer[-2:, :] = [0, border_pulse, 200]
        buffer[:, 0:2] = [0, border_pulse, 200]
        buffer[:, -2:] = [0, border_pulse, 200]

    def _render_camera(self, buffer: np.ndarray) -> None:
        """Render camera view."""
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import draw_rect

        # Draw camera frame
        if self._camera_frame is not None:
            frame = self._camera_frame
            # Convert to grayscale for retro look
            if len(frame.shape) == 3:
                gray = np.mean(frame, axis=2).astype(np.uint8)
            else:
                gray = frame
            # Resize to fit
            from PIL import Image
            img = Image.fromarray(gray)
            img = img.resize((128, 128), Image.Resampling.LANCZOS)
            gray = np.array(img)
            # Apply to all channels with cyan tint
            buffer[:, :, 0] = 0
            buffer[:, :, 1] = gray
            buffer[:, :, 2] = (gray * 0.8).astype(np.uint8)
        else:
            # No camera - show placeholder
            draw_rect(buffer, 0, 0, 128, 128, (20, 40, 40))
            draw_centered_text(buffer, "КАМЕРА...", 60, (0, 255, 200), scale=1)

        # Add viewfinder overlay (pass buffer, get back overlaid buffer)
        overlaid = create_viewfinder_overlay(buffer, self._phase_timer)
        buffer[:] = overlaid

        # Show countdown
        if self._phase == Y2KPhase.CAMERA_CAPTURE and self._countdown > 0:
            draw_centered_text(buffer, str(self._countdown), 55, (255, 255, 0), scale=4)
        elif self._phase == Y2KPhase.CAMERA_PREP:
            draw_centered_text(buffer, "ПРИГОТОВЬСЯ!", 110, (0, 255, 200), scale=1)

    def _render_questions(self, buffer: np.ndarray) -> None:
        """Render question screen."""
        from artifact.graphics.text_utils import draw_centered_text, draw_text
        from artifact.graphics.primitives import draw_rect, draw_rect

        question = self._questions[self._current_question]

        # Dark background
        draw_rect(buffer, 0, 0, 128, 128, (20, 30, 40))

        # Question number and score header
        q_num = f"{self._current_question + 1}/{len(self._questions)}"
        draw_text(buffer, q_num, 2, 2, (100, 100, 100), scale=1)
        draw_text(buffer, f"{self._score}pts", 90, 2, (0, 255, 200), scale=1)

        # Question text (word wrap)
        q_text = question.text
        words = q_text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if len(test_line) > 20:  # ~20 chars per line
                if current_line:
                    lines.append(current_line)
                current_line = word
            else:
                current_line = test_line
        if current_line:
            lines.append(current_line)

        y = 15
        for line in lines[:3]:  # Max 3 lines
            draw_centered_text(buffer, line, y, (255, 255, 255), scale=1)
            y += 10

        # Options in 2x2 grid
        option_y = 50
        for i, opt in enumerate(question.options):
            row = i // 2
            col = i % 2
            x = 5 + col * 62
            y = option_y + row * 35

            # Highlight selected
            is_selected = (i == self._selected_option)
            bg_color = (0, 80, 80) if is_selected else (30, 30, 30)
            text_color = (255, 255, 0) if is_selected else (200, 200, 200)

            # Draw option box
            draw_rect(buffer, x, y, 58, 30, bg_color)
            if is_selected:
                draw_rect(buffer, x, y, 58, 30, (0, 255, 200))

            # Option number (1-4 for keypad)
            number = ["1", "2", "3", "4"][i]
            draw_text(buffer, number, x + 2, y + 2, (0, 255, 200), scale=1)

            # Option text (truncate if needed)
            opt_text = opt[:10] if len(opt) > 10 else opt
            draw_text(buffer, opt_text, x + 2, y + 14, text_color, scale=1)

    def _render_processing(self, buffer: np.ndarray) -> None:
        """Render processing screen."""
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import draw_rect

        # Dark background
        draw_rect(buffer, 0, 0, 128, 128, (20, 30, 40))

        # Title
        draw_centered_text(buffer, "ОБРАБОТКА...", 20, (0, 255, 200), scale=1)

        # Progress bar
        progress = self._progress_tracker.progress
        bar_width = 100
        bar_height = 8
        bar_x = (128 - bar_width) // 2
        bar_y = 60

        # Background
        draw_rect(buffer, bar_x, bar_y, bar_width, bar_height, (40, 40, 40))
        # Fill
        fill_width = int(bar_width * progress)
        if fill_width > 0:
            draw_rect(buffer, bar_x, bar_y, fill_width, bar_height, (0, 255, 200))

        # Status text
        status = self._progress_tracker.current_phase_name or "..."
        draw_centered_text(buffer, status, 75, (150, 150, 150), scale=1)

        # Retro animation - bouncing pixel art
        t = self._phase_timer / 100
        for i in range(5):
            px = 40 + i * 12
            py = 95 + int(5 * math.sin(t + i))
            draw_rect(buffer, px, py, 4, 4, (0, 255, 200))

    def _render_result(self, buffer: np.ndarray) -> None:
        """Render result screen."""
        from artifact.graphics.primitives import draw_rect
        from PIL import Image
        import io

        if self._result_view == 0 and self._caricature_data:
            # Portrait view
            try:
                img = Image.open(io.BytesIO(self._caricature_data))
                img = img.convert('RGB')
                img = img.resize((128, 128), Image.Resampling.LANCZOS)
                buffer[:] = np.array(img)
            except Exception as e:
                logger.error(f"Error displaying portrait: {e}")
                self._render_fallback_result(buffer)
        elif self._result_view == 1:
            # Text view
            self._render_text_result(buffer)
        elif self._result_view == 2 and self._qr_image is not None:
            # QR view
            draw_rect(buffer, 0, 0, 128, 128, (40, 40, 40))
            qr = self._qr_image
            # Scale QR to fit
            qr_size = min(100, qr.shape[0])
            qr_resized = np.array(Image.fromarray(qr).resize((qr_size, qr_size), Image.Resampling.NEAREST))
            x = (128 - qr_size) // 2
            y = (128 - qr_size) // 2
            buffer[y:y+qr_size, x:x+qr_size] = qr_resized
        else:
            self._render_text_result(buffer)

    def _render_text_result(self, buffer: np.ndarray) -> None:
        """Render text result."""
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import draw_rect

        # Dark background
        draw_rect(buffer, 0, 0, 128, 128, (20, 30, 30))

        # Title
        draw_centered_text(buffer, "РЕЗУЛЬТАТ", 10, (0, 255, 200), scale=1)

        # Score
        score_txt = f"{self._score}/{len(self._questions)}"
        draw_centered_text(buffer, score_txt, 30, (255, 255, 0), scale=2)

        # Persona text (word wrap)
        y = 60
        for line in self._persona_text.split('\n')[:4]:  # Max 4 lines
            if len(line) > 18:
                line = line[:17] + "..."
            draw_centered_text(buffer, line, y, (200, 200, 200), scale=1)
            y += 12

    def _render_fallback_result(self, buffer: np.ndarray) -> None:
        """Render fallback when no portrait available."""
        self._render_text_result(buffer)

    def render_ticker(self, buffer: np.ndarray) -> None:
        """Render to ticker display."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)

        # Determine text and color based on phase
        if self._phase == Y2KPhase.QUESTIONS:
            text = f"ВОПРОС {self._current_question + 1}/{len(self._questions)}"
            color = (255, 200, 0)  # Yellow for questions
            effect = TickerEffect.PULSE_SCROLL
        elif self._phase == Y2KPhase.PROCESSING:
            text = "СОЗДАЁМ ТВОЙ ОБРАЗ 2000-х..."
            color = (200, 0, 255)  # Purple for processing
            effect = TickerEffect.SPARKLE_SCROLL
        elif self._phase == Y2KPhase.RESULT:
            text = f"НУЛЕВЫЕ: {self._score}/{len(self._questions)} ★"
            color = (0, 255, 200)  # Cyan for result
            effect = TickerEffect.RAINBOW_SCROLL
        else:
            text = "ДОБРО ПОЖАЛОВАТЬ В НУЛЕВЫЕ!"
            color = (0, 255, 200)  # Cyan default
            effect = TickerEffect.SPARKLE_SCROLL

        render_ticker_animated(
            buffer, text,
            self._phase_timer * 1000,  # Convert to ms
            color,
            effect,
            speed=0.025
        )

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self._phase == Y2KPhase.INTRO:
            return "VNVNC НУЛЕВЫЕ"
        elif self._phase == Y2KPhase.QUESTIONS:
            return f"Q{self._current_question+1} СЧЁТ:{self._score}"
        elif self._phase == Y2KPhase.PROCESSING:
            return "ГЕНЕРАЦИЯ..."
        elif self._phase == Y2KPhase.RESULT:
            return f"2000s {self._score}/{len(self._questions)}"
        return "НУЛЕВЫЕ"

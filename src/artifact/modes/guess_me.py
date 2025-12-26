"""Guess Me Mode - Akinator-style AI guessing game.

The AI asks strategic questions to build a profile, then guesses who you are
based on your photo and answers. Uses dynamic follow-up questions if not confident.

Flow:
1. Camera capture
2. 10 strategic base questions (yes/no)
3. AI analyzes photo + answers
4. If confident → reveals guess
5. If not confident → asks 5 more targeted questions → final guess
"""

import asyncio
import logging
from typing import Optional, Tuple, List, Dict
from datetime import datetime
import random
import math
import numpy as np

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.utils.camera import floyd_steinberg_dither, create_viewfinder_overlay
from artifact.utils.camera_service import camera_service

logger = logging.getLogger(__name__)


class GuessPhase:
    """Sub-phases within Guess Me mode."""
    INTRO = "intro"
    CAMERA_PREP = "camera_prep"
    CAMERA_CAPTURE = "capture"
    QUESTIONS = "questions"          # Base questions
    ANALYZING = "analyzing"          # AI decides confidence
    MORE_QUESTIONS = "more_questions"  # Follow-up questions
    FINAL_ANALYZING = "final_analyzing"
    PROCESSING_IMAGE = "processing_image"  # Generate caricature
    REVEAL = "reveal"
    SHOW_IMAGE = "show_image"
    RESULT = "result"


# =============================================================================
# AKINATOR-STYLE BASE QUESTIONS
# Strategic questions that narrow down personality/character type
# Format: (question_ru, trait_key, yes_meaning, no_meaning)
# =============================================================================

BASE_QUESTIONS: List[Tuple[str, str, str, str]] = [
    # Social dimension
    ("Ты душа компании?", "social", "экстраверт, любит людей", "интроверт, предпочитает одиночество"),

    # Thinking style
    ("Логика важнее эмоций?", "thinking", "логик, аналитик, рационалист", "эмоциональный, чувственный, эмпат"),

    # Risk tolerance
    ("Любишь рисковать?", "risk", "авантюрист, смельчак, предприниматель", "осторожный, консервативный, стабильный"),

    # Planning
    ("Планируешь всё заранее?", "planning", "организованный, контролирующий, методичный", "спонтанный, гибкий, импульсивный"),

    # Values
    ("Карьера важнее семьи?", "values", "амбициозный, карьерист, трудоголик", "семьянин, ценит близких, баланс"),

    # Leadership
    ("Ведёшь людей за собой?", "leadership", "лидер, босс, управленец", "исполнитель, командный игрок, поддержка"),

    # Creativity
    ("Ты творческая натура?", "creative", "художник, креативщик, мечтатель", "практик, реалист, технарь"),

    # Outlook
    ("Стакан наполовину полон?", "outlook", "оптимист, позитивный, вдохновляющий", "реалист, скептик, прагматик"),

    # Attention
    ("Любишь быть в центре внимания?", "attention", "звезда, шоумен, харизматик", "скромный, в тени, наблюдатель"),

    # Control
    ("Тебе нужен контроль?", "control", "перфекционист, контрол-фрик, требовательный", "расслабленный, доверяющий, гибкий"),
]


# =============================================================================
# AI PROMPTS
# =============================================================================

ANALYSIS_PROMPT = """Ты - проницательный провидец в аркадном автомате VNVNC.
Твоя задача - угадать КТО этот человек по фото и ответам на вопросы.

ФОТО: [прикреплено]

ПРОФИЛЬ на основе ответов:
{profile}

Оцени свою уверенность по шкале 1-10.
- Если уверенность >= 7: дай финальную догадку
- Если уверенность < 7: задай 5 уточняющих вопросов

ФОРМАТ ОТВЕТА:
CONFIDENCE: [число 1-10]
[если уверен:]
GUESS: [твоя угадка - кто этот человек, персонаж, типаж, 1-2 предложения, с эмоджи]
TITLE: [короткий титул, например "Король Дедлайнов" или "Душа Вечеринки"]
[если не уверен:]
QUESTIONS:
1. [вопрос]
2. [вопрос]
3. [вопрос]
4. [вопрос]
5. [вопрос]

ВАЖНЫЕ ПРАВИЛА ДЛЯ ВОПРОСОВ:
- Каждый вопрос МАКСИМУМ 30 символов!
- Вопросы ТОЛЬКО на русском языке
- Вопросы ТОЛЬКО для ответа ДА или НЕТ
- Короткие, простые формулировки
- Примеры: "Ты любишь кофе?", "Тебе нравится спорт?", "Ты сова?"
"""

FINAL_GUESS_PROMPT = """Ты - проницательный провидец в аркадном автомате VNVNC.
Угадай КТО этот человек по фото и ПОЛНОМУ профилю ответов.

ФОТО: [прикреплено]

БАЗОВЫЙ ПРОФИЛЬ:
{base_profile}

ДОПОЛНИТЕЛЬНЫЕ ОТВЕТЫ:
{extra_profile}

Теперь ты ДОЛЖЕН дать финальную догадку. Будь креативным и весёлым!

ФОРМАТ:
GUESS: [твоя угадка - кто этот человек, персонаж, типаж, 1-2 предложения, весело, с эмоджи]
TITLE: [короткий титул, 2-4 слова]
"""


class GuessMeMode(BaseMode):
    """Guess Me Mode - Akinator-style AI guessing game.

    Flow:
    1. Camera capture
    2. 10 strategic questions (yes/no with left/right)
    3. AI analyzes photo + answers
    4. If confident: reveals guess
    5. If not confident: asks 5 more targeted questions
    6. Final guess + caricature generation
    """

    name = "guess_me"
    display_name = "КТО Я?"
    description = "Акинатор угадывает тебя!"
    icon = "?"
    style = "pop"
    requires_camera = True
    requires_ai = True
    estimated_duration = 90  # Longer for questions

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._gemini_client = get_gemini_client()
        self._caricature_service = CaricatureService()

        # Sub-phase
        self._sub_phase = GuessPhase.INTRO

        # Camera
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0

        # Questions state
        self._base_questions: List[Tuple[str, str, str, str]] = []
        self._base_answers: List[bool] = []  # True = yes, False = no
        self._follow_up_questions: List[str] = []
        self._follow_up_answers: List[bool] = []
        self._current_question_idx: int = 0
        self._question_answered: bool = False
        self._answer_display_time: float = 0.0

        # AI results
        self._confidence: int = 0
        self._guess_text: str = ""
        self._guess_title: str = ""
        self._illustration: Optional[Caricature] = None

        # Tasks
        self._ai_task: Optional[asyncio.Task] = None
        self._processing_progress: float = 0.0

        # Progress tracker for AI processing
        self._progress_tracker = SmartProgressTracker(mode_theme="guess_me")

        # Visuals
        self._particles = ParticleSystem()
        self._reveal_progress: float = 0.0
        self._primary = (255, 0, 100)   # Hot Pink
        self._secondary = (0, 255, 200)  # Cyan
        self._yes_color = (0, 255, 100)  # Green
        self._no_color = (255, 100, 0)   # Orange

        # Result view state
        self._result_view: str = "text"  # "text" or "image"
        self._text_scroll_complete: bool = False
        self._text_view_time: float = 0.0
        self._scroll_duration: float = 0.0

    @property
    def is_ai_available(self) -> bool:
        return self._gemini_client.is_available

    def on_enter(self) -> None:
        self._sub_phase = GuessPhase.INTRO
        self._photo_data = None
        self._guess_text = ""
        self._guess_title = ""
        self._illustration = None
        self._processing_progress = 0.0
        self._reveal_progress = 0.0
        self._flash_alpha = 0.0
        self._confidence = 0

        # Reset result view state
        self._result_view = "text"
        self._text_scroll_complete = False
        self._text_view_time = 0.0
        self._scroll_duration = 0.0

        # Reset progress tracker
        self._progress_tracker.reset()

        # Reset question state
        self._base_questions = list(BASE_QUESTIONS)
        random.shuffle(self._base_questions)
        self._base_questions = self._base_questions[:10]
        self._base_answers = []
        self._follow_up_questions = []
        self._follow_up_answers = []
        self._current_question_idx = 0
        self._question_answered = False
        self._answer_display_time = 0.0

        # Use shared camera service (always running)
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera service ready for Guess Me")

        # Particles
        confetti = ParticlePresets.confetti(x=64, y=64)
        self._particles.add_emitter("confetti", confetti)

        self.change_phase(ModePhase.INTRO)
        logger.info("Guess Me mode entered")

    def on_update(self, delta_ms: float) -> None:
        self._particles.update(delta_ms)

        # Update preview
        if self._sub_phase in (GuessPhase.CAMERA_PREP, GuessPhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        # Handle answer display timeout
        if self._question_answered:
            self._answer_display_time += delta_ms
            if self._answer_display_time > 800:  # Show answer for 0.8s
                self._question_answered = False
                self._answer_display_time = 0.0
                self._advance_question()

        # Phase logic
        if self.phase == ModePhase.INTRO:
            if self._time_in_phase > 2000:
                self._sub_phase = GuessPhase.CAMERA_PREP
                self.change_phase(ModePhase.ACTIVE)
                self._time_in_phase = 0

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == GuessPhase.CAMERA_PREP:
                if self._time_in_phase > 2000:
                    self._start_capture()

            elif self._sub_phase == GuessPhase.CAMERA_CAPTURE:
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_capture()

                if self._time_in_phase > 3500:
                    # Start questions phase
                    self._sub_phase = GuessPhase.QUESTIONS
                    self._time_in_phase = 0

            elif self._sub_phase == GuessPhase.QUESTIONS:
                # Questions handled via input
                pass

            elif self._sub_phase == GuessPhase.MORE_QUESTIONS:
                # Follow-up questions handled via input
                pass

        elif self.phase == ModePhase.PROCESSING:
            if self._ai_task and self._ai_task.done():
                self._on_ai_complete()
            else:
                self._processing_progress = min(0.95, self._processing_progress + delta_ms / 8000)

        elif self.phase == ModePhase.RESULT:
            # Calculate scroll duration on first entry
            if self._guess_text and self._scroll_duration == 0:
                from artifact.graphics.text_utils import calculate_scroll_duration, MAIN_DISPLAY_WIDTH
                from artifact.graphics.fonts import load_font
                font = load_font("cyrillic")
                rect = (4, 45, 120, 70)
                self._scroll_duration = calculate_scroll_duration(
                    self._guess_text, rect, font, scale=1, line_spacing=2, scroll_interval_ms=1500
                )
                self._scroll_duration = max(3000, self._scroll_duration + 2000)

            # Track time in text view
            if self._result_view == "text":
                self._text_view_time += delta_ms
                if not self._text_scroll_complete and self._text_view_time >= self._scroll_duration:
                    self._text_scroll_complete = True
                    if self._illustration:
                        self._result_view = "image"

            # Auto-complete after 45 seconds
            if self._time_in_phase > 45000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        # Handle question answering
        if self._sub_phase in (GuessPhase.QUESTIONS, GuessPhase.MORE_QUESTIONS):
            if not self._question_answered:
                if event.type == EventType.ARCADE_LEFT:
                    # NO answer
                    self._record_answer(False)
                    return True
                elif event.type == EventType.ARCADE_RIGHT:
                    # YES answer
                    self._record_answer(True)
                    return True

        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT:
                # On image view = print, on text view = switch to image or print
                if self._result_view == "image" or not self._illustration:
                    self._finish()
                    return True
                else:
                    if self._illustration:
                        self._result_view = "image"
                        self._text_scroll_complete = True
                    else:
                        self._finish()
                    return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.RESULT:
                # Toggle to text view
                self._result_view = "text"
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.RESULT and self._illustration:
                # Toggle to image view
                self._result_view = "image"
                return True

        return False

    def _record_answer(self, answer: bool) -> None:
        """Record an answer and show feedback."""
        self._question_answered = True
        self._answer_display_time = 0.0

        if self._sub_phase == GuessPhase.QUESTIONS:
            self._base_answers.append(answer)
            logger.debug(f"Base Q{self._current_question_idx + 1}: {'YES' if answer else 'NO'}")
        else:
            self._follow_up_answers.append(answer)
            logger.debug(f"Follow-up Q{self._current_question_idx + 1}: {'YES' if answer else 'NO'}")

        # Particle burst
        emitter = self._particles.get_emitter("confetti")
        if emitter:
            emitter.burst(10)

    def _advance_question(self) -> None:
        """Move to next question or start analysis."""
        self._current_question_idx += 1

        if self._sub_phase == GuessPhase.QUESTIONS:
            if self._current_question_idx >= len(self._base_questions):
                # Done with base questions, start analysis
                self._start_analysis()
        else:
            if self._current_question_idx >= len(self._follow_up_questions):
                # Done with follow-ups, start final analysis
                self._start_final_analysis()

    def _start_capture(self) -> None:
        self._sub_phase = GuessPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0

    def _do_capture(self) -> None:
        self._photo_data = camera_service.capture_jpeg(quality=90)
        self._flash_alpha = 1.0
        if self._photo_data:
            logger.info(f"Photo captured: {len(self._photo_data)} bytes")
        else:
            logger.warning("Failed to capture photo")

    def _update_camera_preview(self) -> None:
        try:
            frame = camera_service.get_full_frame()
            if frame is not None and frame.size > 0:
                dithered = floyd_steinberg_dither(frame, target_size=(128, 128))
                self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()
                self._camera = True
        except Exception as e:
            logger.warning(f"Camera preview error: {e}")

    def _build_profile_string(self) -> str:
        """Build a profile string from base answers."""
        profile_parts = []
        for i, (question, trait, yes_meaning, no_meaning) in enumerate(self._base_questions):
            if i < len(self._base_answers):
                answer = self._base_answers[i]
                meaning = yes_meaning if answer else no_meaning
                profile_parts.append(f"- {trait}: {meaning}")
        return "\n".join(profile_parts)

    def _build_followup_profile(self) -> str:
        """Build profile from follow-up answers."""
        profile_parts = []
        for i, question in enumerate(self._follow_up_questions):
            if i < len(self._follow_up_answers):
                answer = "ДА" if self._follow_up_answers[i] else "НЕТ"
                profile_parts.append(f"- \"{question}\" → {answer}")
        return "\n".join(profile_parts)

    def _start_analysis(self) -> None:
        """Start AI analysis with photo + base answers."""
        self._sub_phase = GuessPhase.ANALYZING
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        # Start progress tracker
        self._progress_tracker.reset()
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        self._ai_task = asyncio.create_task(self._run_analysis())
        logger.info("Starting Akinator analysis...")

    async def _run_analysis(self) -> None:
        """AI analyzes photo + answers, decides if confident or needs more."""
        try:
            if not self._photo_data:
                self._guess_text = "Не удалось сделать фото :("
                self._guess_title = "Ошибка"
                self._confidence = 10
                return

            profile = self._build_profile_string()
            prompt = ANALYSIS_PROMPT.format(profile=profile)

            # Advance to text generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)

            response = await self._gemini_client.generate_with_image(
                prompt=prompt,
                image_data=self._photo_data,
                model=GeminiModel.FLASH_VISION,
            )

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

            if response:
                self._parse_analysis_response(response)
            else:
                self._guess_text = "Загадочная личность..."
                self._guess_title = "Незнакомец"
                self._confidence = 10

        except Exception as e:
            logger.error(f"Analysis error: {e}")
            self._guess_text = "ИИ задумался о смысле жизни..."
            self._guess_title = "Сбой"
            self._confidence = 10

    def _parse_analysis_response(self, text: str) -> None:
        """Parse AI analysis response."""
        self._confidence = 5  # Default
        self._follow_up_questions = []

        lines = text.strip().split("\n")
        in_questions = False

        for line in lines:
            line = line.strip()
            if line.startswith("CONFIDENCE:"):
                try:
                    self._confidence = int(line.split(":")[1].strip())
                except:
                    self._confidence = 5
            elif line.startswith("GUESS:"):
                self._guess_text = line[6:].strip()
            elif line.startswith("TITLE:"):
                self._guess_title = line[6:].strip()
            elif line.startswith("QUESTIONS:"):
                in_questions = True
            elif in_questions and line and line[0].isdigit():
                # Extract question (remove numbering)
                q = line.split(".", 1)[-1].strip() if "." in line else line
                q = q.split(")", 1)[-1].strip() if ")" in q else q
                if q and len(q) > 5:
                    self._follow_up_questions.append(q)

        logger.info(f"Analysis complete. Confidence: {self._confidence}")
        if self._follow_up_questions:
            logger.info(f"Got {len(self._follow_up_questions)} follow-up questions")

    def _start_final_analysis(self) -> None:
        """Start final analysis after follow-up questions."""
        self._sub_phase = GuessPhase.FINAL_ANALYZING
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        # Reset and start progress tracker for final analysis
        self._progress_tracker.reset()
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        self._ai_task = asyncio.create_task(self._run_final_analysis())
        logger.info("Starting final Akinator analysis...")

    async def _run_final_analysis(self) -> None:
        """Final AI guess with all data."""
        try:
            if not self._photo_data:
                self._guess_text = "Не удалось сделать фото :("
                self._guess_title = "Ошибка"
                return

            base_profile = self._build_profile_string()
            extra_profile = self._build_followup_profile()

            prompt = FINAL_GUESS_PROMPT.format(
                base_profile=base_profile,
                extra_profile=extra_profile
            )

            # Advance to text generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)

            response = await self._gemini_client.generate_with_image(
                prompt=prompt,
                image_data=self._photo_data,
                model=GeminiModel.FLASH_VISION,
            )

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

            if response:
                for line in response.strip().split("\n"):
                    if line.startswith("GUESS:"):
                        self._guess_text = line[6:].strip()
                    elif line.startswith("TITLE:"):
                        self._guess_title = line[6:].strip()

            if not self._guess_text:
                self._guess_text = response[:200] if response else "Загадочная личность..."
            if not self._guess_title:
                self._guess_title = "Незнакомец"

            self._confidence = 10  # Force completion

        except Exception as e:
            logger.error(f"Final analysis error: {e}")
            self._guess_text = "ИИ не справился с задачей..."
            self._guess_title = "Загадка"

    def _on_ai_complete(self) -> None:
        """Handle AI task completion."""
        self._processing_progress = 1.0

        # Complete progress tracker
        self._progress_tracker.complete()

        if self._sub_phase == GuessPhase.ANALYZING:
            if self._confidence >= 7 or not self._follow_up_questions:
                # Confident enough or no follow-ups, generate image
                self._start_image_generation()
            else:
                # Need more questions
                self._sub_phase = GuessPhase.MORE_QUESTIONS
                self._current_question_idx = 0
                self.change_phase(ModePhase.ACTIVE)
                logger.info("Need more questions, entering follow-up phase")

        elif self._sub_phase == GuessPhase.FINAL_ANALYZING:
            self._start_image_generation()

        elif self._sub_phase == GuessPhase.PROCESSING_IMAGE:
            self._sub_phase = GuessPhase.RESULT
            self.change_phase(ModePhase.RESULT)
            # Start with text view, will auto-switch to image after scroll
            self._result_view = "text"
            self._text_scroll_complete = False
            self._text_view_time = 0.0
            self._scroll_duration = 0.0

    def _start_image_generation(self) -> None:
        """Start generating the caricature."""
        self._sub_phase = GuessPhase.PROCESSING_IMAGE
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        # Reset and start progress tracker for image generation
        self._progress_tracker.reset()
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

        # Build personality context from all answers
        profile = self._build_profile_string()
        if self._follow_up_answers:
            profile += "\n" + self._build_followup_profile()

        self._ai_task = asyncio.create_task(self._generate_image(profile))

    async def _generate_image(self, profile: str) -> None:
        """Generate caricature with personality info."""
        try:
            personality = f"{self._guess_title}: {self._guess_text}\n\nПрофиль: {profile}"

            self._illustration = await self._caricature_service.generate_caricature(
                reference_photo=self._photo_data,
                style=CaricatureStyle.GUESS,
                personality_context=personality
            )

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)
        except Exception as e:
            logger.error(f"Image generation error: {e}")

    def on_exit(self) -> None:
        # Clear camera reference (shared service, don't close)
        self._camera = None
        self._camera_frame = None
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()
        self._particles.clear_all()

    def _finish(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=self._guess_text or self._guess_title,
            ticker_text=self._guess_title,
            lcd_text=" КТО Я? ".center(16),
            should_print=True,
            print_data={
                "type": "guess_me",
                "title": self._guess_title,
                "prediction": self._guess_text or "",
                "caricature": self._illustration.image_data if self._illustration else None,
                "photo": self._photo_data,
                "base_answers": len(self._base_answers),
                "followup_answers": len(self._follow_up_answers),
                "confidence": self._confidence,
                "timestamp": datetime.now().isoformat()
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        from artifact.graphics.primitives import fill, draw_rect, draw_line
        from artifact.graphics.text_utils import draw_centered_text, wrap_text, render_scrolling_text_area

        fill(buffer, (20, 20, 40))

        if self._sub_phase == GuessPhase.INTRO:
            draw_centered_text(buffer, "КТО ТЫ?", 50, self._primary, scale=2)
            draw_centered_text(buffer, "Акинатор узнает!", 80, self._secondary, scale=1)

        elif self._sub_phase in (GuessPhase.CAMERA_PREP, GuessPhase.CAMERA_CAPTURE):
            if self._camera_frame is not None:
                if self._camera_frame.shape == (128, 128, 3):
                    np.copyto(buffer, self._camera_frame)

            if self._sub_phase == GuessPhase.CAMERA_CAPTURE:
                cnt = math.ceil(self._camera_countdown)
                if cnt > 0:
                    draw_centered_text(buffer, str(cnt), 64, (255, 255, 255), scale=3)

        elif self._sub_phase == GuessPhase.QUESTIONS:
            self._render_question_screen(buffer, is_followup=False)

        elif self._sub_phase == GuessPhase.MORE_QUESTIONS:
            self._render_question_screen(buffer, is_followup=True)

        elif self._sub_phase in (GuessPhase.ANALYZING, GuessPhase.FINAL_ANALYZING, GuessPhase.PROCESSING_IMAGE):
            self._render_processing(buffer)

        elif self._sub_phase == GuessPhase.RESULT:
            if self._result_view == "image" and self._illustration and self._illustration.image_data:
                # Image view - show illustration
                try:
                    from PIL import Image
                    from io import BytesIO

                    img = Image.open(BytesIO(self._illustration.image_data))
                    img = img.convert("RGB")
                    img = img.resize((120, 100), Image.Resampling.LANCZOS)
                    img_array = np.array(img)
                    buffer[5:105, 4:124] = img_array

                    # Hint at bottom
                    if int(self._time_in_phase / 500) % 2 == 0:
                        draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 112, (100, 200, 100), scale=1)
                    else:
                        draw_centered_text(buffer, "◄ ТЕКСТ", 112, (100, 100, 120), scale=1)
                except Exception as e:
                    logger.warning(f"Failed to render guess illustration: {e}")
                    self._result_view = "text"
            else:
                # Text view - show guess
                draw_centered_text(buffer, self._guess_title, 15, self._primary, scale=1)
                render_scrolling_text_area(
                    buffer,
                    self._guess_text or "",
                    (4, 32, 120, 70),
                    (255, 255, 255),
                    self._text_view_time,  # Use text_view_time for scrolling
                    scale=1,
                    line_spacing=2,
                    scroll_interval_ms=1500,
                )

                # Hint at bottom
                if self._illustration:
                    if int(self._time_in_phase / 600) % 2 == 0:
                        draw_centered_text(buffer, "ФОТО ►", 112, (100, 150, 200), scale=1)
                    else:
                        draw_centered_text(buffer, "НАЖМИ", 112, (100, 100, 120), scale=1)
                else:
                    if int(self._time_in_phase / 500) % 2 == 0:
                        draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 112, (100, 200, 100), scale=1)

        self._particles.render(buffer)

        if self._flash_alpha > 0:
            a = int(255 * self._flash_alpha)
            fill(buffer, (a, a, a))
            self._flash_alpha = max(0, self._flash_alpha - 0.1)

    def _render_question_screen(self, buffer, is_followup: bool) -> None:
        """Render the question answering screen."""
        from artifact.graphics.primitives import draw_rect, draw_line
        from artifact.graphics.text_utils import draw_centered_text, wrap_text

        # Get current question
        if is_followup:
            questions = self._follow_up_questions
            answers = self._follow_up_answers
            total = len(questions)
        else:
            questions = self._base_questions
            answers = self._base_answers
            total = len(questions)

        idx = self._current_question_idx
        if idx >= len(questions):
            return

        # Progress bar
        progress = (idx + 1) / total
        draw_rect(buffer, 10, 5, 108, 6, (40, 40, 60))
        draw_rect(buffer, 10, 5, int(108 * progress), 6, self._secondary)
        draw_centered_text(buffer, f"{idx + 1}/{total}", 4, (255, 255, 255), scale=1)

        # Question text
        if is_followup:
            q_text = questions[idx]
        else:
            q_text = questions[idx][0]

        wrapped = wrap_text(q_text, 20)
        y_start = 30
        for i, line in enumerate(wrapped[:3]):
            draw_centered_text(buffer, line, y_start + i * 12, (255, 255, 255), scale=1)

        # Show answer feedback if just answered
        if self._question_answered:
            last_answer = answers[-1] if answers else False
            if last_answer:
                draw_centered_text(buffer, "ДА!", 80, self._yes_color, scale=2)
            else:
                draw_centered_text(buffer, "НЕТ!", 80, self._no_color, scale=2)
        else:
            # Show buttons
            # Left button (NO)
            draw_rect(buffer, 8, 85, 50, 35, self._no_color)
            draw_centered_text(buffer, "←", 92, (0, 0, 0), scale=1)
            draw_centered_text(buffer, "НЕТ", 105, (0, 0, 0), scale=1)

            # Right button (YES)
            draw_rect(buffer, 70, 85, 50, 35, self._yes_color)
            draw_centered_text(buffer, "→", 92, (0, 0, 0), scale=1)
            draw_centered_text(buffer, "ДА", 105, (0, 0, 0), scale=1)

    def _render_processing(self, buffer) -> None:
        """Render processing animation with progress tracker."""
        from artifact.graphics.primitives import draw_rect, draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        # Update progress tracker
        self._progress_tracker.update(delta_ms=16)

        # Render themed loading animation
        style = "tech" if self._sub_phase == GuessPhase.PROCESSING_IMAGE else "mystical"
        self._progress_tracker.render_loading_animation(
            buffer, style=style, time_ms=self._time_in_phase
        )

        # Status text from progress tracker
        status_message = self._progress_tracker.get_message()
        draw_centered_text(buffer, status_message, 78, self._primary, scale=1)

        # Progress bar using progress tracker
        bar_x, bar_y, bar_w, bar_h = 14, 92, 100, 10
        self._progress_tracker.render_progress_bar(
            buffer, bar_x, bar_y, bar_w, bar_h,
            bar_color=self._secondary,
            bg_color=(40, 40, 60),
            border_color=(100, 80, 140)
        )

    def render_ticker(self, buffer) -> None:
        """Render ticker display with phase-specific messages."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import draw_centered_text

        clear(buffer)

        if self._sub_phase == GuessPhase.INTRO:
            draw_centered_text(buffer, "КТО Я?", 2, self._primary)
        elif self._sub_phase == GuessPhase.CAMERA_PREP:
            draw_centered_text(buffer, "КАМЕРА", 2, self._secondary)
        elif self._sub_phase == GuessPhase.CAMERA_CAPTURE:
            cnt = int(self._camera_countdown) + 1
            draw_centered_text(buffer, f"ФОТО: {cnt}", 2, self._secondary)
        elif self._sub_phase == GuessPhase.QUESTIONS:
            idx = self._current_question_idx + 1
            total = len(self._base_questions)
            draw_centered_text(buffer, f"ВОПРОС {idx}/{total}", 2, self._primary)
        elif self._sub_phase == GuessPhase.MORE_QUESTIONS:
            idx = self._current_question_idx + 1
            total = len(self._follow_up_questions)
            draw_centered_text(buffer, f"ЕЩЁ {idx}/{total}", 2, self._secondary)
        elif self._sub_phase in (GuessPhase.ANALYZING, GuessPhase.FINAL_ANALYZING):
            pct = int(self._processing_progress * 100)
            draw_centered_text(buffer, f"ДУМАЮ {pct}%", 2, self._primary)
        elif self._sub_phase == GuessPhase.PROCESSING_IMAGE:
            draw_centered_text(buffer, "РИСУЮ...", 2, self._secondary)
        elif self._sub_phase == GuessPhase.RESULT:
            if self._result_view == "image":
                draw_centered_text(buffer, "ПОРТРЕТ", 2, self._secondary)
            else:
                title = self._guess_title[:12] if self._guess_title else "КТО Я?"
                draw_centered_text(buffer, title, 2, self._primary)

    def get_lcd_text(self) -> str:
        """Return LCD text based on current phase."""
        if self._sub_phase == GuessPhase.INTRO:
            return "    КТО ТЫ?     "
        elif self._sub_phase == GuessPhase.CAMERA_PREP:
            return " LOOK AT CAMERA "
        elif self._sub_phase == GuessPhase.CAMERA_CAPTURE:
            cnt = int(self._camera_countdown) + 1
            return f"   PHOTO: {cnt}     ".center(16)
        elif self._sub_phase == GuessPhase.QUESTIONS:
            idx = self._current_question_idx + 1
            total = len(self._base_questions)
            return f"  Q {idx}/{total} ← NO → YES".center(16)[:16]
        elif self._sub_phase == GuessPhase.MORE_QUESTIONS:
            idx = self._current_question_idx + 1
            total = len(self._follow_up_questions)
            return f" EXTRA {idx}/{total}    ".center(16)[:16]
        elif self._sub_phase in (GuessPhase.ANALYZING, GuessPhase.FINAL_ANALYZING):
            pct = int(self._processing_progress * 100)
            return f" THINKING {pct:3d}% ".center(16)
        elif self._sub_phase == GuessPhase.PROCESSING_IMAGE:
            pct = int(self._processing_progress * 100)
            return f" DRAWING {pct:3d}%  ".center(16)
        elif self._sub_phase == GuessPhase.RESULT:
            if self._result_view == "image":
                return " PRESS TO PRINT "
            else:
                return "   MY GUESS...  "
        return "    GUESS ME    "

"""AI Prophet mode - The KEY mode with camera + AI integration.

This is the flagship mode of VNVNC:
1. Camera captures user photo
2. User answers 5 fun binary questions (left/right buttons)
3. AI analyzes photo and answers to generate personalized prediction
4. AI generates a caricature of the user
5. Combined receipt prints with caricature + prediction + date

Uses Gemini 2.5 Flash for predictions and Imagen 3 for caricatures.
"""

import asyncio
import logging
from typing import Optional, List, Tuple
from datetime import datetime
import random
import math
import numpy as np

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.ai.predictor import PredictionService, Prediction, PredictionCategory
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.simulator.mock_hardware.camera import (
    SimulatorCamera, create_camera, floyd_steinberg_dither, create_viewfinder_overlay
)

logger = logging.getLogger(__name__)


class ProphetPhase:
    """Sub-phases within the AI Prophet mode."""

    INTRO = "intro"              # Welcome animation
    CAMERA_PREP = "camera_prep"  # "Look at camera" prompt
    CAMERA_CAPTURE = "capture"   # Capturing photo
    QUESTIONS = "questions"      # Binary questions
    PROCESSING = "processing"    # AI generation (parallel)
    REVEAL = "reveal"            # Dramatic reveal
    RESULT = "result"            # Final display


# =============================================================================
# FUN GEN-Z RUSSIAN QUESTIONS DATABASE
# =============================================================================
# Each question is (text, trait_key, left_label, right_label, left_meaning, right_meaning)
# - left_label/right_label: What to show on buttons (SHORT - max 6 chars!)
# - left_meaning/right_meaning: What choosing that option means for AI context

QUESTIONS_DATABASE: List[Tuple[str, str, str, str, str, str]] = [
    # Lifestyle & Vibes - Yes/No questions
    ("Скроллишь рилсы перед сном?", "digital_native", "НЕТ", "ДА", "здоровый сон", "зависим от телефона"),
    ("Пойдешь на тусу без инвайта?", "bold", "НЕТ", "ДА", "осторожный", "дерзкий"),
    ("Веришь в гороскопы?", "mystical", "НЕТ", "ДА", "скептик", "верит в знаки"),
    ("Можешь уехать спонтанно?", "spontaneous", "НЕТ", "ДА", "планирует все", "спонтанный"),
    ("Отвечаешь на сообщения сразу?", "responsive", "НЕТ", "ДА", "игнорит", "быстрый"),

    # Social & Relationships
    ("Первым пишешь крашу?", "confident", "НЕТ", "ДА", "стесняшка", "уверенный"),
    ("Постишь сторис каждый день?", "social_media", "НЕТ", "ДА", "скромный", "активный онлайн"),
    ("Легко говоришь с незнакомцами?", "extrovert", "НЕТ", "ДА", "интроверт", "экстраверт"),
    ("Делишься проблемами с друзьями?", "open", "НЕТ", "ДА", "закрытый", "открытый"),
    ("Веришь в любовь с первого взгляда?", "romantic", "НЕТ", "ДА", "реалист", "романтик"),

    # Life Choices - Choice questions (not yes/no!)
    ("Что важнее?", "materialist", "ДЕНЬГИ", "СЛАВА", "материалист", "хочет признания"),
    ("Пойдешь по головам ради цели?", "ambitious", "НЕТ", "ДА", "добрый", "амбициозный"),
    ("Веришь в карму?", "karma", "НЕТ", "ДА", "не верит", "верит в справедливость"),
    ("Готов рискнуть всем?", "risk_taker", "НЕТ", "ДА", "осторожный", "рисковый"),
    ("Что выберешь?", "adventurous", "ПОКОЙ", "ДВИЖ", "стабильность", "приключения"),

    # Personality Quirks
    ("Плачешь от фильмов?", "emotional", "НЕТ", "ДА", "хладнокровный", "эмоциональный"),
    ("Соврешь ради друга?", "protective", "НЕТ", "ДА", "честный", "защитник"),
    ("Веришь в себя?", "self_confident", "НЕТ", "ДА", "сомневается", "уверен"),
    ("Живешь моментом?", "present_focused", "НЕТ", "ДА", "думает о будущем", "здесь и сейчас"),
    ("Делаешь что хочешь?", "independent", "НЕТ", "ДА", "зависит от других", "независимый"),

    # Fun & Random
    ("Пицца с ананасами?", "open_minded", "ФУ", "ОК", "традиционалист", "открыт новому"),
    ("Споришь до победного?", "stubborn", "НЕТ", "ДА", "уступчивый", "упертый"),
    ("Любишь быть в центре?", "attention_seeker", "НЕТ", "ДА", "скромник", "любит внимание"),
    ("Веришь в знаки вселенной?", "spiritual", "НЕТ", "ДА", "рационалист", "духовный"),
    ("Сначала делаешь потом думаешь?", "impulsive", "НЕТ", "ДА", "рассудительный", "импульсивный"),

    # Deep Questions
    ("Простишь предательство?", "forgiving", "НЕТ", "ДА", "злопамятный", "прощает"),
    ("Все к лучшему?", "optimist", "НЕТ", "ДА", "пессимист", "оптимист"),
    ("Изменил бы прошлое?", "content", "НЕТ", "ДА", "доволен жизнью", "хочет перемен"),
    ("Что важнее?", "happiness_focused", "УСПЕХ", "КАЙФ", "карьерист", "гедонист"),
    ("Веришь во вторые шансы?", "hopeful", "НЕТ", "ДА", "разочарован", "верит в людей"),
]

# Number of questions to ask per session
QUESTIONS_PER_SESSION = 5


def get_random_questions(count: int = QUESTIONS_PER_SESSION) -> List[Tuple[str, str, str, str, str, str]]:
    """Get random questions from the database.

    Args:
        count: Number of questions to select

    Returns:
        List of (question, trait_key, left_label, right_label, left_meaning, right_meaning) tuples
    """
    # Seed with current time to ensure different questions each session
    import time
    random.seed(time.time())
    questions = random.sample(QUESTIONS_DATABASE, min(count, len(QUESTIONS_DATABASE)))
    logger.debug(f"Selected questions: {[q[0] for q in questions]}")
    return questions


class AIProphetMode(BaseMode):
    """AI Prophet - Personalized AI fortune telling.

    The signature mode of VNVNC that combines:
    - Live camera capture
    - Personality profiling via 5 fun Gen-Z questions
    - AI-powered prediction generation
    - AI-generated caricature
    - Combined thermal receipt printing

    Flow:
    1. INTRO: Mystical welcome animation
    2. CAMERA_PREP: "Look at the camera" prompt
    3. CAMERA_CAPTURE: Take photo with countdown
    4. QUESTIONS: 5 binary questions (left=no, right=yes)
    5. PROCESSING: AI generates prediction + caricature (parallel)
    6. REVEAL: Dramatic reveal animation
    7. RESULT: Display prediction, offer print
    """

    name = "ai_prophet"
    display_name = "ПРОРОК"
    description = "ИИ предсказание судьбы"
    icon = "@"
    style = "modern"
    requires_camera = True
    requires_ai = True
    estimated_duration = 90  # Longer for 5 questions

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._prediction_service = PredictionService()
        self._caricature_service = CaricatureService()

        # Sub-phase tracking
        self._sub_phase = ProphetPhase.INTRO

        # Camera state
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None  # Current live frame (dithered)
        self._photo_data: Optional[bytes] = None    # Captured JPEG for AI
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0

        # Questions state - randomized from database
        self._questions: List[Tuple[str, str, str, str]] = []
        self._current_question: int = 0
        self._answers: List[bool] = []
        self._answer_meanings: List[str] = []  # Store what each answer means
        self._answer_animation: float = 0.0

        # AI results
        self._prediction: Optional[Prediction] = None
        self._caricature: Optional[Caricature] = None
        self._ai_task: Optional[asyncio.Task] = None
        self._processing_progress: float = 0.0

        # Animation state
        self._reveal_progress: float = 0.0
        self._glow_phase: float = 0.0
        self._scan_line: float = 0.0

        # Particles
        self._particles = ParticleSystem()

        # Colors (modern/tech style)
        self._primary = (59, 130, 246)    # Blue
        self._secondary = (139, 92, 246)   # Purple
        self._accent = (16, 185, 129)      # Teal

    @property
    def is_ai_available(self) -> bool:
        """Check if AI services are available."""
        return (
            self._prediction_service.is_available or
            self._caricature_service.is_available
        )

    def on_enter(self) -> None:
        """Initialize AI Prophet mode."""
        self._sub_phase = ProphetPhase.INTRO
        self._photo_data = None
        self._camera_frame = None
        self._current_question = 0
        self._answers = []
        self._prediction = None
        self._caricature = None
        self._ai_task = None
        self._processing_progress = 0.0
        self._reveal_progress = 0.0

        # Initialize camera for live preview
        self._camera = create_camera(resolution=(640, 480))
        if self._camera.open():
            logger.info("Camera opened for AI Prophet mode")
        else:
            logger.warning("Could not open camera, using placeholder")

        # Reset prediction service
        self._prediction_service.reset_profile()

        # Get randomized questions for this session
        self._questions = get_random_questions(QUESTIONS_PER_SESSION)
        self._answers = []
        self._answer_meanings = []
        logger.info(f"Selected {len(self._questions)} random questions for session")

        # Setup particles (tech style)
        magic_config = ParticlePresets.magic(x=64, y=64)
        magic_config.color = self._secondary
        self._particles.add_emitter("magic", magic_config)

        spark_config = ParticlePresets.sparkle(x=64, y=64)
        spark_config.color = self._accent
        self._particles.add_emitter("sparks", spark_config)

        self.change_phase(ModePhase.INTRO)
        logger.info("AI Prophet mode entered")

    def on_update(self, delta_ms: float) -> None:
        """Update AI Prophet mode."""
        self._particles.update(delta_ms)

        # Animation updates
        self._glow_phase += delta_ms * 0.003
        self._scan_line = (self._scan_line + delta_ms * 0.1) % 128

        # Update live camera preview during camera phases
        if self._sub_phase in (ProphetPhase.CAMERA_PREP, ProphetPhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            if self._sub_phase == ProphetPhase.INTRO:
                # Intro lasts 2.5 seconds
                if self._time_in_phase > 2500:
                    self._sub_phase = ProphetPhase.CAMERA_PREP
                    self._time_in_phase = 0

            elif self._sub_phase == ProphetPhase.CAMERA_PREP:
                # Camera prep for 2 seconds, then start capture
                if self._time_in_phase > 2000:
                    self._start_camera_capture()

            elif self._sub_phase == ProphetPhase.CAMERA_CAPTURE:
                # Countdown animation
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                # Capture the photo when countdown reaches 0
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._flash_alpha = 1.0  # Flash!

                # Flash effect after capture
                if self._time_in_phase > 3000:
                    self._flash_alpha = max(0, 1.0 - (self._time_in_phase - 3000) / 500)

                    if self._time_in_phase > 3500:
                        self._start_questions()

        elif self.phase == ModePhase.ACTIVE:
            # Questions phase
            if self._sub_phase == ProphetPhase.QUESTIONS:
                # Answer animation decay
                self._answer_animation = max(0, self._answer_animation - delta_ms / 300)

        elif self.phase == ModePhase.PROCESSING:
            # Check AI task progress
            if self._ai_task:
                if self._ai_task.done():
                    self._on_ai_complete()
                else:
                    # Fake progress for visual feedback
                    self._processing_progress = min(0.9, self._processing_progress + delta_ms / 10000)

            # Scan line animation
            self._scan_line = (self._time_in_phase / 20) % 128

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == ProphetPhase.REVEAL:
                self._reveal_progress = min(1.0, self._time_in_phase / 2000)

                if self._reveal_progress >= 1.0:
                    self._sub_phase = ProphetPhase.RESULT

            elif self._sub_phase == ProphetPhase.RESULT:
                # Auto-complete after 30 seconds
                if self._time_in_phase > 30000:
                    self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT:
                self._finish()
                return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ProphetPhase.QUESTIONS:
                self._answer_question(False)  # No
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ProphetPhase.QUESTIONS:
                self._answer_question(True)  # Yes
                return True

        return False

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = ProphetPhase.CAMERA_CAPTURE
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
            # Capture current frame
            frame = self._camera.capture_frame()
            if frame is not None and frame.size > 0:
                # Apply Floyd-Steinberg dithering for pixel art effect
                dithered = floyd_steinberg_dither(frame, target_size=(128, 128), threshold=120)
                # Add viewfinder overlay - store as copy to avoid reference issues
                self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()
        except Exception as e:
            logger.warning(f"Camera preview update error: {e}")
            self._camera_frame = None

    def _start_questions(self) -> None:
        """Start the binary questions sequence."""
        self._sub_phase = ProphetPhase.QUESTIONS
        self._current_question = 0
        self._answers = []
        self.change_phase(ModePhase.ACTIVE)

        logger.info("Questions phase started")

    def _answer_question(self, answer: bool) -> None:
        """Record answer and advance to next question.

        Args:
            answer: True for yes (right), False for no (left)
        """
        if self._current_question >= len(self._questions):
            return

        # Unpack 6-tuple format: (question, trait_key, left_label, right_label, left_meaning, right_meaning)
        question_text, trait_key, left_label, right_label, left_meaning, right_meaning = self._questions[self._current_question]

        # Record answer and its meaning
        self._answers.append(answer)
        meaning = right_meaning if answer else left_meaning
        self._answer_meanings.append(meaning)
        self._prediction_service.record_answer(question_text, answer)

        logger.debug(f"Q: {question_text} -> {answer} ({meaning})")

        # Animation trigger
        self._answer_animation = 1.0

        # Advance or finish
        self._current_question += 1

        if self._current_question >= len(self._questions):
            # All questions answered, start AI processing
            self._start_processing()
        else:
            logger.debug(f"Question {self._current_question}/{len(self._questions)}")

    def _start_processing(self) -> None:
        """Start AI processing (prediction + caricature in parallel)."""
        self._sub_phase = ProphetPhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)
        self._processing_progress = 0.0

        # Start async AI task
        self._ai_task = asyncio.create_task(self._run_ai_generation())

        # Burst particles
        magic = self._particles.get_emitter("magic")
        if magic:
            magic.burst(50)

        logger.info("AI processing started")

    def _build_personality_context(self) -> str:
        """Build a personality context string from questions and answers.

        This provides rich context to AI models about the user's personality
        based on their answers to the fun Gen-Z questions.
        """
        if not self._questions or not self._answer_meanings:
            return ""

        context_parts = ["Профиль личности по ответам:"]
        for i, (q_tuple, meaning) in enumerate(zip(self._questions, self._answer_meanings)):
            question_text = q_tuple[0]
            context_parts.append(f"• {question_text} → {meaning}")

        return "\n".join(context_parts)

    async def _run_ai_generation(self) -> None:
        """Run AI generation tasks in parallel."""
        try:
            # Build personality context from answers
            personality_context = self._build_personality_context()
            logger.info(f"Personality context:\n{personality_context}")

            # Prediction task
            async def generate_prediction():
                if self._photo_data:
                    await self._prediction_service.analyze_photo(self._photo_data)
                return await self._prediction_service.generate_prediction(
                    category=PredictionCategory.MYSTICAL,
                    extra_context=personality_context,
                )

            # Caricature task
            async def generate_caricature():
                if self._photo_data:
                    return await self._caricature_service.generate_caricature(
                        reference_photo=self._photo_data,
                        style=CaricatureStyle.MYSTICAL,
                        personality_context=personality_context,
                    )
                else:
                    # No photo, generate simple caricature
                    return await self._caricature_service.generate_simple_caricature(
                        style=CaricatureStyle.MYSTICAL
                    )

            # Run in parallel
            prediction_task = asyncio.create_task(generate_prediction())
            caricature_task = asyncio.create_task(generate_caricature())

            # Wait for both (with timeout)
            try:
                self._prediction = await asyncio.wait_for(prediction_task, timeout=60.0)
            except asyncio.TimeoutError:
                logger.warning("Prediction generation timed out")
                self._prediction = self._prediction_service._fallback_prediction()

            try:
                self._caricature = await asyncio.wait_for(caricature_task, timeout=120.0)
            except asyncio.TimeoutError:
                logger.warning("Caricature generation timed out")
                self._caricature = None

            logger.info("AI generation complete")

        except Exception as e:
            logger.error(f"AI generation failed: {e}")
            # Use fallback prediction
            self._prediction = self._prediction_service._fallback_prediction()

    def _on_ai_complete(self) -> None:
        """Handle completion of AI processing."""
        self._processing_progress = 1.0
        self._sub_phase = ProphetPhase.REVEAL
        self.change_phase(ModePhase.RESULT)
        self._reveal_progress = 0.0

        # Burst particles for reveal
        sparks = self._particles.get_emitter("sparks")
        if sparks:
            sparks.burst(100)

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
        prediction_text = ""
        if self._prediction:
            prediction_text = self._prediction.text
            # Note: No lucky number added - each prediction is unique!

        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=prediction_text,
            ticker_text=prediction_text,
            lcd_text="ИИ ПРОРОК".center(16),
            should_print=True,
            print_data={
                "prediction": prediction_text,
                "caricature": self._caricature.image_data if self._caricature else None,
                "answers": self._answers,
                "timestamp": datetime.now().isoformat(),
                "type": "ai_prophet"
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_circle, draw_rect, draw_line
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        # Dark tech background
        fill(buffer, (5, 10, 20))

        font = load_font("cyrillic")

        if self._sub_phase == ProphetPhase.INTRO:
            self._render_intro(buffer, font)

        elif self._sub_phase == ProphetPhase.CAMERA_PREP:
            self._render_camera_prep(buffer, font)

        elif self._sub_phase == ProphetPhase.CAMERA_CAPTURE:
            self._render_camera_capture(buffer, font)

        elif self._sub_phase == ProphetPhase.QUESTIONS:
            self._render_questions(buffer, font)

        elif self._sub_phase == ProphetPhase.PROCESSING:
            self._render_processing(buffer, font)

        elif self._sub_phase in (ProphetPhase.REVEAL, ProphetPhase.RESULT):
            self._render_result(buffer, font)

        # Render particles on top
        self._particles.render(buffer)

        # Flash effect
        if self._flash_alpha > 0:
            alpha = int(255 * self._flash_alpha)
            fill(buffer, (alpha, alpha, alpha))

    def _render_intro(self, buffer, font) -> None:
        """Render intro animation."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.text_utils import draw_centered_text

        # Pulsing eye/orb
        pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)
        radius = int(30 * pulse)

        # Outer glow
        for r in range(radius + 20, radius, -2):
            alpha = (r - radius) / 20 * 0.5
            color = tuple(int(c * alpha) for c in self._secondary)
            draw_circle(buffer, 64, 45, r, color, filled=False)

        # Core
        draw_circle(buffer, 64, 45, radius, self._primary)
        draw_circle(buffer, 64, 45, radius - 5, (30, 50, 80))

        # Inner highlight
        draw_circle(buffer, 58, 39, 8, (100, 150, 200))

        # Title - centered, positioned safely
        draw_centered_text(buffer, "ИИ ПРОРОК", 90, self._accent, scale=2)
        draw_centered_text(buffer, "Судьба ждёт", 110, (100, 100, 120), scale=1)

    def _render_camera_prep(self, buffer, font) -> None:
        """Render camera preparation screen with live dithered preview."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        import numpy as np

        # Show live camera preview if available
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

        # Overlay text on top of the preview
        draw_centered_text(buffer, "СМОТРИ В КАМЕРУ", 95, self._accent, scale=1)
        draw_centered_text(buffer, "ПРИГОТОВЬСЯ...", 110, (255, 200, 100), scale=1)

    def _render_camera_capture(self, buffer, font) -> None:
        """Render camera capture with countdown and live preview."""
        from artifact.graphics.primitives import draw_circle, draw_rect, fill
        from artifact.graphics.text_utils import draw_centered_text
        import numpy as np

        # Show live camera preview as background
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

        # Countdown number - large and centered
        if self._camera_countdown > 0:
            countdown_num = str(int(self._camera_countdown) + 1)
            scale = 4 + int((self._camera_countdown % 1) * 2)
            draw_centered_text(buffer, countdown_num, 45, (255, 255, 255), scale=scale)

            # Progress ring around countdown
            progress = 1.0 - (self._camera_countdown % 1)
            for angle in range(0, int(360 * progress), 10):
                rad = math.radians(angle - 90)
                px = int(64 + 45 * math.cos(rad))
                py = int(64 + 45 * math.sin(rad))
                draw_circle(buffer, px, py, 2, self._secondary)

        # Flash effect when capturing
        if self._flash_alpha > 0:
            # White flash overlay
            flash_color = tuple(int(255 * self._flash_alpha) for _ in range(3))
            # Blend flash into buffer
            buffer[:, :] = np.clip(
                buffer.astype(np.int16) + int(255 * self._flash_alpha),
                0, 255
            ).astype(np.uint8)
            draw_centered_text(buffer, "ФОТО!", 60, (50, 50, 50), scale=2)

    def _render_questions(self, buffer, font) -> None:
        """Render binary question screen with animated effects."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.fonts import draw_text_bitmap
        from artifact.graphics.text_utils import (
            draw_animated_text, draw_centered_text, draw_wrapped_text,
            TextEffect, smart_wrap_text, MAIN_DISPLAY_WIDTH
        )

        if self._current_question >= len(self._questions):
            return

        # Unpack question - now includes button labels!
        # Format: (text, trait_key, left_label, right_label, left_meaning, right_meaning)
        q = self._questions[self._current_question]
        question_text = q[0]
        left_label = q[2]   # e.g., "НЕТ" or "ДЕНЬГИ"
        right_label = q[3]  # e.g., "ДА" or "СЛАВА"

        # Question number with glow - compact at top
        q_num = f"{self._current_question + 1}/{len(self._questions)}"
        draw_animated_text(buffer, q_num, 2, self._secondary, self._time_in_phase, TextEffect.GLOW, scale=1)

        # Question text - try scale=2 first, fallback to scale=1 for long questions
        margin = 4
        available_width = MAIN_DISPLAY_WIDTH - margin * 2
        lines_s2 = smart_wrap_text(question_text, available_width, font, scale=2)

        # Use scale=2 if fits in 4 lines, else scale=1
        if len(lines_s2) <= 4:
            lines = lines_s2
            scale = 2
            line_height = 16
            start_y = 14
        else:
            lines = smart_wrap_text(question_text, available_width, font, scale=1)
            scale = 1
            line_height = 10
            start_y = 14

        # Draw wrapped question text centered
        y = start_y
        max_lines = 4 if scale == 2 else 6
        for i, line in enumerate(lines[:max_lines]):
            # Pulse effect for emphasis
            pulse = 0.85 + 0.15 * math.sin(self._time_in_phase / 300 + i * 0.3)
            color = tuple(int(255 * pulse) for _ in range(3))
            draw_centered_text(buffer, line, y, color, scale=scale)
            y += line_height

        # Answer buttons - positioned below question text
        btn_y = 92
        btn_h = 20

        # Determine button highlight based on answer
        left_active = self._answer_animation > 0 and len(self._answers) > 0 and not self._answers[-1]
        right_active = self._answer_animation > 0 and len(self._answers) > 0 and self._answers[-1]

        # Button backgrounds with pulse effect
        left_pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 200) if left_active else 1.0
        right_pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 200) if right_active else 1.0

        left_color = tuple(int(c * left_pulse) for c in ((255, 100, 100) if left_active else (100, 50, 50)))
        right_color = tuple(int(c * right_pulse) for c in ((100, 255, 100) if right_active else (50, 100, 50)))

        # Draw button boxes
        draw_rect(buffer, 4, btn_y, 56, btn_h, left_color)
        draw_rect(buffer, 68, btn_y, 56, btn_h, right_color)

        # Draw DYNAMIC button labels from question data
        # Left button with arrow
        left_text = f"<{left_label}"
        left_w, _ = font.measure_text(left_text)
        left_x = 4 + (56 - left_w) // 2
        left_text_pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)
        left_text_color = tuple(int(255 * left_text_pulse) for _ in range(3))
        draw_text_bitmap(buffer, left_text, left_x, btn_y + 5, left_text_color, font, scale=1)

        # Right button with arrow
        right_text = f"{right_label}>"
        right_w, _ = font.measure_text(right_text)
        right_x = 68 + (56 - right_w) // 2
        right_text_pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300 + math.pi)
        right_text_color = tuple(int(255 * right_text_pulse) for _ in range(3))
        draw_text_bitmap(buffer, right_text, right_x, btn_y + 5, right_text_color, font, scale=1)

        # Hint at bottom - simpler
        draw_centered_text(buffer, "< / >", 118, (80, 80, 100), scale=1)

    def _render_processing(self, buffer, font) -> None:
        """Render AI processing animation with dramatic effects."""
        from artifact.graphics.primitives import draw_rect, draw_line
        from artifact.graphics.text_utils import (
            draw_animated_text, draw_centered_text, TextEffect
        )

        # Scan lines effect - CRT style
        for y in range(0, 128, 4):
            alpha = 0.15 + 0.15 * math.sin((y + self._time_in_phase / 30) / 8)
            color = tuple(int(c * alpha) for c in self._secondary)
            draw_line(buffer, 0, y, 127, y, color)

        # Dramatic processing text with glitch effect - CENTERED
        draw_animated_text(
            buffer, "ЧТЕНИЕ", 40,
            self._accent, self._time_in_phase,
            TextEffect.GLITCH, scale=2
        )

        # Animated dots below
        dots = "." * (int(self._time_in_phase / 300) % 4)
        draw_centered_text(buffer, dots, 58, self._accent, scale=2)

        # Progress bar - centered
        bar_w, bar_h = 100, 6
        bar_x = (128 - bar_w) // 2
        bar_y = 72

        # Background with glow
        draw_rect(buffer, bar_x - 2, bar_y - 2, bar_w + 4, bar_h + 4, (20, 20, 35))
        draw_rect(buffer, bar_x, bar_y, bar_w, bar_h, (40, 40, 60))

        # Progress fill with animation
        progress_w = int(bar_w * self._processing_progress)
        if progress_w > 0:
            # Gradient fill
            for px in range(progress_w):
                pulse = 0.8 + 0.2 * math.sin(self._time_in_phase / 100 + px * 0.1)
                color = tuple(int(c * pulse) for c in self._accent)
                buffer[bar_y:bar_y + bar_h, bar_x + px] = color

        # Scanning indicator
        scan_x = bar_x + int((self._time_in_phase / 10) % bar_w)
        for sx in range(max(bar_x, scan_x - 3), min(bar_x + bar_w, scan_x + 3)):
            brightness = 1.0 - abs(sx - scan_x) / 3
            glow = tuple(int(255 * brightness) for _ in range(3))
            buffer[bar_y:bar_y + bar_h, sx] = np.clip(
                buffer[bar_y:bar_y + bar_h, sx].astype(np.int16) + np.array(glow),
                0, 255
            ).astype(np.uint8)

        # Status text with wave effect - CENTERED
        draw_animated_text(
            buffer, "Анализ судьбы", 95,
            (120, 150, 180), self._time_in_phase,
            TextEffect.WAVE, scale=1
        )

    def _render_result(self, buffer, font) -> None:
        """Render prediction result with caricature and text alternating.

        The result screen alternates between:
        - Caricature display (if available)
        - Prediction text display

        This creates a dynamic presentation showing both the AI-generated
        caricature of the user and their fortune prediction.
        """
        from artifact.graphics.primitives import draw_rect, fill
        from artifact.graphics.text_utils import (
            draw_animated_text, draw_centered_text, smart_wrap_text,
            TextEffect, MAIN_DISPLAY_WIDTH
        )
        from io import BytesIO

        if not self._prediction:
            return

        # Alternate between caricature and prediction every 5 seconds
        show_caricature = self._caricature is not None and (int(self._time_in_phase / 5000) % 2 == 0)

        if show_caricature and self._sub_phase == ProphetPhase.RESULT:
            # Render caricature
            self._render_caricature(buffer, font)
        else:
            # Render prediction text
            self._render_prediction_text(buffer, font)

    def _render_caricature(self, buffer, font) -> None:
        """Render the AI-generated caricature."""
        from artifact.graphics.primitives import fill, draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from io import BytesIO

        if not self._caricature:
            return

        try:
            from PIL import Image

            # Load caricature image
            img = Image.open(BytesIO(self._caricature.image_data))
            img = img.convert("RGB")

            # Resize to fit display (with border)
            display_size = 100
            img = img.resize((display_size, display_size), Image.Resampling.NEAREST)

            # Center position
            x_offset = (128 - display_size) // 2
            y_offset = 5

            # Copy pixels to buffer
            for y in range(display_size):
                for x in range(display_size):
                    bx = x_offset + x
                    by = y_offset + y
                    if 0 <= bx < 128 and 0 <= by < 128:
                        pixel = img.getpixel((x, y))
                        buffer[by, bx] = pixel

            # Add decorative border
            border_color = self._secondary
            draw_rect(buffer, x_offset - 2, y_offset - 2, display_size + 4, display_size + 4, border_color, filled=False)

            # Label at bottom
            draw_centered_text(buffer, "ТВОЯ КАРИКАТУРА", 112, self._accent, scale=1)

        except Exception as e:
            logger.warning(f"Failed to render caricature: {e}")
            # Fallback to prediction text
            self._render_prediction_text(buffer, font)

    def _render_prediction_text(self, buffer, font) -> None:
        """Render the prediction text with effects - auto-scales to fit."""
        from artifact.graphics.text_utils import (
            draw_animated_text, draw_centered_text, smart_wrap_text,
            TextEffect, MAIN_DISPLAY_WIDTH
        )

        if not self._prediction:
            return

        # Try scale=2 first, fall back to scale=1 for long predictions
        margin = 4
        available_width = MAIN_DISPLAY_WIDTH - margin * 2

        # Check if text fits at scale=2 (max 6 lines to fit on screen)
        lines_scale2 = smart_wrap_text(self._prediction.text, available_width, font, scale=2)

        if len(lines_scale2) <= 6:
            # Fits at scale=2
            scale = 2
            lines = lines_scale2
            line_height = 18
            max_lines = 6
            start_y = 8
        else:
            # Use scale=1 for longer text
            scale = 1
            lines = smart_wrap_text(self._prediction.text, available_width, font, scale=1)
            line_height = 10
            max_lines = 11  # More lines fit at scale=1
            start_y = 5

        y = start_y
        for i, line in enumerate(lines[:max_lines]):
            # Staggered reveal animation
            if self._sub_phase == ProphetPhase.REVEAL:
                line_alpha = min(1.0, self._reveal_progress * (max_lines / 2) - i * 0.5)
                if line_alpha <= 0:
                    continue
                color = tuple(int(255 * line_alpha) for _ in range(3))
                draw_centered_text(buffer, line, y, color, scale=scale)
            else:
                # Full display with wave effect
                wave_y = y + int(1.5 * math.sin(self._time_in_phase / 200 + i * 0.4))
                pulse = 0.85 + 0.15 * math.sin(self._time_in_phase / 300 + i * 0.3)
                color = tuple(int(255 * pulse) for _ in range(3))
                draw_centered_text(buffer, line, wave_y, color, scale=scale)
            y += line_height

        # Show "НАЖМИ" hint at bottom only in result phase
        if self._sub_phase == ProphetPhase.RESULT:
            hint_y = 118
            if int(self._time_in_phase / 600) % 2 == 0:
                draw_centered_text(buffer, "НАЖМИ", hint_y, (100, 100, 120), scale=1)

    def render_ticker(self, buffer) -> None:
        """Render ticker with smooth seamless scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, render_ticker_static, TickerEffect, TextEffect

        clear(buffer)

        if self._sub_phase == ProphetPhase.INTRO:
            # Intro with rainbow
            render_ticker_animated(
                buffer, "ИИ ПРОРОК - СУДЬБА ЖДЁТ",
                self._time_in_phase, self._primary,
                TickerEffect.RAINBOW_SCROLL, speed=0.025
            )

        elif self._sub_phase in (ProphetPhase.CAMERA_PREP, ProphetPhase.CAMERA_CAPTURE):
            # Camera phase with pulse
            render_ticker_animated(
                buffer, "СМОТРИ В КАМЕРУ",
                self._time_in_phase, self._accent,
                TickerEffect.PULSE_SCROLL, speed=0.028
            )

        elif self._sub_phase == ProphetPhase.QUESTIONS:
            # Question indicator as static centered text
            text = f"ВОПРОС {self._current_question + 1}/{len(self._questions)}"
            render_ticker_static(
                buffer, text,
                self._time_in_phase, self._accent,
                TextEffect.GLOW
            )

        elif self._sub_phase == ProphetPhase.PROCESSING:
            # Processing with glitch effect
            render_ticker_animated(
                buffer, "ИИ АНАЛИЗИРУЕТ СУДЬБУ",
                self._time_in_phase, self._secondary,
                TickerEffect.GLITCH_SCROLL, speed=0.03
            )

        elif self._sub_phase == ProphetPhase.RESULT and self._prediction:
            # Result prediction with wave
            render_ticker_animated(
                buffer, self._prediction.text,
                self._time_in_phase, self._accent,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )

        else:
            # Default fallback
            render_ticker_animated(
                buffer, "ИИ ПРОРОК",
                self._time_in_phase, self._primary,
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

    def get_lcd_text(self) -> str:
        """Get LCD text with fun symbols."""
        if self._sub_phase == ProphetPhase.CAMERA_PREP:
            # Blinking eye effect
            frame = int(self._time_in_phase / 300) % 2
            eye = "◉" if frame == 0 else "◎"
            return f" {eye} В КАМЕРУ {eye} ".center(16)[:16]
        elif self._sub_phase == ProphetPhase.CAMERA_CAPTURE:
            countdown = int(self._camera_countdown) + 1
            return f" ★ ФОТО: {countdown} ★ ".center(16)[:16]
        elif self._sub_phase == ProphetPhase.QUESTIONS:
            # Use arrows instead of Л/П
            return f"← НЕТ ○ → ДА".center(16)[:16]
        elif self._sub_phase == ProphetPhase.PROCESSING:
            # Animated thinking
            dots = "◐◓◑◒"
            dot = dots[int(self._time_in_phase / 200) % 4]
            return f" {dot} ИИ ДУМАЕТ {dot} ".center(16)[:16]
        elif self._sub_phase == ProphetPhase.RESULT:
            return " ★ ПРОРОЧЕСТВО ★ ".center(16)[:16]
        return " ◆ ИИ ПРОРОК ◆ ".center(16)

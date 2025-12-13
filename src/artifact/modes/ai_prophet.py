"""AI Prophet mode - The KEY mode with camera + AI integration.

This is the flagship mode of ARTIFACT:
1. Camera captures user photo
2. User answers 3-5 binary questions (left/right buttons)
3. AI analyzes photo and answers to generate personalized prediction
4. AI generates a caricature of the user
5. Combined receipt prints with caricature + prediction + date

Uses Gemini 2.5 Flash for predictions and Imagen 3 for caricatures.
"""

import asyncio
import logging
from typing import Optional, List
from datetime import datetime
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.timeline import Timeline
from artifact.animation.easing import Easing
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.ai.predictor import PredictionService, Prediction, PredictionCategory
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle

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


# Russian questions with trait keys
QUESTIONS_RU = [
    ("Ты любишь приключения?", "adventure"),
    ("Ты доверяешь интуиции?", "intuition"),
    ("Ты предпочитаешь действовать?", "action"),
    ("Ты веришь в судьбу?", "fate"),
    ("Ты любишь перемены?", "change"),
]


class AIProphetMode(BaseMode):
    """AI Prophet - Personalized AI fortune telling.

    The signature mode of ARTIFACT that combines:
    - Live camera capture
    - Personality profiling via binary questions
    - AI-powered prediction generation
    - AI-generated caricature
    - Combined thermal receipt printing

    Flow:
    1. INTRO: Mystical welcome animation
    2. CAMERA_PREP: "Look at the camera" prompt
    3. CAMERA_CAPTURE: Take photo with countdown
    4. QUESTIONS: 3-5 binary questions (left=no, right=yes)
    5. PROCESSING: AI generates prediction + caricature (parallel)
    6. REVEAL: Dramatic reveal animation
    7. RESULT: Display prediction, offer print
    """

    name = "ai_prophet"
    display_name = "PROPHET"
    description = "AI-powered personalized fortune"
    icon = "@"
    style = "modern"
    requires_camera = True
    requires_ai = True
    estimated_duration = 60

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._prediction_service = PredictionService()
        self._caricature_service = CaricatureService()

        # Sub-phase tracking
        self._sub_phase = ProphetPhase.INTRO

        # Camera state
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0

        # Questions state
        self._questions = QUESTIONS_RU[:3]  # Use 3 questions by default
        self._current_question: int = 0
        self._answers: List[bool] = []
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
        self._current_question = 0
        self._answers = []
        self._prediction = None
        self._caricature = None
        self._ai_task = None
        self._processing_progress = 0.0
        self._reveal_progress = 0.0

        # Reset prediction service
        self._prediction_service.reset_profile()

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
        if event.event_type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT:
                self._finish()
                return True

        elif event.event_type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ProphetPhase.QUESTIONS:
                self._answer_question(False)  # No
                return True

        elif event.event_type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == ProphetPhase.QUESTIONS:
                self._answer_question(True)  # Yes
                return True

        return False

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = ProphetPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0

        # TODO: Actually capture from camera
        # For now, use placeholder
        self._photo_data = None  # Would be camera.capture()

        logger.info("Camera capture started")

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

        question_text, trait_key = self._questions[self._current_question]

        # Record answer
        self._answers.append(answer)
        self._prediction_service.record_answer(question_text, answer)

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

    async def _run_ai_generation(self) -> None:
        """Run AI generation tasks in parallel."""
        try:
            # Create parallel tasks
            tasks = []

            # Prediction task
            async def generate_prediction():
                if self._photo_data:
                    await self._prediction_service.analyze_photo(self._photo_data)
                return await self._prediction_service.generate_prediction(
                    category=PredictionCategory.MYSTICAL
                )

            # Caricature task
            async def generate_caricature():
                if self._photo_data:
                    return await self._caricature_service.generate_caricature(
                        reference_photo=self._photo_data,
                        style=CaricatureStyle.MYSTICAL,
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

        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        prediction_text = ""
        if self._prediction:
            prediction_text = self._prediction.text
            if self._prediction.lucky_number:
                prediction_text += f" #{self._prediction.lucky_number}"

        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=prediction_text,
            ticker_text=prediction_text,
            lcd_text="AI PROPHET".center(16),
            should_print=True,
            print_data={
                "prediction": prediction_text,
                "lucky_number": self._prediction.lucky_number if self._prediction else None,
                "lucky_color": self._prediction.lucky_color if self._prediction else None,
                "traits": self._prediction.traits if self._prediction else [],
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

        font = load_font("default")

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
        from artifact.graphics.fonts import draw_text_bitmap

        # Pulsing eye/orb
        pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)
        radius = int(30 * pulse)

        # Outer glow
        for r in range(radius + 20, radius, -2):
            alpha = (r - radius) / 20 * 0.5
            color = tuple(int(c * alpha) for c in self._secondary)
            draw_circle(buffer, 64, 50, r, color, filled=False)

        # Core
        draw_circle(buffer, 64, 50, radius, self._primary)
        draw_circle(buffer, 64, 50, radius - 5, (30, 50, 80))

        # Inner highlight
        draw_circle(buffer, 58, 44, 8, (100, 150, 200))

        # Title
        draw_text_bitmap(buffer, "AI PROPHET", 25, 95, self._accent, font, scale=2)
        draw_text_bitmap(buffer, "Your fate awaits", 20, 115, (100, 100, 120), font, scale=1)

    def _render_camera_prep(self, buffer, font) -> None:
        """Render camera preparation screen."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.fonts import draw_text_bitmap

        # Camera frame
        frame_x, frame_y = 24, 20
        frame_w, frame_h = 80, 70

        # Animated corners
        corner_len = 10
        blink = int(self._time_in_phase / 300) % 2 == 0
        color = self._accent if blink else self._primary

        # Top-left
        draw_rect(buffer, frame_x, frame_y, corner_len, 2, color)
        draw_rect(buffer, frame_x, frame_y, 2, corner_len, color)

        # Top-right
        draw_rect(buffer, frame_x + frame_w - corner_len, frame_y, corner_len, 2, color)
        draw_rect(buffer, frame_x + frame_w - 2, frame_y, 2, corner_len, color)

        # Bottom-left
        draw_rect(buffer, frame_x, frame_y + frame_h - 2, corner_len, 2, color)
        draw_rect(buffer, frame_x, frame_y + frame_h - corner_len, 2, corner_len, color)

        # Bottom-right
        draw_rect(buffer, frame_x + frame_w - corner_len, frame_y + frame_h - 2, corner_len, 2, color)
        draw_rect(buffer, frame_x + frame_w - 2, frame_y + frame_h - corner_len, 2, corner_len, color)

        # Text
        draw_text_bitmap(buffer, "LOOK AT CAMERA", 15, 100, self._accent, font, scale=1)
        draw_text_bitmap(buffer, "GET READY...", 30, 115, self._secondary, font, scale=1)

    def _render_camera_capture(self, buffer, font) -> None:
        """Render camera capture with countdown."""
        from artifact.graphics.primitives import draw_circle
        from artifact.graphics.fonts import draw_text_bitmap

        # Countdown number
        if self._camera_countdown > 0:
            countdown_num = str(int(self._camera_countdown) + 1)
            scale = 5 + int((self._camera_countdown % 1) * 2)
            x = 64 - scale * 3
            y = 50 - scale * 4
            draw_text_bitmap(buffer, countdown_num, x, y, self._accent, font, scale=scale)

            # Progress ring
            progress = 1.0 - (self._camera_countdown % 1)
            for angle in range(0, int(360 * progress), 10):
                rad = math.radians(angle - 90)
                px = int(64 + 50 * math.cos(rad))
                py = int(64 + 50 * math.sin(rad))
                draw_circle(buffer, px, py, 2, self._secondary)

    def _render_questions(self, buffer, font) -> None:
        """Render binary question screen."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.fonts import draw_text_bitmap

        if self._current_question >= len(self._questions):
            return

        question_text, _ = self._questions[self._current_question]

        # Question number
        q_num = f"{self._current_question + 1}/{len(self._questions)}"
        draw_text_bitmap(buffer, q_num, 55, 10, self._secondary, font, scale=1)

        # Question text (word wrap)
        words = question_text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + " " + word if current_line else word
            if len(test_line) <= 12:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        y = 35
        for line in lines[:3]:
            line_w = len(line) * 8
            x = (128 - line_w) // 2
            draw_text_bitmap(buffer, line, x, y, (255, 255, 255), font, scale=2)
            y += 18

        # Answer buttons
        btn_y = 95

        # Left = No
        no_color = (255, 100, 100) if self._answer_animation > 0 and len(self._answers) > 0 and not self._answers[-1] else (150, 50, 50)
        draw_rect(buffer, 10, btn_y, 45, 25, no_color)
        draw_text_bitmap(buffer, "< НЕТ", 15, btn_y + 8, (255, 255, 255), font, scale=1)

        # Right = Yes
        yes_color = (100, 255, 100) if self._answer_animation > 0 and len(self._answers) > 0 and self._answers[-1] else (50, 150, 50)
        draw_rect(buffer, 73, btn_y, 45, 25, yes_color)
        draw_text_bitmap(buffer, "ДА >", 83, btn_y + 8, (255, 255, 255), font, scale=1)

    def _render_processing(self, buffer, font) -> None:
        """Render AI processing animation."""
        from artifact.graphics.primitives import draw_rect, draw_line
        from artifact.graphics.fonts import draw_text_bitmap

        # Scan lines effect
        for y in range(0, 128, 8):
            alpha = 0.1 + 0.1 * math.sin((y + self._time_in_phase / 50) / 10)
            color = tuple(int(c * alpha) for c in self._secondary)
            draw_line(buffer, 0, y, 127, y, color)

        # Processing text
        dots = "." * (int(self._time_in_phase / 500) % 4)
        draw_text_bitmap(buffer, f"READING{dots}", 30, 50, self._accent, font, scale=2)

        # Progress bar
        bar_x, bar_y = 20, 75
        bar_w, bar_h = 88, 8

        draw_rect(buffer, bar_x, bar_y, bar_w, bar_h, (30, 30, 50))
        progress_w = int(bar_w * self._processing_progress)
        if progress_w > 0:
            draw_rect(buffer, bar_x, bar_y, progress_w, bar_h, self._accent)

        # Status text
        status = "Analyzing your destiny..."
        draw_text_bitmap(buffer, status, 10, 95, (100, 100, 120), font, scale=1)

    def _render_result(self, buffer, font) -> None:
        """Render prediction result."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.fonts import draw_text_bitmap

        if not self._prediction:
            return

        # Apply reveal animation
        alpha_factor = min(1.0, self._reveal_progress * 2) if self._sub_phase == ProphetPhase.REVEAL else 1.0

        # Prediction text (word wrap)
        prediction_text = self._prediction.text
        words = prediction_text.split()
        lines = []
        current_line = ""

        for word in words:
            test_line = current_line + " " + word if current_line else word
            if len(test_line) <= 12:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        y = 15
        for i, line in enumerate(lines[:5]):
            # Staggered reveal
            line_alpha = min(1.0, (self._reveal_progress * 5 - i) if self._sub_phase == ProphetPhase.REVEAL else 1.0)
            if line_alpha > 0:
                color = tuple(int(c * line_alpha) for c in (255, 255, 255))
                line_w, _ = font.measure_text(line)
                x = (128 - line_w * 2) // 2
                draw_text_bitmap(buffer, line, x, y, color, font, scale=2)
            y += 18

        # Lucky number and color
        if self._sub_phase == ProphetPhase.RESULT:
            if self._prediction.lucky_number:
                draw_text_bitmap(
                    buffer, f"#{self._prediction.lucky_number}",
                    10, 105, self._accent, font, scale=2
                )

            if self._prediction.lucky_color:
                draw_text_bitmap(
                    buffer, self._prediction.lucky_color,
                    70, 108, self._secondary, font, scale=1
                )

    def render_ticker(self, buffer) -> None:
        """Render ticker display."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        clear(buffer)
        font = load_font("default")

        if self._sub_phase == ProphetPhase.QUESTIONS:
            text = f"QUESTION {self._current_question + 1}/{len(self._questions)}"
            draw_text_bitmap(buffer, text, 2, 1, self._accent, font, scale=1)

        elif self._sub_phase == ProphetPhase.PROCESSING:
            text = "AI ANALYZING... "
            scroll = int(self._time_in_phase / 80) % (len(text) * 4 + 48)
            draw_text_bitmap(buffer, text * 2, 48 - scroll, 1, self._secondary, font, scale=1)

        elif self._sub_phase == ProphetPhase.RESULT and self._prediction:
            text = self._prediction.text + " "
            scroll = int(self._time_in_phase / 100) % (len(text) * 4 + 48)
            draw_text_bitmap(buffer, text, 48 - scroll, 1, self._accent, font, scale=1)

        else:
            text = "AI PROPHET - YOUR DESTINY AWAITS "
            scroll = int(self._time_in_phase / 80) % (len(text) * 4 + 48)
            draw_text_bitmap(buffer, text, 48 - scroll, 1, self._primary, font, scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self._sub_phase == ProphetPhase.CAMERA_PREP:
            return "LOOK AT CAMERA".center(16)
        elif self._sub_phase == ProphetPhase.CAMERA_CAPTURE:
            return f"PHOTO IN {int(self._camera_countdown) + 1}...".center(16)
        elif self._sub_phase == ProphetPhase.QUESTIONS:
            return f"Q{self._current_question + 1}: L=NO R=YES".center(16)[:16]
        elif self._sub_phase == ProphetPhase.PROCESSING:
            return "AI THINKING...".center(16)
        elif self._sub_phase == ProphetPhase.RESULT:
            return "YOUR PROPHECY".center(16)
        return "AI PROPHET".center(16)

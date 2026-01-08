"""Bad Santa Mode - Naughty/Nice Determination with Adult Humor.

An R-rated mode where you answer questions to determine if you've been
naughty or nice. Winners (80%+ nice) get a free shot prize!
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
from artifact.utils.coupon_service import get_coupon_service, CouponResult
from artifact.utils.s3_upload import AsyncUploader, UploadResult
from artifact.audio.engine import get_audio_engine
import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# QUESTION DATABASE - Naughty/Nice Questions (Adult humor, Russian)
# Format: (question, [naughty_answer, nice_answer], is_naughty_0_or_nice_1)
# Higher nice_score = more deserving of gift
# =============================================================================

@dataclass
class BadSantaQuestion:
    """A naughty/nice determination question."""
    text: str
    options: List[str]  # [naughty_option, nice_option]
    # Points for each answer: index 0 = first option points, index 1 = second option points
    # Higher = more nice
    nice_points: List[int]  # e.g., [0, 10] means first option = 0 nice, second = 10 nice


# Question bank - mix of funny and revealing questions (adult humor)
BAD_SANTA_QUESTIONS: List[BadSantaQuestion] = [
    # Behavior questions
    BadSantaQuestion(
        "Сколько раз ты напился на корпоративе в этом году?",
        ["Больше чем пальцев на руках", "Я был(а) примером трезвости"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Врал ли ты родителям в этом году?",
        ["Да, и не раз, и не два...", "Я всегда говорю правду (почти)"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Звонил(а) бывшим пьяным?",
        ["Было дело... возможно несколько раз", "У меня есть чувство достоинства"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Крал(а) еду из офисного холодильника?",
        ["А чьи это были чипсы?", "Никогда! Чужое - священно"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Сколько раз симулировал(а) болезнь на работе?",
        ["Кхе-кхе... достаточно", "Я болею только по-настоящему"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Сплетничал(а) о коллегах?",
        ["Это называется 'обмен информацией'", "Я выше этого"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Опаздывал(а) на важные встречи?",
        ["Время - понятие относительное", "Я всегда прихожу вовремя"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Листал(а) тиндер на работе?",
        ["А что ещё делать на совещаниях?", "Работа - это святое"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Притворялся что не видишь знакомых на улице?",
        ["Это искусство, которым я владею", "Я всегда здороваюсь"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Ел(а) последний кусок торта не спрашивая?",
        ["Кто первый встал - того и тапки", "Всегда делюсь с ближними"],
        [0, 10]
    ),

    # More naughty questions
    BadSantaQuestion(
        "Подставлял(а) кого-то чтобы выкрутиться?",
        ["Выживает сильнейший", "Я беру ответственность на себя"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Сколько раз использовал(а) 'собака съела домашку'?",
        ["У меня очень голодная собака", "Я всегда честен с причинами"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Занимал(а) деньги и 'забывал(а)' вернуть?",
        ["Это инвестиция в дружбу", "Долг платежом красен"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Притворялся что работаешь когда босс рядом?",
        ["Excel всегда открыт для вида", "Я работаю честно"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Говорил(а) 'я в пути' лёжа в кровати?",
        ["Технически кровать - часть пути", "Я никогда не вру о местоположении"],
        [0, 10]
    ),

    # Relationship questions
    BadSantaQuestion(
        "Стебал(а) друзей за спиной?",
        ["Это называется 'юмор'", "Я говорю только в глаза"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Флиртовал(а) чтобы получить скидку?",
        ["Это называется 'обаяние'", "Я плачу полную цену с достоинством"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Отвечал(а) на сообщения через три дня?",
        ["Я занятой человек (играл в игры)", "Я всегда отвечаю быстро"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Делал(а) вид что не слышишь просьбу о помощи?",
        ["У меня плохой слух когда удобно", "Я всегда помогаю"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Притворялся что занят чтобы не идти на встречу?",
        ["Социальная усталость - это болезнь", "Я честно говорю когда не хочу"],
        [0, 10]
    ),

    # Modern naughty
    BadSantaQuestion(
        "Использовал(а) чужой Netflix без спроса?",
        ["Sharing is caring", "У меня своя подписка"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Отменял(а) планы в последний момент?",
        ["Гибкость - мой конёк", "Я держу слово"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Читал(а) чужую переписку?",
        ["Случайно... несколько раз", "Приватность священна"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Ставил(а) лайки своим старым фоткам?",
        ["Самолюбие - это нормально", "Это слишком нарциссично"],
        [0, 10]
    ),
    BadSantaQuestion(
        "Гуглил(а) симптомы и паниковал(а)?",
        ["У меня точно 5 редких болезней", "Я хожу к врачу как нормальный человек"],
        [0, 10]
    ),
]


class BadSantaPhase(Enum):
    """Internal phases for Bad Santa mode."""
    INTRO = "intro"
    QUESTIONS = "questions"
    CAMERA_PREP = "camera_prep"
    CAMERA_CAPTURE = "camera_capture"
    PROCESSING = "processing"
    RESULT = "result"


class BadSantaMode(BaseMode):
    """Bad Santa - Naughty/Nice mode with adult humor and prize.

    Flow:
    1. INTRO: Warning that this is 18+ content
    2. QUESTIONS: 5 questions to determine naughty/nice status
    3. CAMERA: Capture user photo for verdict portrait
    4. PROCESSING: AI generates verdict portrait
    5. RESULT: Display verdict + prize code if winner

    Winners (80%+ nice score) get a FREE SHOT coupon!
    """

    name = "bad_santa"
    display_name = "ПЛОХОЙ САНТА"
    description = "Узнай, заслужил ли ты подарки! 18+"
    icon = "santa"
    style = "christmas"
    requires_camera = True
    requires_ai = True
    estimated_duration = 60  # seconds

    NUM_QUESTIONS = 5
    WINNER_THRESHOLD = 0.80  # 80% nice = winner

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Phase management
        self._phase = BadSantaPhase.INTRO
        self._phase_timer = 0.0
        self._total_timer = 0.0

        # Questions state
        self._questions: List[BadSantaQuestion] = []
        self._current_question = 0
        self._selected_option = 0  # Currently highlighted option
        self._answers: List[int] = []  # Indices of selected options
        self._nice_score = 0  # Total nice points
        self._max_nice_score = 0  # Maximum possible nice points

        # Camera state
        self._photo_data: Optional[bytes] = None
        self._countdown = 3
        self._last_frame: Optional[np.ndarray] = None

        # AI portrait
        self._caricature_service = CaricatureService()
        self._caricature: Optional[Caricature] = None
        self._caricature_image: Optional[np.ndarray] = None

        # Upload for QR
        self._uploader = AsyncUploader()
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None

        # Prize coupon
        self._coupon_service = get_coupon_service()
        self._coupon_code: Optional[str] = None
        self._coupon_result: Optional[CouponResult] = None
        self._is_winner = False

        # Visual effects
        self._particles = ParticleSystem()
        self._progress_tracker = SmartProgressTracker(mode_theme="christmas")

        # Verdict text (generated by AI or fallback)
        self._verdict_text: Optional[str] = None

    def _select_questions(self) -> List[BadSantaQuestion]:
        """Select random questions for this session."""
        selected = random.sample(BAD_SANTA_QUESTIONS, min(self.NUM_QUESTIONS, len(BAD_SANTA_QUESTIONS)))
        return selected

    def _calculate_nice_percentage(self) -> float:
        """Calculate nice score as a percentage (0.0 to 1.0)."""
        if self._max_nice_score == 0:
            return 0.5
        return self._nice_score / self._max_nice_score

    def _get_verdict_category(self) -> str:
        """Get verdict category based on nice percentage."""
        pct = self._calculate_nice_percentage()
        if pct >= 0.80:
            return "ПОДАРОК ЗАСЛУЖЕН"
        elif pct >= 0.50:
            return "ПОДАРОК ПОД ВОПРОСОМ"
        else:
            return "УГОЛЬ ТЕБЕ, ЗАСРАНЕЦ"

    def on_enter(self) -> None:
        """Called when mode is activated."""
        logger.info("Bad Santa mode entered")
        self._phase = BadSantaPhase.INTRO
        self._phase_timer = 0.0
        self._total_timer = 0.0

        # Select questions
        self._questions = self._select_questions()
        self._current_question = 0
        self._selected_option = 0
        self._answers = []
        self._nice_score = 0
        self._max_nice_score = sum(max(q.nice_points) for q in self._questions)

        # Reset state
        self._photo_data = None
        self._caricature = None
        self._caricature_image = None
        self._qr_url = None
        self._qr_image = None
        self._coupon_code = None
        self._is_winner = False
        self._verdict_text = None

        # Play intro sound
        audio = get_audio_engine()
        if audio:
            audio.play_sfx("mystical")

    def on_exit(self) -> None:
        """Called when mode is deactivated."""
        logger.info("Bad Santa mode exited")

    def on_input(self, event: Event) -> bool:
        """Handle input events."""
        if event.type == EventType.ARCADE_LEFT:
            return self._handle_left()
        elif event.type == EventType.ARCADE_RIGHT:
            return self._handle_right()
        elif event.type in (EventType.BUTTON_PRESS, EventType.KEYPAD_ENTER):
            return self._handle_confirm()
        elif event.type == EventType.KEYPAD_BACK:
            return self._handle_back()

        return False

    def _handle_left(self) -> bool:
        """Handle left navigation."""
        if self._phase == BadSantaPhase.QUESTIONS:
            # Toggle between options (only 2)
            self._selected_option = 0
            return True
        return False

    def _handle_right(self) -> bool:
        """Handle right navigation."""
        if self._phase == BadSantaPhase.QUESTIONS:
            # Toggle between options (only 2)
            self._selected_option = 1
            return True
        return False

    def _handle_confirm(self) -> bool:
        """Handle confirm button."""
        if self._phase == BadSantaPhase.INTRO:
            # Move to questions
            self._phase = BadSantaPhase.QUESTIONS
            self._phase_timer = 0.0
            return True

        elif self._phase == BadSantaPhase.QUESTIONS:
            # Record answer and move to next question
            self._answers.append(self._selected_option)

            # Add nice points for this answer
            q = self._questions[self._current_question]
            self._nice_score += q.nice_points[self._selected_option]

            self._current_question += 1
            self._selected_option = 0

            if self._current_question >= len(self._questions):
                # All questions answered - determine winner status
                self._is_winner = self._calculate_nice_percentage() >= self.WINNER_THRESHOLD
                # Move to camera
                self._phase = BadSantaPhase.CAMERA_PREP
                self._phase_timer = 0.0
                self._countdown = 3

            return True

        elif self._phase == BadSantaPhase.CAMERA_PREP:
            # Start capture countdown
            self._phase = BadSantaPhase.CAMERA_CAPTURE
            self._phase_timer = 0.0
            self._countdown = 3
            return True

        elif self._phase == BadSantaPhase.RESULT:
            # Complete mode
            self._complete_mode()
            return True

        return False

    def _handle_back(self) -> bool:
        """Handle back button."""
        if self._phase == BadSantaPhase.QUESTIONS and self._current_question > 0:
            # Go back to previous question
            self._current_question -= 1
            if self._answers:
                # Remove last answer and subtract its nice points
                last_answer = self._answers.pop()
                q = self._questions[self._current_question]
                self._nice_score -= q.nice_points[last_answer]
            self._selected_option = 0
            return True
        return False

    def on_update(self, delta_ms: float) -> None:
        """Update mode state."""
        self._phase_timer += delta_ms / 1000.0  # Convert ms to seconds
        self._total_timer += delta_ms / 1000.0

        # Update particles
        self._particles.update(delta_ms)

        # Phase-specific updates
        if self._phase == BadSantaPhase.INTRO:
            self._update_intro(delta_ms)
        elif self._phase == BadSantaPhase.QUESTIONS:
            self._update_questions(delta_ms)
        elif self._phase == BadSantaPhase.CAMERA_PREP:
            self._update_camera_prep(delta_ms)
        elif self._phase == BadSantaPhase.CAMERA_CAPTURE:
            self._update_camera_capture(delta_ms)
        elif self._phase == BadSantaPhase.PROCESSING:
            self._update_processing(delta_ms)
        elif self._phase == BadSantaPhase.RESULT:
            self._update_result(delta_ms)

    def _update_intro(self, delta_ms: float) -> None:
        """Update intro phase."""
        # Auto-advance after 3 seconds
        if self._phase_timer >= 3.0:
            self._phase = BadSantaPhase.QUESTIONS
            self._phase_timer = 0.0

    def _update_questions(self, delta_ms: float) -> None:
        """Update questions phase."""
        # Just wait for user input
        pass

    def _update_camera_prep(self, delta_ms: float) -> None:
        """Update camera prep phase."""
        # Get camera frame for preview
        self._last_frame = camera_service.get_frame()

    def _update_camera_capture(self, delta_ms: float) -> None:
        """Update camera capture phase with countdown."""
        # Update countdown
        new_countdown = 3 - int(self._phase_timer)
        if new_countdown != self._countdown:
            self._countdown = new_countdown
            if self._countdown > 0:
                audio = get_audio_engine()
                if audio:
                    audio.play_sfx("tick")

        # Get latest frame
        self._last_frame = camera_service.get_frame()

        # Capture at countdown end
        if self._phase_timer >= 3.0:
            # Capture photo
            frame = camera_service.get_frame()
            if frame is not None:
                from PIL import Image
                from io import BytesIO

                # Convert to JPEG bytes
                img = Image.fromarray(frame)
                buf = BytesIO()
                img.save(buf, format='JPEG', quality=85)
                self._photo_data = buf.getvalue()

                audio = get_audio_engine()
                if audio:
                    audio.play_sfx("shutter")

            # Move to processing
            self._phase = BadSantaPhase.PROCESSING
            self._phase_timer = 0.0

            # Start async task for AI generation
            asyncio.create_task(self._generate_verdict())

    async def _generate_verdict(self) -> None:
        """Generate AI verdict portrait and handle prize coupon."""
        try:
            # Determine verdict text based on score
            pct = self._calculate_nice_percentage()
            category = self._get_verdict_category()

            # Build personality context for AI
            if pct >= 0.80:
                verdict_hint = f"WINNER - {int(pct*100)}% nice. They deserve a gift. Sarcastic praise."
            elif pct >= 0.50:
                verdict_hint = f"QUESTIONABLE - {int(pct*100)}% nice. Mixed verdict. Suspicious side-eye."
            else:
                verdict_hint = f"NAUGHTY - {int(pct*100)}% nice. Coal for them. Disappointed Santa energy."

            # Start AI portrait generation
            portrait_task = None
            if self._photo_data and self._caricature_service.is_available:
                portrait_task = asyncio.create_task(
                    self._caricature_service.generate_caricature(
                        reference_photo=self._photo_data,
                        style=CaricatureStyle.BAD_SANTA,
                        personality_context=verdict_hint,
                    )
                )

            # Register coupon if winner
            coupon_task = None
            if self._is_winner:
                coupon_task = asyncio.create_task(
                    self._coupon_service.register_shot_win(source="ARCADE_BAD_SANTA")
                )

            # Wait for portrait
            if portrait_task:
                self._caricature = await portrait_task
                if self._caricature:
                    # Convert to numpy array for display
                    from PIL import Image
                    from io import BytesIO

                    img = Image.open(BytesIO(self._caricature.image_data))
                    self._caricature_image = np.array(img.convert('RGB'))

                    # Upload for QR
                    self._uploader.upload_bytes(
                        self._caricature.image_data,
                        prefix="bad_santa",
                        extension="png",
                        content_type="image/png",
                        callback=self._on_upload_complete
                    )

            # Wait for coupon
            if coupon_task:
                self._coupon_result = await coupon_task
                if self._coupon_result and self._coupon_result.success:
                    self._coupon_code = self._coupon_result.coupon_code
                    logger.info(f"Bad Santa prize coupon: {self._coupon_code}")

            # Generate verdict text (fallback if AI doesn't provide)
            if pct >= 0.80:
                self._verdict_text = random.choice([
                    "Ладно, засранец, ты заслужил. Держи свой шот и вали отсюда!",
                    "Ну охуеть теперь, святоша нашлась! Ладно, держи подарок.",
                    "Серьёзно? Ты хороший? Ну... допустим. Держи шот, пока не передумал.",
                    "Блин, ты реально не накосячил? Ладно, один шот тебе.",
                ])
            elif pct >= 0.50:
                self._verdict_text = random.choice([
                    "Ты не плохой, но и не хороший. Короче, хз что с тобой делать.",
                    "50 на 50... Может в следующем году будешь стараться лучше?",
                    "Ну такое... Не уголь, но и не подарок. Иди подумай над поведением.",
                    "Санта в замешательстве. Ты как бы норм, но как бы и нет.",
                ])
            else:
                self._verdict_text = random.choice([
                    "УГОЛЬ ТЕБЕ, ЗАСРАНЕЦ! Ты реально думал что заслужил подарок?",
                    "Хо-хо-хо... НЕТ. Иди нахуй с таким поведением.",
                    "Поздравляю, ты официально в списке плохишей. Уголь твой.",
                    "Санта видел что ты творил. УГОЛЬ. Без вариантов.",
                ])

        except Exception as e:
            logger.exception(f"Verdict generation failed: {e}")
            self._verdict_text = "Санта сломался... но ты наверное плохой!"

        # Move to result phase
        self._phase = BadSantaPhase.RESULT
        self._phase_timer = 0.0

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle upload completion."""
        if result.success:
            self._qr_url = result.url
            self._qr_image = result.qr_image
            logger.info(f"Bad Santa image uploaded: {result.url}")
        else:
            logger.warning(f"Upload failed: {result.error}")

    def _update_processing(self, delta_ms: float) -> None:
        """Update processing phase."""
        # Update progress tracker
        self._progress_tracker.update_processing(
            int(min(self._phase_timer / 10.0, 0.95) * 100)
        )

    def _update_result(self, delta_ms: float) -> None:
        """Update result display phase."""
        # Auto-complete after 30 seconds
        if self._phase_timer >= 30.0:
            self._complete_mode()

    def _complete_mode(self) -> None:
        """Complete the mode and return result."""
        pct = self._calculate_nice_percentage()
        category = self._get_verdict_category()

        # Build print data
        print_data = {
            "verdict": category,
            "nice_score": pct,
            "verdict_text": self._verdict_text or category,
            "display_text": self._verdict_text or category,
            "qr_url": self._qr_url,
        }

        if self._caricature:
            print_data["caricature"] = self._caricature.image_data

        if self._coupon_code:
            print_data["coupon_code"] = self._coupon_code

        # Calculate total score for display
        total_answers = len(self._answers)

        result = ModeResult(
            mode_name=self.name,
            display_text=self._verdict_text or category,
            score=int(pct * 100),
            extra_data={
                "nice_percentage": pct,
                "category": category,
                "is_winner": self._is_winner,
                "coupon_code": self._coupon_code,
                "total_questions": total_answers,
            },
            print_data=print_data,
            photo_data=self._photo_data,
        )

        self.context.event_bus.emit(Event(EventType.MODE_COMPLETE, {"result": result}))

    def render_main(self, buffer: np.ndarray) -> None:
        """Render to main 128x128 display."""
        from artifact.graphics.primitives import clear, draw_rect, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, draw_text

        clear(buffer)

        if self._phase == BadSantaPhase.INTRO:
            self._render_intro(buffer)
        elif self._phase == BadSantaPhase.QUESTIONS:
            self._render_questions(buffer)
        elif self._phase in (BadSantaPhase.CAMERA_PREP, BadSantaPhase.CAMERA_CAPTURE):
            self._render_camera(buffer)
        elif self._phase == BadSantaPhase.PROCESSING:
            self._render_processing(buffer)
        elif self._phase == BadSantaPhase.RESULT:
            self._render_result(buffer)

    def _render_intro(self, buffer: np.ndarray) -> None:
        """Render intro screen with 18+ warning."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text

        # Dark red background
        draw_rect(buffer, 0, 0, 128, 128, (40, 10, 10))

        # Title
        draw_centered_text(buffer, "ПЛОХОЙ", 20, (255, 50, 50), scale=2)
        draw_centered_text(buffer, "САНТА", 42, (255, 50, 50), scale=2)

        # Warning
        draw_centered_text(buffer, "18+", 70, (255, 200, 0), scale=2)
        draw_centered_text(buffer, "ВЗРОСЛЫЙ ЮМОР", 95, (200, 200, 200), scale=1)

        # Prompt
        pulse = 0.5 + 0.5 * math.sin(self._phase_timer * 4)
        alpha = int(255 * pulse)
        draw_centered_text(buffer, "НАЖМИ ЧТОБЫ НАЧАТЬ", 115, (alpha, alpha, alpha), scale=1)

    def _render_questions(self, buffer: np.ndarray) -> None:
        """Render question screen."""
        from artifact.graphics.primitives import draw_rect, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, draw_text

        # Dark background
        draw_rect(buffer, 0, 0, 128, 128, (20, 15, 25))

        # Progress indicator
        progress = (self._current_question + 1) / len(self._questions)
        bar_width = int(120 * progress)
        draw_rect(buffer, 4, 4, bar_width, 4, (255, 50, 50))
        draw_centered_text(buffer, f"{self._current_question + 1}/{len(self._questions)}", 15, (150, 150, 150), scale=1)

        # Question
        q = self._questions[self._current_question]

        # Word wrap question text
        words = q.text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            if len(test_line) <= 18:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Draw question lines
        y = 28
        for line in lines[:3]:  # Max 3 lines
            draw_centered_text(buffer, line, y, (255, 255, 255), scale=1)
            y += 12

        # Draw options
        y = 75
        for i, option in enumerate(q.options):
            is_selected = i == self._selected_option

            # Truncate option text
            display_text = option[:20] + "..." if len(option) > 23 else option

            if is_selected:
                # Highlight box
                draw_rect(buffer, 4, y - 2, 120, 20, (80, 40, 40))
                draw_rect(buffer, 4, y - 2, 120, 20, (255, 100, 100))
                color = (255, 255, 255)
            else:
                color = (150, 150, 150)

            # Arrow indicator
            if is_selected:
                draw_text(buffer, ">", 6, y, color, scale=1)

            draw_text(buffer, display_text, 16, y, color, scale=1)
            y += 24

    def _render_camera(self, buffer: np.ndarray) -> None:
        """Render camera view with countdown."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from PIL import Image

        # Show camera preview
        if self._last_frame is not None:
            # Resize and mirror frame
            frame = np.fliplr(self._last_frame)
            img = Image.fromarray(frame)
            img = img.resize((128, 128), Image.Resampling.NEAREST)
            buffer[:] = np.array(img)

            # Add red overlay for Bad Santa vibe
            red_overlay = np.zeros_like(buffer)
            red_overlay[:, :, 0] = 30  # Red tint
            buffer[:] = np.clip(buffer.astype(np.int16) + red_overlay, 0, 255).astype(np.uint8)
        else:
            draw_rect(buffer, 0, 0, 128, 128, (40, 20, 20))
            draw_centered_text(buffer, "КАМЕРА...", 60, (255, 100, 100), scale=1)

        # Draw countdown
        if self._phase == BadSantaPhase.CAMERA_CAPTURE and self._countdown > 0:
            draw_centered_text(buffer, str(self._countdown), 64, (255, 255, 0), scale=4)
        elif self._phase == BadSantaPhase.CAMERA_PREP:
            draw_centered_text(buffer, "ПОКАЖИ РОЖУ!", 30, (255, 50, 50), scale=1)
            pulse = 0.5 + 0.5 * math.sin(self._phase_timer * 4)
            alpha = int(255 * pulse)
            draw_centered_text(buffer, "НАЖМИ", 100, (alpha, alpha, alpha), scale=1)

    def _render_processing(self, buffer: np.ndarray) -> None:
        """Render processing screen."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text

        draw_rect(buffer, 0, 0, 128, 128, (20, 10, 10))

        # Animated text
        dots = "." * (int(self._phase_timer * 2) % 4)
        draw_centered_text(buffer, "САНТА ДУМАЕТ" + dots, 50, (255, 100, 100), scale=1)

        # Progress bar
        progress = min(self._phase_timer / 10.0, 0.95)
        bar_width = int(100 * progress)
        draw_rect(buffer, 14, 70, bar_width, 8, (255, 50, 50))

        # Nice percentage teaser
        pct = self._calculate_nice_percentage()
        draw_centered_text(buffer, f"ХОРОШИЙ НА {int(pct*100)}%", 95, (150, 150, 150), scale=1)

    def _render_result(self, buffer: np.ndarray) -> None:
        """Render result screen."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from PIL import Image

        # Background color based on verdict
        if self._is_winner:
            draw_rect(buffer, 0, 0, 128, 128, (20, 40, 20))  # Green tint
        else:
            draw_rect(buffer, 0, 0, 128, 128, (40, 15, 15))  # Red tint

        # Show portrait if available
        if self._caricature_image is not None:
            img = Image.fromarray(self._caricature_image)
            img = img.resize((80, 80), Image.Resampling.LANCZOS)
            portrait = np.array(img)
            x_offset = (128 - 80) // 2
            buffer[5:85, x_offset:x_offset+80] = portrait
            y_text = 90
        else:
            y_text = 40

        # Verdict
        category = self._get_verdict_category()
        if self._is_winner:
            draw_centered_text(buffer, "ПОДАРОК!", y_text, (100, 255, 100), scale=1)
        else:
            draw_centered_text(buffer, "УГОЛЬ!", y_text, (255, 100, 100), scale=1)

        # Coupon code if winner
        if self._coupon_code:
            draw_centered_text(buffer, "БЕСПЛАТНЫЙ ШОТ!", y_text + 12, (255, 255, 0), scale=1)
            # Show short code
            short_code = self._coupon_code.replace("VNVNC-", "")[:9]
            draw_centered_text(buffer, short_code, y_text + 24, (200, 200, 200), scale=1)

        # QR code if available
        if self._qr_image is not None:
            qr_size = 30
            qr_x = 128 - qr_size - 4
            qr_y = 128 - qr_size - 4
            qr_resized = Image.fromarray(self._qr_image).resize((qr_size, qr_size), Image.Resampling.NEAREST)
            buffer[qr_y:qr_y+qr_size, qr_x:qr_x+qr_size] = np.array(qr_resized)

    def render_ticker(self, buffer: np.ndarray) -> None:
        """Render to ticker 48x8 display."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import draw_text

        clear(buffer)

        if self._phase == BadSantaPhase.INTRO:
            draw_text(buffer, "18+ САНТА", 2, 0, (255, 50, 50), scale=1)
        elif self._phase == BadSantaPhase.QUESTIONS:
            q_num = self._current_question + 1
            total = len(self._questions)
            draw_text(buffer, f"? {q_num}/{total}", 2, 0, (255, 200, 0), scale=1)
        elif self._phase in (BadSantaPhase.CAMERA_PREP, BadSantaPhase.CAMERA_CAPTURE):
            draw_text(buffer, "ФОТО!", 2, 0, (255, 100, 100), scale=1)
        elif self._phase == BadSantaPhase.PROCESSING:
            draw_text(buffer, "ДУМАЮ...", 2, 0, (255, 100, 0), scale=1)
        elif self._phase == BadSantaPhase.RESULT:
            if self._is_winner:
                draw_text(buffer, "ПОДАРОК!", 2, 0, (100, 255, 100), scale=1)
            else:
                draw_text(buffer, "УГОЛЬ!", 2, 0, (255, 50, 50), scale=1)

    def get_lcd_text(self) -> str:
        """Get text for 16-char LCD."""
        if self._phase == BadSantaPhase.INTRO:
            return "ПЛОХОЙ САНТА 18+"
        elif self._phase == BadSantaPhase.QUESTIONS:
            return f"ВОПРОС {self._current_question + 1}/{len(self._questions)}"
        elif self._phase in (BadSantaPhase.CAMERA_PREP, BadSantaPhase.CAMERA_CAPTURE):
            return "УЛЫБОЧКУ!"
        elif self._phase == BadSantaPhase.PROCESSING:
            return "САНТА ДУМАЕТ..."
        elif self._phase == BadSantaPhase.RESULT:
            pct = int(self._calculate_nice_percentage() * 100)
            return f"ХОРОШИЙ НА {pct}%"
        return "ПЛОХОЙ САНТА"

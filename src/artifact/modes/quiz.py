"""Quiz mode - Timed trivia challenge.

A fast-paced trivia game with timer and scoring.
Uses arcade visual style with countdown bar and score display.
"""

from typing import List, Tuple, Optional
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets


# Quiz questions: (question, option_left, option_right, correct_is_right)
QUIZ_QUESTIONS_RU = [
    ("Столица России?", "Санкт-Петербург", "Москва", True),
    ("Самая длинная река?", "Нил", "Амазонка", False),
    ("Кто написал 'Войну и мир'?", "Толстой", "Достоевский", False),
    ("Сколько планет в Солнечной системе?", "8", "9", False),
    ("Какой газ мы вдыхаем?", "Кислород", "Азот", False),
    ("Столица Франции?", "Лион", "Париж", True),
    ("Сколько дней в году?", "365", "366", False),
    ("Самый большой океан?", "Атлантический", "Тихий", True),
    ("Кто изобрёл телефон?", "Эдисон", "Белл", True),
    ("Столица Японии?", "Киото", "Токио", True),
    ("Какой цвет получается из синего и жёлтого?", "Зелёный", "Оранжевый", False),
    ("Сколько ног у паука?", "6", "8", True),
    ("Самая высокая гора?", "Эверест", "К2", False),
    ("Кто нарисовал Мону Лизу?", "Да Винчи", "Микеланджело", False),
    ("Столица Испании?", "Барселона", "Мадрид", True),
]

# Score ranks
RANKS_RU = [
    (0, "Новичок"),
    (3, "Ученик"),
    (5, "Знаток"),
    (7, "Эрудит"),
    (9, "Мастер"),
    (10, "Гений!"),
]


class QuizMode(BaseMode):
    """Quiz mode - Timed trivia game.

    Flow:
    1. Intro: "Get ready" animation
    2. Active: Questions with timer (10 questions, 10 sec each)
    3. Processing: Score calculation
    4. Result: Display final score and rank
    """

    name = "quiz"
    display_name = "ВИКТОРИНА"
    description = "Проверь свои знания"
    icon = "?"
    style = "arcade"
    requires_camera = False
    requires_ai = False
    estimated_duration = 120

    # Game settings
    QUESTIONS_COUNT = 5
    TIME_PER_QUESTION = 10.0  # seconds

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Game state
        self._questions: List[Tuple] = []
        self._current_question: int = 0
        self._score: int = 0
        self._time_remaining: float = 0.0
        self._answered: bool = False
        self._last_answer_correct: Optional[bool] = None

        # Animation
        self._answer_flash: float = 0.0
        self._score_pop: float = 0.0

        # Particles
        self._particles = ParticleSystem()

        # Colors
        self._primary = (241, 196, 15)    # Yellow
        self._secondary = (46, 204, 113)  # Green
        self._error = (231, 76, 60)       # Red
        self._background = (20, 30, 50)

    def on_enter(self) -> None:
        """Initialize quiz mode."""
        # Select random questions
        all_questions = QUIZ_QUESTIONS_RU.copy()
        random.shuffle(all_questions)
        self._questions = all_questions[:self.QUESTIONS_COUNT]

        self._current_question = 0
        self._score = 0
        self._time_remaining = self.TIME_PER_QUESTION
        self._answered = False
        self._last_answer_correct = None
        self._answer_flash = 0.0
        self._score_pop = 0.0

        # Setup particles
        sparkle_config = ParticlePresets.sparkle(x=64, y=64)
        sparkle_config.color = self._secondary
        self._particles.add_emitter("sparkles", sparkle_config)

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        """Update quiz mode."""
        self._particles.update(delta_ms)

        # Decay animations
        self._answer_flash = max(0, self._answer_flash - delta_ms / 300)
        self._score_pop = max(0, self._score_pop - delta_ms / 500)

        if self.phase == ModePhase.INTRO:
            # Intro for 2 seconds
            if self._time_in_phase > 2000:
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.ACTIVE:
            if not self._answered:
                # Update timer
                self._time_remaining -= delta_ms / 1000

                if self._time_remaining <= 0:
                    # Time's up - wrong answer
                    self._answer_question(None)

            else:
                # Brief pause after answer before next question
                if self._time_in_phase > 1500:
                    self._next_question()

        elif self.phase == ModePhase.RESULT:
            # Auto-complete after 15 seconds
            if self._time_in_phase > 15000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if self.phase == ModePhase.ACTIVE and not self._answered:
            if event.type == EventType.ARCADE_LEFT:
                self._answer_question(False)  # Left option
                return True
            elif event.type == EventType.ARCADE_RIGHT:
                self._answer_question(True)   # Right option
                return True

        elif self.phase == ModePhase.RESULT:
            if event.type == EventType.BUTTON_PRESS:
                self._finish()
                return True

        return False

    def _answer_question(self, chose_right: Optional[bool]) -> None:
        """Process an answer.

        Args:
            chose_right: True if right button, False if left, None if timeout
        """
        if self._answered:
            return

        self._answered = True
        question = self._questions[self._current_question]
        correct_is_right = question[3]

        if chose_right is None:
            # Timeout
            self._last_answer_correct = False
        elif chose_right == correct_is_right:
            # Correct!
            self._score += 1
            self._last_answer_correct = True
            self._score_pop = 1.0

            # Particles
            sparkles = self._particles.get_emitter("sparkles")
            if sparkles:
                sparkles.burst(30)
        else:
            # Wrong
            self._last_answer_correct = False

        self._answer_flash = 1.0
        self._time_in_phase = 0  # Reset for pause timing

    def _next_question(self) -> None:
        """Move to next question or finish."""
        self._current_question += 1

        if self._current_question >= len(self._questions):
            # Quiz complete
            self.change_phase(ModePhase.RESULT)
        else:
            # Reset for next question
            self._time_remaining = self.TIME_PER_QUESTION
            self._answered = False
            self._last_answer_correct = None

    def _get_rank(self) -> str:
        """Get rank based on score."""
        for min_score, rank in reversed(RANKS_RU):
            if self._score >= min_score:
                return rank
        return "Новичок"

    def on_exit(self) -> None:
        """Cleanup."""
        self._particles.clear_all()
        self.stop_animations()

    def _finish(self) -> None:
        """Complete the mode."""
        rank = self._get_rank()
        percentage = int(self._score / len(self._questions) * 100)

        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=f"Score: {self._score}/{len(self._questions)} - {rank}",
            ticker_text=f"{rank}: {self._score}/{len(self._questions)} ({percentage}%)",
            lcd_text=f"{self._score}/{len(self._questions)} {rank}"[:16].center(16),
            should_print=True,
            print_data={
                "score": self._score,
                "total": len(self._questions),
                "percentage": percentage,
                "rank": rank,
                "type": "quiz"
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display."""
        from artifact.graphics.primitives import fill, draw_rect, draw_circle
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        fill(buffer, self._background)
        font = load_font("cyrillic")

        if self.phase == ModePhase.INTRO:
            self._render_intro(buffer, font)
        elif self.phase == ModePhase.ACTIVE:
            self._render_question(buffer, font)
        elif self.phase == ModePhase.RESULT:
            self._render_result(buffer, font)

        # Render particles
        self._particles.render(buffer)

    def _render_intro(self, buffer, font) -> None:
        """Render intro screen."""
        from artifact.graphics.text_utils import draw_centered_text

        # Title - centered
        draw_centered_text(buffer, "ВИКТОРИНА!", 35, self._primary, scale=2)

        # Question count - centered
        draw_centered_text(buffer, f"{self.QUESTIONS_COUNT} Вопросов", 60, (150, 150, 180), scale=1)

        # Countdown - centered
        countdown = max(0, 3 - int(self._time_in_phase / 1000))
        if countdown > 0:
            draw_centered_text(buffer, str(countdown), 85, self._secondary, scale=3)
        else:
            draw_centered_text(buffer, "СТАРТ!", 85, self._secondary, scale=2)

    def _render_question(self, buffer, font) -> None:
        """Render current question."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.fonts import draw_text_bitmap
        from artifact.graphics.text_utils import draw_wrapped_text, fit_text_in_rect

        question = self._questions[self._current_question]
        q_text, opt_left, opt_right, _ = question

        # Score display - left aligned at top
        score_color = self._secondary if self._score_pop > 0 else (100, 100, 120)
        score_scale = 1 if self._score_pop == 0 else 2
        draw_text_bitmap(buffer, f"Счёт:{self._score}", 3, 2, score_color, font, scale=score_scale)

        # Question number - right aligned at top
        q_num = f"{self._current_question + 1}/{len(self._questions)}"
        draw_text_bitmap(buffer, q_num, 100, 2, (100, 100, 120), font, scale=1)

        # Timer bar - centered with margin
        timer_y = 12
        timer_w = 116
        timer_h = 5
        timer_x = (128 - timer_w) // 2
        timer_fill = int(timer_w * (self._time_remaining / self.TIME_PER_QUESTION))

        # Timer color based on remaining time
        if self._time_remaining > 5:
            timer_color = self._secondary
        elif self._time_remaining > 2:
            timer_color = self._primary
        else:
            timer_color = self._error

        draw_rect(buffer, timer_x, timer_y, timer_w, timer_h, (40, 40, 60))
        if timer_fill > 0:
            draw_rect(buffer, timer_x, timer_y, timer_fill, timer_h, timer_color)

        # Question text - smart wrapped, positioned lower
        draw_wrapped_text(buffer, q_text, 22, (255, 255, 255), scale=1, max_lines=3, line_spacing=3)

        # Answer options - positioned to fit within screen
        btn_y = 85
        btn_h = 28

        # Left option
        left_color = self._secondary if self._last_answer_correct == True and not question[3] else (60, 80, 100)
        if self._last_answer_correct == False and not question[3]:
            left_color = self._error

        draw_rect(buffer, 3, btn_y, 58, btn_h, left_color)
        # Fit text within button
        fit_text_in_rect(buffer, opt_left, (3, btn_y, 58, btn_h), (255, 255, 255), font, max_scale=1, padding=3)

        # Right option
        right_color = self._secondary if self._last_answer_correct == True and question[3] else (60, 80, 100)
        if self._last_answer_correct == False and question[3]:
            right_color = self._error

        draw_rect(buffer, 67, btn_y, 58, btn_h, right_color)
        fit_text_in_rect(buffer, opt_right, (67, btn_y, 58, btn_h), (255, 255, 255), font, max_scale=1, padding=3)

        # Answer flash
        if self._answer_flash > 0:
            if self._last_answer_correct:
                color = tuple(int(c * self._answer_flash * 0.3) for c in self._secondary)
            else:
                color = tuple(int(c * self._answer_flash * 0.3) for c in self._error)
            draw_rect(buffer, 0, 0, 128, 128, color)

    def _render_result(self, buffer, font) -> None:
        """Render final results."""
        from artifact.graphics.text_utils import draw_centered_text

        # Title - centered
        draw_centered_text(buffer, "ИТОГИ", 8, self._primary, scale=2)

        # Score - centered with large font
        draw_centered_text(buffer, f"{self._score}/{len(self._questions)}", 35, self._secondary, scale=3)

        # Percentage - centered
        percentage = int(self._score / len(self._questions) * 100)
        draw_centered_text(buffer, f"{percentage}%", 65, (150, 150, 180), scale=2)

        # Rank - centered
        rank = self._get_rank()
        rank_color = self._secondary if self._score >= 7 else self._primary
        draw_centered_text(buffer, rank, 88, rank_color, scale=2)

        # Press to continue - blinking, positioned safely
        if int(self._time_in_phase / 500) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ КНОПКУ", 110, (100, 100, 120), scale=1)

    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        """Simple text wrapping."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= max_chars:
                current = current + " " + word if current else word
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def render_ticker(self, buffer) -> None:
        """Render ticker with smooth seamless scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, render_ticker_static, TickerEffect, TextEffect

        clear(buffer)

        if self.phase == ModePhase.INTRO:
            # Intro scrolling text
            render_ticker_animated(
                buffer, "ВИКТОРИНА - ПРОВЕРЬ СВОИ ЗНАНИЯ",
                self._time_in_phase, self._primary,
                TickerEffect.RAINBOW_SCROLL, speed=0.025
            )

        elif self.phase == ModePhase.ACTIVE:
            # Show timer and score as static centered text with glow
            secs = int(self._time_remaining)
            status = f"ВРЕМЯ:{secs}с СЧЁТ:{self._score}"
            render_ticker_static(
                buffer, status,
                self._time_in_phase, self._primary,
                TextEffect.GLOW
            )

        elif self.phase == ModePhase.RESULT:
            # Result with wave effect
            rank = self._get_rank()
            text = f"{rank} - {self._score}/{len(self._questions)} ПРАВИЛЬНО"
            render_ticker_animated(
                buffer, text,
                self._time_in_phase, self._secondary,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )

    def get_lcd_text(self) -> str:
        """Get LCD text with fun timer bar."""
        if self.phase == ModePhase.ACTIVE:
            # Visual timer bar
            time_left = int(self._time_remaining)
            bar = "█" * min(5, time_left // 2) + "░" * (5 - min(5, time_left // 2))
            return f"← → Q{self._current_question + 1} {bar}"[:16]
        elif self.phase == ModePhase.RESULT:
            pct = int(self._score / len(self._questions) * 100)
            star = "★" if pct >= 70 else "◆" if pct >= 40 else "○"
            return f"{star} {self._score}/{len(self._questions)} {pct}% {star}"[:16].center(16)
        return " ◆ ВИКТОРИНА ◆ ".center(16)

"""ASCII art and fun text utilities for ARTIFACT displays.

This module provides ASCII art animations, symbols, and clever text
for the LCD (16 chars) and ticker (48×8) displays.

Design philosophy:
- The LCD should be FUN and unexpected, not boring mode names
- Use ASCII symbols to create mini-animations
- Each mode has its own themed visual language
- Sync ticker scrolling with LCD status
"""

from typing import List, Tuple, Optional
import random
import math

# Unicode symbols for controls (use these instead of L/R!)
ARROW_LEFT = "←"
ARROW_RIGHT = "→"
ARROW_UP = "▲"
ARROW_DOWN = "▼"
ARROW_LEFT_DOUBLE = "◄"
ARROW_RIGHT_DOUBLE = "►"
BULLET = "●"
HOLLOW_BULLET = "○"
DIAMOND = "◆"
HOLLOW_DIAMOND = "◇"
STAR = "★"
HOLLOW_STAR = "☆"
HEART = "♥"
HOLLOW_HEART = "♡"
SKULL = "☠"
SUN = "☀"
MOON = "☽"
LIGHTNING = "⚡"
FIRE = "🔥"
EYE = "👁"
CRYSTAL = "🔮"
SPARKLE = "✨"
MAGIC = "✦"
SPIRAL = "🌀"
CHECK = "✓"
CROSS = "✗"

# Zodiac symbols
ZODIAC = {
    "ОВЕН": "♈", "ТЕЛЕЦ": "♉", "БЛИЗНЕЦЫ": "♊", "РАК": "♋",
    "ЛЕВ": "♌", "ДЕВА": "♍", "ВЕСЫ": "♎", "СКОРПИОН": "♏",
    "СТРЕЛЕЦ": "♐", "КОЗЕРОГ": "♑", "ВОДОЛЕЙ": "♒", "РЫБЫ": "♓"
}

# ASCII spinner frames (for loading animations)
SPINNER_FRAMES = ["◐", "◓", "◑", "◒"]
DOTS_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
MOON_PHASES = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
WAVE_FRAMES = ["~∿~", "∿~∿", "~∿~", "∿~∿"]

# LCD text patterns - 16 characters max
LCD_WIDTH = 16


class LCDAnimator:
    """Animated LCD display manager."""

    def __init__(self):
        self._frame = 0
        self._text_offset = 0

    def tick(self, delta_ms: float = 16.67) -> None:
        """Advance animation frame."""
        self._frame += 1
        self._text_offset = int(self._frame / 10)

    def get_spinner(self) -> str:
        """Get current spinner character."""
        return SPINNER_FRAMES[self._frame % len(SPINNER_FRAMES)]

    def get_dots_spinner(self) -> str:
        """Get braille dots spinner."""
        return DOTS_FRAMES[self._frame % len(DOTS_FRAMES)]

    def get_moon_phase(self) -> str:
        """Get current moon phase."""
        return MOON_PHASES[(self._frame // 10) % len(MOON_PHASES)]

    def get_wave(self) -> str:
        """Get wave animation."""
        return WAVE_FRAMES[(self._frame // 5) % len(WAVE_FRAMES)]


# Fun LCD text generators

def lcd_idle(time_ms: float) -> str:
    """Generate fun idle LCD text."""
    patterns = [
        "  ★ VNVNC ★  ",
        " ◆ НАЖМИ ◆ ",
        "✦ СУДЬБА ЖДЁТ ✦",
        " ●○●○ ПРИВЕТ ○●○● ",
        "◄► ВЫБЕРИ МЕНЯ ◄►",
    ]
    idx = int(time_ms / 2000) % len(patterns)
    return patterns[idx].center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_fortune_active(time_ms: float) -> str:
    """Fortune teller LCD - mystical and mysterious."""
    frame = int(time_ms / 500)
    patterns = [
        f" {CRYSTAL} СМОТРЮ... {CRYSTAL} ",
        f"  ★ ДУХИ {SPINNER_FRAMES[frame % 4]} ★  ",
        f" {EYE} ВИЖУ ТЕБЯ {EYE} ",
        f"  ◆ ТАЙНЫ ◆  ",
    ]
    return patterns[frame % len(patterns)].center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_fortune_result() -> str:
    """Fortune result LCD."""
    return f" {STAR} СУДЬБА {STAR} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_zodiac_input(digits: str) -> str:
    """Zodiac date input LCD with fun formatting."""
    # Show entered digits with underscores for remaining
    display = ""
    for i in range(8):  # DD.MM.YYYY
        if i == 2 or i == 5:
            display += "."
        elif i < len(digits):
            display += digits[i]
        else:
            display += "_"
    return f" {display} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_zodiac_result(sign: str) -> str:
    """Zodiac result with symbol."""
    symbol = ZODIAC.get(sign, "★")
    return f" {symbol} {sign} {symbol} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_roulette_spin(time_ms: float) -> str:
    """Roulette spinning LCD."""
    frame = int(time_ms / 100)
    spin_chars = "◐◓◑◒"
    spin = spin_chars[frame % len(spin_chars)]
    return f" {spin} КРУЧУ {spin} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_roulette_result(segment: str) -> str:
    """Roulette result LCD."""
    return f"►{segment[:12]}◄".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_quiz_question(num: int, total: int, time_remaining: float) -> str:
    """Quiz question LCD with timer."""
    timer_bar = "█" * int(time_remaining / 2) + "░" * (5 - int(time_remaining / 2))
    return f"Q{num}/{total} {timer_bar}".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_quiz_correct() -> str:
    """Quiz correct answer LCD."""
    return f" {CHECK} ВЕРНО! {CHECK} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_quiz_wrong() -> str:
    """Quiz wrong answer LCD."""
    return f" {CROSS} НЕВЕРНО {CROSS} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_quiz_result(score: int, total: int) -> str:
    """Quiz final result LCD."""
    pct = int(score / total * 100)
    if pct >= 80:
        emoji = "★"
    elif pct >= 50:
        emoji = "◆"
    else:
        emoji = "○"
    return f"{emoji} {score}/{total} {pct}% {emoji}".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_ai_camera_prep(time_ms: float) -> str:
    """AI Prophet camera prep LCD."""
    frame = int(time_ms / 300)
    frames = [
        f" {EYE} СМОТРИ {EYE} ",
        " ○ В КАМЕРУ ○ ",
        f" {SPARKLE} ГОТОВЬСЯ {SPARKLE} ",
    ]
    return frames[frame % len(frames)].center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_ai_countdown(seconds: int) -> str:
    """AI Prophet countdown LCD."""
    return f" ★ {seconds} ★ ФОТО! ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_ai_processing(time_ms: float) -> str:
    """AI Prophet processing LCD."""
    spinner = DOTS_FRAMES[int(time_ms / 100) % len(DOTS_FRAMES)]
    return f" {spinner} ИИ ДУМАЕТ {spinner} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_ai_result() -> str:
    """AI Prophet result LCD."""
    return f" {CRYSTAL} ПРОРОЧЕСТВО {CRYSTAL} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_prompt_buttons() -> str:
    """Generic button prompt LCD."""
    return f" {ARROW_LEFT} НЕТ {ARROW_RIGHT} ДА ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_prompt_start() -> str:
    """Start prompt LCD."""
    return f" {ARROW_DOWN} СТАРТ {ARROW_DOWN} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_loading(time_ms: float) -> str:
    """Generic loading LCD."""
    spinner = SPINNER_FRAMES[int(time_ms / 200) % len(SPINNER_FRAMES)]
    return f" {spinner} ЗАГРУЗКА {spinner} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_printing(time_ms: float) -> str:
    """Printing in progress LCD."""
    progress = int(time_ms / 1000) % 4
    bar = "█" * progress + "░" * (3 - progress)
    return f" ПЕЧАТЬ {bar} ".center(LCD_WIDTH)[:LCD_WIDTH]


def lcd_done() -> str:
    """Generic done LCD."""
    return f" {CHECK} ГОТОВО! {CHECK} ".center(LCD_WIDTH)[:LCD_WIDTH]


# Ticker text generators (for scrolling)

def ticker_mystical() -> str:
    """Mystical scrolling ticker text."""
    return f" {CRYSTAL}{SPARKLE} УЗНАЙ СВОЮ СУДЬБУ {SPARKLE}{CRYSTAL} ◆ НАЖМИ КНОПКУ ◆ "


def ticker_zodiac() -> str:
    """Zodiac ticker text with all symbols."""
    symbols = "".join(ZODIAC.values())
    return f" {symbols} ЗОДИАК ОРАКУЛ {symbols} "


def ticker_roulette() -> str:
    """Roulette ticker text."""
    return f" {DIAMOND} КРУТИ КОЛЕСО ФОРТУНЫ {DIAMOND} {STAR} ВЫИГРАЙ ПРИЗ {STAR} "


def ticker_quiz() -> str:
    """Quiz ticker text."""
    return f" {LIGHTNING} ВИКТОРИНА {LIGHTNING} ПРОВЕРЬ СВОИ ЗНАНИЯ {STAR} "


def ticker_ai() -> str:
    """AI Prophet ticker text."""
    return f" {EYE}{CRYSTAL} ИИ ПРОРОК {CRYSTAL}{EYE} СУДЬБА ЖДЁТ ТЕБЯ {SPARKLE} "


# ASCII Art for main display (simple patterns)

ASCII_EYE = """
    ██████
  ██      ██
██  ●●●●  ██
██   ██   ██
  ██    ██
    ████
"""

ASCII_CRYSTAL_BALL = """
     ◢◤◢◤
   ◢◤    ◢◤
  │  ◆◇  │
  │ ◇◆◇ │
   ◥◣  ◥◣
     ◥◤
"""

ASCII_HEART = """
  ♥♥   ♥♥
♥♥♥♥ ♥♥♥♥
♥♥♥♥♥♥♥♥
 ♥♥♥♥♥♥
  ♥♥♥♥
   ♥♥
"""

ASCII_STAR = """
    ★
   ★★★
  ★★★★★
   ★★★
  ★   ★
 ★     ★
"""


def make_progress_bar(progress: float, width: int = 10) -> str:
    """Create ASCII progress bar.

    Args:
        progress: 0.0 to 1.0
        width: Number of characters

    Returns:
        ASCII progress bar string
    """
    filled = int(progress * width)
    empty = width - filled
    return "█" * filled + "░" * empty


def make_spinner(frame: int) -> str:
    """Get spinner character for given frame."""
    return SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]


def random_sparkle() -> str:
    """Get random sparkle character."""
    sparkles = ["✦", "✧", "★", "☆", "◆", "◇", "●", "○"]
    return random.choice(sparkles)


def format_time_remaining(seconds: float) -> str:
    """Format remaining time for display."""
    secs = int(seconds)
    if secs >= 10:
        return f"{secs:02d}"
    else:
        return f" {secs}"

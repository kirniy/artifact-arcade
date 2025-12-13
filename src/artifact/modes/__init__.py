"""Game modes for ARTIFACT."""

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.modes.manager import ModeManager
from artifact.modes.fortune import FortuneMode
from artifact.modes.zodiac import ZodiacMode
from artifact.modes.ai_prophet import AIProphetMode
from artifact.modes.roulette import RouletteMode
from artifact.modes.quiz import QuizMode

__all__ = [
    # Base
    "BaseMode",
    "ModeContext",
    "ModeResult",
    "ModePhase",
    # Manager
    "ModeManager",
    # Modes
    "FortuneMode",
    "ZodiacMode",
    "AIProphetMode",
    "RouletteMode",
    "QuizMode",
]

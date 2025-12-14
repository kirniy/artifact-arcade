"""Game modes for ARTIFACT."""

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.modes.manager import ModeManager
from artifact.modes.fortune import FortuneMode
from artifact.modes.zodiac import ZodiacMode
from artifact.modes.ai_prophet import AIProphetMode
from artifact.modes.roulette import RouletteMode
from artifact.modes.quiz import QuizMode
from artifact.modes.squid_game import SquidGameMode
from artifact.modes.guess_me import GuessMeMode
from artifact.modes.autopsy import AutopsyMode
from artifact.modes.roast import RoastMeMode

__all__ = [
    "BaseMode",
    "ModeContext",
    "ModeResult",
    "IdleMode",
    "PhotoBoothMode",
    "FortuneMode",
    "RouletteMode",
    "KaraokeMode", 
    "SquidGameMode",
    "GuessMeMode",
    "AutopsyMode",
    "RoastMeMode",
    "AIProphetMode",
    "QuizMode",
]

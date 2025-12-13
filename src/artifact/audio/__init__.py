"""
ARTIFACT Audio System - Synthwave Arcade Sounds.

Procedural audio generation for that retro 80s arcade feel.
Think Stranger Things, synthwave, and classic arcade cabinets.
"""

from .engine import AudioEngine
from .synth import SynthVoice, WaveType

__all__ = ["AudioEngine", "SynthVoice", "WaveType"]

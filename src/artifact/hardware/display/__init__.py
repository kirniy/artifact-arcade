"""Display drivers for ARTIFACT."""

from ..base import Display, TextDisplay
from .hdmi import HDMIDisplay, HDMIDisplayKMSDual, HDMIDisplayScaled
from .ws2812b import WS2812BDisplay, WS2812BDisplayMock
from .lcd import I2CLCDDisplay, I2CLCDDisplayMock

__all__ = [
    # Base classes
    "Display",
    "TextDisplay",
    # HDMI (main display via T50)
    "HDMIDisplay",
    "HDMIDisplayKMSDual",
    "HDMIDisplayScaled",
    # WS2812B (ticker LED strip)
    "WS2812BDisplay",
    "WS2812BDisplayMock",
    # I2C LCD (16x2 character display)
    "I2CLCDDisplay",
    "I2CLCDDisplayMock",
]

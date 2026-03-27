"""Hardware abstraction layer for ARTIFACT.

Keep package imports light: low-level modules such as the WS2812B ticker driver
should be importable in isolation without pulling in the full runner/audio
stack.
"""

from importlib import import_module

from .base import AudioPlayer, Camera, Display, InputDevice, Printer, TextDisplay

__all__ = [
    "Display",
    "TextDisplay",
    "InputDevice",
    "Camera",
    "Printer",
    "AudioPlayer",
    "HardwareRunner",
    "HardwareConfig",
]


def __getattr__(name: str):
    if name in {"HardwareRunner", "HardwareConfig"}:
        module = import_module(".runner", __name__)
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

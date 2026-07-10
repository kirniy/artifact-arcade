import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.modes.base import ModePhase
from artifact.modes.photobooth import PhotoboothMode, PhotoboothState


def _mode(*, phase: ModePhase = ModePhase.ACTIVE, style: str = "summer_camp") -> PhotoboothMode:
    mode = object.__new__(PhotoboothMode)
    mode.phase = phase
    mode._state = PhotoboothState()
    mode._theme = SimpleNamespace(ai_style_key=style, ticker_idle="SUMMER")
    mode._time_in_phase = 1234.0
    return mode


def test_ticker_copy_covers_complete_summer_camp_journey() -> None:
    mode = _mode()
    assert mode._get_ticker_presentation() == ("SUMMER", (255, 255, 255))

    mode._state.awaiting_camera_selection = True
    assert mode._get_ticker_presentation() == ("СПЕРЕДИ", (255, 255, 255))
    mode._state.selected_camera_id = "hdmi"
    assert mode._get_ticker_presentation() == ("СЗАДИ", (255, 255, 255))

    mode._state.awaiting_camera_selection = False
    mode.phase = ModePhase.PROCESSING
    mode._state.countdown = 3
    assert mode._get_ticker_presentation() == ("3", (255, 255, 255))

    mode._state.countdown = 0
    mode._state.is_generating = True
    assert mode._get_ticker_presentation() == ("НЕ УХОДИ", (255, 40, 40))

    mode._state.is_generating = False
    mode._state.show_result = True
    mode._state.result_view = "photo"
    assert mode._get_ticker_presentation() == ("ГОТОВО", (255, 255, 255))
    mode._state.result_view = "qr"
    assert mode._get_ticker_presentation() == ("QR", (255, 255, 255))


def test_render_ticker_uses_single_idle_renderer_on_black(monkeypatch) -> None:
    mode = _mode(phase=ModePhase.RESULT)
    mode._state.show_result = True
    mode._state.result_view = "photo"
    calls = []

    monkeypatch.setattr(
        "artifact.modes.photobooth.render_idle_style_ticker_text",
        lambda buffer, text, color, time_ms: calls.append((buffer.copy(), text, color, time_ms)),
    )

    import numpy as np

    buffer = np.full((8, 48, 3), 255, dtype=np.uint8)
    mode.render_ticker(buffer)

    assert len(calls) == 1
    cleared_buffer, text, color, time_ms = calls[0]
    assert not cleared_buffer.any()
    assert (text, color, time_ms) == ("ГОТОВО", (255, 255, 255), 1234.0)

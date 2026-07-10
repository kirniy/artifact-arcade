import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.modes.base import ModePhase
from artifact.modes.photobooth import PhotoboothMode, PhotoboothState
from artifact.graphics.text_utils import render_idle_style_ticker_text


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
    assert mode._get_ticker_presentation() == ("ЖДИ", (255, 255, 255))

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


def test_summer_camp_ticker_words_are_static_white_on_black() -> None:
    import numpy as np

    for text in ("SUMMER", "CAMP", "VNVNC", "СТАРТ", "ЖДИ", "ГОТОВО", "QR"):
        first = np.zeros((8, 48, 3), dtype=np.uint8)
        later = np.zeros_like(first)
        render_idle_style_ticker_text(first, text, (255, 255, 255), 0.0)
        render_idle_style_ticker_text(later, text, (255, 255, 255), 1900.0)

        assert first.any(), text
        assert np.array_equal(first, later), text
        assert np.array_equal(first[:, :, 0], first[:, :, 1]), text
        assert np.array_equal(first[:, :, 1], first[:, :, 2]), text

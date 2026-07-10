import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.modes.base import ModePhase
from artifact.graphics.text_utils import render_idle_style_ticker_text
from artifact.modes.manager import ModeManager
from artifact.modes.photobooth import PhotoboothMode, PhotoboothState
from artifact.modes.photobooth_themes import THEMES


SUMMER_ACCENT = (198, 236, 56)


def _mode(*, phase: ModePhase = ModePhase.ACTIVE, style: str = "summer_camp") -> PhotoboothMode:
    mode = object.__new__(PhotoboothMode)
    mode.phase = phase
    mode._state = PhotoboothState()
    mode._theme = SimpleNamespace(ai_style_key=style, ticker_idle="SUMMER")
    mode.THEME_CHROME = SUMMER_ACCENT
    mode._time_in_phase = 1234.0
    return mode


def test_ticker_copy_covers_complete_summer_camp_journey() -> None:
    mode = _mode()
    assert mode._get_ticker_presentation() == ("SUMMER", SUMMER_ACCENT)

    mode._state.awaiting_camera_selection = True
    assert mode._get_ticker_presentation() == ("СПЕРЕДИ", SUMMER_ACCENT)
    mode._state.selected_camera_id = "hdmi"
    assert mode._get_ticker_presentation() == ("СЗАДИ", SUMMER_ACCENT)

    mode._state.awaiting_camera_selection = False
    mode.phase = ModePhase.PROCESSING
    mode._state.countdown = 3
    assert mode._get_ticker_presentation() == ("3", SUMMER_ACCENT)

    mode._state.countdown = 0
    mode._state.is_generating = True
    assert mode._get_ticker_presentation() == ("ЖДИ", SUMMER_ACCENT)
    mode._time_in_phase = 4234.0
    assert mode._get_ticker_presentation() == ("НЕ УХОДИ", SUMMER_ACCENT)

    mode._state.is_generating = False
    mode._state.show_result = True
    mode._state.result_view = "photo"
    assert mode._get_ticker_presentation() == ("ФОТО", SUMMER_ACCENT)
    mode._state.result_view = "qr"
    assert mode._get_ticker_presentation() == ("QR", SUMMER_ACCENT)


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
    assert (text, color, time_ms) == ("ФОТО", SUMMER_ACCENT, 1234.0)


def test_summer_camp_ticker_words_are_static_theme_color_on_black() -> None:
    import numpy as np

    for text in ("SUMMER", "CAMP", "VNVNC", "СТАРТ", "ЖДИ", "ФОТО", "QR"):
        first = np.zeros((8, 48, 3), dtype=np.uint8)
        later = np.zeros_like(first)
        render_idle_style_ticker_text(first, text, SUMMER_ACCENT, 0.0)
        render_idle_style_ticker_text(later, text, SUMMER_ACCENT, 1900.0)

        assert first.any(), text
        assert np.array_equal(first, later), text
        assert set(map(tuple, first.reshape(-1, 3))) <= {(0, 0, 0), SUMMER_ACCENT}, text


def test_ticker_skips_post_render_overlay_for_all_modes() -> None:
    import numpy as np

    manager = object.__new__(ModeManager)
    manager._state = SimpleNamespace(name="test")
    manager._idle_animation = SimpleNamespace(render_ticker=lambda buffer: None)
    manager._current_mode = None
    overlay_calls = []
    manager._display_coordinator = SimpleNamespace(
        render_ticker_overlay=lambda buffer: overlay_calls.append(buffer.copy())
    )

    from artifact.modes.manager import ManagerState

    manager._state = ManagerState.IDLE
    buffer = np.zeros((8, 48, 3), dtype=np.uint8)
    manager.render_ticker(buffer)

    assert overlay_calls == []


def test_every_theme_idle_label_fits_and_is_static() -> None:
    import numpy as np
    from artifact.graphics.fonts import load_font

    font = load_font("cyrillic")
    for theme in THEMES.values():
        assert font.measure_text(theme.ticker_idle)[0] <= 48, theme.id

        first = np.zeros((8, 48, 3), dtype=np.uint8)
        later = np.zeros_like(first)
        render_idle_style_ticker_text(first, theme.ticker_idle, theme.theme_chrome, 0.0)
        render_idle_style_ticker_text(later, theme.ticker_idle, theme.theme_chrome, 1900.0)

        assert first.any(), theme.id
        assert np.array_equal(first, later), theme.id

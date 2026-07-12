import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.modes.photobooth import (
    PhotoboothMode,
    PhotoboothState,
    get_configured_photobooth_modes,
    photobooth_ai_enabled,
)


def test_photobooth_ai_can_be_disabled_globally(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_AI_ENABLED", "false")
    assert photobooth_ai_enabled() is False


def test_photobooth_ai_defaults_to_enabled(monkeypatch) -> None:
    monkeypatch.delenv("PHOTOBOOTH_AI_ENABLED", raising=False)
    assert photobooth_ai_enabled() is True


def test_raw_mode_finishes_capture_without_starting_ai() -> None:
    mode = PhotoboothMode.__new__(PhotoboothMode)
    mode._state = PhotoboothState()
    mode._ai_enabled = False
    mode._camera2_ai_enabled = True
    mode._capture_selected_camera_jpeg = lambda quality: b"raw-jpeg"
    mode._decode_photo_frame = lambda _jpeg: "decoded-frame"
    finished = []
    mode._finish_raw_capture_result = lambda: finished.append(True)

    mode._do_flash_and_capture()

    assert mode._state.photo_bytes == b"raw-jpeg"
    assert mode._state.photo_frame == "decoded-frame"
    assert finished == [True]


def test_default_photobooth_menu_is_2k17_only(monkeypatch) -> None:
    monkeypatch.delenv("PHOTOBOOTH_MENU_MODES", raising=False)

    modes = get_configured_photobooth_modes()

    assert [mode.name for mode in modes] == ["photobooth_mode_1"]
    assert modes[0].theme_id_override == "2k17"
    assert modes[0].display_name == "2K17"


def test_empty_photobooth_menu_falls_back_to_2k17_only(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", " ")

    modes = get_configured_photobooth_modes()

    assert [mode.name for mode in modes] == ["photobooth_mode_1"]
    assert modes[0].theme_id_override == "2k17"


def test_unknown_photobooth_menu_falls_back_to_2k17_only(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "nope")

    modes = get_configured_photobooth_modes()

    assert [mode.name for mode in modes] == ["photobooth_mode_1"]
    assert modes[0].theme_id_override == "2k17"

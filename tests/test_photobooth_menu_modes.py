import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.modes.photobooth import get_configured_photobooth_modes


def test_default_photobooth_menu_is_office_core_only(monkeypatch) -> None:
    monkeypatch.delenv("PHOTOBOOTH_MENU_MODES", raising=False)

    modes = get_configured_photobooth_modes()

    assert [mode.name for mode in modes] == ["photobooth_mode_1"]
    assert modes[0].theme_id_override == "office-core"
    assert modes[0].display_name == "OFFICE\nCORE"


def test_empty_photobooth_menu_falls_back_to_office_core_only(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", " ")

    modes = get_configured_photobooth_modes()

    assert [mode.name for mode in modes] == ["photobooth_mode_1"]
    assert modes[0].theme_id_override == "office-core"


def test_unknown_photobooth_menu_falls_back_to_office_core_only(monkeypatch) -> None:
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", "nope")

    modes = get_configured_photobooth_modes()

    assert [mode.name for mode in modes] == ["photobooth_mode_1"]
    assert modes[0].theme_id_override == "office-core"

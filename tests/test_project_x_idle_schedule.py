"""The idle video must follow the same dated theme as the menu and photographs."""
import pytest

from artifact.animation.idle_scenes import RotatingIdleAnimation
from artifact.modes.photobooth_themes import THEMES


@pytest.mark.parametrize(
    "active_theme,stored_theme,expected_variant",
    [
        ("vse-svoi", "project-x", "vse_svoi"),
        ("project-x", "tropical-thai", "project_x"),
        ("vse-svoi", "tropical-thai", "vse_svoi"),
    ],
)
def test_dated_schedule_wins_over_stored_idle_theme(
    monkeypatch, active_theme, stored_theme, expected_variant
):
    monkeypatch.setenv("ARTIFACT_CLUB_THEME_SCHEDULE", "project-x-2026")
    monkeypatch.setenv("PHOTOBOOTH_THEME", stored_theme)
    monkeypatch.setenv("PHOTOBOOTH_MENU_MODES", stored_theme)
    monkeypatch.setattr(
        "artifact.modes.club_theme_schedule.scheduled_theme", lambda: active_theme
    )
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = THEMES[active_theme]

    assert idle._detect_idle_variant() == expected_variant


def test_manual_theme_is_preserved_without_dated_schedule(monkeypatch):
    monkeypatch.delenv("ARTIFACT_CLUB_THEME_SCHEDULE", raising=False)
    monkeypatch.setenv("PHOTOBOOTH_THEME", "tropical-thai")
    idle = RotatingIdleAnimation.__new__(RotatingIdleAnimation)
    idle._theme = THEMES["tropical-thai"]

    assert idle._detect_idle_variant() == "tropical_thai"

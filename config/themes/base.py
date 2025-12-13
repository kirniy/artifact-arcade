"""
Base theme class and theme loading utilities.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ThemeColors:
    """Theme color palette."""
    primary: str = "#7B2D8E"      # Main accent color
    secondary: str = "#FFD700"    # Secondary accent
    background: str = "#0D0D1A"   # Background color
    text: str = "#E0E0FF"         # Text color
    accent: str = "#00FF88"       # Highlight color
    error: str = "#FF4444"        # Error color
    success: str = "#44FF44"      # Success color

    def to_rgb(self, color_name: str) -> tuple[int, int, int]:
        """Convert hex color to RGB tuple."""
        hex_color = getattr(self, color_name, self.text)
        hex_color = hex_color.lstrip("#")
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


@dataclass
class ThemeAnimation:
    """Animation configuration."""
    type: str = "default"
    speed: float = 1.0
    duration: int = 1000  # milliseconds
    particle_count: int = 50
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class ThemeAnimations:
    """Theme animation set."""
    idle: ThemeAnimation = field(default_factory=ThemeAnimation)
    transition: ThemeAnimation = field(default_factory=ThemeAnimation)
    reveal: ThemeAnimation = field(default_factory=ThemeAnimation)
    processing: ThemeAnimation = field(default_factory=ThemeAnimation)


@dataclass
class ThemeSounds:
    """Theme sound configuration."""
    button_press: str = "shared/click.wav"
    mode_enter: str = "shared/whoosh.wav"
    result_reveal: str = "shared/reveal.wav"
    error: str = "shared/error.wav"
    success: str = "shared/success.wav"
    ambient: str | None = None


@dataclass
class ThemeFonts:
    """Theme font configuration."""
    main: str = "pixel_8x8"
    accent: str = "cyrillic_6x8"
    title: str = "pixel_8x8"


@dataclass
class ThemeSprites:
    """Theme sprite configuration."""
    folder: str = "shared"
    idle_bg: str | None = None
    border: str | None = None
    logo: str | None = None


@dataclass
class ThemeMessages:
    """Theme-specific messages (localized)."""
    welcome: str = "ARTIFACT"
    fortune_prefix: str = "Предсказание:"
    processing: str = "Обработка..."
    ready: str = "НАЖМИ КНОПКУ"
    error: str = "Ошибка"


@dataclass
class Theme:
    """Complete theme configuration."""
    name: str = "default"
    description: str = "Default theme"
    style: str = "mystical"  # mystical, arcade, modern

    colors: ThemeColors = field(default_factory=ThemeColors)
    animations: ThemeAnimations = field(default_factory=ThemeAnimations)
    sounds: ThemeSounds = field(default_factory=ThemeSounds)
    fonts: ThemeFonts = field(default_factory=ThemeFonts)
    sprites: ThemeSprites = field(default_factory=ThemeSprites)
    messages: ThemeMessages = field(default_factory=ThemeMessages)

    @classmethod
    def from_yaml(cls, data: dict[str, Any]) -> "Theme":
        """Create theme from YAML data."""
        theme = cls(
            name=data.get("name", "default"),
            description=data.get("description", ""),
            style=data.get("style", "mystical"),
        )

        if "colors" in data:
            theme.colors = ThemeColors(**data["colors"])

        if "animations" in data:
            anims = data["animations"]
            theme.animations = ThemeAnimations(
                idle=ThemeAnimation(**anims.get("idle", {})),
                transition=ThemeAnimation(**anims.get("transition", {})),
                reveal=ThemeAnimation(**anims.get("reveal", {})),
                processing=ThemeAnimation(**anims.get("processing", {})),
            )

        if "sounds" in data:
            theme.sounds = ThemeSounds(**data["sounds"])

        if "fonts" in data:
            theme.fonts = ThemeFonts(**data["fonts"])

        if "sprites" in data:
            theme.sprites = ThemeSprites(**data["sprites"])

        if "messages" in data:
            theme.messages = ThemeMessages(**data["messages"])

        return theme


def load_theme(theme_name: str, themes_path: Path | None = None) -> Theme:
    """
    Load a theme from YAML file.

    Args:
        theme_name: Name of the theme (without .yaml extension)
        themes_path: Path to themes directory

    Returns:
        Theme instance
    """
    if themes_path is None:
        themes_path = Path(__file__).parent

    theme_file = themes_path / f"{theme_name}.yaml"

    if not theme_file.exists():
        # Return default theme
        return Theme(name=theme_name)

    with open(theme_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return Theme.from_yaml(data)


def list_themes(themes_path: Path | None = None) -> list[str]:
    """List available themes."""
    if themes_path is None:
        themes_path = Path(__file__).parent

    themes = []
    for f in themes_path.glob("*.yaml"):
        themes.append(f.stem)

    return sorted(themes)

"""Photobooth Theme Configuration.

Defines themes for different party events. Each theme has:
- Logo path
- Event name and dates
- Color scheme
- Ticker text
- AI prompt variations

Switch themes by setting PHOTOBOOTH_THEME environment variable:
- "boilingroom"
- "tripvenice"
- "loveintheair"
- "malchishnik" (default)
"""

import os
from dataclasses import dataclass
from typing import Tuple, List


@dataclass
class PhotoboothTheme:
    """Configuration for a photobooth theme."""

    # Identity
    id: str
    event_name: str  # e.g., "BOILING ROOM", "TRIP:VENICE"
    event_date: str  # e.g., "31.01", "06.02-07.02"

    # Visual
    logo_filename: str  # In assets/images/
    theme_chrome: Tuple[int, int, int]  # Primary accent color
    theme_red: Tuple[int, int, int]  # Secondary color
    theme_black: Tuple[int, int, int]  # Background

    # Text
    ticker_idle: str  # Shown on ticker when idle
    lcd_prefix: str  # Shown on LCD during countdown
    description: str  # Mode description

    # AI style identifier (maps to prompt variations)
    ai_style_key: str  # e.g., "boilingroom", "tripvenice"


# =============================================================================
# THEME: BOILING ROOM (January 31, 2025)
# =============================================================================
BOILINGROOM_THEME = PhotoboothTheme(
    id="boilingroom",
    event_name="BOILING ROOM",
    event_date="31.01",
    logo_filename="boilingroom.png",
    theme_chrome=(192, 192, 192),  # Chrome silver
    theme_red=(139, 0, 0),  # Deep red
    theme_black=(0, 0, 0),  # Black
    ticker_idle="BOILING",
    lcd_prefix="BOILING",
    description="BOILING ROOM",
    ai_style_key="boilingroom",
)


# =============================================================================
# THEME: TRIP:VENICE (February 6-7, 2025)
# =============================================================================
TRIPVENICE_THEME = PhotoboothTheme(
    id="tripvenice",
    event_name="TRIP:VENICE",
    event_date="06.02-07.02",
    logo_filename="tripvenice.png",
    theme_chrome=(218, 165, 32),  # Gold - Venetian carnival gold
    theme_red=(128, 0, 32),  # Burgundy - deep carnival red
    theme_black=(20, 10, 30),  # Deep purple-black - mysterious carnival night
    ticker_idle="VENICE",
    lcd_prefix="VENICE",
    description="TRIP:VENICE",
    ai_style_key="tripvenice",
)


# =============================================================================
# THEME: LOVE IN THE AIR (February 13-14, 2026)
# =============================================================================
LOVEINTHEAIR_THEME = PhotoboothTheme(
    id="loveintheair",
    event_name="LOVE IN THE AIR",
    event_date="13.02-14.02",
    logo_filename="loveintheair.png",
    theme_chrome=(219, 112, 147),  # Pink - romantic rose pink
    theme_red=(178, 34, 34),  # Deep rose red
    theme_black=(60, 20, 40),  # Dark burgundy-purple
    ticker_idle="LOVE",
    lcd_prefix="LOVE",
    description="LOVE IN THE AIR",
    ai_style_key="loveintheair",
)


# =============================================================================
# THEME: МАЛЬЧИШНИК (February 20-22, 2026)
# =============================================================================
MALCHISHNIK_THEME = PhotoboothTheme(
    id="malchishnik",
    event_name="МАЛЬЧИШНИК",
    event_date="20.02-22.02",
    logo_filename="malchishnik.png",
    theme_chrome=(210, 170, 60),   # Dirty amber gold — old film, disposable camera
    theme_red=(180, 35, 35),       # Blood red — Hangover chaos
    theme_black=(12, 8, 5),        # Near-black — nightclub darkness
    ticker_idle="BACHELORS",       # 9 Latin chars — fits 48px ticker
    lcd_prefix="МАЛЬЧИ",          # 6 Cyrillic chars — fits LCD countdown
    description="МАЛЬЧИШНИК",
    ai_style_key="malchishnik",
)


# =============================================================================
# THEME REGISTRY
# =============================================================================
THEMES = {
    "boilingroom": BOILINGROOM_THEME,
    "tripvenice": TRIPVENICE_THEME,
    "loveintheair": LOVEINTHEAIR_THEME,
    "malchishnik": MALCHISHNIK_THEME,
}

# Default theme
DEFAULT_THEME = "malchishnik"


def get_current_theme() -> PhotoboothTheme:
    """Get the currently active theme based on environment variable.

    Set PHOTOBOOTH_THEME environment variable to switch themes:
    - export PHOTOBOOTH_THEME=boilingroom
    - export PHOTOBOOTH_THEME=tripvenice

    Returns:
        PhotoboothTheme instance for the active theme
    """
    theme_id = os.environ.get("PHOTOBOOTH_THEME", DEFAULT_THEME).lower()

    if theme_id not in THEMES:
        # Fallback to default if invalid theme specified
        theme_id = DEFAULT_THEME

    return THEMES[theme_id]


def get_theme_by_id(theme_id: str) -> PhotoboothTheme:
    """Get a specific theme by ID.

    Args:
        theme_id: Theme identifier (e.g., "boilingroom", "tripvenice")

    Returns:
        PhotoboothTheme instance
    """
    return THEMES.get(theme_id.lower(), THEMES[DEFAULT_THEME])


def list_available_themes() -> List[str]:
    """List all available theme IDs.

    Returns:
        List of theme identifiers
    """
    return list(THEMES.keys())

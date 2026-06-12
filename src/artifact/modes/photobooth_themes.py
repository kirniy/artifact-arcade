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
- "malchishnik"
- "fiesta"
- "feyphoria"
- "brainrot"
- "wedding"
- "whatsapp"
- "fiesta" (default)
"""

import os
from dataclasses import dataclass
from typing import Optional, Tuple, List


@dataclass(frozen=True)
class PhotoboothMenuVariant:
    """Selector metadata for one menu slot under a single active theme."""

    display_name: str
    description: str
    color: Optional[Tuple[int, int, int]] = None
    prompt_variation_index: Optional[int] = None


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
    party_date_rollover_hour: Optional[int] = None  # Use previous date before this Moscow hour
    footer_date_mode: str = "date"  # "date" or "weekday_ru"
    reference_image_filenames: Tuple[str, ...] = ()
    menu_display_name: Optional[str] = None  # Optional selector label override
    menu_description: Optional[str] = None  # Optional selector ticker description
    menu_color: Optional[Tuple[int, int, int]] = None  # Optional selector accent color
    menu_variants: Tuple[PhotoboothMenuVariant, ...] = ()


# =============================================================================
# THEME: BOILING ROOM (March 27-29, 2026)
# =============================================================================
BOILINGROOM_THEME = PhotoboothTheme(
    id="boilingroom",
    event_name="BOILING ROOM",
    event_date="27.03-29.03",
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
# THEME: ФЕЙФОРИЯ (March 6-8, 2026)
# =============================================================================
FEYPHORIA_THEME = PhotoboothTheme(
    id="feyphoria",
    event_name="ФЕЙФОРИЯ",
    event_date="06-08.03",
    logo_filename="feyphoria.png",
    theme_chrome=(207, 155, 120),     # Rose gold — enchanted fairy metallic
    theme_red=(120, 30, 50),          # Burgundy rose — deep botanical accent
    theme_black=(10, 46, 26),         # Deep emerald green — enchanted forest night
    ticker_idle="FEYPHORIA",          # 9 Latin chars — fits 48px ticker
    lcd_prefix="ФЕЙФОР",             # 6 Cyrillic chars — fits LCD countdown
    description="ФЕЙФОРИЯ",
    ai_style_key="feyphoria",
)


# =============================================================================
# THEME: FIESTA (March 13-14, 2026)
# =============================================================================
FIESTA_THEME = PhotoboothTheme(
    id="fiesta",
    event_name="ФИЕСТА",
    event_date="13.03-14.03",
    logo_filename="fiesta.png",
    theme_chrome=(255, 140, 90),    # Warm peach-orange, party accent
    theme_red=(180, 30, 40),        # Saturated fiesta red
    theme_black=(8, 14, 20),        # Deep charcoal-night backdrop
    ticker_idle="ФИЕСТА",
    lcd_prefix="ФИЕСТА",
    description="ФИЕСТА",
    ai_style_key="fiesta",
)


# =============================================================================
# THEME: НОЧЬ В БОЛЬШОМ ГОРОДЕ (March 20-21, 2026)
# =============================================================================
BIGCITYLIFE_THEME = PhotoboothTheme(
    id="bigcitylife",
    event_name="НОЧЬ В БОЛЬШОМ ГОРОДЕ",
    event_date="20.03-21.03",
    logo_filename="bigcitylife.png",
    theme_chrome=(255, 220, 50),     # NYC yellow cab / street neon
    theme_red=(200, 30, 30),         # Graffiti red
    theme_black=(8, 8, 12),          # Deep night city
    ticker_idle="BIGCITY",           # 7 Latin chars
    lcd_prefix="NYC",                # 3 chars for LCD
    description="НОЧЬ В БОЛЬШОМ ГОРОДЕ",
    ai_style_key="bigcitylife",
)


# =============================================================================
# THEME: ITALIAN BRAINROT (Cringe Party, April 4, 2026)
# =============================================================================
BRAINROT_THEME = PhotoboothTheme(
    id="brainrot",
    event_name="КРИНЖ ПАТИ",
    event_date="03.04-05.04",
    logo_filename="brainrot.png",
    theme_chrome=(255, 232, 72),    # Acid yellow headline glow
    theme_red=(255, 70, 166),       # Candy-magenta outer glow
    theme_black=(40, 8, 62),        # Deep violet meme-night background
    ticker_idle="КРИНЖ ПАТИ",
    lcd_prefix="BRAINR",
    description="ИТАЛЬЯНСКИЙ БРЕЙНРОТ",
    menu_display_name="BRAINROT",
    menu_description="КРИНЖ ПАТИ",
    menu_color=(255, 232, 72),
    ai_style_key="brainrot",
)


# =============================================================================
# THEME: СВАДЬБА 2004 (Cringe Party, April 4, 2026)
# =============================================================================
WEDDING_THEME = PhotoboothTheme(
    id="wedding",
    event_name="ФАВТФАА ПЭПЭ",
    event_date="03.04-05.04",
    logo_filename="wedding.png",
    theme_chrome=(255, 214, 232),   # Pink wedding chrome
    theme_red=(219, 72, 140),       # Satin-magenta accent
    theme_black=(58, 26, 54),       # Plum VHS shadow
    ticker_idle="ФАВТФАА ПЭПЭ",
    lcd_prefix="СВАД04",
    description="СЕЛЬСКИЙ ГЛАМУР",
    menu_display_name="ЛЮБОВЬ\nИ ГОЛУБИ",
    menu_description="СЕЛЬСКАЯ СВАДЬБА",
    menu_color=(255, 214, 232),
    ai_style_key="wedding",
)


# =============================================================================
# THEME: WHATSAPP ОТКРЫТКИ (Cringe Party, April 4, 2026)
# =============================================================================
WHATSAPP_THEME = PhotoboothTheme(
    id="whatsapp",
    event_name="ПЭПЭШНЕЙШЕ",
    event_date="03.04-05.04",
    logo_filename="whatsapp.png",
    theme_chrome=(255, 218, 84),    # Gold postcard lettering
    theme_red=(255, 96, 152),       # Rose-pink sparkle accent
    theme_black=(8, 86, 56),        # WhatsApp green shadow
    ticker_idle="ПЭПЭШНЕЙШЕ",
    lcd_prefix="WAPP",
    description="БАБУШКИН ЧАТ",
    menu_display_name="WA\nОТКРЫТКИ",
    menu_description="ОТКРЫТКА В ЧАТ",
    menu_color=(80, 215, 120),
    ai_style_key="whatsapp",
)


# =============================================================================
# THEME: SLAVIC CORE - СЛАВЯНСКАЯ ДУША (April 18, 2026)
# =============================================================================
SLAVIC_SOUL_THEME = PhotoboothTheme(
    id="slavic_soul",
    event_name="СЛАВЯНСКАЯ ДУША",
    event_date="18.04",
    logo_filename="slaviccore-emblem.png",
    theme_chrome=(255, 208, 126),
    theme_red=(158, 42, 36),
    theme_black=(6, 3, 2),
    ticker_idle="ДУША",
    lcd_prefix="ДУША",
    description="СЛАВЯНСКАЯ ДУША",
    menu_display_name="HAPPY B'DAY\nVNVNC",
    menu_description="LUXURY BIRTHDAY POSTER",
    menu_color=(255, 210, 126),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="slavic_soul",
    reference_image_filenames=("slaviccore-vnvnc.png",),
)


# =============================================================================
# THEME: SLAVIC CORE - СЛАВЯНСКИЕ СКАЗКИ (April 18, 2026)
# =============================================================================
SLAVIC_TALES_THEME = PhotoboothTheme(
    id="slavic_tales",
    event_name="СЛАВЯНСКИЕ СКАЗКИ",
    event_date="18.04",
    logo_filename="slaviccore-emblem.png",
    theme_chrome=(238, 196, 120),
    theme_red=(132, 34, 48),
    theme_black=(9, 5, 6),
    ticker_idle="СКАЗКИ",
    lcd_prefix="СКАЗК",
    description="СЛАВЯНСКИЕ СКАЗКИ",
    menu_display_name="ПОСТОЯННИК\nВИНОВНИЦЫ",
    menu_description="VIP LICENSE POSTER",
    menu_color=(214, 92, 106),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="slavic_tales",
    reference_image_filenames=("slaviccore-vnvnc.png",),
)


# =============================================================================
# THEME: SLAVIC CORE - БАННЫЙ ШИК (April 18, 2026)
# =============================================================================
BANYA_CHIC_THEME = PhotoboothTheme(
    id="banya_chic",
    event_name="БАННЫЙ ШИК",
    event_date="18.04",
    logo_filename="slaviccore-emblem.png",
    theme_chrome=(248, 221, 144),
    theme_red=(180, 96, 44),
    theme_black=(7, 4, 2),
    ticker_idle="БАНЯ",
    lcd_prefix="БАНЯ",
    description="БАННЫЙ ШИК",
    menu_display_name="RAP\nGOD",
    menu_description="HYPER-LUXURY HIP-HOP POSTER",
    menu_color=(255, 226, 150),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="banya_chic",
    reference_image_filenames=("slaviccore-vnvnc.png",),
)


# =============================================================================
# THEME: VNVNC B'DAY (9 years)
# =============================================================================
VNVNC_BDAY_THEME = PhotoboothTheme(
    id="vnvnc-bday",
    event_name="VNVNC B'DAY",
    event_date="9 YEARS",
    logo_filename="vnvnc-bday.png",
    theme_chrome=(214, 216, 221),
    theme_red=(179, 19, 23),
    theme_black=(11, 11, 13),
    ticker_idle="BDAYVNV",
    lcd_prefix="B'DAY",
    description="VNVNC B'DAY",
    menu_display_name="B'DAY\nMODE",
    menu_description="VNVNC B'DAY",
    menu_color=(214, 216, 221),
    menu_variants=(
        PhotoboothMenuVariant(
            display_name="B'DAY\nMODE",
            description="LUXURY BIRTHDAY POSTER",
            color=(255, 210, 126),
            prompt_variation_index=0,
        ),
        PhotoboothMenuVariant(
            display_name="КАРТА\nVNVNC",
            description="VIP LICENSE POSTER",
            color=(214, 92, 106),
            prompt_variation_index=1,
        ),
        PhotoboothMenuVariant(
            display_name="RAP\nGOD",
            description="HYPER-LUXURY HIP-HOP POSTER",
            color=(255, 226, 150),
            prompt_variation_index=2,
        ),
    ),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="vnvnc_bday",
    reference_image_filenames=("emblem-v1-chrome-oval.png",),
)


# =============================================================================
# THEME: MTV NIGHT — glossy 90s MTV club poster
# =============================================================================
MTV_NIGHT_THEME = PhotoboothTheme(
    id="mtv-night",
    event_name="MTV NIGHT",
    event_date="",
    logo_filename="mtv-night.png",
    theme_chrome=(233, 236, 255),
    theme_red=(255, 41, 143),
    theme_black=(8, 6, 18),
    ticker_idle="MTVNIGHT",
    lcd_prefix="MTVNT",
    description="MTV NIGHT",
    menu_display_name="MTV\nNIGHT",
    menu_description="GLOSSY 90S POSTER",
    menu_color=(233, 236, 255),
    menu_variants=(
        PhotoboothMenuVariant(
            display_name="MTV\nNIGHT",
            description="GLOSSY 90S POSTER",
            color=(233, 236, 255),
            prompt_variation_index=0,
        ),
        PhotoboothMenuVariant(
            display_name="LOGO\nFEVER",
            description="HYPER-BRANDED MTV COLLAGE",
            color=(255, 41, 143),
            prompt_variation_index=1,
        ),
    ),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="mtv_night",
    reference_image_filenames=(),
)


# =============================================================================
# THEME: КОРОЛЕВСТВО ТЕНЕЙ — gothic chrome castle poster
# =============================================================================
SHADOW_KINGDOM_THEME = PhotoboothTheme(
    id="shadow-kingdom",
    event_name="КОРОЛЕВСТВО ТЕНЕЙ",
    event_date="",
    logo_filename="shadow-kingdom.png",
    theme_chrome=(224, 232, 242),
    theme_red=(164, 18, 42),
    theme_black=(3, 6, 10),
    ticker_idle="SHADOW",
    lcd_prefix="SHADOW",
    description="КОРОЛЕВСТВО ТЕНЕЙ",
    menu_display_name="SHADOW\nKINGDOM",
    menu_description="GOTHIC CASTLE POSTER",
    menu_color=(224, 232, 242),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="shadow_kingdom",
    reference_image_filenames=("shadow-kingdom.png",),
)


# =============================================================================
# THEME: CIRCUS MAXIMUS — Octane 3D Creepy Circus
# =============================================================================
CIRCUS_MAXIMUS_THEME = PhotoboothTheme(
    id="circus-maximus",
    event_name="CIRCUS MAXIMUS",
    event_date="",
    logo_filename="circus-maximus.png",
    theme_chrome=(255, 40, 40),
    theme_red=(180, 20, 20),
    theme_black=(0, 0, 0),
    ticker_idle="MAXIMUS",
    lcd_prefix="MAXIMUS",
    description="CIRCUS MAXIMUS — Creepy Circus",
    menu_display_name="CIRCUS\nMAXIMUS",
    menu_description="CREEPY CIRCUS",
    menu_color=(255, 40, 40),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="circus_maximus",
)


# =============================================================================
# THEME: CANDY SHOP — Pure white pink candy boutique
# =============================================================================
CANDY_SHOP_THEME = PhotoboothTheme(
    id="candy-shop",
    event_name="CANDY SHOP",
    event_date="22.05",
    logo_filename="candy-shop.png",
    theme_chrome=(255, 68, 126),
    theme_red=(192, 24, 48),
    theme_black=(255, 255, 255),
    ticker_idle="CANDY",
    lcd_prefix="CANDY",
    description="CANDY SHOP",
    menu_display_name="CANDY\nSHOP",
    menu_description="WHITE CANDY BOUTIQUE",
    menu_color=(255, 68, 126),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="candy_shop",
    reference_image_filenames=("candy-shop.png",),
)


# =============================================================================
# THEME: STREET HEAT — west coast polaroid luxury
# =============================================================================
STREET_HEAT_THEME = PhotoboothTheme(
    id="street-heat",
    event_name="STREET HEAT",
    event_date="",
    logo_filename="street-heat.png",
    theme_chrome=(205, 167, 106),
    theme_red=(160, 48, 32),
    theme_black=(255, 255, 255),
    ticker_idle="STHEAT",
    lcd_prefix="HEAT",
    description="WEST COAST POLAROID",
    menu_display_name="STREET\nHEAT",
    menu_description="WEST COAST POLAROID",
    menu_color=(205, 167, 106),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="street_heat",
    reference_image_filenames=("street-heat.png", "street-heat-scene-reference.jpg"),
)


# =============================================================================
# THEME: OFFICE CORE — pixel office equipment on pure white
# =============================================================================
OFFICE_CORE_THEME = PhotoboothTheme(
    id="office-core",
    event_name="OFFICE CORE",
    event_date="",
    logo_filename="office-core.png",
    theme_chrome=(28, 84, 196),
    theme_red=(216, 38, 38),
    theme_black=(255, 255, 255),
    ticker_idle="OFFICE",
    lcd_prefix="OFFICE",
    description="OFFICE CORE",
    menu_display_name="OFFICE\nCORE",
    menu_description="PIXEL OFFICE POSTER",
    menu_color=(28, 84, 196),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="office_core",
    reference_image_filenames=("office-core.png",),
)


# =============================================================================
# THEME: SUMMER CAMP — elite pixel sports camp on pure white
# =============================================================================
SUMMER_CAMP_THEME = PhotoboothTheme(
    id="summer-camp",
    event_name="SUMMER CAMP",
    event_date="",
    logo_filename="summer-camp.png",
    theme_chrome=(198, 236, 56),
    theme_red=(34, 92, 54),
    theme_black=(255, 255, 255),
    ticker_idle="SUMMER",
    lcd_prefix="CAMP",
    description="ELITE SPORTS CAMP",
    menu_display_name="SUMMER\nCAMP",
    menu_description="PIXEL SPORTS POSTER",
    menu_color=(198, 236, 56),
    party_date_rollover_hour=12,
    footer_date_mode="weekday_ru",
    ai_style_key="summer_camp",
    reference_image_filenames=("summer-camp.png",),
)


# =============================================================================
# THEME REGISTRY
# =============================================================================
THEMES = {
    "boilingroom": BOILINGROOM_THEME,
    "tripvenice": TRIPVENICE_THEME,
    "loveintheair": LOVEINTHEAIR_THEME,
    "malchishnik": MALCHISHNIK_THEME,
    "feyphoria": FEYPHORIA_THEME,
    "fiesta": FIESTA_THEME,
    "bigcitylife": BIGCITYLIFE_THEME,
    "brainrot": BRAINROT_THEME,
    "wedding": WEDDING_THEME,
    "whatsapp": WHATSAPP_THEME,
    "slavic_soul": SLAVIC_SOUL_THEME,
    "slavic_tales": SLAVIC_TALES_THEME,
    "banya_chic": BANYA_CHIC_THEME,
    "vnvnc-bday": VNVNC_BDAY_THEME,
    "mtv-night": MTV_NIGHT_THEME,
    "shadow-kingdom": SHADOW_KINGDOM_THEME,
    "circus-maximus": CIRCUS_MAXIMUS_THEME,
    "candy-shop": CANDY_SHOP_THEME,
    "street-heat": STREET_HEAT_THEME,
    "office-core": OFFICE_CORE_THEME,
    "summer-camp": SUMMER_CAMP_THEME,
}

# Default theme
DEFAULT_THEME = "summer-camp"


def get_current_theme() -> PhotoboothTheme:
    """Get the currently active theme based on environment variable.

    Set PHOTOBOOTH_THEME environment variable to switch themes:
    - export PHOTOBOOTH_THEME=boilingroom
    - export PHOTOBOOTH_THEME=tripvenice
    - export PHOTOBOOTH_THEME=malchishnik
    - export PHOTOBOOTH_THEME=feyphoria
    - export PHOTOBOOTH_THEME=fiesta
    - export PHOTOBOOTH_THEME=vnvnc-bday

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

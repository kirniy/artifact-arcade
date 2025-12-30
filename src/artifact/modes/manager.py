"""Mode manager for ARTIFACT - handles mode selection, transitions, and idle state."""

from typing import Dict, List, Optional, Type, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
import random
import math
import os

from artifact.core.events import EventBus, Event, EventType
from artifact.core.state import StateMachine, State
from artifact.animation.engine import AnimationEngine
from artifact.animation.idle_scenes import RotatingIdleAnimation
from artifact.animation.reveal_effects import RevealAnimator, RevealStyle
from artifact.graphics.renderer import Renderer
from artifact.graphics.display_coordinator import DisplayCoordinator, CrossDisplayEffect
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.modes.rapgod import RapGodMode
from artifact.audio.engine import get_audio_engine

logger = logging.getLogger(__name__)


# =============================================================================
# BANGER MODE ICONS - Pixel art for each mode (16x16 patterns)
# =============================================================================

MODE_ICONS = {
    "fortune": [  # Crystal ball
        "    ████    ",
        "  ████████  ",
        " ██░░░░░░██ ",
        "██░░░░░░░░██",
        "██░░██░░░░██",
        "██░░░░░░░░██",
        " ██░░░░░░██ ",
        "  ████████  ",
        "   ██████   ",
        "  ████████  ",
    ],
    "roulette": [  # Spinning wheel
        "   ██████   ",
        " ██░░░░░░██ ",
        "██░██░░██░██",
        "██░░░██░░░██",
        "██░░████░░██",
        "██░░░██░░░██",
        "██░██░░██░██",
        " ██░░░░░░██ ",
        "   ██████   ",
        "     ▼      ",
    ],
    "quiz": [  # Question mark podium
        "   ██████   ",
        "  ██░░░░██  ",
        "       ░░██ ",
        "      ░░██  ",
        "     ░░██   ",
        "     ░░██   ",
        "            ",
        "     ██     ",
        "  ██████████",
        " ████████████",
    ],
    "squid_game": [  # Triangle/circle/square
        "     ▲      ",
        "    ███     ",
        "   █████    ",
        "            ",
        "   ████     ",
        "   █  █     ",
        "   ████     ",
        "            ",
        "    ●●      ",
        "    ●●      ",
    ],
    "guess_me": [  # Eye with question
        "  ████████  ",
        " ██░░░░░░██ ",
        "██░░████░░██",
        "██░██████░██",
        "██░░████░░██",
        " ██░░░░░░██ ",
        "  ████████  ",
        "     ?      ",
        "            ",
        "            ",
    ],
    "autopsy": [  # Skull/X-ray
        "  ████████  ",
        " ██░░░░░░██ ",
        "██░██░░██░██",
        "██░░░░░░░░██",
        " ██░░██░░██ ",
        "  ██░░░░██  ",
        "   ██████   ",
        "    ████    ",
        "   █    █   ",
        "            ",
    ],
    "roast": [  # Fire/flame
        "     █      ",
        "    ███     ",
        "   █████    ",
        "  ███████   ",
        " █████████  ",
        "  ███████   ",
        "   █████    ",
        "    ███     ",
        "     █      ",
        "    ▓▓▓     ",
    ],
    "ai_prophet": [  # AI brain/eye
        "  ████████  ",
        " ██░░░░░░██ ",
        "██░░░██░░░██",
        "██░░████░░██",
        "██░░████░░██",
        "██░░░██░░░██",
        " ██░░░░░░██ ",
        "  ████████  ",
        "   ▀████▀   ",
        "            ",
    ],
    "flow_field": [  # Flowing particles/waves
        "█         █ ",
        " █       █  ",
        "  █  █  █   ",
        "   █ █ █    ",
        "    ███     ",
        "   █ █ █    ",
        "  █  █  █   ",
        " █       █  ",
        "█         █ ",
        "            ",
    ],
    "glitch_mirror": [  # Glitchy face
        "  ████████  ",
        " ██░░░░░░██ ",
        "██░█░░░█░░██",
        "  ░░░░░░░░  ",
        "██░░████░░██",
        "██░░░░░░░░██",
        " ██░░██░░██ ",
        "   ██████   ",
        "  █      █  ",
        "            ",
    ],
    "dither_art": [  # Dither pattern
        "█░█░█░█░█░█ ",
        "░█░█░█░█░█░ ",
        "█░█░█░█░█░█ ",
        "░█░█░█░█░█░ ",
        "█░█░█░█░█░█ ",
        "░█░█░█░█░█░ ",
        "█░█░█░█░█░█ ",
        "░█░█░█░█░█░ ",
        "█░█░█░█░█░█ ",
        "░█░█░█░█░█░ ",
    ],
    "ascii_art": [  # Text/ASCII characters
        "   ▄▀▀▄     ",
        "   █▄▄█     ",
        "   █  █     ",
        "            ",
        "   ████     ",
        "   █  █     ",
        "   ████     ",
        "            ",
        "   ░░░░     ",
        "            ",
    ],
    "particle_sculptor": [  # Exploding particles
        "    ●       ",
        "  ● ● ●     ",
        "    ██●     ",
        "  ●████●    ",
        "   ████     ",
        "  ●████●    ",
        "    ██●     ",
        "  ● ● ●     ",
        "    ●       ",
        "            ",
    ],
    "bar_runner": [  # Beer mug
        "    █████   ",
        "   █     █  ",
        "   █░░░░░█  ",
        " ███░░░░░██ ",
        " █░░░░░░░░█ ",
        " █░░░░░░░░█ ",
        " █░░░░░░░░█ ",
        " █░░░░░░░░█ ",
        "  █████████ ",
        "     ██     ",
    ],
    "rap_god": [  # Microphone
        "    ████    ",
        "   ██████   ",
        "   ██████   ",
        "   ██████   ",
        "    ████    ",
        "     ██     ",
        "     ██     ",
        "     ██     ",
        "    ████    ",
        "   ██████   ",
    ],
    "gallery": [  # Camera/photo frame
        "  ████████  ",
        " ██░░░░░░██ ",
        "██░░████░░██",
        "██░█    █░██",
        "██░█    █░██",
        "██░█    █░██",
        "██░░████░░██",
        " ██░░░░░░██ ",
        "  ████████  ",
        "    ████    ",
    ],
}

# Mode colors for visual identity - unique vibrant color per mode
MODE_COLORS = {
    # Currently active modes (in menu order)
    "fortune": (180, 100, 255),     # Mystic purple
    "ai_prophet": (0, 255, 180),    # Neon teal
    "photobooth": (255, 80, 180),   # Hot pink
    "roast": (255, 100, 30),        # Fire orange
    "squid_game": (255, 50, 80),    # Red light
    "quiz": (255, 220, 0),          # Gold
    "tower_stack": (100, 200, 255), # Sky blue
    "brick_breaker": (255, 150, 50),# Warm orange
    "video": (150, 100, 255),       # Electric violet

    # Other modes
    "roulette": (255, 50, 50),      # Red
    "guess_me": (100, 200, 255),    # Cyan
    "autopsy": (150, 255, 150),     # Green
    "flow_field": (100, 150, 255),  # Blue
    "glitch_mirror": (255, 50, 150),# Magenta
    "dither_art": (150, 200, 100),  # Lime
    "ascii_art": (0, 255, 100),     # Terminal green
    "particle_sculptor": (200, 150, 255),  # Lavender
    "bar_runner": (255, 180, 80),   # Amber
    "snake_classic": (120, 255, 120),
    "snake_tiny": (100, 220, 140),
    "pong": (140, 200, 255),
    "flappy": (255, 220, 80),
    "game_2048": (237, 194, 46),
    "lunar_lander": (200, 160, 80),
    "hand_snake": (120, 255, 140),
    "rocketpy": (180, 220, 255),
    "skii": (180, 200, 220),
    "ninja_fruit": (255, 200, 120),
    "rap_god": (255, 50, 200),      # Hot pink/magenta
    "zodiac": (200, 180, 255),      # Cosmic lavender
    "gesture_game": (255, 180, 100),# Warm amber
    "gallery": (100, 180, 255),     # Sky blue
}


class ManagerState(Enum):
    """Mode manager states."""

    IDLE = auto()           # Attract mode - waiting for user
    MODE_SELECT = auto()    # User selecting a mode
    MODE_ACTIVE = auto()    # A mode is running
    RESULT = auto()         # Showing result
    PRINTING = auto()       # Printing receipt
    ADMIN_MENU = auto()     # Hidden admin menu


class SelectorEffect(Enum):
    """Visual effects for mode selector background."""
    DITHER = auto()         # Bayer dithering
    SCANLINES = auto()      # CRT scanline effect
    PIXELATE = auto()       # Chunky pixels
    THERMAL = auto()        # Thermal camera look
    MATRIX = auto()         # Matrix rain style


# Map each mode to its camera effect style
MODE_EFFECTS = {
    "dither_art": SelectorEffect.DITHER,
    "glitch_mirror": SelectorEffect.PIXELATE,
    "ascii_art": SelectorEffect.SCANLINES,
    "particle_sculptor": SelectorEffect.THERMAL,
    "flow_field": SelectorEffect.MATRIX,
    "fortune": SelectorEffect.DITHER,
    "ai_prophet": SelectorEffect.MATRIX,
    "roast": SelectorEffect.THERMAL,
    "quiz": SelectorEffect.SCANLINES,
    "squid_game": SelectorEffect.PIXELATE,
    "roulette": SelectorEffect.SCANLINES,
    "guess_me": SelectorEffect.THERMAL,
    "autopsy": SelectorEffect.THERMAL,
    "zodiac": SelectorEffect.DITHER,
    "bar_runner": SelectorEffect.PIXELATE,
    "tower_stack": SelectorEffect.DITHER,
}

# Menu-specific display name overrides (keep Russian on the selector/ticker/LCD)
MODE_LABELS_RU = {
    "pong": "ПОНГ",
    "rap_god": "РЭП БОГ",
    "snake_classic": "ЗМЕЙКА",
    "snake_tiny": "МИНИ-ЗМЕЙКА",
    "flappy": "ФЛАППИ",
    "lunar_lander": "ЛЕНДЕР",
    "ninja_fruit": "НИНДЗЯ",
    "skii": "ЛЫЖИ",
    "rocketpy": "РАКЕТА",
    "hand_snake": "РУЧНАЯ ЗМЕЙКА",
    "glitch_mirror": "ГЛИТЧ",
    "dither_art": "ДИТЕР",
    "ascii_art": "АСКИ",
    "fortune": "ГАДАТЕЛЬ",
    "quiz": "КВИЗ",
    "ai_prophet": "ОРАКУЛ",
    "roast": "ROAST",
    "zodiac": "ЗОДИАК",
    "roulette": "РУЛЕТКА",
    "squid_game": "ИГРА В КАЛЬМАРА",
    "photobooth": "ФОТОБУДКА",
}

# Brief mode descriptions for ticker display (short, fun, informal)
MODE_DESCRIPTIONS_RU = {
    "fortune": "Гадаем по звездам!",
    "ai_prophet": "ИИ читает тебя как книгу",
    "photobooth": "Фоткайся на память!",
    "roast": "Робот тебя сожжет!",
    "zodiac": "Что говорят звезды?",
    "quiz": "Проверь себя!",
    "squid_game": "Выживи если сможешь",
    "roulette": "Крути колесо!",
    "tower_stack": "Строй башню!",
    "brick_breaker": "Ломай кирпичи!",
    "video": "Смотри видео",
    "rap_god": "Запиши свой трек!",
    "guess_me": "ИИ угадает кто ты",
    "autopsy": "Вскрытие личности",
    "pong": "Олдскул пинг понг",
    "snake_classic": "Ешь и расти!",
    "flappy": "Лети и не падай!",
    "gallery": "Галерея фоток",
}


@dataclass
class ModeInfo:
    """Information about a registered mode."""

    cls: Type[BaseMode]
    name: str
    display_name: str
    icon: str
    style: str
    description: str
    enabled: bool = True


class ModeManager:
    """Manages game modes, selection, and transitions.

    Handles:
    - Idle/attract mode with animations
    - Mode selection carousel
    - Mode lifecycle management
    - Result display and printing flow
    - Hidden admin menu (key combo: * # * #)

    Input Flow:
    - IDLE: Big button → MODE_SELECT
    - MODE_SELECT: Left/Right to browse, Big button to confirm
    - MODE_ACTIVE: Mode handles input
    - RESULT: Big button to print or exit
    """

    # Admin menu key sequence
    ADMIN_SEQUENCE = ['*', '#', '*', '#']

    def __init__(
        self,
        state_machine: StateMachine,
        event_bus: EventBus,
        renderer: Renderer,
        animation_engine: AnimationEngine,
        theme: str = "mystical"
    ):
        self.state_machine = state_machine
        self.event_bus = event_bus
        self.renderer = renderer
        self.animation_engine = animation_engine
        self.theme = theme

        # Manager state
        self._state = ManagerState.IDLE
        self._registered_modes: Dict[str, ModeInfo] = {}
        self._mode_order: List[str] = []
        self._selected_index: int = 0
        self._current_mode: Optional[BaseMode] = None
        self._last_result: Optional[ModeResult] = None

        # Idle animation - uses the new rotating scene system
        self._idle_animation = RotatingIdleAnimation()

        # Admin menu detection
        self._key_buffer: List[str] = []
        self._admin_mode_enabled = False

        # Timing
        self._time_in_state: float = 0.0
        self._idle_timeout: float = 30000  # Return to idle after 30s of inactivity
        self._last_input_time: float = 0.0

        # Result view control - user navigates with LEFT/RIGHT
        self._result_view_index: int = 0      # Current view (0=text, 1=caricature)
        self._result_num_views: int = 2       # Number of views available
        self._result_auto_advance: bool = True  # Auto-advance enabled
        self._result_first_default: float = 8000  # Baseline timing
        self._result_next_default: float = 6000
        self._result_first_advance_time: float = self._result_first_default
        self._result_next_advance_time: float = self._result_next_default
        self._result_last_advance: float = 0.0  # Time of last advance

        # Text pagination within result view (no scrolling!)
        self._result_text_pages: List[List[str]] = []  # Pre-paginated text
        self._result_text_page_index: int = 0          # Current text page

        # Callbacks
        self._on_mode_complete: Optional[Callable[[ModeResult], None]] = None

        # Audio engine for music
        self._audio = get_audio_engine()

        # Cross-display effects coordinator
        self._display_coordinator = DisplayCoordinator()

        # Reveal animator for dramatic result presentations
        self._reveal_animator = RevealAnimator()

        # Register event handlers
        self._setup_event_handlers()

        # Start cycling idle music (will cycle through nostalgic tracks)
        self._audio.start_idle_music()

        # Mode selector camera and effects
        self._selector_frame = None
        self._selector_effect = SelectorEffect.DITHER
        self._selector_effect_index = 0
        self._selector_effects = list(SelectorEffect)
        self._selector_effect_timer = 0.0  # Cycle effect every 3 seconds
        self._bayer_matrix = self._create_bayer_matrix(4)  # 4x4 Bayer matrix

        # Pygame-menu selector (optional)
        use_menu_env = os.getenv("ARTIFACT_USE_PYGAME_MENU", "false").lower()
        self._use_pygame_menu = use_menu_env in ("1", "true", "yes")
        self._menu_failed = False
        self._menu = None
        self._menu_surface = None
        self._menu_events: List = []
        self._menu_widgets: List = []
        self._menu_index_map: List[int] = []
        self._menu_mode_count = 0
        self._menu_render_failures = 0

        logger.info("ModeManager initialized")

    def _create_bayer_matrix(self, size: int) -> list:
        """Create a Bayer ordered dithering matrix."""
        if size == 2:
            return [[0, 2], [3, 1]]
        else:
            smaller = self._create_bayer_matrix(size // 2)
            n = size // 2
            result = [[0] * size for _ in range(size)]
            for y in range(n):
                for x in range(n):
                    val = smaller[y][x] * 4
                    result[y][x] = val
                    result[y][x + n] = val + 2
                    result[y + n][x] = val + 3
                    result[y + n][x + n] = val + 1
            return result

    def _open_selector_camera(self) -> None:
        """Ensure shared camera service is running for selector background."""
        try:
            from artifact.utils.camera_service import camera_service
            if not camera_service.is_running:
                camera_service.start()
        except Exception:
            pass

    def _close_selector_camera(self) -> None:
        """Clear selector camera frame (shared service stays running)."""
        self._selector_frame = None

    def _update_selector_camera(self) -> None:
        """Capture a frame from the shared camera service."""
        try:
            from artifact.utils.camera_service import camera_service
            if not camera_service.is_running:
                self._selector_frame = None
                return
            frame = camera_service.get_frame(timeout=0)
            if frame is not None:
                self._selector_frame = frame
        except Exception:
            self._selector_frame = None

    def _menu_label(self, mode: ModeInfo) -> str:
        """Return ASCII-safe label for pygame-menu."""
        label = mode.display_name.strip()
        if any(ord(ch) > 127 for ch in label):
            label = mode.name.replace("_", " ").upper()
        return label[:12]

    def _ensure_pygame_menu(self) -> None:
        """Build pygame-menu selector if available."""
        if not self._use_pygame_menu or self._menu_failed:
            return
        if self._menu is not None and self._menu_mode_count == len(self._mode_order):
            return
        try:
            import pygame
            import pygame_menu
        except Exception as exc:
            logger.warning(f"pygame-menu unavailable: {exc}")
            self._menu_failed = True
            return

        pygame.font.init()
        try:
            pygame.mouse.set_visible(False)
        except Exception:
            pass

        display_surface = pygame.display.get_surface()
        if display_surface is None:
            logger.warning("pygame-menu skipped: display surface not ready")
            return
        window_w, window_h = display_surface.get_size()
        if window_w < 128 or window_h < 128:
            logger.warning(f"pygame-menu skipped: window too small ({window_w}x{window_h})")
            return

        theme = pygame_menu.themes.THEME_DARK.copy()
        theme.title_font_size = 10
        theme.widget_font_size = 10
        theme.widget_margin = (0, 1)
        theme.widget_padding = 0
        theme.background_color = (12, 12, 16)
        theme.title_background_color = (24, 24, 32)

        menu = pygame_menu.Menu(
            title="SELECT",
            width=128,
            height=128,
            theme=theme,
        )

        self._menu_widgets = []
        self._menu_index_map = []
        for index, name in enumerate(self._mode_order):
            mode = self._registered_modes.get(name)
            if not mode or not mode.enabled:
                continue
            label = self._menu_label(mode)
            widget = menu.add.button(label, self._menu_start_from_menu, index)
            self._menu_widgets.append(widget)
            self._menu_index_map.append(index)

        self._menu = menu
        self._menu_surface = pygame.Surface((128, 128))
        self._menu_events = []
        self._menu_mode_count = len(self._mode_order)
        self._menu_render_failures = 0
        logger.info(f"pygame-menu selector ready: {len(self._menu_widgets)} modes")

    def _menu_start_from_menu(self, index: int) -> None:
        """Start a mode from pygame-menu selection."""
        self._selected_index = index % max(1, len(self._mode_order))
        self._start_selected_mode()

    def _queue_menu_key(self, key) -> None:
        """Queue a pygame-menu key event."""
        if not self._menu or self._menu_failed:
            return
        try:
            import pygame
        except Exception:
            return
        self._menu_events.append(pygame.event.Event(pygame.KEYDOWN, {"key": key}))

    def _update_pygame_menu(self) -> None:
        """Update pygame-menu state and sync selection."""
        if not self._menu:
            return
        events = self._menu_events
        self._menu_events = []
        try:
            self._menu.update(events)
        except Exception as exc:
            logger.debug(f"pygame-menu update error: {exc}")

        selected = self._selected_index
        try:
            widget = None
            if hasattr(self._menu, "get_selected_widget"):
                widget = self._menu.get_selected_widget()
            elif hasattr(self._menu, "get_current") and self._menu.get_current():
                current = self._menu.get_current()
                if hasattr(current, "get_selected_widget"):
                    widget = current.get_selected_widget()
            if widget is not None and widget in self._menu_widgets:
                widget_index = self._menu_widgets.index(widget)
                if widget_index < len(self._menu_index_map):
                    selected = self._menu_index_map[widget_index]
        except Exception:
            pass

        if selected != self._selected_index:
            self._selected_index = selected

    def _render_pygame_menu(self, buffer) -> bool:
        """Render pygame-menu selector to buffer."""
        if not self._menu or not self._menu_surface:
            return False
        try:
            import numpy as np
            self._menu_surface.fill((12, 12, 16))
            self._menu.draw(self._menu_surface)
            import pygame.surfarray

            menu_frame = pygame.surfarray.array3d(self._menu_surface).swapaxes(0, 1)
            # Detect blank/near-blank renders to avoid invisible menu.
            bg = np.array([12, 12, 16], dtype=np.int16)
            delta = np.abs(menu_frame.astype(np.int16) - bg)
            if np.count_nonzero(delta > 6) < 64:
                raise RuntimeError("pygame-menu render empty")
            buffer[:menu_frame.shape[0], :menu_frame.shape[1]] = menu_frame
            return True
        except Exception as exc:
            self._menu_render_failures += 1
            logger.warning(f"pygame-menu render error: {exc}")
            if self._menu_render_failures >= 3:
                self._menu_failed = True
                logger.warning("pygame-menu disabled after repeated render failures")
            return False

    def _setup_event_handlers(self) -> None:
        """Register event handlers."""
        self.event_bus.subscribe(EventType.BUTTON_PRESS, self._on_button_press)
        self.event_bus.subscribe(EventType.ARCADE_LEFT, self._on_arcade_left)
        self.event_bus.subscribe(EventType.ARCADE_RIGHT, self._on_arcade_right)
        self.event_bus.subscribe(EventType.KEYPAD_INPUT, self._on_keypad_input)
        self.event_bus.subscribe(EventType.BACK, self._on_back)
        self.event_bus.subscribe(EventType.REBOOT, self._on_reboot)

    # Mode registration
    def register_mode(self, mode_cls: Type[BaseMode], enabled: bool = True) -> None:
        """Register a mode class.

        Args:
            mode_cls: The mode class to register
            enabled: Whether mode is available for selection
        """
        display_name = MODE_LABELS_RU.get(mode_cls.name, mode_cls.display_name)
        info = ModeInfo(
            cls=mode_cls,
            name=mode_cls.name,
            display_name=display_name,
            icon=mode_cls.icon,
            style=mode_cls.style,
            description=getattr(mode_cls, "description", getattr(mode_cls, "__doc__", "") or display_name),
            enabled=enabled
        )
        self._registered_modes[mode_cls.name] = info
        if enabled:
            self._mode_order.append(mode_cls.name)

        logger.info(f"Registered mode: {mode_cls.name} (enabled={enabled})")

    def unregister_mode(self, name: str) -> None:
        """Unregister a mode."""
        if name in self._registered_modes:
            del self._registered_modes[name]
            if name in self._mode_order:
                self._mode_order.remove(name)

    def get_available_modes(self) -> List[ModeInfo]:
        """Get list of available (enabled) modes."""
        return [
            self._registered_modes[name]
            for name in self._mode_order
            if name in self._registered_modes and self._registered_modes[name].enabled
        ]

    def get_selected_mode(self) -> Optional[ModeInfo]:
        """Get currently selected mode info."""
        if not self._mode_order:
            return None
        name = self._mode_order[self._selected_index % len(self._mode_order)]
        return self._registered_modes.get(name)

    # State management
    @property
    def state(self) -> ManagerState:
        """Get current manager state."""
        return self._state

    def _change_state(self, new_state: ManagerState) -> None:
        """Transition to new state."""
        old_state = self._state
        self._state = new_state
        self._time_in_state = 0.0

        logger.debug(f"ModeManager: {old_state.name} -> {new_state.name}")

        # Initialize result view state when entering RESULT
        if new_state == ManagerState.RESULT:
            # AUTO-PRINT enabled: No confirmation needed, start at view 0 (text)
            # Views: 0=text, 1=caricature (if available)
            self._result_view_index = 0
            self._result_text_page_index = 0
            self._result_text_pages = []
            self._result_auto_advance = True
            self._result_last_advance = 0.0
            self._result_first_advance_time = self._result_first_default
            self._result_next_advance_time = self._result_next_default
            # Determine number of views: 0=text, 1=caricature (optional), 2=QR (optional)
            if self._last_result:
                has_caricature = (self._last_result.print_data and
                                  self._last_result.print_data.get("caricature"))
                has_qr = (self._last_result.print_data and
                          self._last_result.print_data.get("qr_image") is not None)
                # Views: text + caricature (if any) + QR (if any)
                self._result_num_views = 1 + (1 if has_caricature else 0) + (1 if has_qr else 0)
                if self._last_result.display_text:
                    try:
                        from artifact.graphics.fonts import load_font
                        from artifact.graphics.text_utils import smart_wrap_text

                        font = load_font("cyrillic")
                        lines = smart_wrap_text(self._last_result.display_text, 120, font, scale=1)

                        # Pre-paginate text into pages (13 lines per page, fullscreen)
                        lines_per_page = 13
                        self._result_text_pages = []
                        for i in range(0, len(lines), lines_per_page):
                            page_lines = lines[i:i + lines_per_page]
                            self._result_text_pages.append(page_lines)

                        # Ensure at least one page
                        if not self._result_text_pages:
                            self._result_text_pages = [["..."]]

                        line_count = max(1, len(lines))
                        # Add generous reading time for longer fortunes
                        base_ms = 9000
                        per_line_ms = 1200
                        self._result_first_advance_time = max(
                            base_ms,
                            base_ms + max(0, line_count - 4) * per_line_ms
                        )
                        self._result_next_advance_time = max(
                            7000,
                            5000 + max(0, line_count - 4) * 800
                        )
                    except Exception:
                        # Fall back to defaults if anything goes wrong
                        self._result_first_advance_time = self._result_first_default
                        self._result_next_advance_time = self._result_next_default
                        self._result_text_pages = [["..."]]
            else:
                self._result_num_views = 2
                self._result_text_pages = [["..."]]

        # Handle music transitions and cross-display effects
        if new_state == ManagerState.IDLE:
            self._audio.start_idle_music()  # Cycling nostalgic tracks
            self._display_coordinator.clear_effect()  # Clear effects on idle
            self._close_selector_camera()  # Close selector camera if open
        elif new_state == ManagerState.MODE_SELECT:
            self._audio.stop_idle_music()  # Stop cycling idle music
            self._audio.play_music("menu", fade_in_ms=300)
            self._audio.play_ui_confirm()  # Confirmation sound
            self._display_coordinator.set_effect(CrossDisplayEffect.SPARKLE_CASCADE, 0.5)
            # Open camera for selector background effects
            self._open_selector_camera()
            self._selector_effect_timer = 0.0
        elif new_state == ManagerState.RESULT:
            # Result screen - play success music with reveal animation
            self._audio.play_music("idle", fade_in_ms=500)
            self._audio.play_success()
            self._display_coordinator.set_effect(CrossDisplayEffect.FALLING_PARTICLES, 0.8)
            # Start dramatic reveal animation - choose style based on mode
            reveal_style = RevealStyle.CELEBRATION  # Default celebration
            if self._current_mode:
                mode_name = self._current_mode.name
                # Choose reveal style based on mode theme
                if mode_name in ("fortune", "zodiac", "ai_prophet"):
                    reveal_style = RevealStyle.MYSTICAL
                elif mode_name == "quiz":
                    reveal_style = RevealStyle.CONFETTI
                elif mode_name == "roast":
                    reveal_style = RevealStyle.LIGHT_BURST
                elif mode_name == "roulette":
                    reveal_style = RevealStyle.CELEBRATION
                elif mode_name in ("autopsy", "guess_me"):
                    reveal_style = RevealStyle.SCANLINE
            self._reveal_animator.start_reveal(reveal_style, duration=1200.0)
        elif new_state == ManagerState.PRINTING:
            self._audio.stop_music(fade_out_ms=200)
            self._audio.play_print()
            self._display_coordinator.set_effect(CrossDisplayEffect.DATA_STREAM, 0.6)

        # State machine sync
        state_map = {
            ManagerState.IDLE: State.IDLE,
            ManagerState.MODE_SELECT: State.MODE_SELECT,
            ManagerState.MODE_ACTIVE: State.MODE_ACTIVE,
            ManagerState.RESULT: State.RESULT,
            ManagerState.PRINTING: State.PRINTING,
        }
        if new_state in state_map:
            self.state_machine.transition(state_map[new_state])

    # Event handlers
    def _on_button_press(self, event: Event) -> None:
        """Handle main button press."""
        self._last_input_time = self._time_in_state
        self._audio.play_ui_click()

        if self._state == ManagerState.IDLE:
            # Start mode selection
            self._enter_mode_select()

        elif self._state == ManagerState.MODE_SELECT:
            # Confirm selection, start mode
            if self._menu and not self._menu_failed:
                try:
                    import pygame
                    self._queue_menu_key(pygame.K_RETURN)
                except Exception:
                    self._start_selected_mode()
            else:
                self._start_selected_mode()

        elif self._state == ManagerState.MODE_ACTIVE:
            # Pass to active mode
            if self._current_mode:
                self._current_mode.handle_input(event)

        elif self._state == ManagerState.RESULT:
            # Navigate through views: text pages → image → QR → exit
            self._result_auto_advance = False  # User took control, disable auto
            self._result_last_advance = self._time_in_state

            if self._result_view_index == 0 and len(self._result_text_pages) > 1:
                # On text view with multiple pages - navigate pages first
                if self._result_text_page_index < len(self._result_text_pages) - 1:
                    self._result_text_page_index += 1
                    self._audio.play_ui_move()
                    return  # Stay in result view
                else:
                    # At last text page - go to next view if available
                    if self._result_num_views > 1:
                        self._result_view_index = 1
                        self._audio.play_ui_move()
                        return  # Stay in result view
            elif self._result_view_index < self._result_num_views - 1:
                # Not on last view - advance to next view
                self._result_view_index += 1
                self._audio.play_ui_move()
                return  # Stay in result view

            # On last view (or only view) - exit
            self._return_to_idle()

        elif self._state == ManagerState.PRINTING:
            # Skip/cancel printing
            self._return_to_idle()

    def _on_arcade_left(self, event: Event) -> None:
        """Handle left arcade button."""
        self._last_input_time = self._time_in_state

        if self._state == ManagerState.IDLE:
            # Switch to previous idle scene
            self._idle_animation.prev_scene()
        elif self._state == ManagerState.MODE_SELECT:
            if self._menu and not self._menu_failed:
                try:
                    import pygame
                    self._queue_menu_key(pygame.K_UP)
                    self._audio.play_ui_move()
                except Exception:
                    self._select_previous_mode()
            else:
                self._select_previous_mode()
        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.handle_input(event)
        elif self._state == ManagerState.RESULT:
            # Left navigation with text page support
            self._result_auto_advance = False  # User took control, disable auto
            self._result_last_advance = self._time_in_state

            if self._result_view_index == 0 and len(self._result_text_pages) > 1:
                # On text view with multiple pages - navigate pages first
                if self._result_text_page_index > 0:
                    self._result_text_page_index -= 1
                    self._audio.play_ui_move()
                else:
                    # At first text page - wrap to last view (caricature if available)
                    self._result_view_index = (self._result_view_index - 1) % self._result_num_views
                    self._audio.play_ui_move()
            else:
                # On other views - switch views
                self._result_view_index = (self._result_view_index - 1) % self._result_num_views
                # Reset to last text page when entering text view from right
                if self._result_view_index == 0 and len(self._result_text_pages) > 1:
                    self._result_text_page_index = len(self._result_text_pages) - 1
                self._audio.play_ui_move()

    def _on_arcade_right(self, event: Event) -> None:
        """Handle right arcade button."""
        self._last_input_time = self._time_in_state

        if self._state == ManagerState.IDLE:
            # Switch to next idle scene
            self._idle_animation.next_scene()
        elif self._state == ManagerState.MODE_SELECT:
            if self._menu and not self._menu_failed:
                try:
                    import pygame
                    self._queue_menu_key(pygame.K_DOWN)
                    self._audio.play_ui_move()
                except Exception:
                    self._select_next_mode()
            else:
                self._select_next_mode()
        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.handle_input(event)
        elif self._state == ManagerState.RESULT:
            # Right navigation with text page support
            self._result_auto_advance = False  # User took control, disable auto
            self._result_last_advance = self._time_in_state

            if self._result_view_index == 0 and len(self._result_text_pages) > 1:
                # On text view with multiple pages - navigate pages first
                if self._result_text_page_index < len(self._result_text_pages) - 1:
                    self._result_text_page_index += 1
                    self._audio.play_ui_move()
                else:
                    # At last text page - go to next view (caricature if available)
                    self._result_view_index = (self._result_view_index + 1) % self._result_num_views
                    self._audio.play_ui_move()
            else:
                # On other views - switch views
                self._result_view_index = (self._result_view_index + 1) % self._result_num_views
                # Reset to first text page when entering text view from left
                if self._result_view_index == 0:
                    self._result_text_page_index = 0
                self._audio.play_ui_move()

    def _on_keypad_input(self, event: Event) -> None:
        """Handle keypad input."""
        self._last_input_time = self._time_in_state
        key = event.data.get("key", "")

        # Check for admin sequence
        self._key_buffer.append(key)
        if len(self._key_buffer) > len(self.ADMIN_SEQUENCE):
            self._key_buffer.pop(0)

        if self._key_buffer == self.ADMIN_SEQUENCE:
            self._toggle_admin_menu()
            self._key_buffer.clear()
            return

        if self._state == ManagerState.MODE_SELECT and self._menu and not self._menu_failed:
            try:
                import pygame
                if key in ("4", "8"):
                    self._queue_menu_key(pygame.K_UP)
                    self._audio.play_ui_move()
                    return
                if key in ("6", "2"):
                    self._queue_menu_key(pygame.K_DOWN)
                    self._audio.play_ui_move()
                    return
                if key in ("5", "0"):
                    self._queue_menu_key(pygame.K_RETURN)
                    self._audio.play_ui_confirm()
                    return
            except Exception:
                pass

        # During idle, allow GIF navigation with keypad 2/8
        if self._state == ManagerState.IDLE:
            if self._idle_animation.on_input(key):
                self._audio.play_ui_move()
                return

        # Pass to active mode
        if self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.handle_input(event)

    def _on_back(self, event: Event) -> None:
        """Handle back/cancel button - go back one step."""
        self._last_input_time = self._time_in_state
        self._audio.play_ui_back()

        if self._state == ManagerState.MODE_SELECT:
            # Go back to idle from mode select
            self._return_to_idle()

        elif self._state == ManagerState.MODE_ACTIVE:
            # Cancel current mode and return to mode select
            if self._current_mode:
                self._current_mode.exit()
                self._current_mode = None
            self._change_state(ManagerState.MODE_SELECT)

        elif self._state == ManagerState.RESULT:
            # Go back to idle
            self._return_to_idle()

        elif self._state == ManagerState.PRINTING:
            # Cancel printing and go to idle
            self._return_to_idle()

        elif self._state == ManagerState.ADMIN_MENU:
            # Exit admin menu
            self._return_to_idle()

        logger.debug(f"Back pressed, now in state: {self._state.name}")

    def _on_reboot(self, event: Event) -> None:
        """Handle reboot/restart - return to idle and reset everything."""
        logger.info("System reboot requested")

        # Clean up current mode if any
        if self._current_mode:
            self._current_mode.exit()
            self._current_mode = None

        # Reset state
        self._last_result = None
        self._selected_index = 0
        self._key_buffer.clear()
        self._time_in_state = 0.0
        self._last_input_time = 0.0

        # Return to idle
        self._change_state(ManagerState.IDLE)
        self._idle_animation.reset()

        logger.info("System rebooted - returned to idle")

    # Mode selection
    def _enter_mode_select(self) -> None:
        """Enter mode selection state."""
        if not self._mode_order:
            logger.warning("No modes available!")
            return

        self._change_state(ManagerState.MODE_SELECT)
        self._selected_index = 0
        if self._use_pygame_menu:
            self._ensure_pygame_menu()

    def _select_next_mode(self) -> None:
        """Select next mode in carousel."""
        if self._mode_order:
            self._selected_index = (self._selected_index + 1) % len(self._mode_order)
            self._audio.play_ui_move()

    def _select_previous_mode(self) -> None:
        """Select previous mode in carousel."""
        if self._mode_order:
            self._selected_index = (self._selected_index - 1) % len(self._mode_order)
            self._audio.play_ui_move()

    def _start_selected_mode(self) -> None:
        """Start the currently selected mode."""
        mode_info = self.get_selected_mode()
        if not mode_info:
            return

        # Close selector camera before starting mode
        self._close_selector_camera()

        # Create mode context
        context = ModeContext(
            state_machine=self.state_machine,
            event_bus=self.event_bus,
            renderer=self.renderer,
            animation_engine=self.animation_engine,
            theme=self.theme
        )

        # Instantiate and start mode
        self._current_mode = mode_info.cls(context)
        self._current_mode.set_on_complete(self._on_mode_complete_internal)

        # Play mode-specific music
        self._audio.play_music(mode_info.name, fade_in_ms=500)
        self._audio.play_transition()

        self._change_state(ManagerState.MODE_ACTIVE)
        self._current_mode.enter()

    def _on_mode_complete_internal(self, result: ModeResult) -> None:
        """Handle mode completion."""
        self._last_result = result
        self._change_state(ManagerState.RESULT)

        # AUTO-PRINT: Always print immediately without confirmation
        if result.should_print:
            self._start_printing()

        if self._on_mode_complete:
            self._on_mode_complete(result)

    # Printing
    def _start_printing(self) -> None:
        """Start printing process."""
        # AUTO-PRINT: emit print event without switching to a printing screen
        if self._last_result:
            print_data = {
                "type": self._last_result.mode_name,
                "prediction": self._last_result.display_text,
                "display_text": self._last_result.display_text,
                **(self._last_result.print_data or {})
            }
            self.event_bus.emit(Event(
                EventType.PRINT_START,
                data=print_data,
                source="mode_manager"
            ))

        logger.info("Printing started...")

    # Navigation
    def _return_to_idle(self) -> None:
        """Return to idle/attract state."""
        if self._current_mode:
            self._current_mode.exit()
            self._current_mode = None

        self._last_result = None
        self._change_state(ManagerState.IDLE)
        self._idle_animation.reset()

    def _toggle_admin_menu(self) -> None:
        """Toggle admin menu."""
        if self._state == ManagerState.ADMIN_MENU:
            self._return_to_idle()
        else:
            self._change_state(ManagerState.ADMIN_MENU)
            logger.info("Admin menu activated")

    # Update loop
    def update(self, delta_ms: float) -> None:
        """Update manager state."""
        self._time_in_state += delta_ms

        # Update cross-display effects coordinator
        self._display_coordinator.update(delta_ms)

        # Handle state-specific updates
        if self._state == ManagerState.IDLE:
            self._idle_animation.update(delta_ms)
            # Update cycling idle music with motion detection
            # Get motion from camera to pause/resume music after inactivity
            try:
                from artifact.utils.camera_service import camera_service
                _, confidence = camera_service.get_motion_position()
                motion_detected = confidence > 0.1
            except Exception:
                motion_detected = True  # Assume motion if camera unavailable
            self._audio.update_idle_music(delta_ms, motion_detected)

        elif self._state == ManagerState.MODE_SELECT:
            if self._use_pygame_menu:
                self._ensure_pygame_menu()
                if self._menu and not self._menu_failed:
                    self._update_pygame_menu()
            if not self._menu or self._menu_failed:
                # Update camera
                self._update_selector_camera()

                # Set effect based on currently selected mode
                mode = self.get_selected_mode()
                if mode:
                    self._selector_effect = MODE_EFFECTS.get(mode.name, SelectorEffect.DITHER)

            # Timeout back to idle
            if self._time_in_state - self._last_input_time > self._idle_timeout:
                self._return_to_idle()

        elif self._state == ManagerState.MODE_ACTIVE:
            if self._current_mode:
                self._current_mode.update(delta_ms)

        elif self._state == ManagerState.RESULT:
            # Update reveal animation
            if self._reveal_animator.is_active:
                self._reveal_animator.update(delta_ms)

            # Handle auto-advance through result views (only after reveal completes)
            if self._result_auto_advance and self._reveal_animator.is_complete:
                time_since_advance = self._time_in_state - self._result_last_advance
                # First advance takes longer to let user read
                advance_time = (self._result_first_advance_time
                                if self._result_last_advance == 0.0
                                else self._result_next_advance_time)
                if time_since_advance >= advance_time:
                    self._result_view_index = (self._result_view_index + 1) % self._result_num_views
                    self._result_last_advance = self._time_in_state

            # Timeout back to idle after extended inactivity (60 seconds)
            if self._time_in_state - self._last_input_time > 60000:
                self._return_to_idle()

        elif self._state == ManagerState.PRINTING:
            # Simulate print completion after 10 seconds
            if self._time_in_state > 10000:
                self._return_to_idle()

    # Rendering
    def render_main(self, buffer) -> None:
        """Render main display."""
        if self._state == ManagerState.IDLE:
            self._idle_animation.render_main(buffer)
            # Note: Start prompt is now integrated into idle_scenes.py

        elif self._state == ManagerState.MODE_SELECT:
            if self._menu and not self._menu_failed:
                if not self._render_pygame_menu(buffer):
                    self._render_mode_select(buffer)
            else:
                self._render_mode_select(buffer)

        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.render_main(buffer)

        elif self._state == ManagerState.RESULT:
            self._render_result(buffer)
            # Render reveal animation overlay
            if self._reveal_animator.is_active:
                self._reveal_animator.render_overlay(buffer)

        elif self._state == ManagerState.PRINTING:
            self._render_printing(buffer)

        elif self._state == ManagerState.ADMIN_MENU:
            self._render_admin_menu(buffer)

        # Apply cross-display effects overlay
        self._display_coordinator.render_main_overlay(buffer)

    def render_ticker(self, buffer) -> None:
        """Render ticker display."""
        if self._state == ManagerState.IDLE:
            self._idle_animation.render_ticker(buffer)

        elif self._state == ManagerState.MODE_SELECT:
            self._render_mode_select_ticker(buffer)

        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.render_ticker(buffer)

        elif self._state in (ManagerState.RESULT, ManagerState.PRINTING):
            self._render_result_ticker(buffer)

        # Apply cross-display effects overlay
        self._display_coordinator.render_ticker_overlay(buffer)

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self._state == ManagerState.IDLE:
            return self._idle_animation.get_lcd_text()

        elif self._state == ManagerState.MODE_SELECT:
            mode = self.get_selected_mode()
            if mode:
                # Fun LCD with arrows for navigation
                return f"◄ {mode.display_name[:10]} ►".center(16)[:16]
            return "◄► РЕЖИМ ◄►".center(16)

        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            return self._current_mode.get_lcd_text()

        elif self._state == ManagerState.RESULT:
            # Show navigation hint (auto-print already started)
            return "◄► ЛИСТАТЬ".center(16)[:16]

        elif self._state == ManagerState.PRINTING:
            # Fun animated printing
            dots = "●" * (int(self._time_in_state / 300) % 4)
            return f" ПЕЧАТЬ{dots} ".center(16)[:16]

        elif self._state == ManagerState.ADMIN_MENU:
            return "★ ADMIN ★".center(16)

        return "★ VNVNC ★".center(16)

    def _render_start_prompt(self, buffer) -> None:
        """Render 'press start' prompt with arrow."""
        from artifact.graphics.text_utils import draw_centered_text, MAIN_SAFE_BOTTOM_S2
        from artifact.graphics.primitives import draw_rect

        # Blinking "НАЖМИ" at bottom - positioned within safe zone for scale=2
        if int(self._time_in_state / 500) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ", 92, (255, 200, 0), scale=2)

        # Arrow pointing down (to button) - wide at top, point at bottom
        # Position adjusted to stay within safe zone
        base_y = MAIN_SAFE_BOTTOM_S2 + 2  # 110, within safe area
        bounce = int((self._time_in_state / 200) % 3)  # Reduced bounce range
        cx = 64
        # Down arrow: starts wide, ends in point
        for i in range(4):  # Reduced height to fit
            width = (4 - i) * 2 - 1  # 7, 5, 3, 1
            x_start = cx - width // 2
            y_pos = min(base_y + bounce + i, 123)  # Clamp to avoid overflow
            draw_rect(buffer, x_start, y_pos, width, 1, (255, 100, 100))

    def _render_mode_select(self, buffer) -> None:
        """Render beautiful mode selection with FULL SCREEN live camera effect."""
        import numpy as np
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import fill, draw_rect

        t = self._time_in_state / 1000

        # === STEP 1: FULL SCREEN CAMERA EFFECT BACKGROUND ===
        # The camera effect fills the ENTIRE 128x128 display
        if self._selector_frame is not None:
            self._render_camera_effect_background(buffer, t)
        else:
            # Fallback animated gradient if no camera
            self._render_fallback_gradient(buffer, t)

        mode = self.get_selected_mode()
        if not mode:
            draw_centered_text(buffer, "НЕТ РЕЖИМОВ", 60, (255, 100, 100), scale=1)
            return

        # Get mode color with pulsing effect
        mode_color = MODE_COLORS.get(mode.name, (255, 200, 0))
        pulse = 0.7 + 0.3 * math.sin(t * 4)
        glow_color = tuple(int(c * pulse) for c in mode_color)

        # === STEP 2: SEMI-TRANSPARENT CENTER PANEL FOR TEXT ===
        # Darken center area slightly for text readability - VECTORIZED
        import numpy as np
        panel_y1, panel_y2 = 36, 96
        panel_x1, panel_x2 = 4, 124  # Wider panel to fit long names like ФОТОБУДКА

        # Create distance masks for rounded corners
        y_coords = np.arange(panel_y1, panel_y2)[:, np.newaxis]
        x_coords = np.arange(panel_x1, panel_x2)[np.newaxis, :]
        dist_x = np.abs(x_coords - 64) / 56  # Adjusted for wider panel
        dist_y = np.abs(y_coords - 65) / 25
        inside_mask = (dist_x <= 1) & (dist_y <= 1)

        # Apply darkening where inside mask is True
        panel_slice = buffer[panel_y1:panel_y2, panel_x1:panel_x2]
        darkened = (panel_slice * 0.4).astype(np.uint8)
        panel_slice[:] = np.where(inside_mask[:, :, np.newaxis], darkened, panel_slice)

        # === STEP 3: NAVIGATION ARROWS (behind text) ===
        font = load_font("cyrillic")
        if len(self._mode_order) > 1:
            bounce = int(math.sin(t * 6) * 3)
            arrow_y = 55

            # Left arrow with outline
            for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw_text_bitmap(buffer, "<", 4 - bounce + ox, arrow_y + oy, (0, 0, 0), font, scale=2)
            draw_text_bitmap(buffer, "<", 4 - bounce, arrow_y, (255, 255, 255), font, scale=2)

            # Right arrow with outline
            for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw_text_bitmap(buffer, ">", 112 + bounce + ox, arrow_y + oy, (0, 0, 0), font, scale=2)
            draw_text_bitmap(buffer, ">", 112 + bounce, arrow_y, (255, 255, 255), font, scale=2)

        # === STEP 4: MODE NAME - FIT, WRAP, CENTER ===
        from artifact.graphics.text_utils import smart_wrap_text, CHAR_HEIGHT

        label = (mode.display_name or mode.name).strip().upper()
        font = load_font("cyrillic")
        max_width = 116  # Allow up to 116px for text (fits 9+ Cyrillic chars at scale 2)
        max_height = panel_y2 - panel_y1 - 6

        def layout_lines(scale: int, max_lines: int):
            lines = smart_wrap_text(label, max_width, font, scale)
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                last = lines[-1].rstrip()
                while last and font.measure_text(last + "...")[0] * scale > max_width:
                    last = last[:-1]
                lines[-1] = (last + "...") if last else "..."
            line_height = CHAR_HEIGHT * scale + 2
            total_height = len(lines) * line_height
            return lines, line_height, total_height

        scale = 2
        lines, line_height, total_height = layout_lines(scale, 2)
        if total_height > max_height:
            scale = 1
            lines, line_height, total_height = layout_lines(scale, 3)

        text_y = panel_y1 + (panel_y2 - panel_y1 - total_height) // 2
        for line in lines:
            text_w, _ = font.measure_text(line)
            text_x = 64 - (text_w * scale) // 2
            for ox, oy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                draw_text_bitmap(buffer, line, text_x + ox, text_y + oy, (0, 0, 0), font, scale)
            draw_text_bitmap(buffer, line, text_x, text_y, glow_color, font, scale)
            text_y += line_height

        # === STEP 5: PROGRESS DOTS (no counter!) ===
        num_modes = len(self._mode_order)
        if num_modes > 1:
            # Calculate dot layout
            max_dots_width = 100
            dot_spacing = min(8, max_dots_width // max(1, num_modes - 1))
            total_width = (num_modes - 1) * dot_spacing
            start_x = 64 - total_width // 2
            dot_y = 100

            for i in range(num_modes):
                x = start_x + i * dot_spacing
                if i == self._selected_index:
                    # Current mode - larger bright dot
                    draw_rect(buffer, x - 2, dot_y - 2, 5, 5, mode_color)
                    # Glow effect
                    for gx in range(-1, 2):
                        for gy in range(-1, 2):
                            if 0 <= x + gx - 3 < 128 and 0 <= dot_y + gy - 3 < 128:
                                buffer[dot_y + gy - 3, x + gx - 3] = [
                                    min(255, int(buffer[dot_y + gy - 3, x + gx - 3, 0]) + 30),
                                    min(255, int(buffer[dot_y + gy - 3, x + gx - 3, 1]) + 30),
                                    min(255, int(buffer[dot_y + gy - 3, x + gx - 3, 2]) + 30)
                                ]
                else:
                    # Other modes - small dim dot
                    draw_rect(buffer, x - 1, dot_y - 1, 3, 3, (80, 80, 100))

        # === STEP 6: BOTTOM PROMPT ===
        prompt_y = 115
        prompt_color = (100, 200, 100) if int(t * 2) % 2 == 0 else (150, 255, 150)
        # Black outline
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "▼НАЖМИ СТАРТ▼", prompt_y + oy, (0, 0, 0), scale=1)
        draw_centered_text(buffer, "▼НАЖМИ СТАРТ▼", prompt_y, prompt_color, scale=1)

    def _render_camera_effect_background(self, buffer, t: float) -> None:
        """Apply mode-colored tint over camera frame - smooth, not pixelated."""
        import numpy as np

        frame = self._selector_frame
        if frame is None:
            return

        # Get current mode's unique color
        mode = self.get_selected_mode()
        mode_color = MODE_COLORS.get(mode.name, (255, 200, 0)) if mode else (255, 200, 0)

        # Mirror horizontally for selfie view
        frame = np.fliplr(frame)

        # Resize frame to 128x128
        if frame.shape[0] != 128 or frame.shape[1] != 128:
            try:
                import cv2
                frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_LINEAR)
            except ImportError:
                old_h, old_w = frame.shape[:2]
                y_indices = (np.arange(128) * old_h // 128).clip(0, old_h - 1)
                x_indices = (np.arange(128) * old_w // 128).clip(0, old_w - 1)
                frame = frame[y_indices[:, np.newaxis], x_indices]

        # Convert to grayscale for silhouette
        gray = np.mean(frame, axis=2)

        # Apply smooth color tint based on mode color
        # Bright areas get the mode color, dark areas stay dark
        h, w = 128, 128
        r, g, b = mode_color

        # Normalize brightness
        brightness = gray / 255.0

        # Smooth gradient - mode color for bright areas
        pulse = 0.85 + 0.15 * math.sin(t * 2)
        tinted_r = (brightness * r * pulse).astype(np.uint8)
        tinted_g = (brightness * g * pulse).astype(np.uint8)
        tinted_b = (brightness * b * pulse).astype(np.uint8)

        # Dark background tint (complement of mode color, very dark)
        bg_r = int(r * 0.1)
        bg_g = int(g * 0.1)
        bg_b = int(b * 0.1)

        # Blend: dark areas get dark tint, bright areas get mode color
        threshold = 0.3
        blend = np.clip((brightness - threshold) / (1.0 - threshold), 0, 1)

        buffer[:h, :w, 0] = (bg_r * (1 - blend) + tinted_r * blend).astype(np.uint8)
        buffer[:h, :w, 1] = (bg_g * (1 - blend) + tinted_g * blend).astype(np.uint8)
        buffer[:h, :w, 2] = (bg_b * (1 - blend) + tinted_b * blend).astype(np.uint8)

    def _apply_dither_effect(self, buffer, frame, t: float) -> None:
        """Apply Bayer ordered dithering to camera frame - VECTORIZED."""
        import numpy as np

        h, w = frame.shape[:2]
        bayer_size = len(self._bayer_matrix)
        bayer_max = bayer_size * bayer_size

        # Convert to grayscale using vectorized mean
        gray = np.mean(frame, axis=2).astype(np.float32)

        # Create tiled Bayer matrix for entire image
        bayer = np.array(self._bayer_matrix, dtype=np.float32)
        tiles_y, tiles_x = (h + bayer_size - 1) // bayer_size, (w + bayer_size - 1) // bayer_size
        bayer_tiled = np.tile(bayer, (tiles_y, tiles_x))[:h, :w]

        # Threshold with pulsing effect
        pulse = 0.85 + 0.15 * math.sin(t * 2)
        threshold = (bayer_tiled / bayer_max) * 255 * pulse

        # Create output colors using boolean mask
        bright_mask = gray > threshold

        # Bright pixels - cyan/purple gradient (vectorized)
        x_coords = np.arange(w)[np.newaxis, :] / w
        y_coords = np.arange(h)[:, np.newaxis] / 20
        r_bright = np.clip(140 + 100 * x_coords, 0, 255).astype(np.uint8)
        g_bright = np.clip(220 + 35 * np.sin(t + y_coords), 0, 255).astype(np.uint8)
        b_bright = np.full((h, w), 255, dtype=np.uint8)

        # Apply using boolean indexing
        buffer[:h, :w, 0] = np.where(bright_mask, r_bright, 20)
        buffer[:h, :w, 1] = np.where(bright_mask, g_bright, 15)
        buffer[:h, :w, 2] = np.where(bright_mask, b_bright, 50)

    def _apply_scanline_effect(self, buffer, frame, t: float) -> None:
        """Apply CRT scanline effect to camera frame - VECTORIZED."""
        import numpy as np

        h, w = frame.shape[:2]

        # Create scanline intensity mask (even rows brighter)
        scanline_mask = np.zeros((h, 1), dtype=np.float32)
        scanline_mask[0::2] = 0.9  # Even rows
        scanline_mask[1::2] = 0.5  # Odd rows

        # Wave distortion - compute wave offset per row
        y_coords = np.arange(h)
        wave_offsets = (np.sin(y_coords / 10 + t * 5) * 2).astype(np.int32)

        # Apply wave distortion using roll per row (simplified - skip for perf)
        # Instead, just use the frame directly with scanlines
        result = frame.astype(np.float32)

        # Apply scanline intensity with color boost
        result[:, :, 0] *= scanline_mask * 1.1  # R
        result[:, :, 1] *= scanline_mask * 1.3  # G (CRT green boost)
        result[:, :, 2] *= scanline_mask * 1.0  # B

        # Clip and copy to buffer
        np.clip(result, 0, 255, out=result)
        buffer[:h, :w] = result.astype(np.uint8)

        # Phosphor glow - vectorized bloom effect
        bright_mask = buffer[1:-1, :, 1] > 100
        glow = np.zeros_like(buffer[:, :, 1])
        glow[:-2, :] += np.where(bright_mask, 15, 0).astype(np.uint8)
        glow[2:, :] += np.where(bright_mask, 15, 0).astype(np.uint8)
        buffer[:, :, 1] = np.clip(buffer[:, :, 1].astype(np.int16) + glow, 0, 255).astype(np.uint8)

    def _apply_pixelate_effect(self, buffer, frame, t: float) -> None:
        """Apply chunky pixel effect to camera frame - VECTORIZED."""
        import numpy as np

        h, w = frame.shape[:2]
        block_size = 8  # Chunky 8x8 pixels

        # Reshape to blocks and compute mean (vectorized)
        blocks_h, blocks_w = h // block_size, w // block_size
        cropped = frame[:blocks_h * block_size, :blocks_w * block_size]

        # Reshape to (blocks_h, block_size, blocks_w, block_size, 3)
        reshaped = cropped.reshape(blocks_h, block_size, blocks_w, block_size, 3)
        # Mean over block dimensions
        block_means = reshaped.mean(axis=(1, 3)).astype(np.uint8)

        # Quantize to retro palette
        quantized = (block_means // 64) * 64 + 32

        # Expand back to full size using repeat
        expanded = np.repeat(np.repeat(quantized, block_size, axis=0), block_size, axis=1)

        # Create grid line mask
        y_grid = np.arange(blocks_h * block_size) % block_size == 0
        x_grid = np.arange(blocks_w * block_size) % block_size == 0
        grid_mask = y_grid[:, np.newaxis] | x_grid[np.newaxis, :]

        # Apply grid darkening
        result = expanded.copy()
        result[grid_mask] = result[grid_mask] // 2

        # Copy to buffer
        buffer[:blocks_h * block_size, :blocks_w * block_size] = result

    def _apply_thermal_effect(self, buffer, frame, t: float) -> None:
        """Apply thermal camera style effect - VECTORIZED."""
        import numpy as np

        h, w = frame.shape[:2]

        # Convert to grayscale (heat map based on brightness)
        heat = np.mean(frame, axis=2) / 255.0

        # Initialize output channels
        r = np.zeros((h, w), dtype=np.float32)
        g = np.zeros((h, w), dtype=np.float32)
        b = np.zeros((h, w), dtype=np.float32)

        # Thermal color mapping using masks (vectorized)
        # Zone 1: heat < 0.2 -> black to blue
        mask1 = heat < 0.2
        b[mask1] = heat[mask1] * 5 * 150

        # Zone 2: 0.2 <= heat < 0.4 -> blue to purple
        mask2 = (heat >= 0.2) & (heat < 0.4)
        t_heat2 = (heat[mask2] - 0.2) / 0.2
        r[mask2] = t_heat2 * 100
        b[mask2] = 150

        # Zone 3: 0.4 <= heat < 0.6 -> purple to red
        mask3 = (heat >= 0.4) & (heat < 0.6)
        t_heat3 = (heat[mask3] - 0.4) / 0.2
        r[mask3] = 100 + t_heat3 * 155
        b[mask3] = (1 - t_heat3) * 150

        # Zone 4: 0.6 <= heat < 0.8 -> red to orange/yellow
        mask4 = (heat >= 0.6) & (heat < 0.8)
        t_heat4 = (heat[mask4] - 0.6) / 0.2
        r[mask4] = 255
        g[mask4] = t_heat4 * 200

        # Zone 5: heat >= 0.8 -> yellow to white
        mask5 = heat >= 0.8
        t_heat5 = (heat[mask5] - 0.8) / 0.2
        r[mask5] = 255
        g[mask5] = 200 + t_heat5 * 55
        b[mask5] = t_heat5 * 200

        # Combine and clip
        buffer[:h, :w, 0] = np.clip(r, 0, 255).astype(np.uint8)
        buffer[:h, :w, 1] = np.clip(g, 0, 255).astype(np.uint8)
        buffer[:h, :w, 2] = np.clip(b, 0, 255).astype(np.uint8)

    def _apply_matrix_effect(self, buffer, frame, t: float) -> None:
        """Apply Matrix-style green rain effect over camera - VECTORIZED."""
        import numpy as np

        h, w = frame.shape[:2]

        # Convert to grayscale
        brightness = np.mean(frame, axis=2) / 255.0

        # Create coordinate grids for rain effect
        y_coords = np.arange(h)[:, np.newaxis]
        x_coords = np.arange(w)[np.newaxis, :]

        # Matrix rain columns - vectorized
        rain_phase = (y_coords / 8 + x_coords * 0.3 + t * 3) % 10
        rain_intensity = np.where(rain_phase < 5, np.maximum(0, 1 - rain_phase / 5), 0)

        # Combine camera brightness with rain
        g = np.clip(brightness * 150 + rain_intensity * 100, 0, 255).astype(np.uint8)
        r = np.clip(brightness * 20 + rain_intensity * 10, 0, 255).astype(np.uint8)
        b = np.clip(brightness * 30, 0, 255).astype(np.uint8)

        buffer[:h, :w, 0] = r
        buffer[:h, :w, 1] = g
        buffer[:h, :w, 2] = b

    def _render_fallback_gradient(self, buffer, t: float) -> None:
        """Render animated gradient when no camera available - uses mode color."""
        import numpy as np

        # Get current mode's unique color
        mode = self.get_selected_mode()
        mode_color = MODE_COLORS.get(mode.name, (255, 200, 0)) if mode else (255, 200, 0)
        mr, mg, mb = mode_color

        # Create coordinate arrays
        y_coords = np.arange(128)[:, np.newaxis]
        x_coords = np.arange(128)[np.newaxis, :]

        # Animated wave pattern
        wave = np.sin(y_coords / 15 + t * 2) * 0.15
        pulse = 0.7 + 0.3 * math.sin(t * 1.5)

        # Gradient from dark to mode color (top to bottom)
        gradient = y_coords / 128.0  # 0 at top, 1 at bottom

        # Add some horizontal variation for interest
        h_wave = np.sin(x_coords / 20 + t) * 0.1

        # Combine effects
        intensity = np.clip(gradient * 0.6 + wave + h_wave, 0.1, 0.8) * pulse

        # Apply mode color with animated intensity
        r = np.clip(mr * intensity, 0, 255).astype(np.uint8)
        g = np.clip(mg * intensity, 0, 255).astype(np.uint8)
        b = np.clip(mb * intensity, 0, 255).astype(np.uint8)

        # Broadcast to full buffer
        buffer[:, :, 0] = np.broadcast_to(r, (128, 128))
        buffer[:, :, 1] = np.broadcast_to(g, (128, 128))
        buffer[:, :, 2] = np.broadcast_to(b, (128, 128))

    def _draw_pixel_icon(self, buffer, pattern: list, cx: int, cy: int, color: tuple, scale: int = 3, time: float = 0) -> None:
        """Draw a pixel art icon from pattern with animation."""
        from artifact.graphics.primitives import draw_rect

        if not pattern:
            return

        height = len(pattern)
        width = max(len(row) for row in pattern) if pattern else 0

        # Start position (centered)
        start_x = cx - (width * scale) // 2
        start_y = cy - (height * scale) // 2

        for row_idx, row in enumerate(pattern):
            for col_idx, char in enumerate(row):
                x = start_x + col_idx * scale
                y = start_y + row_idx * scale

                if char == '█':
                    # Main outline color
                    draw_rect(buffer, x, y, scale, scale, color)
                elif char == '░':
                    # Inner highlight (lighter)
                    highlight = tuple(min(255, c + 80) for c in color)
                    draw_rect(buffer, x, y, scale, scale, highlight)
                elif char == '▓':
                    # Darker accent
                    dark = tuple(c // 2 for c in color)
                    draw_rect(buffer, x, y, scale, scale, dark)
                elif char == '▼' or char == '▲' or char == '●':
                    # Animated accent
                    pulse = int(math.sin(time * 5 + col_idx + row_idx) * 50)
                    accent = tuple(min(255, max(0, c + pulse)) for c in color)
                    draw_rect(buffer, x, y, scale, scale, accent)
                elif char == '?':
                    # Question mark in different color
                    draw_rect(buffer, x, y, scale, scale, (255, 255, 100))

    def _render_mode_select_ticker(self, buffer) -> None:
        """Render ticker during mode select with smooth scrolling description."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)

        mode = self.get_selected_mode()
        if mode:
            # Get mode description (fallback to name if no description)
            description = MODE_DESCRIPTIONS_RU.get(mode.name, mode.display_name)
            # Scrolling text: mode name + description, repeated for seamless loop
            text = f"{mode.display_name}: {description}   {mode.display_name}: {description}   "
            render_ticker_animated(
                buffer, text,
                self._time_in_state, (255, 200, 0),
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

    def _render_result_ticker(self, buffer) -> None:
        """Render ticker during result/printing states."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)

        if self._last_result:
            # Get mode display name
            mode_name = self._last_result.mode_name
            mode_title = MODE_LABELS_RU.get(mode_name, mode_name.upper())

            # Show mode name and navigation hint
            if self._state == ManagerState.PRINTING:
                text = f"ПЕЧАТАЮ {mode_title}"
                color = (100, 200, 100)  # Green for printing
            else:
                # Show pagination info if multiple pages
                if self._result_text_pages and len(self._result_text_pages) > 1:
                    page_num = self._result_text_page_index + 1
                    total_pages = len(self._result_text_pages)
                    text = f"{mode_title} СТРАНИЦА {page_num}/{total_pages} ЛИСТАТЬ"
                else:
                    text = f"{mode_title} ГОТОВО КНОПКА ПЕЧАТЬ"
                color = (255, 200, 100)  # Gold for result

            render_ticker_animated(
                buffer, text,
                self._time_in_state, color,
                TickerEffect.WAVE_SCROLL, speed=0.022
            )
        else:
            # Fallback
            render_ticker_animated(
                buffer, "ГОТОВО",
                self._time_in_state, (255, 255, 200),
                TickerEffect.SCROLL, speed=0.025
            )

    def _render_result(self, buffer) -> None:
        """Render result screen with user-controlled views.

        Views are navigated with LEFT/RIGHT buttons. Auto-advance is slower
        and can be disabled by user interaction.

        Views (AUTO-PRINT enabled - no confirmation needed):
        - 0: Prediction text with pagination
        - 1: Caricature image (if available)
        """
        from artifact.graphics.text_utils import (
            draw_centered_text,
            MAIN_SAFE_BOTTOM_S1, MAIN_SAFE_BOTTOM_S2, MAIN_HINT_ZONE_Y
        )
        from artifact.graphics.fonts import load_font
        from artifact.graphics.primitives import fill, draw_rect
        from io import BytesIO

        fill(buffer, (20, 30, 40))

        if not self._last_result:
            draw_centered_text(buffer, "ГОТОВО!", 50, (255, 255, 200), scale=2)
            return

        # Use the tracked view index (user-controlled)
        view = self._result_view_index
        has_caricature = (self._last_result.print_data and
                         self._last_result.print_data.get("caricature"))

        # View indicator dots at top (only if multiple views)
        if self._result_num_views > 1:
            self._render_view_dots(buffer, view, self._result_num_views)

        if view == 0:
            # Prediction text view with PAGINATION (no scrolling!)
            # Get mode display name for title (not hardcoded!)
            mode_name = self._last_result.mode_name if self._last_result else "РЕЗУЛЬТАТ"
            mode_title = MODE_LABELS_RU.get(mode_name, mode_name.upper())

            # Compact title line with page arrows (saves vertical space)
            total_pages = len(self._result_text_pages) if self._result_text_pages else 1
            page_idx = min(self._result_text_page_index, total_pages - 1) if self._result_text_pages else 0

            if total_pages > 1:
                # Arrows on sides of title with page numbers
                left_arrow = "◄" if page_idx > 0 else " "
                right_arrow = "►" if page_idx < total_pages - 1 else " "
                title_text = f"{left_arrow} {page_idx + 1}/{total_pages} {right_arrow}"
                draw_centered_text(buffer, title_text, 3, (100, 150, 200), scale=1)
            else:
                draw_centered_text(buffer, mode_title, 3, (255, 200, 100), scale=1)

            # Render current text page - FULLSCREEN (text goes to bottom)
            if self._result_text_pages:
                page_lines = self._result_text_pages[page_idx]

                # Render lines with subtle animation (fullscreen, no wasted space)
                y = 12
                line_height = 8
                for i, line in enumerate(page_lines):
                    # Subtle pulse for readability
                    pulse = 0.9 + 0.1 * math.sin(self._time_in_state / 400 + i * 0.3)
                    color = tuple(int(255 * pulse) for _ in range(3))
                    draw_centered_text(buffer, line, y, color, scale=1)
                    y += line_height
            else:
                draw_centered_text(buffer, "...", 50, (100, 100, 100), scale=1)

            # No bottom hints - fullscreen text!

            # Printing status hint
            if self._state == ManagerState.PRINTING:
                draw_centered_text(buffer, "ПЕЧАТАЮ...", MAIN_HINT_ZONE_Y, (100, 200, 100), scale=1)

        elif view == 1 and has_caricature:
            # Caricature view - FULLSCREEN (no text overlay)
            try:
                from PIL import Image
                import numpy as np

                caricature_data = self._last_result.print_data.get("caricature")
                img = Image.open(BytesIO(caricature_data))
                img = img.convert("RGB")
                # FULLSCREEN - fill entire 128x128 display
                img = img.resize((128, 128), Image.Resampling.LANCZOS)

                img_array = np.array(img)
                buffer[:128, :128] = img_array
            except Exception:
                # Fallback to placeholder
                draw_centered_text(buffer, "ШАРЖ", 50, (200, 200, 200), scale=2)

            # Printing status hint
            if self._state == ManagerState.PRINTING:
                draw_centered_text(buffer, "ПЕЧАТАЮ...", MAIN_HINT_ZONE_Y, (100, 200, 100), scale=1)

        else:
            # QR view - check if QR is available (could be view 1 or 2)
            has_qr = (self._last_result.print_data and
                      self._last_result.print_data.get("qr_image") is not None)
            if has_qr:
                from PIL import Image
                import numpy as np

                fill(buffer, (255, 255, 255))  # White background for QR

                qr_image = self._last_result.print_data.get("qr_image")
                if qr_image is not None:
                    try:
                        qr_h, qr_w = qr_image.shape[:2]
                        target_size = 120
                        if qr_h != target_size or qr_w != target_size:
                            qr_pil = Image.fromarray(qr_image)
                            qr_pil = qr_pil.resize((target_size, target_size), Image.Resampling.NEAREST)
                            qr_scaled = np.array(qr_pil, dtype=np.uint8)
                        else:
                            qr_scaled = qr_image

                        qr_h, qr_w = qr_scaled.shape[:2]
                        x_offset = (128 - qr_w) // 2
                        y_offset = (128 - qr_h) // 2
                        buffer[y_offset:y_offset + qr_h, x_offset:x_offset + qr_w] = qr_scaled
                    except Exception:
                        fill(buffer, (20, 20, 30))
                        draw_centered_text(buffer, "QR", 50, (100, 100, 100), scale=2)
            else:
                # No QR available, show placeholder
                fill(buffer, (20, 20, 30))
                draw_centered_text(buffer, "ГОТОВО", 50, (100, 200, 100), scale=2)

    def _render_view_dots(self, buffer, current_view: int, total_views: int) -> None:
        """Render view indicator dots at top of screen."""
        from artifact.graphics.primitives import draw_circle

        if total_views <= 1:
            return

        dot_spacing = 10
        start_x = 64 - (total_views - 1) * dot_spacing // 2
        y = 3

        for i in range(total_views):
            x = start_x + i * dot_spacing
            if i == current_view:
                draw_circle(buffer, x, y, 2, (255, 200, 100))  # Active dot
            else:
                draw_circle(buffer, x, y, 1, (80, 80, 100))  # Inactive dot

    def _render_printing(self, buffer) -> None:
        """Render printing progress."""
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import fill, draw_rect

        fill(buffer, (30, 30, 30))

        # Title centered
        draw_centered_text(buffer, "ПЕЧАТАЮ", 35, (255, 255, 255), scale=2)

        # Progress bar - centered
        progress = min(1.0, self._time_in_state / 10000)
        bar_width = int(100 * progress)
        bar_x = (128 - 100) // 2  # Center the bar
        draw_rect(buffer, bar_x, 60, 100, 10, (50, 50, 50))
        draw_rect(buffer, bar_x, 60, bar_width, 10, (0, 200, 100))

        # Dots animation - centered below progress bar
        dots = "." * (int(self._time_in_state / 300) % 4)
        if dots:
            draw_centered_text(buffer, dots, 80, (200, 200, 200), scale=2)

    def _render_admin_menu(self, buffer) -> None:
        """Render admin menu."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import fill

        fill(buffer, (40, 20, 20))
        font = load_font("cyrillic")

        # Title centered
        draw_centered_text(buffer, "ADMIN", 10, (255, 100, 100), scale=2)

        # Menu options - left aligned with proper margin
        options = [
            "1. Theme",
            "2. Stats",
            "3. Test",
            "* Exit"
        ]
        y = 40
        for opt in options:
            draw_text_bitmap(buffer, opt, 25, y, (200, 200, 200), font, scale=1)
            y += 15

    # Callbacks
    def set_on_mode_complete(self, callback: Callable[[ModeResult], None]) -> None:
        """Set callback for mode completion."""
        self._on_mode_complete = callback

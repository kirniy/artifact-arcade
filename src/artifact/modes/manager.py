"""Mode manager for ARTIFACT - handles mode selection, transitions, and idle state."""

from typing import Dict, List, Optional, Type, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
import random
import math

from artifact.core.events import EventBus, Event, EventType
from artifact.core.state import StateMachine, State
from artifact.animation.engine import AnimationEngine
from artifact.animation.idle_scenes import RotatingIdleAnimation
from artifact.animation.reveal_effects import RevealAnimator, RevealStyle
from artifact.graphics.renderer import Renderer
from artifact.graphics.display_coordinator import DisplayCoordinator, CrossDisplayEffect
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
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
    "vnvnc_rush": [  # Lightning bolt
        "     ██     ",
        "    ███     ",
        "   ███      ",
        "  ███       ",
        " ████       ",
        "  ███       ",
        "   ███      ",
        "    ███     ",
        "     ███    ",
        "      ██    ",
    ],
}

# Mode colors for visual identity
MODE_COLORS = {
    "fortune": (200, 100, 255),     # Purple
    "roulette": (255, 50, 50),      # Red
    "quiz": (255, 215, 0),          # Gold
    "squid_game": (255, 100, 150),  # Pink
    "guess_me": (100, 200, 255),    # Cyan
    "autopsy": (150, 255, 150),     # Green
    "roast": (255, 150, 50),        # Orange
    "ai_prophet": (100, 255, 200),  # Teal
    "flow_field": (100, 150, 255),  # Blue
    "glitch_mirror": (255, 50, 150),# Magenta
    "dither_art": (150, 200, 100),  # Lime
    "ascii_art": (0, 255, 100),     # Terminal green
    "particle_sculptor": (200, 150, 255),  # Lavender
    "vnvnc_rush": (255, 80, 160),   # Neon pink
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
    "vnvnc_rush": SelectorEffect.PIXELATE,
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
        self._result_view_index: int = 0      # Current view (0=prompt, 1=prediction, 2=caricature)
        self._result_num_views: int = 2       # Number of views available
        self._result_auto_advance: bool = True  # Auto-advance enabled
        self._result_first_default: float = 8000  # Baseline timing
        self._result_next_default: float = 6000
        self._result_first_advance_time: float = self._result_first_default
        self._result_next_advance_time: float = self._result_next_default
        self._result_last_advance: float = 0.0  # Time of last advance

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

        # Start idle music
        self._audio.play_music("idle", fade_in_ms=1000)

        # Mode selector camera and effects
        self._selector_camera = None
        self._selector_frame = None
        self._selector_effect = SelectorEffect.DITHER
        self._selector_effect_index = 0
        self._selector_effects = list(SelectorEffect)
        self._selector_effect_timer = 0.0  # Cycle effect every 3 seconds
        self._bayer_matrix = self._create_bayer_matrix(4)  # 4x4 Bayer matrix

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
        """Open camera for mode selector background."""
        if self._selector_camera is None:
            try:
                from artifact.simulator.mock_hardware.camera import create_camera
                self._selector_camera = create_camera(resolution=(128, 128))
                self._selector_camera.open()
            except Exception:
                self._selector_camera = None

    def _close_selector_camera(self) -> None:
        """Close the selector camera."""
        if self._selector_camera:
            try:
                self._selector_camera.close()
            except Exception:
                pass
            self._selector_camera = None
            self._selector_frame = None

    def _update_selector_camera(self) -> None:
        """Capture a frame from the selector camera."""
        if self._selector_camera:
            try:
                frame = self._selector_camera.capture_frame()
                if frame is not None:
                    self._selector_frame = frame
            except Exception:
                pass

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
        info = ModeInfo(
            cls=mode_cls,
            name=mode_cls.name,
            display_name=mode_cls.display_name,
            icon=mode_cls.icon,
            style=mode_cls.style,
            description=getattr(mode_cls, "description", getattr(mode_cls, "__doc__", "") or mode_cls.display_name),
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
            self._result_view_index = 0
            self._result_auto_advance = True
            self._result_last_advance = 0.0
            self._result_first_advance_time = self._result_first_default
            self._result_next_advance_time = self._result_next_default
            # Determine number of views based on result data
            if self._last_result:
                has_caricature = (self._last_result.print_data and
                                  self._last_result.print_data.get("caricature"))
                self._result_num_views = 3 if has_caricature else 2
                if self._last_result.display_text:
                    try:
                        from artifact.graphics.fonts import load_font
                        from artifact.graphics.text_utils import smart_wrap_text

                        font = load_font("cyrillic")
                        lines = smart_wrap_text(self._last_result.display_text, 120, font, scale=1)
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
            else:
                self._result_num_views = 2

        # Handle music transitions and cross-display effects
        if new_state == ManagerState.IDLE:
            self._audio.play_music("idle", fade_in_ms=1000)
            self._display_coordinator.clear_effect()  # Clear effects on idle
            self._close_selector_camera()  # Close selector camera if open
        elif new_state == ManagerState.MODE_SELECT:
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
            self._start_selected_mode()

        elif self._state == ManagerState.MODE_ACTIVE:
            # Pass to active mode
            if self._current_mode:
                self._current_mode.handle_input(event)

        elif self._state == ManagerState.RESULT:
            # Print or exit
            if self._last_result and self._last_result.should_print:
                self._start_printing()
            else:
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
            self._select_previous_mode()
        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.handle_input(event)
        elif self._state == ManagerState.RESULT:
            # Left = Previous view (with wrap-around)
            self._result_view_index = (self._result_view_index - 1) % self._result_num_views
            self._result_auto_advance = False  # User took control, disable auto
            self._result_last_advance = self._time_in_state
            self._audio.play_ui_move()

    def _on_arcade_right(self, event: Event) -> None:
        """Handle right arcade button."""
        self._last_input_time = self._time_in_state

        if self._state == ManagerState.IDLE:
            # Switch to next idle scene
            self._idle_animation.next_scene()
        elif self._state == ManagerState.MODE_SELECT:
            self._select_next_mode()
        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.handle_input(event)
        elif self._state == ManagerState.RESULT:
            # Right = Next view (with wrap-around)
            self._result_view_index = (self._result_view_index + 1) % self._result_num_views
            self._result_auto_advance = False  # User took control, disable auto
            self._result_last_advance = self._time_in_state
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

        if self._on_mode_complete:
            self._on_mode_complete(result)

    # Printing
    def _start_printing(self) -> None:
        """Start printing process."""
        self._change_state(ManagerState.PRINTING)

        # Emit print event with result data for printer preview
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

        elif self._state == ManagerState.MODE_SELECT:
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
            # Use arrow symbols instead of L/R
            return "← НЕТ ★ → ДА".center(16)[:16]

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
        # Darken center area slightly for text readability
        panel_y1, panel_y2 = 40, 90
        for y in range(panel_y1, panel_y2):
            for x in range(20, 108):
                # Distance from center for rounded corners effect
                dist_x = abs(x - 64) / 44
                dist_y = abs(y - 65) / 25
                if dist_x > 1 or dist_y > 1:
                    continue
                # Subtle darkening
                r = max(0, int(buffer[y, x, 0] * 0.4))
                g = max(0, int(buffer[y, x, 1] * 0.4))
                b = max(0, int(buffer[y, x, 2] * 0.4))
                buffer[y, x] = [r, g, b]

        # === STEP 3: MODE NAME - BIG AND CENTERED ===
        name = mode.display_name.upper()
        font = load_font("cyrillic")

        # Thick black outline for perfect readability
        name_y = 58
        for ox in [-2, -1, 0, 1, 2]:
            for oy in [-2, -1, 0, 1, 2]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, name, name_y + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, name, name_y, glow_color, scale=2)

        # === STEP 4: NAVIGATION ARROWS ===
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
                                    min(255, buffer[dot_y + gy - 3, x + gx - 3, 0] + 30),
                                    min(255, buffer[dot_y + gy - 3, x + gx - 3, 1] + 30),
                                    min(255, buffer[dot_y + gy - 3, x + gx - 3, 2] + 30)
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
                    draw_centered_text(buffer, "НАЖМИ КНОПКУ", prompt_y + oy, (0, 0, 0), scale=1)
        draw_centered_text(buffer, "НАЖМИ КНОПКУ", prompt_y, prompt_color, scale=1)

    def _render_camera_effect_background(self, buffer, t: float) -> None:
        """Apply current effect to camera frame and render to FULL 128x128 buffer."""
        import numpy as np

        frame = self._selector_frame
        if frame is None:
            return

        # Mirror horizontally for selfie view
        frame = np.fliplr(frame)

        # CRITICAL: Resize frame to EXACTLY 128x128 to fill entire screen
        if frame.shape[0] != 128 or frame.shape[1] != 128:
            try:
                import cv2
                frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_LINEAR)
            except ImportError:
                # Manual nearest-neighbor resize if cv2 not available
                old_h, old_w = frame.shape[:2]
                new_frame = np.zeros((128, 128, 3), dtype=np.uint8)
                for y in range(128):
                    for x in range(128):
                        src_y = min(int(y * old_h / 128), old_h - 1)
                        src_x = min(int(x * old_w / 128), old_w - 1)
                        new_frame[y, x] = frame[src_y, src_x]
                frame = new_frame

        # Apply effect based on current selection
        if self._selector_effect == SelectorEffect.DITHER:
            self._apply_dither_effect(buffer, frame, t)
        elif self._selector_effect == SelectorEffect.SCANLINES:
            self._apply_scanline_effect(buffer, frame, t)
        elif self._selector_effect == SelectorEffect.PIXELATE:
            self._apply_pixelate_effect(buffer, frame, t)
        elif self._selector_effect == SelectorEffect.THERMAL:
            self._apply_thermal_effect(buffer, frame, t)
        elif self._selector_effect == SelectorEffect.MATRIX:
            self._apply_matrix_effect(buffer, frame, t)

    def _apply_dither_effect(self, buffer, frame, t: float) -> None:
        """Apply Bayer ordered dithering to camera frame."""
        import numpy as np

        h, w = frame.shape[:2]
        bayer_size = len(self._bayer_matrix)
        bayer_max = bayer_size * bayer_size

        # Convert to grayscale
        gray = np.mean(frame, axis=2).astype(np.float32)

        # Apply dithering with pulsing threshold
        pulse = 0.85 + 0.15 * math.sin(t * 2)
        for y in range(h):
            for x in range(w):
                bayer_val = self._bayer_matrix[y % bayer_size][x % bayer_size]
                threshold = (bayer_val / bayer_max) * 255 * pulse
                if gray[y, x] > threshold:
                    # Bright pixels - vivid cyan/purple gradient
                    r = int(140 + 100 * (x / w))
                    g = int(220 + 35 * math.sin(t + y / 20))
                    b = int(255)
                    buffer[y, x] = [min(255, r), min(255, g), min(255, b)]
                else:
                    # Dark pixels - visible dark blue
                    buffer[y, x] = [20, 15, 50]

    def _apply_scanline_effect(self, buffer, frame, t: float) -> None:
        """Apply CRT scanline effect to camera frame."""
        import numpy as np

        h, w = frame.shape[:2]

        # Copy frame with boosted brightness and CRT look
        for y in range(h):
            scanline_intensity = 0.9 if y % 2 == 0 else 0.5  # Brighter scanlines
            # Add subtle wave distortion
            wave_offset = int(math.sin(y / 10 + t * 5) * 2)
            for x in range(w):
                src_x = (x + wave_offset) % w
                r = int(frame[y, src_x, 0] * scanline_intensity * 1.1)
                g = int(frame[y, src_x, 1] * scanline_intensity * 1.3)  # Strong green for CRT
                b = int(frame[y, src_x, 2] * scanline_intensity * 1.0)
                buffer[y, x] = [min(255, r), min(255, g), min(255, b)]

        # Add phosphor glow on bright areas
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                if buffer[y, x, 1] > 100:  # Green channel bright
                    # Subtle bloom
                    for dy in [-1, 1]:
                        ny = y + dy
                        buffer[ny, x, 1] = min(255, buffer[ny, x, 1] + 15)

    def _apply_pixelate_effect(self, buffer, frame, t: float) -> None:
        """Apply chunky pixel effect to camera frame."""
        import numpy as np

        h, w = frame.shape[:2]
        block_size = 8  # Chunky 8x8 pixels

        for by in range(0, h, block_size):
            for bx in range(0, w, block_size):
                # Average color in block
                block = frame[by:by+block_size, bx:bx+block_size]
                avg_color = np.mean(block, axis=(0, 1)).astype(np.uint8)

                # Quantize colors to retro palette (fewer colors)
                r = (avg_color[0] // 64) * 64 + 32
                g = (avg_color[1] // 64) * 64 + 32
                b = (avg_color[2] // 64) * 64 + 32

                # Fill block with slight variation for texture
                for y in range(by, min(by + block_size, h)):
                    for x in range(bx, min(bx + block_size, w)):
                        # Add pixel grid lines
                        if x % block_size == 0 or y % block_size == 0:
                            buffer[y, x] = [r // 2, g // 2, b // 2]
                        else:
                            buffer[y, x] = [r, g, b]

    def _apply_thermal_effect(self, buffer, frame, t: float) -> None:
        """Apply thermal camera style effect."""
        import numpy as np

        h, w = frame.shape[:2]

        # Convert to grayscale (heat map based on brightness)
        gray = np.mean(frame, axis=2)

        for y in range(h):
            for x in range(w):
                heat = gray[y, x] / 255.0

                # Thermal color mapping: black -> blue -> purple -> red -> yellow -> white
                if heat < 0.2:
                    r, g, b = 0, 0, int(heat * 5 * 150)
                elif heat < 0.4:
                    t_heat = (heat - 0.2) / 0.2
                    r, g, b = int(t_heat * 100), 0, 150
                elif heat < 0.6:
                    t_heat = (heat - 0.4) / 0.2
                    r, g, b = 100 + int(t_heat * 155), 0, int((1 - t_heat) * 150)
                elif heat < 0.8:
                    t_heat = (heat - 0.6) / 0.2
                    r, g, b = 255, int(t_heat * 200), 0
                else:
                    t_heat = (heat - 0.8) / 0.2
                    r, g, b = 255, 200 + int(t_heat * 55), int(t_heat * 200)

                buffer[y, x] = [min(255, r), min(255, g), min(255, b)]

    def _apply_matrix_effect(self, buffer, frame, t: float) -> None:
        """Apply Matrix-style green rain effect over camera."""
        import numpy as np

        h, w = frame.shape[:2]

        # Convert to green-tinted grayscale
        gray = np.mean(frame, axis=2)

        for y in range(h):
            for x in range(w):
                brightness = gray[y, x] / 255.0

                # Matrix rain columns
                rain_phase = (y / 8 + x * 0.3 + t * 3) % 10
                rain_intensity = max(0, 1 - rain_phase / 5) if rain_phase < 5 else 0

                # Combine camera brightness with rain
                g = int(brightness * 150 + rain_intensity * 100)
                r = int(brightness * 20 + rain_intensity * 10)
                b = int(brightness * 30)

                buffer[y, x] = [min(255, r), min(255, g), min(255, b)]

    def _render_fallback_gradient(self, buffer, t: float) -> None:
        """Render animated gradient when no camera available."""
        from artifact.graphics.primitives import draw_line

        for y in range(128):
            wave = math.sin(y / 20 + t * 2) * 10
            r = int(max(0, min(255, 20 + wave + math.sin(t) * 10)))
            g = int(max(0, min(255, 10 + y / 10)))
            b = int(max(0, min(255, 40 + y / 4 + math.cos(t * 0.5) * 20)))
            draw_line(buffer, 0, y, 128, y, (r, g, b))

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
        """Render ticker during mode select with smooth scrolling."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)

        mode = self.get_selected_mode()
        if mode:
            # Explicit nav hint + mode name - using ASCII-safe characters
            text = f"<< >> ЛИСТАЙ - СТАРТ ОК - {mode.display_name}"
            render_ticker_animated(
                buffer, text,
                self._time_in_state, (255, 200, 0),
                TickerEffect.SPARKLE_SCROLL, speed=0.025
            )

    def _render_result(self, buffer) -> None:
        """Render result screen with user-controlled views.

        Views are navigated with LEFT/RIGHT buttons. Auto-advance is slower
        and can be disabled by user interaction.

        Views:
        - 0: Print prompt (do you want to print?)
        - 1: Prediction text with auto-scroll
        - 2: Caricature image (if available)
        """
        from artifact.graphics.text_utils import (
            draw_centered_text, smart_wrap_text,
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

        # View indicator dots at top
        self._render_view_dots(buffer, view, self._result_num_views)

        if view == 0:
            # Print prompt view
            draw_centered_text(buffer, "СОХРАНИТЬ", 25, (150, 180, 200), scale=2)
            draw_centered_text(buffer, "НА ПАМЯТЬ?", 48, (150, 180, 200), scale=2)
            draw_centered_text(buffer, "ПЕЧАТЬ", 75, (255, 255, 100), scale=2)

            # Navigation hint and print options at safe bottom position
            nav_hint = "< НАЗАД  ДАЛЕЕ >"
            draw_centered_text(buffer, nav_hint, 100, (100, 120, 140), scale=1)

            if self._last_result.should_print:
                draw_centered_text(buffer, "НАЖМИ СТАРТ", MAIN_HINT_ZONE_Y, (150, 200, 150), scale=1)
            else:
                draw_centered_text(buffer, "НАЖМИ КНОПКУ", MAIN_HINT_ZONE_Y, (150, 150, 150), scale=1)

        elif view == 1:
            # Prediction text view with auto-scroll for long text
            text = self._last_result.display_text or "..."
            font = load_font("cyrillic")

            # Title
            draw_centered_text(buffer, "ПРОРОЧЕСТВО", 3, (255, 200, 100), scale=1)

            # Wrap text to fit screen width
            lines = smart_wrap_text(text, 120, font, scale=1)
            max_visible = 7  # Lines that fit on screen (with title and hints)

            # Calculate scroll offset for long text - smooth scroll based on time in this view
            if len(lines) > max_visible:
                # Use time since entering this view for scroll
                scroll_cycle = 6000  # 6 seconds per scroll cycle
                time_in_view = self._time_in_state - self._result_last_advance
                scroll_progress = (time_in_view % scroll_cycle) / scroll_cycle
                max_scroll = len(lines) - max_visible
                scroll_offset = int(scroll_progress * max_scroll)
            else:
                scroll_offset = 0

            # Render visible lines
            y = 16
            line_height = 11
            for i in range(max_visible):
                line_idx = scroll_offset + i
                if line_idx < len(lines):
                    draw_centered_text(buffer, lines[line_idx], y, (255, 255, 255), scale=1)
                y += line_height

            # Scroll indicator if text is long
            if len(lines) > max_visible:
                indicator = "▼" if scroll_offset < len(lines) - max_visible else "●"
                draw_centered_text(buffer, indicator, 95, (100, 100, 120), scale=1)

            # Navigation and action hints at safe bottom positions
            draw_centered_text(buffer, "< НАЗАД  ДАЛЕЕ >", 105, (100, 120, 140), scale=1)
            if self._last_result.should_print:
                draw_centered_text(buffer, "СТАРТ: ПЕЧАТЬ", MAIN_HINT_ZONE_Y, (100, 150, 100), scale=1)

        elif view == 2 and has_caricature:
            # Caricature view
            try:
                from PIL import Image
                import numpy as np

                caricature_data = self._last_result.print_data.get("caricature")
                img = Image.open(BytesIO(caricature_data))
                img = img.convert("RGB")
                img = img.resize((96, 96), Image.Resampling.NEAREST)

                # Center on screen with space for hints
                img_array = np.array(img)
                x_offset = (128 - 96) // 2
                y_offset = 8
                buffer[y_offset:y_offset+96, x_offset:x_offset+96] = img_array

                # Title at safe bottom position
                draw_centered_text(buffer, "ТВОЙ ШАРЖ", 105, (255, 200, 100), scale=1)
            except Exception:
                # Fallback to placeholder
                draw_centered_text(buffer, "ШАРЖ", 50, (200, 200, 200), scale=2)

            # Print hint at safe position
            if self._last_result.should_print:
                draw_centered_text(buffer, "СТАРТ: ПЕЧАТЬ", MAIN_HINT_ZONE_Y, (100, 150, 100), scale=1)

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

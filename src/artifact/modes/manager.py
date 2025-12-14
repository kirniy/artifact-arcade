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
from artifact.graphics.renderer import Renderer
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
}

# Mode colors for visual identity
MODE_COLORS = {
    "fortune": (200, 100, 255),   # Purple
    "roulette": (255, 50, 50),    # Red
    "quiz": (255, 215, 0),        # Gold
    "squid_game": (255, 100, 150),# Pink
    "guess_me": (100, 200, 255),  # Cyan
    "autopsy": (150, 255, 150),   # Green
    "roast": (255, 150, 50),      # Orange
    "ai_prophet": (100, 255, 200),# Teal
}


class ManagerState(Enum):
    """Mode manager states."""

    IDLE = auto()           # Attract mode - waiting for user
    MODE_SELECT = auto()    # User selecting a mode
    MODE_ACTIVE = auto()    # A mode is running
    RESULT = auto()         # Showing result
    PRINTING = auto()       # Printing receipt
    ADMIN_MENU = auto()     # Hidden admin menu


@dataclass
class ModeInfo:
    """Information about a registered mode."""

    cls: Type[BaseMode]
    name: str
    display_name: str
    icon: str
    style: str
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

        # Callbacks
        self._on_mode_complete: Optional[Callable[[ModeResult], None]] = None

        # Audio engine for music
        self._audio = get_audio_engine()

        # Register event handlers
        self._setup_event_handlers()

        # Start idle music
        self._audio.play_music("idle", fade_in_ms=1000)

        logger.info("ModeManager initialized")

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

        # Handle music transitions
        if new_state == ManagerState.IDLE:
            self._audio.play_music("idle", fade_in_ms=1000)
        elif new_state == ManagerState.MODE_SELECT:
            self._audio.play_music("menu", fade_in_ms=300)
            self._audio.play_ui_confirm()  # Confirmation sound
        elif new_state == ManagerState.RESULT:
            # Result screen - play success or result music
            self._audio.play_music("idle", fade_in_ms=500)
            self._audio.play_success()
        elif new_state == ManagerState.PRINTING:
            self._audio.stop_music(fade_out_ms=200)
            self._audio.play_print()

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
            # Left = No print, exit
            self._return_to_idle()

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
            # Right = Yes print
            if self._last_result and self._last_result.should_print:
                self._start_printing()

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

        # Handle state-specific updates
        if self._state == ManagerState.IDLE:
            self._idle_animation.update(delta_ms)

        elif self._state == ManagerState.MODE_SELECT:
            # Timeout back to idle
            if self._time_in_state - self._last_input_time > self._idle_timeout:
                self._return_to_idle()

        elif self._state == ManagerState.MODE_ACTIVE:
            if self._current_mode:
                self._current_mode.update(delta_ms)

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

        elif self._state == ManagerState.PRINTING:
            self._render_printing(buffer)

        elif self._state == ManagerState.ADMIN_MENU:
            self._render_admin_menu(buffer)

    def render_ticker(self, buffer) -> None:
        """Render ticker display."""
        if self._state == ManagerState.IDLE:
            self._idle_animation.render_ticker(buffer)

        elif self._state == ManagerState.MODE_SELECT:
            self._render_mode_select_ticker(buffer)

        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.render_ticker(buffer)

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
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import draw_rect

        # Blinking "НАЖМИ" at bottom - positioned to not get cut off
        if int(self._time_in_state / 500) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ", 100, (255, 200, 0), scale=2)

        # Arrow pointing down (to button) - wide at top, point at bottom
        # Position adjusted to stay within 128px height
        base_y = 115
        bounce = int((self._time_in_state / 200) % 3)  # Reduced bounce range
        cx = 64
        # Down arrow: starts wide, ends in point
        for i in range(4):  # Reduced height to fit
            width = (4 - i) * 2 - 1  # 7, 5, 3, 1
            x_start = cx - width // 2
            draw_rect(buffer, x_start, base_y + bounce + i, width, 1, (255, 100, 100))

    def _render_mode_select(self, buffer) -> None:
        """Render BANGER mode selection screen - full animated carousel."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.text_utils import draw_centered_text
        from artifact.graphics.primitives import fill, draw_rect, draw_circle, draw_line

        # Animated gradient background
        t = self._time_in_state / 1000
        for y in range(128):
            # Synthwave gradient with wave effect
            wave = math.sin(y / 20 + t * 2) * 10
            r = int(20 + wave + math.sin(t) * 10)
            g = int(10 + y / 10)
            b = int(40 + y / 4 + math.cos(t * 0.5) * 20)
            draw_line(buffer, 0, y, 128, y, (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))

        # Grid lines for retro effect
        for i in range(0, 128, 16):
            alpha = int(30 + 20 * math.sin(t * 3 + i / 10))
            draw_line(buffer, 0, i, 128, i, (alpha, alpha, alpha + 20))
            draw_line(buffer, i, 0, i, 128, (alpha, alpha, alpha + 20))

        mode = self.get_selected_mode()
        if not mode:
            draw_centered_text(buffer, "НЕТ РЕЖИМОВ", 60, (255, 100, 100), scale=1)
            return

        # Get mode color
        mode_color = MODE_COLORS.get(mode.name, (255, 200, 0))

        # Pulsing glow effect
        pulse = 0.7 + 0.3 * math.sin(t * 4)
        glow_color = tuple(int(c * pulse) for c in mode_color)

        # Draw large animated icon in center
        icon_pattern = MODE_ICONS.get(mode.name)
        if icon_pattern:
            self._draw_pixel_icon(buffer, icon_pattern, 64, 45, mode_color, scale=4, time=t)
        else:
            # Fallback to text icon
            draw_centered_text(buffer, mode.icon, 40, glow_color, scale=4)

        # Mode name with glow - positioned below icon
        name = mode.display_name
        name_scale = 1 if len(name) > 10 else 2

        # Shadow/glow effect
        draw_centered_text(buffer, name, 88, (mode_color[0]//4, mode_color[1]//4, mode_color[2]//4), scale=name_scale)
        draw_centered_text(buffer, name, 87, glow_color, scale=name_scale)

        # Animated arrows with bounce
        if len(self._mode_order) > 1:
            bounce = int(math.sin(t * 6) * 3)
            font = load_font("cyrillic")
            # Left arrow
            draw_text_bitmap(buffer, "<", 5 - bounce, 45, (100, 200, 255), font, scale=2)
            draw_text_bitmap(buffer, "<", 12 - bounce, 45, (50, 100, 150), font, scale=2)
            # Right arrow
            draw_text_bitmap(buffer, ">", 111 + bounce, 45, (100, 200, 255), font, scale=2)
            draw_text_bitmap(buffer, ">", 104 + bounce, 45, (50, 100, 150), font, scale=2)

        # Mode indicator dots with animation
        num_modes = len(self._mode_order)
        if num_modes > 1:
            dot_spacing = 12
            start_x = 64 - (num_modes - 1) * dot_spacing // 2
            for i in range(num_modes):
                x = start_x + i * dot_spacing
                if i == self._selected_index:
                    # Selected dot - animated
                    size = 4 + int(math.sin(t * 8) * 2)
                    draw_circle(buffer, x, 105, size, mode_color)
                    draw_circle(buffer, x, 105, size - 1, (255, 255, 255))
                else:
                    draw_circle(buffer, x, 105, 2, (60, 60, 80))

        # Bottom prompt with flashing
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "ЖМЯКНИ СТАРТ", 118, (150, 200, 150), scale=1)
        else:
            draw_centered_text(buffer, "ЖМЯКНИ СТАРТ", 118, (200, 255, 200), scale=1)

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
            # Mode name with rainbow scroll effect
            render_ticker_animated(
                buffer, f"ВЫБРАНО: {mode.display_name}",
                self._time_in_state, (255, 200, 0),
                TickerEffect.RAINBOW_SCROLL, speed=0.025
            )

    def _render_result(self, buffer) -> None:
        """Render result screen with cycling views."""
        from artifact.graphics.text_utils import draw_centered_text, draw_wrapped_text, smart_wrap_text
        from artifact.graphics.fonts import load_font
        from artifact.graphics.primitives import fill
        from io import BytesIO

        fill(buffer, (20, 30, 40))

        if not self._last_result:
            draw_centered_text(buffer, "ГОТОВО!", 50, (255, 255, 200), scale=2)
            return

        # Cycle through views every 4 seconds: 0=print prompt, 1=prediction, 2=caricature
        cycle_time = 4000
        has_caricature = (self._last_result.print_data and
                         self._last_result.print_data.get("caricature"))
        num_views = 3 if has_caricature else 2
        view = int(self._time_in_state / cycle_time) % num_views

        if view == 0:
            # Print prompt view
            draw_centered_text(buffer, "СОХРАНИТЬ", 25, (150, 180, 200), scale=2)
            draw_centered_text(buffer, "НА ПАМЯТЬ?", 50, (150, 180, 200), scale=2)
            draw_centered_text(buffer, "ПЕЧАТЬ", 80, (255, 255, 100), scale=2)

            # Print options at bottom
            if self._last_result.should_print:
                draw_centered_text(buffer, "< НЕТ  > ДА", 110, (150, 200, 150), scale=1)
            else:
                draw_centered_text(buffer, "НАЖМИ КНОПКУ", 110, (150, 150, 150), scale=1)

        elif view == 1:
            # Prediction text view with auto-scroll for long text
            text = self._last_result.display_text or "..."
            font = load_font("cyrillic")

            # Title
            draw_centered_text(buffer, "ПРОРОЧЕСТВО", 3, (255, 200, 100), scale=1)

            # Wrap text to fit screen width
            lines = smart_wrap_text(text, 120, font, scale=1)
            max_visible = 8  # Lines that fit on screen (with title and hint)

            # Calculate scroll offset for long text
            if len(lines) > max_visible:
                # Scroll through text over the 4-second view cycle
                time_in_view = self._time_in_state % cycle_time
                scroll_duration = cycle_time - 500  # Leave 500ms at start to read beginning
                if time_in_view > 500:
                    scroll_progress = (time_in_view - 500) / scroll_duration
                    max_scroll = len(lines) - max_visible
                    scroll_offset = int(scroll_progress * max_scroll)
                else:
                    scroll_offset = 0
            else:
                scroll_offset = 0

            # Render visible lines
            y = 16
            for i in range(max_visible):
                line_idx = scroll_offset + i
                if line_idx < len(lines):
                    draw_centered_text(buffer, lines[line_idx], y, (255, 255, 255), scale=1)
                y += 11

            # Scroll indicator if text is long
            if len(lines) > max_visible:
                indicator = "▼" if scroll_offset < len(lines) - max_visible else "●"
                draw_centered_text(buffer, indicator, 105, (100, 100, 120), scale=1)

            # Print hint at bottom
            if self._last_result.should_print:
                draw_centered_text(buffer, "< НЕТ  > ДА", 118, (100, 150, 100), scale=1)

        elif view == 2 and has_caricature:
            # Caricature view
            try:
                from PIL import Image
                import numpy as np

                caricature_data = self._last_result.print_data.get("caricature")
                img = Image.open(BytesIO(caricature_data))
                img = img.convert("RGB")
                img = img.resize((100, 100), Image.Resampling.NEAREST)

                # Center on screen
                img_array = np.array(img)
                x_offset = (128 - 100) // 2
                y_offset = 5
                buffer[y_offset:y_offset+100, x_offset:x_offset+100] = img_array

                # Title at bottom
                draw_centered_text(buffer, "ТВОЙ ШАРЖ", 110, (255, 200, 100), scale=1)
            except Exception:
                # Fallback to prediction
                draw_centered_text(buffer, "ШАРЖ", 50, (200, 200, 200), scale=2)

            # Print hint
            if self._last_result.should_print:
                draw_centered_text(buffer, "< НЕТ  > ДА", 118, (100, 150, 100), scale=1)

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

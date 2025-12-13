"""Mode manager for ARTIFACT - handles mode selection, transitions, and idle state."""

from typing import Dict, List, Optional, Type, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import logging
import random

from artifact.core.events import EventBus, Event, EventType
from artifact.core.state import StateMachine, State
from artifact.animation.engine import AnimationEngine
from artifact.animation.idle import create_idle_animation, IdleAnimationConfig
from artifact.graphics.renderer import Renderer
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase

logger = logging.getLogger(__name__)


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

        # Idle animation
        idle_config = IdleAnimationConfig(
            style=theme,
            main_width=128,
            main_height=128,
            ticker_width=48,
            ticker_height=8
        )
        self._idle_animation = create_idle_animation(theme, idle_config)

        # Admin menu detection
        self._key_buffer: List[str] = []
        self._admin_mode_enabled = False

        # Timing
        self._time_in_state: float = 0.0
        self._idle_timeout: float = 30000  # Return to idle after 30s of inactivity
        self._last_input_time: float = 0.0

        # Callbacks
        self._on_mode_complete: Optional[Callable[[ModeResult], None]] = None

        # Register event handlers
        self._setup_event_handlers()

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

        if self._state == ManagerState.MODE_SELECT:
            self._select_previous_mode()
        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            self._current_mode.handle_input(event)
        elif self._state == ManagerState.RESULT:
            # Left = No print, exit
            self._return_to_idle()

    def _on_arcade_right(self, event: Event) -> None:
        """Handle right arcade button."""
        self._last_input_time = self._time_in_state

        if self._state == ManagerState.MODE_SELECT:
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

    def _select_previous_mode(self) -> None:
        """Select previous mode in carousel."""
        if self._mode_order:
            self._selected_index = (self._selected_index - 1) % len(self._mode_order)

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
        # Actual printing handled by print system
        # For now, simulate with timeout
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
            self._render_start_prompt(buffer)

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
                return mode.display_name[:16].center(16)
            return "ВЫБЕРИ РЕЖИМ".center(16)

        elif self._state == ManagerState.MODE_ACTIVE and self._current_mode:
            return self._current_mode.get_lcd_text()

        elif self._state == ManagerState.RESULT:
            return "ПЕЧАТЬ? L=НЕТ R=ДА"[:16]

        elif self._state == ManagerState.PRINTING:
            return "ПЕЧАТАЮ...".center(16)

        elif self._state == ManagerState.ADMIN_MENU:
            return "АДМИН МЕНЮ".center(16)

        return "АРТЕФАКТ".center(16)

    def _render_start_prompt(self, buffer) -> None:
        """Render 'press start' prompt with arrow."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.primitives import draw_rect

        font = load_font("cyrillic")

        # Blinking "НАЖМИ СТАРТ" at bottom
        if int(self._time_in_state / 500) % 2 == 0:
            text = "НАЖМИ"
            text_w, text_h = font.measure_text(text)
            x = (128 - text_w * 2) // 2
            draw_text_bitmap(buffer, text, x, 110, (255, 200, 0), font, scale=2)

        # Arrow pointing down (to button) - wide at top, point at bottom
        base_y = 120
        bounce = int((self._time_in_state / 200) % 5)
        cx = 64
        # Down arrow: starts wide, ends in point
        for i in range(5):
            width = (5 - i) * 2 - 1  # 9, 7, 5, 3, 1
            x_start = cx - width // 2
            draw_rect(buffer, x_start, base_y + bounce + i, width, 1, (255, 100, 100))

    def _render_mode_select(self, buffer) -> None:
        """Render mode selection carousel."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.primitives import fill, draw_rect, draw_circle

        fill(buffer, (20, 20, 30))
        font = load_font("cyrillic")

        # Title - use scale=1 to fit "ВЫБЕРИ РЕЖИМ" on 128px display
        draw_text_bitmap(buffer, "ВЫБЕРИ РЕЖИМ", 25, 10, (200, 200, 200), font, scale=1)

        # Current mode
        mode = self.get_selected_mode()
        if mode:
            # Mode icon (large)
            draw_text_bitmap(buffer, mode.icon, 55, 40, (255, 200, 0), font, scale=4)

            # Mode name
            name = mode.display_name
            name_w, _ = font.measure_text(name)
            x = (128 - name_w * 2) // 2
            draw_text_bitmap(buffer, name, x, 85, (255, 255, 255), font, scale=2)

        # Left/right arrows
        if len(self._mode_order) > 1:
            # Left arrow
            draw_text_bitmap(buffer, "<", 5, 55, (100, 150, 255), font, scale=3)
            # Right arrow
            draw_text_bitmap(buffer, ">", 110, 55, (100, 150, 255), font, scale=3)

        # Dots indicator
        num_modes = len(self._mode_order)
        if num_modes > 1:
            dot_spacing = 10
            start_x = 64 - (num_modes - 1) * dot_spacing // 2
            for i in range(num_modes):
                x = start_x + i * dot_spacing
                color = (255, 200, 0) if i == self._selected_index else (80, 80, 80)
                draw_circle(buffer, x, 105, 3, color)

        # Confirm prompt
        draw_text_bitmap(buffer, "НАЖМИ СТАРТ", 25, 115, (150, 150, 150), font, scale=1)

    def _render_mode_select_ticker(self, buffer) -> None:
        """Render ticker during mode select."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.fonts import load_font, draw_text_bitmap

        clear(buffer)
        font = load_font("cyrillic")

        mode = self.get_selected_mode()
        if mode:
            # Scrolling description
            desc = mode.display_name
            scroll = int(self._time_in_state / 100) % (len(desc) * 4 + 48)
            draw_text_bitmap(buffer, desc, 48 - scroll, 1, (255, 200, 0), font, scale=1)

    def _render_result(self, buffer) -> None:
        """Render result screen."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.primitives import fill

        fill(buffer, (20, 30, 40))
        font = load_font("cyrillic")

        if self._last_result:
            # Result text
            text = self._last_result.display_text[:50] or "ГОТОВО!"
            lines = [text[i:i+15] for i in range(0, len(text), 15)]

            y = 30
            for line in lines[:4]:
                line_w, _ = font.measure_text(line)
                x = (128 - line_w * 2) // 2
                draw_text_bitmap(buffer, line, x, y, (255, 255, 200), font, scale=2)
                y += 20

            # Print prompt
            if self._last_result.should_print:
                draw_text_bitmap(buffer, "ПЕЧАТЬ?", 35, 90, (200, 200, 200), font, scale=2)
                draw_text_bitmap(buffer, "L=НЕТ  R=ДА", 25, 110, (150, 200, 150), font, scale=1)
            else:
                draw_text_bitmap(buffer, "НАЖМИ КНОПКУ", 15, 105, (150, 150, 150), font, scale=1)

    def _render_printing(self, buffer) -> None:
        """Render printing progress."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.primitives import fill, draw_rect

        fill(buffer, (30, 30, 30))
        font = load_font("cyrillic")

        draw_text_bitmap(buffer, "ПЕЧАТАЮ", 25, 40, (255, 255, 255), font, scale=2)

        # Progress bar
        progress = min(1.0, self._time_in_state / 10000)
        bar_width = int(100 * progress)
        draw_rect(buffer, 14, 70, 100, 10, (50, 50, 50))
        draw_rect(buffer, 14, 70, bar_width, 10, (0, 200, 100))

        # Dots animation
        dots = "." * (int(self._time_in_state / 300) % 4)
        draw_text_bitmap(buffer, dots, 75, 90, (200, 200, 200), font, scale=2)

    def _render_admin_menu(self, buffer) -> None:
        """Render admin menu."""
        from artifact.graphics.fonts import load_font, draw_text_bitmap
        from artifact.graphics.primitives import fill

        fill(buffer, (40, 20, 20))
        font = load_font("cyrillic")

        draw_text_bitmap(buffer, "ADMIN", 45, 10, (255, 100, 100), font, scale=2)

        # Menu options
        options = [
            "1. Theme",
            "2. Stats",
            "3. Test",
            "* Exit"
        ]
        y = 40
        for opt in options:
            draw_text_bitmap(buffer, opt, 20, y, (200, 200, 200), font, scale=1)
            y += 15

    # Callbacks
    def set_on_mode_complete(self, callback: Callable[[ModeResult], None]) -> None:
        """Set callback for mode completion."""
        self._on_mode_complete = callback

"""Base class for all game modes in ARTIFACT."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

from artifact.core.events import EventBus, Event, EventType
from artifact.core.state import StateMachine, State
from artifact.animation.engine import AnimationEngine
from artifact.graphics.renderer import Renderer

logger = logging.getLogger(__name__)


class ModePhase(Enum):
    """Phases within a mode's lifecycle."""

    INTRO = auto()       # Entry animation
    ACTIVE = auto()      # Main interaction
    PROCESSING = auto()  # AI/computation
    RESULT = auto()      # Showing result
    OUTRO = auto()       # Exit animation


@dataclass
class ModeResult:
    """Result from a completed mode session."""

    mode_name: str
    success: bool = True
    data: Dict[str, Any] = field(default_factory=dict)
    display_text: str = ""
    ticker_text: str = ""
    lcd_text: str = ""
    should_print: bool = False
    print_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    skip_manager_result: bool = False  # If True, skip manager's result screen (mode handles its own)


@dataclass
class ModeContext:
    """Shared context passed to modes."""

    state_machine: StateMachine
    event_bus: EventBus
    renderer: Renderer
    animation_engine: AnimationEngine

    # Display dimensions
    main_width: int = 128
    main_height: int = 128
    ticker_width: int = 48
    ticker_height: int = 8

    # Theme/style
    theme: str = "mystical"

    # User data
    user_photo: Optional[bytes] = None
    user_answers: List[bool] = field(default_factory=list)


class BaseMode(ABC):
    """Abstract base class for all game modes.

    Each mode implements a complete interactive experience with:
    - Entry/exit animations
    - User input handling
    - Optional AI processing
    - Result display
    - Optional printing

    Lifecycle:
        1. on_enter() - Initialize mode, start intro animation
        2. on_update(delta) - Per-frame logic while active
        3. on_input(event) - Handle user input
        4. on_exit() - Cleanup, prepare result
    """

    # Mode metadata (override in subclasses)
    name: str = "base"
    display_name: str = "Base Mode"
    description: str = "Base mode class"
    icon: str = "?"
    style: str = "mystical"  # mystical, arcade, modern
    requires_camera: bool = False
    requires_ai: bool = False
    estimated_duration: int = 30  # seconds

    def __init__(self, context: ModeContext):
        self.context = context
        self.phase = ModePhase.INTRO
        self._active = False
        self._result: Optional[ModeResult] = None
        self._time_in_mode: float = 0.0
        self._time_in_phase: float = 0.0

        # Callbacks
        self._on_complete: Optional[Callable[[ModeResult], None]] = None
        self._on_phase_change: Optional[Callable[[ModePhase], None]] = None

        logger.debug(f"Mode created: {self.name}")

    @property
    def is_active(self) -> bool:
        """Check if mode is currently active."""
        return self._active

    @property
    def result(self) -> Optional[ModeResult]:
        """Get the mode result (available after completion)."""
        return self._result

    def set_on_complete(self, callback: Callable[[ModeResult], None]) -> None:
        """Set callback for when mode completes."""
        self._on_complete = callback

    def set_on_phase_change(self, callback: Callable[[ModePhase], None]) -> None:
        """Set callback for phase changes."""
        self._on_phase_change = callback

    # Lifecycle methods
    def enter(self) -> None:
        """Called when mode becomes active."""
        self._active = True
        self._time_in_mode = 0.0
        self._time_in_phase = 0.0
        self.phase = ModePhase.INTRO
        self._result = None

        logger.info(f"Entering mode: {self.name}")
        self.on_enter()

    def exit(self) -> ModeResult:
        """Called when mode is deactivated."""
        logger.info(f"Exiting mode: {self.name}")
        self.on_exit()
        self._active = False

        if self._result is None:
            self._result = ModeResult(
                mode_name=self.name,
                success=False,
                error="Mode exited without result"
            )

        return self._result

    def update(self, delta_ms: float) -> None:
        """Update mode state each frame.

        Args:
            delta_ms: Time since last update in milliseconds
        """
        if not self._active:
            return

        self._time_in_mode += delta_ms
        self._time_in_phase += delta_ms

        self.on_update(delta_ms)

    def handle_input(self, event: Event) -> bool:
        """Process input event.

        Args:
            event: Input event to process

        Returns:
            True if event was handled
        """
        if not self._active:
            return False

        return self.on_input(event)

    def change_phase(self, new_phase: ModePhase) -> None:
        """Transition to a new phase."""
        old_phase = self.phase
        self.phase = new_phase
        self._time_in_phase = 0.0

        logger.debug(f"Mode {self.name}: {old_phase.name} -> {new_phase.name}")

        if self._on_phase_change:
            self._on_phase_change(new_phase)

        self.on_phase_changed(old_phase, new_phase)

    def complete(self, result: ModeResult) -> None:
        """Mark mode as complete with result."""
        self._result = result
        self.change_phase(ModePhase.OUTRO)

        if self._on_complete:
            self._on_complete(result)

    # Abstract methods (must be implemented by subclasses)
    @abstractmethod
    def on_enter(self) -> None:
        """Initialize mode state and start intro animation."""
        pass

    @abstractmethod
    def on_update(self, delta_ms: float) -> None:
        """Per-frame update logic."""
        pass

    @abstractmethod
    def on_input(self, event: Event) -> bool:
        """Handle user input. Return True if handled."""
        pass

    @abstractmethod
    def on_exit(self) -> None:
        """Cleanup mode state."""
        pass

    # Optional overrides
    def on_phase_changed(self, old_phase: ModePhase, new_phase: ModePhase) -> None:
        """Called when phase changes. Override for custom behavior."""
        pass

    def render_main(self, buffer) -> None:
        """Render to main display. Override for custom rendering."""
        pass

    def render_ticker(self, buffer) -> None:
        """Render to ticker display. Override for custom rendering."""
        pass

    def get_lcd_text(self) -> str:
        """Get current LCD text. Override for dynamic text."""
        return self.display_name[:16]

    # Utility methods
    def play_animation(self, name: str, **kwargs) -> str:
        """Play an animation through the engine."""
        return self.context.animation_engine.play(
            name=name,
            group=f"mode_{self.name}",
            **kwargs
        )

    def stop_animations(self) -> None:
        """Stop all animations for this mode."""
        self.context.animation_engine.stop_group(f"mode_{self.name}")

    def emit_event(self, event_type: EventType, data: Dict = None) -> None:
        """Emit an event through the event bus."""
        self.context.event_bus.emit(Event(
            event_type=event_type,
            data=data or {},
            source=f"mode_{self.name}"
        ))

    def transition_to_state(self, state: State) -> bool:
        """Request state machine transition."""
        return self.context.state_machine.transition_to(state)

    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Get mode metadata as dictionary."""
        return {
            "name": cls.name,
            "display_name": cls.display_name,
            "description": cls.description,
            "icon": cls.icon,
            "style": cls.style,
            "requires_camera": cls.requires_camera,
            "requires_ai": cls.requires_ai,
            "estimated_duration": cls.estimated_duration,
        }

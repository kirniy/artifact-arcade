"""
State machine for ARTIFACT application flow.

States:
    IDLE: Waiting for user interaction (idle animations playing)
    MODE_SELECT: User is selecting a mode
    MODE_ACTIVE: A mode is currently running
    PROCESSING: AI or other processing in progress
    RESULT: Displaying result to user
    PRINTING: Printing receipt
    ERROR: Error state with recovery options
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Callable, Any
import logging

logger = logging.getLogger(__name__)


class State(Enum):
    """Application states."""
    IDLE = auto()
    MODE_SELECT = auto()
    MODE_ACTIVE = auto()
    PROCESSING = auto()
    RESULT = auto()
    PRINTING = auto()
    ERROR = auto()


@dataclass
class StateTransition:
    """Defines a valid state transition."""
    from_state: State
    to_state: State
    condition: Callable[[], bool] | None = None
    on_transition: Callable[[], None] | None = None


@dataclass
class StateContext:
    """Context data passed between states."""
    current_mode: str | None = None
    mode_data: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None
    result_data: dict[str, Any] = field(default_factory=dict)


class StateMachine:
    """
    Manages application state and transitions.

    The state machine controls the flow of the application,
    ensuring valid transitions and notifying listeners of changes.
    """

    # Valid state transitions
    VALID_TRANSITIONS: list[tuple[State, State]] = [
        # From IDLE
        (State.IDLE, State.MODE_SELECT),
        (State.IDLE, State.MODE_ACTIVE),  # Direct mode entry
        (State.IDLE, State.ERROR),

        # From MODE_SELECT
        (State.MODE_SELECT, State.IDLE),
        (State.MODE_SELECT, State.MODE_ACTIVE),
        (State.MODE_SELECT, State.ERROR),

        # From MODE_ACTIVE
        (State.MODE_ACTIVE, State.PROCESSING),
        (State.MODE_ACTIVE, State.RESULT),
        (State.MODE_ACTIVE, State.IDLE),  # Cancel/timeout
        (State.MODE_ACTIVE, State.ERROR),

        # From PROCESSING
        (State.PROCESSING, State.RESULT),
        (State.PROCESSING, State.ERROR),
        (State.PROCESSING, State.IDLE),  # Cancel

        # From RESULT
        (State.RESULT, State.PRINTING),
        (State.RESULT, State.IDLE),
        (State.RESULT, State.MODE_ACTIVE),  # Play again
        (State.RESULT, State.ERROR),

        # From PRINTING
        (State.PRINTING, State.IDLE),
        (State.PRINTING, State.RESULT),  # Reprint
        (State.PRINTING, State.ERROR),

        # From ERROR
        (State.ERROR, State.IDLE),  # Recovery
    ]

    def __init__(self, initial_state: State = State.IDLE) -> None:
        self._state = initial_state
        self._context = StateContext()
        self._listeners: list[Callable[[State, State, StateContext], None]] = []
        self._valid_transitions = set(self.VALID_TRANSITIONS)
        logger.info(f"StateMachine initialized with state: {initial_state.name}")

    @property
    def state(self) -> State:
        """Get current state."""
        return self._state

    @property
    def context(self) -> StateContext:
        """Get current context."""
        return self._context

    def can_transition(self, to_state: State) -> bool:
        """Check if transition to given state is valid."""
        return (self._state, to_state) in self._valid_transitions

    def transition(self, to_state: State, **context_updates: Any) -> bool:
        """
        Attempt to transition to a new state.

        Args:
            to_state: Target state
            **context_updates: Updates to apply to context

        Returns:
            True if transition successful, False otherwise
        """
        if not self.can_transition(to_state):
            logger.warning(
                f"Invalid transition: {self._state.name} -> {to_state.name}"
            )
            return False

        old_state = self._state
        self._state = to_state

        # Update context
        for key, value in context_updates.items():
            if key == "mode_data":
                self._context.mode_data.update(value)
            elif key == "result_data":
                self._context.result_data.update(value)
            elif hasattr(self._context, key):
                setattr(self._context, key, value)

        logger.info(f"State transition: {old_state.name} -> {to_state.name}")

        # Notify listeners
        for listener in self._listeners:
            try:
                listener(old_state, to_state, self._context)
            except Exception as e:
                logger.error(f"Error in state listener: {e}")

        return True

    def add_listener(
        self,
        callback: Callable[[State, State, StateContext], None]
    ) -> None:
        """Add a state change listener."""
        self._listeners.append(callback)

    def remove_listener(
        self,
        callback: Callable[[State, State, StateContext], None]
    ) -> None:
        """Remove a state change listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def reset(self) -> None:
        """Reset state machine to initial state."""
        old_state = self._state
        self._state = State.IDLE
        self._context = StateContext()

        for listener in self._listeners:
            try:
                listener(old_state, State.IDLE, self._context)
            except Exception as e:
                logger.error(f"Error in state listener during reset: {e}")

        logger.info("StateMachine reset to IDLE")

    def enter_error(self, message: str) -> bool:
        """Convenience method to enter error state."""
        return self.transition(State.ERROR, error_message=message)

    def recover_from_error(self) -> bool:
        """Attempt to recover from error state."""
        if self._state == State.ERROR:
            self._context.error_message = None
            return self.transition(State.IDLE)
        return False

"""
Event bus system for ARTIFACT.

Provides pub/sub messaging between components with async support.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from enum import Enum, auto
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Built-in event types."""
    # Input events
    BUTTON_PRESS = auto()
    BUTTON_RELEASE = auto()
    KEYPAD_INPUT = auto()
    ARCADE_LEFT = auto()
    ARCADE_RIGHT = auto()

    # State events
    STATE_CHANGED = auto()
    MODE_SELECTED = auto()
    MODE_STARTED = auto()
    MODE_ENDED = auto()

    # Display events
    ANIMATION_START = auto()
    ANIMATION_END = auto()
    DISPLAY_UPDATE = auto()

    # AI events
    AI_REQUEST_START = auto()
    AI_REQUEST_COMPLETE = auto()
    AI_REQUEST_ERROR = auto()

    # Camera events
    CAMERA_READY = auto()
    PHOTO_CAPTURED = auto()
    PHOTO_ERROR = auto()

    # Printer events
    PRINT_START = auto()
    PRINT_COMPLETE = auto()
    PRINT_ERROR = auto()

    # Audio events
    SOUND_PLAY = auto()
    SOUND_STOP = auto()

    # System events
    TICK = auto()  # Frame tick
    SHUTDOWN = auto()
    ERROR = auto()


@dataclass
class Event:
    """
    Event data container.

    Attributes:
        type: Event type (EventType enum or custom string)
        data: Event payload
        source: Component that emitted the event
        timestamp: When event was created
    """
    type: EventType | str
    data: dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time()
                             if asyncio.get_event_loop().is_running() else 0.0)

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            import time
            self.timestamp = time.time()


# Type aliases for handlers
SyncHandler = Callable[[Event], None]
AsyncHandler = Callable[[Event], Awaitable[None]]
Handler = SyncHandler | AsyncHandler


class EventBus:
    """
    Central event bus for component communication.

    Supports both synchronous and asynchronous handlers.
    Events can be emitted immediately or queued for batch processing.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType | str, list[Handler]] = defaultdict(list)
        self._global_handlers: list[Handler] = []
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._running = False
        self._event_history: list[Event] = []
        self._history_limit = 100

    def subscribe(
        self,
        event_type: EventType | str,
        handler: Handler
    ) -> Callable[[], None]:
        """
        Subscribe to an event type.

        Args:
            event_type: Type of event to listen for
            handler: Callback function (sync or async)

        Returns:
            Unsubscribe function
        """
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler subscribed to {event_type}")

        def unsubscribe() -> None:
            if handler in self._handlers[event_type]:
                self._handlers[event_type].remove(handler)
                logger.debug(f"Handler unsubscribed from {event_type}")

        return unsubscribe

    def subscribe_all(self, handler: Handler) -> Callable[[], None]:
        """
        Subscribe to all events.

        Args:
            handler: Callback function (sync or async)

        Returns:
            Unsubscribe function
        """
        self._global_handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._global_handlers:
                self._global_handlers.remove(handler)

        return unsubscribe

    def emit(self, event: Event) -> None:
        """
        Emit an event immediately (synchronous handlers only).

        For async handlers, use emit_async or queue_event.
        """
        self._add_to_history(event)
        self._dispatch_sync(event)

    async def emit_async(self, event: Event) -> None:
        """Emit an event and await all handlers (sync and async)."""
        self._add_to_history(event)
        await self._dispatch_async(event)

    def queue_event(self, event: Event) -> None:
        """Queue an event for later processing."""
        self._queue.put_nowait(event)

    async def process_queue(self) -> None:
        """Process all queued events."""
        while not self._queue.empty():
            event = await self._queue.get()
            await self._dispatch_async(event)
            self._queue.task_done()

    async def run(self) -> None:
        """Run the event loop, processing queued events."""
        self._running = True
        logger.info("EventBus started")

        while self._running:
            try:
                event = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=0.1
                )
                await self._dispatch_async(event)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing event: {e}")

    def stop(self) -> None:
        """Stop the event loop."""
        self._running = False
        logger.info("EventBus stopped")

    def _dispatch_sync(self, event: Event) -> None:
        """Dispatch event to synchronous handlers only."""
        handlers = self._handlers.get(event.type, []) + self._global_handlers

        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                continue  # Skip async handlers
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

    async def _dispatch_async(self, event: Event) -> None:
        """Dispatch event to all handlers (sync and async)."""
        handlers = self._handlers.get(event.type, []) + self._global_handlers

        tasks = []
        for handler in handlers:
            if asyncio.iscoroutinefunction(handler):
                tasks.append(asyncio.create_task(handler(event)))
            else:
                try:
                    handler(event)
                except Exception as e:
                    logger.error(f"Error in sync handler: {e}")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Error in async handler: {result}")

    def _add_to_history(self, event: Event) -> None:
        """Add event to history, maintaining limit."""
        self._event_history.append(event)
        if len(self._event_history) > self._history_limit:
            self._event_history.pop(0)

    def get_history(
        self,
        event_type: EventType | str | None = None,
        limit: int = 10
    ) -> list[Event]:
        """Get recent events from history."""
        history = self._event_history
        if event_type is not None:
            history = [e for e in history if e.type == event_type]
        return history[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()


# Convenience functions for creating common events
def button_press_event(source: str = "button") -> Event:
    """Create a button press event."""
    return Event(EventType.BUTTON_PRESS, source=source)


def keypad_event(key: str, source: str = "keypad") -> Event:
    """Create a keypad input event."""
    return Event(EventType.KEYPAD_INPUT, data={"key": key}, source=source)


def arcade_event(direction: str, source: str = "arcade") -> Event:
    """Create an arcade button event."""
    event_type = EventType.ARCADE_LEFT if direction == "left" else EventType.ARCADE_RIGHT
    return Event(event_type, source=source)


def tick_event(delta: float, frame: int) -> Event:
    """Create a frame tick event."""
    return Event(EventType.TICK, data={"delta": delta, "frame": frame})

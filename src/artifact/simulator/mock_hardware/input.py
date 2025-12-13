"""
Simulated input devices for the simulator.

These classes handle keyboard input mapping to virtual buttons and keypad.
"""

from typing import Callable

from ...hardware.base import InputDevice, KeypadInput


class SimulatedButton(InputDevice):
    """
    Simulates the USB big button.

    Press state is controlled by the simulator window
    based on keyboard input (SPACE key).
    """

    def __init__(self) -> None:
        self._pressed = False
        self._press_callbacks: list[Callable[[], None]] = []
        self._release_callbacks: list[Callable[[], None]] = []

    def is_pressed(self) -> bool:
        return self._pressed

    def on_press(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._press_callbacks.append(callback)

        def unsubscribe() -> None:
            if callback in self._press_callbacks:
                self._press_callbacks.remove(callback)

        return unsubscribe

    def on_release(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._release_callbacks.append(callback)

        def unsubscribe() -> None:
            if callback in self._release_callbacks:
                self._release_callbacks.remove(callback)

        return unsubscribe

    def _press(self) -> None:
        """Called by simulator when button is pressed."""
        if not self._pressed:
            self._pressed = True
            for callback in self._press_callbacks:
                try:
                    callback()
                except Exception:
                    pass

    def _release(self) -> None:
        """Called by simulator when button is released."""
        if self._pressed:
            self._pressed = False
            for callback in self._release_callbacks:
                try:
                    callback()
                except Exception:
                    pass


class SimulatedArcade(InputDevice):
    """
    Simulates an arcade button (left or right).

    Press state is controlled by arrow keys.
    """

    def __init__(self, direction: str = "left") -> None:
        self.direction = direction
        self._pressed = False
        self._press_callbacks: list[Callable[[], None]] = []
        self._release_callbacks: list[Callable[[], None]] = []

    def is_pressed(self) -> bool:
        return self._pressed

    def on_press(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._press_callbacks.append(callback)

        def unsubscribe() -> None:
            if callback in self._press_callbacks:
                self._press_callbacks.remove(callback)

        return unsubscribe

    def on_release(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._release_callbacks.append(callback)

        def unsubscribe() -> None:
            if callback in self._release_callbacks:
                self._release_callbacks.remove(callback)

        return unsubscribe

    def _press(self) -> None:
        if not self._pressed:
            self._pressed = True
            for callback in self._press_callbacks:
                try:
                    callback()
                except Exception:
                    pass

    def _release(self) -> None:
        if self._pressed:
            self._pressed = False
            for callback in self._release_callbacks:
                try:
                    callback()
                except Exception:
                    pass


class SimulatedKeypad(KeypadInput):
    """
    Simulates 3x4 matrix keypad.

    Keys are mapped from number keys 0-9 and * #.
    """

    # Keypad layout
    LAYOUT = [
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
        ["*", "0", "#"],
    ]

    VALID_KEYS = set("0123456789*#")

    def __init__(self) -> None:
        self._current_key: str | None = None
        self._last_key: str | None = None
        self._callbacks: list[Callable[[str], None]] = []

    def get_key(self) -> str | None:
        return self._current_key

    def get_last_key(self) -> str | None:
        """Get the last pressed key (for display purposes)."""
        return self._last_key

    def on_key(self, callback: Callable[[str], None]) -> Callable[[], None]:
        self._callbacks.append(callback)

        def unsubscribe() -> None:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

        return unsubscribe

    def _press(self, key: str) -> None:
        """Called by simulator when a key is pressed."""
        if key in self.VALID_KEYS:
            self._current_key = key
            self._last_key = key

            for callback in self._callbacks:
                try:
                    callback(key)
                except Exception:
                    pass

    def _release(self) -> None:
        """Called by simulator when key is released."""
        self._current_key = None

    def get_key_position(self, key: str) -> tuple[int, int] | None:
        """Get row, col position for a key."""
        for row_idx, row in enumerate(self.LAYOUT):
            for col_idx, k in enumerate(row):
                if k == key:
                    return (row_idx, col_idx)
        return None

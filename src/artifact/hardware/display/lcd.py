"""
I2C LCD display driver for ARTIFACT.

Controls a 16x2 character LCD via I2C (PCF8574 expander).
Uses GPIO 2 (SDA) and GPIO 3 (SCL) on the Raspberry Pi.
"""

import logging
from ..base import TextDisplay

logger = logging.getLogger(__name__)

# RPLCD import is deferred
_RPLCD = None


def _get_rplcd():
    """Lazy import RPLCD."""
    global _RPLCD
    if _RPLCD is None:
        try:
            from RPLCD.i2c import CharLCD
            _RPLCD = CharLCD
        except ImportError:
            logger.warning("RPLCD not available - using mock")
            _RPLCD = None
    return _RPLCD


class I2CLCDDisplay(TextDisplay):
    """
    I2C LCD display driver for 16x2 character display.

    Hardware configuration:
    - Interface: I2C via PCF8574 expander
    - Address: 0x27 (common default) or 0x3F
    - Bus: /dev/i2c-1 (GPIO 2=SDA, GPIO 3=SCL)
    - Size: 16 columns x 2 rows

    Usage:
        lcd = I2CLCDDisplay()
        lcd.init()

        lcd.write("Hello World!", row=0, col=0)
        lcd.write("ARTIFACT", row=1, col=4)
    """

    def __init__(
        self,
        cols: int = 16,
        rows: int = 2,
        i2c_address: int = 0x27,
        i2c_bus: int = 1
    ):
        self._cols = cols
        self._rows = rows
        self._i2c_address = i2c_address
        self._i2c_bus = i2c_bus
        self._lcd = None
        self._initialized = False
        # Buffer for tracking displayed content
        self._buffer = [[' ' for _ in range(cols)] for _ in range(rows)]

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    def init(self) -> bool:
        """
        Initialize the I2C LCD.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        CharLCD = _get_rplcd()
        if CharLCD is None:
            logger.error("RPLCD library not available")
            return False

        try:
            # Initialize LCD with PCF8574 I2C expander
            self._lcd = CharLCD(
                i2c_expander='PCF8574',
                address=self._i2c_address,
                port=self._i2c_bus,
                cols=self._cols,
                rows=self._rows,
                dotsize=8,
                charmap='A02',  # Standard character map
                auto_linebreaks=False
            )

            # Clear and set up
            self._lcd.clear()

            self._initialized = True
            logger.info(
                f"I2C LCD initialized: {self._cols}x{self._rows} "
                f"at address 0x{self._i2c_address:02X}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize I2C LCD: {e}")
            # Try alternate address
            if self._i2c_address == 0x27:
                logger.info("Trying alternate address 0x3F...")
                self._i2c_address = 0x3F
                return self.init()
            return False

    def write(self, text: str, row: int = 0, col: int = 0) -> None:
        """
        Write text at specified position.

        Args:
            text: Text to display (will be truncated to fit)
            row: Row number (0 or 1)
            col: Column number (0-15)
        """
        if not self._initialized or self._lcd is None:
            return

        # Clamp position
        row = max(0, min(row, self._rows - 1))
        col = max(0, min(col, self._cols - 1))

        # Truncate text to fit
        max_len = self._cols - col
        text = text[:max_len]

        try:
            self._lcd.cursor_pos = (row, col)
            self._lcd.write_string(text)

            # Update buffer
            for i, char in enumerate(text):
                if col + i < self._cols:
                    self._buffer[row][col + i] = char

        except Exception as e:
            logger.error(f"LCD write error: {e}")

    def clear(self) -> None:
        """Clear the display."""
        if not self._initialized or self._lcd is None:
            return

        try:
            self._lcd.clear()
            # Clear buffer
            self._buffer = [[' ' for _ in range(self._cols)] for _ in range(self._rows)]
        except Exception as e:
            logger.error(f"LCD clear error: {e}")

    def set_cursor(self, col: int, row: int) -> None:
        """Set cursor position."""
        if not self._initialized or self._lcd is None:
            return

        row = max(0, min(row, self._rows - 1))
        col = max(0, min(col, self._cols - 1))

        try:
            self._lcd.cursor_pos = (row, col)
        except Exception as e:
            logger.error(f"LCD cursor error: {e}")

    def set_backlight(self, on: bool) -> None:
        """
        Control LCD backlight.

        Args:
            on: True to enable backlight, False to disable
        """
        if not self._initialized or self._lcd is None:
            return

        try:
            self._lcd.backlight_enabled = on
        except Exception as e:
            logger.error(f"LCD backlight error: {e}")

    def create_char(self, location: int, pattern: list[int]) -> None:
        """
        Create a custom character.

        Args:
            location: Character slot (0-7)
            pattern: 8-byte pattern defining the character
        """
        if not self._initialized or self._lcd is None:
            return

        if not 0 <= location <= 7:
            return
        if len(pattern) != 8:
            return

        try:
            self._lcd.create_char(location, pattern)
        except Exception as e:
            logger.error(f"LCD create_char error: {e}")

    def get_buffer(self) -> list[list[str]]:
        """Get copy of current display buffer."""
        return [row[:] for row in self._buffer]

    def cleanup(self) -> None:
        """Clean up LCD resources."""
        if self._initialized and self._lcd:
            try:
                self._lcd.clear()
                self._lcd.close()
            except Exception:
                pass
            self._initialized = False
            logger.info("I2C LCD cleaned up")

    def __del__(self):
        self.cleanup()


class I2CLCDDisplayMock(TextDisplay):
    """
    Mock I2C LCD display for testing without hardware.

    Provides the same interface but just stores values in a buffer.
    """

    def __init__(self, cols: int = 16, rows: int = 2):
        self._cols = cols
        self._rows = rows
        self._buffer = [[' ' for _ in range(cols)] for _ in range(rows)]
        self._cursor_row = 0
        self._cursor_col = 0
        self._backlight = True
        logger.info(f"I2C LCD mock initialized: {cols}x{rows}")

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    def init(self) -> bool:
        return True

    def write(self, text: str, row: int = 0, col: int = 0) -> None:
        row = max(0, min(row, self._rows - 1))
        col = max(0, min(col, self._cols - 1))
        max_len = self._cols - col
        text = text[:max_len]

        for i, char in enumerate(text):
            if col + i < self._cols:
                self._buffer[row][col + i] = char

    def clear(self) -> None:
        self._buffer = [[' ' for _ in range(self._cols)] for _ in range(self._rows)]
        self._cursor_row = 0
        self._cursor_col = 0

    def set_cursor(self, col: int, row: int) -> None:
        self._cursor_row = max(0, min(row, self._rows - 1))
        self._cursor_col = max(0, min(col, self._cols - 1))

    def set_backlight(self, on: bool) -> None:
        self._backlight = on

    def get_buffer(self) -> list[list[str]]:
        return [row[:] for row in self._buffer]

    def get_display_string(self) -> str:
        """Get display content as a formatted string."""
        lines = [''.join(row) for row in self._buffer]
        border = '+' + '-' * self._cols + '+'
        return f"{border}\n|{'|'.join('')}|\n{border}".replace(
            "||", f"|{lines[0]}|\n|{lines[1]}|"
        )

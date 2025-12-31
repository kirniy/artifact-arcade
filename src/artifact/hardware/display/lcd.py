"""
I2C LCD display driver for ARTIFACT.

Controls a 16x1 character LCD via I2C using direct smbus2 commands.
Uses GPIO 2 (SDA) and GPIO 3 (SCL) on the Raspberry Pi.

Uses Arduino LiquidCrystal_I2C compatible initialization sequence
for compatibility with STM32-based I2C adapters.
"""

import logging
import time
from ..base import TextDisplay

logger = logging.getLogger(__name__)

# smbus2 import is deferred
_smbus2 = None


def _get_smbus2():
    """Lazy import smbus2."""
    global _smbus2
    if _smbus2 is None:
        try:
            import smbus2
            _smbus2 = smbus2
        except ImportError:
            logger.warning("smbus2 not available - using mock")
            _smbus2 = None
    return _smbus2


# LCD Commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_FUNCTIONSET = 0x20
LCD_SETDDRAMADDR = 0x80

# Flags for display entry mode
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTDECREMENT = 0x00

# Flags for display on/off control
LCD_DISPLAYON = 0x04
LCD_CURSOROFF = 0x00
LCD_BLINKOFF = 0x00

# Flags for function set
LCD_4BITMODE = 0x00
LCD_1LINE = 0x00
LCD_5x8DOTS = 0x00

# PCF8574 pin mappings
EN = 0x04  # Enable bit
RS = 0x01  # Register select bit
LCD_BACKLIGHT = 0x08


class I2CLCDDisplay(TextDisplay):
    """
    I2C LCD display driver for 16x1 character display.

    Uses direct smbus2 I2C commands with Arduino LiquidCrystal_I2C
    compatible initialization for STM32-based adapters.

    Hardware configuration:
    - Interface: I2C via PCF8574/STM32 expander
    - Address: 0x27 (default)
    - Bus: /dev/i2c-1 (GPIO 2=SDA, GPIO 3=SCL)
    - Size: 16 columns x 1 row
    """

    def __init__(
        self,
        cols: int = 16,
        rows: int = 1,
        i2c_address: int = 0x27,
        i2c_bus: int = 1
    ):
        self._cols = cols
        self._rows = rows
        self._i2c_address = i2c_address
        self._i2c_bus = i2c_bus
        self._bus = None
        self._initialized = False
        self._backlight = LCD_BACKLIGHT
        # Buffer for tracking displayed content
        self._buffer = [[' ' for _ in range(cols)] for _ in range(rows)]
        # Track last displayed text to avoid redundant updates
        self._last_text: str = ""

    @property
    def cols(self) -> int:
        return self._cols

    @property
    def rows(self) -> int:
        return self._rows

    def _expander_write(self, data: int) -> None:
        """Write byte to I2C expander."""
        if self._bus:
            try:
                self._bus.write_byte(self._i2c_address, data | self._backlight)
            except Exception:
                pass

    def _pulse_enable(self, data: int) -> None:
        """Pulse the enable pin."""
        self._expander_write(data | EN)
        time.sleep(0.000001)  # 1us
        self._expander_write(data & ~EN)
        time.sleep(0.00005)  # 50us

    def _write_4bits(self, value: int) -> None:
        """Write 4 bits to LCD."""
        self._expander_write(value)
        self._pulse_enable(value)

    def _send(self, value: int, mode: int) -> None:
        """Send byte to LCD (command or data)."""
        high_nib = value & 0xF0
        low_nib = (value << 4) & 0xF0
        self._write_4bits(high_nib | mode)
        self._write_4bits(low_nib | mode)

    def _command(self, value: int) -> None:
        """Send command to LCD."""
        self._send(value, 0)

    def _write_char(self, value: int) -> None:
        """Write character to LCD."""
        self._send(value, RS)

    def init(self) -> bool:
        """
        Initialize the I2C LCD using Arduino-compatible sequence.

        Returns:
            True if initialization succeeded
        """
        if self._initialized:
            return True

        smbus2 = _get_smbus2()
        if smbus2 is None:
            logger.error("smbus2 library not available")
            return False

        try:
            self._bus = smbus2.SMBus(self._i2c_bus)

            # Arduino LiquidCrystal_I2C init sequence
            time.sleep(0.05)  # Wait 50ms after power up

            # Reset expander with backlight OFF initially
            self._backlight = 0
            self._expander_write(0)
            time.sleep(0.5)  # Shorter than Arduino's 1s but still substantial

            # Put into 4-bit mode (HD44780 datasheet figure 24)
            self._write_4bits(0x03 << 4)
            time.sleep(0.0045)  # 4.5ms
            self._write_4bits(0x03 << 4)
            time.sleep(0.0045)  # 4.5ms
            self._write_4bits(0x03 << 4)
            time.sleep(0.00015)  # 150us
            self._write_4bits(0x02 << 4)  # Set 4-bit mode

            # Function set: 4-bit, 1-line, 5x8 dots
            display_function = LCD_4BITMODE | LCD_1LINE | LCD_5x8DOTS
            self._command(LCD_FUNCTIONSET | display_function)

            # Display on, cursor off, blink off
            display_control = LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF
            self._command(LCD_DISPLAYCONTROL | display_control)

            # Clear display
            self._command(LCD_CLEARDISPLAY)
            time.sleep(0.002)

            # Entry mode set
            display_mode = LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT
            self._command(LCD_ENTRYMODESET | display_mode)

            # Home
            self._command(LCD_RETURNHOME)
            time.sleep(0.002)

            # Turn backlight ON
            self._backlight = LCD_BACKLIGHT
            self._expander_write(0)

            # Write initial text
            for c in "ARTIFACT":
                self._write_char(ord(c))
            self._last_text = "ARTIFACT".ljust(self._cols)

            self._initialized = True
            logger.info(
                f"I2C LCD initialized: {self._cols}x{self._rows} "
                f"at address 0x{self._i2c_address:02X}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize I2C LCD: {e}")
            return False

    def write(self, text: str, row: int = 0, col: int = 0) -> None:
        """
        Write text at specified position.

        Args:
            text: Text to display (will be truncated to fit)
            row: Row number (0 for 16x1)
            col: Column number (0-15)
        """
        if not self._initialized or self._bus is None:
            return

        # Clamp position
        row = max(0, min(row, self._rows - 1))
        col = max(0, min(col, self._cols - 1))

        # Truncate text to fit
        max_len = self._cols - col
        text = text[:max_len]

        try:
            # Set cursor position
            self._command(LCD_SETDDRAMADDR | col)

            # Write characters
            for c in text:
                self._write_char(ord(c))

            # Update buffer
            for i, char in enumerate(text):
                if col + i < self._cols:
                    self._buffer[row][col + i] = char

        except Exception as e:
            logger.error(f"LCD write error: {e}")

    def clear(self) -> None:
        """Clear the display."""
        if not self._initialized or self._bus is None:
            return

        try:
            self._command(LCD_CLEARDISPLAY)
            time.sleep(0.002)
            # Clear buffer
            self._buffer = [[' ' for _ in range(self._cols)] for _ in range(self._rows)]
        except Exception as e:
            logger.error(f"LCD clear error: {e}")

    def set_cursor(self, col: int, row: int) -> None:
        """Set cursor position."""
        if not self._initialized or self._bus is None:
            return

        row = max(0, min(row, self._rows - 1))
        col = max(0, min(col, self._cols - 1))

        try:
            self._command(LCD_SETDDRAMADDR | col)
        except Exception as e:
            logger.error(f"LCD cursor error: {e}")

    def set_backlight(self, on: bool) -> None:
        """
        Control LCD backlight.

        Args:
            on: True to enable backlight, False to disable
        """
        if not self._initialized or self._bus is None:
            return

        try:
            self._backlight = LCD_BACKLIGHT if on else 0
            self._expander_write(0)
        except Exception as e:
            logger.error(f"LCD backlight error: {e}")

    def create_char(self, location: int, pattern: list[int]) -> None:
        """
        Create a custom character.

        Args:
            location: Character slot (0-7)
            pattern: 8-byte pattern defining the character
        """
        if not self._initialized or self._bus is None:
            return

        if not 0 <= location <= 7:
            return
        if len(pattern) != 8:
            return

        try:
            # Set CGRAM address
            self._command(0x40 | (location << 3))
            # Write pattern
            for byte in pattern:
                self._write_char(byte)
        except Exception as e:
            logger.error(f"LCD create_char error: {e}")

    def set_text(self, text: str) -> None:
        """
        Set full display text (convenience method).

        Only updates the display if text has changed to avoid
        I2C bus flooding (LCD is slow and can't keep up with 60fps).

        Args:
            text: Text to display (truncated to 16 chars)
        """
        if not self._initialized or self._bus is None:
            return

        # Normalize text (truncate and pad to 16 chars)
        text = text[:self._cols].ljust(self._cols)

        # Skip update if text hasn't changed
        if text == self._last_text:
            return

        try:
            # Clear display
            self._command(LCD_CLEARDISPLAY)
            time.sleep(0.002)
            self._buffer = [[' ' for _ in range(self._cols)] for _ in range(self._rows)]

            # Home position
            self._command(LCD_RETURNHOME)
            time.sleep(0.002)

            # Write characters
            for c in text:
                self._write_char(ord(c))

            for i, char in enumerate(text):
                self._buffer[0][i] = char
            self._last_text = text
        except Exception as e:
            logger.error(f"LCD set_text error: {e}")

    def get_buffer(self) -> list[list[str]]:
        """Get copy of current display buffer."""
        return [row[:] for row in self._buffer]

    def cleanup(self) -> None:
        """Clean up LCD resources."""
        if self._initialized and self._bus:
            try:
                self._command(LCD_CLEARDISPLAY)
                self._bus.close()
            except Exception:
                pass
            self._initialized = False
            self._bus = None
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
        self._last_text: str = ""
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

    def set_text(self, text: str) -> None:
        """Set full display text (convenience method)."""
        text = text[:self._cols].ljust(self._cols)
        # Skip update if text hasn't changed (matches real LCD behavior)
        if text == self._last_text:
            return
        self._buffer = [[' ' for _ in range(self._cols)] for _ in range(self._rows)]
        for i, char in enumerate(text):
            self._buffer[0][i] = char
        self._last_text = text

    def get_buffer(self) -> list[list[str]]:
        return [row[:] for row in self._buffer]

    def get_display_string(self) -> str:
        """Get display content as a formatted string."""
        lines = [''.join(row) for row in self._buffer]
        border = '+' + '-' * self._cols + '+'
        return f"{border}\n|{'|'.join('')}|\n{border}".replace(
            "||", f"|{lines[0]}|\n|{lines[1]}|"
        )

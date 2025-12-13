"""EM5820 thermal printer driver for ARTIFACT.

Communicates with the EM5820 58mm thermal printer via UART (serial).
Supports ESC/POS commands for text and raster image printing.

Hardware specifications:
- Paper width: 58mm (~384 dots at 203 DPI)
- Interface: UART (9600 baud default, can be configured)
- Voltage: 5-9V DC
- Commands: ESC/POS compatible
"""

import logging
import asyncio
from typing import Optional

from artifact.hardware.base import Printer
from artifact.printing.receipt import Receipt

logger = logging.getLogger(__name__)


class EM5820Printer(Printer):
    """Driver for EM5820 thermal receipt printer.

    Uses UART serial communication on Raspberry Pi GPIO pins 14/15.
    Falls back to mock mode if hardware is unavailable.
    """

    # Default UART settings
    DEFAULT_BAUD = 9600
    DEFAULT_PORT = "/dev/serial0"  # Pi GPIO UART

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        baud: int = DEFAULT_BAUD,
        mock: bool = False,
    ):
        """Initialize the printer driver.

        Args:
            port: Serial port path
            baud: Baud rate
            mock: If True, simulate printing without hardware
        """
        super().__init__()
        self._port = port
        self._baud = baud
        self._mock = mock
        self._serial = None
        self._connected = False
        self._busy = False

    async def connect(self) -> bool:
        """Connect to the printer.

        Returns:
            True if connection successful
        """
        if self._mock:
            logger.info("EM5820 printer in mock mode")
            self._connected = True
            return True

        try:
            import serial

            self._serial = serial.Serial(
                port=self._port,
                baudrate=self._baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=2.0,
            )

            self._connected = True
            logger.info(f"EM5820 printer connected on {self._port}")

            # Initialize printer
            await self._send_command(b'\x1b\x40')  # ESC @ - Initialize

            return True

        except ImportError:
            logger.warning("pyserial not installed, using mock mode")
            self._mock = True
            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to printer: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the printer."""
        if self._serial:
            self._serial.close()
            self._serial = None

        self._connected = False
        logger.info("EM5820 printer disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if printer is connected."""
        return self._connected

    @property
    def is_busy(self) -> bool:
        """Check if printer is currently printing."""
        return self._busy

    async def print_receipt(self, receipt: Receipt) -> bool:
        """Print a receipt.

        Args:
            receipt: Receipt object to print

        Returns:
            True if printing successful
        """
        if not self._connected:
            logger.error("Printer not connected")
            return False

        if self._busy:
            logger.warning("Printer is busy")
            return False

        self._busy = True

        try:
            if self._mock:
                # Simulate printing delay
                logger.info("=== MOCK PRINT ===")
                print(receipt.preview)
                logger.info("==================")
                await asyncio.sleep(2.0)  # Simulate print time
            else:
                # Send raw commands to printer
                await self._send_command(receipt.raw_commands)

                # Wait for printing to complete
                await self._wait_for_ready()

            logger.info(f"Receipt printed: {receipt.mode_name}")
            return True

        except Exception as e:
            logger.error(f"Print failed: {e}")
            return False

        finally:
            self._busy = False

    async def print_raw(self, data: bytes) -> bool:
        """Send raw ESC/POS commands to printer.

        Args:
            data: Raw command bytes

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        try:
            await self._send_command(data)
            return True
        except Exception as e:
            logger.error(f"Raw print failed: {e}")
            return False

    async def print_text(self, text: str) -> bool:
        """Print simple text with newline.

        Args:
            text: Text to print

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        try:
            # Encode as CP866 for Russian support
            data = text.encode('cp866', errors='replace') + b'\n'
            await self._send_command(data)
            return True
        except Exception as e:
            logger.error(f"Text print failed: {e}")
            return False

    async def feed_paper(self, lines: int = 3) -> bool:
        """Feed paper.

        Args:
            lines: Number of lines to feed

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        # ESC d n - Feed n lines
        await self._send_command(b'\x1b\x64' + bytes([lines]))
        return True

    async def cut_paper(self, partial: bool = True) -> bool:
        """Cut the paper.

        Args:
            partial: If True, partial cut; if False, full cut

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        # GS V m - Cut paper
        # m = 0: full cut, m = 1: partial cut
        cut_mode = b'\x01' if partial else b'\x00'
        await self._send_command(b'\x1d\x56' + cut_mode)
        return True

    async def self_test(self) -> bool:
        """Run printer self-test.

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        # Print test page
        await self._send_command(b'\x12\x54')  # DC2 T - Self test
        return True

    async def get_status(self) -> dict:
        """Get printer status.

        Returns:
            Status dictionary
        """
        return {
            "connected": self._connected,
            "busy": self._busy,
            "mock_mode": self._mock,
            "port": self._port,
            "baud": self._baud,
        }

    async def _send_command(self, data: bytes) -> None:
        """Send command data to printer.

        Args:
            data: Command bytes to send
        """
        if self._mock:
            logger.debug(f"Mock send: {len(data)} bytes")
            return

        if self._serial:
            # Send in chunks to avoid buffer overflow
            chunk_size = 256
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                self._serial.write(chunk)
                self._serial.flush()

                # Small delay between chunks
                await asyncio.sleep(0.01)

    async def _wait_for_ready(self, timeout: float = 30.0) -> bool:
        """Wait for printer to become ready.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if ready, False if timeout
        """
        if self._mock:
            return True

        # Simple delay-based waiting
        # Could be improved with status polling if printer supports it
        await asyncio.sleep(0.5)
        return True


class MockPrinter(EM5820Printer):
    """Mock printer for testing and simulator."""

    def __init__(self):
        super().__init__(mock=True)

    async def connect(self) -> bool:
        """Always succeeds in mock mode."""
        self._connected = True
        return True


def create_printer(mock: bool = False) -> EM5820Printer:
    """Factory function to create appropriate printer.

    Args:
        mock: Force mock mode

    Returns:
        Printer instance
    """
    if mock:
        return MockPrinter()

    # Try to detect if running on Pi with UART available
    try:
        import serial
        return EM5820Printer()
    except ImportError:
        logger.info("pyserial not available, using mock printer")
        return MockPrinter()

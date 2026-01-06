"""EM5820 thermal printer driver for ARTIFACT.

Communicates with the EM5820 58mm thermal printer via UART (serial) or USB.
Supports ESC/POS commands for text and raster image printing.

Hardware specifications:
- Paper width: 58mm (~384 dots at 203 DPI)
- Interface: UART (9600 baud default) or USB-serial
- Voltage: 5-9V DC (9V recommended for best quality)
- Commands: ESC/POS compatible

Supported connections:
- UART: /dev/serial0 (Raspberry Pi GPIO pins 14/15)
- USB-Serial: /dev/ttyUSB0, /dev/ttyACM0 (auto-detected)
- USB Printer: /dev/usb/lp0 (File/raw backend)

Override with env var: ARTIFACT_PRINTER_PORT=/dev/ttyUSB0
"""

import logging
import asyncio
import os
import glob
from typing import Optional, List

from artifact.hardware.base import Printer
from artifact.printing.receipt import Receipt

logger = logging.getLogger(__name__)


def auto_detect_printer_port() -> Optional[str]:
    """Auto-detect printer serial port.
    
    Checks in order:
    1. Environment variable ARTIFACT_PRINTER_PORT
    2. USB-serial devices (/dev/ttyUSB*, /dev/ttyACM*)
    3. Default UART (/dev/serial0)
    4. USB printer class (/dev/usb/lp*)
    
    Returns:
        Detected port path, or None if not found
    """
    # 1. Check environment override first
    env_port = os.environ.get("ARTIFACT_PRINTER_PORT")
    if env_port and os.path.exists(env_port):
        logger.info(f"Using printer port from env: {env_port}")
        return env_port
    
    # 2. Check USB-serial devices (most common for USB connection)
    usb_serial_ports = glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*")
    if usb_serial_ports:
        port = sorted(usb_serial_ports)[0]  # Use first one
        logger.info(f"Auto-detected USB-serial printer: {port}")
        return port
    
    # 3. Check default UART
    if os.path.exists("/dev/serial0"):
        logger.info("Using default UART: /dev/serial0")
        return "/dev/serial0"
    
    # 4. Check USB printer class device
    usb_printers = glob.glob("/dev/usb/lp*")
    if usb_printers:
        port = sorted(usb_printers)[0]
        logger.info(f"Auto-detected USB printer class: {port}")
        return port
    
    logger.warning("No printer port detected")
    return None


class EM5820Printer(Printer):
    """Driver for EM5820 thermal receipt printer.

    Uses UART serial or USB-serial communication.
    Falls back to mock mode if hardware is unavailable.
    """

    # Default UART settings
    DEFAULT_BAUD = 9600
    DEFAULT_PORT = "/dev/serial0"  # Pi GPIO UART

    def __init__(
        self,
        port: Optional[str] = None,
        baud: int = DEFAULT_BAUD,
        mock: bool = False,
    ):
        """Initialize the printer driver.

        Args:
            port: Serial port path (auto-detected if None)
            baud: Baud rate
            mock: If True, simulate printing without hardware
        """
        super().__init__()
        self._port = port or auto_detect_printer_port() or self.DEFAULT_PORT
        self._baud = baud
        self._mock = mock
        self._serial = None
        self._file_backend = None  # For /dev/usb/lp* devices
        self._connected = False
        self._busy = False
        self._is_usb_printer_class = self._port.startswith("/dev/usb/lp") if self._port else False

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
            if self._is_usb_printer_class:
                # USB printer class device - use file backend
                self._file_backend = open(self._port, "wb")
                self._connected = True
                logger.info(f"EM5820 printer connected (USB printer class) on {self._port}")

                # Initialize printer
                self._file_backend.write(b'\x1b\x40')  # ESC @ - Initialize
                self._file_backend.write(b'\x1b\x7b\x01')  # ESC { 1 - Upside-down mode
                self._file_backend.write(b'\x1b\x74\x11')  # ESC t 17 - Select CP866 (Russian)
                self._file_backend.flush()
            else:
                # Serial device (UART or USB-serial)
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
                logger.info(f"EM5820 printer connected (serial) on {self._port}")

                # Initialize printer
                await self._send_command(b'\x1b\x40')  # ESC @ - Initialize
                await self._send_command(b'\x1b\x7b\x01')  # ESC { 1 - Upside-down mode
                await self._send_command(b'\x1b\x74\x11')  # ESC t 17 - Select CP866 (Russian)

            return True

        except ImportError:
            logger.warning("pyserial not installed, using mock mode")
            self._mock = True
            self._connected = True
            return True

        except Exception as e:
            logger.error(f"Failed to connect to printer on {self._port}: {e}")
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from the printer."""
        if self._serial:
            self._serial.close()
            self._serial = None
        
        if self._file_backend:
            self._file_backend.close()
            self._file_backend = None

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

    # Abstract method implementations required by Printer base class
    def feed(self, lines: int = 1) -> None:
        """Feed paper by specified lines (sync wrapper for async feed_paper)."""
        # Run async version in sync context if needed
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.feed_paper(lines))
            else:
                loop.run_until_complete(self.feed_paper(lines))
        except RuntimeError:
            # No event loop, just log
            logger.debug(f"Feed {lines} lines (no event loop)")

    def cut(self) -> None:
        """Cut paper (sync wrapper for async cut_paper)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.cut_paper())
            else:
                loop.run_until_complete(self.cut_paper())
        except RuntimeError:
            logger.debug("Cut paper (no event loop)")

    def is_ready(self) -> bool:
        """Check if printer is ready."""
        return self._connected and not self._busy

    def print_image(self, image_data: bytes) -> None:
        """Print image data (will be dithered for thermal printing)."""
        if not self._connected:
            logger.warning("Printer not connected, cannot print image")
            return
        
        if self._mock:
            logger.info(f"Mock print image: {len(image_data)} bytes")
            return
        
        # For now, log that image printing is not yet implemented
        # Full implementation would convert image to ESC/POS raster format
        logger.warning("Image printing not yet implemented for EM5820")

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

        if self._file_backend:
            # USB printer class - write directly (offload blocking I/O to thread)
            await asyncio.to_thread(self._write_file_backend, data)
            await asyncio.sleep(0.01)
        elif self._serial:
            # Send in chunks to avoid buffer overflow (offload blocking I/O to thread)
            await asyncio.to_thread(self._write_serial_chunks, data)

    def _write_file_backend(self, data: bytes) -> None:
        """Blocking write to file backend (runs in thread pool)."""
        self._file_backend.write(data)
        self._file_backend.flush()

    def _write_serial_chunks(self, data: bytes) -> None:
        """Blocking write to serial port in chunks (runs in thread pool)."""
        chunk_size = 256
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            self._serial.write(chunk)
            self._serial.flush()

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

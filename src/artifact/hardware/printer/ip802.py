"""AIYIN IP-802 thermal label printer driver for ARTIFACT.

Communicates with the AIYIN IP-802 (QR-368C) 80mm thermal label printer via USB.
Uses TSPL (TSC Printer Language) protocol for label printing.

Hardware specifications:
- Max paper width: 80mm (~640 dots at 203 DPI)
- Label size: 58×100mm (user's configuration)
- Print width: 58mm (~464 dots at 203 DPI)
- Interface: USB (USB printer class device)
- Protocol: TSPL (NOT ESC/POS!)
- Gap detection: Automatic label gap sensing

Supported connections:
- Linux: /dev/usb/lp0, /dev/usb/lp1 (auto-detected)
- Mac: Direct USB via pyusb (no /dev/usb/lp* on macOS)

Override with env var: ARTIFACT_PRINTER_PORT=/dev/usb/lp0
"""

import logging
import asyncio
import os
import sys
import glob
from typing import Optional, Union

from artifact.hardware.base import Printer
from artifact.printing.receipt import Receipt

logger = logging.getLogger(__name__)

# USB identifiers for AIYIN IP-802 / IPRT LABELPrinter
USB_VENDOR_ID = 0x353D
USB_PRODUCT_ID = 0x1249

# Check if pyusb is available
try:
    import usb.core
    import usb.util
    PYUSB_AVAILABLE = True
except ImportError:
    PYUSB_AVAILABLE = False
    logger.debug("pyusb not available - USB printing on Mac requires: pip install pyusb")


class _PyUSBBackend:
    """PyUSB backend for direct USB communication on Mac/Linux.

    Used when /dev/usb/lp* devices are not available (macOS)
    or when direct USB control is preferred.
    """

    def __init__(self):
        self.dev = None
        self.ep_out = None
        self.ep_in = None
        self._connected = False

    def connect(self) -> bool:
        """Connect to the printer via USB."""
        if not PYUSB_AVAILABLE:
            logger.error("pyusb not installed - run: pip install pyusb")
            return False

        self.dev = usb.core.find(idVendor=USB_VENDOR_ID, idProduct=USB_PRODUCT_ID)
        if self.dev is None:
            logger.warning("USB label printer not found")
            return False

        logger.info(f"Found USB printer: {self.dev.manufacturer} - {self.dev.product}")

        # Detach kernel driver if necessary (Linux)
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
                logger.debug("Detached kernel driver")
        except Exception:
            pass  # May not have kernel driver on Mac

        # Set configuration
        try:
            self.dev.set_configuration()
        except Exception:
            pass  # May already be configured

        # Claim interface
        try:
            usb.util.claim_interface(self.dev, 0)
            logger.debug("USB interface claimed")
        except Exception as e:
            logger.debug(f"Interface claim note: {e}")

        # Find endpoints
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]  # First interface

        for ep in intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                self.ep_out = ep.bEndpointAddress
            else:
                self.ep_in = ep.bEndpointAddress

        logger.debug(f"USB OUT endpoint: 0x{self.ep_out:02x}")
        self._connected = True
        return True

    def write(self, data: bytes, timeout: int = 10000) -> int:
        """Write data to printer."""
        if not self.dev or not self.ep_out:
            raise RuntimeError("Printer not connected")
        return self.dev.write(self.ep_out, data, timeout=timeout)

    def flush(self) -> None:
        """Flush is a no-op for USB (writes are immediate)."""
        pass

    def close(self) -> None:
        """Release the USB interface."""
        if self.dev:
            try:
                usb.util.release_interface(self.dev, 0)
            except Exception:
                pass
            self.dev = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected


def auto_detect_label_printer() -> Optional[Union[str, dict]]:
    """Auto-detect USB label printer.

    Checks in order:
    1. Environment variable ARTIFACT_PRINTER_PORT
    2. USB printer class (/dev/usb/lp*) - Linux
    3. PyUSB direct detection - Mac/Linux fallback

    Returns:
        - str: Device path like "/dev/usb/lp0" (Linux file backend)
        - dict: {"backend": "pyusb"} (Mac/pyusb backend)
        - None: No printer found
    """
    # 1. Check environment override first
    env_port = os.environ.get("ARTIFACT_PRINTER_PORT")
    if env_port and os.path.exists(env_port):
        logger.info(f"Using printer port from env: {env_port}")
        return env_port

    # 2. Check USB printer class device (primary for Linux)
    usb_printers = glob.glob("/dev/usb/lp*")
    if usb_printers:
        port = sorted(usb_printers)[0]
        logger.info(f"Auto-detected USB label printer: {port}")
        return port

    # 3. Try pyusb (Mac or Linux without usblp module)
    if PYUSB_AVAILABLE:
        try:
            dev = usb.core.find(idVendor=USB_VENDOR_ID, idProduct=USB_PRODUCT_ID)
            if dev:
                logger.info(f"Auto-detected USB printer via pyusb: {dev.manufacturer} {dev.product}")
                return {"backend": "pyusb"}
        except Exception as e:
            logger.debug(f"PyUSB detection failed: {e}")

    logger.warning("No label printer detected")
    return None


class IP802Printer(Printer):
    """Driver for AIYIN IP-802 (QR-368C) thermal label printer.

    Uses TSPL (TSC Printer Language) protocol for communication.
    Supports both file backend (Linux /dev/usb/lp*) and pyusb (Mac).
    Falls back to mock mode if hardware is unavailable.

    Label specifications (user's config):
    - Label width: 58mm
    - Label height: 100mm
    - Print dots: ~464 horizontal (at 203 DPI)
    - Print dots: ~800 vertical (at 203 DPI)
    """

    # Label dimensions at 203 DPI
    LABEL_WIDTH_MM = 58
    LABEL_HEIGHT_MM = 100
    DPI = 203

    # Calculated pixel dimensions
    LABEL_WIDTH_PX = int(LABEL_WIDTH_MM * DPI / 25.4)  # ~464 pixels
    LABEL_HEIGHT_PX = int(LABEL_HEIGHT_MM * DPI / 25.4)  # ~800 pixels

    def __init__(
        self,
        port: Optional[Union[str, dict]] = None,
        mock: bool = False,
    ):
        """Initialize the label printer driver.

        Args:
            port: USB device path, {"backend": "pyusb"}, or None for auto-detect
            mock: If True, simulate printing without hardware
        """
        super().__init__()
        self._port_config = port if port is not None else auto_detect_label_printer()
        self._mock = mock
        self._file_backend = None
        self._pyusb_backend: Optional[_PyUSBBackend] = None
        self._connected = False
        self._busy = False

    async def connect(self) -> bool:
        """Connect to the printer.

        Returns:
            True if connection successful
        """
        if self._mock:
            logger.info("IP-802 label printer in mock mode")
            self._connected = True
            return True

        if not self._port_config:
            logger.warning("No printer port available, using mock mode")
            self._mock = True
            self._connected = True
            return True

        try:
            # Check if using pyusb backend
            if isinstance(self._port_config, dict) and self._port_config.get("backend") == "pyusb":
                # Use pyusb backend (Mac or Linux without usblp)
                self._pyusb_backend = _PyUSBBackend()
                if self._pyusb_backend.connect():
                    self._connected = True
                    logger.info("IP-802 label printer connected via pyusb (TSPL)")
                    return True
                else:
                    raise RuntimeError("PyUSB connection failed")
            else:
                # Use file backend (Linux /dev/usb/lp*)
                port_path = self._port_config if isinstance(self._port_config, str) else str(self._port_config)
                self._file_backend = open(port_path, "wb")
                self._connected = True
                logger.info(f"IP-802 label printer connected on {port_path} (TSPL)")
                return True

        except Exception as e:
            logger.error(f"Failed to connect to printer: {e}")
            logger.info("Falling back to mock mode")
            self._mock = True
            self._connected = True
            return True

    async def _init_printer(self) -> None:
        """Initialize printer - no-op for TSPL (commands include setup)."""
        # TSPL printers don't need initialization - each print job includes
        # SIZE, GAP, DIRECTION commands
        logger.debug("TSPL printer ready (no init needed)")

    async def disconnect(self) -> None:
        """Disconnect from the printer."""
        if self._file_backend:
            try:
                self._file_backend.close()
            except Exception:
                pass
            self._file_backend = None

        if self._pyusb_backend:
            self._pyusb_backend.close()
            self._pyusb_backend = None

        self._connected = False
        logger.info("IP-802 printer disconnected")

    @property
    def is_connected(self) -> bool:
        """Check if printer is connected."""
        return self._connected

    @property
    def is_busy(self) -> bool:
        """Check if printer is currently printing."""
        return self._busy

    @property
    def label_width_px(self) -> int:
        """Get label width in pixels."""
        return self.LABEL_WIDTH_PX

    @property
    def label_height_px(self) -> int:
        """Get label height in pixels."""
        return self.LABEL_HEIGHT_PX

    async def print_receipt(self, receipt: Receipt) -> bool:
        """Print a receipt/label.

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
                logger.info("=== MOCK LABEL PRINT ===")
                print(receipt.preview)
                logger.info("========================")
                await asyncio.sleep(2.0)
            else:
                # Send raw commands to printer with timeout
                try:
                    await asyncio.wait_for(
                        self._send_command(receipt.raw_commands),
                        timeout=15.0  # Labels may take longer
                    )
                    # Wait for printing to complete
                    await asyncio.wait_for(
                        self._wait_for_ready(),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    logger.error("Printer timeout - check paper/status")
                    return False

            logger.info(f"Label printed: {receipt.mode_name}")
            return True

        except Exception as e:
            logger.error(f"Print failed: {e}")
            return False

        finally:
            self._busy = False

    async def print_label_image(self, image_data: bytes) -> bool:
        """Print a full-label image.

        The image should be pre-sized to fit the label dimensions.
        Will be converted to 1-bit dithered format for thermal printing.

        Args:
            image_data: PNG/JPEG image bytes

        Returns:
            True if successful
        """
        if not self._connected:
            logger.error("Printer not connected")
            return False

        if self._busy:
            logger.warning("Printer is busy")
            return False

        self._busy = True

        try:
            from PIL import Image
            from io import BytesIO

            # Load and prepare image
            img = Image.open(BytesIO(image_data))

            # Resize to label dimensions
            img = img.resize((self.LABEL_WIDTH_PX, self.LABEL_HEIGHT_PX), Image.Resampling.LANCZOS)

            # Convert to 1-bit with Floyd-Steinberg dithering
            img = img.convert('L')  # Grayscale first
            img = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

            # Generate ESC/POS raster commands
            raster_data = self._image_to_raster(img)

            if self._mock:
                logger.info(f"Mock label image print: {len(raster_data)} bytes")
                await asyncio.sleep(2.0)
            else:
                await self._send_command(raster_data)
                # Feed to tear position
                await self._feed_to_tear()
                await self._wait_for_ready()

            logger.info("Label image printed successfully")
            return True

        except ImportError:
            logger.error("PIL not available for image printing")
            return False
        except Exception as e:
            logger.error(f"Label image print failed: {e}")
            return False
        finally:
            self._busy = False

    def _image_to_raster(self, img) -> bytes:
        """Convert PIL Image to ESC/POS raster commands.

        Uses GS v 0 (raster bit image) command for best compatibility.

        Args:
            img: PIL Image in 1-bit mode

        Returns:
            ESC/POS command bytes
        """
        width, height = img.size

        # Ensure width is multiple of 8
        if width % 8 != 0:
            from PIL import Image
            new_width = (width // 8 + 1) * 8
            new_img = Image.new('1', (new_width, height), 1)  # White background
            new_img.paste(img, (0, 0))
            img = new_img
            width = new_width

        bytes_per_line = width // 8

        # Build raster data
        raster_data = []

        for y in range(height):
            line_data = []
            for x_byte in range(bytes_per_line):
                byte_val = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < img.width:
                        pixel = img.getpixel((x, y))
                        if pixel == 0:  # Black pixel
                            byte_val |= (0x80 >> bit)
                line_data.append(byte_val)
            raster_data.extend(line_data)

        # Build command: GS v 0 m xL xH yL yH data
        # m = 0 (normal), xL xH = width in bytes, yL yH = height in dots
        commands = []
        commands.append(self.GS + b'v0')
        commands.append(b'\x00')  # m = normal
        commands.append(bytes([bytes_per_line & 0xFF, (bytes_per_line >> 8) & 0xFF]))
        commands.append(bytes([height & 0xFF, (height >> 8) & 0xFF]))
        commands.append(bytes(raster_data))

        return b''.join(commands)

    async def _feed_to_tear(self) -> None:
        """Feed paper to the tear position after printing."""
        # For label printers, advance to the gap between labels
        # ESC d n - Feed n lines
        await self._send_command(b'\x1b\x64\x03')  # Feed 3 lines

        # Small delay for paper movement
        await asyncio.sleep(0.1)

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
            # Encode as UTF-8 (most modern printers support it)
            data = text.encode('utf-8', errors='replace') + b'\n'
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
        await self._send_command(b'\x1b\x64' + bytes([min(lines, 255)]))
        return True

    async def feed_label(self) -> bool:
        """Advance to next label (past the gap).

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        # Feed enough to get past the label and gap
        # The IP-802 should auto-detect gaps, but we can manually advance
        await self._send_command(b'\x1b\x64\x10')  # Feed 16 lines
        return True

    # Abstract method implementations required by Printer base class
    def feed(self, lines: int = 1) -> None:
        """Feed paper by specified lines (sync wrapper)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.feed_paper(lines))
            else:
                loop.run_until_complete(self.feed_paper(lines))
        except RuntimeError:
            logger.debug(f"Feed {lines} lines (no event loop)")

    def cut(self) -> None:
        """Cut paper - label printers don't cut, they feed to gap."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.feed_label())
            else:
                loop.run_until_complete(self.feed_label())
        except RuntimeError:
            logger.debug("Feed to label gap (no event loop)")

    def is_ready(self) -> bool:
        """Check if printer is ready."""
        return self._connected and not self._busy

    def print_image(self, image_data: bytes) -> None:
        """Print image data (sync wrapper)."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.print_label_image(image_data))
            else:
                loop.run_until_complete(self.print_label_image(image_data))
        except RuntimeError:
            logger.warning("Cannot print image (no event loop)")

    async def self_test(self) -> bool:
        """Run printer self-test.

        For IP-802: Hold Advance button until "Dee, Dee Dee" to print test page.

        Returns:
            True if successful
        """
        if not self._connected:
            return False

        # Print a simple test pattern
        await self._send_command(b'\x1b\x40')  # Reset
        await self.print_text("=== IP-802 Test ===")
        await self.print_text("Label Printer OK")
        await self.print_text(f"Width: {self.LABEL_WIDTH_MM}mm")
        await self.print_text(f"Height: {self.LABEL_HEIGHT_MM}mm")
        await self.print_text("=" * 20)
        await self._feed_to_tear()
        return True

    async def get_status(self) -> dict:
        """Get printer status.

        Returns:
            Status dictionary
        """
        backend = "mock"
        if not self._mock:
            if self._pyusb_backend:
                backend = "pyusb"
            elif self._file_backend:
                backend = "file"

        return {
            "connected": self._connected,
            "busy": self._busy,
            "mock_mode": self._mock,
            "backend": backend,
            "protocol": "TSPL",
            "port_config": str(self._port_config),
            "model": "AIYIN IP-802",
            "label_width_mm": self.LABEL_WIDTH_MM,
            "label_height_mm": self.LABEL_HEIGHT_MM,
            "label_width_px": self.LABEL_WIDTH_PX,
            "label_height_px": self.LABEL_HEIGHT_PX,
        }

    async def _send_command(self, data: bytes) -> None:
        """Send command data to printer.

        Args:
            data: Command bytes to send
        """
        if self._mock:
            logger.debug(f"Mock send: {len(data)} bytes")
            return

        if self._pyusb_backend:
            # PyUSB backend - write via USB (offload to thread)
            await asyncio.to_thread(self._write_pyusb_backend, data)
            await asyncio.sleep(0.01)
        elif self._file_backend:
            # File backend (Linux /dev/usb/lp*) - write directly (offload to thread)
            await asyncio.to_thread(self._write_file_backend, data)
            await asyncio.sleep(0.01)

    def _write_file_backend(self, data: bytes) -> None:
        """Blocking write to file backend (runs in thread pool)."""
        self._file_backend.write(data)
        self._file_backend.flush()

    def _write_pyusb_backend(self, data: bytes) -> None:
        """Blocking write to pyusb backend (runs in thread pool)."""
        self._pyusb_backend.write(data)

    async def _wait_for_ready(self, timeout: float = 30.0) -> bool:
        """Wait for printer to become ready.

        Args:
            timeout: Maximum wait time in seconds

        Returns:
            True if ready, False if timeout
        """
        if self._mock:
            return True

        # Label printers need more time than receipt printers
        await asyncio.sleep(1.0)
        return True


class MockLabelPrinter(IP802Printer):
    """Mock label printer for testing and simulator."""

    def __init__(self):
        super().__init__(mock=True)

    async def connect(self) -> bool:
        """Always succeeds in mock mode."""
        self._connected = True
        return True


def create_label_printer(mock: bool = False) -> IP802Printer:
    """Factory function to create appropriate label printer.

    Args:
        mock: Force mock mode

    Returns:
        Printer instance
    """
    if mock:
        return MockLabelPrinter()

    # Try to detect if USB printer is available
    port = auto_detect_label_printer()
    if port:
        return IP802Printer(port=port)
    else:
        logger.info("No USB label printer found, using mock printer")
        return MockLabelPrinter()

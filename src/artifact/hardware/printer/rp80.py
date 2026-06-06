"""Rongta-compatible RP80 80mm USB receipt printer driver.

The new photobooth printer enumerates as a generic ESC/POS USB receipt
printer: VID/PID 0fe6:811e, product "USB Receipt Printer".
"""

from __future__ import annotations

import asyncio
import glob
import logging
import os
from typing import Optional, Union

from artifact.hardware.base import Printer

logger = logging.getLogger(__name__)

USB_VENDOR_ID = 0x0FE6
USB_PRODUCT_ID = 0x811E

try:
    import usb.core
    import usb.util

    PYUSB_AVAILABLE = True
except ImportError:
    PYUSB_AVAILABLE = False


class _RP80PyUSBBackend:
    def __init__(self) -> None:
        self.dev = None
        self.ep_out = None
        self.ep_in = None
        self._connected = False

    def connect(self) -> bool:
        if not PYUSB_AVAILABLE:
            logger.error("pyusb not installed - RP80 USB printing requires pyusb")
            return False

        self.dev = usb.core.find(idVendor=USB_VENDOR_ID, idProduct=USB_PRODUCT_ID)
        if self.dev is None:
            logger.warning("RP80 USB receipt printer not found")
            return False

        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
        except Exception:
            pass

        try:
            self.dev.set_configuration()
        except Exception:
            pass

        try:
            usb.util.claim_interface(self.dev, 0)
        except Exception as exc:
            logger.debug("RP80 interface claim note: %s", exc)

        intf = self.dev.get_active_configuration()[(0, 0)]
        for ep in intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                self.ep_out = ep.bEndpointAddress
            elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                self.ep_in = ep.bEndpointAddress

        if self.ep_out is None:
            logger.error("RP80 USB OUT endpoint not found")
            return False

        self._connected = True
        logger.info("RP80 connected via pyusb endpoint 0x%02x", self.ep_out)
        return True

    def write(self, data: bytes, timeout: int = 20000) -> int:
        if not self.dev or self.ep_out is None:
            raise RuntimeError("RP80 not connected")
        return self.dev.write(self.ep_out, data, timeout=timeout)

    def close(self) -> None:
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


def auto_detect_rp80_printer() -> Optional[Union[str, dict]]:
    """Find the RP80 printer using env override, Linux device, or pyusb."""
    env_port = os.environ.get("ARTIFACT_RP80_PRINTER_PORT") or os.environ.get("ARTIFACT_PRINTER_PORT")
    if env_port and os.path.exists(env_port):
        return env_port

    usb_printers = glob.glob("/dev/usb/lp*")
    if usb_printers:
        return sorted(usb_printers)[0]

    if PYUSB_AVAILABLE:
        try:
            dev = usb.core.find(idVendor=USB_VENDOR_ID, idProduct=USB_PRODUCT_ID)
            if dev:
                return {"backend": "pyusb"}
        except Exception as exc:
            logger.debug("RP80 pyusb detection failed: %s", exc)
    return None


class RP80ReceiptPrinter(Printer):
    """ESC/POS driver for the 80mm RP80 receipt printer with cutter."""

    PAPER_WIDTH_PX = 576

    def __init__(self, port: Optional[Union[str, dict]] = None, mock: bool = False) -> None:
        self._port_config = port if port is not None else auto_detect_rp80_printer()
        self._mock = mock
        self._file_backend_path: Optional[str] = None
        self._pyusb_backend: Optional[_RP80PyUSBBackend] = None
        self._connected = False
        self._busy = False

    async def connect(self) -> bool:
        if self._mock:
            self._connected = True
            logger.info("RP80 printer in mock mode")
            return True

        if not self._port_config:
            logger.warning("No RP80 printer found")
            return False

        try:
            if isinstance(self._port_config, dict) and self._port_config.get("backend") == "pyusb":
                backend = _RP80PyUSBBackend()
                if not backend.connect():
                    return False
                self._pyusb_backend = backend
            else:
                self._file_backend_path = str(self._port_config)
            self._connected = True
            await self._send_command(b"\x1b@")
            logger.info("RP80 receipt printer connected")
            return True
        except Exception as exc:
            logger.error("Failed to connect RP80 printer: %s", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        if self._pyusb_backend:
            self._pyusb_backend.close()
            self._pyusb_backend = None
        self._file_backend_path = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_busy(self) -> bool:
        return self._busy

    async def print_raw(self, data: bytes) -> bool:
        if not self._connected:
            return False
        if self._busy:
            logger.warning("RP80 is busy")
            return False
        self._busy = True
        try:
            await asyncio.wait_for(self._send_command(data), timeout=25.0)
            await asyncio.sleep(0.5)
            return True
        except Exception as exc:
            logger.error("RP80 raw print failed: %s", exc)
            return False
        finally:
            self._busy = False

    async def print_receipt(self, receipt) -> bool:
        return await self.print_raw(receipt.raw_commands)

    async def print_text_async(self, text: str) -> bool:
        return await self.print_raw(b"\x1b@" + text.encode("cp866", errors="replace") + b"\n\x1dV\x01")

    async def _send_command(self, data: bytes) -> None:
        if self._mock:
            logger.info("Mock RP80 send: %d bytes", len(data))
            return
        if self._pyusb_backend:
            await asyncio.to_thread(self._pyusb_backend.write, data)
        elif self._file_backend_path:
            await asyncio.to_thread(self._write_file_backend, data)

    def _write_file_backend(self, data: bytes) -> None:
        with open(self._file_backend_path, "wb") as handle:
            handle.write(data)
            handle.flush()

    async def get_status(self) -> dict:
        return {
            "connected": self._connected,
            "busy": self._busy,
            "mock_mode": self._mock,
            "backend": "pyusb" if self._pyusb_backend else "file" if self._file_backend_path else "none",
            "protocol": "ESC/POS",
            "model": "RP80 USB Receipt Printer",
            "paper_width_px": self.PAPER_WIDTH_PX,
        }

    def print_text(self, text: str, **options) -> None:
        asyncio.create_task(self.print_text_async(text))

    def print_image(self, image_data: bytes) -> None:
        from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator

        gen = PhotoboothRollReceiptGenerator()
        receipt = gen.generate_receipt("photobooth", {"caricature": image_data})
        asyncio.create_task(self.print_raw(receipt.raw_commands))

    def feed(self, lines: int = 1) -> None:
        asyncio.create_task(self._send_command(b"\x1bd" + bytes([min(lines, 255)])))

    def cut(self) -> None:
        asyncio.create_task(self._send_command(b"\x1dV\x01"))

    def is_ready(self) -> bool:
        return self._connected and not self._busy


class MockRP80ReceiptPrinter(RP80ReceiptPrinter):
    def __init__(self) -> None:
        super().__init__(mock=True)


def create_rp80_printer(mock: bool = False) -> RP80ReceiptPrinter:
    if mock:
        return MockRP80ReceiptPrinter()
    port = auto_detect_rp80_printer()
    if port:
        return RP80ReceiptPrinter(port=port)
    return MockRP80ReceiptPrinter()

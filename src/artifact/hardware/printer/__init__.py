"""Printer drivers for ARTIFACT.

Supports two printer types:
- EM5820: 58mm thermal receipt printer (continuous roll, UART/USB-serial)
- IP802: AIYIN IP-802 80mm thermal label printer (58x100mm labels, USB, TSPL protocol)
- RP80: 80mm ESC/POS USB receipt printer with cutter for photobooth prints

The IP802 is now the primary printer for ARTIFACT arcade.
Uses TSPL protocol (not ESC/POS) for proper label printing.
Supports both file backend (Linux /dev/usb/lp*) and pyusb (Mac).
"""

from artifact.hardware.base import Printer
from artifact.hardware.printer.em5820 import EM5820Printer, MockPrinter, create_printer
from artifact.hardware.printer.ip802 import (
    IP802Printer,
    MockLabelPrinter,
    create_label_printer,
    auto_detect_label_printer,
    PYUSB_AVAILABLE,
    USB_VENDOR_ID,
    USB_PRODUCT_ID,
)
from artifact.hardware.printer.rp80 import (
    RP80ReceiptPrinter,
    MockRP80ReceiptPrinter,
    create_rp80_printer,
    auto_detect_rp80_printer,
    USB_VENDOR_ID as RP80_USB_VENDOR_ID,
    USB_PRODUCT_ID as RP80_USB_PRODUCT_ID,
)

__all__ = [
    # Base class
    "Printer",
    # Legacy receipt printer (EM5820)
    "EM5820Printer",
    "MockPrinter",
    "create_printer",
    # Label printer (IP802) - primary
    "IP802Printer",
    "MockLabelPrinter",
    "create_label_printer",
    "auto_detect_label_printer",
    # USB detection helpers
    "PYUSB_AVAILABLE",
    "USB_VENDOR_ID",
    "USB_PRODUCT_ID",
    # RP80 photobooth receipt printer
    "RP80ReceiptPrinter",
    "MockRP80ReceiptPrinter",
    "create_rp80_printer",
    "auto_detect_rp80_printer",
    "RP80_USB_VENDOR_ID",
    "RP80_USB_PRODUCT_ID",
]

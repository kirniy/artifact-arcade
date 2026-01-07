"""Printer drivers for ARTIFACT.

Supports two printer types:
- EM5820: 58mm thermal receipt printer (continuous roll, UART/USB-serial)
- IP802: AIYIN IP-802 80mm thermal label printer (58x100mm labels, USB)

The IP802 is now the primary printer for ARTIFACT arcade.
"""

from artifact.hardware.base import Printer
from artifact.hardware.printer.em5820 import EM5820Printer, MockPrinter, create_printer
from artifact.hardware.printer.ip802 import (
    IP802Printer,
    MockLabelPrinter,
    create_label_printer,
    auto_detect_label_printer,
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
]

"""Printing module for ARTIFACT - Thermal label sticker generation.

Supports two printer types:
- IP802 (Primary): AIYIN IP-802 label printer with 58×100mm stickers
- EM5820 (Legacy): 58mm thermal receipt printer with continuous roll

The IP802 label printer is now the default for ARTIFACT arcade.
"""

# Print manager (handles both printer types)
from artifact.printing.manager import PrintManager

# Label printing (IP802 - primary)
from artifact.printing.label_layout import (
    LabelLayoutEngine,
    LabelLayout,
    TextBlock as LabelTextBlock,
    ImageBlock as LabelImageBlock,
    QRCodeBlock,
    SeparatorBlock as LabelSeparatorBlock,
    SpacerBlock as LabelSpacerBlock,
    Alignment,
    TextSize,
    LABEL_WIDTH_PX,
    LABEL_HEIGHT_PX,
)
from artifact.printing.label_receipt import LabelReceiptGenerator, LabelReceipt

# Legacy receipt printing (EM5820)
from artifact.printing.receipt import ReceiptGenerator, Receipt
from artifact.printing.layout import (
    LayoutEngine,
    ReceiptLayout,
    TextBlock,
    ImageBlock,
    SeparatorBlock,
    SpacerBlock,
)

__all__ = [
    # Print Manager
    "PrintManager",

    # Label printing (primary)
    "LabelReceiptGenerator",
    "LabelReceipt",
    "LabelLayoutEngine",
    "LabelLayout",
    "LabelTextBlock",
    "LabelImageBlock",
    "QRCodeBlock",
    "LabelSeparatorBlock",
    "LabelSpacerBlock",
    "Alignment",
    "TextSize",
    "LABEL_WIDTH_PX",
    "LABEL_HEIGHT_PX",

    # Legacy receipt printing
    "ReceiptGenerator",
    "Receipt",
    "LayoutEngine",
    "ReceiptLayout",
    "TextBlock",
    "ImageBlock",
    "SeparatorBlock",
    "SpacerBlock",
]

#!/usr/bin/env python3
"""CLI tool for testing the AIYIN IP-802 label printer.

Usage:
    python scripts/print_test.py image <path>      Print an image file
    python scripts/print_test.py text <message>    Print text label
    python scripts/print_test.py test              Print test pattern
    python scripts/print_test.py status            Check printer status
    python scripts/print_test.py receipt <mode>    Print a mode receipt (fortune, roast, etc.)

Examples:
    python scripts/print_test.py image ~/photo.png
    python scripts/print_test.py text "Hello World"
    python scripts/print_test.py test
    python scripts/print_test.py receipt fortune
"""

import sys
import os
import argparse
from io import BytesIO
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import usb.core
    import usb.util
    PYUSB_AVAILABLE = True
except ImportError:
    PYUSB_AVAILABLE = False
    print("Warning: pyusb not installed. Run: pip install pyusb")

from PIL import Image, ImageDraw, ImageFont

# Printer constants
VENDOR_ID = 0x353D
PRODUCT_ID = 0x1249
LABEL_WIDTH_MM = 58
LABEL_HEIGHT_MM = 100
DPI = 203
LABEL_WIDTH_PX = int(LABEL_WIDTH_MM * DPI / 25.4)  # 464
LABEL_HEIGHT_PX = int(LABEL_HEIGHT_MM * DPI / 25.4)  # 800


class TSPLPrinter:
    """Simple TSPL printer interface for Mac."""

    def __init__(self):
        self.dev = None
        self.ep_out = None

    def connect(self) -> bool:
        """Connect to printer."""
        if not PYUSB_AVAILABLE:
            print("Error: pyusb required")
            return False

        self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if not self.dev:
            print("Printer not found. Is it connected via USB?")
            return False

        print(f"Connected: {self.dev.manufacturer} - {self.dev.product}")

        try:
            self.dev.set_configuration()
        except:
            pass

        try:
            usb.util.claim_interface(self.dev, 0)
        except:
            pass

        cfg = self.dev.get_active_configuration()
        for ep in cfg[(0, 0)]:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                self.ep_out = ep.bEndpointAddress
                break

        return True

    def disconnect(self):
        """Disconnect from printer."""
        if self.dev:
            try:
                usb.util.release_interface(self.dev, 0)
            except:
                pass

    def send(self, data: bytes) -> int:
        """Send data to printer."""
        if not self.dev or not self.ep_out:
            raise RuntimeError("Not connected")
        return self.dev.write(self.ep_out, data, timeout=30000)

    def image_to_tspl(self, img: Image.Image) -> bytes:
        """Convert PIL Image to TSPL commands."""
        # Scale to fill label
        scale_w = LABEL_WIDTH_PX / img.width
        scale_h = LABEL_HEIGHT_PX / img.height
        scale = min(scale_w, scale_h)

        new_width = int(img.width * scale)
        new_height = int(img.height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create canvas and center
        canvas = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)
        x = (LABEL_WIDTH_PX - new_width) // 2
        y = (LABEL_HEIGHT_PX - new_height) // 2

        if img.mode == 'RGBA':
            # Handle transparency - paste on white
            bg = Image.new('L', img.size, 255)
            img_l = img.convert('L')
            canvas.paste(img_l, (x, y))
        elif img.mode != 'L':
            img = img.convert('L')
            canvas.paste(img, (x, y))
        else:
            canvas.paste(img, (x, y))

        # Dither to 1-bit
        canvas = canvas.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

        # Ensure width is multiple of 8
        width, height = canvas.size
        if width % 8 != 0:
            new_w = (width // 8 + 1) * 8
            new_canvas = Image.new('1', (new_w, height), 1)
            new_canvas.paste(canvas, (0, 0))
            canvas = new_canvas
            width = new_w

        width_bytes = width // 8

        # Build bitmap (TSPL: 1=white, 0=black)
        bitmap = []
        for row in range(height):
            for xb in range(width_bytes):
                byte_val = 0
                for bit in range(8):
                    px = xb * 8 + bit
                    if px < canvas.width and canvas.getpixel((px, row)) == 0:
                        byte_val |= (0x80 >> bit)
                bitmap.append(byte_val ^ 0xFF)  # Invert for TSPL

        # TSPL commands
        commands = [
            f"SIZE {LABEL_WIDTH_MM} mm, {LABEL_HEIGHT_MM} mm\r\n".encode(),
            b"GAP 3 mm, 0 mm\r\n",
            b"DIRECTION 1,0\r\n",
            b"SET TEAR ON\r\n",
            b"CLS\r\n",
            f"BITMAP 0,0,{width_bytes},{height},0,".encode(),
            bytes(bitmap),
            b"\r\n",
            b"PRINT 1,1\r\n"
        ]

        return b''.join(commands)

    def print_image(self, img: Image.Image) -> bool:
        """Print a PIL Image."""
        tspl = self.image_to_tspl(img)
        print(f"Sending {len(tspl)} bytes...")
        sent = self.send(tspl)
        print(f"Sent {sent} bytes")
        return True

    def print_image_file(self, path: str) -> bool:
        """Print an image from file path."""
        if not os.path.exists(path):
            print(f"File not found: {path}")
            return False

        img = Image.open(path)
        print(f"Image: {img.size} {img.mode}")
        return self.print_image(img)

    def print_text(self, text: str, title: str = "ARTIFACT") -> bool:
        """Print a text label."""
        # Create image with text
        img = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)
        draw = ImageDraw.Draw(img)

        # Try to load a nice font
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
            text_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        except:
            title_font = ImageFont.load_default()
            text_font = title_font

        # Draw title
        y = 40
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = bbox[2] - bbox[0]
        draw.text(((LABEL_WIDTH_PX - title_w) // 2, y), title, font=title_font, fill=0)
        y += 70

        # Draw separator
        draw.line([(30, y), (LABEL_WIDTH_PX - 30, y)], fill=0, width=2)
        y += 30

        # Word wrap and draw text
        words = text.split()
        lines = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            bbox = draw.textbbox((0, 0), test, font=text_font)
            if bbox[2] - bbox[0] > LABEL_WIDTH_PX - 40:
                if current:
                    lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=text_font)
            line_w = bbox[2] - bbox[0]
            draw.text(((LABEL_WIDTH_PX - line_w) // 2, y), line, font=text_font, fill=0)
            y += 40

        # Footer
        y = LABEL_HEIGHT_PX - 60
        draw.line([(30, y), (LABEL_WIDTH_PX - 30, y)], fill=0, width=1)
        y += 10
        footer = datetime.now().strftime("%d.%m.%Y %H:%M")
        bbox = draw.textbbox((0, 0), footer, font=ImageFont.load_default())
        footer_w = bbox[2] - bbox[0]
        draw.text(((LABEL_WIDTH_PX - footer_w) // 2, y), footer, fill=0)

        return self.print_image(img)

    def print_test_pattern(self) -> bool:
        """Print a test pattern."""
        img = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)
        draw = ImageDraw.Draw(img)

        # Border
        draw.rectangle([5, 5, LABEL_WIDTH_PX - 6, LABEL_HEIGHT_PX - 6], outline=0, width=3)

        # Title
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
            small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
        except:
            font = ImageFont.load_default()
            small = font

        draw.text((120, 30), "TSPL TEST", font=font, fill=0)

        # Info
        y = 100
        info = [
            f"Label: {LABEL_WIDTH_MM}x{LABEL_HEIGHT_MM}mm",
            f"Pixels: {LABEL_WIDTH_PX}x{LABEL_HEIGHT_PX}",
            f"DPI: {DPI}",
            f"Date: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
        ]
        for line in info:
            draw.text((30, y), line, font=small, fill=0)
            y += 30

        # Grayscale gradient
        y += 20
        draw.text((30, y), "Grayscale:", font=small, fill=0)
        y += 30
        for i in range(10):
            x = 30 + i * 40
            gray = int(255 * i / 9)
            draw.rectangle([x, y, x + 35, y + 40], fill=gray, outline=0)
        y += 60

        # Line test
        draw.text((30, y), "Lines:", font=small, fill=0)
        y += 30
        for i in range(1, 6):
            draw.line([(30, y), (LABEL_WIDTH_PX - 30, y)], fill=0, width=i)
            y += i + 10

        # Checkerboard
        y += 20
        draw.text((30, y), "Pattern:", font=small, fill=0)
        y += 30
        box_size = 20
        for row in range(4):
            for col in range(18):
                if (row + col) % 2 == 0:
                    x = 30 + col * box_size
                    draw.rectangle([x, y, x + box_size - 1, y + box_size - 1], fill=0)
            y += box_size

        # QR-like pattern
        y += 30
        for i in range(8):
            for j in range(8):
                if (i * 8 + j) % 3 == 0:
                    x = 180 + j * 12
                    draw.rectangle([x, y + i * 12, x + 10, y + i * 12 + 10], fill=0)

        return self.print_image(img)


def cmd_image(args):
    """Print an image file."""
    printer = TSPLPrinter()
    if not printer.connect():
        return 1
    try:
        printer.print_image_file(args.path)
        print("Done!")
        return 0
    finally:
        printer.disconnect()


def cmd_text(args):
    """Print a text label."""
    printer = TSPLPrinter()
    if not printer.connect():
        return 1
    try:
        printer.print_text(args.message, args.title)
        print("Done!")
        return 0
    finally:
        printer.disconnect()


def cmd_test(args):
    """Print test pattern."""
    printer = TSPLPrinter()
    if not printer.connect():
        return 1
    try:
        printer.print_test_pattern()
        print("Done!")
        return 0
    finally:
        printer.disconnect()


def cmd_status(args):
    """Check printer status."""
    if not PYUSB_AVAILABLE:
        print("pyusb not installed")
        return 1

    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev:
        print(f"Printer: {dev.manufacturer} - {dev.product}")
        print(f"Serial: {dev.serial_number}")
        print(f"USB: {dev.idVendor:04x}:{dev.idProduct:04x}")
        print("Status: Connected")
        return 0
    else:
        print("Status: Not found")
        return 1


def cmd_receipt(args):
    """Print a mode receipt."""
    try:
        from artifact.printing.label_receipt import LabelReceiptGenerator
    except ImportError:
        print("Error: Could not import label_receipt module")
        return 1

    printer = TSPLPrinter()
    if not printer.connect():
        return 1

    try:
        # Create test data
        from scripts.test_mac_printer import get_test_data
        data = get_test_data(args.mode)

        generator = LabelReceiptGenerator()
        receipt = generator.generate_receipt(args.mode, data)

        # Get the rendered image
        from artifact.printing.label_layout import LabelLayoutEngine
        engine = LabelLayoutEngine()
        img = engine.render_to_image(receipt.layout)

        printer.print_image(img)
        print(f"Printed {args.mode} receipt!")
        return 0
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        printer.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description="AIYIN IP-802 Label Printer Test Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # image command
    p_image = subparsers.add_parser('image', help='Print an image file')
    p_image.add_argument('path', help='Path to image file')
    p_image.set_defaults(func=cmd_image)

    # text command
    p_text = subparsers.add_parser('text', help='Print a text label')
    p_text.add_argument('message', help='Text to print')
    p_text.add_argument('--title', default='ARTIFACT', help='Title (default: ARTIFACT)')
    p_text.set_defaults(func=cmd_text)

    # test command
    p_test = subparsers.add_parser('test', help='Print test pattern')
    p_test.set_defaults(func=cmd_test)

    # status command
    p_status = subparsers.add_parser('status', help='Check printer status')
    p_status.set_defaults(func=cmd_status)

    # receipt command
    p_receipt = subparsers.add_parser('receipt', help='Print a mode receipt')
    p_receipt.add_argument('mode', help='Mode name (fortune, roast, quiz, etc.)')
    p_receipt.set_defaults(func=cmd_receipt)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

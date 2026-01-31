#!/usr/bin/env python3
"""Print sideways warning stickers using the same TSPL code as print_test.py.

Usage:
    python scripts/print_stickers.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import usb.core
    import usb.util
    PYUSB_AVAILABLE = True
except ImportError:
    PYUSB_AVAILABLE = False
    print("Warning: pyusb not installed. Run: pip install pyusb")

from PIL import Image, ImageDraw, ImageFont

# Printer constants (same as print_test.py)
VENDOR_ID = 0x353D
PRODUCT_ID = 0x1249
LABEL_WIDTH_MM = 58
LABEL_HEIGHT_MM = 100
DPI = 203
LABEL_WIDTH_PX = int(LABEL_WIDTH_MM * DPI / 25.4)  # 464
LABEL_HEIGHT_PX = int(LABEL_HEIGHT_MM * DPI / 25.4)  # 800


class TSPLPrinter:
    """Simple TSPL printer interface (same as print_test.py)."""

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
        """Convert PIL Image to TSPL commands (same as print_test.py)."""
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


def create_sideways_sticker(text: str) -> Image.Image:
    """Create a sticker with large sideways text.
    
    The text is rotated 90 degrees so it reads sideways when printed.
    """
    # Create a tall canvas for vertical orientation
    # We'll draw text horizontally then rotate
    
    # First, figure out how big we can make the text
    # Since label is 800px tall, when rotated text can be ~750px wide
    # Text should fill most of the 464px height (which becomes width after rotation)
    
    # Create horizontal image first (will be rotated)
    temp_width = LABEL_HEIGHT_PX - 50  # 750px for text
    temp_height = LABEL_WIDTH_PX - 60  # 404px for text height
    
    temp_img = Image.new('L', (temp_width, temp_height), 255)
    draw = ImageDraw.Draw(temp_img)
    
    # Find the largest font size that fits
    font_path = None
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
        "/System/Library/Fonts/Helvetica.ttc",  # Mac
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",  # Linux alt
    ]
    
    for fp in font_paths:
        if os.path.exists(fp):
            font_path = fp
            break
    
    # Binary search for optimal font size
    best_size = 20
    low, high = 20, 200
    
    while low <= high:
        mid = (low + high) // 2
        try:
            if font_path:
                test_font = ImageFont.truetype(font_path, mid)
            else:
                test_font = ImageFont.load_default()
                break  # Can't resize default font
            
            bbox = draw.textbbox((0, 0), text, font=test_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            
            if text_w <= temp_width - 20 and text_h <= temp_height - 20:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1
        except:
            high = mid - 1
    
    # Create final font
    try:
        if font_path:
            font = ImageFont.truetype(font_path, best_size)
        else:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Draw centered text
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (temp_width - text_w) // 2
    y = (temp_height - text_h) // 2
    
    draw.text((x, y), text, font=font, fill=0)
    
    # Rotate 90 degrees clockwise for sideways orientation
    rotated = temp_img.rotate(-90, expand=True)
    
    # Create final label-sized image and center the rotated text
    final = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)
    paste_x = (LABEL_WIDTH_PX - rotated.width) // 2
    paste_y = (LABEL_HEIGHT_PX - rotated.height) // 2
    final.paste(rotated, (paste_x, paste_y))
    
    return final


def main():
    stickers = [
        "НЕ ТЯНУТЬ НА СЕБЯ",
        "ОТРЫВАЙ ЧЕРЕЗ ВЕРХ"
    ]
    
    printer = TSPLPrinter()
    if not printer.connect():
        return 1
    
    try:
        for i, text in enumerate(stickers):
            print(f"\n=== Printing sticker {i+1}: {text} ===")
            img = create_sideways_sticker(text)
            
            # Save preview
            preview_path = f"/tmp/sticker_{i+1}.png"
            img.save(preview_path)
            print(f"Preview saved to: {preview_path}")
            
            printer.print_image(img)
            print(f"Sticker {i+1} printed!")
            
            if i < len(stickers) - 1:
                import time
                print("Waiting 3 seconds before next sticker...")
                time.sleep(3)
        
        print("\nAll stickers printed!")
        return 0
    
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    finally:
        printer.disconnect()


if __name__ == "__main__":
    sys.exit(main())

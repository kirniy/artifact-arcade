#!/usr/bin/env python3
"""Quick script to print an image using TSPL protocol on AIYIN IP-802."""

import sys
import os
from io import BytesIO

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import usb.core
import usb.util
from PIL import Image

# Printer USB IDs
VENDOR_ID = 0x353D
PRODUCT_ID = 0x1249

# Label dimensions at 203 DPI
LABEL_WIDTH_MM = 58
LABEL_HEIGHT_MM = 100
LABEL_WIDTH_PX = int(LABEL_WIDTH_MM * 203 / 25.4)  # ~464
LABEL_HEIGHT_PX = int(LABEL_HEIGHT_MM * 203 / 25.4)  # ~800


def connect_printer():
    """Connect to printer via USB."""
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Printer not found. Is it connected?")
        return None, None

    print(f"Found: {dev.manufacturer} - {dev.product}")

    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except:
        pass

    try:
        dev.set_configuration()
    except:
        pass

    try:
        usb.util.claim_interface(dev, 0)
    except Exception as e:
        print(f"Note: {e}")

    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = None
    for ep in intf:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
            break

    return dev, ep_out


def image_to_tspl(img_path: str) -> bytes:
    """Convert image to TSPL commands."""
    # Load and resize image
    img = Image.open(img_path)
    print(f"Original size: {img.size}")

    # Resize to fit label (maintain aspect ratio, fit within bounds)
    img.thumbnail((LABEL_WIDTH_PX - 20, LABEL_HEIGHT_PX - 100), Image.Resampling.LANCZOS)
    print(f"Resized to: {img.size}")

    # Create white canvas
    canvas = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)

    # Center image on canvas
    x = (LABEL_WIDTH_PX - img.size[0]) // 2
    y = 50  # Top margin

    # Convert to grayscale if needed
    if img.mode != 'L':
        img = img.convert('L')

    canvas.paste(img, (x, y))

    # Convert to 1-bit with dithering
    canvas = canvas.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

    # Ensure width is multiple of 8
    width, height = canvas.size
    if width % 8 != 0:
        new_width = (width // 8 + 1) * 8
        new_canvas = Image.new('1', (new_width, height), 1)
        new_canvas.paste(canvas, (0, 0))
        canvas = new_canvas
        width = new_width

    width_bytes = width // 8

    # Build bitmap data (TSPL polarity: 1=white, 0=black)
    bitmap_data = []
    for y in range(height):
        for xb in range(width_bytes):
            byte_val = 0
            for bit in range(8):
                px = xb * 8 + bit
                if px < canvas.width:
                    pixel = canvas.getpixel((px, y))
                    if pixel == 0:  # Black in PIL
                        byte_val |= (0x80 >> bit)
            # Invert for TSPL
            byte_val = byte_val ^ 0xFF
            bitmap_data.append(byte_val)

    # Build TSPL commands
    commands = []
    commands.append(f"SIZE {LABEL_WIDTH_MM} mm, {LABEL_HEIGHT_MM} mm\r\n".encode())
    commands.append(b"GAP 3 mm, 0 mm\r\n")
    commands.append(b"DIRECTION 1,0\r\n")
    commands.append(b"SET TEAR ON\r\n")
    commands.append(b"CLS\r\n")
    commands.append(f"BITMAP 0,0,{width_bytes},{height},0,".encode())
    commands.append(bytes(bitmap_data))
    commands.append(b"\r\n")
    commands.append(b"PRINT 1,1\r\n")

    return b''.join(commands)


def main():
    if len(sys.argv) < 2:
        print("Usage: python print_image_tspl.py <image_path>")
        print("\nDefault: printing isolate-super-black images from Downloads")
        images = [
            os.path.expanduser("~/Downloads/isolate-super-black-16-01-2026-15-30-18.png"),
            os.path.expanduser("~/Downloads/isolate-super-black-16-01-2026-15-29-22.png"),
        ]
    else:
        images = sys.argv[1:]

    # Connect to printer
    dev, ep_out = connect_printer()
    if not dev:
        sys.exit(1)

    try:
        for img_path in images:
            if not os.path.exists(img_path):
                print(f"File not found: {img_path}")
                continue

            print(f"\nPrinting: {os.path.basename(img_path)}")

            # Convert to TSPL
            tspl_data = image_to_tspl(img_path)
            print(f"TSPL data: {len(tspl_data)} bytes")

            # Send to printer
            bytes_sent = dev.write(ep_out, tspl_data, timeout=30000)
            print(f"Sent: {bytes_sent} bytes")

            import time
            time.sleep(3)  # Wait for print

            print("Done!")

    finally:
        try:
            usb.util.release_interface(dev, 0)
        except:
            pass


if __name__ == "__main__":
    main()

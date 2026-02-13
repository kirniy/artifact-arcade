#!/usr/bin/env python3
"""Print a large QR code sticker on AIYIN IP-802 via Mac USB."""

import sys
import time
import usb.core
import usb.util
import qrcode
from PIL import Image, ImageDraw, ImageFont

# Printer
VENDOR_ID = 0x353D
PRODUCT_ID = 0x1249

# Label: 58mm x 100mm @ 203 DPI
LABEL_W = 464
LABEL_H = 800

URL = "https://vnvnc.ru/gallery/photobooth"
TEXT = "ОТСКАНИРУЙ ЧТОБЫ СКАЧАТЬ ФОТО"


def build_image() -> Image.Image:
    img = Image.new('1', (LABEL_W, LABEL_H), 1)  # white
    draw = ImageDraw.Draw(img)

    # Text setup
    font_size = 32
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except:
            font = ImageFont.load_default()

    lines = ["ОТСКАНИРУЙ ЧТОБЫ", "СКАЧАТЬ ФОТО"]

    margin = 8
    # QR at very top, full width
    qr_size = LABEL_W - margin * 2
    start_y = margin  # QR starts at top

    # Remaining space for text
    gap = 16
    text_area_top = start_y + qr_size + gap
    text_area_h = LABEL_H - text_area_top - margin
    line_area_h = text_area_h // 2  # each line gets half

    # For each line, find max font size that fits width, then pick smaller to fit height too
    # We'll render each line as its own image to control letter-spacing

    # Generate QR
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=0)
    qr.add_data(URL)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('1')
    qr_img = qr_img.resize((qr_size, qr_size), Image.NEAREST)

    # Place QR at top
    qr_x = (LABEL_W - qr_size) // 2
    img.paste(qr_img, (qr_x, start_y))

    # Draw each text line stretched to fill width and height
    target_w = LABEL_W - margin * 2
    y_cursor = text_area_top
    for line in lines:
        # Find font size where height fits line_area_h
        best_size = 32
        best_font = font
        for sz in range(32, 300):
            try:
                f = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", sz)
            except:
                try:
                    f = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", sz)
                except:
                    break
            bbox = draw.textbbox((0, 0), line, font=f)
            h = bbox[3] - bbox[1]
            if h > line_area_h - 4:
                break
            best_size = sz
            best_font = f

        # Render text to temp image, then stretch to target_w
        bbox = draw.textbbox((0, 0), line, font=best_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # Render at native size
        tmp = Image.new('1', (tw + 4, th + 4), 1)
        tmp_draw = ImageDraw.Draw(tmp)
        tmp_draw.text((-bbox[0], -bbox[1]), line, fill=0, font=best_font)
        # Stretch horizontally to fill width
        stretched = tmp.resize((target_w, th + 4), Image.NEAREST)
        # Center vertically in line area
        line_y = y_cursor + (line_area_h - stretched.height) // 2
        img.paste(stretched, (margin, line_y))
        y_cursor += line_area_h

    return img


def image_to_tspl(img: Image.Image) -> bytes:
    w, h = img.size
    width_bytes = (w + 7) // 8

    cmds = (
        f"SIZE 58 mm, 100 mm\r\n"
        f"GAP 3 mm, 0 mm\r\n"
        f"DIRECTION 1,0\r\n"
        f"SET TEAR ON\r\n"
        f"CLS\r\n"
    ).encode()

    bitmap_data = bytearray()
    for y in range(h):
        for xb in range(width_bytes):
            byte_val = 0
            for bit in range(8):
                x = xb * 8 + bit
                if x < w:
                    pixel = img.getpixel((x, y))
                    if pixel == 0:  # black
                        byte_val |= (0x80 >> bit)
            bitmap_data.append(byte_val ^ 0xFF)  # invert for TSPL

    cmds += f"BITMAP 0,0,{width_bytes},{h},0,".encode()
    cmds += bytes(bitmap_data)
    cmds += b"\r\n"
    cmds += b"PRINT 1,1\r\n"
    return cmds


def main():
    print("Building sticker image...")
    img = build_image()

    preview = "/tmp/qr_sticker_preview.png"
    img.save(preview)
    print(f"Preview saved: {preview}")

    if "--preview" in sys.argv:
        print("Preview only, not printing.")
        return

    print("Connecting to printer...")
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Printer not found! Is it connected?")
        sys.exit(1)

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
    except:
        pass

    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = None
    for ep in intf:
        if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
            ep_out = ep.bEndpointAddress
            break

    tspl = image_to_tspl(img)
    print(f"Sending {len(tspl)} bytes...")
    dev.write(ep_out, tspl, timeout=30000)
    print("Done! Label should be printing.")
    time.sleep(2)
    usb.util.release_interface(dev, 0)


if __name__ == "__main__":
    main()

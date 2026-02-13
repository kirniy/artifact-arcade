#!/usr/bin/env python3
"""Print a text-only sticker on AIYIN IP-802 via Mac USB."""

import sys
import time
import usb.core
import usb.util
from PIL import Image, ImageDraw, ImageFont

VENDOR_ID = 0x353D
PRODUCT_ID = 0x1249
LABEL_W = 464
LABEL_H = 800

LINES = ["ИЩИТЕ", "ФОТО В", "ГАЛЕРЕЕ", "НА САЙТЕ", "VNVNC.RU"]


def build_image() -> Image.Image:
    img = Image.new('1', (LABEL_W, LABEL_H), 1)
    draw = ImageDraw.Draw(img)

    margin = 8
    target_w = LABEL_W - margin * 2
    line_area_h = (LABEL_H - margin * 2) // len(LINES)

    y_cursor = margin
    for line in LINES:
        # Find max font size that fits height
        best_font = None
        for sz in range(32, 400):
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
            best_font = f

        # Render text then stretch to fill width
        bbox = draw.textbbox((0, 0), line, font=best_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tmp = Image.new('1', (tw + 4, th + 4), 1)
        tmp_draw = ImageDraw.Draw(tmp)
        tmp_draw.text((-bbox[0], -bbox[1]), line, fill=0, font=best_font)
        stretched = tmp.resize((target_w, th + 4), Image.NEAREST)
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
                    if pixel == 0:
                        byte_val |= (0x80 >> bit)
            bitmap_data.append(byte_val ^ 0xFF)
    cmds += f"BITMAP 0,0,{width_bytes},{h},0,".encode()
    cmds += bytes(bitmap_data)
    cmds += b"\r\n"
    cmds += b"PRINT 1,1\r\n"
    return cmds


def main():
    print("Building sticker image...")
    img = build_image()
    preview = "/tmp/text_sticker_preview.png"
    img.save(preview)
    print(f"Preview saved: {preview}")

    if "--preview" in sys.argv:
        return

    print("Connecting to printer...")
    dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
    if dev is None:
        print("Printer not found!")
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
    print("Done!")
    time.sleep(2)
    usb.util.release_interface(dev, 0)


if __name__ == "__main__":
    main()

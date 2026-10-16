"""Offline real photographs in a compact mount, without inferred cutouts."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[3]


def render_guest_portrait(photo_bytes: bytes, *, theme_id: str = "twilight") -> bytes:
    """Mount the complete camera photograph. Never cut silhouettes or invent pixels.

    Club lighting defeats portrait segmentation. A naturally proportioned photo
    print is safer than forcing a landscape group into a tall white cutout.
    """
    theme_id = theme_id.replace("_", "-")
    photo = ImageOps.exif_transpose(Image.open(io.BytesIO(photo_bytes))).convert("RGB")
    photo.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
    # Retain the real photograph's colour and details. Thermal conversion belongs
    # to the existing printer pipeline, not the shared digital photo.
    photo = photo.point([round(255 * (x / 255) ** .45) for x in range(256)] * 3)
    photo = ImageOps.contain(photo, (680, 960), Image.Resampling.LANCZOS)
    photo_w, photo_h = photo.size
    header_h, footer_h = (320 if theme_id == "mean-girls" else 228), 160
    height = header_h + photo_h + 32 + footer_h
    canvas = Image.new("RGB", (720, height), "white")
    draw = ImageDraw.Draw(canvas)
    ink = (134, 23, 65) if theme_id == "mean-girls" else (30, 57, 58)
    # The emblem is the hero; no tiny logo floating above an empty certificate.
    if theme_id in {"twilight", "mean-girls"}:
        filename = "mean-girls-emblem.png" if theme_id == "mean-girls" else "twilight-emblem.png"
        with Image.open(ROOT / "assets/images" / filename) as source:
            rgba = source.convert("RGBA")
            emblem = Image.new("RGB", rgba.size, "white")
            emblem.paste(rgba, mask=rgba.getchannel("A"))
        emblem.thumbnail((600, 300) if theme_id == "mean-girls" else (540, 210), Image.Resampling.LANCZOS)
        canvas.paste(emblem, ((720-emblem.width)//2, (header_h-emblem.height)//2))
    photo_y = header_h
    draw.rectangle((16, photo_y-4, 703, photo_y+photo_h+3), outline=ink, width=2)
    canvas.paste(photo, ((720-photo_w)//2, photo_y))
    # A compact white mount keeps a photographic edge and reserves the footer.
    draw.line((20, photo_y+photo_h+18, 700, photo_y+photo_h+18), fill=(193, 206, 203))
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

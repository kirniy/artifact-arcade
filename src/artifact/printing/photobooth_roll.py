"""Dedicated 80mm roll receipt renderer for photobooth prints."""

from __future__ import annotations

import hashlib
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps

from artifact.printing.fortune_quotes import pick_fortune_quote

logger = logging.getLogger(__name__)

PAPER_WIDTH_PX = 576
PRINT_MARGIN_PX = 16
GALLERY_URL = "https://vnvnc.ru/gallery/photobooth"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOGO_PATH = PROJECT_ROOT / "assets" / "logos" / "vnvnc-logo-classic-border-letters-black.png"
LEGACY_LOGO_PATH = Path("/Users/kirniy/Desktop/Current logos/vnvnc-logo-classic-border-letters-black.svg")
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


@dataclass
class PhotoboothRollReceipt:
    """Rendered roll receipt with ESC/POS bytes and a PNG preview."""

    raw_commands: bytes
    preview_image: bytes
    timestamp: datetime
    quote: str


class PhotoboothRollReceiptGenerator:
    """Build a neat 80mm thermal photobooth receipt."""

    def __init__(
        self,
        *,
        paper_width_px: int = PAPER_WIDTH_PX,
        gallery_url: str = GALLERY_URL,
        logo_path: Path = LOGO_PATH,
    ) -> None:
        self.paper_width_px = paper_width_px
        self.gallery_url = gallery_url
        self.logo_path = logo_path

    def generate_receipt(self, mode_name: str, data: dict[str, Any]) -> PhotoboothRollReceipt:
        """Generate a receipt for a photobooth print job."""
        timestamp = self._parse_timestamp(data)
        quote = str(data.get("fortune_quote") or pick_fortune_quote())
        image = self._coerce_photo(data)
        receipt_image = self.render_image(image, timestamp=timestamp, quote=quote)
        raw = self.image_to_escpos(receipt_image)

        buf = BytesIO()
        receipt_image.save(buf, format="PNG")
        return PhotoboothRollReceipt(
            raw_commands=raw,
            preview_image=buf.getvalue(),
            timestamp=timestamp,
            quote=quote,
        )

    def render_image(self, photo: Image.Image, *, timestamp: datetime, quote: str) -> Image.Image:
        """Render the full receipt as a single monochrome-friendly image."""
        content_width = self.paper_width_px - PRINT_MARGIN_PX * 2
        footer_icon_size = 132
        section_gap = 12

        photo = ImageOps.exif_transpose(photo).convert("RGB")
        photo = self._fit_photo(photo, width=content_width)

        qr = self._make_qr(footer_icon_size)
        logo = self._load_logo(footer_icon_size)

        font_body = self._font(21)

        temp = Image.new("L", (self.paper_width_px, 10), 255)
        draw = ImageDraw.Draw(temp)
        quote_lines = self._wrap_text(draw, quote, font_body, content_width)
        quote_height = len(quote_lines) * 27

        time_line = timestamp.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y  %H:%M MSK")

        height = (
            photo.height
            + section_gap
            + 4
            + footer_icon_size
            + 10
            + 30
            + 12
            + quote_height
            + 22
        )
        canvas = Image.new("L", (self.paper_width_px, height), 255)
        draw = ImageDraw.Draw(canvas)

        y = 0
        canvas.paste(photo.convert("L"), (PRINT_MARGIN_PX, y))
        y += photo.height + section_gap

        draw.rectangle((PRINT_MARGIN_PX, y, self.paper_width_px - PRINT_MARGIN_PX - 1, y + 3), fill=0)
        y += 14

        left_x = PRINT_MARGIN_PX
        right_x = self.paper_width_px - PRINT_MARGIN_PX - footer_icon_size
        logo_x = right_x
        qr_x = left_x
        canvas.paste(qr, (qr_x, y))
        canvas.paste(logo, (logo_x, y))

        text_x = qr_x + footer_icon_size + 16
        text_w = logo_x - text_x - 16
        url_text = "VNVNC.RU/GALLERY/PHOTOBOOTH"
        url_font = self._fit_font(url_text, text_w, 31, 13, bold=True)
        time_font = self._fit_font(time_line, text_w, 22, 15, bold=True)
        self._draw_centered(draw, url_text, (text_x, y + 34, text_x + text_w, y + 68), url_font)
        self._draw_centered(draw, time_line, (text_x, y + 76, text_x + text_w, y + 104), time_font)
        y += footer_icon_size + 12

        draw.rectangle((PRINT_MARGIN_PX, y, self.paper_width_px - PRINT_MARGIN_PX - 1, y + 1), fill=0)
        y += 12

        for line in quote_lines:
            self._draw_centered(draw, line, (PRINT_MARGIN_PX, y, self.paper_width_px - PRINT_MARGIN_PX, y + 25), font_body)
            y += 27

        y += 8
        draw.rectangle((PRINT_MARGIN_PX, y, self.paper_width_px - PRINT_MARGIN_PX - 1, y + 5), fill=0)
        y += 6

        return canvas.crop((0, 0, self.paper_width_px, y))

    def image_to_escpos(self, image: Image.Image) -> bytes:
        """Convert a rendered receipt image to ESC/POS raster commands."""
        mono = image.convert("L")
        mono = ImageOps.autocontrast(mono)
        mono = mono.convert("1", dither=Image.Dither.FLOYDSTEINBERG)

        width, height = mono.size
        if width % 8:
            padded = Image.new("1", (((width + 7) // 8) * 8, height), 1)
            padded.paste(mono, (0, 0))
            mono = padded
            width = mono.width

        bytes_per_line = width // 8
        raster = bytearray()
        pixels = mono.load()
        for y in range(height):
            for x_byte in range(bytes_per_line):
                value = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if pixels[x, y] == 0:
                        value |= 0x80 >> bit
                raster.append(value)

        commands = bytearray()
        commands += b"\x1b@"
        commands += b"\x1b3\x18"
        commands += b"\x1dv0\x00"
        commands += bytes([bytes_per_line & 0xFF, (bytes_per_line >> 8) & 0xFF])
        commands += bytes([height & 0xFF, (height >> 8) & 0xFF])
        commands += raster
        commands += b"\x1b2"
        commands += b"\x1dV\x01"
        return bytes(commands)

    def _parse_timestamp(self, data: dict[str, Any]) -> datetime:
        value = data.get("timestamp") or data.get("date")
        if isinstance(value, datetime):
            return value.astimezone(MOSCOW_TZ)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(MOSCOW_TZ)
            except Exception:
                pass
        return datetime.now(MOSCOW_TZ)

    def _coerce_photo(self, data: dict[str, Any]) -> Image.Image:
        for key in ("caricature", "photo", "image", "preview_image"):
            value = data.get(key)
            if value is None:
                continue
            try:
                if isinstance(value, Image.Image):
                    return value.copy()
                if isinstance(value, (bytes, bytearray, memoryview)):
                    return Image.open(BytesIO(bytes(value))).copy()
                if isinstance(value, str):
                    path = Path(value)
                    if path.exists():
                        return Image.open(path).copy()
            except Exception as exc:
                logger.warning("Failed to load photobooth image from %s: %s", key, exc)
        raise ValueError("photobooth print job has no printable image")

    def _fit_photo(self, image: Image.Image, *, width: int) -> Image.Image:
        aspect = image.height / image.width
        height = int(width * aspect)
        return image.resize((width, height), Image.Resampling.LANCZOS)

    def _make_qr(self, size: int) -> Image.Image:
        import qrcode

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(self.gallery_url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("L")
        return image.resize((size, size), Image.Resampling.NEAREST)

    def _load_logo(self, size: int) -> Image.Image:
        for logo_path in self._logo_candidates():
            if logo_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                try:
                    logo = Image.open(logo_path).convert("RGBA")
                    logo.thumbnail((size, size), Image.Resampling.LANCZOS)
                    canvas = Image.new("RGBA", (size, size), "white")
                    canvas.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
                    return canvas.convert("L")
                except Exception as exc:
                    logger.warning("Failed to load logo image %s: %s", logo_path, exc)
                    continue

            cache_key = hashlib.sha1(str(logo_path).encode("utf-8")).hexdigest()[:10]
            cache_path = Path(tempfile.gettempdir()) / f"vnvnc-logo-{cache_key}-{size}.png"
            try:
                if not cache_path.exists() or cache_path.stat().st_mtime < logo_path.stat().st_mtime:
                    subprocess.run(
                        [
                            "magick",
                            "-background",
                            "white",
                            str(logo_path),
                            "-resize",
                            f"{size}x{size}",
                            "-gravity",
                            "center",
                            "-extent",
                            f"{size}x{size}",
                            str(cache_path),
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                return Image.open(cache_path).convert("L")
            except Exception as exc:
                logger.warning("Failed to render logo SVG %s: %s", logo_path, exc)

        fallback = Image.new("L", (size, size), 255)
        draw = ImageDraw.Draw(fallback)
        draw.rectangle((2, 2, size - 3, size - 3), outline=0, width=4)
        self._draw_centered(draw, "VNVNC", (0, size // 2 - 18, size, size // 2 + 18), self._font(24, bold=True))
        return fallback

    def _logo_candidates(self) -> list[Path]:
        candidates = [
            self.logo_path,
            PROJECT_ROOT / "assets" / "logos" / "vnvnc-logo-classic-border-letters-black.svg",
            LEGACY_LOGO_PATH,
        ]
        return [path for path in candidates if path.exists()]

    def _font(self, size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        paths = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in paths:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _fit_font(
        self,
        text: str,
        max_width: int,
        max_size: int,
        min_size: int,
        *,
        bold: bool = False,
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        probe = Image.new("L", (1, 1), 255)
        draw = ImageDraw.Draw(probe)
        for size in range(max_size, min_size - 1, -1):
            font = self._font(size, bold=bold)
            if self._text_width(draw, text, font) <= max_width:
                return font
        return self._font(min_size, bold=bold)

    def _wrap_text(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        words = " ".join(str(text).split()).split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if self._text_width(draw, candidate, font) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
        if current:
            lines.append(current)
        return lines[:4] or [""]

    def _draw_centered(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        box: tuple[int, int, int, int],
        font: ImageFont.ImageFont,
    ) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = box[0] + ((box[2] - box[0]) - tw) // 2
        y = box[1] + ((box[3] - box[1]) - th) // 2 - bbox[1]
        draw.text((x, y), text, fill=0, font=font)

    def _text_width(self, draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

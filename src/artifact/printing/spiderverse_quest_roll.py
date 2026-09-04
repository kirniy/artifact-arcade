"""Dedicated RP80 companion receipt for the SPIDERVERSE photo quest."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator
from artifact.printing.wheel_qr import render_wheel_receipt_qr


SPIDERVERSE_QUEST_MODE_NAME = "spiderverse_quest"
PAPER_WIDTH_PX = 576
MARGIN = 24
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLASSIC_LOGO_PATH = PROJECT_ROOT / "assets/logos/vnvnc-logo-classic-border-letters-black.png"


@dataclass(frozen=True, slots=True)
class SpiderverseQuestRollReceipt:
    raw_commands: bytes
    preview_image: bytes
    qr_region: tuple[int, int, int, int]


class SpiderverseQuestRollReceiptGenerator:
    """Large-type, one-action quest handoff calibrated for the 576px RP80."""

    def generate_receipt(
        self, mode_name: str, data: dict[str, Any]
    ) -> SpiderverseQuestRollReceipt:
        if mode_name != SPIDERVERSE_QUEST_MODE_NAME:
            raise ValueError(f"unsupported quest receipt mode: {mode_name}")
        start_url = self._required(data, "quest_start_url")
        if start_url != "https://t.me/vnvncbattlebot?start=spiderquest":
            raise ValueError("quest receipt requires canonical Telegram HTTPS deep link")

        image, qr_region = self.render_image(data)
        raw = PhotoboothRollReceiptGenerator().image_to_escpos(image)
        preview = BytesIO()
        image.save(preview, format="PNG", optimize=False)
        return SpiderverseQuestRollReceipt(raw, preview.getvalue(), qr_region)

    def render_image(self, data: dict[str, Any]) -> tuple[Image.Image, tuple[int, int, int, int]]:
        start_url = self._required(data, "quest_start_url")
        canvas = Image.new("L", (PAPER_WIDTH_PX, 1170), 255)
        draw = ImageDraw.Draw(canvas)
        left, right = MARGIN, PAPER_WIDTH_PX - MARGIN

        # Suit-like black field with a white web lattice, entirely code-drawn.
        draw.rounded_rectangle((left, 20, right, 274), radius=24, fill=0)
        center = (PAPER_WIDTH_PX // 2, 140)
        for radius in (34, 67, 101):
            draw.ellipse(
                (center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius),
                outline=255,
                width=2,
            )
        for dx, dy in ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1)):
            draw.line((center[0], center[1], center[0] + dx * 130, center[1] + dy * 130), fill=255, width=2)
        # Angular eye/mask marks keep the piece event-specific without licensed art.
        draw.polygon(((185, 107), (263, 128), (213, 174)), fill=255)
        draw.polygon(((391, 107), (313, 128), (363, 174)), fill=255)

        y = 294
        y = self._center(draw, "ПАУЧЬЕ ЧУТЬЁ", y, self._font(50, bold=True), gap=8)
        y = self._center(draw, "КВЕСТ", y, self._font(31, bold=True), gap=16)
        draw.rounded_rectangle((left, y, right, y + 76), radius=15, fill=0)
        self._center_box(draw, "КОКТЕЙЛЬ + ШОТ", (left, y, right, y + 76), self._font(35, bold=True), fill=255)
        y += 95

        qr = render_wheel_receipt_qr(
            start_url,
            max_size_px=360,
            error_correction="H",
            telegram_icon=True,
        ).image
        qx = (PAPER_WIDTH_PX - qr.width) // 2
        canvas.paste(qr, (qx, y))
        qr_region = (qx, y, qx + qr.width, y + qr.height)
        y += qr.height + 15

        for line, size in (
            ("СКАНИРУЙ QR", 34),
            ("ОТКРОЙ КВЕСТ В TELEGRAM", 25),
            ("ВЫПОЛНИ ЗАДАНИЕ", 25),
        ):
            y = self._center(draw, line, y, self._fit_font(draw, line, right - left, size), gap=7)

        y += 10
        draw.line((left, y, right, y), fill=0, width=3)
        y += 13
        logo = self._logo(104)
        canvas.paste(logo, ((PAPER_WIDTH_PX - logo.width) // 2, y))
        y += logo.height + 4
        reference = "ФОТОБУДКА ВИНОВНИЦЫ"
        y = self._center(draw, reference, y, self._fit_font(draw, reference, right - left, 21), gap=12)
        draw.line((left, y, right, y), fill=0, width=5)
        return canvas.crop((0, 0, PAPER_WIDTH_PX, y + 22)), qr_region

    @staticmethod
    def _required(data: dict[str, Any], key: str) -> str:
        value = str(data.get(key) or "").strip()
        if not value:
            raise ValueError(f"quest receipt requires {key}")
        return value

    @staticmethod
    def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
        candidates = (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        )
        for candidate in candidates:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size)
        return ImageFont.load_default()

    def _fit_font(self, draw: ImageDraw.ImageDraw, text: str, width: int, max_size: int) -> ImageFont.ImageFont:
        for size in range(max_size, 15, -1):
            font = self._font(size, bold=True)
            box = draw.textbbox((0, 0), text, font=font)
            if box[2] - box[0] <= width:
                return font
        return self._font(16, bold=True)

    @staticmethod
    def _center(draw: ImageDraw.ImageDraw, text: str, y: int, font: ImageFont.ImageFont, *, gap: int) -> int:
        box = draw.textbbox((0, 0), text, font=font)
        width, height = box[2] - box[0], box[3] - box[1]
        draw.text(((PAPER_WIDTH_PX - width) // 2, y - box[1]), text, font=font, fill=0)
        return y + height + gap

    @staticmethod
    def _center_box(draw: ImageDraw.ImageDraw, text: str, box: tuple[int, int, int, int], font: ImageFont.ImageFont, *, fill: int) -> None:
        bounds = draw.textbbox((0, 0), text, font=font)
        width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        x = box[0] + (box[2] - box[0] - width) // 2
        y = box[1] + (box[3] - box[1] - height) // 2 - bounds[1]
        draw.text((x, y), text, font=font, fill=fill)

    @staticmethod
    def _logo(size: int) -> Image.Image:
        with Image.open(CLASSIC_LOGO_PATH) as source:
            logo = ImageOps.contain(source.convert("L"), (size, size), Image.Resampling.LANCZOS)
        canvas = Image.new("L", (size, size), 255)
        canvas.paste(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
        return canvas

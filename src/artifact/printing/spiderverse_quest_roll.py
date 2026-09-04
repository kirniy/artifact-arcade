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

    def combine_with_photo(self, photo: Image.Image, data: dict[str, Any]) -> Image.Image:
        """One continuous raster: photo then quest; cut only at end."""
        if self._required(data, "quest_start_url") != "https://t.me/vnvncbattlebot?start=spiderquest":
            raise ValueError("quest receipt requires canonical Telegram HTTPS deep link")
        if photo.width != PAPER_WIDTH_PX:
            raise ValueError("combined quest receipt requires 576px RP80 paper")
        quest, _ = self.render_image(data)
        combined = Image.new("L", (PAPER_WIDTH_PX, photo.height + 24 + quest.height), 255)
        combined.paste(photo.convert("L"), (0, 0))
        combined.paste(quest, (0, photo.height + 24))
        return combined

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
        canvas = Image.new("L", (PAPER_WIDTH_PX, 1500), 255)
        draw = ImageDraw.Draw(canvas)
        left, right = MARGIN, PAPER_WIDTH_PX - MARGIN

        # Coarse halftone corners survive thermal stock without becoming mud.
        for yy in range(26, 154, 12):
            for xx in range(right - 112, right, 12):
                if (xx + yy) % 24 == 0:
                    draw.ellipse((xx, yy, xx + 4, yy + 4), fill=0)
        # Diagonal mission ribbon, deliberately shallow to save thermal density.
        draw.polygon(((left, 26), (right - 38, 26), (right, 74), (left + 38, 74)), fill=0)
        self._center_box(draw, "SPIDERVERSE  /  VNVNC", (left + 32, 27, right - 16, 74), self._font(25, bold=True), fill=255)

        y = 88
        # High-contrast eye mask and web are recognizable at 203 dpi without
        # flooding the thermal head with a large solid-black illustration.
        mask_top = y
        outer = (
            (288, mask_top), (343, mask_top + 15), (359, mask_top + 51),
            (339, mask_top + 88), (288, mask_top + 106),
            (237, mask_top + 88), (217, mask_top + 51), (233, mask_top + 15),
        )
        inner = (
            (288, mask_top + 6), (338, mask_top + 20), (352, mask_top + 53),
            (333, mask_top + 82), (288, mask_top + 98),
            (243, mask_top + 82), (224, mask_top + 53), (238, mask_top + 20),
        )
        draw.polygon(outer, fill=0)
        draw.polygon(inner, fill=255)
        # Web lines are drawn first, then the opaque lenses, so no strand
        # crosses the white eye fields.
        for radius in (20, 39, 58):
            draw.arc((288 - radius, mask_top + 50 - radius, 288 + radius, mask_top + 50 + radius), 18, 162, fill=0, width=2)
            draw.arc((288 - radius, mask_top + 50 - radius, 288 + radius, mask_top + 50 + radius), 198, 342, fill=0, width=2)
        for endpoint in ((247, mask_top + 25), (230, mask_top + 53), (250, mask_top + 83),
                         (329, mask_top + 25), (346, mask_top + 53), (326, mask_top + 83)):
            draw.line((288, mask_top + 50, *endpoint), fill=0, width=2)
        left_eye = ((232, mask_top + 37), (278, mask_top + 49), (257, mask_top + 84), (237, mask_top + 68))
        right_eye = ((344, mask_top + 37), (298, mask_top + 49), (319, mask_top + 84), (339, mask_top + 68))
        draw.polygon(left_eye, fill=0)
        draw.polygon(right_eye, fill=0)
        draw.polygon(((239, mask_top + 44), (270, mask_top + 52), (254, mask_top + 76), (242, mask_top + 65)), fill=255)
        draw.polygon(((337, mask_top + 44), (306, mask_top + 52), (322, mask_top + 76), (334, mask_top + 65)), fill=255)
        y += 116
        y = self._center(draw, "ПАУЧЬЕ", y, self._font(57, bold=True), gap=-2)
        y = self._center(draw, "ЧУТЬЁ", y, self._font(57, bold=True), gap=3)
        y = self._center(draw, "ФОТО-КВЕСТ", y, self._font(27, bold=True), gap=12)
        draw.line((left, y, right, y), fill=0, width=4)
        y += 12

        # Two visibly separate rewards, matching the two codes in the chest.
        for number, reward in (("01", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ"), ("02", "БЕСПЛАТНЫЙ ШОТ")):
            draw.rectangle((left, y, right, y + 67), outline=0, width=4)
            draw.rectangle((left, y, left + 64, y + 67), fill=0)
            self._center_box(draw, number, (left, y, left + 64, y + 67), self._font(27, bold=True), fill=255)
            self._center_box(draw, reward, (left + 72, y, right - 8, y + 67), self._fit_font(draw, reward, right - left - 94, 29), fill=0)
            y += 76
        y += 2
        y = self._center(draw, "5 ФОТО-ЗАДАНИЙ", y, self._font(31, bold=True), gap=8)

        qr = render_wheel_receipt_qr(
            start_url,
            max_size_px=370,
            error_correction="H",
            telegram_icon=True,
        ).image
        qx = (PAPER_WIDTH_PX - qr.width) // 2
        canvas.paste(qr, (qx, y))
        qr_region = (qx, y, qx + qr.width, y + qr.height)
        y += qr.height + 15

        for line, size in (
            ("1  СКАНИРУЙ QR", 29),
            ("2  СДЕЛАЙ 5 ФОТО", 27),
            ("3  ОТКРОЙ СУНДУК ПРИЗОВ", 24),
        ):
            y = self._center(draw, line, y, self._fit_font(draw, line, right - left, size), gap=7)

        y += 8
        draw.rectangle((left, y, right, y + 118), fill=0)
        self._center_box(draw, "ПОКАЖИ ДВА КОДА СОТРУДНИКУ", (left + 8, y + 5, right - 8, y + 38), self._fit_font(draw, "ПОКАЖИ ДВА КОДА СОТРУДНИКУ", right - left - 20, 23), fill=255)
        self._center_box(draw, "НА ВХОДЕ", (left + 8, y + 40, right - 8, y + 65), self._font(24, bold=True), fill=255)
        self._center_box(draw, "НАПРОТИВ ГАРДЕРОБА", (left + 8, y + 66, right - 8, y + 91), self._font(24, bold=True), fill=255)
        self._center_box(draw, "ДО 07:00", (left + 8, y + 92, right - 8, y + 115), self._font(23, bold=True), fill=255)
        y += 130
        logo = self._logo(82)
        canvas.paste(logo, ((PAPER_WIDTH_PX - logo.width) // 2, y))
        y += logo.height + 4
        reference = "ФОТОБУДКА ВИНОВНИЦЫ"
        y = self._center(draw, reference, y, self._fit_font(draw, reference, right - left, 19), gap=12)
        draw.line((left, y, right, y), fill=0, width=5)
        final_height = y + 22
        draw.rectangle((10, 10, PAPER_WIDTH_PX - 10, final_height - 10), outline=0, width=5)
        return canvas.crop((0, 0, PAPER_WIDTH_PX, final_height)), qr_region

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

"""Receipt generator for ARTIFACT modes.

Creates formatted receipts for each game mode, combining:
- ARTIFACT logo/branding
- Mode-specific content (predictions, caricatures, etc.)
- Date/time stamp
- QR codes (optional)
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from artifact.printing.layout import (
    LayoutEngine,
    ReceiptLayout,
    TextBlock,
    ImageBlock,
    Alignment,
    TextSize,
)

logger = logging.getLogger(__name__)


@dataclass
class Receipt:
    """A generated receipt ready for printing."""

    mode_name: str
    layout: ReceiptLayout
    raw_commands: bytes
    preview: str
    timestamp: datetime


class ReceiptGenerator:
    """Generator for mode-specific receipts.

    Creates beautifully formatted thermal receipts for each
    ARTIFACT game mode output.
    """

    def __init__(self):
        self._layout_engine = LayoutEngine()
        self._logo_data: Optional[bytes] = None

    def set_logo(self, logo_data: bytes) -> None:
        """Set the ARTIFACT logo image data.

        Args:
            logo_data: PNG or JPG image bytes
        """
        self._logo_data = logo_data

    def generate_receipt(self, mode_name: str, data: Dict[str, Any]) -> Receipt:
        """Generate a receipt for a mode result.

        Args:
            mode_name: Name of the mode (fortune, zodiac, ai_prophet, etc.)
            data: Mode-specific data from ModeResult.print_data

        Returns:
            Receipt object ready for printing
        """
        # Create layout based on mode
        if mode_name == "fortune":
            layout = self._create_fortune_receipt(data)
        elif mode_name == "zodiac":
            layout = self._create_zodiac_receipt(data)
        elif mode_name == "ai_prophet":
            layout = self._create_ai_prophet_receipt(data)
        elif mode_name == "roulette":
            layout = self._create_roulette_receipt(data)
        elif mode_name == "quiz":
            layout = self._create_quiz_receipt(data)
        elif mode_name == "squid_game":
            layout = self._create_squid_game_receipt(data)
        elif mode_name == "guess_me":
            layout = self._create_guess_me_receipt(data)
        elif mode_name == "roast":
            layout = self._create_roast_receipt(data)
        elif mode_name == "autopsy":
            layout = self._create_autopsy_receipt(data)
        elif mode_name == "photobooth":
            layout = self._create_photobooth_receipt(data)
        elif mode_name == "rap_god":
            layout = self._create_rapgod_receipt(data)
        elif mode_name == "tower_stack":
            layout = self._create_tower_stack_receipt(data)
        elif mode_name == "brick_breaker":
            layout = self._create_brick_breaker_receipt(data)
        elif mode_name == "video":
            layout = self._create_video_receipt(data)
        else:
            layout = self._create_generic_receipt(mode_name, data)

        # Render to commands
        raw_commands = self._layout_engine.render(layout)

        # Generate preview
        preview = self._layout_engine.preview_text(layout)

        timestamp = self._parse_timestamp(data)
        return Receipt(
            mode_name=mode_name,
            layout=layout,
            raw_commands=raw_commands,
            preview=preview,
            timestamp=timestamp,
        )

    def _parse_timestamp(self, data: Dict[str, Any]) -> datetime:
        """Parse an ISO timestamp from mode data, falling back to now."""
        ts = data.get("timestamp")
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                pass
        return datetime.now()

    def _coerce_image(self, image: Any) -> Optional[bytes]:
        """Convert image-like input to PNG bytes."""
        if image is None:
            return None
        if isinstance(image, (bytes, bytearray, memoryview)):
            return bytes(image)
        if isinstance(image, str):
            try:
                path = Path(image)
                if path.exists():
                    from PIL import Image
                    img = Image.open(path)
                    buf = BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue()
            except Exception:
                return None

        try:
            from PIL import Image
        except Exception:
            return None

        try:
            if isinstance(image, Image.Image):
                img = image
            else:
                import numpy as np
                if isinstance(image, np.ndarray):
                    img = Image.fromarray(image)
                else:
                    return None
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return None

    def _prepare_qr_image(self, image: Any) -> Optional[bytes]:
        """Normalize QR image to black-on-white for thermal printing."""
        raw = self._coerce_image(image)
        if not raw:
            return None
        try:
            from PIL import Image, ImageOps, ImageStat

            img = Image.open(BytesIO(raw)).convert("L")
            if ImageStat.Stat(img).mean[0] < 128:
                img = ImageOps.invert(img)
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            return raw

    def _add_body_text(self, layout: ReceiptLayout, text: str, size: TextSize = TextSize.SMALL) -> None:
        layout.add_text(text, alignment=Alignment.LEFT, size=size)

    def _add_kv(self, layout: ReceiptLayout, label: str, value: str) -> None:
        layout.add_text(f"{label}: {value}", alignment=Alignment.LEFT, size=TextSize.SMALL)

    def _create_header(self, layout: ReceiptLayout) -> None:
        """Add standard VNVNC header to layout."""
        # Logo if available
        if self._logo_data:
            layout.add_image(self._logo_data, width=256, dither=True)
            layout.add_space(1)
        else:
            # Text logo fallback
            layout.add_text("VNVNC", size=TextSize.LARGE, bold=True)
            layout.add_text("VNVNC ARCADE", size=TextSize.SMALL)

        layout.add_separator("double")
        layout.add_space(1)

    def _create_footer(self, layout: ReceiptLayout, data: Dict[str, Any]) -> None:
        """Add standard footer with date/time."""
        layout.add_space(1)
        layout.add_separator("line")

        # Date and time
        now = self._parse_timestamp(data)
        date_str = now.strftime("%d.%m.%Y %H:%M")
        layout.add_text(date_str, size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_text("Спасибо за визит!", size=TextSize.SMALL)
        layout.add_text("vnvnc.ai", size=TextSize.SMALL)
        layout.add_space(2)

    def _create_fortune_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Fortune Teller mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ГАДАЛКА", size=TextSize.LARGE, bold=True)
        layout.add_separator("line")
        layout.add_space(1)

        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            layout.add_image(caricature, width=384, dither=True)
            layout.add_space(1)

        fortune = (
            data.get("fortune") or
            data.get("prediction") or
            data.get("display_text") or
            "Звезды молчат..."
        )
        layout.add_text("ПРЕДСКАЗАНИЕ", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
        layout.add_text(fortune, alignment=Alignment.LEFT, size=TextSize.MEDIUM)

        details = []
        birthdate = data.get("birthdate") or data.get("birthday")
        if birthdate:
            details.append(("Дата рождения", birthdate))
        zodiac = data.get("zodiac_sign") or data.get("zodiac_ru")
        if zodiac:
            details.append(("Знак", zodiac))
        chinese = data.get("chinese_zodiac")
        if chinese:
            details.append(("Китайский знак", chinese))
        lucky_color = data.get("lucky_color")
        if lucky_color:
            details.append(("Счастливый цвет", lucky_color))

        if details:
            layout.add_space(1)
            layout.add_separator("line")
            layout.add_text("ДАННЫЕ", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
            for label, value in details:
                self._add_kv(layout, label, value)

        qr_image = self._prepare_qr_image(data.get("qr_image"))
        qr_url = data.get("qr_url")
        if qr_image or qr_url:
            layout.add_space(1)
            layout.add_separator("line")
            layout.add_text("СКАЧАТЬ:", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
            if qr_image:
                layout.add_image(qr_image, width=192, dither=False)
            else:
                layout.add_text(qr_url, alignment=Alignment.LEFT, size=TextSize.SMALL)

        self._create_footer(layout, data)
        return layout

    def _create_zodiac_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Zodiac mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        # Zodiac sign
        zodiac_ru = data.get("zodiac_ru", "Unknown")
        zodiac_symbol = data.get("zodiac_symbol", "*")
        birthday = data.get("birthday", "")

        layout.add_text(f"{zodiac_symbol} {zodiac_ru} {zodiac_symbol}", size=TextSize.LARGE, bold=True)

        if birthday:
            layout.add_text(f"({birthday})", size=TextSize.SMALL)

        layout.add_separator("stars")
        layout.add_space(1)

        # Horoscope
        horoscope = data.get("horoscope", "The stars await...")
        layout.add_text(horoscope, alignment=Alignment.LEFT, size=TextSize.MEDIUM)

        layout.add_space(1)
        layout.add_separator("stars")

        self._create_footer(layout, data)
        return layout

    def _create_ai_prophet_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for AI Prophet mode (the KEY receipt).

        This is the flagship receipt combining:
        - Caricature image
        - AI prediction
        - Lucky number and color
        - Date/time
        """
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ИИ ПРОРОК", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            layout.add_image(caricature, width=384, dither=True)
            layout.add_space(1)

        prediction = (
            data.get("prediction") or
            data.get("display_text") or
            "Твое будущее сияет..."
        )
        layout.add_text("ПРОРОЧЕСТВО", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
        layout.add_text(prediction, alignment=Alignment.LEFT, size=TextSize.MEDIUM)

        lucky_number = data.get("lucky_number")
        lucky_color = data.get("lucky_color")
        traits = data.get("traits", [])

        if lucky_number or lucky_color or traits:
            layout.add_space(1)
            layout.add_separator("line")
            if lucky_number:
                self._add_kv(layout, "Счастливое число", str(lucky_number))
            if lucky_color:
                self._add_kv(layout, "Счастливый цвет", str(lucky_color))
            if traits:
                layout.add_text("Черты характера:", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
                layout.add_text(", ".join(traits[:3]), alignment=Alignment.LEFT, size=TextSize.SMALL)

        qr_image = self._prepare_qr_image(data.get("qr_image"))
        qr_url = data.get("qr_url")
        if qr_image or qr_url:
            layout.add_space(1)
            layout.add_separator("line")
            layout.add_text("СКАЧАТЬ:", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
            if qr_image:
                layout.add_image(qr_image, width=192, dither=False)
            else:
                layout.add_text(qr_url, alignment=Alignment.LEFT, size=TextSize.SMALL)

        self._create_footer(layout, data)
        return layout

    def _create_roulette_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Roulette mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ROULETTE", size=TextSize.LARGE, bold=True)
        layout.add_separator("line")
        layout.add_space(1)

        # Result
        result = data.get("result", "???")
        layout.add_text(result, size=TextSize.LARGE, bold=True)

        # Category
        category = data.get("category", "")
        if category:
            layout.add_text(f"({category})", size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_separator("line")

        self._create_footer(layout, data)
        return layout

    def _create_quiz_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Quiz mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ВИКТОРИНА", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        doodle = self._coerce_image(data.get("caricature"))
        if doodle:
            layout.add_image(doodle, width=384, dither=True)
            layout.add_space(1)

        score = data.get("score", 0)
        total = data.get("total", 0)
        layout.add_text(f"СЧЕТ: {score}/{total}", alignment=Alignment.LEFT, size=TextSize.MEDIUM, bold=True)

        percentage = data.get("percentage")
        if percentage is None and total > 0:
            percentage = int(score / total * 100)
        if percentage is not None:
            layout.add_text(f"{percentage}%", alignment=Alignment.LEFT, size=TextSize.SMALL)

        if data.get("won_cocktail"):
            layout.add_space(1)
            layout.add_text("ПРИЗ: БЕСПЛАТНЫЙ КОКТЕЙЛЬ", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)

            # Show coupon code if available
            coupon = data.get("coupon_code")
            if coupon:
                layout.add_separator("line")
                layout.add_text(f"КОД: {coupon}", size=TextSize.LARGE, bold=True)
                layout.add_text("Покажи бармену", size=TextSize.MEDIUM)
                layout.add_separator("line")

        rank = data.get("rank", "")
        if rank:
            layout.add_space(1)
            layout.add_text(rank, alignment=Alignment.LEFT, size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_squid_game_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Receipt for Squid Game mode with sketch + result."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ИГРА В КАЛЬМАРА", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        result = (data.get("result") or "").upper()
        if result:
            result_text = "ПОБЕДА" if result == "VICTORY" else "ВЫБЫЛ" if result == "ELIMINATED" else result
            layout.add_text(result_text, size=TextSize.MEDIUM, bold=True)

        # Sketch photo - FULL WIDTH, NO FRAME
        sketch = self._coerce_image(data.get("caricature") or data.get("sketch"))
        if sketch:
            layout.add_space(1)
            layout.add_image(sketch, width=384, dither=True)
            layout.add_space(1)

        coupon = data.get("coupon_code")
        if coupon:
            layout.add_separator("line")
            layout.add_text(f"КОД: {coupon}", size=TextSize.LARGE, bold=True)
            layout.add_text("Покажи бармену", size=TextSize.MEDIUM)
        else:
            layout.add_text("Фото твоего бега!", size=TextSize.MEDIUM)

        reason = data.get("elimination_reason")
        if reason:
            layout.add_space(1)
            layout.add_text(reason, alignment=Alignment.LEFT, size=TextSize.SMALL)

        survived = data.get("survived_time")
        if survived:
            layout.add_text(f"Время: {survived}", alignment=Alignment.LEFT, size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_roast_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Roast mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ПРОЖАРКА", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        # Doodle image - FULL WIDTH, NO FRAME
        doodle = self._coerce_image(data.get("doodle") or data.get("caricature"))
        if doodle:
            layout.add_image(doodle, width=384, dither=True)
            layout.add_space(1)

        # Roast text
        roast_text = data.get("roast") or data.get("display_text") or ""
        if roast_text:
            layout.add_text(roast_text, alignment=Alignment.LEFT, size=TextSize.MEDIUM)

        vibe = data.get("vibe")
        if vibe:
            layout.add_space(1)
            self._add_kv(layout, "Вайб", str(vibe))

        qr_image = self._prepare_qr_image(data.get("qr_image"))
        qr_url = data.get("qr_url")
        if qr_image or qr_url:
            layout.add_space(1)
            layout.add_separator("line")
            layout.add_text("СКАЧАТЬ:", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
            if qr_image:
                layout.add_image(qr_image, width=192, dither=False)
            else:
                layout.add_text(qr_url, alignment=Alignment.LEFT, size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_autopsy_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Autopsy mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ДИАГНОЗ", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        # X-ray scan image - FULL WIDTH, NO FRAME
        scan_image = self._coerce_image(data.get("scan_image") or data.get("caricature"))
        if scan_image:
            layout.add_image(scan_image, width=384, dither=True)
            layout.add_space(1)

        # Subject ID
        subject_id = data.get("id") or ""
        if subject_id:
            layout.add_text(f"ID: {subject_id}", size=TextSize.MEDIUM, bold=True)

        # Diagnosis text
        diagnosis = data.get("diagnosis") or data.get("display_text") or ""
        if diagnosis:
            layout.add_text(diagnosis, alignment=Alignment.LEFT, size=TextSize.MEDIUM)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_generic_receipt(self, mode_name: str, data: Dict[str, Any]) -> ReceiptLayout:
        """Create a generic receipt for any mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        # Mode name as title
        layout.add_text(mode_name.upper(), size=TextSize.LARGE, bold=True)
        layout.add_separator("line")
        layout.add_space(1)

        # Display text if available
        display_text = data.get("display_text") or data.get("result", "")
        if display_text:
            layout.add_text(display_text, alignment=Alignment.LEFT, size=TextSize.MEDIUM)

        layout.add_space(1)
        layout.add_separator("line")

        self._create_footer(layout, data)
        return layout

    def _create_photobooth_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Photobooth mode.

        Adapted from raspi-photo-booth thermal printing pattern.
        Includes photo and optional QR code for sharing.
        """
        layout = ReceiptLayout()
        self._create_header(layout)
        layout.add_space(1)

        # Photo image - FULL WIDTH, adapted from raspi-photo-booth printPhoto()
        photo = self._coerce_image(data.get("caricature") or data.get("photo"))
        if photo:
            layout.add_image(photo, width=384, dither=True)
            layout.add_space(1)

        # QR code URL if available (from file.io upload)
        qr_image = self._prepare_qr_image(data.get("qr_image"))
        qr_url = data.get("qr_url")
        if qr_image or qr_url:
            layout.add_separator("line")
            layout.add_text("СКАЧАТЬ ФОТО:", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
            if qr_image:
                layout.add_image(qr_image, width=192, dither=False)
            else:
                layout.add_text(qr_url, alignment=Alignment.LEFT, size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_rapgod_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for RapGod mode.

        Includes song title, artist, hook lyrics, and download QR code.
        """
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("RAP GOD", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        # Song title and artist
        song_title = data.get("song_title") or "Untitled"
        artist = data.get("artist") or "ARTIFACT AI"

        layout.add_text(song_title, alignment=Alignment.LEFT, size=TextSize.MEDIUM, bold=True)
        layout.add_text(artist, alignment=Alignment.LEFT, size=TextSize.SMALL)
        layout.add_space(1)

        # Genre and BPM
        genre = data.get("genre") or "trap"
        bpm = data.get("bpm") or 140
        layout.add_text(f"{genre.upper()} / {bpm} BPM", alignment=Alignment.LEFT, size=TextSize.SMALL)
        layout.add_separator("line")
        layout.add_space(1)

        # Hook lyrics (4-6 lines)
        hook = data.get("hook") or ""
        if hook:
            layout.add_text("ПРИПЕВ:", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
            # Split and print each line
            lines = hook.split("\n")[:6]  # Max 6 lines
            for line in lines:
                if line.strip():
                    layout.add_text(line.strip()[:40], alignment=Alignment.LEFT, size=TextSize.SMALL)
            layout.add_space(1)

        # One-liner tagline
        one_liner = data.get("one_liner")
        if one_liner:
            layout.add_text(f'"{one_liner}"', alignment=Alignment.LEFT, size=TextSize.SMALL)
            layout.add_space(1)

        # Download URL with QR
        download_url = data.get("download_url")
        if download_url:
            layout.add_separator("line")
            layout.add_text("СКАЧАТЬ ТРЕК:", alignment=Alignment.LEFT, size=TextSize.SMALL, bold=True)
            # Wrap long URL
            if len(download_url) > 32:
                layout.add_text(download_url[:32], alignment=Alignment.LEFT, size=TextSize.SMALL)
                layout.add_text(download_url[32:], alignment=Alignment.LEFT, size=TextSize.SMALL)
            else:
                layout.add_text(download_url, alignment=Alignment.LEFT, size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_tower_stack_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Tower Stack mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("БАШНЯ", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        score = data.get("score", 0)
        layout.add_text(f"СЧЕТ: {score}", alignment=Alignment.LEFT, size=TextSize.MEDIUM, bold=True)

        height = data.get("height")
        if height is not None:
            self._add_kv(layout, "Высота", str(height))

        max_streak = data.get("max_streak")
        if max_streak is not None:
            self._add_kv(layout, "Макс. серия", str(max_streak))

        difficulty = data.get("difficulty")
        if difficulty:
            self._add_kv(layout, "Сложность", str(difficulty))

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_brick_breaker_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Brick Breaker mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("КИРПИЧИ", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        score = data.get("score", 0)
        layout.add_text(f"СЧЕТ: {score}", alignment=Alignment.LEFT, size=TextSize.MEDIUM, bold=True)

        level = data.get("level")
        if level is not None:
            self._add_kv(layout, "Уровень", str(level))

        max_combo = data.get("max_combo")
        if max_combo is not None:
            self._add_kv(layout, "Комбо", f"x{max_combo}")

        lives = data.get("lives_remaining")
        if lives is not None:
            self._add_kv(layout, "Жизни", str(lives))

        win = data.get("win")
        if win is not None:
            outcome = "ПОБЕДА" if win else "ПРОИГРЫШ"
            self._add_kv(layout, "Итог", outcome)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_video_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Video mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("ВИДЕО", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        title = data.get("title") or data.get("media_name") or "Без названия"
        layout.add_text(title, alignment=Alignment.LEFT, size=TextSize.MEDIUM, bold=True)

        media_type = data.get("media_type")
        if media_type:
            type_map = {
                "VIDEO": "ВИДЕО",
                "IMAGE": "ФОТО",
                "GIF": "GIF",
            }
            self._add_kv(layout, "Тип", type_map.get(str(media_type), str(media_type)))

        index = data.get("index")
        total = data.get("total")
        if index is not None and total is not None:
            self._add_kv(layout, "Позиция", f"{index}/{total}")

        status = data.get("status")
        if status:
            self._add_kv(layout, "Статус", str(status))

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

    def _create_guess_me_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Guess Me mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("WHO AM I?", size=TextSize.LARGE, bold=True)
        layout.add_separator("line")
        layout.add_space(1)

        title = data.get("title") or "Загадка"
        prediction = data.get("prediction") or ""
        layout.add_text(title, alignment=Alignment.LEFT, size=TextSize.MEDIUM, bold=True)
        if prediction:
            layout.add_space(1)
            layout.add_text(prediction, alignment=Alignment.LEFT, size=TextSize.MEDIUM)

        # Caricature - FULL WIDTH, NO FRAME
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            layout.add_space(1)
            layout.add_image(caricature, width=384, dither=True)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout, data)
        return layout

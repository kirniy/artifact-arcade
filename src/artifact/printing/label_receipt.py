"""Label receipt generator for ARTIFACT modes.

Creates formatted label receipts for each game mode, optimized for
58×100mm thermal sticker labels on the AIYIN IP-802 printer.

Key differences from roll receipts:
- Fixed label size (58×100mm / 464×800 pixels)
- Content must fit within label bounds
- Larger images and text for better visibility
- No continuous paper - each label is standalone
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from artifact.printing.label_layout import (
    LabelLayoutEngine,
    LabelLayout,
    TextBlock,
    ImageBlock,
    QRCodeBlock,
    SeparatorBlock,
    SpacerBlock,
    Alignment,
    TextSize,
    LABEL_WIDTH_PX,
    LABEL_HEIGHT_PX,
)

logger = logging.getLogger(__name__)


@dataclass
class LabelReceipt:
    """A generated label receipt ready for printing."""

    mode_name: str
    layout: LabelLayout
    raw_commands: bytes
    preview_image: Optional[bytes]  # PNG preview
    timestamp: datetime


class LabelReceiptGenerator:
    """Generator for mode-specific label receipts.

    Creates beautifully formatted thermal label stickers for each
    ARTIFACT game mode output. Optimized for 58×100mm labels.
    """

    def __init__(self):
        self._layout_engine = LabelLayoutEngine()
        self._logo_data: Optional[bytes] = None

    def set_logo(self, logo_data: bytes) -> None:
        """Set the ARTIFACT logo image data.

        Args:
            logo_data: PNG or JPG image bytes
        """
        self._logo_data = logo_data

    def generate_receipt(self, mode_name: str, data: Dict[str, Any]) -> LabelReceipt:
        """Generate a label receipt for a mode result.

        Args:
            mode_name: Name of the mode (fortune, zodiac, ai_prophet, etc.)
            data: Mode-specific data from ModeResult.print_data

        Returns:
            LabelReceipt object ready for printing
        """
        # Create layout based on mode
        if mode_name == "fortune":
            layout = self._create_fortune_label(data)
        elif mode_name == "zodiac":
            layout = self._create_zodiac_label(data)
        elif mode_name == "ai_prophet":
            layout = self._create_ai_prophet_label(data)
        elif mode_name == "roulette":
            layout = self._create_roulette_label(data)
        elif mode_name == "quiz":
            layout = self._create_quiz_label(data)
        elif mode_name == "squid_game":
            layout = self._create_squid_game_label(data)
        elif mode_name == "guess_me":
            layout = self._create_guess_me_label(data)
        elif mode_name == "roast":
            layout = self._create_roast_label(data)
        elif mode_name == "autopsy":
            layout = self._create_autopsy_label(data)
        elif mode_name == "photobooth":
            layout = self._create_photobooth_label(data)
        elif mode_name == "rap_god":
            layout = self._create_rapgod_label(data)
        elif mode_name == "tower_stack":
            layout = self._create_tower_stack_label(data)
        elif mode_name == "brick_breaker":
            layout = self._create_brick_breaker_label(data)
        elif mode_name == "video":
            layout = self._create_video_label(data)
        elif mode_name == "sorting_hat":
            layout = self._create_sorting_hat_label(data)
        else:
            layout = self._create_generic_label(mode_name, data)

        # Render to ESC/POS commands
        raw_commands = self._layout_engine.render(layout)

        # Generate preview image
        preview_image = self._layout_engine.render_to_png(layout)

        timestamp = self._parse_timestamp(data)
        return LabelReceipt(
            mode_name=mode_name,
            layout=layout,
            raw_commands=raw_commands,
            preview_image=preview_image,
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

    def _get_date_string(self, data: Dict[str, Any]) -> str:
        """Get formatted date string."""
        now = self._parse_timestamp(data)
        return now.strftime("%d.%m.%Y %H:%M")

    def _calculate_image_height(self, image_data: bytes, target_width: int) -> int:
        """Calculate image height at target width, maintaining aspect ratio."""
        try:
            from PIL import Image
            img = Image.open(BytesIO(image_data))
            aspect = img.height / img.width
            return int(target_width * aspect)
        except Exception:
            return target_width  # Assume square if can't determine

    def _estimate_text_height(self, text: str, size: TextSize) -> int:
        """Estimate text height in pixels."""
        # Font sizes from TextSize enum
        font_size = size.value
        line_height = font_size + 4
        # Rough estimate of lines based on average char width
        chars_per_line = max(1, (LABEL_WIDTH_PX - 32) // (font_size // 2))
        num_lines = max(1, (len(text) + chars_per_line - 1) // chars_per_line)
        return num_lines * line_height

    def _create_header(self, layout: LabelLayout, title: str) -> None:
        """Add standard header with title."""
        layout.add_text("VNVNC ARCADE", size=TextSize.SMALL)
        layout.add_space(4)
        layout.add_text(title, size=TextSize.TITLE, bold=True)
        layout.add_separator("double")
        layout.add_space(8)

    def _create_footer(self, layout: LabelLayout, data: Dict[str, Any]) -> None:
        """Add standard footer with date."""
        layout.add_space(8)
        layout.add_separator("line")
        layout.add_text(self._get_date_string(data), size=TextSize.TINY)
        layout.add_text("vnvnc.ru", size=TextSize.TINY)

    def _add_qr_section(
        self,
        layout: LabelLayout,
        data: Dict[str, Any],
        label: str = "СКАЧАТЬ:",
    ) -> bool:
        """Add QR code section if URL available. Returns True if added."""
        qr_url = data.get("qr_url") or data.get("short_url") or data.get("download_url")
        if not qr_url:
            return False

        layout.add_space(8)
        layout.add_separator("line")
        layout.add_text(label, size=TextSize.TINY, bold=True)
        layout.add_qr(qr_url, size=70)

        # Show short URL if available
        short_url = data.get("short_url")
        if short_url:
            layout.add_text(short_url, size=TextSize.TINY)

        return True

    # =========================================================================
    # Mode-specific label generators
    # =========================================================================

    def _create_fortune_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Fortune Teller mode."""
        layout = LabelLayout()
        self._create_header(layout, "🔮 ГАДАЛКА")

        # Caricature image
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            layout.add_image(caricature, width=380)
            layout.add_space(8)

        # Fortune text
        fortune = (
            data.get("fortune") or
            data.get("prediction") or
            data.get("display_text") or
            "Звёзды молчат..."
        )
        layout.add_text(fortune, size=TextSize.MEDIUM)

        # Details section
        details = []
        zodiac = data.get("zodiac_sign") or data.get("zodiac_ru")
        if zodiac:
            details.append(f"Знак: {zodiac}")
        lucky_color = data.get("lucky_color")
        if lucky_color:
            details.append(f"Цвет: {lucky_color}")

        if details:
            layout.add_space(6)
            for detail in details:
                layout.add_text(detail, size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_zodiac_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Zodiac mode."""
        layout = LabelLayout()

        # Zodiac sign header
        zodiac_ru = data.get("zodiac_ru", "Знак")
        zodiac_symbol = data.get("zodiac_symbol", "⭐")
        birthday = data.get("birthday", "")

        layout.add_text("VNVNC ARCADE", size=TextSize.SMALL)
        layout.add_space(4)
        layout.add_text(f"{zodiac_symbol} {zodiac_ru}", size=TextSize.TITLE, bold=True)

        if birthday:
            layout.add_text(f"({birthday})", size=TextSize.SMALL)

        layout.add_separator("dashes")
        layout.add_space(8)

        # Portrait if available
        portrait = self._coerce_image(data.get("caricature") or data.get("portrait"))
        if portrait:
            layout.add_image(portrait, width=360)
            layout.add_space(8)

        # Horoscope
        horoscope = data.get("horoscope", "Звёзды ждут...")
        layout.add_text(horoscope, size=TextSize.MEDIUM)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_ai_prophet_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for AI Prophet mode (flagship mode)."""
        layout = LabelLayout()
        self._create_header(layout, "🧙 ИИ ПРОРОК")

        # Caricature - large and prominent
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            layout.add_image(caricature, width=400)
            layout.add_space(10)

        # Prediction text
        prediction = (
            data.get("prediction") or
            data.get("display_text") or
            "Твоё будущее сияет..."
        )
        layout.add_text(prediction, size=TextSize.MEDIUM)

        # Lucky details
        lucky_number = data.get("lucky_number")
        lucky_color = data.get("lucky_color")
        if lucky_number or lucky_color:
            layout.add_space(6)
            if lucky_number:
                layout.add_text(f"Число: {lucky_number}", size=TextSize.TINY)
            if lucky_color:
                layout.add_text(f"Цвет: {lucky_color}", size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_roulette_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Roulette mode."""
        layout = LabelLayout()
        self._create_header(layout, "🎰 РУЛЕТКА")

        # Result - big and bold
        result = data.get("result", "???")
        layout.add_text(result, size=TextSize.HUGE, bold=True)

        # Category
        category = data.get("category", "")
        if category:
            layout.add_text(f"({category})", size=TextSize.SMALL)

        self._create_footer(layout, data)
        return layout

    def _create_quiz_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Quiz mode."""
        layout = LabelLayout()
        self._create_header(layout, "❓ ВИКТОРИНА")

        # Doodle image
        doodle = self._coerce_image(data.get("caricature"))
        if doodle:
            layout.add_image(doodle, width=360)
            layout.add_space(8)

        # Score
        score = data.get("score", 0)
        total = data.get("total", 0)
        layout.add_text(f"СЧЁТ: {score}/{total}", size=TextSize.LARGE, bold=True)

        percentage = data.get("percentage")
        if percentage is None and total > 0:
            percentage = int(score / total * 100)
        if percentage is not None:
            layout.add_text(f"{percentage}%", size=TextSize.MEDIUM)

        # Prize section
        if data.get("won_cocktail"):
            layout.add_space(10)
            layout.add_separator("double")
            layout.add_text("🍹 БЕСПЛАТНЫЙ", size=TextSize.LARGE, bold=True)
            layout.add_text("КОКТЕЙЛЬ!", size=TextSize.LARGE, bold=True)

            coupon = data.get("coupon_code")
            if coupon:
                layout.add_space(6)
                layout.add_text(f"КОД: {coupon}", size=TextSize.TITLE, bold=True)
                layout.add_text("Покажи бармену", size=TextSize.SMALL)

            layout.add_separator("double")

        # Rank
        rank = data.get("rank", "")
        if rank:
            layout.add_space(6)
            layout.add_text(rank, size=TextSize.SMALL)

        self._create_footer(layout, data)
        return layout

    def _create_squid_game_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Squid Game mode."""
        layout = LabelLayout()
        self._create_header(layout, "🦑 КАЛЬМАР")

        # Result status
        result = (data.get("result") or "").upper()
        if result:
            result_text = "🏆 ПОБЕДА" if result == "VICTORY" else "💀 ВЫБЫЛ" if result == "ELIMINATED" else result
            layout.add_text(result_text, size=TextSize.LARGE, bold=True)
            layout.add_space(8)

        # Sketch
        sketch = self._coerce_image(data.get("caricature") or data.get("sketch"))
        if sketch:
            layout.add_image(sketch, width=380)
            layout.add_space(8)

        # Coupon or message
        coupon = data.get("coupon_code")
        if coupon:
            layout.add_separator("double")
            layout.add_text(f"КОД: {coupon}", size=TextSize.TITLE, bold=True)
            layout.add_text("Покажи бармену", size=TextSize.SMALL)
            layout.add_separator("double")
        else:
            layout.add_text("Фото твоего бега!", size=TextSize.SMALL)

        # Stats
        reason = data.get("elimination_reason")
        if reason:
            layout.add_text(reason, size=TextSize.TINY)

        survived = data.get("survived_time")
        if survived:
            layout.add_text(f"Время: {survived}", size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_roast_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Roast mode."""
        layout = LabelLayout()
        self._create_header(layout, "🔥 ПРОЖАРКА")

        # Doodle
        doodle = self._coerce_image(data.get("doodle") or data.get("caricature"))
        if doodle:
            layout.add_image(doodle, width=380)
            layout.add_space(8)

        # Roast text
        roast_text = data.get("roast") or data.get("display_text") or ""
        if roast_text:
            layout.add_text(roast_text, size=TextSize.MEDIUM)

        # Vibe
        vibe = data.get("vibe")
        if vibe:
            layout.add_space(6)
            layout.add_text(f"Вайб: {vibe}", size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_autopsy_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Autopsy/Diagnosis mode."""
        layout = LabelLayout()
        self._create_header(layout, "🩻 ДИАГНОЗ")

        # X-ray scan
        scan_image = self._coerce_image(data.get("scan_image") or data.get("caricature"))
        if scan_image:
            layout.add_image(scan_image, width=380)
            layout.add_space(8)

        # Subject ID
        subject_id = data.get("id") or ""
        if subject_id:
            layout.add_text(f"ID: {subject_id}", size=TextSize.SMALL, bold=True)

        # Diagnosis
        diagnosis = data.get("diagnosis") or data.get("display_text") or ""
        if diagnosis:
            layout.add_text(diagnosis, size=TextSize.MEDIUM)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_photobooth_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Photobooth mode - optimized for photo stickers."""
        layout = LabelLayout(margin_y=12)  # Smaller margins for more photo space

        # Photo takes most of the space
        photo = self._coerce_image(data.get("caricature") or data.get("photo"))
        if photo:
            layout.add_image(photo, width=420)  # Nearly full width
            layout.add_space(6)

        layout.add_text("VNVNC ARCADE", size=TextSize.SMALL)

        # QR for download
        self._add_qr_section(layout, data, "📥 СКАЧАТЬ ФОТО:")

        layout.add_text(self._get_date_string(data), size=TextSize.TINY)
        return layout

    def _create_rapgod_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for RapGod mode."""
        layout = LabelLayout()
        self._create_header(layout, "🎤 RAP GOD")

        # Song title and artist
        song_title = data.get("song_title") or "Untitled"
        artist = data.get("artist") or "ARTIFACT AI"

        layout.add_text(song_title, size=TextSize.LARGE, bold=True)
        layout.add_text(artist, size=TextSize.SMALL)
        layout.add_space(6)

        # Genre and BPM
        genre = data.get("genre") or "trap"
        bpm = data.get("bpm") or 140
        layout.add_text(f"{genre.upper()} / {bpm} BPM", size=TextSize.TINY)
        layout.add_separator("line")
        layout.add_space(6)

        # Hook lyrics (max 4 lines)
        hook = data.get("hook") or ""
        if hook:
            layout.add_text("ПРИПЕВ:", size=TextSize.TINY, bold=True)
            lines = hook.split("\n")[:4]
            for line in lines:
                if line.strip():
                    layout.add_text(line.strip()[:35], size=TextSize.SMALL, alignment=Alignment.LEFT)
            layout.add_space(6)

        # One-liner
        one_liner = data.get("one_liner")
        if one_liner:
            layout.add_text(f'"{one_liner}"', size=TextSize.TINY)

        self._add_qr_section(layout, data, "🎵 СКАЧАТЬ ТРЕК:")
        self._create_footer(layout, data)
        return layout

    def _create_tower_stack_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Tower Stack game."""
        layout = LabelLayout()
        self._create_header(layout, "🏗️ БАШНЯ")

        # Score - big
        score = data.get("score", 0)
        layout.add_text(f"СЧЁТ: {score}", size=TextSize.HUGE, bold=True)

        # Stats
        height = data.get("height")
        max_streak = data.get("max_streak")
        difficulty = data.get("difficulty")

        layout.add_space(8)
        if height is not None:
            layout.add_text(f"Высота: {height}", size=TextSize.SMALL)
        if max_streak is not None:
            layout.add_text(f"Макс. серия: {max_streak}", size=TextSize.SMALL)
        if difficulty:
            layout.add_text(f"Сложность: {difficulty}", size=TextSize.SMALL)

        self._create_footer(layout, data)
        return layout

    def _create_brick_breaker_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Brick Breaker game."""
        layout = LabelLayout()
        self._create_header(layout, "🧱 КИРПИЧИ")

        # Score
        score = data.get("score", 0)
        layout.add_text(f"СЧЁТ: {score}", size=TextSize.HUGE, bold=True)

        # Stats
        level = data.get("level")
        max_combo = data.get("max_combo")
        lives = data.get("lives_remaining")
        win = data.get("win")

        layout.add_space(8)
        if level is not None:
            layout.add_text(f"Уровень: {level}", size=TextSize.SMALL)
        if max_combo is not None:
            layout.add_text(f"Комбо: x{max_combo}", size=TextSize.SMALL)
        if lives is not None:
            layout.add_text(f"Жизни: {lives}", size=TextSize.SMALL)
        if win is not None:
            outcome = "🏆 ПОБЕДА" if win else "💀 ПРОИГРЫШ"
            layout.add_text(outcome, size=TextSize.MEDIUM, bold=True)

        self._create_footer(layout, data)
        return layout

    def _create_video_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Video mode."""
        layout = LabelLayout()
        self._create_header(layout, "🎬 ВИДЕО")

        title = data.get("title") or data.get("media_name") or "Без названия"
        layout.add_text(title, size=TextSize.LARGE, bold=True)

        media_type = data.get("media_type")
        if media_type:
            type_map = {"VIDEO": "ВИДЕО", "IMAGE": "ФОТО", "GIF": "GIF"}
            layout.add_text(f"Тип: {type_map.get(str(media_type), str(media_type))}", size=TextSize.SMALL)

        index = data.get("index")
        total = data.get("total")
        if index is not None and total is not None:
            layout.add_text(f"Позиция: {index}/{total}", size=TextSize.SMALL)

        self._create_footer(layout, data)
        return layout

    def _create_guess_me_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Guess Me / Who Am I mode."""
        layout = LabelLayout()
        self._create_header(layout, "🎭 КТО Я?")

        title = data.get("title") or "Загадка"
        prediction = data.get("prediction") or ""

        layout.add_text(title, size=TextSize.LARGE, bold=True)
        if prediction:
            layout.add_space(6)
            layout.add_text(prediction, size=TextSize.MEDIUM)

        # Caricature
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            layout.add_space(8)
            layout.add_image(caricature, width=380)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_sorting_hat_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Sorting Hat (Harry Potter) mode.

        This is a key mode with:
        - Hogwarts house name (big and bold)
        - AI-generated portrait in house robes
        - House traits
        - QR code for download
        - Bracelet reminder
        """
        layout = LabelLayout()

        # Magic header
        layout.add_text("VNVNC ARCADE", size=TextSize.TINY)
        layout.add_text("🎩 РАСПРЕДЕЛЯЮЩАЯ", size=TextSize.MEDIUM, bold=True)
        layout.add_text("ШЛЯПА", size=TextSize.MEDIUM, bold=True)
        layout.add_separator("dashes")
        layout.add_space(6)

        # House name - BIG AND PROMINENT
        house_ru = data.get("house_name_ru") or data.get("house_ru") or data.get("house") or "Хогвартс"
        layout.add_text(house_ru.upper(), size=TextSize.TITLE, bold=True)

        # Animal
        animal_ru = data.get("animal_ru")
        if animal_ru:
            layout.add_text(f"({animal_ru})", size=TextSize.SMALL)

        layout.add_space(6)

        # Portrait - prominent
        portrait = self._coerce_image(data.get("caricature") or data.get("portrait"))
        if portrait:
            layout.add_image(portrait, width=380)
            layout.add_space(6)

        # House traits
        traits = data.get("traits", [])
        if traits:
            traits_text = ", ".join(traits[:3])
            layout.add_text(traits_text, size=TextSize.TINY)

        # Bracelet reminder
        layout.add_space(8)
        layout.add_separator("double")
        layout.add_text("ПОЛУЧИ СВОЙ", size=TextSize.MEDIUM, bold=True)
        layout.add_text("БРАСЛЕТ!", size=TextSize.MEDIUM, bold=True)
        layout.add_separator("double")

        # QR code
        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

    def _create_generic_label(self, mode_name: str, data: Dict[str, Any]) -> LabelLayout:
        """Create a generic label for any unknown mode."""
        layout = LabelLayout()
        self._create_header(layout, mode_name.upper())

        # Display text if available
        display_text = data.get("display_text") or data.get("result", "")
        if display_text:
            layout.add_text(display_text, size=TextSize.MEDIUM)

        # Image if available
        image = self._coerce_image(
            data.get("caricature") or
            data.get("portrait") or
            data.get("photo") or
            data.get("image")
        )
        if image:
            layout.add_space(8)
            layout.add_image(image, width=380)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data)
        return layout

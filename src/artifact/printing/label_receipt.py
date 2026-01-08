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
    BoxBlock,
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
        elif mode_name == "y2k":
            layout = self._create_y2k_label(data)
        elif mode_name == "bad_santa":
            layout = self._create_bad_santa_label(data)
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

    def _get_adaptive_text_size(self, text: str, has_image: bool = True) -> TextSize:
        """Pick font size based on text length to ensure ALL text fits.

        NEVER truncate text - always make it fit by using smaller font.
        Be aggressive about shrinking to prevent overflow.
        """
        text_len = len(text) if text else 0

        if has_image:
            # With image: very limited space - be aggressive
            if text_len <= 100:
                return TextSize.MEDIUM  # 24px - only for short text
            elif text_len <= 200:
                return TextSize.SMALL   # 18px - still readable
            else:
                return TextSize.TINY    # 14px - for medium/long text
        else:
            # No image: more space but still be careful
            if text_len <= 180:
                return TextSize.MEDIUM  # 24px
            elif text_len <= 350:
                return TextSize.SMALL   # 18px
            else:
                return TextSize.TINY    # 14px - for very long text

    def _get_adaptive_image_width(self, text: str, base_width: int = 280) -> int:
        """Shrink image when text is long to make room for all content.

        NEVER cut off text - reduce image size instead.
        Default to smaller images to prevent overflow.
        """
        text_len = len(text) if text else 0

        if text_len <= 120:
            return base_width          # Full size image
        elif text_len <= 200:
            return int(base_width * 0.85)  # 15% smaller
        elif text_len <= 300:
            return int(base_width * 0.70)  # 30% smaller
        else:
            return int(base_width * 0.55)  # 45% smaller for long text

    def _create_header(self, layout: LabelLayout, title: str, style: str = "standard") -> None:
        """Add stylish header with title.

        Args:
            layout: The layout to add to
            title: Main title text
            style: Header style - "standard", "mystical", "game", "prize"
        """
        if style == "mystical":
            # Mystical style for fortune/zodiac/prophet
            layout.add_separator("stars")
            layout.add_text(title, size=TextSize.TITLE, bold=True)
            layout.add_separator("fancy")
            layout.add_space(4)
        elif style == "game":
            # Game style for quiz/squid/games
            layout.add_text("▶ VNVNC ARCADE ◀", size=TextSize.SMALL, bold=True)
            layout.add_text(title, size=TextSize.TITLE, bold=True)
            layout.add_separator("arrows")
            layout.add_space(4)
        elif style == "prize":
            # Prize style for winners
            layout.add_separator("stars")
            layout.add_text("★ VNVNC ARCADE ★", size=TextSize.SMALL, bold=True)
            layout.add_text(title, size=TextSize.TITLE, bold=True)
            layout.add_separator("stars")
            layout.add_space(4)
        else:
            # Standard style
            layout.add_text("VNVNC ARCADE", size=TextSize.SMALL)
            layout.add_text(title, size=TextSize.TITLE, bold=True)
            layout.add_separator("double")
            layout.add_space(6)

    def _create_footer(self, layout: LabelLayout, data: Dict[str, Any], style: str = "standard") -> None:
        """Add stylish footer with date.

        Args:
            layout: The layout to add to
            data: Mode data (for timestamp)
            style: Footer style - "standard", "mystical", "minimal"
        """
        if style == "mystical":
            layout.add_space(4)
            layout.add_separator("fancy")
            layout.add_text(self._get_date_string(data), size=TextSize.TINY)
            layout.add_text("vnvnc.ru", size=TextSize.TINY)
        elif style == "minimal":
            layout.add_space(4)
            layout.add_text(self._get_date_string(data), size=TextSize.TINY)
            layout.add_text("vnvnc.ru", size=TextSize.TINY)
        else:
            layout.add_space(6)
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

        layout.add_space(4)
        layout.add_separator("line")
        layout.add_text(label, size=TextSize.TINY, bold=True)
        layout.add_qr(qr_url, size=80)  # Compact QR for better fit

        # Show short URL if available
        short_url = data.get("short_url")
        if short_url:
            layout.add_text(short_url, size=TextSize.TINY)

        return True

    # =========================================================================
    # Mode-specific label generators
    # =========================================================================

    def _create_fortune_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Fortune Teller mode - mystical design with full border."""
        layout = LabelLayout(page_border="double")
        self._create_header(layout, "🔮 ГАДАЛКА", style="mystical")

        # Get fortune text first to determine adaptive sizing
        fortune = (
            data.get("fortune") or
            data.get("prediction") or
            data.get("display_text") or
            "Звёзды молчат..."
        )
        has_image = bool(data.get("caricature"))

        # Caricature image - adaptive size based on text length
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            img_width = self._get_adaptive_image_width(fortune, base_width=320)
            layout.add_image(caricature, width=img_width)
            layout.add_space(4)

        # Fortune text in a nice box
        layout.add_separator("wave")
        text_size = self._get_adaptive_text_size(fortune, has_image=has_image)
        layout.add_text(fortune, size=text_size)
        layout.add_separator("wave")

        # Details section with better formatting
        zodiac = data.get("zodiac_sign") or data.get("zodiac_ru")
        lucky_color = data.get("lucky_color")
        if zodiac or lucky_color:
            layout.add_space(2)
            if zodiac:
                layout.add_text(f"☆ {zodiac} ☆", size=TextSize.SMALL, bold=True)
            if lucky_color:
                layout.add_text(f"Счастливый цвет: {lucky_color}", size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="mystical")
        return layout

    def _create_zodiac_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Zodiac mode - celestial design with stars border."""
        layout = LabelLayout(page_border="stars")

        # Get horoscope text first to determine adaptive sizing
        horoscope = data.get("horoscope", "Звёзды ждут...")
        has_image = bool(data.get("caricature") or data.get("portrait"))

        # Zodiac sign header - compact
        zodiac_ru = data.get("zodiac_ru", "Знак")
        zodiac_symbol = data.get("zodiac_symbol", "⭐")
        birthday = data.get("birthday", "")

        layout.add_text(f"{zodiac_symbol} {zodiac_ru.upper()} {zodiac_symbol}", size=TextSize.MEDIUM, bold=True)
        if birthday:
            layout.add_text(f"ДР: {birthday}", size=TextSize.TINY)

        # Portrait - smaller
        portrait = self._coerce_image(data.get("caricature") or data.get("portrait"))
        if portrait:
            img_width = self._get_adaptive_image_width(horoscope, base_width=220)
            layout.add_image(portrait, width=img_width)
            layout.add_space(2)

        # Horoscope
        text_size = self._get_adaptive_text_size(horoscope, has_image=has_image)
        layout.add_text(horoscope, size=text_size)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="mystical")
        return layout

    def _create_ai_prophet_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for AI Prophet mode (flagship mode) - mystical design."""
        layout = LabelLayout(page_border="ornate")
        self._create_header(layout, "🧙 ИИ ПРОРОК", style="mystical")

        # Get prediction text first to determine adaptive sizing
        prediction = (
            data.get("prediction") or
            data.get("display_text") or
            "Твоё будущее сияет..."
        )
        has_image = bool(data.get("caricature"))

        # Caricature - adaptive size based on text length
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            img_width = self._get_adaptive_image_width(prediction, base_width=260)
            layout.add_image(caricature, width=img_width)
            layout.add_space(4)

        # Prediction text with elegant framing
        layout.add_separator("wave")
        text_size = self._get_adaptive_text_size(prediction, has_image=has_image)
        layout.add_text(prediction, size=text_size)
        layout.add_separator("wave")

        # Lucky details in styled format
        lucky_number = data.get("lucky_number")
        lucky_color = data.get("lucky_color")
        if lucky_number or lucky_color:
            layout.add_space(2)
            if lucky_number and lucky_color:
                layout.add_text(f"✦ {lucky_number} ✦ {lucky_color} ✦", size=TextSize.TINY)
            elif lucky_number:
                layout.add_text(f"✦ Число: {lucky_number} ✦", size=TextSize.TINY)
            elif lucky_color:
                layout.add_text(f"✦ Цвет: {lucky_color} ✦", size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="mystical")
        return layout

    def _create_roulette_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Roulette mode - casino ticket style with solid border."""
        layout = LabelLayout(page_border="solid")

        # Casino-style header
        layout.add_separator("stars")
        layout.add_text("🎰 РУЛЕТКА 🎰", size=TextSize.TITLE, bold=True)
        layout.add_separator("stars")
        layout.add_space(4)

        # Result in a fancy box
        result = data.get("result", "???")
        box = layout.add_box(border_style="ornate", padding=8, title="РЕЗУЛЬТАТ")
        box.content_blocks.append(TextBlock(result, size=TextSize.LARGE, bold=True))

        # Category with styling
        category = data.get("category", "")
        if category:
            layout.add_space(4)
            layout.add_text(f"✦ {category} ✦", size=TextSize.SMALL)

        layout.add_separator("fancy")
        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_quiz_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Quiz mode - game style with prize highlight and double border."""
        layout = LabelLayout(page_border="double")

        # Check if winner for special prize styling
        won_cocktail = data.get("won_cocktail", False)
        header_style = "prize" if won_cocktail else "game"
        self._create_header(layout, "❓ ВИКТОРИНА", style=header_style)

        # Doodle image - smaller to fit
        doodle = self._coerce_image(data.get("caricature"))
        if doodle:
            layout.add_image(doodle, width=220)
            layout.add_space(4)

        # Score display
        score = data.get("score", 0)
        total = data.get("total", 0)
        percentage = data.get("percentage")
        if percentage is None and total > 0:
            percentage = int(score / total * 100)

        layout.add_text(f"СЧЁТ: {score}/{total}", size=TextSize.MEDIUM, bold=True)
        if percentage is not None:
            layout.add_text(f"▶ {percentage}% ◀", size=TextSize.SMALL, bold=True)

        # Prize section - compact but visible
        if won_cocktail:
            layout.add_space(4)
            layout.add_separator("stars")
            layout.add_text("🍹 КОКТЕЙЛЬ! 🍹", size=TextSize.MEDIUM, bold=True)

            coupon = data.get("coupon_code")
            if coupon:
                box = layout.add_box(border_style="double", padding=6, title="КОД")
                box.content_blocks.append(TextBlock(coupon, size=TextSize.LARGE, bold=True))
                box.content_blocks.append(TextBlock("Покажи бармену!", size=TextSize.TINY))

        # Rank
        rank = data.get("rank", "")
        if rank:
            layout.add_text(rank, size=TextSize.TINY, bold=True)

        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_squid_game_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Squid Game mode - dramatic game style with solid border."""
        layout = LabelLayout(page_border="solid")

        # Determine win/lose for styling
        result = (data.get("result") or "").upper()
        is_victory = result == "VICTORY"
        header_style = "prize" if is_victory else "game"
        self._create_header(layout, "🦑 КАЛЬМАР", style=header_style)

        # Result status - compact
        if result:
            if is_victory:
                layout.add_text("🏆 ПОБЕДА! 🏆", size=TextSize.MEDIUM, bold=True)
            else:
                layout.add_text("💀 ВЫБЫЛ 💀", size=TextSize.MEDIUM, bold=True)

        # Sketch - smaller
        sketch = self._coerce_image(data.get("caricature") or data.get("sketch"))
        if sketch:
            layout.add_image(sketch, width=220)
            layout.add_space(2)

        # Prize coupon in compact box (if winner)
        coupon = data.get("coupon_code")
        if coupon:
            box = layout.add_box(border_style="double", padding=6, title="ПРИЗ")
            box.content_blocks.append(TextBlock(coupon, size=TextSize.LARGE, bold=True))
            box.content_blocks.append(TextBlock("Покажи бармену!", size=TextSize.TINY))

        # Stats section - compact
        reason = data.get("elimination_reason")
        survived = data.get("survived_time")
        if survived:
            layout.add_text(f"⏱ {survived}", size=TextSize.TINY)
        if reason:
            layout.add_text(reason, size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_roast_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Roast mode - fiery design with wave border."""
        layout = LabelLayout(page_border="solid")

        # Fire-themed header
        layout.add_separator("wave")
        layout.add_text("🔥 ПРОЖАРКА 🔥", size=TextSize.LARGE, bold=True)
        layout.add_separator("wave")

        # Get roast text first to determine adaptive sizing
        roast_text = data.get("roast") or data.get("display_text") or ""
        has_image = bool(data.get("doodle") or data.get("caricature"))

        # Doodle - smaller
        doodle = self._coerce_image(data.get("doodle") or data.get("caricature"))
        if doodle:
            img_width = self._get_adaptive_image_width(roast_text, base_width=240)
            layout.add_image(doodle, width=img_width)
            layout.add_space(2)

        # Roast text
        if roast_text:
            text_size = self._get_adaptive_text_size(roast_text, has_image=has_image)
            layout.add_text(roast_text, size=text_size)

        # Vibe - compact
        vibe = data.get("vibe")
        if vibe:
            layout.add_text(f"✨ {vibe} ✨", size=TextSize.TINY, bold=True)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_autopsy_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Autopsy/Diagnosis mode - medical report style with double border."""
        layout = LabelLayout(page_border="double")

        # Medical report header
        layout.add_text("🩻 ДИАГНОЗ", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")

        # Get diagnosis text first to determine adaptive sizing
        diagnosis = data.get("diagnosis") or data.get("display_text") or ""
        has_image = bool(data.get("scan_image") or data.get("caricature"))

        # Subject ID - compact
        subject_id = data.get("id") or ""
        if subject_id:
            layout.add_text(f"📋 {subject_id}", size=TextSize.TINY, bold=True)

        # X-ray scan - smaller
        scan_image = self._coerce_image(data.get("scan_image") or data.get("caricature"))
        if scan_image:
            img_width = self._get_adaptive_image_width(diagnosis, base_width=240)
            layout.add_image(scan_image, width=img_width)
            layout.add_space(2)

        # Diagnosis text
        if diagnosis:
            text_size = self._get_adaptive_text_size(diagnosis, has_image=has_image)
            layout.add_text(diagnosis, size=text_size)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_photobooth_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Photobooth mode - elegant photo sticker with ornate border."""
        layout = LabelLayout(margin_y=12, page_border="ornate")

        # Photo takes most of the space
        photo = self._coerce_image(data.get("caricature") or data.get("photo"))
        if photo:
            layout.add_image(photo, width=380)
            layout.add_space(4)

        # Minimal branding
        layout.add_text("📸 VNVNC", size=TextSize.SMALL, bold=True)

        # QR for download
        self._add_qr_section(layout, data, "СКАЧАТЬ:")

        layout.add_text(self._get_date_string(data), size=TextSize.TINY)
        return layout

    def _create_rapgod_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for RapGod mode - hip-hop record style with solid border."""
        layout = LabelLayout(page_border="solid")

        # Hip-hop style header
        layout.add_text("🎤 RAP GOD 🎤", size=TextSize.LARGE, bold=True)
        layout.add_separator("wave")

        # Song title and artist - compact
        song_title = data.get("song_title") or "Untitled"
        artist = data.get("artist") or "AI"

        layout.add_text(song_title, size=TextSize.MEDIUM, bold=True)
        layout.add_text(f"by {artist}", size=TextSize.TINY)

        # Genre and BPM - compact
        genre = data.get("genre") or "trap"
        bpm = data.get("bpm") or 140
        layout.add_text(f"🔊 {genre.upper()} • {bpm} BPM", size=TextSize.TINY, bold=True)

        # Hook lyrics - compact
        hook = data.get("hook") or ""
        if hook:
            layout.add_separator("dots")
            lines = hook.split("\n")[:3]  # Max 3 lines
            for line in lines:
                if line.strip():
                    layout.add_text(f"» {line.strip()[:28]}", size=TextSize.TINY, alignment=Alignment.LEFT)

        # One-liner quote
        one_liner = data.get("one_liner")
        if one_liner:
            layout.add_text(f'"{one_liner[:35]}"', size=TextSize.TINY)

        self._add_qr_section(layout, data, "🎵 ТРЕК:")
        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_tower_stack_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Tower Stack game - arcade score card style with double border."""
        layout = LabelLayout(page_border="double")
        self._create_header(layout, "🏗️ БАШНЯ", style="game")

        # Score display
        score = data.get("score", 0)
        layout.add_text(str(score), size=TextSize.HUGE, bold=True)

        # Stats section - compact
        height = data.get("height")
        max_streak = data.get("max_streak")
        difficulty = data.get("difficulty")

        layout.add_separator("arrows")

        if height is not None:
            layout.add_text(f"🏢 Высота: {height}", size=TextSize.TINY)
        if max_streak is not None:
            layout.add_text(f"🔥 Серия: {max_streak}", size=TextSize.TINY)
        if difficulty:
            layout.add_text(f"⚡ {difficulty}", size=TextSize.TINY)

        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_brick_breaker_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Brick Breaker game - retro arcade style with double border."""
        layout = LabelLayout(page_border="double")

        # Check if winner for special styling
        win = data.get("win")
        header_style = "prize" if win else "game"
        self._create_header(layout, "🧱 КИРПИЧИ", style=header_style)

        # Score display
        score = data.get("score", 0)
        layout.add_text(str(score), size=TextSize.HUGE, bold=True)

        # Win/Lose status - compact
        if win is not None:
            outcome = "🏆 ПОБЕДА!" if win else "💀 GAME OVER"
            layout.add_text(outcome, size=TextSize.MEDIUM, bold=True)

        # Stats section - compact
        level = data.get("level")
        max_combo = data.get("max_combo")
        lives = data.get("lives_remaining")

        layout.add_separator("dots")
        if level is not None:
            layout.add_text(f"📊 Уровень: {level}", size=TextSize.TINY)
        if max_combo is not None:
            layout.add_text(f"🔥 Комбо: x{max_combo}", size=TextSize.TINY)
        if lives is not None:
            layout.add_text(f"❤️ Жизни: {lives}", size=TextSize.TINY)

        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_video_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Video mode - film ticket style with solid border."""
        layout = LabelLayout(page_border="solid")

        # Film-style header
        layout.add_text("🎬 ВИДЕО 🎬", size=TextSize.LARGE, bold=True)
        layout.add_separator("dots")

        # Title
        title = data.get("title") or data.get("media_name") or "Без названия"
        layout.add_text(title, size=TextSize.MEDIUM, bold=True)

        # Media details - compact
        media_type = data.get("media_type")
        if media_type:
            type_map = {"VIDEO": "🎥 ВИДЕО", "IMAGE": "🖼 ФОТО", "GIF": "✨ GIF"}
            layout.add_text(type_map.get(str(media_type), str(media_type)), size=TextSize.TINY)

        index = data.get("index")
        total = data.get("total")
        if index is not None and total is not None:
            layout.add_text(f"📍 {index} из {total}", size=TextSize.TINY)

        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_guess_me_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Guess Me / Who Am I mode - mysterious style with ornate border."""
        layout = LabelLayout(page_border="ornate")

        # Mysterious header
        layout.add_text("🎭 КТО Я? 🎭", size=TextSize.LARGE, bold=True)
        layout.add_separator("fancy")

        title = data.get("title") or "Загадка"
        prediction = data.get("prediction") or ""
        has_image = bool(data.get("caricature"))

        # Title
        layout.add_text(title, size=TextSize.MEDIUM, bold=True)

        # Caricature - smaller, before prediction
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            img_width = self._get_adaptive_image_width(prediction, base_width=220)
            layout.add_image(caricature, width=img_width)
            layout.add_space(2)

        # Prediction text
        if prediction:
            text_size = self._get_adaptive_text_size(prediction, has_image=has_image)
            layout.add_text(prediction, size=text_size)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="mystical")
        return layout

    def _create_sorting_hat_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Sorting Hat mode - magical style with stars border."""
        layout = LabelLayout(margin_y=12, page_border="stars")

        # Magical header
        layout.add_text("🎩 ШЛЯПА", size=TextSize.LARGE, bold=True)

        # House name
        house_ru = data.get("house_name_ru") or data.get("house_ru") or data.get("house") or "Хогвартс"
        animal_ru = data.get("animal_ru")

        layout.add_text(house_ru.upper(), size=TextSize.MEDIUM, bold=True)
        if animal_ru:
            layout.add_text(f"({animal_ru})", size=TextSize.TINY)

        # Portrait - compact
        portrait = self._coerce_image(data.get("caricature") or data.get("portrait"))
        if portrait:
            layout.add_image(portrait, width=200)

        # House traits - compact
        traits = data.get("traits", [])
        if traits:
            traits_text = " ✦ ".join(traits[:3])
            layout.add_text(traits_text, size=TextSize.TINY)

        # Bracelet reminder - compact
        layout.add_text("🎁 БРАСЛЕТ! 🎁", size=TextSize.SMALL, bold=True)

        # QR code
        qr_url = data.get("qr_url") or data.get("short_url")
        if qr_url:
            layout.add_qr(qr_url, size=70)

        layout.add_text(self._get_date_string(data), size=TextSize.TINY)
        return layout

    def _create_y2k_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Y2K (2000s) mode - retro millennium style with double border."""
        layout = LabelLayout(page_border="double")

        # Retro 2000s header with CRT vibes
        layout.add_text("💿 НУЛЕВЫЕ 💿", size=TextSize.LARGE, bold=True)
        layout.add_separator("wave")

        # Get archetype/character description
        archetype = data.get("archetype") or data.get("character_type") or ""
        description = data.get("description") or data.get("display_text") or ""
        has_image = bool(data.get("caricature"))

        # Score display
        score = data.get("score")
        total = data.get("total")
        if score is not None and total is not None:
            percentage = int(score / total * 100) if total > 0 else 0
            layout.add_text(f"СЧЁТ: {score}/{total} ({percentage}%)", size=TextSize.SMALL, bold=True)

        # Archetype title
        if archetype:
            layout.add_text(archetype, size=TextSize.MEDIUM, bold=True)

        # 2000s character portrait - adaptive size
        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            img_width = self._get_adaptive_image_width(description, base_width=260)
            layout.add_image(caricature, width=img_width)
            layout.add_space(4)

        # Character description
        if description:
            layout.add_separator("dots")
            text_size = self._get_adaptive_text_size(description, has_image=has_image)
            layout.add_text(description, size=text_size)

        # Category scores (if available)
        category_scores = data.get("category_scores")
        if category_scores:
            layout.add_space(2)
            top_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)[:3]
            cats_text = " • ".join([f"{cat}" for cat, _ in top_categories])
            layout.add_text(cats_text, size=TextSize.TINY)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_bad_santa_label(self, data: Dict[str, Any]) -> LabelLayout:
        """Create label for Bad Santa mode - naughty/nice verdict with prize code."""
        # Determine verdict for styling
        verdict = data.get("verdict") or data.get("result") or "NICE"
        is_winner = verdict.upper() in ["NICE", "ПОДАРОК ЗАСЛУЖЕН", "WINNER"]
        border_style = "stars" if is_winner else "solid"
        layout = LabelLayout(page_border=border_style)

        # Bad Santa header with adult vibes
        layout.add_text("🎅 ПЛОХОЙ САНТА 🎅", size=TextSize.LARGE, bold=True)
        layout.add_separator("wave")

        # Score display
        nice_score = data.get("nice_score")
        if nice_score is not None:
            percentage = int(nice_score * 100) if nice_score <= 1 else int(nice_score)
            layout.add_text(f"ХОРОШИЙ НА {percentage}%", size=TextSize.SMALL, bold=True)

        # Verdict portrait - adaptive size
        verdict_text = data.get("verdict_text") or data.get("display_text") or ""
        has_image = bool(data.get("caricature"))

        caricature = self._coerce_image(data.get("caricature"))
        if caricature:
            img_width = self._get_adaptive_image_width(verdict_text, base_width=240)
            layout.add_image(caricature, width=img_width)
            layout.add_space(4)

        # Verdict result - big and bold
        if is_winner:
            layout.add_text("🎁 ПОДАРОК ЗАСЛУЖЕН! 🎁", size=TextSize.MEDIUM, bold=True)
        else:
            layout.add_text("💀 УГОЛЬ ТЕБЕ! 💀", size=TextSize.MEDIUM, bold=True)

        # Verdict text/roast
        if verdict_text:
            layout.add_separator("dots")
            text_size = self._get_adaptive_text_size(verdict_text, has_image=has_image)
            layout.add_text(verdict_text, size=text_size)

        # Prize coupon (only for winners)
        coupon = data.get("coupon_code")
        if coupon and is_winner:
            layout.add_space(4)
            layout.add_separator("stars")
            layout.add_text("🍹 БЕСПЛАТНЫЙ ШОТ! 🍹", size=TextSize.MEDIUM, bold=True)
            box = layout.add_box(border_style="double", padding=6, title="КОД")
            box.content_blocks.append(TextBlock(coupon, size=TextSize.LARGE, bold=True))
            box.content_blocks.append(TextBlock("Покажи бармену!", size=TextSize.TINY))

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="minimal")
        return layout

    def _create_generic_label(self, mode_name: str, data: Dict[str, Any]) -> LabelLayout:
        """Create a generic label for any unknown mode - clean versatile design with solid border."""
        layout = LabelLayout(page_border="solid")

        # Clean header
        layout.add_text(mode_name.upper(), size=TextSize.LARGE, bold=True)
        layout.add_separator("fancy")

        # Get display text first to determine adaptive sizing
        display_text = data.get("display_text") or data.get("result", "")
        has_image = bool(
            data.get("caricature") or
            data.get("portrait") or
            data.get("photo") or
            data.get("image")
        )

        # Image - compact, before text
        image = self._coerce_image(
            data.get("caricature") or
            data.get("portrait") or
            data.get("photo") or
            data.get("image")
        )
        if image:
            img_width = self._get_adaptive_image_width(display_text, base_width=220)
            layout.add_image(image, width=img_width)
            layout.add_space(2)

        # Display text - adaptive font size to fit ALL text
        if display_text:
            text_size = self._get_adaptive_text_size(display_text, has_image=has_image)
            layout.add_text(display_text, size=text_size)

        self._add_qr_section(layout, data)
        self._create_footer(layout, data, style="minimal")
        return layout

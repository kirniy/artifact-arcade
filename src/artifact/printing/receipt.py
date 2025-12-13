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
        else:
            layout = self._create_generic_receipt(mode_name, data)

        # Render to commands
        raw_commands = self._layout_engine.render(layout)

        # Generate preview
        preview = self._layout_engine.preview_text(layout)

        return Receipt(
            mode_name=mode_name,
            layout=layout,
            raw_commands=raw_commands,
            preview=preview,
            timestamp=datetime.now(),
        )

    def _create_header(self, layout: ReceiptLayout) -> None:
        """Add standard ARTIFACT header to layout."""
        # Logo if available
        if self._logo_data:
            layout.add_image(self._logo_data, width=256, dither=True)
            layout.add_space(1)
        else:
            # Text logo fallback
            layout.add_text("* ARTIFACT *", size=TextSize.LARGE, bold=True)
            layout.add_text("Fortune Machine", size=TextSize.SMALL)

        layout.add_separator("double")
        layout.add_space(1)

    def _create_footer(self, layout: ReceiptLayout) -> None:
        """Add standard footer with date/time."""
        layout.add_space(1)
        layout.add_separator("line")

        # Date and time
        now = datetime.now()
        date_str = now.strftime("%d.%m.%Y %H:%M")
        layout.add_text(date_str, size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_text("artifact-arcade.com", size=TextSize.SMALL)
        layout.add_space(2)

    def _create_fortune_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Fortune Teller mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        # Fortune title
        layout.add_text("YOUR FORTUNE", size=TextSize.MEDIUM, bold=True)
        layout.add_separator("stars")
        layout.add_space(1)

        # Fortune text
        fortune = data.get("fortune", "The stars are silent...")
        layout.add_text(fortune, size=TextSize.MEDIUM)

        layout.add_space(1)
        layout.add_separator("stars")

        self._create_footer(layout)
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
        layout.add_text(horoscope, size=TextSize.MEDIUM)

        layout.add_space(1)
        layout.add_separator("stars")

        self._create_footer(layout)
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

        # AI Prophet title
        layout.add_text("AI PROPHECY", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        # Caricature image (if available)
        caricature = data.get("caricature")
        if caricature:
            layout.add_image(caricature, width=300, dither=True)
            layout.add_space(1)

        layout.add_separator("stars")
        layout.add_space(1)

        # Prediction
        prediction = data.get("prediction", "Your future is bright...")
        layout.add_text(prediction, size=TextSize.MEDIUM)

        layout.add_space(1)

        # Lucky number and color
        lucky_number = data.get("lucky_number")
        lucky_color = data.get("lucky_color")

        if lucky_number:
            layout.add_text(f"Lucky Number: {lucky_number}", size=TextSize.SMALL)

        if lucky_color:
            layout.add_text(f"Lucky Color: {lucky_color}", size=TextSize.SMALL)

        # Personality traits
        traits = data.get("traits", [])
        if traits:
            layout.add_space(1)
            layout.add_text("Your Traits:", size=TextSize.SMALL)
            layout.add_text(", ".join(traits[:3]), size=TextSize.SMALL)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout)
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

        self._create_footer(layout)
        return layout

    def _create_quiz_receipt(self, data: Dict[str, Any]) -> ReceiptLayout:
        """Create receipt for Quiz mode."""
        layout = ReceiptLayout()
        self._create_header(layout)

        layout.add_text("QUIZ RESULTS", size=TextSize.LARGE, bold=True)
        layout.add_separator("double")
        layout.add_space(1)

        # Score
        score = data.get("score", 0)
        total = data.get("total", 0)
        layout.add_text(f"Score: {score}/{total}", size=TextSize.LARGE, bold=True)

        # Percentage
        if total > 0:
            percentage = int(score / total * 100)
            layout.add_text(f"{percentage}%", size=TextSize.MEDIUM)

        # Rank
        rank = data.get("rank", "")
        if rank:
            layout.add_space(1)
            layout.add_text(rank, size=TextSize.MEDIUM)

        layout.add_space(1)
        layout.add_separator("double")

        self._create_footer(layout)
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
            layout.add_text(display_text, size=TextSize.MEDIUM)

        layout.add_space(1)
        layout.add_separator("line")

        self._create_footer(layout)
        return layout

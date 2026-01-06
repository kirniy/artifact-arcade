"""Layout engine for thermal printer receipts.

Handles text formatting, image positioning, and receipt composition
for the EM5820 thermal printer (58mm paper width, ~384 pixels).
"""

import logging
from typing import List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO

logger = logging.getLogger(__name__)


class Alignment(Enum):
    """Text alignment options."""

    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class TextSize(Enum):
    """Text size options (printer-specific)."""

    SMALL = 1      # Normal size
    MEDIUM = 2     # Double height
    LARGE = 3      # Double width + height
    TITLE = 4      # Triple size for headers


@dataclass
class TextBlock:
    """A block of text for the receipt."""

    text: str
    alignment: Alignment = Alignment.CENTER
    size: TextSize = TextSize.SMALL
    bold: bool = False
    underline: bool = False
    inverted: bool = False  # White on black


@dataclass
class ImageBlock:
    """An image block for the receipt."""

    image_data: bytes
    width: int = 384  # Full width
    height: Optional[int] = None  # Auto from aspect ratio
    dither: bool = True  # Apply dithering for better quality
    alignment: Alignment = Alignment.CENTER


@dataclass
class SeparatorBlock:
    """A visual separator line."""

    style: str = "line"  # line, dashes, dots, stars
    thickness: int = 1


@dataclass
class SpacerBlock:
    """Vertical spacing."""

    lines: int = 1


@dataclass
class ReceiptLayout:
    """Complete receipt layout definition."""

    blocks: List[Union[TextBlock, ImageBlock, SeparatorBlock, SpacerBlock]] = field(default_factory=list)
    paper_width: int = 384  # pixels (58mm paper)
    margin: int = 8  # pixels on each side

    def add_text(
        self,
        text: str,
        alignment: Alignment = Alignment.CENTER,
        size: TextSize = TextSize.SMALL,
        bold: bool = False,
        underline: bool = False,
    ) -> "ReceiptLayout":
        """Add a text block."""
        self.blocks.append(TextBlock(
            text=text,
            alignment=alignment,
            size=size,
            bold=bold,
            underline=underline,
        ))
        return self

    def add_image(
        self,
        image_data: bytes,
        width: int = 384,
        dither: bool = True,
    ) -> "ReceiptLayout":
        """Add an image block."""
        self.blocks.append(ImageBlock(
            image_data=image_data,
            width=width,
            dither=dither,
        ))
        return self

    def add_separator(self, style: str = "line") -> "ReceiptLayout":
        """Add a separator line."""
        self.blocks.append(SeparatorBlock(style=style))
        return self

    def add_space(self, lines: int = 1) -> "ReceiptLayout":
        """Add vertical spacing."""
        self.blocks.append(SpacerBlock(lines=lines))
        return self


class LayoutEngine:
    """Engine for rendering receipt layouts to printer commands.

    Converts ReceiptLayout to ESC/POS commands for thermal printer,
    with support for Russian text via image rendering (for Chinese printers).
    """

    # ESC/POS command constants
    ESC = b'\x1b'
    GS = b'\x1d'
    LF = b'\x0a'

    # Character sets
    CHARSET_CP866 = b'\x1b\x74\x11'  # Russian CP866

    # Render text as images for Chinese printers (fixes Russian + upside-down)
    RENDER_TEXT_AS_IMAGE = True
    ROTATE_180 = True  # For upside-down mounted printers

    def __init__(self, paper_width: int = 384):
        self.paper_width = paper_width
        self.char_width = 12  # Approximate character width in pixels
        self._font = None  # Cached font for text rendering

    def _size_width_multiplier(self, size: TextSize) -> int:
        """Get width multiplier for text size."""
        return {
            TextSize.SMALL: 1,
            TextSize.MEDIUM: 1,
            TextSize.LARGE: 2,
            TextSize.TITLE: 3,
        }.get(size, 1)

    def _max_chars(self, size: TextSize) -> int:
        """Maximum characters per line for a given text size."""
        base = max(1, self.paper_width // self.char_width)
        return max(1, base // self._size_width_multiplier(size))

    def _wrap_text(self, text: str, max_chars: int) -> List[str]:
        """Wrap text to fit within the given width."""
        if max_chars <= 0:
            return [text] if text else [""]

        lines: List[str] = []
        raw_lines = text.splitlines() or [""]

        for raw in raw_lines:
            leading = len(raw) - len(raw.lstrip(" "))
            prefix = " " * leading
            content = raw.lstrip(" ")
            words = content.split()
            if not words:
                lines.append(raw)
                continue

            max_width = max(1, max_chars - leading)
            current = ""
            for word in words:
                if len(word) > max_width:
                    if current:
                        lines.append(prefix + current)
                        current = ""
                    while len(word) > max_width:
                        lines.append(prefix + word[:max_width])
                        word = word[max_width:]
                    current = word
                    continue

                if not current:
                    current = word
                elif len(current) + 1 + len(word) <= max_width:
                    current = f"{current} {word}"
                else:
                    lines.append(prefix + current)
                    current = word

            if current:
                lines.append(prefix + current)

        return lines

    def render(self, layout: ReceiptLayout) -> bytes:
        """Render a receipt layout to printer commands.

        Args:
            layout: The receipt layout to render

        Returns:
            ESC/POS command bytes ready to send to printer
        """
        commands = []

        # Initialize printer
        commands.append(self._cmd_init())
        commands.append(self.CHARSET_CP866)

        # When rotating 180°, reverse block order so receipt reads correctly
        # (first block becomes last when paper is flipped)
        blocks = list(reversed(layout.blocks)) if self.ROTATE_180 else layout.blocks

        for block in blocks:
            if isinstance(block, TextBlock):
                commands.append(self._render_text(block))
            elif isinstance(block, ImageBlock):
                commands.append(self._render_image(block))
            elif isinstance(block, SeparatorBlock):
                commands.append(self._render_separator(block))
            elif isinstance(block, SpacerBlock):
                commands.append(self._render_spacer(block))

        # Cut paper (partial cut)
        commands.append(self._cmd_cut())

        return b''.join(commands)

    def _cmd_init(self) -> bytes:
        """Initialize printer command."""
        return self.ESC + b'@'

    def _cmd_cut(self) -> bytes:
        """Partial paper cut command."""
        return self.GS + b'V' + b'\x01'

    def _cmd_align(self, alignment: Alignment) -> bytes:
        """Set text alignment."""
        align_byte = {
            Alignment.LEFT: b'\x00',
            Alignment.CENTER: b'\x01',
            Alignment.RIGHT: b'\x02',
        }
        return self.ESC + b'a' + align_byte.get(alignment, b'\x00')

    def _cmd_text_size(self, size: TextSize) -> bytes:
        """Set text size."""
        # GS ! n - Select character size
        size_byte = {
            TextSize.SMALL: b'\x00',   # Normal
            TextSize.MEDIUM: b'\x01',  # Double height
            TextSize.LARGE: b'\x11',   # Double width + height
            TextSize.TITLE: b'\x22',   # Triple (if supported)
        }
        return self.GS + b'!' + size_byte.get(size, b'\x00')

    def _cmd_bold(self, enabled: bool) -> bytes:
        """Set bold mode."""
        return self.ESC + b'E' + (b'\x01' if enabled else b'\x00')

    def _cmd_underline(self, enabled: bool) -> bytes:
        """Set underline mode."""
        return self.ESC + b'-' + (b'\x01' if enabled else b'\x00')

    def _get_font(self, size: int = 20):
        """Get a font for text rendering, with fallback."""
        try:
            from PIL import ImageFont
            # Try common system fonts that support Cyrillic
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/System/Library/Fonts/Helvetica.ttc",  # macOS
            ]
            for path in font_paths:
                try:
                    return ImageFont.truetype(path, size)
                except (OSError, IOError):
                    continue
            # Fallback to default
            return ImageFont.load_default()
        except Exception:
            return None

    def _render_text_as_image(self, block: TextBlock) -> bytes:
        """Render text as an image for printers that don't support CP866."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Font size based on text size
            font_sizes = {
                TextSize.SMALL: 20,
                TextSize.MEDIUM: 28,
                TextSize.LARGE: 36,
                TextSize.TITLE: 44,
            }
            font_size = font_sizes.get(block.size, 20)
            font = self._get_font(font_size)

            # Calculate text dimensions
            max_chars = self._max_chars(block.size)
            lines = self._wrap_text(block.text, max_chars) or [""]

            # Create temporary image to measure text
            temp_img = Image.new('1', (1, 1), 1)
            draw = ImageDraw.Draw(temp_img)

            line_height = font_size + 4
            total_height = len(lines) * line_height
            img_width = self.paper_width

            # Create actual image
            img = Image.new('1', (img_width, total_height), 1)  # White background
            draw = ImageDraw.Draw(img)

            y = 0
            for line in lines:
                # Get text width for alignment
                bbox = draw.textbbox((0, 0), line, font=font) if font else (0, 0, len(line) * 10, font_size)
                text_width = bbox[2] - bbox[0]

                if block.alignment == Alignment.CENTER:
                    x = (img_width - text_width) // 2
                elif block.alignment == Alignment.RIGHT:
                    x = img_width - text_width - 8
                else:
                    x = 8

                draw.text((x, y), line, font=font, fill=0)  # Black text
                y += line_height

            # Rotate 180° if printer is mounted upside-down
            if self.ROTATE_180:
                img = img.rotate(180)

            # Convert to raster commands
            return self._image_to_raster(img, Alignment.LEFT)

        except ImportError:
            logger.warning("PIL not available, falling back to text mode")
            return self._render_text_native(block)
        except Exception as e:
            logger.error(f"Text-as-image rendering failed: {e}")
            return self._render_text_native(block)

    def _render_text_native(self, block: TextBlock) -> bytes:
        """Render text using native printer commands (fallback)."""
        commands = []
        commands.append(self._cmd_align(block.alignment))
        commands.append(self._cmd_text_size(block.size))
        commands.append(self._cmd_bold(block.bold))
        commands.append(self._cmd_underline(block.underline))

        max_chars = self._max_chars(block.size)
        lines = self._wrap_text(block.text, max_chars) or [""]
        for line in lines:
            try:
                text_bytes = line.encode('cp866', errors='replace')
            except Exception:
                text_bytes = line.encode('ascii', errors='replace')
            commands.append(text_bytes)
            commands.append(self.LF)

        commands.append(self._cmd_bold(False))
        commands.append(self._cmd_underline(False))
        commands.append(self._cmd_text_size(TextSize.SMALL))
        return b''.join(commands)

    def _render_text(self, block: TextBlock) -> bytes:
        """Render a text block to commands."""
        if self.RENDER_TEXT_AS_IMAGE:
            return self._render_text_as_image(block)
        return self._render_text_native(block)

    def _render_image(self, block: ImageBlock) -> bytes:
        """Render an image block to commands.

        Uses raster bit image mode for best compatibility.
        """
        try:
            from PIL import Image

            # Load image
            img = Image.open(BytesIO(block.image_data))

            # Resize to fit paper width
            target_width = min(block.width, self.paper_width)
            aspect = img.height / img.width
            target_height = int(target_width * aspect)

            resample = Image.Resampling.NEAREST if not block.dither else Image.Resampling.LANCZOS
            img = img.resize((target_width, target_height), resample)

            # Convert to 1-bit black and white
            if block.dither:
                img = img.convert('L')  # Grayscale first
                img = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)
            else:
                img = img.convert('1', dither=Image.Dither.NONE)

            # Rotate 180° for upside-down mounted printer
            if self.ROTATE_180:
                img = img.rotate(180)

            # Convert to raster data
            return self._image_to_raster(img, block.alignment)

        except ImportError:
            logger.warning("PIL not available, skipping image")
            return b''
        except Exception as e:
            logger.error(f"Image rendering failed: {e}")
            return b''

    def _image_to_raster(self, img, alignment: Alignment) -> bytes:
        """Convert PIL Image to ESC/POS raster commands."""
        width, height = img.size

        # Ensure width is multiple of 8
        if width % 8 != 0:
            from PIL import Image
            new_width = (width // 8 + 1) * 8
            new_img = Image.new('1', (new_width, height), 1)  # White background
            offset = (new_width - width) // 2 if alignment == Alignment.CENTER else 0
            new_img.paste(img, (offset, 0))
            img = new_img
            width = new_width

        bytes_per_line = width // 8

        # Build raster data
        raster_data = []

        for y in range(height):
            line_data = []
            for x_byte in range(bytes_per_line):
                byte_val = 0
                for bit in range(8):
                    x = x_byte * 8 + bit
                    if x < img.width:
                        pixel = img.getpixel((x, y))
                        if pixel == 0:  # Black pixel
                            byte_val |= (0x80 >> bit)
                line_data.append(byte_val)
            raster_data.extend(line_data)

        # GS v 0 - Print raster bit image
        # Format: GS v 0 m xL xH yL yH data
        # m = 0 (normal), xL xH = width in bytes, yL yH = height in dots
        commands = []
        commands.append(self._cmd_align(alignment))
        commands.append(self.GS + b'v0')
        commands.append(b'\x00')  # m = normal
        commands.append(bytes([bytes_per_line & 0xFF, (bytes_per_line >> 8) & 0xFF]))
        commands.append(bytes([height & 0xFF, (height >> 8) & 0xFF]))
        commands.append(bytes(raster_data))

        return b''.join(commands)

    def _render_separator(self, block: SeparatorBlock) -> bytes:
        """Render a separator line."""
        chars_per_line = self._max_chars(TextSize.SMALL)
        text = self._separator_text(block.style, chars_per_line)
        return self._render_text(TextBlock(text=text, alignment=Alignment.CENTER))

    def _render_spacer(self, block: SpacerBlock) -> bytes:
        """Render vertical spacing."""
        return self.LF * block.lines

    def preview_text(self, layout: ReceiptLayout) -> str:
        """Generate a text preview of the receipt (for simulator).

        Args:
            layout: The receipt layout to preview

        Returns:
            ASCII art representation of the receipt
        """
        lines = []
        chars_per_line = self._max_chars(TextSize.SMALL)

        lines.append("+" + "-" * chars_per_line + "+")

        for block in layout.blocks:
            if isinstance(block, TextBlock):
                max_chars = self._max_chars(block.size)
                wrapped = self._wrap_text(block.text, max_chars) or [""]
                for line in wrapped:
                    text = line[:chars_per_line]
                    if block.alignment == Alignment.CENTER:
                        text = text.center(chars_per_line)
                    elif block.alignment == Alignment.RIGHT:
                        text = text.rjust(chars_per_line)
                    else:
                        text = text.ljust(chars_per_line)

                    if block.size in (TextSize.LARGE, TextSize.TITLE):
                        text = text.upper()
                    lines.append("|" + text + "|")

            elif isinstance(block, ImageBlock):
                lines.append("|" + "[IMAGE]".center(chars_per_line) + "|")

            elif isinstance(block, SeparatorBlock):
                text = self._separator_text(block.style, chars_per_line)
                lines.append("|" + text + "|")

            elif isinstance(block, SpacerBlock):
                for _ in range(block.lines):
                    lines.append("|" + " " * chars_per_line + "|")

        lines.append("+" + "-" * chars_per_line + "+")

        return "\n".join(lines)

    def _separator_text(self, style: str, chars_per_line: int) -> str:
        separators = {
            "line": "-" * chars_per_line,
            "dashes": "- " * (chars_per_line // 2),
            "dots": ". " * (chars_per_line // 2),
            "stars": "* " * (chars_per_line // 2),
            "double": "=" * chars_per_line,
        }
        return separators.get(style, separators["line"])

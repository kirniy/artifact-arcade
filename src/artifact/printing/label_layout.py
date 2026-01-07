"""Label layout engine for thermal sticker printer.

Renders receipt content to a fixed-size label image (58×100mm).
All content is rendered as a single image for consistent output
on the AIYIN IP-802 label printer.

Label specifications:
- Width: 58mm = ~464 pixels at 203 DPI
- Height: 100mm = ~800 pixels at 203 DPI
"""

import logging
from typing import List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO

logger = logging.getLogger(__name__)


# Label dimensions at 203 DPI
LABEL_WIDTH_MM = 58
LABEL_HEIGHT_MM = 100
DPI = 203

LABEL_WIDTH_PX = int(LABEL_WIDTH_MM * DPI / 25.4)  # ~464 pixels
LABEL_HEIGHT_PX = int(LABEL_HEIGHT_MM * DPI / 25.4)  # ~800 pixels


class Alignment(Enum):
    """Text alignment options."""
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


class TextSize(Enum):
    """Text size options with font sizes."""
    TINY = 14      # Very small
    SMALL = 18     # Normal small text
    MEDIUM = 24    # Medium text
    LARGE = 32     # Large text
    TITLE = 40     # Title/header
    HUGE = 56      # Very large


@dataclass
class TextBlock:
    """A block of text for the label."""
    text: str
    alignment: Alignment = Alignment.CENTER
    size: TextSize = TextSize.SMALL
    bold: bool = False


@dataclass
class ImageBlock:
    """An image block for the label."""
    image_data: bytes
    width: Optional[int] = None  # None = auto-fit
    height: Optional[int] = None  # None = auto from aspect
    alignment: Alignment = Alignment.CENTER


@dataclass
class SeparatorBlock:
    """A visual separator line."""
    style: str = "line"  # line, dashes, dots, double
    thickness: int = 2


@dataclass
class SpacerBlock:
    """Vertical spacing in pixels."""
    pixels: int = 10


@dataclass
class QRCodeBlock:
    """QR code block for the label."""
    url: str
    size: int = 80  # QR code size in pixels
    alignment: Alignment = Alignment.CENTER


@dataclass
class LabelLayout:
    """Complete label layout definition."""
    blocks: List[Union[TextBlock, ImageBlock, SeparatorBlock, SpacerBlock, QRCodeBlock]] = field(default_factory=list)
    margin_x: int = 16  # Horizontal margin in pixels
    margin_y: int = 20  # Vertical margin in pixels

    def add_text(
        self,
        text: str,
        alignment: Alignment = Alignment.CENTER,
        size: TextSize = TextSize.SMALL,
        bold: bool = False,
    ) -> "LabelLayout":
        """Add a text block."""
        self.blocks.append(TextBlock(
            text=text,
            alignment=alignment,
            size=size,
            bold=bold,
        ))
        return self

    def add_image(
        self,
        image_data: bytes,
        width: Optional[int] = None,
        height: Optional[int] = None,
        alignment: Alignment = Alignment.CENTER,
    ) -> "LabelLayout":
        """Add an image block."""
        self.blocks.append(ImageBlock(
            image_data=image_data,
            width=width,
            height=height,
            alignment=alignment,
        ))
        return self

    def add_qr(
        self,
        url: str,
        size: int = 80,
        alignment: Alignment = Alignment.CENTER,
    ) -> "LabelLayout":
        """Add a QR code block."""
        self.blocks.append(QRCodeBlock(
            url=url,
            size=size,
            alignment=alignment,
        ))
        return self

    def add_separator(self, style: str = "line", thickness: int = 2) -> "LabelLayout":
        """Add a separator line."""
        self.blocks.append(SeparatorBlock(style=style, thickness=thickness))
        return self

    def add_space(self, pixels: int = 10) -> "LabelLayout":
        """Add vertical spacing."""
        self.blocks.append(SpacerBlock(pixels=pixels))
        return self


class LabelLayoutEngine:
    """Engine for rendering label layouts to printer-ready images.

    Renders all content to a single PIL Image that can be sent
    directly to the label printer using raster commands.
    """

    def __init__(
        self,
        width: int = LABEL_WIDTH_PX,
        height: int = LABEL_HEIGHT_PX,
    ):
        """Initialize the label layout engine.

        Args:
            width: Label width in pixels
            height: Label height in pixels
        """
        self.width = width
        self.height = height
        self._font_cache = {}

    def _get_font(self, size: int, bold: bool = False):
        """Get a font for text rendering, with caching."""
        cache_key = (size, bold)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        try:
            from PIL import ImageFont

            # Font paths to try (Cyrillic support required)
            if bold:
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                ]
            else:
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
                    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                    "/System/Library/Fonts/Helvetica.ttc",
                ]

            for path in font_paths:
                try:
                    font = ImageFont.truetype(path, size)
                    self._font_cache[cache_key] = font
                    return font
                except (OSError, IOError):
                    continue

            # Fallback to default
            font = ImageFont.load_default()
            self._font_cache[cache_key] = font
            return font

        except ImportError:
            return None

    def _wrap_text(self, text: str, font, draw, max_width: int) -> List[str]:
        """Wrap text to fit within the given pixel width."""
        if not text:
            return [""]

        def get_width(s: str) -> int:
            if not s:
                return 0
            try:
                bbox = draw.textbbox((0, 0), s, font=font)
                return bbox[2] - bbox[0]
            except Exception:
                return len(s) * 10

        lines: List[str] = []
        raw_lines = text.split('\n') if '\n' in text else [text]

        for raw in raw_lines:
            words = raw.split()
            if not words:
                lines.append("")
                continue

            current = ""
            for word in words:
                # Handle very long words
                if get_width(word) > max_width:
                    if current:
                        lines.append(current)
                        current = ""
                    # Break word character by character
                    for char in word:
                        test = current + char
                        if get_width(test) > max_width and current:
                            lines.append(current)
                            current = char
                        else:
                            current = test
                    continue

                if not current:
                    current = word
                else:
                    test = current + " " + word
                    if get_width(test) <= max_width:
                        current = test
                    else:
                        lines.append(current)
                        current = word

            if current:
                lines.append(current)

        return lines if lines else [""]

    def render(self, layout: LabelLayout) -> bytes:
        """Render a label layout to ESC/POS raster commands.

        Args:
            layout: The label layout to render

        Returns:
            ESC/POS raster command bytes ready to send to printer
        """
        # First render to PIL Image
        img = self.render_to_image(layout)

        # Then convert to ESC/POS raster commands
        return self._image_to_escpos_raster(img)

    def render_to_image(self, layout: LabelLayout):
        """Render a label layout to a PIL Image.

        Args:
            layout: The label layout to render

        Returns:
            PIL Image in 1-bit mode (ready for thermal printing)
        """
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            raise RuntimeError("PIL/Pillow is required for label printing")

        # Create white background image
        img = Image.new('L', (self.width, self.height), 255)  # Grayscale white
        draw = ImageDraw.Draw(img)

        # Calculate usable area
        content_width = self.width - (layout.margin_x * 2)
        y_pos = layout.margin_y

        for block in layout.blocks:
            if y_pos >= self.height - layout.margin_y:
                logger.warning("Label content exceeds available space")
                break

            if isinstance(block, TextBlock):
                y_pos = self._render_text_block(
                    draw, block, layout.margin_x, y_pos, content_width
                )
            elif isinstance(block, ImageBlock):
                y_pos = self._render_image_block(
                    img, draw, block, layout.margin_x, y_pos, content_width
                )
            elif isinstance(block, QRCodeBlock):
                y_pos = self._render_qr_block(
                    img, block, layout.margin_x, y_pos, content_width
                )
            elif isinstance(block, SeparatorBlock):
                y_pos = self._render_separator_block(
                    draw, block, layout.margin_x, y_pos, content_width
                )
            elif isinstance(block, SpacerBlock):
                y_pos += block.pixels

        # Convert to 1-bit with Floyd-Steinberg dithering
        img = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

        return img

    def _render_text_block(
        self,
        draw,
        block: TextBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render a text block and return new y position."""
        font_size = block.size.value
        font = self._get_font(font_size, block.bold)
        if font is None:
            return y_pos + font_size + 4

        # Wrap text to fit width
        lines = self._wrap_text(block.text, font, draw, content_width)
        line_height = font_size + 4

        # Calculate available space for text
        available_height = self.height - y_pos - 40  # Reserve 40px for footer
        max_lines = max(1, available_height // line_height)

        # Limit lines if too many
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            # Add ellipsis to last line if truncated
            if lines[-1] and len(lines[-1]) > 3:
                lines[-1] = lines[-1][:-3] + "..."
            logger.debug(f"Text truncated to {max_lines} lines")

        for line in lines:
            # Calculate text width for alignment
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
            except Exception:
                text_width = len(line) * (font_size // 2)

            # Calculate x position based on alignment
            if block.alignment == Alignment.CENTER:
                x = margin_x + (content_width - text_width) // 2
            elif block.alignment == Alignment.RIGHT:
                x = margin_x + content_width - text_width
            else:
                x = margin_x

            # Ensure x doesn't go negative
            x = max(margin_x, x)

            # Draw text (black on white)
            draw.text((x, y_pos), line, font=font, fill=0)
            y_pos += line_height

        return y_pos

    def _render_image_block(
        self,
        img,
        draw,
        block: ImageBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render an image block and return new y position."""
        try:
            from PIL import Image

            # Load image
            block_img = Image.open(BytesIO(block.image_data))

            # Calculate available height (leave some room for footer)
            available_height = self.height - y_pos - 100  # Reserve 100px for footer

            # Calculate target size
            if block.width and block.height:
                target_width = min(block.width, content_width)
                target_height = min(block.height, available_height)
            elif block.width:
                target_width = min(block.width, content_width)
                aspect = block_img.height / block_img.width
                target_height = int(target_width * aspect)
                # Constrain to available height
                if target_height > available_height:
                    target_height = available_height
                    target_width = int(target_height / aspect)
            elif block.height:
                target_height = min(block.height, available_height)
                aspect = block_img.width / block_img.height
                target_width = min(int(target_height * aspect), content_width)
            else:
                # Auto-fit to content width
                target_width = content_width
                aspect = block_img.height / block_img.width
                target_height = int(target_width * aspect)
                # Constrain to available height
                if target_height > available_height:
                    target_height = available_height
                    target_width = int(target_height / aspect)

            # Ensure minimum dimensions
            target_width = max(10, target_width)
            target_height = max(10, target_height)

            # Resize image
            block_img = block_img.resize(
                (target_width, target_height),
                Image.Resampling.LANCZOS
            )

            # Convert to grayscale
            if block_img.mode != 'L':
                block_img = block_img.convert('L')

            # Calculate x position based on alignment
            if block.alignment == Alignment.CENTER:
                x = margin_x + (content_width - target_width) // 2
            elif block.alignment == Alignment.RIGHT:
                x = margin_x + content_width - target_width
            else:
                x = margin_x

            # Ensure we don't paste outside image bounds
            x = max(0, min(x, self.width - target_width))

            # Paste image
            img.paste(block_img, (x, y_pos))

            return y_pos + target_height + 8  # 8px padding after image

        except Exception as e:
            logger.error(f"Failed to render image block: {e}")
            return y_pos + 20

    def _render_qr_block(
        self,
        img,
        block: QRCodeBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render a QR code block and return new y position."""
        try:
            import qrcode
            from PIL import Image

            # Generate QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=4,
                border=1,
            )
            qr.add_data(block.url)
            qr.make(fit=True)

            qr_img = qr.make_image(fill_color="black", back_color="white")
            qr_img = qr_img.convert('L')

            # Resize to requested size
            qr_img = qr_img.resize((block.size, block.size), Image.Resampling.NEAREST)

            # Calculate x position based on alignment
            if block.alignment == Alignment.CENTER:
                x = margin_x + (content_width - block.size) // 2
            elif block.alignment == Alignment.RIGHT:
                x = margin_x + content_width - block.size
            else:
                x = margin_x

            # Paste QR code
            img.paste(qr_img, (x, y_pos))

            return y_pos + block.size + 8

        except ImportError:
            logger.warning("qrcode library not available")
            return y_pos + 20
        except Exception as e:
            logger.error(f"Failed to render QR code: {e}")
            return y_pos + 20

    def _render_separator_block(
        self,
        draw,
        block: SeparatorBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render a separator line and return new y position."""
        y_center = y_pos + 5

        if block.style == "line":
            draw.line(
                [(margin_x, y_center), (margin_x + content_width, y_center)],
                fill=0,
                width=block.thickness,
            )
        elif block.style == "double":
            draw.line(
                [(margin_x, y_center - 2), (margin_x + content_width, y_center - 2)],
                fill=0,
                width=1,
            )
            draw.line(
                [(margin_x, y_center + 2), (margin_x + content_width, y_center + 2)],
                fill=0,
                width=1,
            )
        elif block.style == "dashes":
            dash_len = 8
            gap_len = 4
            x = margin_x
            while x < margin_x + content_width:
                draw.line(
                    [(x, y_center), (min(x + dash_len, margin_x + content_width), y_center)],
                    fill=0,
                    width=block.thickness,
                )
                x += dash_len + gap_len
        elif block.style == "dots":
            dot_gap = 6
            x = margin_x
            while x < margin_x + content_width:
                draw.ellipse(
                    [(x, y_center - 1), (x + 2, y_center + 1)],
                    fill=0,
                )
                x += dot_gap

        return y_pos + 10 + block.thickness

    def _image_to_escpos_raster(self, img) -> bytes:
        """Convert PIL Image to ESC/POS raster commands.

        Args:
            img: PIL Image in 1-bit mode

        Returns:
            ESC/POS command bytes
        """
        width, height = img.size

        # Ensure width is multiple of 8
        if width % 8 != 0:
            from PIL import Image
            new_width = (width // 8 + 1) * 8
            new_img = Image.new('1', (new_width, height), 1)
            new_img.paste(img, (0, 0))
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

        # Build command: GS v 0 m xL xH yL yH data
        GS = b'\x1d'
        commands = []

        # Initialize printer first
        commands.append(b'\x1b\x40')  # ESC @ - Reset

        # Set left margin to 0
        commands.append(b'\x1d\x4c\x00\x00')  # GS L - Set left margin to 0

        # GS v 0 - Print raster bit image
        commands.append(GS + b'v0')
        commands.append(b'\x00')  # m = normal mode
        commands.append(bytes([bytes_per_line & 0xFF, (bytes_per_line >> 8) & 0xFF]))
        commands.append(bytes([height & 0xFF, (height >> 8) & 0xFF]))
        commands.append(bytes(raster_data))

        # Feed past the label gap
        commands.append(b'\x1b\x64\x04')  # ESC d 4 - Feed 4 lines

        return b''.join(commands)

    def render_to_png(self, layout: LabelLayout) -> bytes:
        """Render layout to PNG image bytes (for preview/debugging).

        Args:
            layout: The label layout to render

        Returns:
            PNG image bytes
        """
        img = self.render_to_image(layout)

        # Convert to RGB for PNG (1-bit looks bad in some viewers)
        img = img.convert('RGB')

        buffer = BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()


def create_fortune_label(
    prediction: str,
    image_data: Optional[bytes] = None,
    mode_title: str = "ARTIFACT",
    date_str: Optional[str] = None,
    qr_url: Optional[str] = None,
) -> LabelLayout:
    """Create a fortune-style label layout.

    Args:
        prediction: The fortune/prediction text
        image_data: Optional caricature/portrait image
        mode_title: Title to show at top
        date_str: Optional date string
        qr_url: Optional URL for QR code

    Returns:
        LabelLayout ready for rendering
    """
    layout = LabelLayout()

    # Header
    layout.add_text(mode_title, size=TextSize.TITLE, bold=True)
    layout.add_separator("double")
    layout.add_space(5)

    # Image (if provided)
    if image_data:
        layout.add_image(image_data, width=300)
        layout.add_space(10)

    # Prediction text
    layout.add_text(prediction, size=TextSize.MEDIUM)
    layout.add_space(10)

    # QR code (if provided)
    if qr_url:
        layout.add_separator("line")
        layout.add_space(5)
        layout.add_qr(qr_url, size=70)
        layout.add_text("Scan for full image", size=TextSize.TINY)

    # Footer
    layout.add_space(5)
    layout.add_separator("line")
    if date_str:
        layout.add_text(date_str, size=TextSize.TINY)

    return layout


def create_sorting_hat_label(
    house: str,
    description: str,
    image_data: Optional[bytes] = None,
    qr_url: Optional[str] = None,
) -> LabelLayout:
    """Create a Sorting Hat result label.

    Args:
        house: The Hogwarts house name
        description: House description/traits
        image_data: Optional portrait image
        qr_url: Optional URL for QR code

    Returns:
        LabelLayout ready for rendering
    """
    layout = LabelLayout()

    # Header
    layout.add_text("🎩 SORTING HAT", size=TextSize.LARGE, bold=True)
    layout.add_separator("double")
    layout.add_space(5)

    # Image (if provided)
    if image_data:
        layout.add_image(image_data, width=280)
        layout.add_space(8)

    # House name (big!)
    layout.add_text(house.upper(), size=TextSize.HUGE, bold=True)
    layout.add_space(5)

    # Description
    layout.add_text(description, size=TextSize.SMALL)

    # QR code (if provided)
    if qr_url:
        layout.add_space(8)
        layout.add_qr(qr_url, size=60)

    return layout


def create_photo_label(
    image_data: bytes,
    caption: Optional[str] = None,
    qr_url: Optional[str] = None,
    date_str: Optional[str] = None,
) -> LabelLayout:
    """Create a simple photo sticker label.

    Args:
        image_data: Photo image data
        caption: Optional caption text
        qr_url: Optional URL for QR code
        date_str: Optional date string

    Returns:
        LabelLayout ready for rendering
    """
    layout = LabelLayout(margin_y=10)

    # Photo takes most of the space
    layout.add_image(image_data, width=420)

    if caption:
        layout.add_space(5)
        layout.add_text(caption, size=TextSize.SMALL)

    if qr_url:
        layout.add_space(5)
        layout.add_qr(qr_url, size=50)

    if date_str:
        layout.add_text(date_str, size=TextSize.TINY)

    return layout

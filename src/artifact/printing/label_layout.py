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
    style: str = "line"  # line, dashes, dots, double, stars, fancy, ornate, wave
    thickness: int = 2
    margin: int = 0  # Extra horizontal margin from content edges


@dataclass
class SpacerBlock:
    """Vertical spacing in pixels."""
    pixels: int = 10


@dataclass
class FlexSpacerBlock:
    """Flexible spacer that fills remaining vertical space.

    Used to push content (like footer) to bottom of label.
    """
    min_pixels: int = 10  # Minimum spacing even if no room


@dataclass
class QRCodeBlock:
    """QR code block for the label."""
    url: str
    size: int = 80  # QR code size in pixels
    alignment: Alignment = Alignment.CENTER


@dataclass
class IconBlock:
    """An icon from Font Awesome for the label."""
    icon: str  # Icon name like "fire", "star", "gift"
    size: int = 24
    alignment: Alignment = Alignment.CENTER


# Font Awesome 6 Unicode codepoints for common icons
FA_ICONS = {
    "fire": "\uf06d",
    "star": "\uf005",
    "star-half": "\uf089",
    "gift": "\uf06b",
    "trophy": "\uf091",
    "gamepad": "\uf11b",
    "dice": "\uf522",
    "question": "\uf128",
    "question-circle": "\uf059",
    "skull": "\uf54c",
    "skull-crossbones": "\uf714",
    "glass-martini": "\uf000",
    "cocktail": "\uf561",
    "wine-glass": "\uf4e3",
    "music": "\uf001",
    "camera": "\uf030",
    "video": "\uf03d",
    "film": "\uf008",
    "user-secret": "\uf21b",
    "magic": "\uf0d0",
    "hat-wizard": "\uf6e8",
    "compact-disc": "\uf51f",
    "microphone": "\uf130",
    "crown": "\uf521",
    "heart": "\uf004",
    "bolt": "\uf0e7",
    "gem": "\uf3a5",
    "cube": "\uf1b2",
    "square": "\uf0c8",
    "circle": "\uf111",
    "check": "\uf00c",
    "times": "\uf00d",
    "exclamation": "\uf12a",
    "info": "\uf129",
    "arrow-right": "\uf061",
    "arrow-left": "\uf060",
    "chevron-right": "\uf054",
    "chevron-left": "\uf053",
    "sparkles": "\uf890",  # FA 6 only
    "wand-sparkles": "\uf72b",
    "crystal-ball": "\uf72b",  # using wand as fallback
    "ghost": "\uf6e2",
    "robot": "\uf544",
    "brain": "\uf5dc",
    "eye": "\uf06e",
    "comment": "\uf075",
    "quote-left": "\uf10d",
    "quote-right": "\uf10e",
}


@dataclass
class HeaderRowBlock:
    """Compact centered header with icon + title.

    Layout: [icon TITLE] centered
    """
    title: str
    icon: Optional[str] = None  # Font Awesome icon name
    qr_url: Optional[str] = None  # Ignored now - QR goes in footer
    qr_size: int = 80  # Ignored
    title_size: int = 42  # Title font size
    icon_size: int = 32  # Icon size


@dataclass
class FooterWithQRBlock:
    """Two-column footer: text on left, QR on right.

    Layout: [СКАЧАЙ:        ]  [QR]
            [vnvnc.ru/p/xxx ]  [QR]
            [date           ]  [QR]
    """
    date_text: str
    website: str = "VNVNC.RU"
    qr_url: str = ""
    qr_size: int = 150  # Large for thermal printer scannability (minimum 120px)
    label_text: str = "СКАЧАЙ:"
    short_url: str = ""  # Display URL like "vnvnc.ru/p/abc123"


@dataclass
class BoxBlock:
    """A framed box containing other elements."""
    content_blocks: List[Union["TextBlock", "ImageBlock", "SpacerBlock", "IconBlock"]] = field(default_factory=list)
    border_style: str = "solid"  # solid, dashed, double, rounded, ornate
    padding: int = 8
    corner_style: str = "square"  # square, rounded, ornate
    title: Optional[str] = None  # Optional title text at top of box
    fill_pattern: Optional[str] = None  # None, dots, lines, crosshatch


@dataclass
class LabelLayout:
    """Complete label layout definition."""
    blocks: List[Union[TextBlock, ImageBlock, SeparatorBlock, SpacerBlock, FlexSpacerBlock, QRCodeBlock, BoxBlock, IconBlock, HeaderRowBlock, FooterWithQRBlock]] = field(default_factory=list)
    margin_x: int = 16  # Horizontal margin in pixels
    margin_y: int = 20  # Vertical margin in pixels
    page_border: Optional[str] = None  # None, "solid", "double", "ornate", "stars"
    page_border_margin: int = 4  # Margin from edge for page border

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

    def add_icon(
        self,
        icon: str,
        size: int = 24,
        alignment: Alignment = Alignment.CENTER,
    ) -> "LabelLayout":
        """Add an icon from Font Awesome.

        Args:
            icon: Icon name (e.g., "fire", "star", "gift") from FA_ICONS
            size: Icon size in pixels
            alignment: Horizontal alignment
        """
        self.blocks.append(IconBlock(
            icon=icon,
            size=size,
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

    def add_flex_space(self, min_pixels: int = 10) -> "LabelLayout":
        """Add flexible spacing that fills remaining vertical space.

        Use this to push footer content to the bottom of the label.
        """
        self.blocks.append(FlexSpacerBlock(min_pixels=min_pixels))
        return self

    def add_header_row(
        self,
        title: str,
        icon: Optional[str] = None,
        qr_url: Optional[str] = None,
        qr_size: int = 70,
        title_size: int = 48,
        icon_size: int = 32,
    ) -> "LabelLayout":
        """Add a header row with title on left, optional QR on right.

        Modern layout that puts QR code in the header to save space.
        Example: [icon ПРОЖАРКА     [QR]]
        """
        self.blocks.append(HeaderRowBlock(
            title=title,
            icon=icon,
            qr_url=qr_url,
            qr_size=qr_size,
            title_size=title_size,
            icon_size=icon_size,
        ))
        return self

    def add_box(
        self,
        border_style: str = "solid",
        padding: int = 8,
        corner_style: str = "square",
        title: Optional[str] = None,
        fill_pattern: Optional[str] = None,
    ) -> "BoxBlock":
        """Add a framed box and return it for adding content.

        Usage:
            box = layout.add_box(border_style="double", title="РЕЗУЛЬТАТ")
            box.content_blocks.append(TextBlock("Your text here", size=TextSize.LARGE))
        """
        box = BoxBlock(
            border_style=border_style,
            padding=padding,
            corner_style=corner_style,
            title=title,
            fill_pattern=fill_pattern,
        )
        self.blocks.append(box)
        return box


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
        self._icon_font_cache = {}

    def _get_icon_font(self, size: int):
        """Get Font Awesome icon font for rendering icons."""
        if size in self._icon_font_cache:
            return self._icon_font_cache[size]

        try:
            from PIL import ImageFont
            from pathlib import Path

            # Find Font Awesome font file
            fa_paths = [
                Path(__file__).parent.parent.parent / "assets" / "fonts" / "fa-solid-900.ttf",
                Path("/Users/kirniy/dev/modular-arcade/assets/fonts/fa-solid-900.ttf"),
            ]

            for path in fa_paths:
                if path.exists():
                    font = ImageFont.truetype(str(path), size)
                    self._icon_font_cache[size] = font
                    return font

            return None
        except Exception:
            return None

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

    def render(self, layout: LabelLayout, protocol: str = "tspl") -> bytes:
        """Render a label layout to printer commands.

        Args:
            layout: The label layout to render
            protocol: Printer protocol - "tspl" (default) or "escpos"

        Returns:
            Printer command bytes ready to send
        """
        # First render to PIL Image
        img = self.render_to_image(layout)

        # Convert to appropriate protocol
        if protocol == "tspl":
            return self._image_to_tspl_commands(img)
        else:
            return self._image_to_escpos_raster(img)

    def _estimate_block_height(self, block, content_width: int, draw=None) -> int:
        """Estimate the height a block will take when rendered."""
        if isinstance(block, TextBlock):
            font_size = block.size.value
            font = self._get_font(font_size, block.bold)
            if font and draw:
                lines = self._wrap_text(block.text, font, draw, content_width)
                return len(lines) * (font_size + 4)
            # Rough estimate without font
            chars_per_line = content_width // (font_size // 2)
            lines = max(1, len(block.text) // chars_per_line + 1)
            return lines * (font_size + 4)
        elif isinstance(block, ImageBlock):
            # Calculate actual height based on image aspect ratio and target width
            if block.height:
                return block.height
            if block.width and block.image_data:
                try:
                    from PIL import Image
                    import io
                    if isinstance(block.image_data, Image.Image):
                        img = block.image_data
                    else:
                        img = Image.open(io.BytesIO(block.image_data))
                    aspect = img.height / img.width
                    return int(block.width * aspect)
                except Exception:
                    pass
            return block.width or 200  # Assume square if can't determine
        elif isinstance(block, QRCodeBlock):
            return block.size + 8
        elif isinstance(block, SeparatorBlock):
            return block.thickness + 12
        elif isinstance(block, SpacerBlock):
            return block.pixels
        elif isinstance(block, IconBlock):
            return block.size + 8
        elif isinstance(block, BoxBlock):
            # Estimate box content
            inner_height = sum(
                self._estimate_block_height(b, content_width - block.padding * 2, draw)
                for b in block.content_blocks
            )
            return inner_height + block.padding * 2 + 20
        elif isinstance(block, FlexSpacerBlock):
            return block.min_pixels  # Will be expanded later
        elif isinstance(block, HeaderRowBlock):
            # Compact header height
            return block.title_size + 8
        elif isinstance(block, FooterWithQRBlock):
            # Two-column footer height = max(QR size, text height) + separator + padding
            text_height = 24 + 3 + 22 + 3 + 24  # 78px for text stack
            return max(block.qr_size, text_height) + 10
        return 0

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
        available_height = self.height - (layout.margin_y * 2)

        # First pass: estimate total fixed height and count flex spacers
        flex_spacers = []
        fixed_height = 0
        for i, block in enumerate(layout.blocks):
            if isinstance(block, FlexSpacerBlock):
                flex_spacers.append(i)
                fixed_height += block.min_pixels
            else:
                fixed_height += self._estimate_block_height(block, content_width, draw)

        # Calculate flex space to distribute
        remaining_space = max(0, available_height - fixed_height)
        flex_space_per_block = remaining_space // max(1, len(flex_spacers)) if flex_spacers else 0

        # Second pass: render with calculated flex space
        y_pos = layout.margin_y

        for i, block in enumerate(layout.blocks):
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
            elif isinstance(block, BoxBlock):
                y_pos = self._render_box_block(
                    img, draw, block, layout.margin_x, y_pos, content_width
                )
            elif isinstance(block, IconBlock):
                y_pos = self._render_icon_block(
                    draw, block, layout.margin_x, y_pos, content_width
                )
            elif isinstance(block, SpacerBlock):
                y_pos += block.pixels
            elif isinstance(block, FlexSpacerBlock):
                # Add calculated flex space (only if there's room)
                if flex_space_per_block > 0:
                    y_pos += flex_space_per_block
                else:
                    y_pos += block.min_pixels
            elif isinstance(block, HeaderRowBlock):
                y_pos = self._render_header_row_block(
                    img, draw, block, layout.margin_x, y_pos, content_width
                )
            elif isinstance(block, FooterWithQRBlock):
                y_pos = self._render_footer_with_qr_block(
                    img, draw, block, layout.margin_x, y_pos, content_width
                )

        # Draw page border if specified
        if layout.page_border:
            self._draw_page_border(draw, layout)

        # Convert to 1-bit with Floyd-Steinberg dithering
        img = img.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

        return img

    def _draw_page_border(self, draw, layout: LabelLayout) -> None:
        """Draw a decorative border around the entire page."""
        m = layout.page_border_margin
        x0, y0 = m, m
        x1, y1 = self.width - m - 1, self.height - m - 1
        style = layout.page_border

        if style == "solid":
            # Simple solid rectangle
            draw.rectangle([x0, y0, x1, y1], outline=0, width=2)

        elif style == "double":
            # Double line border
            draw.rectangle([x0, y0, x1, y1], outline=0, width=1)
            inner_m = m + 4
            draw.rectangle([inner_m, inner_m, self.width - inner_m - 1, self.height - inner_m - 1], outline=0, width=1)

        elif style == "ornate":
            # Solid border with corner decorations
            draw.rectangle([x0, y0, x1, y1], outline=0, width=2)
            # Corner decorations (small diamonds)
            corner_size = 8
            for cx, cy in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
                draw.polygon([
                    (cx, cy - corner_size if cy == y0 else cy + corner_size),
                    (cx + corner_size if cx == x0 else cx - corner_size, cy),
                    (cx, cy + corner_size if cy == y0 else cy - corner_size),
                    (cx - corner_size if cx == x0 else cx + corner_size, cy),
                ], fill=0)

        elif style == "stars":
            # Border with stars at corners and midpoints
            draw.rectangle([x0, y0, x1, y1], outline=0, width=1)
            # Draw stars at key points
            star_positions = [
                (x0 + 6, y0 + 6),  # Top-left
                (x1 - 6, y0 + 6),  # Top-right
                (x0 + 6, y1 - 6),  # Bottom-left
                (x1 - 6, y1 - 6),  # Bottom-right
                ((x0 + x1) // 2, y0 + 6),  # Top-center
                ((x0 + x1) // 2, y1 - 6),  # Bottom-center
            ]
            for sx, sy in star_positions:
                # Small 5-pointed star approximation
                draw.ellipse([sx - 3, sy - 3, sx + 3, sy + 3], fill=0)

    def _render_text_block(
        self,
        draw,
        block: TextBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render a text block and return new y position.

        NEVER truncates text - the receipt generator uses adaptive font
        sizing to ensure all text fits. This just renders what's given.
        """
        font_size = block.size.value
        font = self._get_font(font_size, block.bold)
        if font is None:
            return y_pos + font_size + 4

        # Wrap text to fit width (wrapping only, no truncation)
        lines = self._wrap_text(block.text, font, draw, content_width)
        line_height = font_size + 4

        # Render ALL lines - no truncation
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

    def _render_icon_block(
        self,
        draw,
        block: IconBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render a Font Awesome icon and return new y position."""
        icon_font = self._get_icon_font(block.size)
        if not icon_font:
            # Fallback: skip icon if font not available
            return y_pos + block.size + 4

        # Get icon character from FA_ICONS mapping
        icon_char = FA_ICONS.get(block.icon, "\uf111")  # Default to circle

        # Get icon width for centering
        try:
            bbox = draw.textbbox((0, 0), icon_char, font=icon_font)
            icon_width = bbox[2] - bbox[0]
        except Exception:
            icon_width = block.size

        # Calculate x position based on alignment
        if block.alignment == Alignment.CENTER:
            x = margin_x + (content_width - icon_width) // 2
        elif block.alignment == Alignment.RIGHT:
            x = margin_x + content_width - icon_width
        else:
            x = margin_x

        # Draw icon
        draw.text((x, y_pos), icon_char, font=icon_font, fill=0)

        return y_pos + block.size + 4

    def _render_header_row_block(
        self,
        img,
        draw,
        block: HeaderRowBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render compact centered header: [icon TITLE] centered."""
        row_height = block.title_size + 8

        # Calculate total width of icon + title for centering
        total_width = 0
        icon_width = 0

        if block.icon:
            icon_font = self._get_icon_font(block.icon_size)
            if icon_font:
                icon_char = FA_ICONS.get(block.icon, "\uf111")
                try:
                    bbox = draw.textbbox((0, 0), icon_char, font=icon_font)
                    icon_width = bbox[2] - bbox[0]
                except Exception:
                    icon_width = block.icon_size
                total_width += icon_width + 8  # icon + space

        title_font = self._get_font(block.title_size, bold=True)
        title_width = 0
        if title_font:
            try:
                bbox = draw.textbbox((0, 0), block.title, font=title_font)
                title_width = bbox[2] - bbox[0]
            except Exception:
                title_width = len(block.title) * (block.title_size // 2)
            total_width += title_width

        # Center the whole thing
        start_x = margin_x + (content_width - total_width) // 2
        current_x = start_x

        # Draw icon
        if block.icon and icon_width > 0:
            icon_font = self._get_icon_font(block.icon_size)
            icon_char = FA_ICONS.get(block.icon, "\uf111")
            icon_y = y_pos + (row_height - block.icon_size) // 2
            draw.text((current_x, icon_y), icon_char, font=icon_font, fill=0)
            current_x += icon_width + 8

        # Draw title
        if title_font:
            text_y = y_pos + (row_height - block.title_size) // 2
            draw.text((current_x, text_y), block.title, font=title_font, fill=0)

        return y_pos + row_height + 4

    def _render_footer_with_qr_block(
        self,
        img,
        draw,
        block: FooterWithQRBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render two-column footer: text on left, QR on right, both centered in their columns."""
        try:
            import qrcode
            from PIL import Image as PILImage
        except ImportError:
            return y_pos

        # Calculate available height (leave room for page border)
        max_y = self.height - 16  # 16px margin for page border (increased from 8px)
        available_height = max_y - y_pos - 8  # 8px for top separator + padding

        # QR size - use requested size but clamp to available space
        # Minimum 120px for scannability on thermal printer (at 203 DPI, ~15mm)
        qr_size = min(block.qr_size, available_height - 20)  # 20px buffer
        qr_size = max(qr_size, 120)  # Ensure minimum scannable size

        # Draw top separator line
        draw.line([(margin_x, y_pos), (margin_x + content_width, y_pos)], fill=0, width=1)
        y_pos += 6

        # Calculate text heights (slightly smaller to fit)
        # label (24) + gap (3) + url (18) + gap (4) + date (20) = ~69px
        text_total_height = 24 + 3 + 18 + 4 + 20  # label + gap + url + gap + date = 69px

        # Row height is the larger of QR or text, clamped to available
        row_height = min(max(qr_size, text_total_height), available_height)
        row_start_y = y_pos

        # Calculate column positions - split into two equal columns with dotted separator
        center_x = margin_x + content_width // 2
        left_col_start = margin_x
        left_col_width = center_x - margin_x - 4  # 4px gap from center line
        right_col_start = center_x + 4
        right_col_width = margin_x + content_width - right_col_start

        # LEFT SIDE: Text column - centered both vertically AND horizontally
        text_start_y = row_start_y + (row_height - text_total_height) // 2
        text_y = text_start_y

        # Helper to center text in left column
        def draw_centered_text(text: str, font, y: int, bold: bool = False):
            if not font:
                return
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
            except Exception:
                text_width = len(text) * 10
            text_x = left_col_start + (left_col_width - text_width) // 2
            draw.text((text_x, y), text, font=font, fill=0)

        # "СКАЧАЙ:" label - centered
        label_font = self._get_font(24, bold=True)
        draw_centered_text(block.label_text, label_font, text_y)
        text_y += 27

        # Short URL (e.g., "vnvnc.ru/p/abc123") - centered, smaller font
        if block.short_url:
            url_font = self._get_font(18, bold=False)
            # Extract just the path part for cleaner display
            url_display = block.short_url.replace("https://", "").replace("http://", "")
            draw_centered_text(url_display, url_font, text_y)
            text_y += 22
        else:
            # Fallback to website if no short URL
            web_font = self._get_font(22, bold=True)
            draw_centered_text(block.website, web_font, text_y)
            text_y += 25

        # Date - centered
        date_font = self._get_font(20, bold=False)
        draw_centered_text(block.date_text, date_font, text_y)

        # DOTTED VERTICAL SEPARATOR in center
        dot_gap = 6
        dot_y = row_start_y
        while dot_y < row_start_y + row_height - 2:
            draw.ellipse([(center_x - 1, dot_y), (center_x + 1, dot_y + 2)], fill=0)
            dot_y += dot_gap

        # RIGHT SIDE: QR code - centered both vertically AND horizontally in right column
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,  # Larger box size for better scannability
            border=1,
        )
        qr.add_data(block.qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img = qr_img.convert('L').resize((qr_size, qr_size), PILImage.Resampling.NEAREST)

        # Center QR horizontally in right column
        qr_x = right_col_start + (right_col_width - qr_size) // 2
        # Center QR vertically in row
        qr_y = row_start_y + (row_height - qr_size) // 2
        img.paste(qr_img, (qr_x, qr_y))

        return row_start_y + row_height + 4  # Small padding after

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

            # Calculate available height (leave room for footer with QR code)
            available_height = self.height - y_pos - 180  # Reserve 180px for footer with 150px QR

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
        # Apply extra margin if specified
        left_x = margin_x + block.margin
        right_x = margin_x + content_width - block.margin
        y_center = y_pos + 5

        if block.style == "line":
            draw.line(
                [(left_x, y_center), (right_x, y_center)],
                fill=0,
                width=block.thickness,
            )
        elif block.style == "double":
            draw.line(
                [(left_x, y_center - 2), (right_x, y_center - 2)],
                fill=0,
                width=1,
            )
            draw.line(
                [(left_x, y_center + 2), (right_x, y_center + 2)],
                fill=0,
                width=1,
            )
        elif block.style == "dashes":
            dash_len = 8
            gap_len = 4
            x = left_x
            while x < right_x:
                draw.line(
                    [(x, y_center), (min(x + dash_len, right_x), y_center)],
                    fill=0,
                    width=block.thickness,
                )
                x += dash_len + gap_len
        elif block.style == "dots":
            dot_gap = 6
            x = left_x
            while x < right_x:
                draw.ellipse(
                    [(x, y_center - 1), (x + 2, y_center + 1)],
                    fill=0,
                )
                x += dot_gap
        elif block.style == "stars":
            # ★ stars pattern
            star_gap = 20
            center_x = (left_x + right_x) // 2
            # Draw center star
            draw.text((center_x - 5, y_center - 6), "★", font=self._get_font(12), fill=0)
            # Draw side stars
            x_left = center_x - star_gap
            x_right = center_x + star_gap
            while x_left > left_x or x_right < right_x:
                if x_left > left_x:
                    draw.text((x_left - 5, y_center - 6), "★", font=self._get_font(10), fill=0)
                if x_right < right_x:
                    draw.text((x_right - 5, y_center - 6), "★", font=self._get_font(10), fill=0)
                x_left -= star_gap
                x_right += star_gap
        elif block.style == "fancy":
            # Fancy flourish: ═══════ ◆ ═══════
            center_x = (left_x + right_x) // 2
            # Draw double lines on sides
            draw.line([(left_x, y_center - 1), (center_x - 12, y_center - 1)], fill=0, width=1)
            draw.line([(left_x, y_center + 1), (center_x - 12, y_center + 1)], fill=0, width=1)
            draw.line([(center_x + 12, y_center - 1), (right_x, y_center - 1)], fill=0, width=1)
            draw.line([(center_x + 12, y_center + 1), (right_x, y_center + 1)], fill=0, width=1)
            # Draw diamond in center
            diamond_size = 6
            draw.polygon([
                (center_x, y_center - diamond_size),
                (center_x + diamond_size, y_center),
                (center_x, y_center + diamond_size),
                (center_x - diamond_size, y_center),
            ], fill=0)
        elif block.style == "ornate":
            # Ornate: ─────═══●═══─────
            center_x = (left_x + right_x) // 2
            third = (right_x - left_x) // 3
            # Thin outer lines
            draw.line([(left_x, y_center), (left_x + third, y_center)], fill=0, width=1)
            draw.line([(right_x - third, y_center), (right_x, y_center)], fill=0, width=1)
            # Thick inner lines
            draw.line([(left_x + third, y_center), (center_x - 8, y_center)], fill=0, width=3)
            draw.line([(center_x + 8, y_center), (right_x - third, y_center)], fill=0, width=3)
            # Center dot
            draw.ellipse([(center_x - 5, y_center - 5), (center_x + 5, y_center + 5)], fill=0)
        elif block.style == "wave":
            # Wavy line pattern
            import math
            wave_points = []
            amplitude = 3
            frequency = 0.15
            for x in range(left_x, right_x, 2):
                y = y_center + int(amplitude * math.sin(frequency * (x - left_x)))
                wave_points.append((x, y))
            if len(wave_points) > 1:
                draw.line(wave_points, fill=0, width=block.thickness)
        elif block.style == "arrows":
            # Arrow chain: ──►──►──►──
            arrow_gap = 15
            x = left_x
            while x < right_x - 10:
                # Draw line segment
                draw.line([(x, y_center), (x + arrow_gap - 5, y_center)], fill=0, width=1)
                # Draw arrow head
                arrow_x = x + arrow_gap - 3
                if arrow_x < right_x:
                    draw.polygon([
                        (arrow_x, y_center),
                        (arrow_x - 4, y_center - 3),
                        (arrow_x - 4, y_center + 3),
                    ], fill=0)
                x += arrow_gap

        return y_pos + 12 + block.thickness

    def _render_box_block(
        self,
        img,
        draw,
        block: BoxBlock,
        margin_x: int,
        y_pos: int,
        content_width: int,
    ) -> int:
        """Render a framed box with content and return new y position."""
        padding = block.padding
        border_width = 2

        # Calculate box dimensions by pre-rendering content to measure height
        temp_y = y_pos + padding + border_width
        if block.title:
            temp_y += 22  # Space for title

        # Calculate content height
        content_start_y = temp_y
        for content_block in block.content_blocks:
            if isinstance(content_block, TextBlock):
                font = self._get_font(content_block.size.value, content_block.bold)
                lines = self._wrap_text(content_block.text, font, draw, content_width - padding * 2 - border_width * 2)
                temp_y += len(lines) * (content_block.size.value + 4)
            elif isinstance(content_block, SpacerBlock):
                temp_y += content_block.pixels

        content_height = temp_y - content_start_y
        box_height = content_height + padding * 2 + border_width * 2
        if block.title:
            box_height += 22

        # Draw box border
        box_left = margin_x
        box_right = margin_x + content_width
        box_top = y_pos
        box_bottom = y_pos + box_height

        if block.border_style == "solid":
            draw.rectangle(
                [(box_left, box_top), (box_right, box_bottom)],
                outline=0,
                width=border_width,
            )
        elif block.border_style == "double":
            # Outer border
            draw.rectangle(
                [(box_left, box_top), (box_right, box_bottom)],
                outline=0,
                width=1,
            )
            # Inner border
            draw.rectangle(
                [(box_left + 3, box_top + 3), (box_right - 3, box_bottom - 3)],
                outline=0,
                width=1,
            )
        elif block.border_style == "dashed":
            # Draw dashed border (4 sides)
            dash_len = 6
            gap_len = 3
            # Top
            x = box_left
            while x < box_right:
                end_x = min(x + dash_len, box_right)
                draw.line([(x, box_top), (end_x, box_top)], fill=0, width=border_width)
                x += dash_len + gap_len
            # Bottom
            x = box_left
            while x < box_right:
                end_x = min(x + dash_len, box_right)
                draw.line([(x, box_bottom), (end_x, box_bottom)], fill=0, width=border_width)
                x += dash_len + gap_len
            # Left
            y = box_top
            while y < box_bottom:
                end_y = min(y + dash_len, box_bottom)
                draw.line([(box_left, y), (box_left, end_y)], fill=0, width=border_width)
                y += dash_len + gap_len
            # Right
            y = box_top
            while y < box_bottom:
                end_y = min(y + dash_len, box_bottom)
                draw.line([(box_right, y), (box_right, end_y)], fill=0, width=border_width)
                y += dash_len + gap_len
        elif block.border_style == "ornate":
            # Ornate border with corner decorations
            draw.rectangle(
                [(box_left, box_top), (box_right, box_bottom)],
                outline=0,
                width=border_width,
            )
            # Corner decorations
            corner_size = 8
            for cx, cy in [(box_left, box_top), (box_right, box_top),
                           (box_left, box_bottom), (box_right, box_bottom)]:
                draw.ellipse(
                    [(cx - corner_size // 2, cy - corner_size // 2),
                     (cx + corner_size // 2, cy + corner_size // 2)],
                    fill=0,
                )

        # Draw fill pattern if specified
        if block.fill_pattern == "dots":
            for px in range(box_left + 8, box_right - 8, 12):
                for py in range(box_top + 8, box_bottom - 8, 12):
                    draw.ellipse([(px, py), (px + 2, py + 2)], fill=180)

        # Draw title if present
        current_y = box_top + border_width + padding
        if block.title:
            title_font = self._get_font(14, bold=True)
            try:
                bbox = draw.textbbox((0, 0), block.title, font=title_font)
                title_width = bbox[2] - bbox[0]
            except Exception:
                title_width = len(block.title) * 7
            title_x = margin_x + (content_width - title_width) // 2
            draw.text((title_x, current_y), block.title, font=title_font, fill=0)
            current_y += 18
            # Draw line under title
            draw.line(
                [(box_left + padding, current_y), (box_right - padding, current_y)],
                fill=0,
                width=1,
            )
            current_y += 4

        # Render content blocks
        inner_width = content_width - padding * 2 - border_width * 2
        for content_block in block.content_blocks:
            if isinstance(content_block, TextBlock):
                current_y = self._render_text_block(
                    draw, content_block,
                    margin_x + padding + border_width,
                    current_y,
                    inner_width
                )
            elif isinstance(content_block, SpacerBlock):
                current_y += content_block.pixels

        return box_bottom + 8  # Add some space after box

    def _image_to_tspl_commands(self, img) -> bytes:
        """Convert PIL Image to TSPL raster commands for label printers.

        TSPL (TSC Printer Language) is used by AIYIN IP-802 and similar
        label printers. Key differences from ESC/POS:
        - Text-based command structure
        - Inverted bitmap polarity (1=white, 0=black)
        - Explicit label size and gap commands

        Args:
            img: PIL Image in 1-bit mode

        Returns:
            TSPL command bytes ready to send to printer
        """
        width, height = img.size

        # Ensure width is multiple of 8 for byte alignment
        if width % 8 != 0:
            from PIL import Image
            new_width = (width // 8 + 1) * 8
            new_img = Image.new('1', (new_width, height), 1)  # White background
            new_img.paste(img, (0, 0))
            img = new_img
            width = new_width

        width_bytes = width // 8

        # Build bitmap data with TSPL polarity (inverted: 1=white, 0=black)
        bitmap_data = []
        for y in range(height):
            for xb in range(width_bytes):
                byte_val = 0
                for bit in range(8):
                    x = xb * 8 + bit
                    if x < img.width:
                        pixel = img.getpixel((x, y))
                        if pixel == 0:  # Black pixel in PIL
                            byte_val |= (0x80 >> bit)
                # CRITICAL: XOR with 0xFF to invert for TSPL polarity
                # In TSPL bitmap: bit=1 means NO PRINT (white), bit=0 means PRINT (black)
                byte_val = byte_val ^ 0xFF
                bitmap_data.append(byte_val)

        # Build TSPL command sequence
        commands = []

        # Label setup commands
        commands.append(f"SIZE {LABEL_WIDTH_MM} mm, {LABEL_HEIGHT_MM} mm\r\n".encode())
        commands.append(b"GAP 3 mm, 0 mm\r\n")  # Gap between labels
        commands.append(b"DIRECTION 1,0\r\n")   # Print direction
        commands.append(b"SET TEAR ON\r\n")     # Auto-advance to tear position
        commands.append(b"CLS\r\n")             # Clear image buffer

        # BITMAP command: BITMAP x,y,width_bytes,height,mode,<data>
        # mode 0 = OVERWRITE
        bitmap_header = f"BITMAP 0,0,{width_bytes},{height},0,".encode()
        commands.append(bitmap_header)
        commands.append(bytes(bitmap_data))
        commands.append(b"\r\n")

        # Print command: PRINT copies, pages
        commands.append(b"PRINT 1,1\r\n")

        return b''.join(commands)

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

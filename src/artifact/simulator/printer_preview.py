"""Thermal printer preview for simulator.

Renders a realistic preview of what would be printed on
the 58mm thermal receipt paper.
"""

import pygame
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from io import BytesIO

from artifact.printing.receipt import ReceiptGenerator
from artifact.printing.layout import ImageBlock


_PREVIEW_GENERATOR = ReceiptGenerator()


@dataclass
class PreviewImage:
    """Image metadata for preview rendering."""
    data: bytes
    width: int = 384


@dataclass
class PrintJob:
    """A print job with preview-ready content."""
    mode_name: str
    preview_lines: List[str]
    images: List[PreviewImage] = field(default_factory=list)


class ThermalPrinterPreview:
    """Renders a thermal printer receipt preview.

    Simulates a 58mm thermal receipt paper with:
    - Monospace dot-matrix style font
    - Paper texture
    - Fade/burn effects
    - Cut line at bottom
    - Caricature images (dithered for thermal printer)
    """

    # 58mm paper is ~384 pixels at 203 DPI (thermal printer standard)
    PAPER_WIDTH = 384
    CHAR_WIDTH = 12  # Approximate pixels per character
    CHARS_PER_LINE = 32  # Characters that fit per line

    def __init__(self):
        self._surface: Optional[pygame.Surface] = None
        self._current_job: Optional[PrintJob] = None
        self._scroll_offset: float = 0.0
        self._is_printing: bool = False
        self._print_progress: float = 0.0

        # Receipt content lines
        self._lines: List[str] = []
        self._line_styles: List[str] = []  # 'normal', 'bold', 'small', 'center', 'image'

        # Image surfaces for preview rendering
        self._image_surfaces: List[Tuple[pygame.Surface, int]] = []

        # Fonts (initialized on first render)
        self._font: Optional[pygame.font.Font] = None
        self._bold_font: Optional[pygame.font.Font] = None
        self._small_font: Optional[pygame.font.Font] = None

        # Visible height for scroll calculations
        self._visible_height: int = 400
        self._paper_width: int = self.PAPER_WIDTH

    def _init_fonts(self) -> None:
        """Initialize fonts for receipt rendering."""
        if self._font is not None:
            return

        # Try to find a monospace font
        font_paths = [
            "/System/Library/Fonts/Monaco.ttf",
            "/System/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]

        font_path = None
        for path in font_paths:
            try:
                pygame.font.Font(path, 14)
                font_path = path
                break
            except:
                continue

        if font_path:
            self._font = pygame.font.Font(font_path, 14)
            self._bold_font = pygame.font.Font(font_path, 16)
            self._small_font = pygame.font.Font(font_path, 11)
        else:
            self._font = pygame.font.SysFont("monospace", 14)
            self._bold_font = pygame.font.SysFont("monospace", 16, bold=True)
            self._small_font = pygame.font.SysFont("monospace", 11)

    def set_print_job(self, job: PrintJob) -> None:
        """Set a new print job and generate receipt content."""
        self._current_job = job
        self._lines = list(job.preview_lines)
        self._line_styles = [
            "image" if line.strip() == "[IMAGE]" else "normal"
            for line in self._lines
        ]
        self._image_surfaces = []

        for img in job.images:
            surface = self._load_image(img.data)
            if surface:
                self._image_surfaces.append((surface, img.width))

        self._is_printing = True
        self._print_progress = 0.0
        self._scroll_offset = 0.0

    def _load_image(self, image_data: bytes) -> Optional[pygame.Surface]:
        """Load image bytes into a pygame surface."""
        try:
            from PIL import Image

            # Load image from bytes
            img = Image.open(BytesIO(image_data))
            img = img.convert("L")  # Convert to grayscale for thermal look

            # Convert to pygame surface
            img_rgb = img.convert("RGB")
            raw_data = img_rgb.tobytes()
            return pygame.image.fromstring(
                raw_data, img_rgb.size, "RGB"
            )

        except Exception as e:
            print(f"Failed to load image: {e}")
            return None

    def update(self, delta_ms: float) -> None:
        """Update printing animation."""
        if self._is_printing:
            # Simulate paper feeding - about 2 seconds for full receipt
            self._print_progress += delta_ms / 2000
            if self._print_progress >= 1.0:
                self._print_progress = 1.0
                self._is_printing = False

    def scroll(self, direction: int, amount: int = 40) -> None:
        """Scroll the print preview up or down.

        Args:
            direction: -1 for up, 1 for down
            amount: Pixels to scroll per step
        """
        self._scroll_offset += direction * amount

        # Calculate total content height
        total_height = self._content_height(self._paper_width)

        # Clamp scroll offset - use tracked visible height
        max_scroll = max(0, total_height - self._visible_height)
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll))

    def set_visible_height(self, height: int) -> None:
        """Set the visible height for scroll calculations."""
        self._visible_height = height

    def _content_height(self, paper_w: int) -> int:
        """Estimate total content height for scrolling."""
        height = 40
        image_index = 0
        for line, style in zip(self._lines, self._line_styles):
            if style == "image":
                if image_index < len(self._image_surfaces):
                    surface, target_width = self._image_surfaces[image_index]
                    image_index += 1
                    orig_w, orig_h = surface.get_size()
                    img_w = min(target_width, paper_w)
                    img_h = int(img_w * orig_h / orig_w)
                    height += img_h + 5
                else:
                    height += 18
            else:
                height += 18
        return height

    def render(self, screen: pygame.Surface, x: int, y: int, width: int, height: int) -> None:
        """Render the printer preview at the specified position."""
        self._init_fonts()

        # Background (printer housing)
        housing_rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (40, 45, 55), housing_rect, border_radius=8)
        pygame.draw.rect(screen, (60, 65, 75), housing_rect, 2, border_radius=8)

        # Title
        if self._font:
            title = "◈ THERMAL PRINT ◈"
            title_surf = self._font.render(title, True, (100, 150, 200))
            screen.blit(title_surf, (x + (width - title_surf.get_width()) // 2, y + 5))

        # Paper slot area
        slot_rect = pygame.Rect(x + 10, y + 28, width - 20, height - 38)
        pygame.draw.rect(screen, (25, 28, 35), slot_rect, border_radius=4)

        # Paper surface
        paper_x = x + 15
        paper_y = y + 32
        paper_w = width - 30
        paper_visible_h = height - 45
        self._paper_width = paper_w
        paper_height = self._content_height(paper_w)
        visible_height = min(paper_height, height - 40)

        # Track visible height for scroll calculations
        self._visible_height = paper_visible_h

        # Create paper texture
        paper_surf = pygame.Surface((paper_w, paper_visible_h))
        paper_surf.fill((250, 248, 240))  # Slightly off-white paper color

        # Add subtle paper texture (horizontal lines)
        for py in range(0, paper_visible_h, 3):
            alpha = 5 + (py % 6)
            pygame.draw.line(paper_surf, (230, 228, 220), (0, py), (paper_w, py))

        # Render receipt content
        if self._current_job and self._font:
            line_y = 10 - int(self._scroll_offset)  # Apply scroll offset

            # Calculate how many lines to show based on print progress
            visible_lines = int(len(self._lines) * self._print_progress) if self._is_printing else len(self._lines)

            image_index = 0
            for i, (line, style) in enumerate(zip(self._lines[:visible_lines], self._line_styles[:visible_lines])):
                # Skip lines that are above the visible area
                if line_y < -200:
                    if style == "image" and image_index < len(self._image_surfaces):
                        surface, target_width = self._image_surfaces[image_index]
                        image_index += 1
                        orig_w, orig_h = surface.get_size()
                        img_w = min(target_width, paper_w)
                        img_h = int(img_w * orig_h / orig_w)
                        line_y += img_h + 5
                    else:
                        line_y += 18
                    continue

                # Stop if we're past the visible area
                if line_y > paper_visible_h + 20:
                    break

                # Handle image style - full-width or QR-width depending on layout
                if style == "image" and image_index < len(self._image_surfaces):
                    surface, target_width = self._image_surfaces[image_index]
                    image_index += 1
                    img_width = min(target_width, paper_w)
                    orig_w, orig_h = surface.get_size()
                    img_height = int(img_width * orig_h / orig_w)
                    scaled_img = pygame.transform.scale(
                        surface, (img_width, img_height)
                    )
                    img_x = (paper_w - img_width) // 2
                    paper_surf.blit(scaled_img, (img_x, line_y))
                    line_y += img_height + 5
                    continue

                # Choose font based on style
                if style == "bold":
                    font = self._bold_font
                    color = (20, 20, 20)
                elif style == "small":
                    font = self._small_font
                    color = (80, 80, 80)
                else:
                    font = self._font
                    color = (40, 40, 40)

                if font:
                    text_surf = font.render(line, True, color)

                    # Center if needed
                    if style == "center":
                        text_x = (paper_w - text_surf.get_width()) // 2
                    else:
                        text_x = 8

                    paper_surf.blit(text_surf, (text_x, line_y))

                line_y += 18 if style != "small" else 14

            # Printing animation - paper feed effect
            if self._is_printing:
                # Add "printing" indicator
                dots = "." * (int(pygame.time.get_ticks() / 300) % 4)
                if self._font:
                    status = f"ПЕЧАТЬ{dots}"
                    status_surf = self._font.render(status, True, (200, 100, 50))
                    paper_surf.blit(status_surf, (paper_w - 80, paper_visible_h - 20))

        # Draw paper
        screen.blit(paper_surf, (paper_x, paper_y))

        # Paper edge shadow
        pygame.draw.rect(screen, (200, 195, 185), (paper_x, paper_y, paper_w, 3))

        # Print slot overlay (top)
        slot_overlay = pygame.Rect(x + 10, y + 25, width - 20, 10)
        pygame.draw.rect(screen, (35, 38, 45), slot_overlay)

        # Scroll indicators if content is longer than visible area
        if self._current_job:
            total_height = self._content_height(paper_w)

            if total_height > paper_visible_h:
                # Show scroll hint
                if self._font:
                    # Up arrow if can scroll up
                    if self._scroll_offset > 0:
                        up_surf = self._font.render("▲", True, (100, 150, 200))
                        screen.blit(up_surf, (x + width - 25, y + 35))

                    # Down arrow if can scroll down
                    max_scroll = max(0, total_height - paper_visible_h)
                    if self._scroll_offset < max_scroll:
                        down_surf = self._font.render("▼", True, (100, 150, 200))
                        screen.blit(down_surf, (x + width - 25, y + height - 25))

    def is_printing(self) -> bool:
        """Check if currently printing."""
        return self._is_printing

    def has_content(self) -> bool:
        """Check if there's content to display."""
        return self._current_job is not None


def create_print_job_from_result(result: Dict[str, Any]) -> PrintJob:
    """Create a PrintJob from a mode result."""
    mode_type = (
        result.get("type") or
        result.get("mode") or
        result.get("mode_name") or
        "generic"
    )

    receipt = _PREVIEW_GENERATOR.generate_receipt(mode_type, result)
    lines = receipt.preview.splitlines()
    if lines and lines[0].startswith("+"):
        lines = lines[1:-1]

    preview_lines: List[str] = []
    for line in lines:
        if line.startswith("|") and line.endswith("|"):
            line = line[1:-1]
        preview_lines.append(line)

    images: List[PreviewImage] = []
    for block in receipt.layout.blocks:
        if isinstance(block, ImageBlock):
            images.append(PreviewImage(data=block.image_data, width=block.width))

    return PrintJob(
        mode_name=mode_type,
        preview_lines=preview_lines,
        images=images,
    )

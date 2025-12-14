"""Thermal printer preview for simulator.

Renders a realistic preview of what would be printed on
the 58mm thermal receipt paper.
"""

import pygame
import math
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO


@dataclass
class PrintJob:
    """A print job with content to render."""
    mode_name: str
    title: str
    main_text: str
    secondary_text: Optional[str] = None
    lucky_number: Optional[int] = None
    lucky_color: Optional[str] = None
    traits: Optional[List[str]] = None
    caricature: Optional[bytes] = None
    timestamp: Optional[datetime] = None


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
    CARICATURE_SIZE = 200  # Caricature display size in pixels (larger for full width)

    def __init__(self):
        self._surface: Optional[pygame.Surface] = None
        self._current_job: Optional[PrintJob] = None
        self._scroll_offset: float = 0.0
        self._is_printing: bool = False
        self._print_progress: float = 0.0

        # Receipt content lines
        self._lines: List[str] = []
        self._line_styles: List[str] = []  # 'normal', 'bold', 'small', 'center', 'image'

        # Caricature image surface (pygame)
        self._caricature_surface: Optional[pygame.Surface] = None

        # Fonts (initialized on first render)
        self._font: Optional[pygame.font.Font] = None
        self._bold_font: Optional[pygame.font.Font] = None
        self._small_font: Optional[pygame.font.Font] = None

        # Visible height for scroll calculations
        self._visible_height: int = 400

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
        self._lines = []
        self._line_styles = []
        self._caricature_surface = None

        # Load caricature image if available
        if job.caricature:
            self._load_caricature(job.caricature)

        self._generate_receipt_content()
        self._is_printing = True
        self._print_progress = 0.0

    def _load_caricature(self, image_data: bytes) -> None:
        """Load caricature image bytes into a pygame surface."""
        try:
            from PIL import Image

            # Load image from bytes
            img = Image.open(BytesIO(image_data))
            img = img.convert("L")  # Convert to grayscale for thermal look

            # Resize to fit receipt
            img = img.resize((self.CARICATURE_SIZE, self.CARICATURE_SIZE), Image.Resampling.NEAREST)

            # Convert to pygame surface
            img_rgb = img.convert("RGB")
            raw_data = img_rgb.tobytes()
            self._caricature_surface = pygame.image.fromstring(
                raw_data, img_rgb.size, "RGB"
            )

        except Exception as e:
            print(f"Failed to load caricature: {e}")
            self._caricature_surface = None

    def _generate_receipt_content(self) -> None:
        """Generate the receipt text content."""
        if not self._current_job:
            return

        job = self._current_job

        # Header
        self._add_line("═" * 32, "normal")
        self._add_line("      ★ V N V N C ★", "bold")
        self._add_line("  МАШИНА ПРЕДСКАЗАНИЙ", "center")
        self._add_line("═" * 32, "normal")
        self._add_line("", "normal")

        # Mode title
        self._add_line(f"◆ {job.title.upper()} ◆", "bold")
        self._add_line("─" * 32, "normal")
        self._add_line("", "normal")

        # Caricature image (if available)
        if job.caricature and self._caricature_surface:
            self._add_line("ТВОЙ ПОРТРЕТ:", "small")
            self._add_line("", "normal")
            # Add special marker for image rendering
            self._add_line("__CARICATURE__", "image")
            self._add_line("", "normal")

        # Main prediction text - word wrap
        if job.main_text:
            self._add_line("ПРЕДСКАЗАНИЕ:", "small")
            self._add_line("", "normal")
            wrapped = self._word_wrap(job.main_text, 30)
            for line in wrapped:
                self._add_line(line, "normal")
            self._add_line("", "normal")

        # Lucky number
        if job.lucky_number is not None:
            self._add_line("", "normal")
            self._add_line(f"СЧАСТЛИВОЕ ЧИСЛО: {job.lucky_number}", "bold")

        # Lucky color
        if job.lucky_color:
            self._add_line(f"СЧАСТЛИВЫЙ ЦВЕТ: {job.lucky_color}", "normal")

        # Traits
        if job.traits:
            self._add_line("", "normal")
            self._add_line("ЧЕРТЫ ХАРАКТЕРА:", "small")
            for trait in job.traits[:3]:
                self._add_line(f"  • {trait}", "normal")

        # Timestamp
        self._add_line("", "normal")
        self._add_line("─" * 32, "normal")
        timestamp = job.timestamp or datetime.now()
        self._add_line(timestamp.strftime("%d.%m.%Y  %H:%M"), "center")

        # Footer
        self._add_line("", "normal")
        self._add_line("Спасибо за визит!", "center")
        self._add_line("", "normal")
        self._add_line("    ★ VNVNC.RU ★", "bold")
        self._add_line("", "normal")
        self._add_line("▼ ▼ ▼ ▼ ▼ ▼ ▼ ▼", "center")  # Cut line

    def _add_line(self, text: str, style: str) -> None:
        """Add a line to the receipt."""
        self._lines.append(text)
        self._line_styles.append(style)

    def _word_wrap(self, text: str, max_chars: int) -> List[str]:
        """Word wrap text to fit within max characters, breaking long words."""
        words = text.split()
        lines = []
        current_line = ""

        for word in words:
            # If word itself is too long, break it
            if len(word) > max_chars:
                # Flush current line first
                if current_line:
                    lines.append(current_line)
                    current_line = ""
                # Break the long word
                while len(word) > max_chars:
                    lines.append(word[:max_chars - 1] + "-")
                    word = word[max_chars - 1:]
                # Continue with the remainder
                current_line = word
            elif len(current_line) + len(word) + 1 <= max_chars:
                if current_line:
                    current_line += " " + word
                else:
                    current_line = word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word

        if current_line:
            lines.append(current_line)

        return lines

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
        total_height = len(self._lines) * 18 + 40
        if self._caricature_surface:
            total_height += self.CARICATURE_SIZE + 30

        # Clamp scroll offset - use tracked visible height
        max_scroll = max(0, total_height - self._visible_height)
        self._scroll_offset = max(0, min(self._scroll_offset, max_scroll))

    def set_visible_height(self, height: int) -> None:
        """Set the visible height for scroll calculations."""
        self._visible_height = height

    def render(self, screen: pygame.Surface, x: int, y: int, width: int, height: int) -> None:
        """Render the printer preview at the specified position."""
        self._init_fonts()

        # Create paper surface
        paper_height = len(self._lines) * 18 + 40
        visible_height = min(paper_height, height - 40)

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

            for i, (line, style) in enumerate(zip(self._lines[:visible_lines], self._line_styles[:visible_lines])):
                # Skip lines that are above the visible area
                if line_y < -200:
                    if style == "image" and self._caricature_surface:
                        line_y += self.CARICATURE_SIZE + 10
                    else:
                        line_y += 18
                    continue

                # Stop if we're past the visible area
                if line_y > paper_visible_h + 20:
                    break

                # Handle image style (caricature) - FULL WIDTH, NO FRAME
                if style == "image" and self._caricature_surface:
                    # Scale caricature to FULL paper width (no margins)
                    img_width = paper_w
                    # Calculate height maintaining aspect ratio
                    orig_w, orig_h = self._caricature_surface.get_size()
                    img_height = int(img_width * orig_h / orig_w)
                    scaled_img = pygame.transform.scale(
                        self._caricature_surface, (img_width, img_height)
                    )
                    # No centering - full width from edge to edge
                    paper_surf.blit(scaled_img, (0, line_y))
                    # NO BORDER - clean edge-to-edge image
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
            total_height = len(self._lines) * 18 + 40
            if self._caricature_surface:
                total_height += self.CARICATURE_SIZE + 30

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
    mode_type = result.get("type", "unknown")

    # Map mode types to titles
    title_map = {
        "ai_prophet": "ИИ ПРОРОК",
        "fortune": "ПРЕДСКАЗАНИЕ",
        "zodiac": "ГОРОСКОП",
        "roulette": "РУЛЕТКА",
        "quiz": "ВИКТОРИНА",
        "guess_me": "КТО Я?",
        "squid_game": "ИГРА В КАЛЬМАРА",
        "roast": "ПРОЖАРКА",
        "autopsy": "ДИАГНОЗ",
    }

    # Get main text - different modes use different keys
    main_text = (
        result.get("prediction") or
        result.get("display_text") or
        result.get("roast") or  # Roast mode
        result.get("diagnosis") or  # Autopsy mode
        result.get("horoscope") or  # Zodiac mode
        ""
    )

    # Get image - different modes use different keys
    image_data = (
        result.get("caricature") or
        result.get("doodle") or  # Roast mode
        result.get("scan_image") or  # Autopsy mode
        result.get("sketch") or  # Squid game
        None
    )

    return PrintJob(
        mode_name=mode_type,
        title=title_map.get(mode_type, "ARTIFACT"),
        main_text=main_text,
        lucky_number=result.get("lucky_number"),
        lucky_color=result.get("lucky_color"),
        traits=result.get("traits"),
        caricature=image_data,
        timestamp=datetime.fromisoformat(result.get("timestamp")) if result.get("timestamp") else None,
    )

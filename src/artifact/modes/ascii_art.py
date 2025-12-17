"""ASCII Art Mode - Transform your face into character art.

Your face becomes a living terminal masterpiece! Watch as you're
rendered in classic ASCII characters, block elements, or custom
character sets in real-time.

Controls:
- LEFT: Cycle through character sets
- RIGHT: Change color scheme
- START: Capture your ASCII portrait
"""

from typing import Optional, List, Tuple
from enum import Enum, auto
import math
import random
import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.fonts import load_font, draw_text_bitmap
from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect
from artifact.graphics.algorithmic_art import ASCIIRenderer, hsv_to_rgb


class CharacterSet(Enum):
    """Available character sets for ASCII rendering."""
    STANDARD = auto()      # .:-=+*#%@
    BLOCKS = auto()        # ░▒▓█
    DENSE = auto()         # Many characters
    SIMPLE = auto()        # .oO@
    BINARY = auto()        # 01
    MATRIX = auto()        # Matrix-style
    EMOJI = auto()         # Simple shapes


class ColorScheme(Enum):
    """Color schemes for ASCII art."""
    GREEN = auto()         # Classic terminal green
    AMBER = auto()         # Amber phosphor
    WHITE = auto()         # White on black
    RAINBOW = auto()       # Rainbow gradient
    MATRIX = auto()        # Matrix green fade
    CYBER = auto()         # Cyberpunk neon


class AsciiPhase(Enum):
    """ASCII mode phases."""
    INTRO = "intro"
    LIVE = "live"
    CAPTURE = "capture"


class AsciiArtMode(BaseMode):
    """Interactive ASCII art mode.

    Real-time ASCII rendering of camera feed with
    multiple character sets and color schemes.
    """

    name = "ascii_art"
    display_name = "АСКИ"
    icon = "text"
    style = "terminal"

    # Character sets
    CHARSETS = {
        CharacterSet.STANDARD: " .:-=+*#%@",
        CharacterSet.BLOCKS: " ░▒▓█",
        CharacterSet.DENSE: " .'`^\",:;Il!i><~+_-?][}{1)(|/\\tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
        CharacterSet.SIMPLE: " .oO@",
        CharacterSet.BINARY: " 01",
        CharacterSet.MATRIX: " 0123456789",
        CharacterSet.EMOJI: " ○●◐◑◒◓",
    }

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._sub_phase = AsciiPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0

        # Camera
        self._camera = None
        self._camera_frame: Optional[NDArray] = None

        # ASCII renderer
        self._renderer: Optional[ASCIIRenderer] = None
        self._ascii_chars: List[List[str]] = []

        # Settings
        self._charset = CharacterSet.STANDARD
        self._charset_index = 0
        self._charsets = list(CharacterSet)

        self._color_scheme = ColorScheme.GREEN
        self._color_index = 0
        self._color_schemes = list(ColorScheme)

        # Cell size (characters per pixel block)
        self._cell_size = 8  # 128/8 = 16 chars wide

        # Captured frame
        self._captured_frame: Optional[NDArray] = None
        self._captured_chars: List[List[str]] = []

        # Animation
        self._cursor_blink = 0.0
        self._rain_drops: List[dict] = []

    def on_enter(self) -> None:
        """Initialize mode."""
        self._sub_phase = AsciiPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0
        self._charset_index = 0
        self._charset = self._charsets[0]
        self._color_index = 0
        self._color_scheme = self._color_schemes[0]

        # Initialize renderer
        self._renderer = ASCIIRenderer(
            charset=self.CHARSETS[self._charset],
            cell_size=self._cell_size
        )

        # Try to open camera
        try:
            from artifact.simulator.mock_hardware.camera import create_camera
            self._camera = create_camera(resolution=(128, 128))
            self._camera.open()
        except Exception:
            self._camera = None

        # Initialize rain effect
        self._rain_drops = []
        for _ in range(10):
            self._rain_drops.append({
                'x': random.randint(0, 15),
                'y': random.uniform(-16, 0),
                'speed': random.uniform(0.02, 0.05),
                'char': random.choice(list(self.CHARSETS[CharacterSet.MATRIX]))
            })

        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        """Cleanup."""
        if self._camera:
            try:
                self._camera.close()
            except Exception:
                pass
            self._camera = None

    def handle_input(self, event: Event) -> None:
        """Handle user input."""
        if self._sub_phase == AsciiPhase.INTRO:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = AsciiPhase.LIVE
                self._time_in_phase = 0.0
            return

        if self._sub_phase == AsciiPhase.LIVE:
            if event.type == EventType.ARCADE_LEFT:
                # Cycle character set
                self._charset_index = (self._charset_index + 1) % len(self._charsets)
                self._charset = self._charsets[self._charset_index]
                self._renderer = ASCIIRenderer(
                    charset=self.CHARSETS[self._charset],
                    cell_size=self._cell_size
                )
                self.context.audio.play_ui_click()

            elif event.type == EventType.ARCADE_RIGHT:
                # Cycle color scheme
                self._color_index = (self._color_index + 1) % len(self._color_schemes)
                self._color_scheme = self._color_schemes[self._color_index]
                self.context.audio.play_ui_click()

            elif event.type == EventType.BUTTON_PRESS:
                # Capture
                self._capture_image()
                self.context.audio.play_success()

        elif self._sub_phase == AsciiPhase.CAPTURE:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = AsciiPhase.LIVE
                self._time_in_phase = 0.0

    def update(self, delta_ms: float) -> None:
        """Update mode state."""
        self._time_in_phase += delta_ms
        self._total_time += delta_ms
        self._cursor_blink = (self._cursor_blink + delta_ms / 500) % 2

        # Update rain drops
        for drop in self._rain_drops:
            drop['y'] += drop['speed'] * delta_ms
            if drop['y'] > 16:
                drop['y'] = random.uniform(-5, 0)
                drop['x'] = random.randint(0, 15)
                drop['char'] = random.choice(list(self.CHARSETS[CharacterSet.MATRIX]))

        if self._sub_phase == AsciiPhase.INTRO:
            if self._time_in_phase > 2500:
                self._sub_phase = AsciiPhase.LIVE
                self._time_in_phase = 0.0

        elif self._sub_phase == AsciiPhase.LIVE:
            # Capture camera
            self._capture_camera()

            # Process to ASCII
            if self._camera_frame is not None:
                self._ascii_chars = self._renderer.render(self._camera_frame)

        elif self._sub_phase == AsciiPhase.CAPTURE:
            if self._time_in_phase > 3000:
                self._sub_phase = AsciiPhase.LIVE
                self._time_in_phase = 0.0

    def _capture_camera(self):
        """Capture frame from camera."""
        if self._camera and self._camera.is_open:
            try:
                frame = self._camera.capture_frame()
                if frame is not None:
                    if frame.shape[:2] != (128, 128):
                        from PIL import Image
                        img = Image.fromarray(frame)
                        img = img.resize((128, 128), Image.Resampling.BILINEAR)
                        frame = np.array(img)
                    self._camera_frame = frame
            except Exception:
                pass
        else:
            self._create_demo_frame()

    def _create_demo_frame(self):
        """Create demo pattern if no camera."""
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        t = self._total_time / 1000

        # Create animated pattern
        cx, cy = 64, 64

        for y in range(128):
            for x in range(128):
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx * dx + dy * dy)

                # Animated face
                if dist < 45:
                    # Pulsing brightness
                    brightness = 150 + 50 * math.sin(dist * 0.1 + t * 2)
                    v = max(0, min(255, int(brightness)))
                    frame[y, x] = (v, v, v)

                    # Eyes
                    if 0 < y - 45 < 20:
                        if abs(x - 45) < 8 or abs(x - 83) < 8:
                            frame[y, x] = (0, 0, 0)

        self._camera_frame = frame

    def _capture_image(self):
        """Capture current ASCII state."""
        self._captured_frame = self._camera_frame.copy() if self._camera_frame is not None else None
        self._captured_chars = [row[:] for row in self._ascii_chars]
        self._sub_phase = AsciiPhase.CAPTURE
        self._time_in_phase = 0.0

    def _get_char_color(self, char: str, x: int, y: int) -> Tuple[int, int, int]:
        """Get color for a character based on scheme."""
        charset = self.CHARSETS[self._charset]
        intensity = charset.index(char) / max(1, len(charset) - 1) if char in charset else 0.5

        if self._color_scheme == ColorScheme.GREEN:
            return (int(50 * intensity), int(255 * intensity), int(50 * intensity))

        elif self._color_scheme == ColorScheme.AMBER:
            return (int(255 * intensity), int(180 * intensity), int(50 * intensity))

        elif self._color_scheme == ColorScheme.WHITE:
            v = int(255 * intensity)
            return (v, v, v)

        elif self._color_scheme == ColorScheme.RAINBOW:
            hue = (x * 20 + y * 10 + self._total_time / 20) % 360
            return hsv_to_rgb(hue, 1.0, intensity)

        elif self._color_scheme == ColorScheme.MATRIX:
            # Fade effect based on y position
            fade = (y / 16) * 0.5 + 0.5
            return (0, int(255 * intensity * fade), int(50 * intensity * fade))

        elif self._color_scheme == ColorScheme.CYBER:
            # Alternating neon colors
            if (x + y) % 2 == 0:
                return (int(255 * intensity), int(50 * intensity), int(200 * intensity))
            else:
                return (int(50 * intensity), int(255 * intensity), int(200 * intensity))

        return (int(255 * intensity), int(255 * intensity), int(255 * intensity))

    # =========================================================================
    # RENDERING
    # =========================================================================

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        t = self._time_in_phase

        if self._sub_phase == AsciiPhase.INTRO:
            self._render_intro(buffer, t)
        elif self._sub_phase == AsciiPhase.LIVE:
            self._render_live(buffer, t)
        elif self._sub_phase == AsciiPhase.CAPTURE:
            self._render_capture(buffer, t)

    def _render_intro(self, buffer: NDArray[np.uint8], t: float):
        """Render intro screen."""
        fill(buffer, (0, 10, 0))

        # Matrix rain effect
        font = load_font("cyrillic")
        for drop in self._rain_drops:
            x = int(drop['x'] * 8)
            y = int(drop['y'] * 8)
            if 0 <= y < 128:
                # Bright head
                draw_text_bitmap(buffer, drop['char'], x, y, (100, 255, 100), font, scale=1)
                # Trail
                for trail in range(1, 5):
                    trail_y = y - trail * 8
                    if 0 <= trail_y < 128:
                        fade = 1 - trail / 5
                        color = (0, int(200 * fade), 0)
                        char = random.choice(list(self.CHARSETS[CharacterSet.MATRIX]))
                        draw_text_bitmap(buffer, char, x, trail_y, color, font, scale=1)

        # Title
        draw_rect(buffer, 15, 35, 98, 58, (0, 0, 0))
        draw_centered_text(buffer, "ASCII", 42, (50, 255, 50), scale=2)
        draw_centered_text(buffer, "АРТ", 62, (100, 255, 100), scale=2)

        # Blinking cursor
        if self._cursor_blink < 1:
            draw_rect(buffer, 64 + 20, 65, 8, 14, (50, 255, 50))

        draw_animated_text(buffer, "НАЖМИ СТАРТ", 115, (50, 150, 50), t, TextEffect.PULSE, scale=1)

    def _render_live(self, buffer: NDArray[np.uint8], t: float):
        """Render live ASCII view."""
        # Background
        if self._color_scheme == ColorScheme.GREEN or self._color_scheme == ColorScheme.MATRIX:
            fill(buffer, (0, 10, 0))
        elif self._color_scheme == ColorScheme.AMBER:
            fill(buffer, (10, 5, 0))
        else:
            fill(buffer, (0, 0, 0))

        # Render ASCII characters
        font = load_font("cyrillic")

        for row_idx, row in enumerate(self._ascii_chars):
            y = row_idx * 8
            if y >= 128:
                break

            for col_idx, char in enumerate(row):
                x = col_idx * 8
                if x >= 128:
                    break

                color = self._get_char_color(char, col_idx, row_idx)
                draw_text_bitmap(buffer, char, x, y, color, font, scale=1)

        # Matrix rain overlay (subtle)
        if self._color_scheme == ColorScheme.MATRIX:
            for drop in self._rain_drops:
                x = int(drop['x'] * 8)
                y = int(drop['y'] * 8)
                if 0 <= y < 128 and 0 <= x < 128:
                    # Add bright spot
                    buffer[y, x] = (100, 255, 100)

        # UI overlay
        charset_names = {
            CharacterSet.STANDARD: "СТД",
            CharacterSet.BLOCKS: "БЛК",
            CharacterSet.DENSE: "ПЛТ",
            CharacterSet.SIMPLE: "ПРС",
            CharacterSet.BINARY: "БИН",
            CharacterSet.MATRIX: "МТР",
            CharacterSet.EMOJI: "ЭМО",
        }

        color_names = {
            ColorScheme.GREEN: "ЗЕЛ",
            ColorScheme.AMBER: "АМБ",
            ColorScheme.WHITE: "БЕЛ",
            ColorScheme.RAINBOW: "РАД",
            ColorScheme.MATRIX: "МТР",
            ColorScheme.CYBER: "КИБ",
        }

        # Info boxes
        draw_rect(buffer, 0, 0, 28, 12, (0, 0, 0))
        draw_text_bitmap(buffer, charset_names.get(self._charset, "?"), 2, 2,
                        (50, 255, 50), font, scale=1)

        draw_rect(buffer, 100, 0, 28, 12, (0, 0, 0))
        draw_text_bitmap(buffer, color_names.get(self._color_scheme, "?"), 102, 2,
                        (255, 200, 50), font, scale=1)

        # Hint
        hint_alpha = 0.4 + 0.2 * math.sin(t / 400)
        hint_color = tuple(int(c * hint_alpha) for c in (50, 150, 50))
        draw_centered_text(buffer, "<ШРИФТ  ЦВЕТ>", 118, hint_color, scale=1)

    def _render_capture(self, buffer: NDArray[np.uint8], t: float):
        """Render capture confirmation."""
        # Render captured ASCII
        fill(buffer, (0, 10, 0))
        font = load_font("cyrillic")

        for row_idx, row in enumerate(self._captured_chars):
            y = row_idx * 8
            if y >= 128:
                break

            for col_idx, char in enumerate(row):
                x = col_idx * 8
                if x >= 128:
                    break

                color = self._get_char_color(char, col_idx, row_idx)
                draw_text_bitmap(buffer, char, x, y, color, font, scale=1)

        # Flash effect
        flash = max(0, 1 - t / 300)
        if flash > 0:
            buffer[:] = np.clip(buffer.astype(np.int16) + int(100 * flash), 0, 255).astype(np.uint8)

        # Confirmation
        draw_rect(buffer, 15, 48, 98, 32, (0, 20, 0))
        draw_centered_text(buffer, "СОХРАНЕНО!", 55, (50, 255, 50), scale=2)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display with ASCII-style animation."""
        from artifact.graphics.primitives import clear

        clear(buffer)
        font = load_font("cyrillic")

        if self._sub_phase == AsciiPhase.LIVE:
            # Scrolling ASCII art pattern
            offset = int(self._total_time / 100) % 48

            for x in range(48):
                idx = (x + offset) % len(self.CHARSETS[self._charset])
                char = self.CHARSETS[self._charset][idx % len(self.CHARSETS[self._charset])]

                # Color based on position
                intensity = (math.sin(x * 0.3 + self._total_time / 200) + 1) / 2
                color = (
                    int(50 * intensity),
                    int(255 * intensity),
                    int(50 * intensity)
                )

                # Draw character (scaled to fit ticker)
                if x % 6 == 0:  # Every 6 pixels
                    draw_text_bitmap(buffer, char, x, 0, color, font, scale=1)

        elif self._sub_phase == AsciiPhase.INTRO:
            # Matrix rain on ticker
            for drop in self._rain_drops[:5]:
                x = int(drop['x'] * 3) % 48
                y = int(drop['y']) % 8
                if 0 <= y < 8 and 0 <= x < 48:
                    buffer[y, x] = (100, 255, 100)

        else:  # CAPTURE
            # Flash
            intensity = max(0, 1 - self._time_in_phase / 500)
            v = int(200 * intensity)
            buffer[:] = (0, v, 0)

    def get_lcd_text(self) -> str:
        """Get LCD text - shows current settings."""
        if self._sub_phase == AsciiPhase.INTRO:
            return "   ASCII ART   "

        elif self._sub_phase == AsciiPhase.LIVE:
            charset_names = {
                CharacterSet.STANDARD: "СТАНДАРТ",
                CharacterSet.BLOCKS: "БЛОКИ",
                CharacterSet.DENSE: "ПЛОТНЫЙ",
                CharacterSet.SIMPLE: "ПРОСТОЙ",
                CharacterSet.BINARY: "БИНАРНЫЙ",
                CharacterSet.MATRIX: "МАТРИЦА",
                CharacterSet.EMOJI: "СИМВОЛЫ",
            }
            name = charset_names.get(self._charset, "ASCII")
            return f" {name:^14} "

        elif self._sub_phase == AsciiPhase.CAPTURE:
            return "  СОХРАНЕНО!   "

        return "   ASCII ART   "

"""Dither Art Mode - Classic dithering algorithms for retro digital art.

Transform your face into stunning pixel art using legendary dithering
algorithms from computing history. Floyd-Steinberg, Atkinson, Bayer ordered,
halftone dots - each creates a unique aesthetic.

Controls:
- LEFT: Cycle through dithering algorithms
- RIGHT: Change color palette
- START: Capture your pixel masterpiece
"""

from typing import Optional, List, Tuple
from enum import Enum, auto
import math
import random
import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_circle
from artifact.graphics.fonts import load_font, draw_text_bitmap
from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect
from artifact.graphics.algorithmic_art import (
    Dithering, hsv_to_rgb, posterize, color_quantize,
    PALETTE_GAMEBOY, PALETTE_CGA, PALETTE_PICO8
)


class DitherAlgorithm(Enum):
    """Available dithering algorithms."""
    FLOYD_STEINBERG = auto()   # Classic error diffusion
    ATKINSON = auto()          # Mac classic look
    BAYER_4X4 = auto()         # Ordered dithering small
    BAYER_8X8 = auto()         # Ordered dithering large
    HALFTONE = auto()          # Newspaper dots
    THRESHOLD = auto()         # Simple threshold


class ColorMode(Enum):
    """Color palette modes."""
    MONO = auto()              # Black and white
    GAMEBOY = auto()           # Classic green
    CGA = auto()               # Cyan/Magenta
    PICO8 = auto()             # 16 colors
    THERMAL = auto()           # Thermal printer
    NEON = auto()              # Neon glow
    AMBER = auto()             # Amber monitor


class DitherPhase(Enum):
    """Dither mode phases."""
    INTRO = "intro"
    LIVE = "live"
    CAPTURE = "capture"


class DitherArtMode(BaseMode):
    """Interactive dithering art mode.

    Real-time dithering effects applied to camera feed,
    creating retro pixel art from your face.
    """

    name = "dither_art"
    display_name = "DITHER"
    icon = "pixel"
    style = "retro"

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._sub_phase = DitherPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0

        # Camera
        self._camera = None
        self._camera_frame: Optional[NDArray] = None
        self._processed_frame: Optional[NDArray] = None

        # Algorithm settings
        self._algorithm = DitherAlgorithm.FLOYD_STEINBERG
        self._algo_index = 0
        self._algorithms = list(DitherAlgorithm)

        # Color settings
        self._color_mode = ColorMode.MONO
        self._color_index = 0
        self._color_modes = list(ColorMode)

        # Effect parameters
        self._threshold = 128
        self._halftone_size = 4
        self._contrast = 1.2

        # Animation
        self._transition_progress = 0.0
        self._prev_frame: Optional[NDArray] = None

        # Captured image
        self._captured_image: Optional[NDArray] = None

        # Ticker animation
        self._ticker_pattern: List[bool] = [False] * 48
        self._ticker_offset = 0

    def on_enter(self) -> None:
        """Initialize mode."""
        self._sub_phase = DitherPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0
        self._algo_index = 0
        self._algorithm = self._algorithms[0]
        self._color_index = 0
        self._color_mode = self._color_modes[0]

        # Try to open camera
        try:
            from artifact.simulator.mock_hardware.camera import create_camera
            self._camera = create_camera(resolution=(128, 128))
            self._camera.open()
        except Exception:
            self._camera = None

        # Initialize ticker pattern
        self._update_ticker_pattern()

        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        """Cleanup."""
        if self._camera:
            try:
                self._camera.close()
            except Exception:
                pass
            self._camera = None

    def on_input(self, event: Event) -> bool:
        """Handle user input."""
        if self._sub_phase == DitherPhase.INTRO:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = DitherPhase.LIVE
                self._time_in_phase = 0.0
                return True
            return False

        if self._sub_phase == DitherPhase.LIVE:
            if event.type == EventType.ARCADE_LEFT:
                # Cycle algorithm
                self._prev_frame = self._processed_frame
                self._algo_index = (self._algo_index + 1) % len(self._algorithms)
                self._algorithm = self._algorithms[self._algo_index]
                self._transition_progress = 0.0
                self._update_ticker_pattern()
                hasattr(self.context, "audio") and self.context.audio and self.context.audio.play_ui_click()
                return True

            elif event.type == EventType.ARCADE_RIGHT:
                # Cycle color mode
                self._color_index = (self._color_index + 1) % len(self._color_modes)
                self._color_mode = self._color_modes[self._color_index]
                hasattr(self.context, "audio") and self.context.audio and self.context.audio.play_ui_click()
                return True

            elif event.type == EventType.BUTTON_PRESS:
                # Capture
                self._capture_image()
                hasattr(self.context, "audio") and self.context.audio and self.context.audio.play_success()
                return True

        elif self._sub_phase == DitherPhase.CAPTURE:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = DitherPhase.LIVE
                self._time_in_phase = 0.0
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        """Update mode state."""
        self._time_in_phase += delta_ms
        self._total_time += delta_ms

        # Update transition
        if self._transition_progress < 1.0:
            self._transition_progress = min(1.0, self._transition_progress + delta_ms / 300)

        # Update ticker offset
        self._ticker_offset = (self._ticker_offset + delta_ms / 100) % 48

        if self._sub_phase == DitherPhase.INTRO:
            if self._time_in_phase > 2500:
                self._sub_phase = DitherPhase.LIVE
                self._time_in_phase = 0.0

        elif self._sub_phase == DitherPhase.LIVE:
            # Capture camera
            self._capture_camera()

            # Process with dithering
            if self._camera_frame is not None:
                self._process_dither()

        elif self._sub_phase == DitherPhase.CAPTURE:
            if self._time_in_phase > 3000:
                self._sub_phase = DitherPhase.LIVE
                self._time_in_phase = 0.0

    def _update_ticker_pattern(self):
        """Update ticker display pattern based on current algorithm."""
        # Create visual pattern representing the algorithm
        self._ticker_pattern = [False] * 48

        if self._algorithm == DitherAlgorithm.FLOYD_STEINBERG:
            # Error diffusion pattern
            for i in range(48):
                self._ticker_pattern[i] = (i % 3) == 0

        elif self._algorithm == DitherAlgorithm.ATKINSON:
            # Sparser pattern
            for i in range(48):
                self._ticker_pattern[i] = (i % 4) == 0

        elif self._algorithm == DitherAlgorithm.BAYER_4X4:
            # 4-pixel pattern
            pattern = [True, False, True, False]
            for i in range(48):
                self._ticker_pattern[i] = pattern[i % 4]

        elif self._algorithm == DitherAlgorithm.BAYER_8X8:
            # 8-pixel pattern
            pattern = [True, False, False, True, False, True, True, False]
            for i in range(48):
                self._ticker_pattern[i] = pattern[i % 8]

        elif self._algorithm == DitherAlgorithm.HALFTONE:
            # Dot pattern
            for i in range(48):
                self._ticker_pattern[i] = (i % 6) < 3

        else:  # THRESHOLD
            # Solid half
            for i in range(48):
                self._ticker_pattern[i] = i < 24

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

        # Create a face-like pattern
        cx, cy = 64, 64

        for y in range(128):
            for x in range(128):
                dx = x - cx
                dy = y - cy
                dist = math.sqrt(dx * dx + dy * dy)

                # Face oval
                if dist < 50:
                    brightness = 200 - dist * 2
                    # Add some noise for texture
                    noise = random.randint(-20, 20)
                    v = max(0, min(255, int(brightness + noise)))
                    frame[y, x] = (v, v, v)

                # Eyes
                eye_l_dist = math.sqrt((x - 45) ** 2 + (y - 50) ** 2)
                eye_r_dist = math.sqrt((x - 83) ** 2 + (y - 50) ** 2)
                if eye_l_dist < 10 or eye_r_dist < 10:
                    frame[y, x] = (30, 30, 30)
                if eye_l_dist < 5 or eye_r_dist < 5:
                    frame[y, x] = (0, 0, 0)

                # Mouth
                if 70 < y < 85 and 50 < x < 78:
                    mouth_curve = abs(y - 77 - (x - 64) * 0.1)
                    if mouth_curve < 3:
                        frame[y, x] = (50, 50, 50)

        self._camera_frame = frame

    def _process_dither(self):
        """Apply current dithering algorithm."""
        if self._camera_frame is None:
            return

        # Apply contrast enhancement
        frame = self._camera_frame.astype(np.float32)
        frame = (frame - 128) * self._contrast + 128
        frame = np.clip(frame, 0, 255).astype(np.uint8)

        # Apply dithering based on algorithm
        if self._algorithm == DitherAlgorithm.FLOYD_STEINBERG:
            dithered = Dithering.floyd_steinberg(frame, levels=2)
        elif self._algorithm == DitherAlgorithm.ATKINSON:
            dithered = Dithering.atkinson(frame, levels=2)
        elif self._algorithm == DitherAlgorithm.BAYER_4X4:
            dithered = Dithering.ordered_bayer(frame, matrix_size=4, levels=2)
        elif self._algorithm == DitherAlgorithm.BAYER_8X8:
            dithered = Dithering.ordered_bayer(frame, matrix_size=8, levels=2)
        elif self._algorithm == DitherAlgorithm.HALFTONE:
            dithered = Dithering.halftone(frame, dot_size=self._halftone_size)
        else:  # THRESHOLD
            gray = np.mean(frame, axis=2) if len(frame.shape) == 3 else frame
            binary = np.where(gray > self._threshold, 255, 0).astype(np.uint8)
            dithered = np.stack([binary, binary, binary], axis=2)

        # Apply color mode
        self._processed_frame = self._apply_color_mode(dithered)

    def _apply_color_mode(self, image: NDArray) -> NDArray:
        """Apply color palette to dithered image."""
        if self._color_mode == ColorMode.MONO:
            return image

        elif self._color_mode == ColorMode.GAMEBOY:
            return color_quantize(image, PALETTE_GAMEBOY)

        elif self._color_mode == ColorMode.CGA:
            return color_quantize(image, PALETTE_CGA)

        elif self._color_mode == ColorMode.PICO8:
            return color_quantize(image, PALETTE_PICO8)

        elif self._color_mode == ColorMode.THERMAL:
            # Black on yellowish paper
            result = image.copy()
            mask = np.mean(image, axis=2) > 128
            result[mask] = (240, 220, 180)  # Paper
            result[~mask] = (30, 20, 10)    # Ink
            return result

        elif self._color_mode == ColorMode.NEON:
            # Neon glow effect
            result = image.copy()
            brightness = np.mean(image, axis=2)
            hue = (self._total_time / 20) % 360

            for y in range(128):
                for x in range(128):
                    if brightness[y, x] > 128:
                        # Bright pixels - neon color
                        result[y, x] = hsv_to_rgb(hue + x, 1.0, 1.0)
                    else:
                        # Dark pixels - deep black with hint of color
                        result[y, x] = hsv_to_rgb(hue + x, 0.5, 0.1)
            return result

        elif self._color_mode == ColorMode.AMBER:
            # Amber phosphor monitor
            result = image.copy()
            brightness = np.mean(image, axis=2)
            for y in range(128):
                for x in range(128):
                    v = brightness[y, x] / 255
                    result[y, x] = (
                        int(255 * v),
                        int(180 * v),
                        int(50 * v)
                    )
            return result

        return image

    def _capture_image(self):
        """Capture current dithered image."""
        self._captured_image = self._processed_frame.copy() if self._processed_frame is not None else None
        self._sub_phase = DitherPhase.CAPTURE
        self._time_in_phase = 0.0

    # =========================================================================
    # RENDERING
    # =========================================================================

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        t = self._time_in_phase

        if self._sub_phase == DitherPhase.INTRO:
            self._render_intro(buffer, t)
        elif self._sub_phase == DitherPhase.LIVE:
            self._render_live(buffer, t)
        elif self._sub_phase == DitherPhase.CAPTURE:
            self._render_capture(buffer, t)

    def _render_intro(self, buffer: NDArray[np.uint8], t: float):
        """Render intro screen."""
        fill(buffer, (20, 30, 20))

        # Animated dither pattern demo
        for y in range(128):
            for x in range(128):
                # Gradient
                gradient = x / 128

                # Apply bayer dithering to gradient
                bayer = Dithering.BAYER_8X8[y % 8, x % 8]
                threshold = gradient + (bayer - 0.5) * 0.5 + math.sin(t / 200 + x * 0.1) * 0.1

                if threshold > 0.5:
                    buffer[y, x] = (180, 220, 180)
                else:
                    buffer[y, x] = (20, 40, 20)

        # Title
        draw_rect(buffer, 20, 25, 88, 30, (0, 0, 0))
        draw_centered_text(buffer, "ДИЗЕР", 30, (100, 255, 100), scale=2)
        draw_centered_text(buffer, "АРТ", 48, (180, 255, 180), scale=1)

        # Algorithm showcase
        algo_names = ["F-S", "ATK", "B4", "B8", "HT", "TH"]
        y_pos = 75
        for i, name in enumerate(algo_names):
            x_pos = 10 + i * 20
            draw_rect(buffer, x_pos, y_pos, 18, 12, (0, 0, 0))
            color = (100, 200, 100) if i == int(t / 400) % 6 else (60, 100, 60)
            draw_text_bitmap(buffer, name, x_pos + 2, y_pos + 2, color, load_font("cyrillic"), scale=1)

        draw_animated_text(buffer, "НАЖМИ СТАРТ", 115, (80, 150, 80), t, TextEffect.PULSE, scale=1)

    def _render_live(self, buffer: NDArray[np.uint8], t: float):
        """Render live dithered view."""
        if self._processed_frame is not None:
            # Apply transition effect
            if self._transition_progress < 1.0 and self._prev_frame is not None:
                # Wipe transition
                wipe_x = int(128 * self._transition_progress)
                np.copyto(buffer[:, :wipe_x], self._processed_frame[:, :wipe_x])
                np.copyto(buffer[:, wipe_x:], self._prev_frame[:, wipe_x:])
            else:
                np.copyto(buffer, self._processed_frame)
        else:
            fill(buffer, (30, 30, 30))

        # UI overlay
        algo_names = {
            DitherAlgorithm.FLOYD_STEINBERG: "F-S",
            DitherAlgorithm.ATKINSON: "ATK",
            DitherAlgorithm.BAYER_4X4: "B4X4",
            DitherAlgorithm.BAYER_8X8: "B8X8",
            DitherAlgorithm.HALFTONE: "DOTS",
            DitherAlgorithm.THRESHOLD: "TRSH",
        }

        color_names = {
            ColorMode.MONO: "Ч/Б",
            ColorMode.GAMEBOY: "GB",
            ColorMode.CGA: "CGA",
            ColorMode.PICO8: "P8",
            ColorMode.THERMAL: "ТЕР",
            ColorMode.NEON: "НЕО",
            ColorMode.AMBER: "АМБ",
        }

        font = load_font("cyrillic")

        # Algorithm indicator
        draw_rect(buffer, 0, 0, 35, 12, (0, 0, 0))
        algo_text = algo_names.get(self._algorithm, "?")
        algo_w, _ = font.measure_text(algo_text)
        algo_scale = max(1, min(2, 30 // max(1, algo_w)))
        draw_text_bitmap(buffer, algo_text, 2, 2, (100, 255, 100), font, scale=algo_scale)

        # Color mode indicator
        draw_rect(buffer, 93, 0, 35, 12, (0, 0, 0))
        color_text = color_names.get(self._color_mode, "?")
        color_w, _ = font.measure_text(color_text)
        color_scale = max(1, min(2, 30 // max(1, color_w)))
        draw_text_bitmap(buffer, color_text, 95, 2, (255, 200, 100), font, scale=color_scale)

        # Hint
        hint_alpha = 0.4 + 0.2 * math.sin(t / 400)
        hint_color = tuple(int(c * hint_alpha) for c in (100, 150, 100))
        draw_centered_text(buffer, "<АЛГО  ЦВЕТ>", 118, hint_color, scale=1)

    def _render_capture(self, buffer: NDArray[np.uint8], t: float):
        """Render capture confirmation."""
        if self._captured_image is not None:
            np.copyto(buffer, self._captured_image)

        # Flash effect
        flash = max(0, 1 - t / 300)
        if flash > 0:
            buffer[:] = np.clip(buffer.astype(np.int16) + int(150 * flash), 0, 255).astype(np.uint8)

        # Confirmation
        draw_rect(buffer, 15, 48, 98, 32, (0, 0, 0))
        draw_centered_text(buffer, "СОХРАНЕНО!", 55, (100, 255, 100), scale=2)

        # Pixelated border animation
        phase = int(t / 100) % 8
        for i in range(0, 128, 8):
            if (i // 8 + phase) % 2 == 0:
                draw_rect(buffer, i, 0, 8, 4, (100, 255, 100))
                draw_rect(buffer, i, 124, 8, 4, (100, 255, 100))

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display as camera continuation with dither effect."""
        from artifact.graphics.primitives import clear

        clear(buffer)

        if self._sub_phase == DitherPhase.LIVE and self._camera_frame is not None:
            # Show camera-based dithered ticker (continuation of main display)
            color = self._get_mode_color()

            for ty in range(8):
                for tx in range(48):
                    # Map to camera coordinates (top band)
                    cam_y = (ty * 128) // 8
                    cam_x = (tx * 128) // 48

                    if cam_y < 128 and cam_x < 128:
                        # Get brightness from camera
                        pixel = self._camera_frame[cam_y, cam_x]
                        brightness = (int(pixel[0]) + int(pixel[1]) + int(pixel[2])) // 3 / 255

                        # Apply dithering
                        bayer = Dithering.BAYER_4X4[ty % 4, tx % 4]
                        threshold = brightness + (bayer - 0.5) * 0.4

                        if threshold > 0.5:
                            buffer[ty, tx] = color
                        else:
                            buffer[ty, tx] = (10, 15, 10)

        elif self._sub_phase == DitherPhase.INTRO:
            # Animated gradient dither
            for x in range(48):
                gradient = x / 48
                bayer_col = x % 4
                for y in range(8):
                    bayer = Dithering.BAYER_4X4[y % 4, bayer_col]
                    if gradient + bayer * 0.5 > 0.5:
                        buffer[y, x] = (100, 200, 100)
                    else:
                        buffer[y, x] = (20, 40, 20)

        else:  # CAPTURE
            # Flash
            intensity = max(0, 1 - self._time_in_phase / 500)
            v = int(200 * intensity)
            buffer[:] = (v, v, v)

    def _get_mode_color(self) -> Tuple[int, int, int]:
        """Get color based on current color mode."""
        if self._color_mode == ColorMode.GAMEBOY:
            return (139, 172, 15)
        elif self._color_mode == ColorMode.CGA:
            return (85, 255, 255)
        elif self._color_mode == ColorMode.NEON:
            hue = (self._total_time / 20) % 360
            return hsv_to_rgb(hue, 1.0, 1.0)
        elif self._color_mode == ColorMode.AMBER:
            return (255, 180, 50)
        elif self._color_mode == ColorMode.THERMAL:
            return (30, 20, 10)
        else:
            return (200, 200, 200)

    def get_lcd_text(self) -> str:
        """Get LCD text - shows current algorithm."""
        if self._sub_phase == DitherPhase.INTRO:
            return "  ДИЗЕР-АРТ    "

        elif self._sub_phase == DitherPhase.LIVE:
            algo_names = {
                DitherAlgorithm.FLOYD_STEINBERG: "ФЛОЙД-СТЕЙНБ",
                DitherAlgorithm.ATKINSON: "АТКИНСОН",
                DitherAlgorithm.BAYER_4X4: "БЕЙЕР 4x4",
                DitherAlgorithm.BAYER_8X8: "БЕЙЕР 8x8",
                DitherAlgorithm.HALFTONE: "ПОЛУТОН",
                DitherAlgorithm.THRESHOLD: "ПОРОГ",
            }
            name = algo_names.get(self._algorithm, "ДИЗЕР")
            return f" {name:^14} "

        elif self._sub_phase == DitherPhase.CAPTURE:
            return "  СОХРАНЕНО!   "

        return "   ДИЗЕР-АРТ   "

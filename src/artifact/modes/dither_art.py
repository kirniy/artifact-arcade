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
        """Create demo pattern if no camera - VECTORIZED."""
        frame = np.zeros((128, 128, 3), dtype=np.uint8)

        # Create coordinate grids
        y_coords = np.arange(128)[:, np.newaxis]
        x_coords = np.arange(128)[np.newaxis, :]
        cx, cy = 64, 64

        # Distance from center
        dx = x_coords - cx
        dy = y_coords - cy
        dist = np.sqrt(dx * dx + dy * dy)

        # Face oval
        face_mask = dist < 50
        brightness = 200 - dist * 2
        noise = np.random.randint(-20, 21, (128, 128))
        face_v = np.clip(brightness + noise, 0, 255).astype(np.uint8)
        frame[face_mask, 0] = face_v[face_mask]
        frame[face_mask, 1] = face_v[face_mask]
        frame[face_mask, 2] = face_v[face_mask]

        # Eyes
        eye_l_dist = np.sqrt((x_coords - 45) ** 2 + (y_coords - 50) ** 2)
        eye_r_dist = np.sqrt((x_coords - 83) ** 2 + (y_coords - 50) ** 2)
        eye_outer = (eye_l_dist < 10) | (eye_r_dist < 10)
        eye_inner = (eye_l_dist < 5) | (eye_r_dist < 5)
        frame[eye_outer] = (30, 30, 30)
        frame[eye_inner] = (0, 0, 0)

        # Mouth
        mouth_mask = (y_coords > 70) & (y_coords < 85) & (x_coords > 50) & (x_coords < 78)
        mouth_curve = np.abs(y_coords - 77 - (x_coords - 64) * 0.1)
        mouth_visible = mouth_mask & (mouth_curve < 3)
        frame[mouth_visible] = (50, 50, 50)

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
            # Neon glow effect - VECTORIZED
            result = np.zeros_like(image)
            brightness = np.mean(image, axis=2)
            base_hue = (self._total_time / 20) % 360

            x_coords = np.arange(128)[np.newaxis, :]
            hue = (base_hue + x_coords) % 360
            h60 = hue / 60.0
            h_i = (h60.astype(int) % 6)
            f = h60 - h60.astype(int)

            bright_mask = brightness > 128
            # Bright: full saturation, full value
            # Dark: half saturation, 0.1 value

            # For bright pixels (s=1.0, v=1.0)
            p_b, q_b, t_b = 0, 1 - f, f
            r_b = np.where(h_i == 0, 1.0, np.where(h_i == 1, q_b, np.where(h_i == 2, 0, np.where(h_i == 3, 0, np.where(h_i == 4, t_b, 1.0)))))
            g_b = np.where(h_i == 0, t_b, np.where(h_i == 1, 1.0, np.where(h_i == 2, 1.0, np.where(h_i == 3, q_b, np.where(h_i == 4, 0, 0)))))
            b_b = np.where(h_i == 0, 0, np.where(h_i == 1, 0, np.where(h_i == 2, t_b, np.where(h_i == 3, 1.0, np.where(h_i == 4, 1.0, q_b)))))

            # For dark pixels (s=0.5, v=0.1)
            p_d, q_d, t_d = 0.05, 0.1 * (1 - 0.5 * f), 0.1 * (1 - 0.5 * (1 - f))
            r_d = np.where(h_i == 0, 0.1, np.where(h_i == 1, q_d, np.where(h_i == 2, p_d, np.where(h_i == 3, p_d, np.where(h_i == 4, t_d, 0.1)))))
            g_d = np.where(h_i == 0, t_d, np.where(h_i == 1, 0.1, np.where(h_i == 2, 0.1, np.where(h_i == 3, q_d, np.where(h_i == 4, p_d, p_d)))))
            b_d = np.where(h_i == 0, p_d, np.where(h_i == 1, p_d, np.where(h_i == 2, t_d, np.where(h_i == 3, 0.1, np.where(h_i == 4, 0.1, q_d)))))

            result[:, :, 0] = np.where(bright_mask, r_b * 255, r_d * 255).astype(np.uint8)
            result[:, :, 1] = np.where(bright_mask, g_b * 255, g_d * 255).astype(np.uint8)
            result[:, :, 2] = np.where(bright_mask, b_b * 255, b_d * 255).astype(np.uint8)
            return result

        elif self._color_mode == ColorMode.AMBER:
            # Amber phosphor monitor - VECTORIZED
            brightness = np.mean(image, axis=2) / 255.0
            result = np.zeros_like(image)
            result[:, :, 0] = (255 * brightness).astype(np.uint8)
            result[:, :, 1] = (180 * brightness).astype(np.uint8)
            result[:, :, 2] = (50 * brightness).astype(np.uint8)
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
        """Render intro screen - VECTORIZED."""
        # Animated dither pattern demo
        y_coords = np.arange(128)[:, np.newaxis]
        x_coords = np.arange(128)[np.newaxis, :]

        # Gradient
        gradient = x_coords / 128.0

        # Apply bayer dithering to gradient
        bayer = Dithering.BAYER_8X8[y_coords % 8, x_coords % 8]
        threshold = gradient + (bayer - 0.5) * 0.5 + np.sin(t / 200 + x_coords * 0.1) * 0.1

        bright = threshold > 0.5
        buffer[:, :, 0] = np.where(bright, 180, 20)
        buffer[:, :, 1] = np.where(bright, 220, 40)
        buffer[:, :, 2] = np.where(bright, 180, 20)

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
        """Render ticker display as camera continuation with dither effect - VECTORIZED."""
        buffer[:] = 0

        if self._sub_phase == DitherPhase.LIVE and self._camera_frame is not None:
            # Map camera to ticker coordinates - VECTORIZED
            color = self._get_mode_color()
            ty_coords = np.arange(8)[:, np.newaxis]
            tx_coords = np.arange(48)[np.newaxis, :]
            cam_y = np.clip((ty_coords * 128) // 8, 0, 127)
            cam_x = np.clip((tx_coords * 128) // 48, 0, 127)

            sampled = self._camera_frame[cam_y, cam_x]
            brightness = sampled.astype(np.float32).mean(axis=-1) / 255.0

            # Apply bayer dithering
            bayer = Dithering.BAYER_4X4[ty_coords % 4, tx_coords % 4]
            threshold = brightness + (bayer - 0.5) * 0.4
            bright = threshold > 0.5

            buffer[:, :, 0] = np.where(bright, color[0], 10)
            buffer[:, :, 1] = np.where(bright, color[1], 15)
            buffer[:, :, 2] = np.where(bright, color[2], 10)

        elif self._sub_phase == DitherPhase.INTRO:
            # Animated gradient dither - VECTORIZED
            y_coords = np.arange(8)[:, np.newaxis]
            x_coords = np.arange(48)[np.newaxis, :]
            gradient = x_coords / 48.0
            bayer = Dithering.BAYER_4X4[y_coords % 4, x_coords % 4]
            bright = (gradient + bayer * 0.5) > 0.5

            buffer[:, :, 0] = np.where(bright, 100, 20)
            buffer[:, :, 1] = np.where(bright, 200, 40)
            buffer[:, :, 2] = np.where(bright, 100, 20)

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

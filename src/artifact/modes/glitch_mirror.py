"""Glitch Mirror Mode - Real-time glitch art effects on your face.

Your reflection becomes a canvas for digital chaos. Watch as your face
gets pixel-sorted, channel-shifted, data-moshed in real time!

Controls:
- LEFT: Cycle through glitch effects
- RIGHT: Trigger intense glitch burst
- START: Capture glitched masterpiece
"""

from typing import Optional, List, Tuple
from enum import Enum, auto
import math
import random
import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.fonts import load_font, draw_text_bitmap
from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect
from artifact.graphics.algorithmic_art import (
    GlitchEffects, Dithering, hsv_to_rgb, pixelate, posterize
)


class GlitchStyle(Enum):
    """Available glitch effect styles."""
    CHANNEL_SHIFT = auto()    # RGB channel separation
    PIXEL_SORT = auto()       # Pixel sorting madness
    SCANLINE = auto()         # Scanline displacement
    BLOCK_GLITCH = auto()     # Random block displacement
    DATA_MOSH = auto()        # Corrupt the data
    VHS_NOISE = auto()        # VHS tape aesthetic
    CHROMATIC = auto()        # Chromatic aberration
    WAVE_DISTORT = auto()     # Wave distortion


class GlitchPhase(Enum):
    """Glitch mirror mode phases."""
    INTRO = "intro"
    MIRROR = "mirror"
    BURST = "burst"
    CAPTURE = "capture"


class GlitchMirrorMode(BaseMode):
    """Interactive glitch art mirror mode.

    Real-time glitch effects applied to camera feed,
    creating unique digital art from your face.
    """

    name = "glitch_mirror"
    display_name = "GLITCH"
    icon = "glitch"
    style = "cyber"

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._sub_phase = GlitchPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0

        # Camera
        self._camera = None
        self._camera_frame: Optional[NDArray] = None
        self._processed_frame: Optional[NDArray] = None

        # Glitch settings
        self._style = GlitchStyle.CHANNEL_SHIFT
        self._style_index = 0
        self._styles = list(GlitchStyle)
        self._intensity = 0.5
        self._auto_intensity = 0.0  # Animated intensity

        # Effect parameters
        self._channel_offset = 5
        self._pixel_sort_threshold = 100
        self._block_count = 5
        self._corruption_level = 0.05
        self._wave_phase = 0.0

        # Burst state
        self._burst_active = False
        self._burst_timer = 0.0
        self._burst_intensity = 0.0

        # Captured image
        self._captured_image: Optional[NDArray] = None

        # Scanline effect (for ticker sync)
        self._scanline_y = 0

        # Ticker glitch state
        self._ticker_glitch_chars = []
        self._ticker_target_text = ""
        self._ticker_reveal_pos = 0

    def on_enter(self) -> None:
        """Initialize mode."""
        self._sub_phase = GlitchPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0
        self._style_index = 0
        self._style = self._styles[0]
        self._intensity = 0.5
        self._burst_active = False

        # Try to open camera
        try:
            from artifact.utils.camera import create_camera
            self._camera = create_camera(resolution=(128, 128))
            self._camera.open()
        except Exception:
            self._camera = None

        # Initialize ticker glitch
        self._ticker_glitch_chars = [chr(random.randint(33, 126)) for _ in range(48)]
        self._ticker_target_text = "ГЛИТЧ-ЗЕРКАЛО"

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
        if self._sub_phase == GlitchPhase.INTRO:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = GlitchPhase.MIRROR
                self._time_in_phase = 0.0
                return True
            return False

        if self._sub_phase == GlitchPhase.MIRROR:
            if event.type == EventType.ARCADE_LEFT:
                # Cycle glitch style
                self._style_index = (self._style_index + 1) % len(self._styles)
                self._style = self._styles[self._style_index]
                hasattr(self.context, "audio") and self.context.audio and self.context.audio.play_ui_click()
                return True

            elif event.type == EventType.ARCADE_RIGHT:
                # Trigger burst
                if not self._burst_active:
                    self._trigger_burst()
                    hasattr(self.context, "audio") and self.context.audio and self.context.audio.play_ui_confirm()
                return True

            elif event.type == EventType.BUTTON_PRESS:
                # Capture
                self._capture_image()
                hasattr(self.context, "audio") and self.context.audio and self.context.audio.play_success()
                return True

        elif self._sub_phase == GlitchPhase.CAPTURE:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = GlitchPhase.MIRROR
                self._time_in_phase = 0.0
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        """Update mode state."""
        self._time_in_phase += delta_ms
        self._total_time += delta_ms
        self._wave_phase += delta_ms / 200

        # Auto-animate intensity
        self._auto_intensity = 0.3 + 0.2 * math.sin(self._total_time / 500)

        # Update scanline
        self._scanline_y = int((self._total_time / 50) % 128)

        # Update ticker reveal
        if self._sub_phase == GlitchPhase.MIRROR:
            reveal_speed = 0.01
            self._ticker_reveal_pos = min(
                len(self._ticker_target_text),
                int(self._time_in_phase * reveal_speed)
            )

            # Randomize unrevealed chars
            for i in range(self._ticker_reveal_pos, len(self._ticker_glitch_chars)):
                if random.random() < 0.1:
                    self._ticker_glitch_chars[i] = chr(random.randint(33, 126))

        if self._sub_phase == GlitchPhase.INTRO:
            if self._time_in_phase > 2500:
                self._sub_phase = GlitchPhase.MIRROR
                self._time_in_phase = 0.0

        elif self._sub_phase == GlitchPhase.MIRROR:
            # Capture camera frame
            self._capture_camera()

            # Process with glitch effects
            if self._camera_frame is not None:
                self._process_glitch()

            # Update burst
            if self._burst_active:
                self._burst_timer -= delta_ms
                self._burst_intensity = max(0, self._burst_timer / 1000)
                if self._burst_timer <= 0:
                    self._burst_active = False

        elif self._sub_phase == GlitchPhase.CAPTURE:
            if self._time_in_phase > 3000:
                self._sub_phase = GlitchPhase.MIRROR
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
            # Demo pattern
            self._create_demo_frame()

    def _create_demo_frame(self):
        """Create demo pattern if no camera - VECTORIZED."""
        t = self._total_time / 1000

        # Create coordinate grids
        y_coords = np.arange(128)[:, np.newaxis]
        x_coords = np.arange(128)[np.newaxis, :]

        # Animated gradient (vectorized)
        r = (127 + 127 * np.sin(x_coords * 0.1 + t)).astype(np.uint8)
        g = (127 + 127 * np.sin(y_coords * 0.1 + t * 1.3)).astype(np.uint8)
        b = (127 + 127 * np.sin((x_coords + y_coords) * 0.05 + t * 0.7)).astype(np.uint8)

        frame = np.stack([r, g, b], axis=-1).reshape(128, 128, 3).astype(np.uint8)

        # Add some shapes using pygame-style rectangle draws
        cx, cy = 64, 64
        for angle in range(0, 360, 45):
            rad = math.radians(angle + t * 50)
            px = int(cx + 30 * math.cos(rad))
            py = int(cy + 30 * math.sin(rad))
            # Draw 11x11 white square centered at (px, py)
            y1, y2 = max(0, py - 5), min(128, py + 6)
            x1, x2 = max(0, px - 5), min(128, px + 6)
            frame[y1:y2, x1:x2] = (255, 255, 255)

        self._camera_frame = frame

    def _process_glitch(self):
        """Apply current glitch effect."""
        if self._camera_frame is None:
            return

        frame = self._camera_frame.copy()
        intensity = self._intensity + self._auto_intensity

        # Apply burst intensity
        if self._burst_active:
            intensity += self._burst_intensity * 0.5

        if self._style == GlitchStyle.CHANNEL_SHIFT:
            offset = int(self._channel_offset * intensity)
            # Animate offset
            offset_x = int(offset * math.sin(self._wave_phase))
            offset_y = int(offset * 0.5 * math.cos(self._wave_phase * 0.7))
            frame = GlitchEffects.channel_shift(
                frame,
                r_offset=(offset_x, offset_y),
                g_offset=(0, 0),
                b_offset=(-offset_x, -offset_y)
            )

        elif self._style == GlitchStyle.PIXEL_SORT:
            threshold = int(self._pixel_sort_threshold * (1.5 - intensity))
            frame = GlitchEffects.pixel_sort(frame, threshold=threshold)

        elif self._style == GlitchStyle.SCANLINE:
            frame = GlitchEffects.scanline_glitch(frame, intensity=intensity * 0.5)

        elif self._style == GlitchStyle.BLOCK_GLITCH:
            num_blocks = int(self._block_count * intensity * 2)
            frame = GlitchEffects.block_glitch(frame, num_blocks=num_blocks)

        elif self._style == GlitchStyle.DATA_MOSH:
            corruption = self._corruption_level * intensity
            frame = GlitchEffects.data_mosh(frame, corruption=corruption)

        elif self._style == GlitchStyle.VHS_NOISE:
            frame = self._apply_vhs_effect(frame, intensity)

        elif self._style == GlitchStyle.CHROMATIC:
            frame = self._apply_chromatic_aberration(frame, intensity)

        elif self._style == GlitchStyle.WAVE_DISTORT:
            frame = self._apply_wave_distortion(frame, intensity)

        # Apply burst effects
        if self._burst_active:
            frame = self._apply_burst_effects(frame)

        self._processed_frame = frame

    def _apply_vhs_effect(self, frame: NDArray, intensity: float) -> NDArray:
        """Apply VHS tape aesthetic."""
        result = frame.copy()
        height = result.shape[0]

        # Horizontal tracking lines
        num_lines = int(3 + intensity * 5)
        for _ in range(num_lines):
            y = random.randint(0, height - 1)
            line_height = random.randint(1, 4)
            for dy in range(line_height):
                if 0 <= y + dy < height:
                    result[y + dy] = np.roll(result[y + dy], random.randint(-15, 15), axis=0)
                    result[y + dy] = (result[y + dy].astype(np.float32) * 0.7).astype(np.uint8)

        # Add noise
        noise = np.random.randint(-30, 30, frame.shape, dtype=np.int16)
        result = np.clip(result.astype(np.int16) + noise * intensity, 0, 255).astype(np.uint8)

        # Color bleeding
        result = GlitchEffects.channel_shift(
            result,
            r_offset=(2, 0),
            b_offset=(-2, 0)
        )

        return result

    def _apply_chromatic_aberration(self, frame: NDArray, intensity: float) -> NDArray:
        """Apply chromatic aberration effect - SIMPLIFIED for performance."""
        # Simple channel shift based on intensity (much faster than radial)
        offset = int(2 + intensity * 3)

        result = frame.copy()

        # Red channel - shift right/down
        result[:, :-offset, 0] = frame[:, offset:, 0]

        # Green channel - no shift
        # Already copied

        # Blue channel - shift left/up
        result[:, offset:, 2] = frame[:, :-offset, 2]

        return result

    def _apply_wave_distortion(self, frame: NDArray, intensity: float) -> NDArray:
        """Apply wave distortion effect - VECTORIZED."""
        height, width = frame.shape[:2]

        # Calculate wave offset per row (vectorized)
        y_coords = np.arange(height)
        wave = np.sin(y_coords * 0.1 + self._wave_phase) * intensity * 15
        wave += np.sin(y_coords * 0.05 + self._wave_phase * 0.7) * intensity * 10
        wave = wave.astype(np.int32)

        # Apply horizontal roll per row
        result = np.zeros_like(frame)
        for y in range(height):
            result[y] = np.roll(frame[y], wave[y], axis=0)

        return result

    def _trigger_burst(self):
        """Trigger intense glitch burst."""
        self._burst_active = True
        self._burst_timer = 1000  # 1 second burst
        self._burst_intensity = 1.0

    def _apply_burst_effects(self, frame: NDArray) -> NDArray:
        """Apply intense burst effects."""
        result = frame.copy()

        # Heavy scanline displacement
        result = GlitchEffects.scanline_glitch(result, intensity=0.5)

        # Block glitch
        result = GlitchEffects.block_glitch(result, num_blocks=10)

        # Flash
        flash = int(200 * self._burst_intensity)
        if random.random() < 0.3:
            result = np.clip(result.astype(np.int16) + flash, 0, 255).astype(np.uint8)

        return result

    def _capture_image(self):
        """Capture current glitched image."""
        self._captured_image = self._processed_frame.copy() if self._processed_frame is not None else None
        self._sub_phase = GlitchPhase.CAPTURE
        self._time_in_phase = 0.0

    # =========================================================================
    # RENDERING
    # =========================================================================

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        t = self._time_in_phase

        if self._sub_phase == GlitchPhase.INTRO:
            self._render_intro(buffer, t)
        elif self._sub_phase == GlitchPhase.MIRROR:
            self._render_mirror(buffer, t)
        elif self._sub_phase == GlitchPhase.CAPTURE:
            self._render_capture(buffer, t)

    def _render_intro(self, buffer: NDArray[np.uint8], t: float):
        """Render intro screen."""
        fill(buffer, (5, 5, 15))

        # Glitchy animated background
        for _ in range(20):
            x = random.randint(0, 127)
            y = random.randint(0, 127)
            w = random.randint(5, 30)
            h = random.randint(2, 8)
            color = random.choice([
                (255, 0, 100),
                (0, 255, 200),
                (255, 200, 0),
            ])
            alpha = random.uniform(0.2, 0.5)
            color = tuple(int(c * alpha) for c in color)
            draw_rect(buffer, x, y, w, h, color)

        # Scanlines - VECTORIZED
        buffer[::3] = (buffer[::3].astype(np.float32) * 0.7).astype(np.uint8)

        # Title with glitch effect
        if random.random() < 0.1:
            offset = random.randint(-5, 5)
        else:
            offset = 0

        draw_centered_text(buffer, "ГЛИТЧ", 30 + offset, (255, 0, 100), scale=2)
        draw_centered_text(buffer, "ЗЕРКАЛО", 55, (0, 255, 200), scale=2)

        # Instructions
        draw_centered_text(buffer, "СТАНЬ ЦИФРОВЫМ", 85, (150, 150, 200), scale=1)
        draw_centered_text(buffer, "ИСКУССТВОМ", 100, (150, 150, 200), scale=1)

        draw_animated_text(buffer, "НАЖМИ СТАРТ", 115, (100, 100, 150), t, TextEffect.PULSE, scale=1)

    def _render_mirror(self, buffer: NDArray[np.uint8], t: float):
        """Render glitch mirror view."""
        if self._processed_frame is not None:
            np.copyto(buffer, self._processed_frame)
        else:
            fill(buffer, (20, 10, 30))

        # UI overlay
        style_names = {
            GlitchStyle.CHANNEL_SHIFT: "RGB",
            GlitchStyle.PIXEL_SORT: "СОРТ",
            GlitchStyle.SCANLINE: "СКАН",
            GlitchStyle.BLOCK_GLITCH: "БЛОК",
            GlitchStyle.DATA_MOSH: "МОЗГ",
            GlitchStyle.VHS_NOISE: "VHS",
            GlitchStyle.CHROMATIC: "ХРОМ",
            GlitchStyle.WAVE_DISTORT: "ВОЛНА",
        }

        style_text = style_names.get(self._style, "?")

        # Semi-transparent background
        draw_rect(buffer, 0, 0, 45, 12, (0, 0, 0))
        draw_text_bitmap(buffer, style_text, 2, 2, (255, 100, 150),
                        load_font("cyrillic"), scale=1)

        # Intensity bar
        bar_width = int(30 * (self._intensity + self._auto_intensity))
        draw_rect(buffer, 90, 2, 35, 8, (30, 30, 30))
        if bar_width > 0:
            draw_rect(buffer, 92, 4, min(bar_width, 31), 4, (255, 100, 150))

        # Hint at bottom
        if not self._burst_active:
            hint_alpha = 0.4 + 0.2 * math.sin(t / 400)
            hint_color = tuple(int(c * hint_alpha) for c in (100, 150, 100))
            draw_centered_text(buffer, "<ЭФФЕКТ  ВЗРЫВ>", 118, hint_color, scale=1)

        # Burst indicator - VECTORIZED
        if self._burst_active:
            flash = int(100 * self._burst_intensity)
            # Add chromatic border (top = red boost, bottom = blue boost)
            buffer[:3, :, 0] = np.clip(buffer[:3, :, 0].astype(np.int16) + flash, 0, 255).astype(np.uint8)
            buffer[-3:, :, 2] = np.clip(buffer[-3:, :, 2].astype(np.int16) + flash, 0, 255).astype(np.uint8)

    def _render_capture(self, buffer: NDArray[np.uint8], t: float):
        """Render capture confirmation."""
        if self._captured_image is not None:
            np.copyto(buffer, self._captured_image)

        # Flash effect
        flash = max(0, 1 - t / 300)
        if flash > 0:
            buffer[:] = np.clip(buffer.astype(np.int16) + int(200 * flash), 0, 255).astype(np.uint8)

        # Confirmation overlay
        draw_rect(buffer, 10, 45, 108, 38, (0, 0, 0))
        draw_rect(buffer, 12, 47, 104, 34, (50, 20, 60))

        draw_centered_text(buffer, "ЗАХВАЧЕНО!", 55, (255, 100, 200), scale=2)

        # Animated border - VECTORIZED
        phase = int(t / 100) % 4
        colors = [(255, 0, 100), (0, 255, 200), (255, 200, 0), (200, 100, 255)]
        border_color = colors[phase]
        offset = int(t / 50)
        # Create mask for dashed pattern
        indices = np.arange(128)
        mask = ((indices + offset) % 8) < 4
        # Apply to borders
        buffer[0, mask] = border_color
        buffer[127, mask] = border_color
        buffer[mask, 0] = border_color
        buffer[mask, 127] = border_color

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display as camera continuation with glitch effect - VECTORIZED."""
        buffer[:] = 0
        t = self._total_time

        if self._sub_phase == GlitchPhase.MIRROR and self._camera_frame is not None:
            # Map camera to ticker coordinates - VECTORIZED
            ty_coords = np.arange(8)[:, np.newaxis]
            tx_coords = np.arange(48)[np.newaxis, :]
            cam_y = (ty_coords * 128) // 8
            cam_x = (tx_coords * 128) // 48

            # Sample camera (clipped to bounds)
            cam_y = np.clip(cam_y, 0, 127)
            cam_x = np.clip(cam_x, 0, 127)
            sampled = self._camera_frame[cam_y, cam_x]

            # Calculate brightness from RGB average
            brightness = sampled.astype(np.float32).mean(axis=-1) / 255.0

            # Calculate hue gradient across ticker
            hue = (self._style_index * 45 + tx_coords * 2 + t / 20) % 360

            # HSV to RGB for tinted pixels (vectorized approximation)
            h60 = hue / 60.0
            h_i = (h60.astype(int) % 6)
            f = h60 - h60.astype(int)
            s = 0.8
            p = brightness * (1 - s)
            q = brightness * (1 - s * f)
            t_val = brightness * (1 - s * (1 - f))

            r = np.zeros((8, 48), dtype=np.float32)
            g = np.zeros((8, 48), dtype=np.float32)
            b = np.zeros((8, 48), dtype=np.float32)

            # Sector 0: r=v, g=t, b=p
            m0 = h_i == 0
            r[m0] = brightness[m0]; g[m0] = t_val[m0]; b[m0] = p[m0]
            # Sector 1: r=q, g=v, b=p
            m1 = h_i == 1
            r[m1] = q[m1]; g[m1] = brightness[m1]; b[m1] = p[m1]
            # Sector 2: r=p, g=v, b=t
            m2 = h_i == 2
            r[m2] = p[m2]; g[m2] = brightness[m2]; b[m2] = t_val[m2]
            # Sector 3: r=p, g=q, b=v
            m3 = h_i == 3
            r[m3] = p[m3]; g[m3] = q[m3]; b[m3] = brightness[m3]
            # Sector 4: r=t, g=p, b=v
            m4 = h_i == 4
            r[m4] = t_val[m4]; g[m4] = p[m4]; b[m4] = brightness[m4]
            # Sector 5: r=v, g=p, b=q
            m5 = h_i == 5
            r[m5] = brightness[m5]; g[m5] = p[m5]; b[m5] = q[m5]

            buffer[:, :, 0] = (r * 255).astype(np.uint8)
            buffer[:, :, 1] = (g * 255).astype(np.uint8)
            buffer[:, :, 2] = (b * 255).astype(np.uint8)

            # Apply random glitch to ~10% of pixels
            glitch_mask = np.random.random((8, 48)) < 0.1
            glitch_colors = np.random.randint(50, 256, (8, 48, 3), dtype=np.uint8)
            buffer[glitch_mask] = glitch_colors[glitch_mask]

            # Scanline sync - vertical white line
            scan_x = int((self._scanline_y / 128) * 48)
            if 0 <= scan_x < 48:
                buffer[:, scan_x] = (255, 255, 255)

        elif self._sub_phase == GlitchPhase.INTRO:
            # Static glitch noise - VECTORIZED
            noise_mask = np.random.random((8, 48)) < 0.3
            noise_vals = np.random.randint(0, 256, (8, 48), dtype=np.uint8)
            buffer[noise_mask, 0] = noise_vals[noise_mask]
            buffer[noise_mask, 1] = noise_vals[noise_mask]
            buffer[noise_mask, 2] = noise_vals[noise_mask]

        else:
            # Capture - flash
            intensity = max(0, 1 - self._time_in_phase / 500)
            v = int(255 * intensity)
            buffer[:] = (v, v, v)

    def get_lcd_text(self) -> str:
        """Get LCD text - synced with current state."""
        if self._sub_phase == GlitchPhase.INTRO:
            # Glitchy intro text
            text = "ГЛИТЧ-ЗЕРКАЛО"
            if random.random() < 0.2:
                # Random corruption
                chars = list(text)
                idx = random.randint(0, len(chars) - 1)
                chars[idx] = chr(random.randint(33, 126))
                text = ''.join(chars)
            return f" {text:^14} "

        elif self._sub_phase == GlitchPhase.MIRROR:
            style_names = {
                GlitchStyle.CHANNEL_SHIFT: "RGB-СДВИГ",
                GlitchStyle.PIXEL_SORT: "ПИКС-СОРТ",
                GlitchStyle.SCANLINE: "СКАНЛАЙН",
                GlitchStyle.BLOCK_GLITCH: "БЛОК-ГЛИТЧ",
                GlitchStyle.DATA_MOSH: "ДАТАМОШ",
                GlitchStyle.VHS_NOISE: "VHS-ШУМ",
                GlitchStyle.CHROMATIC: "ХРОМАТИКА",
                GlitchStyle.WAVE_DISTORT: "ВОЛНА",
            }
            name = style_names.get(self._style, "ГЛИТЧ")
            return f" {name:^14} "

        elif self._sub_phase == GlitchPhase.CAPTURE:
            return "  ЗАХВАЧЕНО!   "

        return "  ГЛИТЧ-МОДА   "

"""Enhanced idle animation scenes with dramatic effects.

This module provides 4 stunning idle animation scenes that cycle automatically:
1. MYSTICAL EYE - A living, breathing eye that tracks and looks around
2. COSMIC PORTAL - Swirling galaxy/portal effect with stars
3. FORTUNE CARDS - Animated tarot cards shuffling and revealing
4. MATRIX RAIN - Cyberpunk matrix-style cascading characters

Each scene has coordinated animations for:
- Main display (128x128)
- Ticker display (48x8)
- LCD display (16 chars)
"""

from typing import List, Tuple, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum, auto
import math
import random
import numpy as np
from numpy.typing import NDArray

from artifact.graphics.primitives import clear, draw_circle, draw_rect, fill, draw_line
from artifact.graphics.fonts import load_font, draw_text_bitmap
from artifact.graphics.text_utils import (
    draw_animated_text, draw_centered_text, TextEffect,
    render_ticker_animated, TickerEffect, hsv_to_rgb
)


# Scene duration in milliseconds
SCENE_DURATION = 15000  # 15 seconds per scene


class IdleScene(Enum):
    """Available idle scenes."""
    MYSTICAL_EYE = auto()
    COSMIC_PORTAL = auto()
    CAMERA_MIRROR = auto()  # Replaced FORTUNE_CARDS with camera effects
    MATRIX_RAIN = auto()


@dataclass
class SceneState:
    """Shared state for scene animations."""
    time: float = 0.0
    scene_time: float = 0.0  # Time within current scene
    frame: int = 0
    current_scene: IdleScene = IdleScene.MYSTICAL_EYE


class RotatingIdleAnimation:
    """Master idle animation that rotates through multiple stunning scenes.

    Each scene has coordinated animations across all three displays:
    - Main: The primary visual spectacle
    - Ticker: Complementary scrolling/animated text
    - LCD: Scene-appropriate text display

    Supports manual scene switching via left/right navigation, or automatic
    rotation if left alone.
    """

    def __init__(self):
        self.state = SceneState()
        self.scenes = list(IdleScene)
        # Randomize scene order on boot
        random.shuffle(self.scenes)
        self.scene_index = 0
        self.state.current_scene = self.scenes[0]

        # Manual control
        self.manual_mode = False  # True when user has switched scenes
        self.manual_timeout = 0.0  # Return to auto after this much time

        # Scene transition effects
        self.transition_progress = 0.0
        self.transitioning = False
        self.next_scene_index = 0

        # Scene-specific state
        self._init_mystical_eye()
        self._init_cosmic_portal()
        self._init_camera_mirror()
        self._init_matrix_rain()

        # Colors
        self.purple = (147, 51, 234)
        self.gold = (251, 191, 36)
        self.teal = (20, 184, 166)
        self.pink = (236, 72, 153)
        self.blue = (59, 130, 246)
        self.green = (34, 197, 94)

    def _init_mystical_eye(self):
        """Initialize mystical eye scene state."""
        self.eye_x = 0.0
        self.eye_y = 0.0
        self.eye_target_x = 0.0
        self.eye_target_y = 0.0
        self.eye_target_time = 0.0
        self.blink_progress = 0.0
        self.is_blinking = False
        self.blink_cooldown = 0.0
        self.pupil_size = 1.0
        self.iris_rotation = 0.0

    def _init_cosmic_portal(self):
        """Initialize cosmic portal scene state."""
        self.stars: List[List[float]] = []
        self.portal_rotation = 0.0
        self.portal_pulse = 0.0
        self._generate_stars(100)

    def _generate_stars(self, count: int):
        """Generate star field for cosmic portal."""
        self.stars = []
        for _ in range(count):
            # [x, y, z (depth), brightness, speed]
            self.stars.append([
                random.uniform(-64, 64),
                random.uniform(-64, 64),
                random.uniform(1, 64),
                random.uniform(0.3, 1.0),
                random.uniform(0.5, 2.0)
            ])

    def _init_camera_mirror(self):
        """Initialize camera mirror scene state."""
        self._camera = None
        self._camera_frame = None
        self._camera_effect = "normal"  # normal, negative, blur, edge, pixelate
        self._effect_time = 0.0
        self._effect_index = 0
        self._effects = ["normal", "negative", "edge", "pixelate", "scanline"]
        self._glitch_lines: List[int] = []
        self._scanline_offset = 0.0
        self._frame_buffer = None
        # Try to open camera
        try:
            from artifact.simulator.mock_hardware.camera import create_camera
            self._camera = create_camera(resolution=(128, 128))
            self._camera.open()
        except Exception:
            self._camera = None

    def _init_matrix_rain(self):
        """Initialize matrix rain scene state."""
        self.columns: List[dict] = []
        self._generate_columns()

    def _generate_columns(self):
        """Generate matrix rain columns."""
        self.columns = []
        for x in range(0, 128, 8):
            self.columns.append({
                "x": x,
                "y": random.uniform(-50, 0),
                "speed": random.uniform(50, 150),
                "chars": [random.choice("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789")
                         for _ in range(15)],
                "length": random.randint(8, 15),
            })

    def update(self, delta_ms: float) -> None:
        """Update animation state."""
        self.state.time += delta_ms
        self.state.scene_time += delta_ms
        self.state.frame += 1

        # Handle transition effect
        if self.transitioning:
            self.transition_progress += delta_ms / 500  # 500ms transition
            if self.transition_progress >= 1.0:
                self.transitioning = False
                self.transition_progress = 0.0
                self.scene_index = self.next_scene_index
                self.state.current_scene = self.scenes[self.scene_index]
                self.state.scene_time = 0.0
                self._on_scene_enter()

        # Manual mode timeout (return to auto after 30 seconds of no input)
        if self.manual_mode:
            self.manual_timeout -= delta_ms
            if self.manual_timeout <= 0:
                self.manual_mode = False

        # Auto scene transition (only if not in manual mode and not transitioning)
        if not self.manual_mode and not self.transitioning:
            if self.state.scene_time >= SCENE_DURATION:
                self._start_transition((self.scene_index + 1) % len(self.scenes))

        # Update current scene
        scene = self.state.current_scene
        if scene == IdleScene.MYSTICAL_EYE:
            self._update_mystical_eye(delta_ms)
        elif scene == IdleScene.COSMIC_PORTAL:
            self._update_cosmic_portal(delta_ms)
        elif scene == IdleScene.CAMERA_MIRROR:
            self._update_camera_mirror(delta_ms)
        elif scene == IdleScene.MATRIX_RAIN:
            self._update_matrix_rain(delta_ms)

    def _start_transition(self, target_index: int) -> None:
        """Start a transition to a new scene."""
        if target_index != self.scene_index and not self.transitioning:
            self.transitioning = True
            self.transition_progress = 0.0
            self.next_scene_index = target_index

    def next_scene(self) -> None:
        """Switch to the next scene (manual control)."""
        self.manual_mode = True
        self.manual_timeout = 30000  # 30 seconds before returning to auto
        target = (self.scene_index + 1) % len(self.scenes)
        self._start_transition(target)

    def prev_scene(self) -> None:
        """Switch to the previous scene (manual control)."""
        self.manual_mode = True
        self.manual_timeout = 30000  # 30 seconds before returning to auto
        target = (self.scene_index - 1) % len(self.scenes)
        self._start_transition(target)

    def get_scene_name(self) -> str:
        """Get the name of the current scene for display."""
        names = {
            IdleScene.MYSTICAL_EYE: "ГЛАЗ",
            IdleScene.COSMIC_PORTAL: "ПОРТАЛ",
            IdleScene.CAMERA_MIRROR: "ЗЕРКАЛО",
            IdleScene.MATRIX_RAIN: "МАТРИЦА",
        }
        return names.get(self.state.current_scene, "СЦЕНА")

    def _on_scene_enter(self):
        """Called when entering a new scene."""
        scene = self.state.current_scene
        if scene == IdleScene.CAMERA_MIRROR:
            self._effect_index = 0
            self._effect_time = 0.0
            # Re-open camera if needed
            if self._camera is None:
                try:
                    from artifact.simulator.mock_hardware.camera import create_camera
                    self._camera = create_camera(resolution=(128, 128))
                    self._camera.open()
                except Exception:
                    pass
        elif scene == IdleScene.MATRIX_RAIN:
            self._generate_columns()
        elif scene == IdleScene.COSMIC_PORTAL:
            self._generate_stars(100)

    def _update_mystical_eye(self, delta_ms: float):
        """Update mystical eye animation."""
        t = self.state.scene_time

        # Update eye target every 2-4 seconds
        if t > self.eye_target_time:
            self.eye_target_x = random.uniform(-12, 12)
            self.eye_target_y = random.uniform(-8, 8)
            self.eye_target_time = t + random.uniform(1500, 3500)

        # Smooth lerp toward target
        lerp = 0.02 * delta_ms / 16
        self.eye_x += (self.eye_target_x - self.eye_x) * lerp
        self.eye_y += (self.eye_target_y - self.eye_y) * lerp

        # Blinking
        if not self.is_blinking and t > self.blink_cooldown:
            if random.random() < 0.002:  # Random chance to blink
                self.is_blinking = True
                self.blink_progress = 0.0

        if self.is_blinking:
            self.blink_progress += delta_ms / 150  # Blink duration
            if self.blink_progress >= 1.0:
                self.is_blinking = False
                self.blink_cooldown = t + random.uniform(2000, 5000)

        # Pupil dilation (reacts to scene time)
        self.pupil_size = 0.8 + 0.4 * math.sin(t / 1000)

        # Iris pattern rotation
        self.iris_rotation += delta_ms / 500

    def _update_cosmic_portal(self, delta_ms: float):
        """Update cosmic portal animation."""
        # Rotate portal
        self.portal_rotation += delta_ms / 50
        self.portal_pulse = math.sin(self.state.scene_time / 300) * 0.3 + 0.7

        # Move stars toward camera (z decreases)
        for star in self.stars:
            star[2] -= star[4] * delta_ms / 16
            if star[2] <= 0:
                # Reset star to far distance
                star[0] = random.uniform(-64, 64)
                star[1] = random.uniform(-64, 64)
                star[2] = 64
                star[3] = random.uniform(0.3, 1.0)

    def _update_camera_mirror(self, delta_ms: float):
        """Update camera mirror animation with effects."""
        t = self.state.scene_time

        # Cycle through effects every 3 seconds
        effect_duration = 3000
        new_effect_index = int(t / effect_duration) % len(self._effects)
        if new_effect_index != self._effect_index:
            self._effect_index = new_effect_index
            self._camera_effect = self._effects[self._effect_index]

        # Update scanline offset for scanline effect
        self._scanline_offset += delta_ms / 20
        if self._scanline_offset > 128:
            self._scanline_offset = 0

        # Update glitch lines randomly
        if random.random() < 0.05:  # 5% chance per frame
            self._glitch_lines = [random.randint(0, 127) for _ in range(random.randint(1, 5))]
        elif random.random() < 0.3:
            self._glitch_lines = []

        # Capture camera frame
        if self._camera and self._camera.is_open:
            try:
                frame = self._camera.capture_frame()
                if frame is not None:
                    self._camera_frame = frame
            except Exception:
                pass

    def _update_matrix_rain(self, delta_ms: float):
        """Update matrix rain animation."""
        for col in self.columns:
            col["y"] += col["speed"] * delta_ms / 1000
            if col["y"] > 128 + col["length"] * 8:
                col["y"] = random.uniform(-80, -20)
                col["speed"] = random.uniform(50, 150)
                col["chars"] = [random.choice("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789")
                               for _ in range(15)]

    # =========================================================================
    # MAIN DISPLAY RENDERING
    # =========================================================================

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render current scene to main display with transition effects."""
        scene = self.state.current_scene

        if scene == IdleScene.MYSTICAL_EYE:
            self._render_mystical_eye_main(buffer)
        elif scene == IdleScene.COSMIC_PORTAL:
            self._render_cosmic_portal_main(buffer)
        elif scene == IdleScene.CAMERA_MIRROR:
            self._render_camera_mirror_main(buffer)
        elif scene == IdleScene.MATRIX_RAIN:
            self._render_matrix_rain_main(buffer)

        # Apply transition fade effect
        if self.transitioning:
            # Fade to black then to new scene
            if self.transition_progress < 0.5:
                # Fading out
                fade = self.transition_progress * 2  # 0 to 1
            else:
                # Fading in (handled by new scene rendering next frame)
                fade = (1 - self.transition_progress) * 2  # 1 to 0

            # Apply fade as darkening
            fade_amount = int(255 * fade)
            buffer[:, :] = np.clip(buffer.astype(np.int16) - fade_amount, 0, 255).astype(np.uint8)

        # NO counter display - user requested removal of "1/4", "2/4" etc.

    def _render_mystical_eye_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render the mystical all-seeing eye."""
        fill(buffer, (20, 15, 40))
        t = self.state.scene_time
        cx, cy = 64, 64

        # Outer mystical aura - multiple layers
        for ring in range(5):
            ring_r = 55 - ring * 5
            hue = (t / 20 + ring * 30) % 360
            ring_color = hsv_to_rgb(hue, 0.7, 0.3 - ring * 0.05)
            for angle in range(0, 360, 3):
                rad = math.radians(angle + t / 10)
                wobble = math.sin(rad * 3 + t / 200) * 2
                px = int(cx + (ring_r + wobble) * math.cos(rad))
                py = int(cy + (ring_r + wobble) * math.sin(rad))
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = ring_color

        # Eye white (sclera) with subtle veins
        eye_h, eye_w = 35, 50
        for y in range(-eye_h, eye_h + 1):
            for x in range(-eye_w, eye_w + 1):
                # Almond shape
                if (x / eye_w) ** 2 + (y / eye_h) ** 2 <= 1:
                    # Distance from center for gradient
                    dist = math.sqrt(x*x + y*y) / max(eye_w, eye_h)
                    base = int(220 - dist * 50)
                    # Add subtle red veins
                    vein = int(20 * math.sin(x * 0.3 + y * 0.2 + t / 500))
                    px, py = cx + x, cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        # Clamp values to avoid uint8 overflow
                        r = min(255, max(0, base + vein))
                        g = min(255, max(0, base - 10))
                        b = min(255, max(0, base - 10))
                        buffer[py, px] = (r, g, b)

        # Iris with rotating pattern
        iris_r = 22
        iris_cx = cx + int(self.eye_x)
        iris_cy = cy + int(self.eye_y)

        for y in range(-iris_r, iris_r + 1):
            for x in range(-iris_r, iris_r + 1):
                dist = math.sqrt(x*x + y*y)
                if dist <= iris_r:
                    # Spiral pattern in iris
                    angle = math.atan2(y, x) + self.iris_rotation
                    spiral = math.sin(angle * 6 + dist * 0.3) * 0.3 + 0.7

                    # Color gradient from gold center to purple edge
                    t_color = dist / iris_r
                    r = int(self.gold[0] * (1 - t_color) + self.purple[0] * t_color)
                    g = int(self.gold[1] * (1 - t_color) + self.purple[1] * t_color)
                    b = int(self.gold[2] * (1 - t_color) + self.purple[2] * t_color)

                    px, py = iris_cx + x, iris_cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = (int(r * spiral), int(g * spiral), int(b * spiral))

        # Pupil (black hole with slight blue glow)
        pupil_r = int(8 * self.pupil_size)
        pupil_cx = iris_cx + int(self.eye_x * 0.3)
        pupil_cy = iris_cy + int(self.eye_y * 0.3)

        for y in range(-pupil_r - 2, pupil_r + 3):
            for x in range(-pupil_r - 2, pupil_r + 3):
                dist = math.sqrt(x*x + y*y)
                if dist <= pupil_r + 2:
                    px, py = pupil_cx + x, pupil_cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        if dist <= pupil_r:
                            # Deep black with slight blue tinge
                            buffer[py, px] = (5, 5, 15)
                        else:
                            # Glow edge
                            glow = 1 - (dist - pupil_r) / 2
                            buffer[py, px] = (int(30 * glow), int(30 * glow), int(60 * glow))

        # Pupil highlight (light reflection)
        hl_x = pupil_cx - 3
        hl_y = pupil_cy - 3
        if 0 <= hl_x < 128 and 0 <= hl_y < 128:
            buffer[hl_y, hl_x] = (255, 255, 255)
            buffer[hl_y, hl_x + 1] = (200, 200, 255)
            buffer[hl_y + 1, hl_x] = (200, 200, 255)

        # Blink overlay
        if self.is_blinking:
            blink = math.sin(self.blink_progress * math.pi)  # 0->1->0
            eyelid_y = int(eye_h * blink)
            for y in range(-eye_h, -eye_h + eyelid_y * 2):
                for x in range(-eye_w, eye_w + 1):
                    if (x / eye_w) ** 2 + (y / eye_h) ** 2 <= 1:
                        px, py = cx + x, cy + y
                        if 0 <= px < 128 and 0 <= py < 128:
                            buffer[py, px] = (80, 50, 100)

        # Title with glow effect
        draw_animated_text(buffer, "VNVNC", 8, self.gold, t, TextEffect.GLOW, scale=2)
        draw_animated_text(buffer, "НАЖМИ СТАРТ", 115, self.teal, t, TextEffect.PULSE, scale=1)

    def _render_cosmic_portal_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render swirling cosmic portal with stars."""
        fill(buffer, (5, 5, 15))
        t = self.state.scene_time
        cx, cy = 64, 64

        # Star field (3D projection)
        for star in self.stars:
            sx, sy, sz = star[0], star[1], star[2]
            # Project 3D to 2D
            if sz > 0:
                px = int(cx + sx * 64 / sz)
                py = int(cy + sy * 64 / sz)

                if 0 <= px < 128 and 0 <= py < 128:
                    # Brightness based on depth
                    brightness = star[3] * (1 - sz / 64)
                    size = max(1, int(3 * (1 - sz / 64)))
                    color = (int(255 * brightness), int(255 * brightness), int(255 * brightness))

                    if size == 1:
                        buffer[py, px] = color
                    else:
                        draw_circle(buffer, px, py, size, color)

        # Portal rings (concentric spirals)
        for ring in range(8):
            ring_base_r = 10 + ring * 6
            ring_r = ring_base_r + 3 * math.sin(t / 200 + ring)
            hue = (t / 5 + ring * 40) % 360

            for angle in range(0, 360, 2):
                rad = math.radians(angle + self.portal_rotation + ring * 15)
                # Spiral distortion
                spiral_r = ring_r + 5 * math.sin(rad * 3 + t / 100)

                px = int(cx + spiral_r * math.cos(rad))
                py = int(cy + spiral_r * math.sin(rad))

                if 0 <= px < 128 and 0 <= py < 128:
                    brightness = 0.5 + 0.5 * math.sin(angle / 30 + t / 100)
                    color = hsv_to_rgb(hue, 0.8, brightness * self.portal_pulse)
                    buffer[py, px] = color

        # Central glow
        for r in range(15, 0, -1):
            alpha = (15 - r) / 15
            glow_color = (int(100 * alpha), int(50 * alpha), int(150 * alpha))
            draw_circle(buffer, cx, cy, r, glow_color)

        # Title - NO RAINBOW, use purple/blue gradient instead
        draw_animated_text(buffer, "VNVNC", 8, self.pink, t, TextEffect.GLOW, scale=2)
        draw_animated_text(buffer, "ПОРТАЛ СУДЬБЫ", 115, self.blue, t, TextEffect.WAVE, scale=1)

    def _render_camera_mirror_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render camera with fun visual effects."""
        t = self.state.scene_time

        # If no camera frame, show a placeholder
        if self._camera_frame is None:
            fill(buffer, (30, 20, 50))
            draw_animated_text(buffer, "ЗЕРКАЛО", 50, self.teal, t, TextEffect.WAVE, scale=2)
            draw_animated_text(buffer, "КАМЕРА...", 75, self.pink, t, TextEffect.PULSE, scale=1)
            return

        # Resize camera frame to 128x128 if needed
        frame = self._camera_frame
        if frame.shape[:2] != (128, 128):
            from PIL import Image
            img = Image.fromarray(frame)
            img = img.resize((128, 128), Image.Resampling.NEAREST)
            frame = np.array(img)

        # Apply the current effect
        effect = self._camera_effect

        if effect == "negative":
            # Negative/inverted colors
            frame = 255 - frame

        elif effect == "edge":
            # Edge detection effect (cyan/pink colors)
            gray = np.mean(frame, axis=2).astype(np.uint8)
            # Simple edge detection
            edges = np.zeros_like(gray)
            edges[1:, :] = np.abs(gray[1:, :].astype(np.int16) - gray[:-1, :].astype(np.int16))
            edges[:, 1:] += np.abs(gray[:, 1:].astype(np.int16) - gray[:, :-1].astype(np.int16))
            edges = np.clip(edges, 0, 255).astype(np.uint8)
            # Color the edges cyan
            frame = np.zeros((128, 128, 3), dtype=np.uint8)
            frame[:, :, 0] = edges // 4  # Minimal red
            frame[:, :, 1] = edges  # Full green
            frame[:, :, 2] = edges  # Full blue (cyan)

        elif effect == "pixelate":
            # Pixelate effect
            pixel_size = 8
            for py in range(0, 128, pixel_size):
                for px in range(0, 128, pixel_size):
                    block = frame[py:py+pixel_size, px:px+pixel_size]
                    avg_color = block.mean(axis=(0, 1)).astype(np.uint8)
                    frame[py:py+pixel_size, px:px+pixel_size] = avg_color

        elif effect == "scanline":
            # CRT scanline effect with purple tint
            for y in range(0, 128, 2):
                frame[y, :] = (frame[y, :].astype(np.int16) * 0.6).astype(np.uint8)
            # Add purple tint
            frame[:, :, 0] = np.clip(frame[:, :, 0].astype(np.int16) + 30, 0, 255).astype(np.uint8)
            frame[:, :, 2] = np.clip(frame[:, :, 2].astype(np.int16) + 50, 0, 255).astype(np.uint8)

        # Copy frame to buffer
        np.copyto(buffer, frame)

        # Add glitch lines effect
        for line_y in self._glitch_lines:
            if 0 <= line_y < 128:
                shift = random.randint(-10, 10)
                buffer[line_y, :] = np.roll(buffer[line_y, :], shift, axis=0)
                buffer[line_y, :] = (255 - buffer[line_y, :])  # Invert glitch line

        # Effect name overlay at bottom
        effect_names = {
            "normal": "ЗЕРКАЛО",
            "negative": "НЕГАТИВ",
            "edge": "КОНТУР",
            "pixelate": "ПИКСЕЛИ",
            "scanline": "РЕТРО"
        }
        effect_text = effect_names.get(effect, "ЭФФЕКТ")

        # Dark bar for text
        draw_rect(buffer, 0, 110, 128, 18, (0, 0, 0))
        draw_centered_text(buffer, effect_text, 112, self.teal, scale=1)

        # Title at top
        draw_rect(buffer, 0, 0, 128, 14, (0, 0, 0))
        draw_centered_text(buffer, "НАЖМИ СТАРТ", 3, self.pink, scale=1)

    def _render_matrix_rain_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render matrix-style character rain."""
        fill(buffer, (0, 5, 0))
        t = self.state.scene_time
        font = load_font("cyrillic")

        # Draw each column
        for col in self.columns:
            x = col["x"]
            base_y = int(col["y"])

            for i, char in enumerate(col["chars"][:col["length"]]):
                y = base_y - i * 8

                if 0 <= y < 128:
                    # Brightness gradient (brightest at head)
                    if i == 0:
                        color = (200, 255, 200)  # Bright head
                    else:
                        fade = 1 - i / col["length"]
                        color = (0, int(180 * fade), 0)

                    draw_text_bitmap(buffer, char, x, y, color, font, scale=1)

        # Glowing title overlay
        draw_rect(buffer, 0, 45, 128, 35, (0, 20, 0))  # Dark backdrop
        draw_animated_text(buffer, "VNVNC", 50, self.green, t, TextEffect.GLITCH, scale=2)
        draw_animated_text(buffer, "СИСТЕМА ГОТОВА", 75, (0, 150, 0), t, TextEffect.TYPING, scale=1)

    # =========================================================================
    # TICKER DISPLAY RENDERING
    # =========================================================================

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render current scene to ticker display."""
        clear(buffer)
        scene = self.state.current_scene
        t = self.state.scene_time

        if scene == IdleScene.MYSTICAL_EYE:
            text = "ВЗГЛЯНИ В ГЛАЗА СУДЬБЫ"
            render_ticker_animated(buffer, text, t, self.gold, TickerEffect.SPARKLE_SCROLL)

        elif scene == IdleScene.COSMIC_PORTAL:
            text = "ПОРТАЛ В НЕИЗВЕДАННОЕ"
            render_ticker_animated(buffer, text, t, self.pink, TickerEffect.SPARKLE_SCROLL)

        elif scene == IdleScene.CAMERA_MIRROR:
            text = "ПОСМОТРИ НА СЕБЯ"
            render_ticker_animated(buffer, text, t, self.teal, TickerEffect.WAVE_SCROLL)

        elif scene == IdleScene.MATRIX_RAIN:
            text = "ЗАГРУЗКА СУДЬБЫ"
            render_ticker_animated(buffer, text, t, self.green, TickerEffect.GLITCH_SCROLL)

    # =========================================================================
    # LCD DISPLAY TEXT
    # =========================================================================

    def get_lcd_text(self) -> str:
        """Get LCD text for current scene."""
        scene = self.state.current_scene
        t = self.state.scene_time

        # Cycle through multiple texts per scene
        idx = int(t / 2000) % 3

        if scene == IdleScene.MYSTICAL_EYE:
            texts = ["  ВСЁ ВИДЯЩЕЕ  ", "    ГЛАЗ    ", " НАЖМИ СТАРТ "]
        elif scene == IdleScene.COSMIC_PORTAL:
            texts = [" КОСМОС ЖДЁТ ", "  ТВОЙ ПУТЬ  ", " НАЖМИ СТАРТ "]
        elif scene == IdleScene.CAMERA_MIRROR:
            texts = ["МАГИЯ ЗЕРКАЛА", " КТО ТЫ?     ", " НАЖМИ СТАРТ "]
        elif scene == IdleScene.MATRIX_RAIN:
            texts = ["СИСТЕМА ОНЛАЙН", " ПОДКЛЮЧИСЬ  ", " НАЖМИ СТАРТ "]
        else:
            texts = ["    VNVNC    ", " НАЖМИ СТАРТ ", "    ★★★★    "]

        return texts[idx].center(16)[:16]

    def reset(self) -> None:
        """Reset animation state with randomized scene order."""
        self.state = SceneState()
        # Re-randomize scene order on reset/reboot
        random.shuffle(self.scenes)
        self.scene_index = 0
        self.state.current_scene = self.scenes[0]
        self._init_mystical_eye()
        self._init_cosmic_portal()
        self._init_camera_mirror()
        self._init_matrix_rain()

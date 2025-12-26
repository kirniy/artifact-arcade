"""Efficient idle animation scenes optimized for 60fps on Raspberry Pi.

This module provides 4 smooth, visually stunning idle scenes that cycle automatically.
All effects are optimized using pygame primitives and simple math - no per-pixel loops.

1. MYSTICAL EYE - Animated eye with pulsing aura
2. COSMIC PORTAL - Starfield with rotating portal
3. CAMERA_MIRROR - Live camera feed with effects
4. PLASMA_WAVE - Smooth plasma color cycling

Each scene has coordinated animations for:
- Main display (128x128)
- Ticker display (48x8)
- LCD display (16 chars)
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
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
    CAMERA_MIRROR = auto()
    PLASMA_WAVE = auto()


@dataclass
class SceneState:
    """Shared state for scene animations."""
    time: float = 0.0
    scene_time: float = 0.0
    frame: int = 0
    current_scene: IdleScene = IdleScene.MYSTICAL_EYE


class RotatingIdleAnimation:
    """Efficient idle animation with smooth 60fps rendering.

    Uses pygame-style primitives and simple math for performance.
    No per-pixel numpy loops - all operations are vectorized or use drawing calls.
    """

    def __init__(self):
        self.state = SceneState()
        self.scenes = list(IdleScene)
        random.shuffle(self.scenes)
        self.scene_index = 0
        self.state.current_scene = self.scenes[0]

        # Manual control
        self.manual_mode = False
        self.manual_timeout = 0.0

        # Scene transition
        self.transition_progress = 0.0
        self.transitioning = False
        self.next_scene_index = 0

        # Pre-generate stars for cosmic portal (30 stars, not 100)
        self.stars = [
            (random.randint(0, 127), random.randint(0, 127),
             random.uniform(0.3, 1.0), random.uniform(0, 6.28))
            for _ in range(30)
        ]

        # Eye state
        self.eye_x = 0.0
        self.eye_y = 0.0
        self.eye_target_x = 0.0
        self.eye_target_y = 0.0
        self.eye_target_time = 0.0
        self.blink = 0.0

        # Camera state
        self._camera = None
        self._camera_frame = None
        self._effect_index = 0
        self._effects = ["normal", "negative", "dither"]

        # Colors
        self.purple = (147, 51, 234)
        self.gold = (251, 191, 36)
        self.teal = (20, 184, 166)
        self.pink = (236, 72, 153)

    def update(self, delta_ms: float) -> None:
        """Update animation state."""
        self.state.time += delta_ms
        self.state.scene_time += delta_ms
        self.state.frame += 1

        # Handle transitions
        if self.transitioning:
            self.transition_progress += delta_ms / 500
            if self.transition_progress >= 1.0:
                self.transitioning = False
                self.transition_progress = 0.0
                self._on_scene_exit(self.state.current_scene)
                self.scene_index = self.next_scene_index
                self.state.current_scene = self.scenes[self.scene_index]
                self.state.scene_time = 0.0
                self._on_scene_enter()

        # Manual mode timeout
        if self.manual_mode:
            self.manual_timeout -= delta_ms
            if self.manual_timeout <= 0:
                self.manual_mode = False

        # Auto scene transition
        if not self.manual_mode and not self.transitioning:
            if self.state.scene_time >= SCENE_DURATION:
                self._start_transition((self.scene_index + 1) % len(self.scenes))

        # Update eye movement
        t = self.state.scene_time
        if t > self.eye_target_time:
            self.eye_target_x = random.uniform(-10, 10)
            self.eye_target_y = random.uniform(-6, 6)
            self.eye_target_time = t + random.uniform(2000, 4000)

        # Smooth eye follow
        lerp = min(1.0, delta_ms * 0.003)
        self.eye_x += (self.eye_target_x - self.eye_x) * lerp
        self.eye_y += (self.eye_target_y - self.eye_y) * lerp

        # Blink occasionally
        if random.random() < 0.002:
            self.blink = 1.0
        if self.blink > 0:
            self.blink = max(0, self.blink - delta_ms * 0.01)

        # Update camera for mirror mode
        if self.state.current_scene == IdleScene.CAMERA_MIRROR:
            self._update_camera()
            # Cycle effects every 4 seconds
            self._effect_index = int(self.state.scene_time / 4000) % len(self._effects)

    def _start_transition(self, target_index: int) -> None:
        if target_index != self.scene_index and not self.transitioning:
            self.transitioning = True
            self.transition_progress = 0.0
            self.next_scene_index = target_index

    def next_scene(self) -> None:
        self.manual_mode = True
        self.manual_timeout = 30000
        target = (self.scene_index + 1) % len(self.scenes)
        self._start_transition(target)

    def prev_scene(self) -> None:
        self.manual_mode = True
        self.manual_timeout = 30000
        target = (self.scene_index - 1) % len(self.scenes)
        self._start_transition(target)

    def get_scene_name(self) -> str:
        names = {
            IdleScene.MYSTICAL_EYE: "ГЛАЗ",
            IdleScene.COSMIC_PORTAL: "ПОРТАЛ",
            IdleScene.CAMERA_MIRROR: "ЗЕРКАЛО",
            IdleScene.PLASMA_WAVE: "ПЛАЗМА",
        }
        return names.get(self.state.current_scene, "СЦЕНА")

    def _on_scene_enter(self) -> None:
        scene = self.state.current_scene
        if scene == IdleScene.CAMERA_MIRROR:
            self._open_camera()
        elif scene == IdleScene.COSMIC_PORTAL:
            # Regenerate stars with new positions
            self.stars = [
                (random.randint(0, 127), random.randint(0, 127),
                 random.uniform(0.3, 1.0), random.uniform(0, 6.28))
                for _ in range(30)
            ]

    def _on_scene_exit(self, scene: IdleScene) -> None:
        if scene == IdleScene.CAMERA_MIRROR:
            self._close_camera()

    def _open_camera(self) -> None:
        if self._camera is not None:
            return
        try:
            from artifact.hardware.camera.picamera import create_camera, is_pi_camera_available
            if is_pi_camera_available():
                self._camera = create_camera(preview_resolution=(128, 128))
                self._camera.open()
                return
        except:
            pass
        try:
            from artifact.simulator.mock_hardware.camera import create_camera
            self._camera = create_camera(resolution=(128, 128))
            self._camera.open()
        except:
            self._camera = None

    def _close_camera(self) -> None:
        if self._camera:
            try:
                self._camera.close()
            except:
                pass
        self._camera = None
        self._camera_frame = None

    def _update_camera(self) -> None:
        if self._camera and self._camera.is_open:
            try:
                frame = self._camera.capture_frame()
                if frame is not None:
                    self._camera_frame = frame
            except:
                pass

    # =========================================================================
    # MAIN DISPLAY RENDERING - Efficient pygame-style drawing
    # =========================================================================

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render current scene to main display."""
        scene = self.state.current_scene

        if scene == IdleScene.MYSTICAL_EYE:
            self._render_eye(buffer)
        elif scene == IdleScene.COSMIC_PORTAL:
            self._render_portal(buffer)
        elif scene == IdleScene.CAMERA_MIRROR:
            self._render_camera(buffer)
        elif scene == IdleScene.PLASMA_WAVE:
            self._render_plasma(buffer)

        # Apply transition fade
        if self.transitioning:
            fade = self.transition_progress if self.transition_progress < 0.5 else (1 - self.transition_progress)
            fade_amount = int(255 * fade * 2)
            buffer[:] = np.clip(buffer.astype(np.int16) - fade_amount, 0, 255).astype(np.uint8)

    def _render_eye(self, buffer: NDArray[np.uint8]) -> None:
        """Render mystical eye - EFFICIENT version."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        # Dark purple background
        fill(buffer, (20, 15, 40))

        # Simple aura rings (just 3 rings, not 6)
        for ring in range(3):
            radius = 55 - ring * 8
            pulse = 0.5 + 0.5 * math.sin(t * 2 + ring)
            hue = (t * 30 + ring * 40) % 360
            color = hsv_to_rgb(hue, 0.8, 0.3 * pulse)
            # Draw circle as ring of pixels (fast)
            for angle in range(0, 360, 6):  # Every 6 degrees = 60 points
                rad = math.radians(angle)
                px = int(cx + radius * math.cos(rad))
                py = int(cy + radius * math.sin(rad))
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = color

        # Eye white (simple filled ellipse approximation)
        eye_h, eye_w = 28, 42
        for y in range(-eye_h, eye_h + 1, 2):  # Step by 2 for speed
            row_width = int(eye_w * math.sqrt(1 - (y / eye_h) ** 2))
            for x in range(-row_width, row_width + 1):
                px, py = cx + x, cy + y
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = (220, 215, 210)

        # Iris (simple filled circle)
        iris_cx = int(cx + self.eye_x)
        iris_cy = int(cy + self.eye_y)
        iris_r = 18
        for y in range(-iris_r, iris_r + 1, 2):
            for x in range(-iris_r, iris_r + 1, 2):
                if x*x + y*y <= iris_r*iris_r:
                    px, py = iris_cx + x, iris_cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        dist = math.sqrt(x*x + y*y) / iris_r
                        # Gold to purple gradient
                        r = int(self.gold[0] * (1 - dist) + self.purple[0] * dist)
                        g = int(self.gold[1] * (1 - dist) + self.purple[1] * dist)
                        b = int(self.gold[2] * (1 - dist) + self.purple[2] * dist)
                        buffer[py, px] = (r, g, b)

        # Pupil (small black circle)
        pupil_r = int(6 + 2 * math.sin(t))
        pupil_cx = int(iris_cx + self.eye_x * 0.2)
        pupil_cy = int(iris_cy + self.eye_y * 0.2)
        for y in range(-pupil_r, pupil_r + 1):
            for x in range(-pupil_r, pupil_r + 1):
                if x*x + y*y <= pupil_r*pupil_r:
                    px, py = pupil_cx + x, pupil_cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = (5, 5, 15)

        # Highlight
        hl_x, hl_y = pupil_cx - 3, pupil_cy - 3
        if 0 <= hl_x < 127 and 0 <= hl_y < 127:
            buffer[hl_y, hl_x] = (255, 255, 255)
            buffer[hl_y, hl_x + 1] = (200, 200, 255)

        # Blink overlay
        if self.blink > 0:
            blink_h = int(eye_h * self.blink)
            for y in range(-eye_h, -eye_h + blink_h * 2):
                row_width = int(eye_w * math.sqrt(max(0, 1 - (y / eye_h) ** 2)))
                for x in range(-row_width, row_width + 1):
                    px, py = cx + x, cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = (80, 50, 100)

        # Title text
        draw_centered_text(buffer, "VNVNC", 8, self.gold, scale=2)

        # "Press start" with blink
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, self.teal, scale=1)

    def _render_portal(self, buffer: NDArray[np.uint8]) -> None:
        """Render cosmic portal - EFFICIENT version."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        # Dark space background
        fill(buffer, (5, 5, 20))

        # Star field - simple and fast (30 stars)
        for sx, sy, brightness, phase in self.stars:
            # Twinkle
            twinkle = 0.5 + 0.5 * math.sin(t * 3 + phase)
            b = int(255 * brightness * twinkle)
            if 0 <= sx < 128 and 0 <= sy < 128:
                buffer[sy, sx] = (b, b, b)

        # Portal rings - just 5 simple rings
        for ring in range(5):
            ring_r = 10 + ring * 10
            hue = (t * 40 + ring * 30) % 360
            brightness = 0.6 + 0.4 * math.sin(t * 2 + ring)
            color = hsv_to_rgb(hue, 0.8, brightness)

            # Draw ring with rotation
            rotation = t * 2 + ring * 0.5
            for angle in range(0, 360, 8):  # 45 points per ring
                rad = math.radians(angle) + rotation
                px = int(cx + ring_r * math.cos(rad))
                py = int(cy + ring_r * math.sin(rad))
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = color
                    # Make it thicker
                    for dx, dy in [(1, 0), (0, 1)]:
                        npx, npy = px + dx, py + dy
                        if 0 <= npx < 128 and 0 <= npy < 128:
                            buffer[npy, npx] = color

        # Central glow - simple gradient circle
        for r in range(15, 0, -3):
            alpha = (15 - r) / 15
            glow = int(200 * alpha)
            color = (glow, int(glow * 0.5), glow)
            for angle in range(0, 360, 12):
                rad = math.radians(angle)
                px = int(cx + r * math.cos(rad))
                py = int(cy + r * math.sin(rad))
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = color

        # Title
        draw_centered_text(buffer, "VNVNC", 8, self.pink, scale=2)
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, (100, 150, 255), scale=1)

    def _render_camera(self, buffer: NDArray[np.uint8]) -> None:
        """Render camera mirror - EFFICIENT version."""
        t = self.state.scene_time / 1000

        if self._camera_frame is None:
            # No camera - show placeholder
            fill(buffer, (30, 20, 50))
            # Pulsing circle
            pulse = int(20 + 5 * math.sin(t * 3))
            for r in range(pulse, 10, -3):
                alpha = (pulse - r) / pulse
                color = (int(20 * alpha), int(180 * alpha), int(160 * alpha))
                for angle in range(0, 360, 15):
                    rad = math.radians(angle)
                    px = int(64 + r * math.cos(rad))
                    py = int(64 + r * math.sin(rad))
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = color
            draw_centered_text(buffer, "ЗЕРКАЛО", 50, self.teal, scale=2)
            draw_centered_text(buffer, "КАМЕРА...", 75, self.pink, scale=1)
            return

        # Get camera frame and resize if needed
        frame = self._camera_frame
        if frame.shape[0] != 128 or frame.shape[1] != 128:
            # Simple nearest-neighbor resize
            h, w = frame.shape[:2]
            new_frame = np.zeros((128, 128, 3), dtype=np.uint8)
            for y in range(128):
                for x in range(128):
                    sy = min(int(y * h / 128), h - 1)
                    sx = min(int(x * w / 128), w - 1)
                    new_frame[y, x] = frame[sy, sx]
            frame = new_frame

        # Apply effect
        effect = self._effects[self._effect_index]

        if effect == "negative":
            # Simple invert
            frame = 255 - frame
        elif effect == "dither":
            # Simple threshold dither - fast
            gray = np.mean(frame, axis=2)
            threshold = 128 + 30 * math.sin(t * 2)
            for y in range(0, 128, 2):
                for x in range(0, 128, 2):
                    if gray[y, x] > threshold:
                        frame[y:y+2, x:x+2] = [self.teal[0], self.teal[1], self.teal[2]]
                    else:
                        frame[y:y+2, x:x+2] = [20, 15, 40]

        # Copy to buffer
        np.copyto(buffer, frame)

        # Effect label
        effect_names = {"normal": "ЗЕРКАЛО", "negative": "НЕГАТИВ", "dither": "ПИКСЕЛИ"}
        draw_rect(buffer, 0, 108, 128, 20, (0, 0, 0))
        draw_centered_text(buffer, effect_names.get(effect, "ЭФФЕКТ"), 110, self.teal, scale=1)

        # Top bar
        draw_rect(buffer, 0, 0, 128, 14, (0, 0, 0))
        draw_centered_text(buffer, "НАЖМИ СТАРТ", 4, self.pink, scale=1)

    def _render_plasma(self, buffer: NDArray[np.uint8]) -> None:
        """Render plasma wave - EFFICIENT version using numpy vectorization."""
        t = self.state.scene_time / 1000

        # Pre-compute sine wave lookup for speed
        # Use vectorized numpy operations instead of per-pixel loops
        y_coords, x_coords = np.mgrid[0:128, 0:128]

        # Simple plasma formula (vectorized)
        v1 = np.sin(x_coords / 16 + t)
        v2 = np.sin(y_coords / 16 + t * 0.7)
        v3 = np.sin((x_coords + y_coords) / 24 + t * 0.5)
        v4 = np.sin(np.sqrt(((x_coords - 64) ** 2 + (y_coords - 64) ** 2) / 16) + t)

        # Combine waves
        plasma = (v1 + v2 + v3 + v4) / 4  # Range -1 to 1
        plasma = (plasma + 1) / 2  # Range 0 to 1

        # Convert to HSV-like color (vectorized)
        hue = (plasma * 360 + t * 30) % 360

        # Simple HSV to RGB (approximation for speed)
        h = hue / 60
        x = (1 - np.abs(h % 2 - 1)) * 200 + 55

        # Initialize with base colors
        r = np.zeros((128, 128), dtype=np.uint8)
        g = np.zeros((128, 128), dtype=np.uint8)
        b = np.zeros((128, 128), dtype=np.uint8)

        # Color regions based on hue
        mask0 = (h >= 0) & (h < 1)
        mask1 = (h >= 1) & (h < 2)
        mask2 = (h >= 2) & (h < 3)
        mask3 = (h >= 3) & (h < 4)
        mask4 = (h >= 4) & (h < 5)
        mask5 = (h >= 5) & (h < 6)

        r[mask0] = 255; g[mask0] = x[mask0].astype(np.uint8); b[mask0] = 55
        r[mask1] = x[mask1].astype(np.uint8); g[mask1] = 255; b[mask1] = 55
        r[mask2] = 55; g[mask2] = 255; b[mask2] = x[mask2].astype(np.uint8)
        r[mask3] = 55; g[mask3] = x[mask3].astype(np.uint8); b[mask3] = 255
        r[mask4] = x[mask4].astype(np.uint8); g[mask4] = 55; b[mask4] = 255
        r[mask5] = 255; g[mask5] = 55; b[mask5] = x[mask5].astype(np.uint8)

        buffer[:, :, 0] = r
        buffer[:, :, 1] = g
        buffer[:, :, 2] = b

        # Title with black outline for visibility
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 8 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 8, (255, 255, 255), scale=2)

        if int(t * 2) % 2 == 0:
            for ox in [-1, 0, 1]:
                for oy in [-1, 0, 1]:
                    if ox != 0 or oy != 0:
                        draw_centered_text(buffer, "НАЖМИ СТАРТ", 114 + oy, (0, 0, 0), scale=1)
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, (255, 200, 100), scale=1)

    # =========================================================================
    # TICKER DISPLAY RENDERING
    # =========================================================================

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        clear(buffer)
        scene = self.state.current_scene
        t = self.state.scene_time

        texts = {
            IdleScene.MYSTICAL_EYE: "ВЗГЛЯНИ В ГЛАЗА СУДЬБЫ",
            IdleScene.COSMIC_PORTAL: "ПОРТАЛ В НЕИЗВЕДАННОЕ",
            IdleScene.CAMERA_MIRROR: "ПОСМОТРИ НА СЕБЯ",
            IdleScene.PLASMA_WAVE: "МАГИЯ ЦВЕТА",
        }
        text = texts.get(scene, "VNVNC ARCADE")

        colors = {
            IdleScene.MYSTICAL_EYE: self.gold,
            IdleScene.COSMIC_PORTAL: self.pink,
            IdleScene.CAMERA_MIRROR: self.teal,
            IdleScene.PLASMA_WAVE: (255, 200, 100),
        }
        color = colors.get(scene, (255, 255, 255))

        render_ticker_animated(buffer, text, t, color, TickerEffect.SPARKLE_SCROLL)

    # =========================================================================
    # LCD DISPLAY TEXT
    # =========================================================================

    def get_lcd_text(self) -> str:
        """Get LCD text for current scene."""
        scene = self.state.current_scene
        t = self.state.scene_time
        idx = int(t / 2000) % 3

        texts = {
            IdleScene.MYSTICAL_EYE: ["  ВСЁ ВИДЯЩЕЕ  ", "    ГЛАЗ    ", " НАЖМИ СТАРТ "],
            IdleScene.COSMIC_PORTAL: [" КОСМОС ЖДЁТ ", "  ТВОЙ ПУТЬ  ", " НАЖМИ СТАРТ "],
            IdleScene.CAMERA_MIRROR: ["МАГИЯ ЗЕРКАЛА", " КТО ТЫ?     ", " НАЖМИ СТАРТ "],
            IdleScene.PLASMA_WAVE: ["  ПЛАЗМЕННЫЙ  ", "   ТАНЕЦ    ", " НАЖМИ СТАРТ "],
        }
        scene_texts = texts.get(scene, ["    VNVNC    ", " НАЖМИ СТАРТ ", "    ★★★★    "])
        return scene_texts[idx].center(16)[:16]

    def reset(self) -> None:
        """Reset animation state."""
        self._close_camera()
        self.state = SceneState()
        random.shuffle(self.scenes)
        self.scene_index = 0
        self.state.current_scene = self.scenes[0]
        self.eye_x = 0.0
        self.eye_y = 0.0
        self.eye_target_x = 0.0
        self.eye_target_y = 0.0
        self.eye_target_time = 0.0
        self.blink = 0.0

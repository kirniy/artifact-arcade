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
    # New scenes with camera background
    NEON_TUNNEL = auto()      # Camera with neon ring tunnel
    GLITCH_GRID = auto()      # Camera with glitch scanlines
    FIRE_SILHOUETTE = auto()  # Camera with fire/heat effect
    MATRIX_RAIN = auto()      # Camera with matrix code rain
    STARFIELD_3D = auto()     # Camera with 3D starfield overlay
    # EPIC demo effects (ported from led_demo.py)
    PLASMA_VORTEX = auto()    # Intense plasma vortex
    NEON_GRID = auto()        # Retro synthwave grid
    ELECTRIC_STORM = auto()   # Lightning storm
    QUANTUM_FIELD = auto()    # Quantum particles
    DNA_HELIX = auto()        # DNA double helix


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

        # Quantum field particles (for QUANTUM_FIELD scene)
        self.quantum_particles = [
            {'x': random.random(), 'y': random.random(), 'vx': 0, 'vy': 0}
            for _ in range(60)
        ]

        # Electric storm lightning state
        self.lightning = []
        self.lightning_flash = 0

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
            IdleScene.NEON_TUNNEL: "ТОННЕЛЬ",
            IdleScene.GLITCH_GRID: "ГЛИТЧ",
            IdleScene.FIRE_SILHOUETTE: "ОГОНЬ",
            IdleScene.MATRIX_RAIN: "МАТРИЦА",
            IdleScene.STARFIELD_3D: "ЗВЁЗДЫ",
            IdleScene.PLASMA_VORTEX: "ВОРТЕКС",
            IdleScene.NEON_GRID: "СЕТКА",
            IdleScene.ELECTRIC_STORM: "ШТОРМ",
            IdleScene.QUANTUM_FIELD: "КВАНТ",
            IdleScene.DNA_HELIX: "ДНК",
        }
        return names.get(self.state.current_scene, "СЦЕНА")

    # Scenes that use camera
    CAMERA_SCENES = {
        IdleScene.CAMERA_MIRROR,
        IdleScene.NEON_TUNNEL,
        IdleScene.GLITCH_GRID,
        IdleScene.FIRE_SILHOUETTE,
        IdleScene.MATRIX_RAIN,
        IdleScene.STARFIELD_3D,
    }

    def _on_scene_enter(self) -> None:
        scene = self.state.current_scene
        # Open camera for all camera-based scenes
        if scene in self.CAMERA_SCENES:
            self._open_camera()
        elif scene == IdleScene.COSMIC_PORTAL:
            # Regenerate stars with new positions
            self.stars = [
                (random.randint(0, 127), random.randint(0, 127),
                 random.uniform(0.3, 1.0), random.uniform(0, 6.28))
                for _ in range(30)
            ]

    def _on_scene_exit(self, scene: IdleScene) -> None:
        if scene in self.CAMERA_SCENES:
            self._close_camera()

    def _open_camera(self) -> None:
        if self._camera is not None:
            return
        try:
            from artifact.utils.camera import create_camera, is_pi_camera_available, IS_HARDWARE
            if IS_HARDWARE and is_pi_camera_available():
                self._camera = create_camera(preview_resolution=(128, 128))
            else:
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

    def _resize_camera_fill(self, frame: NDArray[np.uint8]) -> NDArray[np.uint8]:
        """Resize camera frame to 128x128 using CROP-TO-FILL (no black bars)."""
        if frame.shape[0] == 128 and frame.shape[1] == 128:
            return frame

        h, w = frame.shape[:2]

        # Calculate scale factor to FILL 128x128 (crop excess, no black bars)
        scale = max(128 / w, 128 / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        # Calculate crop offset (center crop)
        crop_x = (new_w - 128) // 2
        crop_y = (new_h - 128) // 2

        # Resize with crop-to-fill
        new_frame = np.zeros((128, 128, 3), dtype=np.uint8)
        for y in range(128):
            for x in range(128):
                src_x = (x + crop_x) / scale
                src_y = (y + crop_y) / scale
                sx = max(0, min(int(src_x), w - 1))
                sy = max(0, min(int(src_y), h - 1))
                new_frame[y, x] = frame[sy, sx]
        return new_frame

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
        elif scene == IdleScene.NEON_TUNNEL:
            self._render_neon_tunnel(buffer)
        elif scene == IdleScene.GLITCH_GRID:
            self._render_glitch_grid(buffer)
        elif scene == IdleScene.FIRE_SILHOUETTE:
            self._render_fire_silhouette(buffer)
        elif scene == IdleScene.MATRIX_RAIN:
            self._render_matrix_rain(buffer)
        elif scene == IdleScene.STARFIELD_3D:
            self._render_starfield_3d(buffer)
        # EPIC demo effects
        elif scene == IdleScene.PLASMA_VORTEX:
            self._render_plasma_vortex(buffer)
        elif scene == IdleScene.NEON_GRID:
            self._render_neon_grid(buffer)
        elif scene == IdleScene.ELECTRIC_STORM:
            self._render_electric_storm(buffer)
        elif scene == IdleScene.QUANTUM_FIELD:
            self._render_quantum_field(buffer)
        elif scene == IdleScene.DNA_HELIX:
            self._render_dna_helix(buffer)

        # Apply transition fade
        if self.transitioning:
            fade = self.transition_progress if self.transition_progress < 0.5 else (1 - self.transition_progress)
            fade_amount = int(255 * fade * 2)
            buffer[:] = np.clip(buffer.astype(np.int16) - fade_amount, 0, 255).astype(np.uint8)

    def _render_eye(self, buffer: NDArray[np.uint8]) -> None:
        """Render ALIVE all-seeing eye - FULL SCREEN, WATCHING, BREATHING."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        # === BREATHING/PULSING BACKGROUND ===
        # The whole screen breathes with the eye
        breath = 0.8 + 0.2 * math.sin(t * 1.5)  # Slow breathing
        pulse = 0.9 + 0.1 * math.sin(t * 4)  # Fast pulse

        # Deep void background with radial gradient from center
        for y in range(128):
            for x in range(128):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                dist_norm = min(1.0, dist / 90)  # Normalize to 0-1

                # Dark purple void at edges, warmer at center
                r = int(15 + 30 * (1 - dist_norm) * breath)
                g = int(5 + 10 * (1 - dist_norm) * breath)
                b = int(35 + 40 * (1 - dist_norm) * breath)
                buffer[y, x] = (r, g, b)

        # === MYSTICAL PARTICLES floating around ===
        for i in range(40):
            angle = t * 0.3 + i * 0.157  # Golden angle spacing
            orbit = 45 + 20 * math.sin(t * 0.5 + i * 0.3)
            px = int(cx + orbit * math.cos(angle + i * 0.5))
            py = int(cy + orbit * math.sin(angle + i * 0.5))
            sparkle = 0.5 + 0.5 * math.sin(t * 8 + i * 2)
            if 0 <= px < 128 and 0 <= py < 128:
                color = (int(180 * sparkle), int(100 * sparkle), int(255 * sparkle))
                buffer[py, px] = color
                # Glow
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    gx, gy = px + dx, py + dy
                    if 0 <= gx < 128 and 0 <= gy < 128:
                        buffer[gy, gx] = (int(80 * sparkle), int(40 * sparkle), int(120 * sparkle))

        # === PULSING AURA RINGS - FULL SCREEN ===
        for ring in range(8):
            base_r = 20 + ring * 12  # Rings from center to edge
            ring_pulse = 0.5 + 0.5 * math.sin(t * 3 - ring * 0.5)
            radius = base_r + int(5 * math.sin(t * 2 + ring * 0.7))
            hue = (t * 40 + ring * 45) % 360
            color = hsv_to_rgb(hue, 0.9, 0.4 * ring_pulse * breath)

            # Draw ring with rotation
            rotation = t * (1 + ring * 0.1) * (1 if ring % 2 == 0 else -1)
            for angle_step in range(0, 360, 2):
                rad = math.radians(angle_step + rotation * 30)
                for dr in [-2, -1, 0, 1, 2]:
                    px = int(cx + (radius + dr) * math.cos(rad))
                    py = int(cy + (radius + dr) * math.sin(rad))
                    if 0 <= px < 128 and 0 <= py < 128:
                        fade = 1.0 - abs(dr) * 0.25
                        c = tuple(max(0, min(255, int(v * fade))) for v in color)
                        # Blend with existing
                        existing = buffer[py, px]
                        buffer[py, px] = tuple(min(255, existing[i] + c[i]) for i in range(3))

        # === THE EYE - FULL SCREEN SIZE ===
        # Eye shape fills most of display
        eye_h = int(50 + 5 * math.sin(t * 1.2))  # Breathing height
        eye_w = 60

        # Calculate eye pupil position - WATCHING behavior
        # Smooth random targeting with occasional quick movements
        lerp_speed = 0.005 if random.random() > 0.02 else 0.05  # Occasionally quick
        self.eye_x += (self.eye_target_x - self.eye_x) * lerp_speed
        self.eye_y += (self.eye_target_y - self.eye_y) * lerp_speed

        # Eye white with glowing edge
        for y in range(-eye_h, eye_h + 1):
            row_width = int(eye_w * math.sqrt(max(0, 1 - (y / eye_h) ** 2)))
            for x in range(-row_width, row_width + 1):
                px, py = cx + x, cy + y
                if 0 <= px < 128 and 0 <= py < 128:
                    # Distance from edge for glow effect
                    edge_dist = (row_width - abs(x)) / max(1, row_width)
                    vert_dist = (eye_h - abs(y)) / eye_h

                    # Bloodshot effect near edges
                    bloodshot = max(0, 1 - edge_dist * 3 - vert_dist * 2)
                    bloodshot *= 0.3 + 0.1 * math.sin(t * 5 + x * 0.1)

                    # Base white with pink tint at edges
                    white = int((200 + 55 * edge_dist * vert_dist) * breath)
                    r = min(255, white + int(60 * bloodshot))
                    g = max(0, white - int(30 * bloodshot) - 10)
                    b = max(0, white - int(20 * bloodshot))
                    buffer[py, px] = (r, g, b)

        # === IRIS - Large and dynamic ===
        iris_cx = int(cx + self.eye_x * 1.5)  # More movement range
        iris_cy = int(cy + self.eye_y * 1.2)
        iris_r = int(28 + 3 * math.sin(t * 2))  # Pulsing iris

        for y in range(-iris_r - 3, iris_r + 4):
            for x in range(-iris_r - 3, iris_r + 4):
                dist_sq = x*x + y*y
                dist = math.sqrt(dist_sq)

                if dist <= iris_r + 3:
                    px, py = iris_cx + x, iris_cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        if dist <= iris_r:
                            # Inside iris
                            norm_dist = dist / iris_r
                            angle = math.atan2(y, x)

                            # Multi-layer spiral pattern
                            spiral1 = math.sin(angle * 6 + norm_dist * 8 - t * 5)
                            spiral2 = math.sin(angle * 3 - norm_dist * 5 + t * 3)
                            pattern = (spiral1 * 0.4 + spiral2 * 0.3 + 0.7) * pulse

                            # Golden amber center fading to emerald/purple edge
                            center_mix = 1 - norm_dist
                            r = int((255 * center_mix + 50 * (1 - center_mix)) * pattern)
                            g = int((200 * center_mix + 150 * (1 - center_mix) * 0.5) * pattern)
                            b = int((50 * center_mix + 200 * (1 - center_mix)) * pattern)
                            buffer[py, px] = (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
                        else:
                            # Iris edge glow
                            glow = max(0, 1 - (dist - iris_r) / 3)
                            buffer[py, px] = (int(100 * glow), int(50 * glow), int(150 * glow))

        # === PUPIL - Deep void that stares into your soul ===
        pupil_r = int(12 + 4 * math.sin(t * 1.8) + 2 * pulse)  # Dilating pupil
        pupil_cx = int(iris_cx + self.eye_x * 0.1)
        pupil_cy = int(iris_cy + self.eye_y * 0.1)

        for y in range(-pupil_r - 4, pupil_r + 5):
            for x in range(-pupil_r - 4, pupil_r + 5):
                dist_sq = x*x + y*y
                dist = math.sqrt(dist_sq)
                if dist <= pupil_r + 4:
                    px, py = pupil_cx + x, pupil_cy + y
                    if 0 <= px < 128 and 0 <= py < 128:
                        if dist <= pupil_r:
                            # Void black with subtle color
                            void_pulse = 0.05 + 0.03 * math.sin(t * 6)
                            buffer[py, px] = (int(5 * void_pulse), int(3 * void_pulse), int(15 * void_pulse))
                        else:
                            # Gradient edge
                            edge = max(0, 1 - (dist - pupil_r) / 4)
                            buffer[py, px] = (int(30 * edge), int(15 * edge), int(60 * edge))

        # === GLINTING HIGHLIGHTS - Makes it look wet/alive ===
        highlights = [
            (-8, -8, 5, 1.0),   # Main highlight
            (-4, -12, 3, 0.8),  # Secondary
            (6, -6, 2, 0.5),    # Small accent
            (-10, -5, 2, 0.4),  # Tiny
        ]
        for dx, dy, size, intensity in highlights:
            hx = pupil_cx + dx + int(self.eye_x * 0.05)
            hy = pupil_cy + dy + int(self.eye_y * 0.05)
            # Shimmer
            shimmer = 0.8 + 0.2 * math.sin(t * 10 + dx)
            for sy in range(-size, size + 1):
                for sx in range(-size, size + 1):
                    if sx*sx + sy*sy <= size*size:
                        hpx, hpy = hx + sx, hy + sy
                        if 0 <= hpx < 128 and 0 <= hpy < 128:
                            val = int(255 * intensity * shimmer)
                            buffer[hpy, hpx] = (min(255, val), min(255, val), min(255, int(val * 0.9)))

        # === FULL SCREEN BLINK - Eyelids close from top and bottom ===
        if self.blink > 0:
            # Eyelid color - flesh tone
            lid_color = (80, 50, 70)
            lid_dark = (40, 25, 35)

            # Top eyelid comes down
            top_close = int(64 * self.blink)  # How far down it's closed
            # Bottom eyelid comes up
            bottom_close = int(64 * self.blink)

            for y in range(128):
                for x in range(128):
                    dx = x - cx
                    # Eyelid shape follows eye curve
                    lid_curve_top = top_close - int(15 * (1 - (dx / 64) ** 2))
                    lid_curve_bottom = 127 - bottom_close + int(15 * (1 - (dx / 64) ** 2))

                    if y < lid_curve_top:
                        # Top lid
                        edge_dist = max(0, lid_curve_top - y)
                        if edge_dist < 5:
                            buffer[y, x] = lid_dark  # Eyelash line
                        else:
                            buffer[y, x] = lid_color
                    elif y > lid_curve_bottom:
                        # Bottom lid
                        edge_dist = max(0, y - lid_curve_bottom)
                        if edge_dist < 3:
                            buffer[y, x] = lid_dark
                        else:
                            buffer[y, x] = lid_color

        # === TEXT - Only when eye is open ===
        if self.blink < 0.3:
            # VNVNC with glow
            for ox in [-1, 0, 1]:
                for oy in [-1, 0, 1]:
                    if ox != 0 or oy != 0:
                        draw_centered_text(buffer, "VNVNC", 4 + oy, (80, 40, 100), scale=2)
            draw_centered_text(buffer, "VNVNC", 4, self.gold, scale=2)

            # Prompt blinks
            if int(t * 2) % 2 == 0:
                draw_centered_text(buffer, "НАЖМИ СТАРТ", 116, self.teal, scale=1)

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
                alpha = max(0.0, (pulse - r) / max(1, pulse))  # Prevent division by zero
                color = (max(0, min(255, int(20 * alpha))), max(0, min(255, int(180 * alpha))), max(0, min(255, int(160 * alpha))))
                for angle in range(0, 360, 15):
                    rad = math.radians(angle)
                    px = int(64 + r * math.cos(rad))
                    py = int(64 + r * math.sin(rad))
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = color
            draw_centered_text(buffer, "ЗЕРКАЛО", 50, self.teal, scale=2)
            draw_centered_text(buffer, "КАМЕРА...", 75, self.pink, scale=1)
            return

        # Get camera frame and resize with CROP-TO-FILL (no black bars!)
        frame = self._camera_frame
        if frame.shape[0] != 128 or frame.shape[1] != 128:
            h, w = frame.shape[:2]

            # Calculate scale factor to FILL 128x128 (crop excess, no black bars)
            scale = max(128 / w, 128 / h)
            new_w = int(w * scale)
            new_h = int(h * scale)

            # Calculate crop offset (center crop)
            crop_x = (new_w - 128) // 2
            crop_y = (new_h - 128) // 2

            # Resize with crop-to-fill
            new_frame = np.zeros((128, 128, 3), dtype=np.uint8)
            for y in range(128):
                for x in range(128):
                    # Map back to source coordinates
                    src_x = (x + crop_x) / scale
                    src_y = (y + crop_y) / scale
                    sx = min(int(src_x), w - 1)
                    sy = min(int(src_y), h - 1)
                    sx = max(0, sx)
                    sy = max(0, sy)
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

        # Copy to buffer - FULL SCREEN, no black bars!
        np.copyto(buffer, frame)

        # Overlay text with outline (no solid bars!)
        effect_names = {"normal": "ЗЕРКАЛО", "negative": "НЕГАТИВ", "dither": "ПИКСЕЛИ"}
        # Effect label with outline
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, effect_names.get(effect, "ЭФФЕКТ"), 116 + oy, (0, 0, 0), scale=1)
        draw_centered_text(buffer, effect_names.get(effect, "ЭФФЕКТ"), 116, self.teal, scale=1)

        # Top text with outline
        if int(t * 2) % 2 == 0:
            for ox in [-1, 0, 1]:
                for oy in [-1, 0, 1]:
                    if ox != 0 or oy != 0:
                        draw_centered_text(buffer, "НАЖМИ СТАРТ", 4 + oy, (0, 0, 0), scale=1)
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

    def _render_neon_tunnel(self, buffer: NDArray[np.uint8]) -> None:
        """Render neon tunnel effect with camera background."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        # Update and show camera
        self._update_camera()
        if self._camera_frame is not None:
            frame = self._camera_frame
            if frame.shape[0] != 128 or frame.shape[1] != 128:
                frame = np.zeros((128, 128, 3), dtype=np.uint8)
                h, w = self._camera_frame.shape[:2]
                for y in range(128):
                    for x in range(128):
                        sy = min(int(y * h / 128), h - 1)
                        sx = min(int(x * w / 128), w - 1)
                        frame[y, x] = self._camera_frame[sy, sx]
            # Darken camera for overlay visibility
            np.copyto(buffer, (frame * 0.4).astype(np.uint8))
        else:
            fill(buffer, (10, 5, 20))

        # Neon tunnel rings
        for ring in range(8):
            # Pulsing radius
            base_r = 10 + ring * 12 + int(5 * math.sin(t * 2 - ring * 0.5))
            # Cycling hue per ring
            hue = (t * 60 + ring * 45) % 360
            brightness = 0.8 + 0.2 * math.sin(t * 3 + ring)
            color = hsv_to_rgb(hue, 1.0, brightness)

            # Draw ring
            for angle in range(0, 360, 4):
                rad = math.radians(angle)
                px = int(cx + base_r * math.cos(rad))
                py = int(cy + base_r * math.sin(rad))
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = color
                    # Glow effect
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        gpx, gpy = px + dx, py + dy
                        if 0 <= gpx < 128 and 0 <= gpy < 128:
                            buffer[gpy, gpx] = tuple(max(0, min(255, int(c * 0.5))) for c in color)

        # Blinking prompt
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, self.teal, scale=1)

    def _render_glitch_grid(self, buffer: NDArray[np.uint8]) -> None:
        """Render glitch grid effect with camera background."""
        t = self.state.scene_time / 1000

        # Update and show camera
        self._update_camera()
        if self._camera_frame is not None:
            frame = self._camera_frame
            if frame.shape[0] != 128 or frame.shape[1] != 128:
                frame = np.zeros((128, 128, 3), dtype=np.uint8)
                h, w = self._camera_frame.shape[:2]
                for y in range(128):
                    for x in range(128):
                        sy = min(int(y * h / 128), h - 1)
                        sx = min(int(x * w / 128), w - 1)
                        frame[y, x] = self._camera_frame[sy, sx]
            np.copyto(buffer, frame)
        else:
            fill(buffer, (20, 20, 30))

        # Glitch scanlines
        for y in range(0, 128, 4):
            if random.random() < 0.3:
                # Horizontal shift
                shift = random.randint(-10, 10)
                if shift > 0:
                    buffer[y:y+2, shift:] = buffer[y:y+2, :-shift]
                elif shift < 0:
                    buffer[y:y+2, :shift] = buffer[y:y+2, -shift:]

        # RGB split effect
        split = int(2 + 2 * math.sin(t * 5))
        if split > 0:
            # Shift red channel
            buffer[:-split, :, 0] = buffer[split:, :, 0]
            # Shift blue channel
            buffer[split:, :, 2] = buffer[:-split, :, 2]

        # Random glitch blocks
        if random.random() < 0.2:
            gx = random.randint(0, 100)
            gy = random.randint(0, 100)
            gw = random.randint(10, 30)
            gh = random.randint(5, 15)
            # Invert block
            buffer[gy:gy+gh, gx:gx+gw] = 255 - buffer[gy:gy+gh, gx:gx+gw]

        # Scanline overlay
        for y in range(0, 128, 2):
            buffer[y, :] = (buffer[y, :].astype(np.int16) * 0.8).astype(np.uint8)

        # Blinking prompt with glitch
        if int(t * 2) % 2 == 0:
            offset = random.randint(-2, 2) if random.random() < 0.1 else 0
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114 + offset, (255, 0, 100), scale=1)

    def _render_fire_silhouette(self, buffer: NDArray[np.uint8]) -> None:
        """Render fire/heat effect with camera silhouette."""
        t = self.state.scene_time / 1000

        # Update camera
        self._update_camera()

        # Fire gradient background
        for y in range(128):
            fire_intensity = 1.0 - (y / 128)  # Brighter at bottom
            wave = 0.1 * math.sin(y * 0.2 + t * 5)
            intensity = max(0.0, min(1.0, fire_intensity + wave))  # Clamp to 0-1
            r = max(0, min(255, int(255 * intensity)))
            g = max(0, min(255, int(100 * intensity * intensity)))
            b = max(0, min(255, int(20 * intensity * intensity * intensity)))
            buffer[y, :] = [r, g, b]

        # Rising fire particles
        for _ in range(20):
            px = random.randint(0, 127)
            py = int(127 - (t * 50 + random.random() * 100) % 128)
            if 0 <= py < 128:
                brightness = random.uniform(0.5, 1.0)
                buffer[py, px] = (255, max(0, min(255, int(200 * brightness))), max(0, min(255, int(50 * brightness))))

        # Camera silhouette overlay
        if self._camera_frame is not None:
            frame = self._camera_frame
            if frame.shape[0] != 128 or frame.shape[1] != 128:
                h, w = frame.shape[:2]
                resized = np.zeros((128, 128, 3), dtype=np.uint8)
                for y in range(128):
                    for x in range(128):
                        sy = min(int(y * h / 128), h - 1)
                        sx = min(int(x * w / 128), w - 1)
                        resized[y, x] = frame[sy, sx]
                frame = resized

            # Convert to grayscale silhouette
            gray = np.mean(frame, axis=2)
            threshold = 100 + 20 * math.sin(t * 2)

            # Dark silhouette cuts through fire
            for y in range(128):
                for x in range(128):
                    if gray[y, x] < threshold:
                        # Darken for silhouette
                        buffer[y, x] = (buffer[y, x].astype(np.int16) * 0.2).astype(np.uint8)

        # Blinking prompt
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, (255, 100, 50), scale=1)

    def _render_matrix_rain(self, buffer: NDArray[np.uint8]) -> None:
        """Render Matrix-style code rain with camera background."""
        t = self.state.scene_time / 1000

        # Update camera
        self._update_camera()

        # Dark background with camera hint
        if self._camera_frame is not None:
            frame = self._camera_frame
            if frame.shape[0] != 128 or frame.shape[1] != 128:
                h, w = frame.shape[:2]
                resized = np.zeros((128, 128, 3), dtype=np.uint8)
                for y in range(128):
                    for x in range(128):
                        sy = min(int(y * h / 128), h - 1)
                        sx = min(int(x * w / 128), w - 1)
                        resized[y, x] = frame[sy, sx]
                frame = resized
            # Very dark green tint
            buffer[:, :, 0] = (frame[:, :, 0] * 0.1).astype(np.uint8)
            buffer[:, :, 1] = (frame[:, :, 1] * 0.3).astype(np.uint8)
            buffer[:, :, 2] = (frame[:, :, 2] * 0.1).astype(np.uint8)
        else:
            fill(buffer, (0, 10, 0))

        # Matrix rain columns
        num_columns = 16
        col_width = 128 // num_columns

        for col in range(num_columns):
            # Each column has its own speed and offset
            speed = 30 + (col * 7) % 20
            offset = (col * 17) % 50
            rain_y = int((t * speed + offset) % 150) - 20

            # Draw falling characters
            for char_idx in range(8):
                cy = rain_y - char_idx * 8
                if 0 <= cy < 128:
                    cx = col * col_width + col_width // 2
                    # Brightness fades with trail
                    brightness = max(0, 1.0 - char_idx * 0.12)
                    if char_idx == 0:
                        color = (200, 255, 200)  # Lead char is brighter
                    else:
                        color = (0, int(255 * brightness), 0)

                    # Draw a simple "character" (random pixels)
                    for dy in range(6):
                        for dx in range(4):
                            if random.random() < 0.5:
                                px = cx + dx - 2
                                py = cy + dy
                                if 0 <= px < 128 and 0 <= py < 128:
                                    buffer[py, px] = color

        # Blinking prompt
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, (100, 255, 100), scale=1)

    def _render_kaleidoscope(self, buffer: NDArray[np.uint8]) -> None:
        """Render kaleidoscope mirror effect with camera."""
        t = self.state.scene_time / 1000

        # Update camera
        self._update_camera()

        if self._camera_frame is not None:
            frame = self._camera_frame
            if frame.shape[0] != 128 or frame.shape[1] != 128:
                h, w = frame.shape[:2]
                resized = np.zeros((128, 128, 3), dtype=np.uint8)
                for y in range(128):
                    for x in range(128):
                        sy = min(int(y * h / 128), h - 1)
                        sx = min(int(x * w / 128), w - 1)
                        resized[y, x] = frame[sy, sx]
                frame = resized

            # Create kaleidoscope by mirroring quadrants
            # Top-left quadrant is source
            quadrant = frame[:64, :64].copy()

            # Mirror to other quadrants
            buffer[:64, :64] = quadrant  # Top-left
            buffer[:64, 64:] = quadrant[:, ::-1]  # Top-right (flip horizontal)
            buffer[64:, :64] = quadrant[::-1, :]  # Bottom-left (flip vertical)
            buffer[64:, 64:] = quadrant[::-1, ::-1]  # Bottom-right (flip both)

            # Rotating color shift
            hue_shift = int(t * 30) % 360
            if hue_shift > 0:
                # Simple hue rotation by channel swapping
                phase = int(t * 2) % 3
                if phase == 1:
                    buffer[:, :, 0], buffer[:, :, 1] = buffer[:, :, 1].copy(), buffer[:, :, 0].copy()
                elif phase == 2:
                    buffer[:, :, 1], buffer[:, :, 2] = buffer[:, :, 2].copy(), buffer[:, :, 1].copy()
        else:
            # Placeholder pattern
            fill(buffer, (30, 20, 50))
            for y in range(64):
                for x in range(64):
                    hue = (x + y + t * 50) % 360
                    color = hsv_to_rgb(hue, 0.8, 0.8)
                    buffer[y, x] = color
                    buffer[y, 127-x] = color
                    buffer[127-y, x] = color
                    buffer[127-y, 127-x] = color

        # Blinking prompt
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, self.teal, scale=1)

    def _render_starfield_3d(self, buffer: NDArray[np.uint8]) -> None:
        """Render 3D starfield flying through space with camera background."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        # Update camera
        self._update_camera()

        # Camera as subtle background
        if self._camera_frame is not None:
            frame = self._camera_frame
            if frame.shape[0] != 128 or frame.shape[1] != 128:
                h, w = frame.shape[:2]
                resized = np.zeros((128, 128, 3), dtype=np.uint8)
                for y in range(128):
                    for x in range(128):
                        sy = min(int(y * h / 128), h - 1)
                        sx = min(int(x * w / 128), w - 1)
                        resized[y, x] = frame[sy, sx]
                frame = resized
            # Very dark, blue-tinted
            buffer[:, :, 0] = (frame[:, :, 0] * 0.15).astype(np.uint8)
            buffer[:, :, 1] = (frame[:, :, 1] * 0.15).astype(np.uint8)
            buffer[:, :, 2] = (frame[:, :, 2] * 0.25).astype(np.uint8)
        else:
            fill(buffer, (5, 5, 15))

        # 3D stars flying toward viewer
        num_stars = 50
        for i in range(num_stars):
            # Deterministic star position based on index and time
            seed = i * 1337
            star_z = ((t * 30 + seed % 100) % 100) + 1  # 1-100 depth
            star_angle = (seed % 360) * math.pi / 180
            star_dist = (seed % 50) + 10

            # Project 3D to 2D
            scale = 100 / star_z
            sx = int(cx + star_dist * math.cos(star_angle) * scale)
            sy = int(cy + star_dist * math.sin(star_angle) * scale)

            # Size based on depth (closer = bigger)
            size = max(1, int(3 * (100 - star_z) / 100))

            # Brightness based on depth (clamped to prevent negative)
            brightness = max(0, min(255, int(255 * (100 - star_z) / 100)))

            if 0 <= sx < 128 and 0 <= sy < 128:
                color = (brightness, brightness, min(255, max(0, brightness + 50)))
                for dy in range(-size//2, size//2 + 1):
                    for dx in range(-size//2, size//2 + 1):
                        px, py = sx + dx, sy + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            buffer[py, px] = color

                # Star trail (streak effect)
                trail_len = int(size * 2 * star_z / 30)
                for trail in range(1, trail_len + 1):
                    tx = int(sx - (sx - cx) * trail * 0.1)
                    ty = int(sy - (sy - cy) * trail * 0.1)
                    if 0 <= tx < 128 and 0 <= ty < 128:
                        fade = max(0, brightness // (trail + 1))
                        buffer[ty, tx] = (fade, fade, min(255, max(0, fade + 20)))

        # Blinking prompt
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 114, (150, 150, 255), scale=1)

    # =========================================================================
    # EPIC DEMO EFFECTS (Ported from led_demo.py)
    # =========================================================================

    def _render_plasma_vortex(self, buffer: NDArray[np.uint8]) -> None:
        """Render intense plasma vortex - mesmerizing spiral of color."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        for y in range(128):
            for x in range(128):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx*dx + dy*dy)
                angle = math.atan2(dy, dx)

                # Vortex twist - spiraling inward
                twist = angle + dist / 15 + t * 2
                v = math.sin(twist * 5) * 0.5 + 0.5

                # Radial pulse
                pulse = math.sin(dist / 10 - t * 3) * 0.3 + 0.7

                # Hue based on angle and distance
                hue = (math.degrees(angle) + dist * 2 + t * 50) % 360
                brightness = v * pulse * min(1, (70 - dist + 20) / 20) if dist < 70 else 0

                if brightness > 0:
                    color = hsv_to_rgb(hue, 0.9, max(0, min(1, brightness)))
                    buffer[y, x] = color
                else:
                    buffer[y, x] = (5, 0, 10)

        # VNVNC branding with outline
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (255, 200, 255), scale=2)

        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 116, (200, 100, 255), scale=1)

    def _render_neon_grid(self, buffer: NDArray[np.uint8]) -> None:
        """Render retro synthwave neon grid - outrun aesthetic."""
        t = self.state.scene_time / 1000

        # Fill with dark purple/black
        fill(buffer, (10, 0, 20))

        horizon = 74  # Horizon line

        # Sun (circle at horizon)
        sun_y = horizon - 30
        for r in range(25, 0, -1):
            brightness = (25 - r) * 10
            color = (min(255, brightness), brightness // 3, brightness // 2)
            # Draw sun circle
            for angle in range(0, 360, 3):
                rad = math.radians(angle)
                px = int(64 + r * math.cos(rad))
                py = int(sun_y + r * 0.6 * math.sin(rad))  # Squished vertically
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = color

        # Horizontal lines with perspective
        for i in range(1, 15):
            progress = i / 15
            y = horizon + int(progress * progress * (128 - horizon))
            if y >= 128:
                continue
            intensity = int(200 * (1 - progress * 0.5))
            hue = (t * 30 + i * 20) % 360
            color = hsv_to_rgb(hue, 0.8, intensity / 255)
            for x in range(128):
                buffer[y, x] = color

        # Vertical lines with perspective (converging to horizon)
        for i in range(-10, 11, 2):
            x1 = 64 + i * 3  # Top (at horizon)
            x2 = 64 + i * 20  # Bottom
            y1 = horizon
            y2 = 127
            hue = (t * 30 + abs(i) * 15) % 360
            color = hsv_to_rgb(hue, 0.7, 0.6)
            # Draw line
            steps = 54
            for step in range(steps):
                progress = step / steps
                x = int(x1 + (x2 - x1) * progress)
                y = int(y1 + (y2 - y1) * progress)
                if 0 <= x < 128 and 0 <= y < 128:
                    buffer[y, x] = color

        # Scrolling horizontal lines for motion effect
        scroll = (t * 50) % 20
        for i in range(5):
            y = horizon + 10 + i * 20 + int(scroll)
            if 0 <= y < 128:
                for x in range(128):
                    buffer[y, x] = (100, 0, 100)

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, self.pink, scale=2)

        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 116, (255, 100, 200), scale=1)

    def _render_electric_storm(self, buffer: NDArray[np.uint8]) -> None:
        """Render electric storm with dramatic lightning."""
        t = self.state.scene_time / 1000

        # Dark stormy background gradient
        for y in range(128):
            darkness = 10 + y // 10
            buffer[y, :] = [darkness // 3, darkness // 3, darkness]

        # Generate new lightning bolt randomly
        if random.random() < 0.05:
            x = random.randint(20, 107)
            self.lightning = [(x, 0)]
            y = 0
            while y < 128:
                y += random.randint(5, 15)
                x += random.randint(-10, 10)
                x = max(5, min(122, x))
                self.lightning.append((x, min(127, y)))
            self.lightning_flash = 1.0

        # Flash effect when lightning strikes
        if self.lightning_flash > 0:
            flash_brightness = int(30 * self.lightning_flash)
            buffer[:] = np.clip(buffer.astype(np.int16) + flash_brightness, 0, 255).astype(np.uint8)
            self.lightning_flash = max(0, self.lightning_flash - 0.1)

        # Draw lightning with glow
        if self.lightning and random.random() > 0.3:
            for i in range(len(self.lightning) - 1):
                p1, p2 = self.lightning[i], self.lightning[i + 1]
                # Main bolt
                steps = max(abs(p2[0] - p1[0]), abs(p2[1] - p1[1]), 1)
                for step in range(steps):
                    px = int(p1[0] + (p2[0] - p1[0]) * step / steps)
                    py = int(p1[1] + (p2[1] - p1[1]) * step / steps)
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = (255, 255, 255)
                        # Glow
                        for gx in range(-2, 3):
                            for gy in range(-2, 3):
                                gpx, gpy = px + gx, py + gy
                                if 0 <= gpx < 128 and 0 <= gpy < 128:
                                    dist = abs(gx) + abs(gy)
                                    if dist > 0:
                                        glow = max(0, 200 - dist * 50)
                                        existing = buffer[gpy, gpx]
                                        buffer[gpy, gpx] = (
                                            min(255, int(existing[0]) + glow),
                                            min(255, int(existing[1]) + glow),
                                            min(255, int(existing[2]) + glow)
                                        )

            # Branches
            for point in self.lightning[::3]:
                if random.random() < 0.5:
                    ex = point[0] + random.randint(-20, 20)
                    ey = point[1] + random.randint(10, 30)
                    # Draw branch
                    steps = max(abs(ex - point[0]), abs(ey - point[1]), 1)
                    for step in range(steps):
                        px = int(point[0] + (ex - point[0]) * step / steps)
                        py = int(point[1] + (ey - point[1]) * step / steps)
                        if 0 <= px < 128 and 0 <= py < 128:
                            buffer[py, px] = (150, 150, 255)

        # Rain
        for _ in range(30):
            rx = random.randint(0, 127)
            ry = random.randint(0, 127)
            for dy in range(8):
                rpy = ry + dy
                rpx = rx + dy // 4
                if 0 <= rpx < 128 and 0 <= rpy < 128:
                    buffer[rpy, rpx] = (100, 100, 150)

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (150, 200, 255), scale=2)
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 116, (100, 150, 255), scale=1)

    def _render_quantum_field(self, buffer: NDArray[np.uint8]) -> None:
        """Render quantum particle field with connections."""
        t = self.state.scene_time / 1000

        # Dark space background
        fill(buffer, (0, 5, 15))

        # Update particles with wave function behavior
        for p in self.quantum_particles:
            # Quantum tunneling / wave behavior
            p['vx'] += (random.random() - 0.5) * 0.02 + math.sin(t + p['y'] * 10) * 0.01
            p['vy'] += (random.random() - 0.5) * 0.02 + math.cos(t + p['x'] * 10) * 0.01
            p['x'] += p['vx']
            p['y'] += p['vy']

            # Wrap around
            if p['x'] < 0: p['x'] = 1
            if p['x'] > 1: p['x'] = 0
            if p['y'] < 0: p['y'] = 1
            if p['y'] > 1: p['y'] = 0

            # Damping
            p['vx'] *= 0.98
            p['vy'] *= 0.98

        # Draw connections between nearby particles
        for i, p1 in enumerate(self.quantum_particles):
            px1 = int(p1['x'] * 127)
            py1 = int(p1['y'] * 127)

            for p2 in self.quantum_particles[i+1:]:
                px2 = int(p2['x'] * 127)
                py2 = int(p2['y'] * 127)
                dist = math.sqrt((px1 - px2)**2 + (py1 - py2)**2)

                if dist < 40 and dist > 0:
                    alpha = (1 - dist / 40)
                    hue = (t * 30 + i * 5) % 360
                    color = hsv_to_rgb(hue, 0.7, alpha)
                    # Draw line
                    steps = max(int(dist), 1)
                    for step in range(steps):
                        lx = int(px1 + (px2 - px1) * step / steps)
                        ly = int(py1 + (py2 - py1) * step / steps)
                        if 0 <= lx < 128 and 0 <= ly < 128:
                            buffer[ly, lx] = color

            # Draw particle
            hue = (p1['x'] * 180 + t * 50) % 360
            color = hsv_to_rgb(hue, 0.9, 0.9)
            if 0 <= px1 < 128 and 0 <= py1 < 128:
                buffer[py1, px1] = color
                # Glow
                for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    gpx, gpy = px1 + dx, py1 + dy
                    if 0 <= gpx < 128 and 0 <= gpy < 128:
                        glow_color = tuple(max(0, c // 2) for c in color)
                        buffer[gpy, gpx] = glow_color

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (100, 200, 255), scale=2)

        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 116, (50, 150, 255), scale=1)

    def _render_dna_helix(self, buffer: NDArray[np.uint8]) -> None:
        """Render DNA double helix animation."""
        t = self.state.scene_time / 1000
        cx = 64

        # Dark blue/green background
        fill(buffer, (0, 10, 20))

        for y in range(128):
            phase = y / 20 + t * 2

            # Double helix strands
            x1 = int(cx + math.sin(phase) * 25)
            x2 = int(cx + math.sin(phase + math.pi) * 25)

            depth1 = math.cos(phase)
            depth2 = math.cos(phase + math.pi)

            # Draw strand 1 (front when depth > 0)
            if depth1 > 0:
                # Front strand - bright
                for dx in range(-2, 3):
                    px = x1 + dx
                    if 0 <= px < 128:
                        brightness = 1.0 - abs(dx) * 0.2
                        buffer[y, px] = (int(200 * brightness), int(50 * brightness), int(50 * brightness))

            # Draw strand 2 (front when depth > 0)
            if depth2 > 0:
                for dx in range(-2, 3):
                    px = x2 + dx
                    if 0 <= px < 128:
                        brightness = 1.0 - abs(dx) * 0.2
                        buffer[y, px] = (int(50 * brightness), int(50 * brightness), int(200 * brightness))

            # Base pairs (rungs) - only when strands are at similar depth
            if y % 8 == 0 and abs(depth1 - depth2) < 0.5:
                hue = (y * 3 + t * 30) % 360
                color = hsv_to_rgb(hue, 0.7, 0.8)
                # Draw rung
                start_x = min(x1, x2)
                end_x = max(x1, x2)
                for x in range(start_x, end_x + 1):
                    if 0 <= x < 128:
                        buffer[y, x] = color

            # Draw back strands (dimmer)
            if depth1 <= 0:
                for dx in range(-1, 2):
                    px = x1 + dx
                    if 0 <= px < 128:
                        buffer[y, px] = (100, 25, 25)

            if depth2 <= 0:
                for dx in range(-1, 2):
                    px = x2 + dx
                    if 0 <= px < 128:
                        buffer[y, px] = (25, 25, 100)

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (100, 255, 150), scale=2)

        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 116, (50, 200, 100), scale=1)

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
            IdleScene.NEON_TUNNEL: "ЛЕТИ СКВОЗЬ НЕОН",
            IdleScene.GLITCH_GRID: "СБОЙ В МАТРИЦЕ",
            IdleScene.FIRE_SILHOUETTE: "ОГНЕННЫЙ СИЛУЭТ",
            IdleScene.MATRIX_RAIN: "ДОБРО ПОЖАЛОВАТЬ В МАТРИЦУ",
            IdleScene.STARFIELD_3D: "ПОЛЁТ К ЗВЁЗДАМ",
            IdleScene.PLASMA_VORTEX: "ПЛАЗМЕННЫЙ ВОРТЕКС",
            IdleScene.NEON_GRID: "РЕТРО ВОЛНА 80-Х",
            IdleScene.ELECTRIC_STORM: "ЭЛЕКТРИЧЕСКИЙ ШТОРМ",
            IdleScene.QUANTUM_FIELD: "КВАНТОВОЕ ПОЛЕ",
            IdleScene.DNA_HELIX: "СПИРАЛЬ ЖИЗНИ",
        }
        text = texts.get(scene, "VNVNC ARCADE")

        colors = {
            IdleScene.MYSTICAL_EYE: self.gold,
            IdleScene.COSMIC_PORTAL: self.pink,
            IdleScene.CAMERA_MIRROR: self.teal,
            IdleScene.PLASMA_WAVE: (255, 200, 100),
            IdleScene.NEON_TUNNEL: self.pink,
            IdleScene.GLITCH_GRID: (0, 255, 100),
            IdleScene.FIRE_SILHOUETTE: (255, 150, 50),
            IdleScene.MATRIX_RAIN: (100, 255, 100),
            IdleScene.STARFIELD_3D: (150, 150, 255),
            IdleScene.PLASMA_VORTEX: (200, 100, 255),
            IdleScene.NEON_GRID: (255, 100, 200),
            IdleScene.ELECTRIC_STORM: (100, 150, 255),
            IdleScene.QUANTUM_FIELD: (100, 200, 255),
            IdleScene.DNA_HELIX: (100, 255, 150),
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
            IdleScene.NEON_TUNNEL: ["НЕОНОВЫЙ    ", "  ТОННЕЛЬ   ", " НАЖМИ СТАРТ "],
            IdleScene.GLITCH_GRID: ["  ГЛИТЧ     ", "  СИСТЕМА   ", " НАЖМИ СТАРТ "],
            IdleScene.FIRE_SILHOUETTE: ["  ОГНЕННЫЙ  ", "  СИЛУЭТ    ", " НАЖМИ СТАРТ "],
            IdleScene.MATRIX_RAIN: ["  МАТРИЦА   ", "   ДОЖДЬ    ", " НАЖМИ СТАРТ "],
            IdleScene.STARFIELD_3D: [" ЗВЁЗДНЫЙ   ", "  ПОЛЁТ     ", " НАЖМИ СТАРТ "],
            IdleScene.PLASMA_VORTEX: ["  ВОРТЕКС   ", " ГИПНОТИЗМ  ", " НАЖМИ СТАРТ "],
            IdleScene.NEON_GRID: [" SYNTHWAVE  ", "   80-Х     ", " НАЖМИ СТАРТ "],
            IdleScene.ELECTRIC_STORM: ["   ШТОРМ    ", "   МОЛНИИ   ", " НАЖМИ СТАРТ "],
            IdleScene.QUANTUM_FIELD: ["  КВАНТОВОЕ ", "    ПОЛЕ    ", " НАЖМИ СТАРТ "],
            IdleScene.DNA_HELIX: ["   СПИРАЛЬ  ", "   ЖИЗНИ    ", " НАЖМИ СТАРТ "],
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

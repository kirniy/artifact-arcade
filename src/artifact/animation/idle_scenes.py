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
from artifact.utils.camera_service import camera_service


# Scene duration in milliseconds
SCENE_DURATION = 12000  # 12 seconds per scene (more dynamic pacing)
TRANSITION_DURATION = 1000  # 1 second smooth fade (increased from 500ms)


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
    # Classic effects
    SNOWFALL = auto()         # Winter snowfall
    FIREPLACE = auto()        # Cozy fireplace
    PLASMA_CLASSIC = auto()   # Classic plasma effect
    TUNNEL = auto()           # Infinite tunnel
    WAVE_PATTERN = auto()     # Wave interference
    AURORA = auto()           # Northern lights
    KALEIDOSCOPE = auto()     # Kaleidoscope pattern
    FIREWORKS = auto()        # Exploding fireworks
    LAVA_LAMP = auto()        # Floating blobs
    GAME_OF_LIFE = auto()     # Conway's game
    RADAR_SWEEP = auto()      # Radar scanning
    SPIRAL_GALAXY = auto()    # Spinning galaxy
    BLACK_HOLE = auto()       # Black hole effect
    HYPERCUBE = auto()        # 4D hypercube
    # Iconic/character scenes
    PACMAN = auto()           # Pac-Man chase
    NYAN_CAT = auto()         # Rainbow cat
    TETRIS = auto()           # Falling blocks
    FOUR_SEASONS = auto()     # Fractal tree with seasons


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

        # Scene transition with crossfade
        self.transition_progress = 0.0
        self.transitioning = False
        self.next_scene_index = 0
        self.prev_scene_buffer = None  # Store previous scene for crossfade

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

        # Snowfall state
        self.snowflakes = [
            {'x': random.randint(0, 127), 'y': random.randint(-128, 0),
             'speed': random.uniform(0.5, 2), 'size': random.randint(1, 3)}
            for _ in range(150)
        ]

        # Fireplace state
        self.flames = [[0] * 70 for _ in range(62)]

        # Matrix rain state
        self.matrix_columns = [
            {'y': random.randint(-128, 0), 'speed': random.uniform(0.5, 2),
             'length': random.randint(5, 15)}
            for _ in range(128)
        ]

        # Starfield 3D state
        self.stars_3d = [
            {'x': random.uniform(-1, 1), 'y': random.uniform(-1, 1), 'z': random.uniform(0.1, 1)}
            for _ in range(100)
        ]

        # Aurora state
        self.aurora_curtains = [
            {'x': random.randint(0, 127), 'phase': random.uniform(0, 6.28)}
            for _ in range(8)
        ]

        # Fireworks state
        self.firework_explosions = []
        self.firework_rockets = []

        # Lava lamp blobs
        self.lava_blobs = [
            {'x': random.uniform(0.2, 0.8), 'y': random.uniform(0.2, 0.8),
             'r': random.uniform(0.08, 0.15), 'vx': 0, 'vy': 0,
             'hue': random.randint(0, 60)}
            for _ in range(6)
        ]

        # Game of Life state
        self.gol_grid = [[1 if random.random() < 0.3 else 0 for _ in range(128)] for _ in range(128)]
        self.gol_colors = [[random.randint(0, 360) for _ in range(128)] for _ in range(128)]
        self.gol_generation = 0

        # Radar sweep state
        self.radar_blips = []

        # Spiral galaxy stars
        self.galaxy_stars = []
        for _ in range(300):
            arm = random.randint(0, 2)
            dist = random.uniform(5, 60)
            spread = random.uniform(-0.3, 0.3)
            base_angle = arm * 2 * math.pi / 3
            self.galaxy_stars.append({
                'dist': dist, 'arm_offset': base_angle, 'spread': spread,
                'brightness': random.uniform(0.3, 1.0), 'hue': random.randint(180, 280)
            })

        # Hypercube vertices (4D tesseract)
        self.hypercube_vertices = []
        for w in [-1, 1]:
            for z in [-1, 1]:
                for y in [-1, 1]:
                    for x in [-1, 1]:
                        self.hypercube_vertices.append([x, y, z, w])
        self.hypercube_edges = []
        for i in range(16):
            for j in range(i + 1, 16):
                diff = sum(abs(self.hypercube_vertices[i][k] - self.hypercube_vertices[j][k]) for k in range(4))
                if diff == 2:
                    self.hypercube_edges.append((i, j))

        # Pac-Man state
        self.pacman_x = -20.0
        self.pacman_pellets = [{'x': i * 12 + 6, 'eaten': False} for i in range(12)]
        self.pacman_power_mode = False
        self.pacman_power_timer = 0

        # Nyan Cat state
        self.nyan_rainbow_trail = []

        # Tetris state
        self.tetris_grid = [[None] * 13 for _ in range(16)]
        self.tetris_piece = None
        self.tetris_piece_x = 0
        self.tetris_piece_y = 0
        self.tetris_fall_timer = 0
        self.tetris_pieces = [
            ([[1, 1, 1, 1]], (0, 255, 255)),
            ([[1, 1], [1, 1]], (255, 255, 0)),
            ([[0, 1, 0], [1, 1, 1]], (128, 0, 128)),
            ([[1, 0, 0], [1, 1, 1]], (255, 165, 0)),
            ([[0, 0, 1], [1, 1, 1]], (0, 0, 255)),
            ([[0, 1, 1], [1, 1, 0]], (0, 255, 0)),
            ([[1, 1, 0], [0, 1, 1]], (255, 0, 0)),
        ]

        # Four Seasons tree state
        self.tree_season = 0  # 0=spring, 1=summer, 2=autumn, 3=winter
        self.tree_season_time = 0.0
        self.tree_particles: List[dict] = []
        self.tree_branch_cache: List[Tuple[float, float, int]] = []

    def update(self, delta_ms: float) -> None:
        """Update animation state."""
        self.state.time += delta_ms
        self.state.scene_time += delta_ms
        self.state.frame += 1

        # Handle transitions with smooth timing
        if self.transitioning:
            self.transition_progress += delta_ms / TRANSITION_DURATION
            if self.transition_progress >= 1.0:
                self.transitioning = False
                self.transition_progress = 0.0
                self.prev_scene_buffer = None  # Clean up crossfade buffer
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
        """Start smooth transition to next scene with crossfade."""
        if target_index != self.scene_index and not self.transitioning:
            self.transitioning = True
            self.transition_progress = 0.0
            self.next_scene_index = target_index
            # Capture current scene for smooth crossfade
            self.prev_scene_buffer = np.zeros((128, 128, 3), dtype=np.uint8)

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
        """Open camera - uses shared camera_service (always running)."""
        # Camera service is already running, just set flag
        self._camera = camera_service.is_running or camera_service.has_camera
        if not self._camera:
            # Try to start if not running
            camera_service.start()
            self._camera = camera_service.is_running

    def _close_camera(self) -> None:
        """Close camera - don't stop shared service, just clear frame."""
        # Don't stop the shared service, just clear our cached frame
        self._camera = None
        self._camera_frame = None

    def _update_camera(self) -> None:
        """Update camera frame from shared camera_service."""
        # Get frame from shared camera service (instant, no waiting)
        frame = camera_service.get_frame(timeout=0)
        if frame is not None:
            self._camera_frame = frame
            self._camera = True  # Mark as active

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
        # Classic effects
        elif scene == IdleScene.SNOWFALL:
            self._render_snowfall(buffer)
        elif scene == IdleScene.FIREPLACE:
            self._render_fireplace(buffer)
        elif scene == IdleScene.PLASMA_CLASSIC:
            self._render_plasma_classic(buffer)
        elif scene == IdleScene.TUNNEL:
            self._render_tunnel(buffer)
        elif scene == IdleScene.WAVE_PATTERN:
            self._render_wave_pattern(buffer)
        elif scene == IdleScene.AURORA:
            self._render_aurora(buffer)
        elif scene == IdleScene.KALEIDOSCOPE:
            self._render_kaleidoscope(buffer)
        elif scene == IdleScene.FIREWORKS:
            self._render_fireworks(buffer)
        elif scene == IdleScene.LAVA_LAMP:
            self._render_lava_lamp(buffer)
        elif scene == IdleScene.GAME_OF_LIFE:
            self._render_game_of_life(buffer)
        elif scene == IdleScene.RADAR_SWEEP:
            self._render_radar_sweep(buffer)
        elif scene == IdleScene.SPIRAL_GALAXY:
            self._render_spiral_galaxy(buffer)
        elif scene == IdleScene.BLACK_HOLE:
            self._render_black_hole(buffer)
        elif scene == IdleScene.HYPERCUBE:
            self._render_hypercube(buffer)
        # Iconic/character scenes
        elif scene == IdleScene.PACMAN:
            self._render_pacman(buffer)
        elif scene == IdleScene.NYAN_CAT:
            self._render_nyan_cat(buffer)
        elif scene == IdleScene.TETRIS:
            self._render_tetris(buffer)
        elif scene == IdleScene.FOUR_SEASONS:
            self._render_four_seasons(buffer)

        # Apply smooth crossfade transition with easing
        if self.transitioning:
            # Ease-in-out cubic for buttery smooth transitions
            t = self.transition_progress
            eased = t * t * (3.0 - 2.0 * t)  # Smoothstep easing

            # During first half: capture old scene, fade it out
            if t < 0.5 and self.prev_scene_buffer is not None:
                # Fade out old scene
                alpha = 1.0 - (eased * 2.0)  # 1.0 -> 0.0
                buffer[:] = np.clip(
                    buffer.astype(np.float32) * alpha,
                    0, 255
                ).astype(np.uint8)
            # During second half: fade in new scene (already rendered)
            elif t >= 0.5:
                # Fade in new scene
                alpha = (eased - 0.5) * 2.0  # 0.0 -> 1.0
                buffer[:] = np.clip(
                    buffer.astype(np.float32) * alpha,
                    0, 255
                ).astype(np.uint8)

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
                        # Blend with existing (convert to int to avoid overflow)
                        existing = buffer[py, px]
                        buffer[py, px] = tuple(min(255, int(existing[i]) + c[i]) for i in range(3))

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
    # CLASSIC DEMO EFFECTS (ported from led_demo.py)
    # =========================================================================

    def _render_snowfall(self, buffer: NDArray[np.uint8]) -> None:
        """Render winter snowfall scene."""
        t = self.state.scene_time / 1000

        # Night sky gradient
        for y in range(128):
            blue = int(20 + y * 0.2)
            buffer[y, :] = (5, 5, blue)

        # Snow ground
        buffer[113:128, :] = (240, 240, 255)

        # Update and draw snowflakes
        for f in self.snowflakes:
            x = int(f['x'] + math.sin(t + f['y'] * 0.1) * 2)
            y = int(f['y'])
            if 0 <= x < 128 and 0 <= y < 128:
                brightness = 200 + f['size'] * 18
                # Draw snowflake with size
                for dx in range(-f['size'] + 1, f['size']):
                    for dy in range(-f['size'] + 1, f['size']):
                        px, py = x + dx, y + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            buffer[py, px] = (brightness, brightness, 255)
            f['y'] += f['speed']
            if f['y'] > 128:
                f['y'] = random.randint(-20, -5)
                f['x'] = random.randint(0, 127)

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (200, 220, 255), scale=2)
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 116, (180, 200, 255), scale=1)

    def _render_fireplace(self, buffer: NDArray[np.uint8]) -> None:
        """Render cozy fireplace scene."""
        # Room background
        fill(buffer, (20, 10, 5))

        # Fireplace frame
        for y in range(50, 128):
            for x in range(20, 108):
                buffer[y, x] = (60, 30, 20)

        # Fire opening
        for y in range(60, 120):
            for x in range(30, 98):
                buffer[y, x] = (10, 5, 0)

        # Mantle
        for y in range(45, 53):
            for x in range(15, 113):
                buffer[y, x] = (80, 40, 25)

        # Generate fire
        for x in range(68):
            self.flames[59][x] = random.randint(200, 255)
            self.flames[58][x] = random.randint(150, 255)

        for y in range(57, 0, -1):
            for x in range(1, 67):
                avg = (self.flames[y + 1][x - 1] + self.flames[y + 1][x] +
                       self.flames[y + 1][x + 1] + self.flames[y][x]) / 4.08
                self.flames[y][x] = max(0, avg - random.random() * 3)

        # Draw fire
        for y in range(60):
            for x in range(68):
                h = int(self.flames[y][x])
                if h > 30:
                    if h > 180:
                        color = (255, 200 + min(55, (h - 180) * 2), min(100, h - 180))
                    elif h > 120:
                        color = (255, min(200, (h - 60) * 2), 0)
                    elif h > 50:
                        color = (min(255, h * 3), min(100, h), 0)
                    else:
                        color = (h * 2, 0, 0)
                    buffer[60 + y, 30 + x] = color

        # Stockings
        colors = [(200, 0, 0), (0, 150, 0), (200, 0, 0)]
        for i, c in enumerate(colors):
            for dy in range(18):
                for dx in range(12):
                    buffer[30 + dy, 25 + i * 35 + dx] = c
            for dx in range(12):
                for dy in range(4):
                    buffer[30 + dy, 25 + i * 35 + dx] = (255, 255, 255)

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (255, 150, 50), scale=2)

    def _render_plasma_classic(self, buffer: NDArray[np.uint8]) -> None:
        """Render classic plasma effect."""
        t = self.state.scene_time / 1000

        for y in range(128):
            for x in range(128):
                v = (math.sin(x / 16 + t) + math.sin(y / 8 + t * 0.5) +
                     math.sin((x + y) / 16 + t * 0.7) +
                     math.sin(math.sqrt(x * x + y * y) / 8 + t * 0.3)) / 4
                color = hsv_to_rgb((v + 1) * 180 + t * 30, 1.0, 0.9)
                buffer[y, x] = color

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (255, 255, 255), scale=2)

    def _render_tunnel(self, buffer: NDArray[np.uint8]) -> None:
        """Render infinite tunnel effect."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        for y in range(128):
            for x in range(128):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx * dx + dy * dy) + 0.1
                angle = math.atan2(dy, dx)
                v = 1.0 / dist * 20 + t * 2
                checker = ((int(angle / math.pi * 8) + int(v)) % 2)
                brightness = (0.3 + 0.7 * checker) * min(1, 30 / dist)
                color = hsv_to_rgb((v * 30 + t * 50) % 360, 0.8, brightness)
                buffer[y, x] = color

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (255, 200, 255), scale=2)

    def _render_wave_pattern(self, buffer: NDArray[np.uint8]) -> None:
        """Render wave interference pattern."""
        t = self.state.scene_time / 1000

        for y in range(128):
            for x in range(128):
                d1 = math.sqrt((x - 30) ** 2 + (y - 30) ** 2)
                d2 = math.sqrt((x - 100) ** 2 + (y - 30) ** 2)
                d3 = math.sqrt((x - 64) ** 2 + (y - 100) ** 2)

                v = (math.sin(d1 / 8 - t * 3) +
                     math.sin(d2 / 10 - t * 2.5) +
                     math.sin(d3 / 12 - t * 2)) / 3

                hue = (v * 60 + t * 20 + x + y) % 360
                brightness = (v + 1) / 2
                buffer[y, x] = hsv_to_rgb(hue, 0.9, brightness)

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (100, 200, 255), scale=2)

    def _render_aurora(self, buffer: NDArray[np.uint8]) -> None:
        """Render northern lights / aurora borealis."""
        t = self.state.scene_time / 1000

        # Dark night sky gradient
        for y in range(128):
            darkness = 5 + int(y / 128 * 15)
            buffer[y, :] = (0, darkness // 4, darkness)

        # Stars
        for i in range(30):
            sx = (i * 73 + int(t * 3)) % 128
            sy = (i * 41) % 64
            twinkle = 150 + int(50 * math.sin(t * 3 + i))
            if 0 <= sx < 128 and 0 <= sy < 128:
                buffer[sy, sx] = (twinkle, twinkle, twinkle)

        # Aurora curtains
        for curtain in self.aurora_curtains:
            for y in range(20, 80):
                wave = math.sin(y / 15 + t * 2 + curtain['phase']) * 15
                wave += math.sin(y / 8 + t * 3) * 5
                x = int(curtain['x'] + wave)

                intensity = 1.0 - abs(y - 50) / 40
                intensity *= 0.5 + 0.5 * math.sin(t + curtain['phase'])

                if intensity > 0 and 0 <= x < 128:
                    hue = 120 + (y - 20) * 1.5 + math.sin(t) * 30
                    color = hsv_to_rgb(hue, 0.8, intensity * 0.8)

                    for gx in range(-2, 3):
                        px = x + gx
                        if 0 <= px < 128:
                            glow = max(0, 1 - abs(gx) / 3)
                            old = buffer[y, px]
                            new = tuple(min(255, int(old[i] + color[i] * glow)) for i in range(3))
                            buffer[y, px] = new

            curtain['x'] += math.sin(t * 0.5 + curtain['phase']) * 0.3

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (100, 255, 150), scale=2)

    def _render_kaleidoscope(self, buffer: NDArray[np.uint8]) -> None:
        """Render kaleidoscope pattern."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        for y in range(128):
            for x in range(128):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx * dx + dy * dy)
                angle = math.atan2(dy, dx)

                # Mirror into 6 segments
                segments = 6
                angle = abs((angle + math.pi) % (2 * math.pi / segments) - math.pi / segments)

                rot_angle = angle + t * 0.5
                pattern = math.sin(dist / 10 + rot_angle * 3 + t)
                pattern += math.sin(dist / 5 - t * 2)
                pattern /= 2

                hue = (dist * 3 + t * 50 + angle * 60) % 360
                brightness = 0.3 + 0.7 * (pattern + 1) / 2
                buffer[y, x] = hsv_to_rgb(hue, 0.9, max(0, brightness))

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (255, 200, 100), scale=2)

    def _render_fireworks(self, buffer: NDArray[np.uint8]) -> None:
        """Render fireworks display."""
        t = self.state.scene_time / 1000

        # Dark sky
        fill(buffer, (5, 5, 20))

        # Launch new rockets
        if random.random() < 0.03 and len(self.firework_rockets) < 3:
            self.firework_rockets.append({
                'x': random.randint(20, 108),
                'y': 128.0,
                'target_y': random.randint(20, 60),
                'speed': random.uniform(2, 4),
                'hue': random.randint(0, 360)
            })

        # Update rockets
        new_rockets = []
        for r in self.firework_rockets:
            r['y'] -= r['speed']
            # Draw rocket trail
            for i in range(5):
                ty = int(r['y'] + i * 3)
                if 0 <= ty < 128 and 0 <= int(r['x']) < 128:
                    brightness = 200 - i * 40
                    buffer[ty, int(r['x'])] = (brightness, brightness // 2, 0)

            if r['y'] <= r['target_y']:
                # Explode!
                particles = []
                for _ in range(50):
                    angle = random.uniform(0, 2 * math.pi)
                    speed = random.uniform(1, 4)
                    particles.append({
                        'x': r['x'], 'y': r['y'],
                        'vx': math.cos(angle) * speed,
                        'vy': math.sin(angle) * speed,
                        'life': random.uniform(30, 60),
                        'hue': r['hue'] + random.randint(-20, 20)
                    })
                self.firework_explosions.append({'particles': particles, 'age': 0})
            else:
                new_rockets.append(r)
        self.firework_rockets = new_rockets

        # Update explosions
        new_explosions = []
        for exp in self.firework_explosions:
            exp['age'] += 1
            for p in exp['particles']:
                p['x'] += p['vx']
                p['y'] += p['vy']
                p['vy'] += 0.08
                p['life'] -= 1

                if p['life'] > 0:
                    px, py = int(p['x']), int(p['y'])
                    if 0 <= px < 128 and 0 <= py < 128:
                        brightness = p['life'] / 60
                        color = hsv_to_rgb(p['hue'] % 360, 0.9, brightness)
                        buffer[py, px] = color

            if exp['age'] < 80:
                new_explosions.append(exp)
        self.firework_explosions = new_explosions

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (255, 200, 100), scale=2)

    def _render_lava_lamp(self, buffer: NDArray[np.uint8]) -> None:
        """Render lava lamp with floating blobs."""
        t = self.state.scene_time / 1000

        # Background gradient
        for y in range(128):
            tt = y / 128
            r = int(40 + tt * 20)
            g = int(10 + tt * 15)
            b = int(60 + tt * 30)
            buffer[y, :] = (r, g, b)

        # Update blobs
        for blob in self.lava_blobs:
            blob['vx'] += (random.random() - 0.5) * 0.002
            blob['vy'] += (random.random() - 0.5) * 0.002 - 0.0003

            if blob['y'] > 0.7:
                blob['vy'] -= 0.001
            if blob['y'] < 0.3:
                blob['vy'] += 0.001

            blob['vx'] *= 0.98
            blob['vy'] *= 0.98
            blob['x'] += blob['vx']
            blob['y'] += blob['vy']

            if blob['x'] < 0.1: blob['x'] = 0.1; blob['vx'] *= -0.5
            if blob['x'] > 0.9: blob['x'] = 0.9; blob['vx'] *= -0.5
            if blob['y'] < 0.1: blob['y'] = 0.1; blob['vy'] *= -0.5
            if blob['y'] > 0.9: blob['y'] = 0.9; blob['vy'] *= -0.5

        # Draw blobs
        for y in range(128):
            for x in range(128):
                total = 0
                avg_hue = 0
                for blob in self.lava_blobs:
                    bx = blob['x'] * 128
                    by = blob['y'] * 128
                    r = blob['r'] * 128
                    dist = math.sqrt((x - bx) ** 2 + (y - by) ** 2)
                    if dist < r * 3:
                        influence = (r * r) / (dist * dist + 0.1)
                        total += influence
                        avg_hue += blob['hue'] * influence

                if total > 0.5:
                    avg_hue /= total
                    brightness = min(1.0, (total - 0.5) * 2)
                    color = hsv_to_rgb((avg_hue + t * 10) % 360, 0.9, 0.5 + brightness * 0.5)
                    buffer[y, x] = color

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (255, 150, 200), scale=2)

    def _render_game_of_life(self, buffer: NDArray[np.uint8]) -> None:
        """Render Conway's Game of Life."""
        t = self.state.scene_time / 1000

        fill(buffer, (10, 10, 20))

        # Update every few frames
        if int(t * 10) % 3 == 0:
            new_grid = [[0] * 128 for _ in range(128)]
            for y in range(128):
                for x in range(128):
                    neighbors = 0
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            if dx == 0 and dy == 0:
                                continue
                            ny, nx = (y + dy) % 128, (x + dx) % 128
                            neighbors += self.gol_grid[ny][nx]

                    if self.gol_grid[y][x]:
                        new_grid[y][x] = 1 if neighbors in (2, 3) else 0
                    else:
                        if neighbors == 3:
                            new_grid[y][x] = 1
                            self.gol_colors[y][x] = (self.gol_colors[y][x] + 30) % 360

            self.gol_grid = new_grid
            self.gol_generation += 1

            if self.gol_generation % 200 == 0:
                self.gol_grid = [[1 if random.random() < 0.3 else 0 for _ in range(128)] for _ in range(128)]

        # Draw cells
        for y in range(128):
            for x in range(128):
                if self.gol_grid[y][x]:
                    color = hsv_to_rgb(self.gol_colors[y][x], 0.8, 0.9)
                    buffer[y, x] = color

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (100, 255, 100), scale=2)

    def _render_radar_sweep(self, buffer: NDArray[np.uint8]) -> None:
        """Render radar/sonar scanning effect."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        fill(buffer, (0, 15, 5))

        # Concentric rings
        for r in range(10, 65, 12):
            for angle in range(0, 360, 2):
                rad = math.radians(angle)
                x = int(cx + r * math.cos(rad))
                y = int(cy + r * math.sin(rad))
                if 0 <= x < 128 and 0 <= y < 128:
                    buffer[y, x] = (0, 50, 20)

        # Crosshairs
        for x in range(128):
            buffer[cy, x] = (0, 60, 30)
        for y in range(128):
            buffer[y, cx] = (0, 60, 30)

        sweep_angle = t * 2

        # Sweep with fade trail
        for i in range(40):
            angle = sweep_angle - i * 0.03
            intensity = 1.0 - i / 40
            for r in range(5, 64):
                x = int(cx + r * math.cos(angle))
                y = int(cy + r * math.sin(angle))
                if 0 <= x < 128 and 0 <= y < 128:
                    brightness = int(100 * intensity * (1 - r / 64))
                    buffer[y, x] = (0, min(255, brightness + 50), brightness // 2)

        # Add blips
        if random.random() < 0.02:
            dist = random.uniform(15, 55)
            angle = random.uniform(0, 2 * math.pi)
            self.radar_blips.append({
                'x': cx + dist * math.cos(angle),
                'y': cy + dist * math.sin(angle),
                'life': 60
            })

        # Draw blips
        new_blips = []
        for blip in self.radar_blips:
            blip['life'] -= 1
            if blip['life'] > 0:
                brightness = blip['life'] / 60
                px, py = int(blip['x']), int(blip['y'])
                if 0 <= px < 128 and 0 <= py < 128:
                    color = (0, int(255 * brightness), int(100 * brightness))
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            npx, npy = px + dx, py + dy
                            if 0 <= npx < 128 and 0 <= npy < 128:
                                buffer[npy, npx] = color
                new_blips.append(blip)
        self.radar_blips = new_blips

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (0, 255, 100), scale=2)

    def _render_spiral_galaxy(self, buffer: NDArray[np.uint8]) -> None:
        """Render spinning spiral galaxy."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        fill(buffer, (0, 0, 10))

        for star in self.galaxy_stars:
            angle = star['arm_offset'] + star['dist'] / 15 + t * (1 - star['dist'] / 80)
            angle += star['spread']

            x = int(cx + star['dist'] * math.cos(angle))
            y = int(cy + star['dist'] * math.sin(angle))

            if 0 <= x < 128 and 0 <= y < 128:
                twinkle = 0.7 + 0.3 * math.sin(t * 5 + star['dist'])
                brightness = star['brightness'] * twinkle

                if star['dist'] < 15:
                    hue = 40
                    sat = 0.5
                else:
                    hue = star['hue']
                    sat = 0.8

                color = hsv_to_rgb(hue, sat, brightness)
                buffer[y, x] = color

        # Bright core
        for r in range(12, 0, -1):
            brightness = (12 - r) / 12
            color = hsv_to_rgb(40, 0.3, brightness)
            for angle in range(0, 360, 3):
                rad = math.radians(angle)
                x = int(cx + r * math.cos(rad))
                y = int(cy + r * math.sin(rad))
                if 0 <= x < 128 and 0 <= y < 128:
                    buffer[y, x] = color

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (200, 150, 255), scale=2)

    def _render_black_hole(self, buffer: NDArray[np.uint8]) -> None:
        """Render black hole effect."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        for y in range(128):
            for x in range(128):
                dx, dy = x - cx, y - cy
                dist = math.sqrt(dx * dx + dy * dy) + 0.1
                angle = math.atan2(dy, dx)

                # Warped space
                warp = 1.0 / (1 + dist / 20)
                warped_angle = angle + t * warp * 3

                # Accretion disk
                disk_brightness = 0
                if 15 < dist < 60:
                    disk_pattern = math.sin(warped_angle * 8 + dist / 5 - t * 4)
                    disk_brightness = (disk_pattern * 0.5 + 0.5) * (1 - abs(dist - 37) / 25)

                # Event horizon darkness
                if dist < 15:
                    darkness = max(0, dist / 15)
                    buffer[y, x] = (int(10 * darkness), int(5 * darkness), int(20 * darkness))
                else:
                    hue = (warped_angle * 60 + t * 30 + dist) % 360
                    brightness = disk_brightness * 0.8
                    if brightness > 0.05:
                        buffer[y, x] = hsv_to_rgb(hue, 0.9, brightness)
                    else:
                        buffer[y, x] = (0, 0, 5)

        # Branding
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        draw_centered_text(buffer, "VNVNC", 4, (150, 100, 255), scale=2)

    def _render_hypercube(self, buffer: NDArray[np.uint8]) -> None:
        """Render 4D hypercube (tesseract) projection."""
        t = self.state.scene_time / 1000
        cx, cy = 64, 64

        fill(buffer, (0, 0, 10))

        # Rotation angles in 4D
        angles = [t * 0.5, t * 0.3, t * 0.4, t * 0.6]

        def rotate4d(vertex, angles):
            x, y, z, w = vertex
            # XY rotation
            a = angles[0]
            x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
            # XZ rotation
            a = angles[1]
            x, z = x * math.cos(a) - z * math.sin(a), x * math.sin(a) + z * math.cos(a)
            # XW rotation
            a = angles[2]
            x, w = x * math.cos(a) - w * math.sin(a), x * math.sin(a) + w * math.cos(a)
            # YZ rotation
            a = angles[3]
            y, z = y * math.cos(a) - z * math.sin(a), y * math.sin(a) + z * math.cos(a)
            return [x, y, z, w]

        def project4dto2d(vertex):
            x, y, z, w = vertex
            distance = 3
            factor3d = distance / (distance - w)
            x3d, y3d, z3d = x * factor3d, y * factor3d, z * factor3d
            factor2d = distance / (distance - z3d)
            return x3d * factor2d, y3d * factor2d

        projected = []
        for v in self.hypercube_vertices:
            rotated = rotate4d(v, angles)
            px, py = project4dto2d(rotated)
            projected.append((int(cx + px * 30), int(cy + py * 30), rotated[3]))

        # Draw edges
        for i, j in self.hypercube_edges:
            hue = (t * 30 + (projected[i][2] + projected[j][2]) * 50) % 360
            depth = (projected[i][2] + projected[j][2] + 2) / 4
            brightness = min(1.0, max(0.0, 0.3 + depth * 0.7))
            color = hsv_to_rgb(hue, 0.8, brightness)

            # Draw line
            x1, y1 = projected[i][0], projected[i][1]
            x2, y2 = projected[j][0], projected[j][1]
            steps = max(abs(x2 - x1), abs(y2 - y1), 1)
            for step in range(steps + 1):
                lx = int(x1 + (x2 - x1) * step / steps)
                ly = int(y1 + (y2 - y1) * step / steps)
                if 0 <= lx < 128 and 0 <= ly < 128:
                    buffer[ly, lx] = color

        # Draw vertices
        for px, py, w in projected:
            if 0 <= px < 128 and 0 <= py < 128:
                brightness = min(1.0, max(0.0, 0.5 + (w + 1) / 4))
                color = hsv_to_rgb((t * 50) % 360, 0.9, brightness)
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        npx, npy = px + dx, py + dy
                        if 0 <= npx < 128 and 0 <= npy < 128:
                            buffer[npy, npx] = color

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (100, 200, 255), scale=2)

    # =========================================================================
    # ICONIC/CHARACTER SCENES
    # =========================================================================

    def _render_pacman(self, buffer: NDArray[np.uint8]) -> None:
        """Render Pac-Man chase scene."""
        t = self.state.scene_time / 1000

        # Maze background
        fill(buffer, (0, 0, 20))

        # Walls
        wall_color = (33, 33, 255)
        for x in range(128):
            buffer[20:24, x] = wall_color
            buffer[104:108, x] = wall_color
        for y in range(20, 108):
            buffer[y, 0:4] = wall_color
            buffer[y, 124:128] = wall_color
        # Middle obstacles
        for dy in range(20):
            for dx in range(25):
                buffer[45 + dy, 30 + dx] = wall_color
                buffer[45 + dy, 73 + dx] = wall_color
                buffer[85 + dy, 30 + dx] = wall_color
                buffer[85 + dy, 73 + dx] = wall_color

        # Pellets
        pellet_y = 64
        for pellet in self.pacman_pellets:
            if not pellet['eaten']:
                px = int(pellet['x'])
                if pellet['x'] % 48 < 12:
                    size = 4
                else:
                    size = 2
                if 0 <= px < 128:
                    for dy in range(-size, size + 1):
                        for dx in range(-size, size + 1):
                            if dx * dx + dy * dy <= size * size:
                                npx, npy = px + dx, pellet_y + dy
                                if 0 <= npx < 128 and 0 <= npy < 128:
                                    buffer[npy, npx] = (255, 184, 174)

        # Move Pac-Man
        self.pacman_x += 1.5
        if self.pacman_x > 148:
            self.pacman_x = -30
            for pellet in self.pacman_pellets:
                pellet['eaten'] = False

        # Eat pellets
        for pellet in self.pacman_pellets:
            if not pellet['eaten'] and abs(pellet['x'] - self.pacman_x) < 8:
                pellet['eaten'] = True
                if pellet['x'] % 48 < 12:
                    self.pacman_power_mode = True
                    self.pacman_power_timer = 60

        if self.pacman_power_timer > 0:
            self.pacman_power_timer -= 1
        else:
            self.pacman_power_mode = False

        # Draw Pac-Man
        pac_x = int(self.pacman_x)
        mouth_open = int(t * 20) % 2
        if 0 <= pac_x < 128:
            # Yellow circle
            for dy in range(-10, 11):
                for dx in range(-10, 11):
                    if dx * dx + dy * dy <= 100:
                        npx, npy = pac_x + dx, 64 + dy
                        if 0 <= npx < 128 and 0 <= npy < 128:
                            # Cut mouth
                            if mouth_open and dx > 0 and abs(dy) < dx // 2:
                                continue
                            buffer[npy, npx] = (255, 255, 0)
            # Eye
            if pac_x - 2 >= 0 and pac_x - 2 < 128:
                buffer[60, pac_x - 2] = (0, 0, 0)

        # Draw ghosts chasing
        ghost_colors = [(255, 0, 0), (255, 184, 255), (0, 255, 255), (255, 184, 82)]
        for i, gc in enumerate(ghost_colors):
            gx = int(self.pacman_x - 25 - i * 18)
            color = (0, 0, 200) if self.pacman_power_mode else gc
            if 0 <= gx < 128:
                # Ghost body
                for dy in range(-10, 11):
                    for dx in range(-10, 11):
                        if dy < 5:
                            if dx * dx + (dy + 5) * (dy + 5) <= 100:
                                npx, npy = gx + dx, 64 + dy
                                if 0 <= npx < 128 and 0 <= npy < 128:
                                    buffer[npy, npx] = color
                        else:
                            if abs(dx) <= 10:
                                wave = (int(t * 10) + dx) % 4 < 2
                                if wave:
                                    npx, npy = gx + dx, 64 + dy
                                    if 0 <= npx < 128 and 0 <= npy < 128:
                                        buffer[npy, npx] = color
                # Eyes
                if not self.pacman_power_mode:
                    for ex in [-4, 4]:
                        ex_pos = gx + ex
                        if 0 <= ex_pos < 128:
                            buffer[61, ex_pos] = (255, 255, 255)
                            buffer[62, ex_pos] = (0, 0, 200)

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (255, 255, 0), scale=2)

    def _render_nyan_cat(self, buffer: NDArray[np.uint8]) -> None:
        """Render Nyan Cat with rainbow trail."""
        t = self.state.scene_time / 1000

        # Space background
        fill(buffer, (0, 0, 50))

        # Stars
        for i in range(50):
            sx = (i * 37 + int(t * 50)) % 128
            sy = (i * 23) % 128
            twinkle = 0.5 + 0.5 * math.sin(t * 5 + i)
            if 0 <= sx < 128 and 0 <= sy < 128:
                buffer[sy, sx] = (int(255 * twinkle), int(255 * twinkle), int(255 * twinkle))

        cat_x = 80
        cat_y = 55 + int(math.sin(t * 10) * 5)

        # Add rainbow segment
        self.nyan_rainbow_trail.append({'x': cat_x - 4, 'y': cat_y + 9})
        if len(self.nyan_rainbow_trail) > 50:
            self.nyan_rainbow_trail.pop(0)

        # Rainbow colors
        rainbow_colors = [
            (255, 0, 0), (255, 154, 0), (255, 255, 0),
            (0, 255, 0), (0, 0, 255), (130, 0, 255)
        ]

        # Draw rainbow trail
        for i, segment in enumerate(self.nyan_rainbow_trail):
            for j, color in enumerate(rainbow_colors):
                ry = int(segment['y'] - 9 + j * 3)
                rx = int(segment['x'] - (len(self.nyan_rainbow_trail) - i) * 2)
                if 0 <= rx < 128 and 0 <= ry < 128:
                    for ddy in range(3):
                        for ddx in range(3):
                            nrx, nry = rx + ddx, ry + ddy
                            if 0 <= nrx < 128 and 0 <= nry < 128:
                                buffer[nry, nrx] = color

        # Draw pop-tart body (pink pastry)
        for dy in range(-8, 9):
            for dx in range(-12, 13):
                px, py = cat_x + dx, cat_y + dy
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = (255, 150, 180)

        # Pink frosting
        for dy in range(-6, 7):
            for dx in range(-10, 11):
                px, py = cat_x + dx, cat_y + dy
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = (255, 100, 150)

        # Sprinkles
        sprinkle_positions = [(-6, -4), (-2, -2), (4, -3), (7, 0), (-4, 3), (2, 4), (-7, 1)]
        sprinkle_colors = [(255, 0, 0), (255, 255, 0), (0, 255, 0), (0, 255, 255)]
        for i, (sx, sy) in enumerate(sprinkle_positions):
            px, py = cat_x + sx, cat_y + sy
            if 0 <= px < 128 and 0 <= py < 128:
                buffer[py, px] = sprinkle_colors[i % len(sprinkle_colors)]

        # Cat face (gray)
        face_x = cat_x + 8
        for dy in range(-5, 6):
            for dx in range(-4, 5):
                px, py = face_x + dx, cat_y + dy
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = (150, 150, 150)

        # Eyes
        if face_x - 2 >= 0 and face_x - 2 < 128:
            buffer[cat_y - 2, face_x - 2] = (0, 0, 0)
        if face_x + 2 >= 0 and face_x + 2 < 128:
            buffer[cat_y - 2, face_x + 2] = (0, 0, 0)

        # Cheeks (pink)
        if face_x - 3 >= 0 and face_x - 3 < 128:
            buffer[cat_y + 1, face_x - 3] = (255, 150, 150)
        if face_x + 3 >= 0 and face_x + 3 < 128:
            buffer[cat_y + 1, face_x + 3] = (255, 150, 150)

        # Legs (animated)
        leg_frame = int(t * 8) % 2
        leg_y = cat_y + 10 + leg_frame
        for lx in [-8, -3, 3, 8]:
            px = cat_x + lx
            if 0 <= px < 128 and 0 <= leg_y < 128:
                buffer[leg_y, px] = (150, 150, 150)
                if leg_y + 1 < 128:
                    buffer[leg_y + 1, px] = (150, 150, 150)

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (255, 100, 150), scale=2)

    def _render_tetris(self, buffer: NDArray[np.uint8]) -> None:
        """Render Tetris falling blocks."""
        fill(buffer, (0, 0, 0))

        cell_size = 8
        offset_x = (128 - 13 * cell_size) // 2
        offset_y = (128 - 16 * cell_size) // 2

        # Draw border
        for y in range(offset_y - 2, offset_y + 16 * cell_size + 2):
            for x in [offset_x - 2, offset_x - 1, offset_x + 13 * cell_size, offset_x + 13 * cell_size + 1]:
                if 0 <= x < 128 and 0 <= y < 128:
                    buffer[y, x] = (100, 100, 100)
        for x in range(offset_x - 2, offset_x + 13 * cell_size + 2):
            for y in [offset_y - 2, offset_y - 1, offset_y + 16 * cell_size, offset_y + 16 * cell_size + 1]:
                if 0 <= x < 128 and 0 <= y < 128:
                    buffer[y, x] = (100, 100, 100)

        # Draw grid
        for y, row in enumerate(self.tetris_grid):
            for x, cell in enumerate(row):
                if cell:
                    px = offset_x + x * cell_size
                    py = offset_y + y * cell_size
                    for dy in range(cell_size - 1):
                        for dx in range(cell_size - 1):
                            npx, npy = px + dx, py + dy
                            if 0 <= npx < 128 and 0 <= npy < 128:
                                buffer[npy, npx] = cell
                    # Highlight
                    if py >= 0 and py < 128:
                        for dx in range(cell_size - 1):
                            if px + dx < 128:
                                buffer[py, px + dx] = (255, 255, 255)

        # Spawn new piece
        if self.tetris_piece is None:
            shape, color = random.choice(self.tetris_pieces)
            self.tetris_piece = {'shape': shape, 'color': color}
            self.tetris_piece_x = random.randint(0, 13 - len(shape[0]))
            self.tetris_piece_y = 0

        # Fall
        self.tetris_fall_timer += 1
        if self.tetris_fall_timer > 8:
            self.tetris_fall_timer = 0

            # Check if can move down
            can_move = True
            shape = self.tetris_piece['shape']
            for y, row in enumerate(shape):
                for x, cell in enumerate(row):
                    if cell:
                        new_y = self.tetris_piece_y + y + 1
                        new_x = self.tetris_piece_x + x
                        if new_y >= 16 or (new_y >= 0 and self.tetris_grid[new_y][new_x]):
                            can_move = False
                            break

            if can_move:
                self.tetris_piece_y += 1
            else:
                # Lock piece
                color = self.tetris_piece['color']
                for y, row in enumerate(shape):
                    for x, cell in enumerate(row):
                        if cell:
                            grid_y = self.tetris_piece_y + y
                            grid_x = self.tetris_piece_x + x
                            if 0 <= grid_y < 16 and 0 <= grid_x < 13:
                                self.tetris_grid[grid_y][grid_x] = color

                # Clear lines
                new_grid = [row for row in self.tetris_grid if any(cell is None for cell in row)]
                lines_cleared = 16 - len(new_grid)
                self.tetris_grid = [[None] * 13 for _ in range(lines_cleared)] + new_grid

                self.tetris_piece = None

        # Draw current piece
        if self.tetris_piece:
            shape = self.tetris_piece['shape']
            color = self.tetris_piece['color']
            for y, row in enumerate(shape):
                for x, cell in enumerate(row):
                    if cell:
                        px = offset_x + (self.tetris_piece_x + x) * cell_size
                        py = offset_y + (self.tetris_piece_y + y) * cell_size
                        for dy in range(cell_size - 1):
                            for dx in range(cell_size - 1):
                                npx, npy = px + dx, py + dy
                                if 0 <= npx < 128 and 0 <= npy < 128:
                                    buffer[npy, npx] = color

        # Reset if grid full
        if any(self.tetris_grid[0]):
            self.tetris_grid = [[None] * 13 for _ in range(16)]

        # Branding
        draw_centered_text(buffer, "VNVNC", 4, (0, 255, 255), scale=2)

    def _render_four_seasons(self, buffer: NDArray[np.uint8]) -> None:
        """Render magical fractal tree with changing seasons."""
        t = self.state.scene_time / 1000

        # Sky gradient based on season
        for y in range(113):
            sky_t = y / 113
            if self.tree_season == 0:  # Spring dawn - pink/orange
                r = int(255 * sky_t + 100)
                g = int(150 + 50 * sky_t)
                b = int(180 + 60 * sky_t)
            elif self.tree_season == 1:  # Summer day - blue
                r = int(100 + 100 * sky_t)
                g = int(150 + 100 * sky_t)
                b = 255
            elif self.tree_season == 2:  # Autumn sunset - orange/red
                r = 255
                g = int(100 + 80 * sky_t)
                b = int(50 + 100 * sky_t)
            else:  # Winter night - dark blue
                r = int(20 + 30 * sky_t)
                g = int(25 + 35 * sky_t)
                b = int(50 + 50 * sky_t)
            buffer[y, :] = [min(255, r), min(255, g), min(255, b)]

        # Ground
        if self.tree_season == 3:
            buffer[113:, :] = [220, 220, 240]  # Snow
        elif self.tree_season == 2:
            buffer[113:, :] = [80, 50, 30]  # Dead grass
        else:
            buffer[113:, :] = [40, 100, 40]  # Green grass

        # Clear branch cache
        self.tree_branch_cache = []

        # Draw fractal tree
        def draw_branch(x: float, y: float, angle: float, length: float, depth: int, max_depth: int):
            if depth > max_depth or length < 2:
                if depth >= max_depth - 1:
                    self.tree_branch_cache.append((x, y, depth))
                return

            # Wind sway
            wind = math.sin(t * 2 + depth * 0.5 + x * 0.01) * (depth * 0.02)
            end_x = x + math.cos(angle + wind) * length
            end_y = y - math.sin(angle + wind) * length

            # Branch color
            if depth < max_depth - 2:
                color = (60 + depth * 5, 40 + depth * 3, 20)  # Brown bark
            else:
                if self.tree_season == 0:  # Spring - pink
                    color = (255, 150 + depth * 10, 180)
                elif self.tree_season == 1:  # Summer - green
                    color = (50, 180 - depth * 10, 50)
                elif self.tree_season == 2:  # Autumn - orange
                    hue = max(0, 30 - depth * 5 + random.randint(-10, 10))
                    color = hsv_to_rgb(hue, 0.9, 0.9)
                else:  # Winter - frost
                    color = (150, 150, 160)

            # Draw branch line
            steps = max(1, int(length))
            for step in range(steps + 1):
                lx = int(x + (end_x - x) * step / steps)
                ly = int(y + (end_y - y) * step / steps)
                if 0 <= lx < 128 and 0 <= ly < 128:
                    buffer[ly, lx] = color

            # Asymmetric branching
            angle_var = 0.4 + 0.1 * math.sin(t + depth)
            len_var = 0.65 + 0.1 * math.sin(t * 0.5 + x * 0.1)

            draw_branch(end_x, end_y, angle + angle_var, length * len_var, depth + 1, max_depth)
            draw_branch(end_x, end_y, angle - angle_var * 0.9, length * (len_var + 0.05), depth + 1, max_depth)

        # Draw main tree
        draw_branch(64, 113, math.pi / 2, 25, 0, 7)

        # Draw leaves/blossoms at branch ends
        for bx, by, depth in self.tree_branch_cache:
            if self.tree_season == 0:  # Cherry blossoms
                for _ in range(2):
                    px = int(bx + random.randint(-3, 3))
                    py = int(by + random.randint(-3, 3))
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = [255, 180, 200]
            elif self.tree_season == 1:  # Green leaves
                for _ in range(2):
                    px = int(bx + random.randint(-2, 2))
                    py = int(by + random.randint(-2, 2))
                    if 0 <= px < 128 and 0 <= py < 128:
                        green = random.randint(120, 200)
                        buffer[py, px] = [50, green, 50]

        # Seasonal particles
        if self.tree_season == 0 and random.random() < 0.1:  # Falling petals
            self.tree_particles.append({'x': random.randint(0, 128), 'y': -5, 'type': 'petal'})
        elif self.tree_season == 2 and random.random() < 0.08:  # Falling leaves
            self.tree_particles.append({'x': random.randint(0, 128), 'y': -5, 'type': 'leaf',
                                       'hue': random.randint(15, 45)})
        elif self.tree_season == 3 and random.random() < 0.15:  # Snow
            self.tree_particles.append({'x': random.randint(0, 128), 'y': -5, 'type': 'snow'})
        elif self.tree_season == 1 and random.random() < 0.02:  # Fireflies
            self.tree_particles.append({'x': random.randint(0, 128), 'y': random.randint(20, 100),
                                       'type': 'firefly', 'life': 60})

        # Update and draw particles
        new_particles = []
        for p in self.tree_particles:
            if p['type'] == 'petal':
                p['x'] += math.sin(t * 3 + p['y'] * 0.1) * 0.5
                p['y'] += 0.8
                if p['y'] < 128:
                    px, py = int(p['x']), int(p['y'])
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = [255, 200, 210]
                    new_particles.append(p)
            elif p['type'] == 'leaf':
                p['x'] += math.sin(t * 2 + p['y'] * 0.05) * 1.5
                p['y'] += 1.2
                if p['y'] < 128:
                    px, py = int(p['x']), int(p['y'])
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = hsv_to_rgb(p['hue'], 0.9, 0.8)
                    new_particles.append(p)
            elif p['type'] == 'snow':
                p['x'] += math.sin(t * 2 + p['y'] * 0.1) * 0.3
                p['y'] += 0.6
                if p['y'] < 118:
                    px, py = int(p['x']), int(p['y'])
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = [255, 255, 255]
                    new_particles.append(p)
            elif p['type'] == 'firefly':
                p['x'] += math.sin(t * 4 + p['y']) * 0.5
                p['y'] += math.cos(t * 3 + p['x'] * 0.1) * 0.3
                p['life'] -= 1
                if p['life'] > 0:
                    glow = int(200 * abs(math.sin(t * 8 + p['x'])))
                    px, py = int(p['x']), int(p['y'])
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = [glow, glow, 50]
                    new_particles.append(p)

        self.tree_particles = new_particles[-100:]  # Limit particles

        # Season transition
        self.tree_season_time += 0.002
        if self.tree_season_time > 1:
            self.tree_season_time = 0
            self.tree_season = (self.tree_season + 1) % 4
            self.tree_particles = []

        # Branding with shadow
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 0, 0), scale=2)
        season_colors = [(255, 150, 200), (100, 200, 100), (255, 150, 50), (200, 200, 255)]
        draw_centered_text(buffer, "VNVNC", 4, season_colors[self.tree_season], scale=2)

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
            # Classic effects
            IdleScene.SNOWFALL: "ЗИМНЯЯ СКАЗКА",
            IdleScene.FIREPLACE: "УЮТНЫЙ КАМИН",
            IdleScene.PLASMA_CLASSIC: "КЛАССИЧЕСКАЯ ПЛАЗМА",
            IdleScene.TUNNEL: "БЕСКОНЕЧНЫЙ ТОННЕЛЬ",
            IdleScene.WAVE_PATTERN: "ВОЛНОВАЯ ИНТЕРФЕРЕНЦИЯ",
            IdleScene.AURORA: "СЕВЕРНОЕ СИЯНИЕ",
            IdleScene.KALEIDOSCOPE: "КАЛЕЙДОСКОП",
            IdleScene.FIREWORKS: "ФЕЙЕРВЕРК",
            IdleScene.LAVA_LAMP: "ЛАВОВАЯ ЛАМПА",
            IdleScene.GAME_OF_LIFE: "ИГРА ЖИЗНИ КОНВЕЯ",
            IdleScene.RADAR_SWEEP: "РАДАРНОЕ СКАНИРОВАНИЕ",
            IdleScene.SPIRAL_GALAXY: "СПИРАЛЬНАЯ ГАЛАКТИКА",
            IdleScene.BLACK_HOLE: "ЧЁРНАЯ ДЫРА",
            IdleScene.HYPERCUBE: "ГИПЕРКУБ 4D",
            # Iconic scenes
            IdleScene.PACMAN: "PAC-MAN ПОГОНЯ",
            IdleScene.NYAN_CAT: "NYAN CAT В КОСМОСЕ",
            IdleScene.TETRIS: "ТЕТРИС",
            IdleScene.FOUR_SEASONS: "ЧЕТЫРЕ СЕЗОНА",
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
            # Classic effects
            IdleScene.SNOWFALL: (200, 220, 255),
            IdleScene.FIREPLACE: (255, 150, 50),
            IdleScene.PLASMA_CLASSIC: (255, 100, 200),
            IdleScene.TUNNEL: (100, 200, 255),
            IdleScene.WAVE_PATTERN: (100, 255, 200),
            IdleScene.AURORA: (100, 255, 150),
            IdleScene.KALEIDOSCOPE: (255, 200, 100),
            IdleScene.FIREWORKS: (255, 255, 100),
            IdleScene.LAVA_LAMP: (255, 100, 50),
            IdleScene.GAME_OF_LIFE: (100, 255, 100),
            IdleScene.RADAR_SWEEP: (0, 255, 100),
            IdleScene.SPIRAL_GALAXY: (200, 150, 255),
            IdleScene.BLACK_HOLE: (100, 50, 200),
            IdleScene.HYPERCUBE: (0, 255, 255),
            # Iconic scenes
            IdleScene.PACMAN: (255, 255, 0),
            IdleScene.NYAN_CAT: (255, 150, 200),
            IdleScene.TETRIS: (100, 255, 255),
            IdleScene.FOUR_SEASONS: (150, 200, 100),
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
            # Classic effects
            IdleScene.SNOWFALL: ["   ЗИМНЯЯ   ", "   СКАЗКА   ", " НАЖМИ СТАРТ "],
            IdleScene.FIREPLACE: ["   УЮТНЫЙ   ", "   КАМИН    ", " НАЖМИ СТАРТ "],
            IdleScene.PLASMA_CLASSIC: [" КЛАССИКА   ", "   ПЛАЗМЫ   ", " НАЖМИ СТАРТ "],
            IdleScene.TUNNEL: ["БЕСКОНЕЧНЫЙ ", "  ТОННЕЛЬ   ", " НАЖМИ СТАРТ "],
            IdleScene.WAVE_PATTERN: ["   ВОЛНЫ    ", "ИНТЕРФЕРЕНЦ.", " НАЖМИ СТАРТ "],
            IdleScene.AURORA: ["  СЕВЕРНОЕ  ", "  СИЯНИЕ    ", " НАЖМИ СТАРТ "],
            IdleScene.KALEIDOSCOPE: ["КАЛЕЙДОСКОП ", "   ЦВЕТА    ", " НАЖМИ СТАРТ "],
            IdleScene.FIREWORKS: [" ФЕЙЕРВЕРК  ", "   ПРАЗДНИК ", " НАЖМИ СТАРТ "],
            IdleScene.LAVA_LAMP: ["  ЛАВОВАЯ   ", "   ЛАМПА    ", " НАЖМИ СТАРТ "],
            IdleScene.GAME_OF_LIFE: [" ИГРА ЖИЗНИ ", "   КОНВЕЯ   ", " НАЖМИ СТАРТ "],
            IdleScene.RADAR_SWEEP: ["   РАДАР    ", "СКАНИРОВАНИЕ", " НАЖМИ СТАРТ "],
            IdleScene.SPIRAL_GALAXY: ["СПИРАЛЬНАЯ  ", " ГАЛАКТИКА  ", " НАЖМИ СТАРТ "],
            IdleScene.BLACK_HOLE: ["  ЧЁРНАЯ    ", "   ДЫРА     ", " НАЖМИ СТАРТ "],
            IdleScene.HYPERCUBE: [" ГИПЕРКУБ   ", "    4D      ", " НАЖМИ СТАРТ "],
            # Iconic scenes
            IdleScene.PACMAN: ["  PAC-MAN   ", "  ПОГОНЯ    ", " НАЖМИ СТАРТ "],
            IdleScene.NYAN_CAT: [" NYAN CAT   ", "  РАДУГА    ", " НАЖМИ СТАРТ "],
            IdleScene.TETRIS: ["  ТЕТРИС    ", "   БЛОКИ    ", " НАЖМИ СТАРТ "],
            IdleScene.FOUR_SEASONS: ["  ЧЕТЫРЕ    ", "  СЕЗОНА    ", " НАЖМИ СТАРТ "],
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

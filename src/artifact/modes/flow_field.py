"""Flow Field Mode - Mesmerizing particle art from your face.

Your face emerges from thousands of flowing particles guided by Perlin noise.
Use buttons to control the flow, create explosions, and paint with light.

Controls:
- LEFT: Change flow pattern (spiral, waves, chaos)
- RIGHT: Spawn burst of particles from face
- START: Capture beautiful moment / Change color palette
"""

from typing import Optional, List, Tuple
from enum import Enum, auto
import math
import random
import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_circle, draw_rect
from artifact.graphics.fonts import load_font, draw_text_bitmap
from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect
from artifact.graphics.algorithmic_art import FlowField, PerlinNoise, hsv_to_rgb, Dithering


class FlowPattern(Enum):
    """Available flow patterns."""
    ORBITAL = auto()      # Circular orbital flow
    WAVES = auto()        # Horizontal waves
    SPIRAL = auto()       # Spiral inward
    CHAOS = auto()        # Pure noise
    EXPLOSION = auto()    # Radial outward
    VORTEX = auto()       # Double vortex


class ColorPalette(Enum):
    """Color palette themes."""
    NEON = auto()         # Bright neon colors
    FIRE = auto()         # Red/orange/yellow
    OCEAN = auto()        # Blue/teal/cyan
    AURORA = auto()       # Green/purple/pink
    MONO = auto()         # Single color gradient
    RAINBOW = auto()      # Full spectrum


class FlowPhase(Enum):
    """Flow field mode phases."""
    INTRO = "intro"
    CAMERA_CAPTURE = "camera_capture"
    FLOWING = "flowing"
    CAPTURE_MOMENT = "capture_moment"
    RESULT = "result"


class FlowFieldMode(BaseMode):
    """Interactive flow field art mode.

    Creates stunning particle art from the player's face,
    with particles flowing according to Perlin noise patterns.
    """

    name = "flow_field"
    display_name = "ПОТОК"
    icon = "flow"
    style = "mystical"

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._sub_phase = FlowPhase.INTRO
        self._time_in_phase = 0.0

        # Flow field
        self._flow_field: Optional[FlowField] = None
        self._pattern = FlowPattern.ORBITAL
        self._pattern_index = 0
        self._patterns = list(FlowPattern)

        # Color palette
        self._palette = ColorPalette.NEON
        self._palette_index = 0
        self._palettes = list(ColorPalette)
        self._hue_offset = 0.0

        # Camera
        self._camera = None
        self._camera_frame: Optional[NDArray] = None
        self._face_brightness: Optional[NDArray] = None

        # Particle spawning
        self._spawn_rate = 5  # Particles per frame
        self._max_particles = 2000
        self._particle_speed = 1.5

        # Trail buffer (persistent)
        self._trail_buffer: Optional[NDArray] = None

        # Captured moments
        self._captured_image: Optional[NDArray] = None

        # Animation state
        self._burst_cooldown = 0.0
        self._flow_evolution = 0.0
        self._intensity = 1.0
        self._total_time = 0.0

    def on_enter(self) -> None:
        """Initialize mode."""
        self._sub_phase = FlowPhase.INTRO
        self._time_in_phase = 0.0
        self._pattern_index = 0
        self._pattern = self._patterns[0]
        self._palette_index = 0
        self._palette = self._palettes[0]
        self._hue_offset = 0.0
        self._total_time = 0.0

        # Initialize flow field
        self._flow_field = FlowField(128, 128, scale=0.04, seed=random.randint(0, 65535))

        # Initialize trail buffer
        self._trail_buffer = np.zeros((128, 128, 3), dtype=np.uint8)

        # Try to open camera
        try:
            from artifact.utils.camera import create_camera
            self._camera = create_camera(resolution=(128, 128))
            self._camera.open()
        except Exception:
            self._camera = None

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
        if self._sub_phase == FlowPhase.INTRO:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = FlowPhase.CAMERA_CAPTURE
                self._time_in_phase = 0.0
                return True
            return False

        if self._sub_phase == FlowPhase.FLOWING:
            if event.type == EventType.ARCADE_LEFT:
                # Change pattern
                self._pattern_index = (self._pattern_index + 1) % len(self._patterns)
                self._pattern = self._patterns[self._pattern_index]
                self._update_flow_pattern()
                if hasattr(self.context, 'audio') and self.context.audio:
                    self.context.audio.play_ui_click()
                return True

            elif event.type == EventType.ARCADE_RIGHT:
                # Spawn burst of particles
                if self._burst_cooldown <= 0:
                    self._spawn_particle_burst(200)
                    self._burst_cooldown = 500  # 500ms cooldown
                    if hasattr(self.context, 'audio') and self.context.audio:
                        self.context.audio.play_ui_confirm()
                return True

            elif event.type == EventType.BUTTON_PRESS:
                # Change palette and capture moment
                self._palette_index = (self._palette_index + 1) % len(self._palettes)
                self._palette = self._palettes[self._palette_index]
                self._capture_moment()
                if hasattr(self.context, 'audio') and self.context.audio:
                    self.context.audio.play_success()
                return True

        elif self._sub_phase == FlowPhase.RESULT:
            if event.type == EventType.BUTTON_PRESS:
                # Restart
                self._sub_phase = FlowPhase.FLOWING
                self._time_in_phase = 0.0
                self._trail_buffer = np.zeros((128, 128, 3), dtype=np.uint8)
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        """Update mode state."""
        self._time_in_phase += delta_ms
        self._total_time += delta_ms
        self._hue_offset += delta_ms / 50  # Slow hue rotation
        self._flow_evolution += delta_ms / 1000
        self._burst_cooldown = max(0, self._burst_cooldown - delta_ms)

        if self._sub_phase == FlowPhase.INTRO:
            if self._time_in_phase > 3000:
                self._sub_phase = FlowPhase.CAMERA_CAPTURE
                self._time_in_phase = 0.0

        elif self._sub_phase == FlowPhase.CAMERA_CAPTURE:
            # Capture camera frame
            self._capture_camera()
            if self._camera_frame is not None:
                # Process face brightness for particle spawning
                self._process_face()
                self._sub_phase = FlowPhase.FLOWING
                self._time_in_phase = 0.0

            # Timeout
            if self._time_in_phase > 5000:
                # Create fake face pattern
                self._create_demo_face()
                self._sub_phase = FlowPhase.FLOWING
                self._time_in_phase = 0.0

        elif self._sub_phase == FlowPhase.FLOWING:
            # Continuously capture camera for dynamic face tracking
            if self._camera and self._camera.is_open:
                try:
                    frame = self._camera.capture_frame()
                    if frame is not None:
                        self._camera_frame = frame
                        self._process_face()
                except Exception:
                    pass

            # Update flow field
            self._flow_field.time_offset = self._flow_evolution
            self._update_flow_pattern()
            self._flow_field.update(delta_ms, evolve=False)

            # Spawn particles from face
            self._spawn_particles_from_face()

            # Update intensity based on particle count
            particle_ratio = len(self._flow_field.particles) / self._max_particles
            self._intensity = 0.5 + 0.5 * particle_ratio

        elif self._sub_phase == FlowPhase.CAPTURE_MOMENT:
            if self._time_in_phase > 2000:
                self._sub_phase = FlowPhase.FLOWING
                self._time_in_phase = 0.0

    def _capture_camera(self):
        """Capture frame from camera."""
        if self._camera and self._camera.is_open:
            try:
                frame = self._camera.capture_frame()
                if frame is not None:
                    # Resize if needed
                    if frame.shape[:2] != (128, 128):
                        from PIL import Image
                        img = Image.fromarray(frame)
                        img = img.resize((128, 128), Image.Resampling.BILINEAR)
                        frame = np.array(img)
                    self._camera_frame = frame
            except Exception:
                pass

    def _process_face(self):
        """Process camera frame to extract face brightness."""
        if self._camera_frame is None:
            return

        # Convert to grayscale brightness map
        if len(self._camera_frame.shape) == 3:
            self._face_brightness = np.mean(self._camera_frame, axis=2).astype(np.float32)
        else:
            self._face_brightness = self._camera_frame.astype(np.float32)

        # Enhance contrast
        min_val = np.min(self._face_brightness)
        max_val = np.max(self._face_brightness)
        if max_val > min_val:
            self._face_brightness = (self._face_brightness - min_val) / (max_val - min_val) * 255

    def _create_demo_face(self):
        """Create a demo pattern if no camera - VECTORIZED."""
        self._face_brightness = np.zeros((128, 128), dtype=np.float32)
        cx, cy = 64, 64

        # Create coordinate grids
        y_coords = np.arange(128)[:, np.newaxis]
        x_coords = np.arange(128)[np.newaxis, :]

        # Distance from center
        dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)

        # Face oval - apply where dist < 45
        face_mask = dist < 45
        self._face_brightness[face_mask] = (200 * (1 - dist[face_mask] / 45))

        # Eyes - override in specific regions
        eye_mask = (y_coords > 20) & (y_coords < 50) & (
            (np.abs(x_coords - 45) < 10) | (np.abs(x_coords - 83) < 10)
        )
        self._face_brightness[eye_mask] = 255

    def _spawn_particles_from_face(self):
        """Spawn particles from bright areas of face."""
        if self._face_brightness is None:
            return

        if len(self._flow_field.particles) >= self._max_particles:
            return

        for _ in range(self._spawn_rate):
            # Random position weighted by brightness
            y = random.randint(0, 127)
            x = random.randint(0, 127)
            brightness = self._face_brightness[y, x] / 255

            # Higher chance to spawn in bright areas
            if random.random() < brightness * 0.3:
                color = self._get_particle_color(x, y, brightness)
                self._flow_field.particles.append(
                    self._create_particle(x, y, color)
                )

    def _spawn_particle_burst(self, count: int):
        """Spawn a burst of particles from face center."""
        if self._face_brightness is None:
            return

        # Find brightest area (approximate face center)
        bright_coords = np.argwhere(self._face_brightness > 100)
        if len(bright_coords) == 0:
            cx, cy = 64, 64
        else:
            cy, cx = bright_coords.mean(axis=0).astype(int)

        for _ in range(count):
            # Spawn around center with some spread
            x = cx + random.gauss(0, 20)
            y = cy + random.gauss(0, 20)
            x = max(0, min(127, x))
            y = max(0, min(127, y))

            brightness = self._face_brightness[int(y), int(x)] / 255
            color = self._get_particle_color(x, y, brightness)
            particle = self._create_particle(x, y, color)
            particle.speed = random.uniform(2, 5)  # Faster burst particles
            self._flow_field.particles.append(particle)

    def _create_particle(self, x: float, y: float, color: Tuple[int, int, int]):
        """Create a flow particle."""
        from artifact.graphics.algorithmic_art import FlowParticle
        return FlowParticle(
            x=x, y=y, prev_x=x, prev_y=y,
            speed=self._particle_speed * random.uniform(0.8, 1.2),
            color=color,
            max_age=random.randint(80, 200)
        )

    def _get_particle_color(self, x: float, y: float, brightness: float) -> Tuple[int, int, int]:
        """Get color for particle based on palette and position."""
        t = self._time_in_phase

        if self._palette == ColorPalette.NEON:
            hue = (x / 128 * 120 + y / 128 * 60 + self._hue_offset) % 360
            return hsv_to_rgb(hue, 1.0, brightness)

        elif self._palette == ColorPalette.FIRE:
            hue = 20 + brightness * 40  # Orange to yellow
            return hsv_to_rgb(hue, 1.0, 0.5 + brightness * 0.5)

        elif self._palette == ColorPalette.OCEAN:
            hue = 180 + brightness * 40  # Cyan to blue
            return hsv_to_rgb(hue, 0.8, 0.5 + brightness * 0.5)

        elif self._palette == ColorPalette.AURORA:
            hue = (120 + brightness * 180 + self._hue_offset * 0.5) % 360
            return hsv_to_rgb(hue, 0.9, brightness)

        elif self._palette == ColorPalette.MONO:
            v = int(255 * brightness)
            return (v, v, v)

        else:  # RAINBOW
            hue = (self._hue_offset + x + y) % 360
            return hsv_to_rgb(hue, 1.0, brightness)

    def _update_flow_pattern(self):
        """Update flow field based on current pattern - VECTORIZED."""
        t = self._flow_evolution
        cx, cy = 64, 64

        # Create coordinate grids (cache these if needed for more speed)
        y_coords = np.arange(128)[:, np.newaxis].astype(np.float32)
        x_coords = np.arange(128)[np.newaxis, :].astype(np.float32)

        # Distance and angle from center
        dx = x_coords - cx
        dy = y_coords - cy
        dist = np.sqrt(dx * dx + dy * dy)
        angle_to_center = np.arctan2(dy, dx)

        if self._pattern == FlowPattern.ORBITAL:
            # Circular orbital flow with simplified noise
            base_angle = angle_to_center + np.pi / 2
            noise_val = np.sin(x_coords * 0.03 + t) * np.cos(y_coords * 0.03) * 0.5 - 0.25
            self._flow_field.field = base_angle + noise_val * 0.5

        elif self._pattern == FlowPattern.WAVES:
            # Horizontal waves
            self._flow_field.field = np.sin(y_coords * 0.1 + t * 2) * 0.3

        elif self._pattern == FlowPattern.SPIRAL:
            # Spiral inward
            self._flow_field.field = angle_to_center - dist * 0.05 + np.pi

        elif self._pattern == FlowPattern.CHAOS:
            # Simplified chaos using trig functions instead of Perlin
            chaos = np.sin(x_coords * 0.05 + t) * np.cos(y_coords * 0.05 + t) * np.pi * 4
            self._flow_field.field = chaos

        elif self._pattern == FlowPattern.EXPLOSION:
            # Radial outward
            self._flow_field.field = angle_to_center

        elif self._pattern == FlowPattern.VORTEX:
            # Double vortex
            vortex1_x, vortex1_y = 40, 64
            vortex2_x, vortex2_y = 88, 64

            angle1 = np.arctan2(y_coords - vortex1_y, x_coords - vortex1_x) + np.pi / 2
            angle2 = np.arctan2(y_coords - vortex2_y, x_coords - vortex2_x) - np.pi / 2
            dist1 = np.sqrt((x_coords - vortex1_x) ** 2 + (y_coords - vortex1_y) ** 2)
            dist2 = np.sqrt((x_coords - vortex2_x) ** 2 + (y_coords - vortex2_y) ** 2)

            # Blend based on distance
            w1 = 1 / (dist1 + 1)
            w2 = 1 / (dist2 + 1)
            self._flow_field.field = (angle1 * w1 + angle2 * w2) / (w1 + w2)

    def _capture_moment(self):
        """Capture current visual as an image."""
        self._captured_image = self._trail_buffer.copy()
        self._sub_phase = FlowPhase.CAPTURE_MOMENT
        self._time_in_phase = 0.0

    # =========================================================================
    # RENDERING
    # =========================================================================

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        t = self._time_in_phase

        if self._sub_phase == FlowPhase.INTRO:
            self._render_intro(buffer, t)
        elif self._sub_phase == FlowPhase.CAMERA_CAPTURE:
            self._render_camera_capture(buffer, t)
        elif self._sub_phase == FlowPhase.FLOWING:
            self._render_flowing(buffer, t)
        elif self._sub_phase == FlowPhase.CAPTURE_MOMENT:
            self._render_capture_moment(buffer, t)
        elif self._sub_phase == FlowPhase.RESULT:
            self._render_result(buffer, t)

    def _render_intro(self, buffer: NDArray[np.uint8], t: float):
        """Render intro screen."""
        fill(buffer, (10, 5, 20))

        # Animated particles preview
        cx, cy = 64, 64
        for i in range(50):
            angle = t / 200 + i * 0.12
            r = 30 + 15 * math.sin(t / 300 + i * 0.1)
            px = int(cx + r * math.cos(angle))
            py = int(cy + r * math.sin(angle))
            if 0 <= px < 128 and 0 <= py < 128:
                hue = (i * 7 + t / 10) % 360
                buffer[py, px] = hsv_to_rgb(hue, 1.0, 0.8)

        # Title
        draw_centered_text(buffer, "ПОТОК", 15, (255, 200, 100), scale=2)
        draw_centered_text(buffer, "ЧАСТИЦ", 35, (200, 150, 255), scale=2)

        # Instructions
        draw_centered_text(buffer, "ТВОЁ ЛИЦО", 75, (150, 200, 150), scale=1)
        draw_centered_text(buffer, "СТАНЕТ ИСКУССТВОМ", 90, (150, 200, 150), scale=1)

        draw_animated_text(buffer, "НАЖМИ СТАРТ", 110, (100, 150, 100), t, TextEffect.PULSE, scale=1)

    def _render_camera_capture(self, buffer: NDArray[np.uint8], t: float):
        """Render camera capture phase with live camera preview - VECTORIZED."""
        fill(buffer, (20, 10, 30))

        # Show camera preview with flow-style coloring
        if self._camera_frame is not None:
            # Calculate brightness from camera frame (vectorized)
            brightness = np.mean(self._camera_frame, axis=2) / 255.0

            # Create coordinate grids for hue shift
            y_coords = np.arange(128)[:, np.newaxis]
            x_coords = np.arange(128)[np.newaxis, :]
            hue_shift = np.sin(x_coords * 0.05 + y_coords * 0.05 + t / 300) * 30

            # Apply flow-style purple/blue tint
            r = np.clip((80 + hue_shift) * brightness, 0, 255).astype(np.uint8)
            g = np.clip((100 + hue_shift * 0.5) * brightness, 0, 255).astype(np.uint8)
            b = np.clip(200 * brightness, 0, 255).astype(np.uint8)

            buffer[:, :, 0] = r
            buffer[:, :, 1] = g
            buffer[:, :, 2] = b

        # Scanning line overlay
        scan_y = int((t % 2000) / 2000 * 128)
        if 0 <= scan_y < 128:
            buffer[scan_y, :] = (0, 255, 200)
        if 0 <= scan_y + 1 < 128:
            buffer[scan_y + 1, :] = (0, 200, 150)

        # Pulsing circle overlay
        pulse = 0.7 + 0.3 * math.sin(t / 150)
        draw_circle(buffer, 64, 64, int(40 * pulse), (100, 50, 150))

        draw_centered_text(buffer, "СКАНИРУЮ...", 100, (150, 200, 200), scale=1)

    def _render_flowing(self, buffer: NDArray[np.uint8], t: float):
        """Render the flowing particles with live camera background - VECTORIZED."""
        # First, render camera as a subtle background
        if self._camera_frame is not None:
            # Calculate brightness from camera frame (vectorized)
            brightness = np.mean(self._camera_frame, axis=2) / 255.0

            # Deep blue/purple tint at 15% intensity
            buffer[:, :, 0] = (10 + 15 * brightness).astype(np.uint8)
            buffer[:, :, 1] = (5 + 12 * brightness).astype(np.uint8)
            buffer[:, :, 2] = (20 + 25 * brightness).astype(np.uint8)
        else:
            # Clear to dark background
            buffer[:] = (10, 5, 20)

        # Fade trail buffer (in-place for efficiency)
        self._trail_buffer[:] = (self._trail_buffer * 0.92).astype(np.uint8)

        # Render particles to trail buffer (keep particle loop - necessary for trails)
        # Limit particles processed per frame for performance
        particles = self._flow_field.particles
        max_per_frame = min(len(particles), 500)
        for i in range(max_per_frame):
            particle = particles[i]
            alpha = particle.life
            color = (
                int(particle.color[0] * alpha),
                int(particle.color[1] * alpha),
                int(particle.color[2] * alpha),
            )

            px, py = int(particle.x), int(particle.y)
            prev_px, prev_py = int(particle.prev_x), int(particle.prev_y)

            # Draw line from previous position (particle trail)
            if particle.age > 0:
                self._draw_line(self._trail_buffer, prev_px, prev_py, px, py, color)
            elif 0 <= px < 128 and 0 <= py < 128:
                self._trail_buffer[py, px] = color

        # Blend trail buffer on top of camera background (additive) - VECTORIZED
        blended = buffer.astype(np.int16) + self._trail_buffer.astype(np.int16)
        np.clip(blended, 0, 255, out=blended)
        buffer[:] = blended.astype(np.uint8)

        # UI overlay
        self._render_ui_overlay(buffer, t)

    def _draw_line(self, buffer: NDArray[np.uint8], x1: int, y1: int, x2: int, y2: int, color):
        """Draw a line on buffer."""
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        while True:
            if 0 <= x1 < 128 and 0 <= y1 < 128:
                buffer[y1, x1] = color

            if x1 == x2 and y1 == y2:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x1 += sx
            if e2 < dx:
                err += dx
                y1 += sy

    def _render_ui_overlay(self, buffer: NDArray[np.uint8], t: float):
        """Render UI overlay on flowing view."""
        # Pattern name (top left)
        pattern_names = {
            FlowPattern.ORBITAL: "ОРБИТА",
            FlowPattern.WAVES: "ВОЛНЫ",
            FlowPattern.SPIRAL: "СПИРАЛЬ",
            FlowPattern.CHAOS: "ХАОС",
            FlowPattern.EXPLOSION: "ВЗРЫВ",
            FlowPattern.VORTEX: "ВИХРЬ",
        }
        pattern_text = pattern_names.get(self._pattern, "?")

        # Semi-transparent background for text
        draw_rect(buffer, 0, 0, 50, 12, (0, 0, 0))
        draw_text_bitmap(buffer, pattern_text, 2, 2, (150, 150, 200),
                         load_font("cyrillic"), scale=1)

        # Particle count (top right)
        count_text = f"{len(self._flow_field.particles)}"
        draw_rect(buffer, 100, 0, 28, 12, (0, 0, 0))
        draw_text_bitmap(buffer, count_text, 102, 2, (100, 200, 100),
                         load_font("cyrillic"), scale=1)

        # Hint at bottom
        hint_alpha = 0.5 + 0.3 * math.sin(t / 500)
        hint_color = (int(80 * hint_alpha), int(100 * hint_alpha), int(80 * hint_alpha))
        draw_centered_text(buffer, "<ПАТТЕРН  ВСПЛЕСК>", 118, hint_color, scale=1)

    def _render_capture_moment(self, buffer: NDArray[np.uint8], t: float):
        """Render captured moment."""
        if self._captured_image is not None:
            np.copyto(buffer, self._captured_image)

        # Flash effect
        flash = max(0, 1 - t / 500)
        if flash > 0:
            buffer[:] = np.clip(buffer.astype(np.int16) + int(200 * flash), 0, 255).astype(np.uint8)

        # Text overlay
        draw_rect(buffer, 0, 50, 128, 28, (0, 0, 0))
        draw_centered_text(buffer, "СОХРАНЕНО!", 55, (255, 200, 100), scale=2)

    def _render_result(self, buffer: NDArray[np.uint8], t: float):
        """Render result screen."""
        if self._captured_image is not None:
            np.copyto(buffer, self._captured_image)
        else:
            fill(buffer, (20, 20, 40))

        draw_centered_text(buffer, "ПОТОК ИСКУССТВА", 110, (200, 200, 255), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display as camera continuation - VECTORIZED."""
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect
        from artifact.graphics.primitives import clear

        clear(buffer)
        t = self._time_in_phase

        if self._sub_phase == FlowPhase.FLOWING and self._camera_frame is not None:
            # Map ticker coords to camera coords
            ty_coords = np.arange(8)[:, np.newaxis]
            tx_coords = np.arange(48)[np.newaxis, :]
            cam_y = (ty_coords * 128) // 8
            cam_x = (tx_coords * 128) // 48

            # Sample camera at mapped coordinates
            sampled = self._camera_frame[cam_y, cam_x]
            brightness = np.mean(sampled, axis=2) / 255.0

            # Flow field colors (blue-purple)
            hue_shift = np.sin(tx_coords * 0.2 + self._total_time / 1000) * 30
            r = np.clip((100 + hue_shift) * brightness, 0, 255).astype(np.uint8)
            g = np.clip((150 + hue_shift * 0.5) * brightness, 0, 255).astype(np.uint8)
            b = np.clip(255 * brightness, 0, 255).astype(np.uint8)

            buffer[:, :, 0] = r
            buffer[:, :, 1] = g
            buffer[:, :, 2] = b
        else:
            render_ticker_animated(buffer, "ПОТОК ЧАСТИЦ", t, (200, 150, 255), TickerEffect.SPARKLE_SCROLL)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self._sub_phase == FlowPhase.FLOWING:
            return f" {self._pattern.name[:8]:^14} "
        elif self._sub_phase == FlowPhase.INTRO:
            return "  ПОТОК ЧАСТИЦ  "
        else:
            return "   СКАНИРУЮ...  "

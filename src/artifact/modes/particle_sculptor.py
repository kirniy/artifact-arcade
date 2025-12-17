"""Particle Sculptor Mode - Your face as a living particle sculpture.

Your face dissolves into thousands of particles that respond to forces.
Explode them, swirl them into vortexes, let gravity pull them down,
then watch them reform into your likeness!

Controls:
- LEFT: Change force type (gravity, vortex, explode, attract)
- RIGHT: Apply force burst
- START: Reset particles to face / Capture
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
from artifact.graphics.algorithmic_art import hsv_to_rgb


class ForceType(Enum):
    """Types of forces that can be applied to particles."""
    GRAVITY = auto()       # Particles fall down
    VORTEX = auto()        # Spiral toward center
    EXPLODE = auto()       # Push outward from center
    ATTRACT = auto()       # Pull toward center
    WAVE = auto()          # Sine wave motion
    WIND = auto()          # Horizontal force


class SculptorPhase(Enum):
    """Sculptor mode phases."""
    INTRO = "intro"
    CAPTURE = "capture"
    SCULPTING = "sculpting"
    REFORMING = "reforming"
    SAVED = "saved"


class Particle:
    """A single particle in the sculpture."""
    __slots__ = ['x', 'y', 'home_x', 'home_y', 'vx', 'vy',
                 'color', 'brightness', 'active', 'size']

    def __init__(self, x: float, y: float, color: Tuple[int, int, int], brightness: float):
        self.x = x
        self.y = y
        self.home_x = x
        self.home_y = y
        self.vx = 0.0
        self.vy = 0.0
        self.color = color
        self.brightness = brightness
        self.active = True
        self.size = 1


class ParticleSculptorMode(BaseMode):
    """Interactive particle sculpture mode.

    Creates a particle-based representation of the user's face
    that responds to various forces and can be manipulated.
    """

    name = "particle_sculptor"
    display_name = "СКУЛЬПТОР"
    icon = "particles"
    style = "artistic"

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._sub_phase = SculptorPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0

        # Camera
        self._camera = None
        self._camera_frame: Optional[NDArray] = None

        # Particles
        self._particles: List[Particle] = []
        self._max_particles = 800  # Optimized for Pi 4

        # Force settings
        self._force_type = ForceType.GRAVITY
        self._force_index = 0
        self._force_types = list(ForceType)
        self._force_strength = 0.0
        self._force_active = False

        # Physics settings
        self._friction = 0.98
        self._home_pull = 0.02  # How strongly particles return home

        # Animation
        self._spawn_progress = 0.0
        self._reform_progress = 0.0
        self._explosion_center = (64, 64)

        # Captured image
        self._captured_image: Optional[NDArray] = None

        # Visual effects
        self._glow_phase = 0.0
        self._trail_buffer: Optional[NDArray] = None

    def on_enter(self) -> None:
        """Initialize mode."""
        self._sub_phase = SculptorPhase.INTRO
        self._time_in_phase = 0.0
        self._total_time = 0.0
        self._force_index = 0
        self._force_type = self._force_types[0]
        self._particles = []
        self._spawn_progress = 0.0

        # Initialize trail buffer
        self._trail_buffer = np.zeros((128, 128, 3), dtype=np.uint8)

        # Try to open camera
        try:
            from artifact.simulator.mock_hardware.camera import create_camera
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

    def handle_input(self, event: Event) -> None:
        """Handle user input."""
        if self._sub_phase == SculptorPhase.INTRO:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = SculptorPhase.CAPTURE
                self._time_in_phase = 0.0
            return

        if self._sub_phase == SculptorPhase.SCULPTING:
            if event.type == EventType.ARCADE_LEFT:
                # Cycle force type
                self._force_index = (self._force_index + 1) % len(self._force_types)
                self._force_type = self._force_types[self._force_index]
                self.context.audio.play_ui_click()

            elif event.type == EventType.ARCADE_RIGHT:
                # Apply force burst
                self._apply_force_burst()
                self.context.audio.play_ui_confirm()

            elif event.type == EventType.BUTTON_PRESS:
                # Reset/reform particles or capture
                if self._is_scattered():
                    self._start_reform()
                else:
                    self._capture_sculpture()
                self.context.audio.play_success()

        elif self._sub_phase == SculptorPhase.REFORMING:
            if event.type == EventType.BUTTON_PRESS:
                # Skip to sculpting
                self._sub_phase = SculptorPhase.SCULPTING
                self._time_in_phase = 0.0

        elif self._sub_phase == SculptorPhase.SAVED:
            if event.type == EventType.BUTTON_PRESS:
                self._sub_phase = SculptorPhase.SCULPTING
                self._time_in_phase = 0.0

    def update(self, delta_ms: float) -> None:
        """Update mode state."""
        self._time_in_phase += delta_ms
        self._total_time += delta_ms
        self._glow_phase += delta_ms / 300

        if self._sub_phase == SculptorPhase.INTRO:
            if self._time_in_phase > 2500:
                self._sub_phase = SculptorPhase.CAPTURE
                self._time_in_phase = 0.0

        elif self._sub_phase == SculptorPhase.CAPTURE:
            self._capture_camera()
            if self._camera_frame is not None:
                self._create_particles_from_face()
                self._sub_phase = SculptorPhase.SCULPTING
                self._time_in_phase = 0.0
            elif self._time_in_phase > 3000:
                self._create_demo_particles()
                self._sub_phase = SculptorPhase.SCULPTING
                self._time_in_phase = 0.0

        elif self._sub_phase == SculptorPhase.SCULPTING:
            self._update_particles(delta_ms)

            # Decay force strength
            self._force_strength = max(0, self._force_strength - delta_ms / 500)

        elif self._sub_phase == SculptorPhase.REFORMING:
            self._update_reform(delta_ms)
            if self._reform_progress >= 1.0:
                self._sub_phase = SculptorPhase.SCULPTING
                self._time_in_phase = 0.0

        elif self._sub_phase == SculptorPhase.SAVED:
            if self._time_in_phase > 2500:
                self._sub_phase = SculptorPhase.SCULPTING
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

    def _create_particles_from_face(self):
        """Create particles from camera frame."""
        if self._camera_frame is None:
            return

        self._particles = []

        # Convert to grayscale
        if len(self._camera_frame.shape) == 3:
            gray = np.mean(self._camera_frame, axis=2)
        else:
            gray = self._camera_frame.astype(np.float32)

        # Sample pixels and create particles
        # Use stratified sampling for better coverage
        stride = max(1, int(math.sqrt(128 * 128 / self._max_particles)))

        for y in range(0, 128, stride):
            for x in range(0, 128, stride):
                brightness = gray[y, x] / 255

                # Skip very dark pixels
                if brightness < 0.1:
                    continue

                # Get color from original
                if len(self._camera_frame.shape) == 3:
                    color = tuple(int(c) for c in self._camera_frame[y, x])
                else:
                    v = int(gray[y, x])
                    color = (v, v, v)

                # Add some randomness to position
                px = x + random.uniform(-1, 1)
                py = y + random.uniform(-1, 1)

                self._particles.append(Particle(px, py, color, brightness))

                if len(self._particles) >= self._max_particles:
                    return

    def _create_demo_particles(self):
        """Create demo particles if no camera."""
        self._particles = []
        cx, cy = 64, 64

        # Create circular face pattern
        for _ in range(self._max_particles):
            angle = random.uniform(0, 2 * math.pi)
            dist = random.uniform(0, 45)

            x = cx + dist * math.cos(angle)
            y = cy + dist * math.sin(angle)

            brightness = 1 - (dist / 50)
            hue = (angle / (2 * math.pi)) * 360
            color = hsv_to_rgb(hue, 0.5, brightness)

            self._particles.append(Particle(x, y, color, brightness))

    def _update_particles(self, delta_ms: float):
        """Update particle physics."""
        dt = delta_ms / 16.67  # Normalize to ~60fps

        for particle in self._particles:
            if not particle.active:
                continue

            # Apply current force
            fx, fy = self._get_force(particle)
            particle.vx += fx * dt * self._force_strength
            particle.vy += fy * dt * self._force_strength

            # Apply gentle pull toward home
            dx = particle.home_x - particle.x
            dy = particle.home_y - particle.y
            particle.vx += dx * self._home_pull * dt
            particle.vy += dy * self._home_pull * dt

            # Apply friction
            particle.vx *= self._friction
            particle.vy *= self._friction

            # Update position
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt

            # Bounce off edges
            if particle.x < 0:
                particle.x = 0
                particle.vx = -particle.vx * 0.5
            elif particle.x >= 128:
                particle.x = 127
                particle.vx = -particle.vx * 0.5

            if particle.y < 0:
                particle.y = 0
                particle.vy = -particle.vy * 0.5
            elif particle.y >= 128:
                particle.y = 127
                particle.vy = -particle.vy * 0.5

    def _get_force(self, particle: Particle) -> Tuple[float, float]:
        """Get force vector for a particle."""
        cx, cy = self._explosion_center

        if self._force_type == ForceType.GRAVITY:
            return (0, 0.15)

        elif self._force_type == ForceType.VORTEX:
            dx = particle.x - cx
            dy = particle.y - cy
            dist = max(1, math.sqrt(dx * dx + dy * dy))
            # Tangential force (perpendicular to radius)
            return (-dy / dist * 0.2, dx / dist * 0.2)

        elif self._force_type == ForceType.EXPLODE:
            dx = particle.x - cx
            dy = particle.y - cy
            dist = max(1, math.sqrt(dx * dx + dy * dy))
            force = 3.0 / (dist * 0.1 + 1)
            return (dx / dist * force, dy / dist * force)

        elif self._force_type == ForceType.ATTRACT:
            dx = cx - particle.x
            dy = cy - particle.y
            dist = max(1, math.sqrt(dx * dx + dy * dy))
            return (dx / dist * 0.3, dy / dist * 0.3)

        elif self._force_type == ForceType.WAVE:
            wave = math.sin(particle.y * 0.1 + self._total_time / 200)
            return (wave * 0.3, 0)

        elif self._force_type == ForceType.WIND:
            return (0.2, math.sin(self._total_time / 500) * 0.1)

        return (0, 0)

    def _apply_force_burst(self):
        """Apply a burst of the current force."""
        self._force_strength = 1.0
        self._explosion_center = (64, 64)

        # For explode, add initial velocity
        if self._force_type == ForceType.EXPLODE:
            for particle in self._particles:
                dx = particle.x - 64
                dy = particle.y - 64
                dist = max(1, math.sqrt(dx * dx + dy * dy))
                particle.vx += dx / dist * 3
                particle.vy += dy / dist * 3

    def _is_scattered(self) -> bool:
        """Check if particles are significantly scattered from home."""
        if not self._particles:
            return False

        total_dist = 0
        for p in self._particles:
            dx = p.x - p.home_x
            dy = p.y - p.home_y
            total_dist += math.sqrt(dx * dx + dy * dy)

        avg_dist = total_dist / len(self._particles)
        return avg_dist > 15

    def _start_reform(self):
        """Start reforming particles to their home positions."""
        self._sub_phase = SculptorPhase.REFORMING
        self._reform_progress = 0.0
        self._time_in_phase = 0.0
        self._home_pull = 0.15  # Stronger pull during reform

    def _update_reform(self, delta_ms: float):
        """Update reform animation."""
        self._reform_progress = min(1.0, self._reform_progress + delta_ms / 1500)
        self._update_particles(delta_ms)

        # Check if reformed
        if self._reform_progress >= 1.0:
            self._home_pull = 0.02  # Reset to normal

    def _capture_sculpture(self):
        """Capture current sculpture state."""
        self._captured_image = self._trail_buffer.copy()
        self._sub_phase = SculptorPhase.SAVED
        self._time_in_phase = 0.0

    # =========================================================================
    # RENDERING
    # =========================================================================

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        t = self._time_in_phase

        if self._sub_phase == SculptorPhase.INTRO:
            self._render_intro(buffer, t)
        elif self._sub_phase == SculptorPhase.CAPTURE:
            self._render_capture_phase(buffer, t)
        elif self._sub_phase in (SculptorPhase.SCULPTING, SculptorPhase.REFORMING):
            self._render_sculpting(buffer, t)
        elif self._sub_phase == SculptorPhase.SAVED:
            self._render_saved(buffer, t)

    def _render_intro(self, buffer: NDArray[np.uint8], t: float):
        """Render intro screen."""
        fill(buffer, (10, 5, 20))

        # Animated particle preview
        cx, cy = 64, 64
        num_preview = 100
        for i in range(num_preview):
            angle = t / 500 + i * 0.063
            dist = 30 + 15 * math.sin(t / 300 + i * 0.1)
            px = int(cx + dist * math.cos(angle))
            py = int(cy + dist * math.sin(angle))

            if 0 <= px < 128 and 0 <= py < 128:
                hue = (i * 3.6 + t / 5) % 360
                buffer[py, px] = hsv_to_rgb(hue, 0.8, 0.9)

                # Add some neighboring pixels for glow
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        nx, ny = px + dx, py + dy
                        if 0 <= nx < 128 and 0 <= ny < 128:
                            existing = buffer[ny, nx]
                            glow = hsv_to_rgb(hue, 0.4, 0.3)
                            buffer[ny, nx] = tuple(max(e, g) for e, g in zip(existing, glow))

        # Title
        draw_centered_text(buffer, "СКУЛЬПТОР", 20, (200, 150, 255), scale=2)
        draw_centered_text(buffer, "ЧАСТИЦ", 45, (150, 200, 255), scale=2)

        # Instructions
        draw_centered_text(buffer, "ВЗРЫВАЙ, КРУТИ,", 80, (150, 150, 200), scale=1)
        draw_centered_text(buffer, "ТВОРИ ХАОС!", 95, (150, 150, 200), scale=1)

        draw_animated_text(buffer, "НАЖМИ СТАРТ", 115, (100, 100, 150), t, TextEffect.PULSE, scale=1)

    def _render_capture_phase(self, buffer: NDArray[np.uint8], t: float):
        """Render camera capture phase."""
        fill(buffer, (20, 10, 30))

        # Pulsing capture indicator
        pulse = 0.5 + 0.5 * math.sin(t / 150)
        draw_circle(buffer, 64, 64, int(40 * pulse), (100, 50, 150))
        draw_circle(buffer, 64, 64, int(30 * pulse), (150, 80, 200))

        # Scanning effect
        scan_y = int((t / 30) % 128)
        for x in range(128):
            if 0 <= scan_y < 128:
                buffer[scan_y, x] = (200, 100, 255)

        draw_centered_text(buffer, "СКАНИРУЮ", 55, (200, 150, 255), scale=2)
        draw_centered_text(buffer, "ЛИЦО...", 80, (150, 100, 200), scale=1)

    def _render_sculpting(self, buffer: NDArray[np.uint8], t: float):
        """Render sculpting view."""
        # Fade trail buffer
        self._trail_buffer = (self._trail_buffer.astype(np.float32) * 0.85).astype(np.uint8)

        # Render particles to trail buffer
        for particle in self._particles:
            if not particle.active:
                continue

            px, py = int(particle.x), int(particle.y)
            if 0 <= px < 128 and 0 <= py < 128:
                # Particle color with velocity-based intensity
                speed = math.sqrt(particle.vx ** 2 + particle.vy ** 2)
                intensity = min(1.0, 0.5 + speed * 0.3)

                color = tuple(int(c * intensity) for c in particle.color)
                self._trail_buffer[py, px] = color

                # Glow for fast particles
                if speed > 1:
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            nx, ny = px + dx, py + dy
                            if 0 <= nx < 128 and 0 <= ny < 128:
                                glow_color = tuple(int(c * 0.3) for c in particle.color)
                                existing = self._trail_buffer[ny, nx]
                                self._trail_buffer[ny, nx] = tuple(
                                    max(e, g) for e, g in zip(existing, glow_color)
                                )

        # Copy to main buffer
        np.copyto(buffer, self._trail_buffer)

        # UI overlay
        force_names = {
            ForceType.GRAVITY: "ГРАВИТ",
            ForceType.VORTEX: "ВИХРЬ",
            ForceType.EXPLODE: "ВЗРЫВ",
            ForceType.ATTRACT: "ПРИТЯЖ",
            ForceType.WAVE: "ВОЛНА",
            ForceType.WIND: "ВЕТЕР",
        }

        # Force indicator
        draw_rect(buffer, 0, 0, 50, 12, (0, 0, 0))
        force_text = force_names.get(self._force_type, "?")
        color = (255, 150, 200) if self._force_strength > 0.1 else (150, 100, 150)
        draw_text_bitmap(buffer, force_text, 2, 2, color, load_font("cyrillic"), scale=1)

        # Particle count
        count_text = f"{len(self._particles)}"
        draw_rect(buffer, 100, 0, 28, 12, (0, 0, 0))
        draw_text_bitmap(buffer, count_text, 102, 2, (100, 200, 255),
                        load_font("cyrillic"), scale=1)

        # Reform indicator
        if self._sub_phase == SculptorPhase.REFORMING:
            progress = int(self._reform_progress * 100)
            draw_rect(buffer, 30, 55, 68, 18, (0, 0, 0))
            draw_centered_text(buffer, f"СБОРКА {progress}%", 58, (200, 200, 255), scale=1)

        # Hint
        hint_alpha = 0.4 + 0.2 * math.sin(t / 400)
        hint_color = tuple(int(c * hint_alpha) for c in (100, 150, 100))
        draw_centered_text(buffer, "<СИЛА  ТОЛЧОК>", 118, hint_color, scale=1)

    def _render_saved(self, buffer: NDArray[np.uint8], t: float):
        """Render saved confirmation."""
        if self._captured_image is not None:
            np.copyto(buffer, self._captured_image)

        # Flash effect
        flash = max(0, 1 - t / 300)
        if flash > 0:
            buffer[:] = np.clip(buffer.astype(np.int16) + int(150 * flash), 0, 255).astype(np.uint8)

        # Confirmation
        draw_rect(buffer, 15, 48, 98, 32, (0, 0, 0))
        draw_centered_text(buffer, "ШЕДЕВР!", 55, (200, 150, 255), scale=2)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display with particle visualization."""
        from artifact.graphics.primitives import clear

        clear(buffer)

        if self._sub_phase == SculptorPhase.SCULPTING:
            # Show particle velocity as a bar graph
            # Sample some particles and show their speed
            if self._particles:
                num_samples = min(48, len(self._particles))
                step = max(1, len(self._particles) // num_samples)

                for i in range(num_samples):
                    idx = (i * step) % len(self._particles)
                    particle = self._particles[idx]

                    speed = math.sqrt(particle.vx ** 2 + particle.vy ** 2)
                    height = min(8, int(speed * 2))

                    for y in range(8 - height, 8):
                        hue = (particle.x * 2 + particle.y + self._total_time / 10) % 360
                        buffer[y, i] = hsv_to_rgb(hue, 0.8, 0.9)

        elif self._sub_phase == SculptorPhase.REFORMING:
            # Progress bar
            progress_width = int(48 * self._reform_progress)
            for x in range(progress_width):
                for y in range(8):
                    hue = (x * 5 + self._total_time / 10) % 360
                    buffer[y, x] = hsv_to_rgb(hue, 0.6, 0.8)

        else:
            # Idle animation
            for x in range(48):
                wave = int(3 + 3 * math.sin(x * 0.2 + self._total_time / 200))
                for y in range(8 - wave, 8):
                    buffer[y, x] = (150, 100, 200)

    def get_lcd_text(self) -> str:
        """Get LCD text - shows current force."""
        if self._sub_phase == SculptorPhase.INTRO:
            return " СКУЛЬПТОР    "

        elif self._sub_phase == SculptorPhase.CAPTURE:
            return "  СКАНИРУЮ... "

        elif self._sub_phase == SculptorPhase.SCULPTING:
            force_names = {
                ForceType.GRAVITY: "ГРАВИТАЦИЯ",
                ForceType.VORTEX: "ВИХРЬ",
                ForceType.EXPLODE: "ВЗРЫВ",
                ForceType.ATTRACT: "ПРИТЯЖЕНИЕ",
                ForceType.WAVE: "ВОЛНА",
                ForceType.WIND: "ВЕТЕР",
            }
            name = force_names.get(self._force_type, "СИЛА")
            return f" {name:^14} "

        elif self._sub_phase == SculptorPhase.REFORMING:
            progress = int(self._reform_progress * 100)
            return f" СБОРКА: {progress:3d}%  "

        elif self._sub_phase == SculptorPhase.SAVED:
            return "   ШЕДЕВР!    "

        return "  СКУЛЬПТОР   "

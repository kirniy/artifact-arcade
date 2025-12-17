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
        # Nebula clouds
        self.nebula_clouds: List[dict] = []
        self._generate_nebula_clouds(15)
        # Shooting stars
        self.shooting_stars: List[dict] = []
        # Energy particles orbiting portal
        self.portal_particles: List[dict] = []
        self._generate_portal_particles(20)

    def _generate_stars(self, count: int):
        """Generate star field for cosmic portal."""
        self.stars = []
        for _ in range(count):
            # [x, y, z (depth), brightness, speed, twinkle_phase]
            self.stars.append([
                random.uniform(-64, 64),
                random.uniform(-64, 64),
                random.uniform(1, 64),
                random.uniform(0.3, 1.0),
                random.uniform(0.5, 2.0),
                random.uniform(0, 2 * math.pi)  # twinkle phase
            ])

    def _generate_nebula_clouds(self, count: int):
        """Generate nebula cloud particles."""
        self.nebula_clouds = []
        for _ in range(count):
            self.nebula_clouds.append({
                "x": random.uniform(-80, 80),
                "y": random.uniform(-80, 80),
                "size": random.uniform(20, 50),
                "hue": random.choice([280, 200, 320, 180]),  # purples, blues, pinks
                "drift_x": random.uniform(-0.02, 0.02),
                "drift_y": random.uniform(-0.02, 0.02),
                "alpha": random.uniform(0.1, 0.3),
                "pulse_phase": random.uniform(0, 2 * math.pi),
            })

    def _generate_portal_particles(self, count: int):
        """Generate particles orbiting the portal."""
        self.portal_particles = []
        for i in range(count):
            angle = (i / count) * 2 * math.pi
            self.portal_particles.append({
                "angle": angle,
                "radius": random.uniform(25, 55),
                "speed": random.uniform(0.5, 1.5),
                "size": random.randint(1, 3),
                "hue": random.randint(180, 300),
            })

    def _init_camera_mirror(self):
        """Initialize camera mirror scene state."""
        self._camera = None
        self._camera_frame = None
        self._camera_effect = "normal"  # normal, negative, blur, edge, pixelate
        self._effect_time = 0.0
        self._effect_index = 0
        self._effects = ["normal", "negative", "edge", "pixelate", "scanline", "thermal", "vhs"]
        self._glitch_lines: List[int] = []
        self._scanline_offset = 0.0
        self._frame_buffer = None
        # VHS effect state
        self._vhs_tracking = 0.0
        self._vhs_noise_lines: List[Tuple[int, float]] = []
        # Thermal color map
        self._thermal_colors = [
            (0, 0, 30), (0, 0, 100), (60, 0, 130), (150, 0, 80),
            (200, 50, 0), (255, 100, 0), (255, 200, 50), (255, 255, 200)
        ]
        # Camera stays closed until scene is entered to avoid startup failures

    def _open_camera(self) -> None:
        """Attempt to open the simulator camera lazily."""
        if self._camera is not None:
            return
        try:
            from artifact.simulator.mock_hardware.camera import create_camera
            cam = create_camera(resolution=(128, 128))
            cam.open()
            self._camera = cam
        except Exception:
            self._camera = None

    def _close_camera(self) -> None:
        """Close and release the camera."""
        if self._camera:
            try:
                self._camera.close()
            except Exception:
                pass
        self._camera = None
        self._camera_frame = None

    def _init_matrix_rain(self):
        """Initialize matrix rain scene state."""
        self.columns: List[dict] = []
        self._generate_columns()
        # Lightning effects
        self.lightning_active = False
        self.lightning_timer = 0.0
        self.lightning_duration = 0.0
        self.lightning_branches: List[List[Tuple[int, int]]] = []
        # Background glow spots
        self.glow_spots: List[dict] = []
        self._generate_glow_spots(8)
        # Data stream particles
        self.data_particles: List[dict] = []

    def _generate_columns(self):
        """Generate matrix rain columns."""
        self.columns = []
        for x in range(0, 128, 8):
            self.columns.append({
                "x": x,
                "y": random.uniform(-50, 0),
                "speed": random.uniform(50, 150),
                "chars": [random.choice("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789αβγδεζηθικλμνξπρστυφχψω")
                         for _ in range(15)],
                "length": random.randint(8, 15),
                "brightness": random.uniform(0.7, 1.0),
            })

    def _generate_glow_spots(self, count: int):
        """Generate background glow spots for matrix scene."""
        self.glow_spots = []
        for _ in range(count):
            self.glow_spots.append({
                "x": random.randint(0, 127),
                "y": random.randint(0, 127),
                "radius": random.randint(15, 35),
                "pulse_phase": random.uniform(0, 2 * math.pi),
                "intensity": random.uniform(0.1, 0.25),
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
                previous_scene = self.state.current_scene
                self._on_scene_exit(previous_scene)
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
            self._vhs_tracking = 0.0
            self._vhs_noise_lines = []
            self._glitch_lines = []
            # Re-open camera if needed
            self._open_camera()
        elif scene == IdleScene.MATRIX_RAIN:
            self._generate_columns()
            self._generate_glow_spots(8)
            self.lightning_active = False
            self.lightning_timer = random.uniform(1000, 3000)
            self.lightning_branches = []
            self.data_particles = []
        elif scene == IdleScene.COSMIC_PORTAL:
            self._generate_stars(100)
            self._generate_nebula_clouds(15)
            self._generate_portal_particles(20)
            self.shooting_stars = []
        elif scene == IdleScene.MYSTICAL_EYE:
            self._init_mystical_eye()

    def _on_scene_exit(self, scene: IdleScene) -> None:
        """Cleanup when leaving a scene."""
        if scene == IdleScene.CAMERA_MIRROR:
            self._close_camera()

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
        t = self.state.scene_time

        # Rotate portal
        self.portal_rotation += delta_ms / 50
        self.portal_pulse = math.sin(t / 300) * 0.3 + 0.7

        # Move stars toward camera (z decreases) with twinkle
        for star in self.stars:
            star[2] -= star[4] * delta_ms / 16
            star[5] += delta_ms / 200  # Update twinkle phase
            if star[2] <= 0:
                # Reset star to far distance
                star[0] = random.uniform(-64, 64)
                star[1] = random.uniform(-64, 64)
                star[2] = 64
                star[3] = random.uniform(0.3, 1.0)
                star[5] = random.uniform(0, 2 * math.pi)

        # Update nebula clouds (slow drift)
        for cloud in self.nebula_clouds:
            cloud["x"] += cloud["drift_x"] * delta_ms
            cloud["y"] += cloud["drift_y"] * delta_ms
            # Wrap around
            if cloud["x"] < -100:
                cloud["x"] = 100
            elif cloud["x"] > 100:
                cloud["x"] = -100
            if cloud["y"] < -100:
                cloud["y"] = 100
            elif cloud["y"] > 100:
                cloud["y"] = -100

        # Update portal particles (orbit)
        for particle in self.portal_particles:
            particle["angle"] += particle["speed"] * delta_ms / 500

        # Spawn shooting stars occasionally
        if random.random() < 0.005:  # ~5% chance per frame
            self.shooting_stars.append({
                "x": random.uniform(-20, 128),
                "y": random.uniform(-20, 40),
                "vx": random.uniform(2, 5),
                "vy": random.uniform(1, 3),
                "length": random.randint(8, 20),
                "life": 1.0,
            })

        # Update shooting stars
        for star in self.shooting_stars:
            star["x"] += star["vx"] * delta_ms / 16
            star["y"] += star["vy"] * delta_ms / 16
            star["life"] -= delta_ms / 800

        # Remove dead shooting stars
        self.shooting_stars = [s for s in self.shooting_stars if s["life"] > 0]

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
        t = self.state.scene_time

        # Update columns
        for col in self.columns:
            col["y"] += col["speed"] * delta_ms / 1000
            if col["y"] > 128 + col["length"] * 8:
                col["y"] = random.uniform(-80, -20)
                col["speed"] = random.uniform(50, 150)
                col["chars"] = [random.choice("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789αβγδεζηθικλμνξπρστυφχψω")
                               for _ in range(15)]
                col["brightness"] = random.uniform(0.7, 1.0)

            # Randomly mutate characters
            if random.random() < 0.02:
                idx = random.randint(0, len(col["chars"]) - 1)
                col["chars"][idx] = random.choice("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ0123456789αβγδεζηθικλμνξπρστυφχψω")

        # Lightning logic
        self.lightning_timer -= delta_ms
        if self.lightning_active:
            self.lightning_duration -= delta_ms
            if self.lightning_duration <= 0:
                self.lightning_active = False
                self.lightning_branches = []
        elif self.lightning_timer <= 0:
            # Spawn new lightning
            if random.random() < 0.15:  # 15% chance when timer expires
                self.lightning_active = True
                self.lightning_duration = random.uniform(80, 200)
                self._generate_lightning_branches()
            self.lightning_timer = random.uniform(2000, 5000)

        # Spawn data particles occasionally
        if random.random() < 0.08:
            self.data_particles.append({
                "x": random.randint(0, 127),
                "y": 0,
                "speed": random.uniform(80, 200),
                "char": random.choice("01"),
                "life": 1.0,
            })

        # Update data particles
        for particle in self.data_particles:
            particle["y"] += particle["speed"] * delta_ms / 1000
            particle["life"] -= delta_ms / 1500

        # Remove dead particles
        self.data_particles = [p for p in self.data_particles if p["life"] > 0 and p["y"] < 128]

    def _generate_lightning_branches(self):
        """Generate lightning bolt branches."""
        self.lightning_branches = []
        # Main bolt
        start_x = random.randint(20, 108)
        x, y = start_x, 0
        main_branch = [(x, y)]

        while y < 128:
            y += random.randint(5, 15)
            x += random.randint(-10, 10)
            x = max(5, min(122, x))
            main_branch.append((x, y))

            # Spawn sub-branches occasionally
            if random.random() < 0.3:
                sub_branch = [(x, y)]
                sub_x, sub_y = x, y
                branch_dir = random.choice([-1, 1])
                for _ in range(random.randint(2, 5)):
                    sub_y += random.randint(3, 8)
                    sub_x += branch_dir * random.randint(3, 10)
                    sub_x = max(0, min(127, sub_x))
                    sub_branch.append((sub_x, sub_y))
                self.lightning_branches.append(sub_branch)

        self.lightning_branches.append(main_branch)

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
        """Render the mystical all-seeing eye with enhanced effects."""
        fill(buffer, (20, 15, 40))
        t = self.state.scene_time
        cx, cy = 64, 64

        # Background energy particles
        for i in range(30):
            particle_angle = (t / 500 + i * 0.2) % (2 * math.pi)
            particle_r = 45 + 15 * math.sin(t / 300 + i)
            px = int(cx + particle_r * math.cos(particle_angle))
            py = int(cy + particle_r * math.sin(particle_angle))
            if 0 <= px < 128 and 0 <= py < 128:
                brightness = 0.3 + 0.3 * math.sin(t / 100 + i * 0.5)
                buffer[py, px] = (int(147 * brightness), int(51 * brightness), int(234 * brightness))

        # Outer mystical aura - multiple layers with improved effects
        for ring in range(6):
            ring_r = 58 - ring * 5
            hue = (t / 15 + ring * 25) % 360
            base_brightness = 0.35 - ring * 0.04

            for angle in range(0, 360, 2):
                rad = math.radians(angle + t / 8)
                wobble = math.sin(rad * 4 + t / 150) * 3
                pulse = 1 + 0.1 * math.sin(t / 200 + ring)

                final_r = (ring_r + wobble) * pulse
                px = int(cx + final_r * math.cos(rad))
                py = int(cy + final_r * math.sin(rad))

                if 0 <= px < 128 and 0 <= py < 128:
                    angle_brightness = base_brightness * (0.7 + 0.3 * math.sin(rad * 2 + t / 100))
                    ring_color = hsv_to_rgb(hue, 0.8, angle_brightness)
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

        # Title with glow effect - safe Y positions
        draw_animated_text(buffer, "VNVNC", 8, self.gold, t, TextEffect.GLOW, scale=2)
        draw_animated_text(buffer, "НАЖМИ СТАРТ", 114, self.teal, t, TextEffect.PULSE, scale=1)

    def _render_cosmic_portal_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render swirling cosmic portal with stars, nebulae, and shooting stars."""
        fill(buffer, (5, 5, 15))
        t = self.state.scene_time
        cx, cy = 64, 64

        # Layer 1: Nebula clouds (background)
        for cloud in self.nebula_clouds:
            cloud_x = int(cx + cloud["x"])
            cloud_y = int(cy + cloud["y"])
            size = int(cloud["size"])
            pulse = 0.8 + 0.2 * math.sin(t / 500 + cloud["pulse_phase"])
            alpha = cloud["alpha"] * pulse

            # Draw soft gradient cloud
            for dy in range(-size, size + 1, 2):
                for dx in range(-size, size + 1, 2):
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < size:
                        px, py = cloud_x + dx, cloud_y + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            falloff = (1 - dist / size) ** 2 * alpha
                            color = hsv_to_rgb(cloud["hue"], 0.6, falloff * 0.4)
                            # Blend with existing
                            existing = buffer[py, px]
                            buffer[py, px] = (
                                min(255, existing[0] + color[0]),
                                min(255, existing[1] + color[1]),
                                min(255, existing[2] + color[2]),
                            )

        # Layer 2: Star field (3D projection) with twinkle
        for star in self.stars:
            sx, sy, sz = star[0], star[1], star[2]
            twinkle = star[5] if len(star) > 5 else 0
            # Project 3D to 2D
            if sz > 0:
                px = int(cx + sx * 64 / sz)
                py = int(cy + sy * 64 / sz)

                if 0 <= px < 128 and 0 <= py < 128:
                    # Brightness based on depth with twinkle
                    base_brightness = star[3] * (1 - sz / 64)
                    twinkle_mod = 0.7 + 0.3 * math.sin(twinkle)
                    brightness = base_brightness * twinkle_mod
                    size = max(1, int(3 * (1 - sz / 64)))

                    # Slight color variation
                    r = int(255 * brightness)
                    g = int(255 * brightness * 0.95)
                    b = int(255 * brightness)
                    color = (r, g, b)

                    if size == 1:
                        buffer[py, px] = color
                    else:
                        draw_circle(buffer, px, py, size, color)

        # Layer 3: Shooting stars
        for star in self.shooting_stars:
            alpha = star["life"]
            length = int(star["length"] * alpha)
            x, y = int(star["x"]), int(star["y"])
            # Draw trail
            for i in range(length):
                trail_x = int(x - star["vx"] * i * 0.3)
                trail_y = int(y - star["vy"] * i * 0.3)
                if 0 <= trail_x < 128 and 0 <= trail_y < 128:
                    fade = (1 - i / length) * alpha
                    color = (int(255 * fade), int(255 * fade), int(200 * fade))
                    buffer[trail_y, trail_x] = color

        # Layer 4: Portal particles (orbiting energy)
        for particle in self.portal_particles:
            angle = particle["angle"]
            radius = particle["radius"] + 5 * math.sin(t / 200 + angle * 2)
            px = int(cx + radius * math.cos(angle))
            py = int(cy + radius * math.sin(angle))

            if 0 <= px < 128 and 0 <= py < 128:
                brightness = 0.6 + 0.4 * math.sin(t / 100 + angle)
                color = hsv_to_rgb(particle["hue"], 0.9, brightness)
                size = particle["size"]
                if size == 1:
                    buffer[py, px] = color
                else:
                    draw_circle(buffer, px, py, size, color)

        # Layer 5: Portal rings (concentric spirals with improved effects)
        for ring in range(10):
            ring_base_r = 8 + ring * 5
            ring_r = ring_base_r + 3 * math.sin(t / 200 + ring)
            hue = (t / 5 + ring * 35) % 360

            for angle in range(0, 360, 2):
                rad = math.radians(angle + self.portal_rotation + ring * 12)
                # Spiral distortion with more dynamic movement
                spiral_r = ring_r + 5 * math.sin(rad * 4 + t / 80) + 2 * math.cos(rad * 2 - t / 120)

                px = int(cx + spiral_r * math.cos(rad))
                py = int(cy + spiral_r * math.sin(rad))

                if 0 <= px < 128 and 0 <= py < 128:
                    brightness = 0.4 + 0.6 * math.sin(angle / 25 + t / 100)
                    color = hsv_to_rgb(hue, 0.85, brightness * self.portal_pulse)
                    # Additive blend
                    existing = buffer[py, px]
                    buffer[py, px] = (
                        min(255, existing[0] + color[0] // 2),
                        min(255, existing[1] + color[1] // 2),
                        min(255, existing[2] + color[2] // 2),
                    )

        # Layer 6: Central glow with pulsing core
        pulse_intensity = 0.8 + 0.2 * math.sin(t / 150)
        for r in range(20, 0, -1):
            alpha = ((20 - r) / 20) ** 1.5 * pulse_intensity
            # Multi-color glow (purple/blue/white gradient)
            if r < 5:
                glow_color = (int(200 * alpha), int(180 * alpha), int(255 * alpha))
            elif r < 12:
                glow_color = (int(120 * alpha), int(60 * alpha), int(180 * alpha))
            else:
                glow_color = (int(60 * alpha), int(30 * alpha), int(100 * alpha))
            draw_circle(buffer, cx, cy, r, glow_color)

        # Layer 7: Core sparkle
        for i in range(5):
            sparkle_angle = t / 100 + i * math.pi * 2 / 5
            sparkle_r = 3 + 2 * math.sin(t / 80 + i)
            sx = int(cx + sparkle_r * math.cos(sparkle_angle))
            sy = int(cy + sparkle_r * math.sin(sparkle_angle))
            if 0 <= sx < 128 and 0 <= sy < 128:
                buffer[sy, sx] = (255, 255, 255)

        # Title - safe Y positions
        draw_animated_text(buffer, "VNVNC", 8, self.pink, t, TextEffect.GLOW, scale=2)
        draw_animated_text(buffer, "ПОРТАЛ СУДЬБЫ", 114, self.blue, t, TextEffect.WAVE, scale=1)

    def _render_camera_mirror_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render camera with fun visual effects."""
        t = self.state.scene_time

        # If no camera frame, show a placeholder with animated visual
        if self._camera_frame is None:
            fill(buffer, (30, 20, 50))
            # Draw animated placeholder
            cx, cy = 64, 64
            # Pulsing circle representing camera
            pulse = 0.7 + 0.3 * math.sin(t / 200)
            for r in range(25, 10, -3):
                alpha = (25 - r) / 15 * pulse
                color = (int(20 * alpha), int(184 * alpha), int(166 * alpha))
                draw_circle(buffer, cx, cy, r, color)
            # Camera icon in center
            draw_rect(buffer, 54, 54, 20, 16, (100, 100, 100))
            draw_circle(buffer, 64, 62, 5, (150, 150, 150))
            draw_circle(buffer, 64, 62, 3, (50, 50, 50))
            draw_animated_text(buffer, "ЗЕРКАЛО", 85, self.teal, t, TextEffect.WAVE, scale=2)
            draw_animated_text(buffer, "КАМЕРА...", 108, self.pink, t, TextEffect.PULSE, scale=1)
            return

        # Resize camera frame to 128x128 if needed
        frame = self._camera_frame.copy()
        if frame.shape[:2] != (128, 128):
            from PIL import Image
            img = Image.fromarray(frame)
            img = img.resize((128, 128), Image.Resampling.NEAREST)
            frame = np.array(img)

        # Apply the current effect
        effect = self._camera_effect

        if effect == "negative":
            # Negative/inverted colors with slight color shift
            frame = 255 - frame
            # Add slight cyan tint
            frame[:, :, 1] = np.clip(frame[:, :, 1].astype(np.int16) + 20, 0, 255).astype(np.uint8)
            frame[:, :, 2] = np.clip(frame[:, :, 2].astype(np.int16) + 30, 0, 255).astype(np.uint8)

        elif effect == "edge":
            # Edge detection effect (neon pink/cyan colors)
            gray = np.mean(frame, axis=2).astype(np.uint8)
            # Sobel-like edge detection
            edges_v = np.zeros_like(gray)
            edges_h = np.zeros_like(gray)
            edges_v[1:, :] = np.abs(gray[1:, :].astype(np.int16) - gray[:-1, :].astype(np.int16))
            edges_h[:, 1:] = np.abs(gray[:, 1:].astype(np.int16) - gray[:, :-1].astype(np.int16))
            edges = np.clip(edges_v + edges_h, 0, 255).astype(np.uint8)
            # Neon coloring based on edge intensity
            frame = np.zeros((128, 128, 3), dtype=np.uint8)
            # Cyan for vertical edges, pink for horizontal
            frame[:, :, 0] = np.clip(edges_h * 1.5, 0, 255).astype(np.uint8)  # Pink-ish red
            frame[:, :, 1] = edges_v  # Cyan green
            frame[:, :, 2] = edges  # Combined blue

        elif effect == "pixelate":
            # Pixelate effect with color posterization
            pixel_size = 8
            for py in range(0, 128, pixel_size):
                for px in range(0, 128, pixel_size):
                    block = frame[py:py+pixel_size, px:px+pixel_size]
                    avg_color = block.mean(axis=(0, 1)).astype(np.uint8)
                    # Posterize to fewer colors
                    avg_color = (avg_color // 64) * 64 + 32
                    frame[py:py+pixel_size, px:px+pixel_size] = avg_color

        elif effect == "scanline":
            # CRT scanline effect with purple tint and curvature
            for y in range(0, 128, 2):
                frame[y, :] = (frame[y, :].astype(np.int16) * 0.5).astype(np.uint8)
            # Add purple tint
            frame[:, :, 0] = np.clip(frame[:, :, 0].astype(np.int16) + 40, 0, 255).astype(np.uint8)
            frame[:, :, 2] = np.clip(frame[:, :, 2].astype(np.int16) + 60, 0, 255).astype(np.uint8)
            # Vignette effect
            for y in range(128):
                for x in range(128):
                    dist = math.sqrt((x - 64) ** 2 + (y - 64) ** 2) / 90
                    if dist > 0.5:
                        darken = min(1.0, (dist - 0.5) * 2)
                        frame[y, x] = (frame[y, x].astype(np.float32) * (1 - darken * 0.5)).astype(np.uint8)

        elif effect == "thermal":
            # Thermal vision effect
            gray = np.mean(frame, axis=2).astype(np.uint8)
            thermal_frame = np.zeros((128, 128, 3), dtype=np.uint8)
            for y in range(128):
                for x in range(128):
                    intensity = gray[y, x]
                    # Map to thermal color
                    idx = int(intensity / 32)
                    idx = min(7, max(0, idx))
                    thermal_frame[y, x] = self._thermal_colors[idx]
            frame = thermal_frame

        elif effect == "vhs":
            # VHS distortion effect
            # Horizontal shift with tracking issues
            self._vhs_tracking += 0.1
            tracking_offset = int(5 * math.sin(self._vhs_tracking))

            # Chromatic aberration
            shifted_frame = np.zeros_like(frame)
            shifted_frame[:, 2:, 0] = frame[:, :-2, 0]  # Red shifted right
            shifted_frame[:, :, 1] = frame[:, :, 1]  # Green centered
            shifted_frame[:, :-2, 2] = frame[:, 2:, 2]  # Blue shifted left
            frame = shifted_frame

            # Add noise lines
            if random.random() < 0.1:
                self._vhs_noise_lines = [(random.randint(0, 127), random.uniform(0.5, 1.0)) for _ in range(random.randint(1, 4))]
            for line_y, intensity in self._vhs_noise_lines:
                if 0 <= line_y < 128:
                    noise = np.random.randint(0, int(100 * intensity), (128, 3), dtype=np.uint8)
                    frame[line_y, :] = np.clip(frame[line_y, :].astype(np.int16) + noise - 50, 0, 255).astype(np.uint8)

            # Tracking bar at bottom
            bar_height = 8 + int(4 * math.sin(t / 100))
            bar_y = 128 - bar_height + tracking_offset
            if 0 <= bar_y < 128:
                for y in range(max(0, bar_y), min(128, bar_y + bar_height)):
                    frame[y, :] = np.clip(frame[y, :].astype(np.int16) + 80, 0, 255).astype(np.uint8)

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
            "scanline": "РЕТРО",
            "thermal": "ТЕПЛО",
            "vhs": "VHS",
        }
        effect_text = effect_names.get(effect, "ЭФФЕКТ")

        # Dark bar for text at safe bottom position
        draw_rect(buffer, 0, 108, 128, 20, (0, 0, 0))
        draw_centered_text(buffer, effect_text, 110, self.teal, scale=1)

        # Title at top
        draw_rect(buffer, 0, 0, 128, 14, (0, 0, 0))
        draw_centered_text(buffer, "НАЖМИ СТАРТ", 4, self.pink, scale=1)

    def _render_matrix_rain_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render matrix-style character rain with lightning and glow effects."""
        t = self.state.scene_time
        font = load_font("cyrillic")

        # Layer 0: Dark background with subtle gradient
        for y in range(128):
            intensity = int(5 + 3 * (y / 128))
            for x in range(128):
                buffer[y, x] = (0, intensity, 0)

        # Layer 1: Background glow spots
        for spot in self.glow_spots:
            spot_x, spot_y = spot["x"], spot["y"]
            radius = spot["radius"]
            pulse = 0.7 + 0.3 * math.sin(t / 400 + spot["pulse_phase"])
            intensity = spot["intensity"] * pulse

            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < radius:
                        px, py = spot_x + dx, spot_y + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            falloff = (1 - dist / radius) ** 2 * intensity
                            existing = buffer[py, px]
                            buffer[py, px] = (
                                existing[0],
                                min(255, existing[1] + int(60 * falloff)),
                                existing[2],
                            )

        # Layer 2: Draw each column
        for col in self.columns:
            x = col["x"]
            base_y = int(col["y"])
            col_brightness = col.get("brightness", 1.0)

            for i, char in enumerate(col["chars"][:col["length"]]):
                y = base_y - i * 8

                if 0 <= y < 128:
                    # Brightness gradient (brightest at head)
                    if i == 0:
                        # Glowing white-green head
                        color = (180, 255, 180)
                    elif i == 1:
                        # Bright green second character
                        color = (100, 255, 100)
                    else:
                        fade = (1 - i / col["length"]) * col_brightness
                        color = (0, int(180 * fade), int(20 * fade))

                    draw_text_bitmap(buffer, char, x, y, color, font, scale=1)

        # Layer 3: Data particles (falling 01s)
        for particle in self.data_particles:
            px = int(particle["x"])
            py = int(particle["y"])
            if 0 <= px < 128 and 0 <= py < 128:
                intensity = particle["life"]
                color = (int(100 * intensity), int(255 * intensity), int(100 * intensity))
                draw_text_bitmap(buffer, particle["char"], px, py, color, font, scale=1)

        # Layer 4: Lightning effect
        if self.lightning_active:
            # Flash the whole screen slightly
            flash_intensity = 30 if random.random() < 0.5 else 15
            for y in range(128):
                for x in range(128):
                    existing = buffer[y, x]
                    buffer[y, x] = (
                        min(255, existing[0] + flash_intensity),
                        min(255, existing[1] + flash_intensity),
                        min(255, existing[2] + flash_intensity),
                    )

            # Draw lightning branches
            for branch in self.lightning_branches:
                for i in range(len(branch) - 1):
                    x1, y1 = branch[i]
                    x2, y2 = branch[i + 1]
                    # Draw thick lightning line
                    draw_line(buffer, x1, y1, x2, y2, (200, 255, 200))
                    # Core glow
                    draw_line(buffer, x1, y1, x2, y2, (255, 255, 255))

        # Layer 5: Scanline effect overlay
        for y in range(0, 128, 3):
            for x in range(128):
                existing = buffer[y, x]
                buffer[y, x] = (
                    int(existing[0] * 0.85),
                    int(existing[1] * 0.85),
                    int(existing[2] * 0.85),
                )

        # Layer 6: Glowing title overlay
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
        self._close_camera()
        self.state = SceneState()
        # Re-randomize scene order on reset/reboot
        random.shuffle(self.scenes)
        self.scene_index = 0
        self.state.current_scene = self.scenes[0]
        self._init_mystical_eye()
        self._init_cosmic_portal()
        self._init_camera_mirror()
        self._init_matrix_rain()

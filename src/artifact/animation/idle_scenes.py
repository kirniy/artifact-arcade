"""Efficient idle animation scenes optimized for 60fps on Raspberry Pi.

This module provides 9 curated idle scenes that cycle automatically.
All effects are optimized using pygame primitives and simple math - no per-pixel loops.

Scenes:
1. VNVNC_ENTRANCE - Grand entrance with neon sign
2. CAMERA_EFFECTS - Live camera with cycling effects
3. DIVOOM_GALLERY - Cycling Divoom pixel art GIFs
4. SAGA_LIVE - SAGA live video with audio
5. POSTER_SLIDESHOW - Fast slideshow of event posters
6. DNA_HELIX - DNA double helix animation
7. SNOWFALL - Winter snowfall
8. FIREPLACE - Cozy fireplace
9. HYPERCUBE - 4D hypercube rotation

Each scene has coordinated animations for:
- Main display (128x128)
- Ticker display (48x8)
- LCD display (16 chars)
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
import math
import random
import logging
import numpy as np
from numpy.typing import NDArray

from artifact.graphics.primitives import clear, draw_circle, draw_rect, fill, draw_line

logger = logging.getLogger(__name__)
from artifact.graphics.fonts import load_font, draw_text_bitmap
from artifact.graphics.text_utils import (
    draw_animated_text, draw_centered_text, TextEffect,
    render_ticker_animated, render_ticker_static, TickerEffect, hsv_to_rgb
)
from artifact.utils.camera_service import camera_service
from artifact.utils.audio_utils import extract_audio_from_video


# Scene duration in milliseconds
SCENE_DURATION = 12000  # 12 seconds per scene (more dynamic pacing)
TRANSITION_DURATION = 1000  # 1 second smooth fade (increased from 500ms)
CAMERA_EFFECT_DURATION = 8000  # 8 seconds per camera effect before auto-cycling

# Scene-specific duration overrides (ms)
SCENE_DURATIONS = {
    # DIVOOM_GALLERY is the star - New Year celebration, plays all GIFs fully
    'DIVOOM_GALLERY': 180000,  # 3 minutes - cycles through ~15 GIFs
    # VNVNC entrance gets more time - it's the signature scene
    'VNVNC_ENTRANCE': 25000,  # 25 seconds
    # SAGA_LIVE video plays once with audio
    'SAGA_LIVE': 45000,       # 45 seconds - video duration
    # POSTER_SLIDESHOW cycles quickly through event posters
    'POSTER_SLIDESHOW': 60000,  # 60 seconds to show many posters
}


class IdleScene(Enum):
    """Available idle scenes - curated set of 9 effects."""
    VNVNC_ENTRANCE = auto()   # Grand entrance with neon sign - ALWAYS FIRST
    CAMERA_EFFECTS = auto()   # Camera with cycling effects (mirror, neon, glitch, fire, matrix, starfield)
    DIVOOM_GALLERY = auto()   # Cycling Divoom pixel art GIFs
    SAGA_LIVE = auto()        # SAGA live video with audio
    POSTER_SLIDESHOW = auto() # Fast slideshow of event posters
    DNA_HELIX = auto()        # DNA double helix animation
    SNOWFALL = auto()         # Winter snowfall
    FIREPLACE = auto()        # Cozy fireplace
    HYPERCUBE = auto()        # 4D hypercube rotation


# Camera effect sub-modes (cycled within CAMERA_EFFECTS scene)
class CameraEffect(Enum):
    """Sub-effects for CAMERA_EFFECTS scene."""
    MIRROR = auto()           # Basic silhouette mirror
    NEON_TUNNEL = auto()      # Neon ring tunnel overlay
    GLITCH_GRID = auto()      # Glitch scanlines
    FIRE_SILHOUETTE = auto()  # Fire/heat effect
    MATRIX_RAIN = auto()      # Matrix code rain
    STARFIELD_3D = auto()     # 3D starfield overlay


@dataclass
class SceneState:
    """Shared state for scene animations."""
    time: float = 0.0
    scene_time: float = 0.0
    frame: int = 0
    current_scene: IdleScene = IdleScene.VNVNC_ENTRANCE
    # Camera effects sub-mode state
    camera_effect: CameraEffect = CameraEffect.MIRROR
    camera_effect_time: float = 0.0  # Time in current effect


class RotatingIdleAnimation:
    """Efficient idle animation with smooth 60fps rendering.

    Uses pygame-style primitives and simple math for performance.
    No per-pixel numpy loops - all operations are vectorized or use drawing calls.
    """

    def __init__(self):
        self.state = SceneState()
        # VNVNC_ENTRANCE is ALWAYS first, then shuffle the rest
        self.scenes = [IdleScene.VNVNC_ENTRANCE]
        other_scenes = [s for s in IdleScene if s != IdleScene.VNVNC_ENTRANCE]
        random.shuffle(other_scenes)
        self.scenes.extend(other_scenes)
        self.scene_index = 0
        self.state.current_scene = self.scenes[0]

        # Manual control
        self.manual_mode = False
        self.manual_timeout = 0.0

        # Lock current scene (numpad 0 toggles)
        self.locked = False

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

        # Poster slideshow state
        self.poster_images: List[NDArray[np.uint8]] = []
        self.poster_index = 0
        self.poster_time = 0.0
        self.poster_interval = 500.0  # 500ms per poster (fast!)
        self.poster_dates: List[str] = []  # DD.MM.YY format
        self._pil_available = False
        try:
            from PIL import Image
            self._pil_available = True
        except ImportError:
            logger.warning("PIL not available for poster slideshow")

        # Pac-Man maze and state
        self.pacman_tile = 8
        self.pacman_maze = [
            "################",
            "#..............#",
            "#.####.##.####.#",
            "#.#....##....#.#",
            "#.#.########.#.#",
            "#.#....##....#.#",
            "#.####.##.####.#",
            "#..............#",
            "#.####.##.####.#",
            "#.#....##....#.#",
            "#.#.########.#.#",
            "#.#....##....#.#",
            "#.####.##.####.#",
            "#..............#",
            "#.############.#",
            "################",
        ]
        self.pacman_open_tiles = [
            (x, y)
            for y, row in enumerate(self.pacman_maze)
            for x, cell in enumerate(row)
            if cell != "#"
        ]
        self.pacman_power_tiles = {(1, 1), (14, 1), (1, 13), (14, 13)}
        self.pacman_eaten = set()
        self.pacman_pos = [0.0, 0.0]
        self.pacman_dir = (1, 0)
        self.pacman_speed = 28.0
        self.pacman_last_time = 0.0
        self.pacman_power_timer = 0.0
        self.pacman_ghosts: List[dict] = []
        self._reset_pacman_scene()

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

        # VNVNC Entrance state
        self.entrance_confetti: List[dict] = []
        self.entrance_diamonds: List[dict] = [
            {'x': 20, 'y': 25, 'phase': 0, 'scale': 0.8},
            {'x': 108, 'y': 25, 'phase': 1.5, 'scale': 0.8},
        ]
        self.entrance_snow: List[dict] = []
        for _ in range(50):
            self.entrance_snow.append({
                'x': random.randint(0, 127), 'y': random.randint(100, 127),
                'speed': random.uniform(0.1, 0.3), 'size': 1
            })

        # Bar Cocktails state
        self.bar_glasses: List[dict] = []
        self.bar_shots: List[dict] = []
        self.bar_bubbles: List[dict] = []
        self.bar_neon_flicker = 1.0
        self._init_bar_scene()

        # Divoom Gallery state (GIF animations from Divoom)
        self.divoom_gifs: List[List[np.ndarray]] = []  # List of GIFs, each is list of frames
        self.divoom_gif_index = 0
        self.divoom_frame_index = 0
        self.divoom_frame_time = 0.0
        self.divoom_frame_duration = 100.0  # ms per frame
        self.divoom_gif_duration = 12000.0  # 12 seconds per GIF for full animation
        self.divoom_gif_time = 0.0
        self.divoom_gif_play_count = 0  # How many times current GIF has played
        self.divoom_gif_plays_required = 2  # Play each GIF twice before moving on
        self._load_divoom_gifs()

        # SAGA_LIVE video state
        self.saga_video_capture = None
        self.saga_video_path: Optional[Path] = None
        self.saga_audio_playing = False
        self._cv2_available = False
        self._pygame_mixer_available = False
        self._load_saga_video()

    def _load_divoom_gifs(self) -> None:
        """Load all Divoom GIF animations from assets folder."""
        try:
            from PIL import Image
        except ImportError:
            logger.warning("PIL not available, Divoom GIFs disabled")
            return

        gif_dir = Path(__file__).parent.parent.parent.parent / "assets" / "divoom_animations"
        if not gif_dir.exists():
            logger.info(f"Divoom animations directory not found: {gif_dir}")
            return

        gif_files = sorted(gif_dir.glob("*.gif"))
        if not gif_files:
            logger.info("No Divoom GIF files found")
            return

        logger.info(f"Loading {len(gif_files)} Divoom GIF animations...")

        for gif_path in gif_files:
            try:
                img = Image.open(gif_path)
                frames = []

                # Extract all frames
                for frame_num in range(img.n_frames):
                    img.seek(frame_num)
                    # Convert to RGB and resize to 128x128 if needed
                    frame = img.convert('RGB')
                    if frame.size != (128, 128):
                        frame = frame.resize((128, 128), Image.Resampling.NEAREST)
                    # Convert to numpy array
                    frame_array = np.array(frame, dtype=np.uint8)
                    frames.append(frame_array)

                if frames:
                    self.divoom_gifs.append(frames)

            except Exception as e:
                logger.warning(f"Failed to load GIF {gif_path.name}: {e}")
                continue

        if self.divoom_gifs:
            # Shuffle the GIFs for variety
            random.shuffle(self.divoom_gifs)
            logger.info(f"Loaded {len(self.divoom_gifs)} Divoom GIF animations")
            # Re-initialize scenes with DIVOOM_GALLERY FIRST (New Year special!)
            self.scenes = [IdleScene.DIVOOM_GALLERY, IdleScene.VNVNC_ENTRANCE]
            other_scenes = [s for s in IdleScene if s not in (IdleScene.VNVNC_ENTRANCE, IdleScene.DIVOOM_GALLERY)]
            random.shuffle(other_scenes)
            self.scenes.extend(other_scenes)
            self.scene_index = 0
            self.state.current_scene = self.scenes[0]
        else:
            logger.warning("No Divoom GIFs loaded successfully")

    def _load_saga_video(self) -> None:
        """Load SAGA LIVE video for idle scene."""
        # Check for opencv
        try:
            import cv2
            self._cv2_available = True
        except ImportError:
            logger.warning("OpenCV not available, SAGA_LIVE disabled")
            return

        # Check for pygame.mixer
        try:
            import pygame.mixer
            self._pygame_mixer_available = True
        except ImportError:
            logger.warning("pygame.mixer not available for SAGA_LIVE audio")

        # Find the video file
        video_path = Path(__file__).parent.parent.parent.parent / "assets" / "videos" / "sagalive_crop_center.mp4"
        if video_path.exists():
            self.saga_video_path = video_path
            logger.info(f"Loaded SAGA LIVE video: {video_path.name}")
        else:
            logger.warning(f"SAGA LIVE video not found: {video_path}")

    def _start_saga_video(self) -> None:
        """Start playing SAGA LIVE video with audio."""
        if not self._cv2_available or not self.saga_video_path:
            return

        import cv2
        import pygame
        import pygame.mixer
        from artifact.audio.engine import get_audio_engine

        # Stop ALL audio before playing video
        audio = get_audio_engine()
        audio.stop_idle_music()
        audio.stop_all()

        # Ensure mixer is initialized
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
            logger.info("Initialized pygame.mixer for SAGA LIVE audio")

        # Open video capture
        self.saga_video_capture = cv2.VideoCapture(str(self.saga_video_path))

        # Extract and start audio playback (pygame can't play MP4 directly)
        try:
            logger.info(f"Extracting audio from {self.saga_video_path.name}...")
            audio_path = extract_audio_from_video(self.saga_video_path)
            if audio_path and audio_path.exists():
                pygame.mixer.music.load(str(audio_path))
                pygame.mixer.music.set_volume(0.8)
                pygame.mixer.music.play(loops=-1)  # Loop for idle
                self.saga_audio_playing = True
                logger.info(f"Started SAGA LIVE audio from {audio_path.name}")
            else:
                logger.error("Could not extract audio from SAGA video")
        except Exception as e:
            logger.exception(f"Failed to start SAGA LIVE audio: {e}")

    def _stop_saga_video(self) -> None:
        """Stop SAGA LIVE video and audio."""
        if self.saga_video_capture:
            self.saga_video_capture.release()
            self.saga_video_capture = None

        if self.saga_audio_playing and self._pygame_mixer_available:
            try:
                import pygame.mixer
                pygame.mixer.music.stop()
            except Exception:
                pass
            self.saga_audio_playing = False

        # Resume idle music
        from artifact.audio.engine import get_audio_engine
        audio = get_audio_engine()
        audio.start_idle_music()

    def _init_bar_scene(self) -> None:
        """Initialize bar scene with glasses and shots."""
        # Cocktail glasses on bar counter
        self.bar_glasses = [
            {'x': 20, 'type': 'martini', 'color': (255, 100, 150), 'phase': 0},
            {'x': 45, 'type': 'highball', 'color': (100, 200, 255), 'phase': 1.2},
            {'x': 70, 'type': 'wine', 'color': (180, 50, 80), 'phase': 2.4},
            {'x': 95, 'type': 'shot', 'color': (255, 180, 50), 'phase': 3.6},
            {'x': 110, 'type': 'martini', 'color': (150, 255, 100), 'phase': 4.8},
        ]
        # Falling shots
        self.bar_shots = []
        # Rising bubbles
        self.bar_bubbles = []

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

        # Auto scene transition - use scene-specific duration if defined
        # Skip if locked (numpad 0 toggles lock)
        if not self.manual_mode and not self.transitioning and not self.locked:
            scene_name = self.state.current_scene.name
            duration = SCENE_DURATIONS.get(scene_name, SCENE_DURATION)
            if self.state.scene_time >= duration:
                self._start_transition((self.scene_index + 1) % len(self.scenes))

        # Auto-cycle camera effects within CAMERA_EFFECTS scene
        if self.state.current_scene == IdleScene.CAMERA_EFFECTS:
            self.state.camera_effect_time += delta_ms
            if self.state.camera_effect_time >= CAMERA_EFFECT_DURATION:
                self.state.camera_effect_time = 0.0
                effects = list(CameraEffect)
                current_idx = effects.index(self.state.camera_effect)
                self.state.camera_effect = effects[(current_idx + 1) % len(effects)]

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

        # Update camera for camera effects mode
        if self.state.current_scene == IdleScene.CAMERA_EFFECTS:
            self._update_camera()
            # Cycle effects every 8 seconds
            self.state.camera_effect_time += delta_ms
            if self.state.camera_effect_time >= CAMERA_EFFECT_DURATION:
                self.state.camera_effect_time = 0
                effects = list(CameraEffect)
                current_idx = effects.index(self.state.camera_effect)
                self.state.camera_effect = effects[(current_idx + 1) % len(effects)]

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

    def next_gif(self) -> None:
        """Navigate to next GIF in DIVOOM_GALLERY."""
        if self.state.current_scene == IdleScene.DIVOOM_GALLERY and self.divoom_gifs:
            self.divoom_gif_index = (self.divoom_gif_index + 1) % len(self.divoom_gifs)
            self.divoom_frame_index = 0
            self.divoom_frame_time = 0.0
            self.divoom_gif_time = 0.0
            self.divoom_gif_play_count = 0
            logger.debug(f"Next GIF: {self.divoom_gif_index + 1}/{len(self.divoom_gifs)}")

    def prev_gif(self) -> None:
        """Navigate to previous GIF in DIVOOM_GALLERY."""
        if self.state.current_scene == IdleScene.DIVOOM_GALLERY and self.divoom_gifs:
            self.divoom_gif_index = (self.divoom_gif_index - 1) % len(self.divoom_gifs)
            self.divoom_frame_index = 0
            self.divoom_frame_time = 0.0
            self.divoom_gif_time = 0.0
            self.divoom_gif_play_count = 0
            logger.debug(f"Prev GIF: {self.divoom_gif_index + 1}/{len(self.divoom_gifs)}")

    def on_input(self, key: str) -> bool:
        """Handle keypad input during idle animation.

        Args:
            key: Keypad key pressed ('0'-'9', '*', '#')

        Returns:
            True if input was handled, False otherwise
        """
        # Numpad 0 toggles lock on current scene
        if key == '0':
            self.locked = not self.locked
            logger.info(f"Idle scene {'LOCKED' if self.locked else 'UNLOCKED'}: {self.state.current_scene.name}")
            return True

        # During DIVOOM_GALLERY, allow GIF navigation with 2 (prev) and 8 (next)
        if self.state.current_scene == IdleScene.DIVOOM_GALLERY:
            if key == '2':
                self.prev_gif()
                return True
            elif key == '8':
                self.next_gif()
                return True

        # During CAMERA_EFFECTS, allow effect cycling with 2 (prev) and 8 (next)
        if self.state.current_scene == IdleScene.CAMERA_EFFECTS:
            effects = list(CameraEffect)
            current_idx = effects.index(self.state.camera_effect)
            if key == '2':
                new_idx = (current_idx - 1) % len(effects)
                self.state.camera_effect = effects[new_idx]
                self.state.camera_effect_time = 0.0
                logger.info(f"Camera effect: {self.state.camera_effect.name}")
                return True
            elif key == '8':
                new_idx = (current_idx + 1) % len(effects)
                self.state.camera_effect = effects[new_idx]
                self.state.camera_effect_time = 0.0
                logger.info(f"Camera effect: {self.state.camera_effect.name}")
                return True

        return False

    def get_scene_name(self) -> str:
        names = {
            IdleScene.VNVNC_ENTRANCE: "ВХОД",
            IdleScene.CAMERA_EFFECTS: "КАМЕРА",
            IdleScene.DIVOOM_GALLERY: "ГАЛЕРЕЯ",
            IdleScene.SAGA_LIVE: "САГА",
            IdleScene.POSTER_SLIDESHOW: "АФИШИ",
            IdleScene.DNA_HELIX: "ДНК",
            IdleScene.SNOWFALL: "СНЕГ",
            IdleScene.FIREPLACE: "КАМИН",
            IdleScene.HYPERCUBE: "ГИПЕР",
        }
        return names.get(self.state.current_scene, "СЦЕНА")

    def _on_scene_enter(self) -> None:
        scene = self.state.current_scene
        # Open camera for CAMERA_EFFECTS scene
        if scene == IdleScene.CAMERA_EFFECTS:
            self._open_camera()
            self.state.camera_effect = CameraEffect.MIRROR
            self.state.camera_effect_time = 0.0
        elif scene == IdleScene.POSTER_SLIDESHOW:
            self._load_poster_slideshow()
        elif scene == IdleScene.SAGA_LIVE:
            self._start_saga_video()

    def _on_scene_exit(self, scene: IdleScene) -> None:
        if scene == IdleScene.CAMERA_EFFECTS:
            self._close_camera()
        elif scene == IdleScene.SAGA_LIVE:
            self._stop_saga_video()

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

        if scene == IdleScene.VNVNC_ENTRANCE:
            self._render_vnvnc_entrance(buffer)
        elif scene == IdleScene.CAMERA_EFFECTS:
            self._render_camera_effects(buffer)
        elif scene == IdleScene.DIVOOM_GALLERY:
            self._render_divoom_gallery(buffer)
        elif scene == IdleScene.SAGA_LIVE:
            self._render_saga_live(buffer)
        elif scene == IdleScene.POSTER_SLIDESHOW:
            self._render_poster_slideshow(buffer)
        elif scene == IdleScene.DNA_HELIX:
            self._render_dna_helix(buffer)
        elif scene == IdleScene.SNOWFALL:
            self._render_snowfall(buffer)
        elif scene == IdleScene.FIREPLACE:
            self._render_fireplace(buffer)
        elif scene == IdleScene.HYPERCUBE:
            self._render_hypercube(buffer)

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

    def _render_vnvnc_entrance(self, buffer: NDArray[np.uint8]) -> None:
        """Render grand VNVNC entrance - neon sign, red carpet, golden doorway."""
        t = self.state.scene_time / 1000

        # === SKY / BACKGROUND ===
        # Warm evening gradient
        for y in range(60):
            tt = y / 60
            r = int(40 + 30 * tt)
            g = int(30 + 20 * tt)
            b = int(50 + 30 * tt)
            buffer[y, :] = (r, g, b)

        # === BUILDING FACADE ===
        # Cream/beige building walls
        for y in range(20, 100):
            for x in range(128):
                # Left column area
                if x < 25 or x > 102:
                    buffer[y, x] = (180, 160, 130)  # Beige stone
                # Main wall
                elif 25 <= x <= 102:
                    buffer[y, x] = (160, 145, 115)  # Slightly darker

        # === COLUMNS (Greek style) ===
        # Left column
        for y in range(25, 95):
            for x in range(10, 22):
                dist = abs(x - 16)
                shade = int(200 - dist * 10)
                buffer[y, x] = (shade, shade - 10, shade - 20)
        # Right column
        for y in range(25, 95):
            for x in range(106, 118):
                dist = abs(x - 112)
                shade = int(200 - dist * 10)
                buffer[y, x] = (shade, shade - 10, shade - 20)

        # Column tops (capitals)
        for x in range(8, 24):
            for y in range(22, 27):
                buffer[y, x] = (220, 210, 190)
        for x in range(104, 120):
            for y in range(22, 27):
                buffer[y, x] = (220, 210, 190)

        # === CHRISTMAS WREATHS on columns ===
        # Left wreath
        wreath_pulse = 0.8 + 0.2 * math.sin(t * 2)
        for angle in range(0, 360, 15):
            rad = math.radians(angle)
            for r in range(6, 10):
                wx = int(16 + r * math.cos(rad))
                wy = int(45 + r * math.sin(rad))
                if 0 <= wx < 128 and 0 <= wy < 128:
                    green = int((100 + 50 * math.sin(angle * 0.1 + t)) * wreath_pulse)
                    buffer[wy, wx] = (30, max(80, min(200, green)), 30)
        # Red bow
        for dy in range(-2, 3):
            for dx in range(-3, 4):
                if abs(dx) + abs(dy) < 4:
                    buffer[53 + dy, 16 + dx] = (200, 50, 50)

        # Right wreath
        for angle in range(0, 360, 15):
            rad = math.radians(angle)
            for r in range(6, 10):
                wx = int(112 + r * math.cos(rad))
                wy = int(45 + r * math.sin(rad))
                if 0 <= wx < 128 and 0 <= wy < 128:
                    green = int((100 + 50 * math.sin(angle * 0.1 + t + 1)) * wreath_pulse)
                    buffer[wy, wx] = (30, max(80, min(200, green)), 30)
        for dy in range(-2, 3):
            for dx in range(-3, 4):
                if abs(dx) + abs(dy) < 4:
                    buffer[53 + dy, 112 + dx] = (200, 50, 50)

        # === ARCH / DOORWAY ===
        # Dark archway
        for y in range(35, 95):
            arch_width = int(20 + 15 * (1 - ((y - 35) / 60) ** 2))
            for x in range(64 - arch_width, 64 + arch_width):
                if 0 <= x < 128:
                    buffer[y, x] = (30, 25, 20)

        # Arch frame (ornate)
        for y in range(33, 95):
            arch_width = int(22 + 15 * (1 - ((max(35, y) - 35) / 60) ** 2))
            # Left frame
            if 64 - arch_width - 3 >= 0:
                buffer[y, 64 - arch_width - 2] = (80, 70, 50)
                buffer[y, 64 - arch_width - 1] = (100, 90, 70)
            # Right frame
            if 64 + arch_width + 3 < 128:
                buffer[y, 64 + arch_width + 1] = (100, 90, 70)
                buffer[y, 64 + arch_width + 2] = (80, 70, 50)

        # === GOLDEN LIGHT from doorway ===
        glow_intensity = 0.7 + 0.3 * math.sin(t * 1.5)
        for y in range(40, 95):
            glow_width = int(15 + 10 * ((y - 40) / 55))
            for x in range(64 - glow_width, 64 + glow_width):
                if 0 <= x < 128:
                    dist = abs(x - 64) / glow_width
                    intensity = (1 - dist) * glow_intensity
                    r = int(255 * intensity)
                    g = int(200 * intensity)
                    b = int(100 * intensity * 0.5)
                    # Blend with existing (cast to int to avoid uint8 overflow)
                    existing = buffer[y, x]
                    buffer[y, x] = (
                        min(255, int(existing[0]) + r),
                        min(255, int(existing[1]) + g),
                        min(255, int(existing[2]) + b)
                    )

        # === WROUGHT IRON GATE (open) ===
        gate_swing = 0.3 + 0.1 * math.sin(t * 0.5)  # Slightly moving
        # Left gate panel
        for y in range(45, 90):
            gx = int(44 - gate_swing * 8)
            if 0 <= gx < 128:
                buffer[y, gx] = (40, 35, 30)
                buffer[y, gx + 1] = (50, 45, 40)
        # Right gate panel
        for y in range(45, 90):
            gx = int(84 + gate_swing * 8)
            if 0 <= gx < 128:
                buffer[y, gx] = (50, 45, 40)
                buffer[y, gx - 1] = (40, 35, 30)

        # === RED CARPET ===
        for y in range(90, 128):
            carpet_width = int(10 + (y - 90) * 0.4)
            for x in range(64 - carpet_width, 64 + carpet_width):
                if 0 <= x < 128:
                    # Carpet texture
                    shade = 150 + int(20 * math.sin(y * 0.5 + x * 0.1))
                    buffer[y, x] = (shade, 20, 30)
        # Carpet gold trim
        for y in range(90, 128):
            carpet_width = int(10 + (y - 90) * 0.4)
            if 64 - carpet_width >= 0:
                buffer[y, 64 - carpet_width] = (200, 170, 80)
            if 64 + carpet_width - 1 < 128:
                buffer[y, 64 + carpet_width - 1] = (200, 170, 80)

        # === COBBLESTONE GROUND ===
        for y in range(100, 128):
            for x in range(128):
                # Skip carpet area
                carpet_width = int(10 + (y - 90) * 0.4)
                if 64 - carpet_width <= x < 64 + carpet_width:
                    continue
                # Cobblestone pattern
                stone = ((x // 5) + (y // 4)) % 3
                shades = [(100, 95, 90), (90, 85, 80), (110, 105, 100)]
                buffer[y, x] = shades[stone]

        # === SNOW on ground ===
        for snow in self.entrance_snow:
            snow['x'] += math.sin(t + snow['y'] * 0.1) * 0.1
            snow['y'] += snow['speed']
            if snow['y'] > 127:
                snow['y'] = 100
                snow['x'] = random.randint(0, 127)
            px, py = int(snow['x']) % 128, int(snow['y'])
            if 0 <= px < 128 and 0 <= py < 128:
                buffer[py, px] = (240, 240, 250)

        # === DIAMONDS floating ===
        for diamond in self.entrance_diamonds:
            dx = diamond['x']
            dy = int(diamond['y'] + 5 * math.sin(t * 2 + diamond['phase']))
            scale = diamond['scale']
            sparkle = 0.7 + 0.3 * math.sin(t * 6 + diamond['phase'])

            # Diamond shape (simple)
            points = [
                (0, -6), (-4, 0), (0, 4), (4, 0)  # Top, left, bottom, right
            ]
            color = (
                int(150 * sparkle + 100),
                int(200 * sparkle + 50),
                int(255 * sparkle)
            )
            # Fill diamond
            for py in range(-6, 5):
                width = 4 - abs(py) if py < 0 else 4 - py
                for px in range(-width, width + 1):
                    ddx, ddy = int(dx + px * scale), int(dy + py * scale)
                    if 0 <= ddx < 128 and 0 <= ddy < 128:
                        buffer[ddy, ddx] = color

        # === NEON SIGN "VNVNC" at top ===
        sign_y = 8
        neon_pulse = 0.85 + 0.15 * math.sin(t * 4)
        flicker = 1.0 if random.random() > 0.02 else 0.6  # Occasional flicker

        # Sign background (dark panel)
        for y in range(4, 20):
            for x in range(30, 98):
                buffer[y, x] = (30, 20, 35)

        # Neon glow behind text
        for ox in range(-2, 3):
            for oy in range(-2, 3):
                if ox != 0 or oy != 0:
                    glow_color = (
                        int(100 * neon_pulse * flicker),
                        int(40 * neon_pulse * flicker),
                        int(120 * neon_pulse * flicker)
                    )
                    draw_centered_text(buffer, "VNVNC", sign_y + oy, glow_color, scale=2)

        # Main neon text
        neon_color = (
            int(255 * neon_pulse * flicker),
            int(100 * neon_pulse * flicker),
            int(220 * neon_pulse * flicker)
        )
        draw_centered_text(buffer, "VNVNC", sign_y, neon_color, scale=2)

        # === CONFETTI particles ===
        # Spawn new confetti
        if random.random() < 0.15:
            self.entrance_confetti.append({
                'x': random.randint(0, 127),
                'y': random.randint(-10, 0),
                'vx': random.uniform(-0.5, 0.5),
                'vy': random.uniform(0.5, 1.5),
                'color': random.choice([
                    (255, 215, 0),    # Gold
                    (255, 100, 150),  # Pink
                    (100, 200, 255),  # Light blue
                    (255, 255, 255),  # White
                    (200, 100, 255),  # Purple
                ])
            })

        # Update and draw confetti
        new_confetti = []
        for c in self.entrance_confetti:
            c['x'] += c['vx'] + math.sin(t * 3 + c['y'] * 0.1) * 0.3
            c['y'] += c['vy']
            if c['y'] < 120:
                px, py = int(c['x']), int(c['y'])
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = c['color']
                new_confetti.append(c)
        self.entrance_confetti = new_confetti[-100:]  # Limit particles

        # === "НАЖМИ СТАРТ" prompt ===
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 118, (255, 220, 150), scale=1)

    def _render_bar_cocktails(self, buffer: NDArray[np.uint8]) -> None:
        """Render bar scene with cocktails, shots, and neon vibes."""
        t = self.state.scene_time / 1000

        # === BACKGROUND - Dark bar atmosphere ===
        for y in range(128):
            # Gradient from dark ceiling to slightly lit bar
            tt = y / 128
            r = int(15 + 20 * tt)
            g = int(10 + 15 * tt)
            b = int(25 + 30 * tt)
            buffer[y, :] = (r, g, b)

        # === BACK BAR SHELVES with bottles ===
        shelf_y = 30
        # Shelf
        for x in range(10, 118):
            buffer[shelf_y, x] = (60, 50, 40)
            buffer[shelf_y + 1, x] = (50, 40, 30)

        # Bottles on shelf (silhouettes with colored liquid)
        bottles = [
            (20, (100, 200, 100), 15),   # Green (absinthe)
            (35, (200, 150, 50), 12),    # Amber (whiskey)
            (50, (255, 100, 100), 14),   # Red (campari)
            (65, (150, 200, 255), 13),   # Blue (curaçao)
            (80, (255, 200, 150), 11),   # Orange (aperol)
            (95, (200, 100, 200), 14),   # Purple (violet)
            (110, (255, 255, 200), 12),  # Pale (vodka)
        ]

        for bx, color, height in bottles:
            # Bottle silhouette
            for by in range(shelf_y - height, shelf_y):
                width = 3 if by < shelf_y - height + 3 else 4
                for dx in range(-width, width + 1):
                    px = bx + dx
                    if 0 <= px < 128:
                        # Glass with liquid
                        liquid_level = shelf_y - height + 4
                        if by >= liquid_level:
                            buffer[by, px] = color
                        else:
                            buffer[by, px] = (40, 35, 45)  # Empty glass

        # Second shelf
        shelf_y2 = 50
        for x in range(10, 118):
            buffer[shelf_y2, x] = (60, 50, 40)

        # === BAR COUNTER ===
        counter_y = 85
        # Wood grain counter
        for y in range(counter_y, counter_y + 8):
            for x in range(128):
                grain = int(math.sin(x * 0.2 + y * 0.1) * 10)
                buffer[y, x] = (80 + grain, 50 + grain // 2, 30 + grain // 3)

        # Counter edge (brass rail)
        for x in range(128):
            shimmer = int(30 * math.sin(x * 0.3 + t * 2))
            buffer[counter_y - 1, x] = (180 + shimmer, 150 + shimmer, 50)

        # === COCKTAIL GLASSES on counter ===
        for glass in self.bar_glasses:
            gx = glass['x']
            gy = counter_y - 2
            color = glass['color']
            gtype = glass['type']
            phase = glass['phase']

            # Glass shimmer
            shimmer = 0.7 + 0.3 * math.sin(t * 3 + phase)
            r, g, b = color
            c = (int(r * shimmer), int(g * shimmer), int(b * shimmer))

            if gtype == 'martini':
                # Martini glass shape (V)
                for dy in range(-15, 0):
                    width = (-dy) // 2
                    for dx in range(-width, width + 1):
                        px, py = gx + dx, gy + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            if dy > -12:  # Liquid level
                                buffer[py, px] = c
                            else:
                                buffer[py, px] = (200, 200, 220)  # Glass rim
                # Stem
                for dy in range(0, 8):
                    if 0 <= gy + dy < 128:
                        buffer[gy + dy, gx] = (180, 180, 200)
                # Olive
                buffer[gy - 8, gx] = (80, 120, 50)

            elif gtype == 'highball':
                # Tall glass
                for dy in range(-20, 0):
                    for dx in range(-4, 5):
                        px, py = gx + dx, gy + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            if dy > -16:  # Liquid
                                buffer[py, px] = c
                            else:
                                buffer[py, px] = (150, 200, 255)  # Ice
                # Straw
                if 0 <= gx + 2 < 128:
                    for dy in range(-22, -5):
                        if 0 <= gy + dy < 128:
                            buffer[gy + dy, gx + 2] = (255, 50, 50)

            elif gtype == 'wine':
                # Wine glass (rounded bowl)
                for dy in range(-12, 0):
                    width = int(5 * math.sin((dy + 12) / 12 * math.pi * 0.8))
                    for dx in range(-width, width + 1):
                        px, py = gx + dx, gy + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            if dy > -8:
                                buffer[py, px] = c
                            else:
                                buffer[py, px] = (220, 200, 220)
                # Stem
                for dy in range(0, 6):
                    if 0 <= gy + dy < 128:
                        buffer[gy + dy, gx] = (200, 200, 220)

            elif gtype == 'shot':
                # Shot glass (small)
                for dy in range(-8, 0):
                    width = 2 + dy // 4
                    for dx in range(-width, width + 1):
                        px, py = gx + dx, gy + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            buffer[py, px] = c

        # === FALLING SHOTS animation ===
        if random.random() < 0.03:
            self.bar_shots.append({
                'x': random.randint(20, 108),
                'y': 0,
                'vy': 0,
                'color': random.choice([
                    (255, 180, 50),   # Whiskey
                    (200, 255, 200),  # Absinthe
                    (255, 100, 100),  # Grenadine
                    (100, 200, 255),  # Blue shot
                ])
            })

        new_shots = []
        for shot in self.bar_shots:
            shot['vy'] += 0.2  # Gravity
            shot['y'] += shot['vy']

            if shot['y'] < counter_y - 8:
                # Draw falling shot
                gx, gy = int(shot['x']), int(shot['y'])
                for dy in range(-6, 0):
                    for dx in range(-2, 3):
                        px, py = gx + dx, gy + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            buffer[py, px] = shot['color']
                new_shots.append(shot)
            else:
                # Splash effect - create bubbles
                for _ in range(8):
                    self.bar_bubbles.append({
                        'x': shot['x'] + random.randint(-5, 5),
                        'y': counter_y - 10,
                        'vy': random.uniform(-2, -0.5),
                        'life': random.randint(20, 40),
                        'color': shot['color']
                    })
        self.bar_shots = new_shots

        # === BUBBLES ===
        new_bubbles = []
        for bubble in self.bar_bubbles:
            bubble['y'] += bubble['vy']
            bubble['vy'] += 0.05  # Slow down
            bubble['life'] -= 1

            if bubble['life'] > 0 and bubble['y'] > 0:
                px, py = int(bubble['x']), int(bubble['y'])
                if 0 <= px < 128 and 0 <= py < 128:
                    alpha = bubble['life'] / 40
                    c = bubble['color']
                    buffer[py, px] = (int(c[0] * alpha), int(c[1] * alpha), int(c[2] * alpha))
                new_bubbles.append(bubble)
        self.bar_bubbles = new_bubbles[-50:]

        # === NEON SIGNS on wall ===
        # "BAR" neon
        neon_pulse = 0.8 + 0.2 * math.sin(t * 3)
        self.bar_neon_flicker = 1.0 if random.random() > 0.03 else 0.5

        # Glow
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                glow = (int(100 * neon_pulse), int(50 * neon_pulse), int(150 * neon_pulse))
                draw_centered_text(buffer, "VNVNC ARCADE", 55 + oy, glow, scale=1)

        # Main text
        neon_color = (
            int(255 * neon_pulse * self.bar_neon_flicker),
            int(100 * neon_pulse * self.bar_neon_flicker),
            int(200 * neon_pulse * self.bar_neon_flicker)
        )
        draw_centered_text(buffer, "VNVNC ARCADE", 55, neon_color, scale=1)

        # === Floor (dark tiles) ===
        for y in range(counter_y + 8, 128):
            for x in range(128):
                tile = ((x // 8) + (y // 8)) % 2
                if tile:
                    buffer[y, x] = (25, 20, 30)
                else:
                    buffer[y, x] = (35, 30, 40)

        # === VNVNC title ===
        draw_centered_text(buffer, "VNVNC", 4, (255, 200, 100), scale=2)

        # === Prompt ===
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "НАЖМИ СТАРТ", 118, self.teal, scale=1)

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
        """Render stunning northern lights / aurora borealis with layered curtains."""
        t = self.state.scene_time / 1000

        # Deep night sky gradient with subtle stars
        for y in range(128):
            # Night sky gradient: deep blue at top, darker blue-green at bottom
            progress = y / 128
            r = int(5 + progress * 5)
            g = int(8 + (1 - progress) * 15)
            b = int(25 + (1 - progress) * 20)
            buffer[y, :] = (r, g, b)

        # Twinkling stars (more visible)
        for i in range(50):
            sx = (i * 73 + int(t * 2)) % 128
            sy = (i * 41) % 70  # Keep stars in upper portion
            twinkle = 100 + int(100 * math.sin(t * 4 + i * 0.7))
            if 0 <= sx < 128 and 0 <= sy < 128:
                buffer[sy, sx] = (twinkle, twinkle, min(255, twinkle + 50))
                # Some stars have small glow
                if i % 5 == 0 and twinkle > 150:
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = sx + dx, sy + dy
                        if 0 <= nx < 128 and 0 <= ny < 128:
                            buffer[ny, nx] = tuple(min(255, c + 30) for c in buffer[ny, nx])

        # Multi-layered aurora curtains with different colors
        aurora_colors = [
            (120, 0.9, 0.9),   # Green
            (160, 0.7, 0.8),   # Cyan-green
            (280, 0.6, 0.7),   # Purple
            (100, 0.8, 0.6),   # Yellow-green
        ]

        for idx, curtain in enumerate(self.aurora_curtains):
            color_idx = idx % len(aurora_colors)
            base_hue, saturation, value = aurora_colors[color_idx]

            # Curtain spans most of the screen vertically
            y_start = 15 + int(math.sin(t * 0.5 + idx) * 10)
            y_end = 95 + int(math.sin(t * 0.3 + idx * 2) * 15)

            for y in range(max(0, y_start), min(128, y_end)):
                # Complex wave motion for realistic curtain movement
                wave1 = math.sin(y / 12 + t * 1.5 + curtain['phase']) * 20
                wave2 = math.sin(y / 6 + t * 2.5 + curtain['phase'] * 2) * 8
                wave3 = math.sin(y / 25 + t * 0.8) * 12
                x = int(curtain['x'] + wave1 + wave2 + wave3)

                # Intensity varies with height (brightest in middle)
                y_center = (y_start + y_end) / 2
                y_range = (y_end - y_start) / 2
                height_factor = max(0, 1 - abs(y - y_center) / y_range)

                # Pulsing intensity
                pulse = 0.6 + 0.4 * math.sin(t * 2 + curtain['phase'] + y / 30)
                intensity = height_factor * pulse

                if intensity > 0.1 and 0 <= x < 128:
                    # Color shifts with height and time
                    hue = base_hue + (y - y_start) * 0.8 + math.sin(t * 0.5 + idx) * 20
                    color = hsv_to_rgb(hue % 360, saturation, intensity * value)

                    # Wide glow for each curtain line
                    for gx in range(-4, 5):
                        px = x + gx
                        if 0 <= px < 128:
                            glow = max(0, 1 - abs(gx) / 4.5) ** 1.5
                            old = buffer[y, px]
                            blend = [min(255, int(old[i] + color[i] * glow)) for i in range(3)]
                            buffer[y, px] = tuple(blend)

            # Slow curtain drift
            curtain['x'] += math.sin(t * 0.3 + curtain['phase']) * 0.4
            if curtain['x'] < -20:
                curtain['x'] = 140
            elif curtain['x'] > 148:
                curtain['x'] = -12

        # Occasional bright flash/shimmer
        if int(t * 10) % 40 < 2:
            flash_x = int(64 + math.sin(t * 7) * 50)
            flash_y = int(50 + math.sin(t * 5) * 20)
            if 0 <= flash_x < 128 and 0 <= flash_y < 128:
                for dx in range(-6, 7):
                    for dy in range(-3, 4):
                        px, py = flash_x + dx, flash_y + dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            dist = abs(dx) + abs(dy)
                            if dist < 6:
                                glow = int((6 - dist) * 20)
                                old = buffer[py, px]
                                buffer[py, px] = tuple(min(255, c + glow) for c in old)

        # Branding with glow
        for ox in [-1, 0, 1]:
            for oy in [-1, 0, 1]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, "VNVNC", 4 + oy, (0, 20, 10), scale=2)
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

    def _pacman_tile_center(self, col: int, row: int) -> Tuple[int, int]:
        tile = self.pacman_tile
        return col * tile + tile // 2, row * tile + tile // 2

    def _pacman_tile_from_pos(self, pos: List[float]) -> Tuple[int, int]:
        tile = self.pacman_tile
        col = int(pos[0] // tile)
        row = int(pos[1] // tile)
        col = max(0, min(col, len(self.pacman_maze[0]) - 1))
        row = max(0, min(row, len(self.pacman_maze) - 1))
        return col, row

    def _pacman_is_open(self, col: int, row: int) -> bool:
        if row < 0 or col < 0:
            return False
        if row >= len(self.pacman_maze) or col >= len(self.pacman_maze[0]):
            return False
        return self.pacman_maze[row][col] != "#"

    def _pacman_available_dirs(self, col: int, row: int) -> List[Tuple[int, int]]:
        dirs = []
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if self._pacman_is_open(col + dx, row + dy):
                dirs.append((dx, dy))
        return dirs

    def _pacman_manhattan(self, a: Tuple[int, int], b: Tuple[int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _reset_pacman_scene(self) -> None:
        self.pacman_eaten = set()
        self.pacman_power_timer = 0.0
        start_col, start_row = 1, 7
        cx, cy = self._pacman_tile_center(start_col, start_row)
        self.pacman_pos = [float(cx), float(cy)]
        self.pacman_dir = (1, 0)
        self.pacman_last_time = self.state.scene_time

        ghost_tiles = [(7, 7), (8, 7), (9, 7), (10, 7)]
        ghost_colors = [
            ((255, 0, 0), "red", (14, 1)),
            ((255, 184, 255), "pink", (1, 1)),
            ((0, 255, 255), "cyan", (14, 13)),
            ((255, 184, 82), "orange", (1, 13)),
        ]
        self.pacman_ghosts = []
        for (gx, gy), (color, personality, scatter) in zip(ghost_tiles, ghost_colors):
            px, py = self._pacman_tile_center(gx, gy)
            self.pacman_ghosts.append({
                "pos": [float(px), float(py)],
                "dir": (-1, 0),
                "color": color,
                "speed": 24.0,
                "personality": personality,
                "scatter": scatter,
            })

    def _render_pacman(self, buffer: NDArray[np.uint8]) -> None:
        """Render Pac-Man chase scene with roaming maze navigation."""
        t = self.state.scene_time / 1000

        # Maze background
        fill(buffer, (0, 0, 0))

        # Maze walls (tile-based)
        wall_color = (30, 60, 220)
        wall_inner = (8, 20, 80)
        tile = self.pacman_tile
        for row_idx, row in enumerate(self.pacman_maze):
            for col_idx, cell in enumerate(row):
                if cell == "#":
                    x = col_idx * tile
                    y = row_idx * tile
                    draw_rect(buffer, x, y, tile, tile, wall_color)
                    draw_rect(buffer, x + 1, y + 1, tile - 2, tile - 2, wall_inner,
                              filled=False, thickness=1)

        # Pellets
        pellet_color = (255, 184, 174)
        for col, row in self.pacman_open_tiles:
            if (col, row) in self.pacman_eaten:
                continue
            cx, cy = self._pacman_tile_center(col, row)
            if (col, row) in self.pacman_power_tiles:
                size = 3 if int(t * 4) % 2 == 0 else 2
            else:
                size = 1
            for dy in range(-size, size + 1):
                for dx in range(-size, size + 1):
                    if dx * dx + dy * dy <= size * size:
                        npx, npy = cx + dx, cy + dy
                        if 0 <= npx < 128 and 0 <= npy < 128:
                            buffer[npy, npx] = pellet_color

        # Time step for movement
        dt = (self.state.scene_time - self.pacman_last_time) / 1000.0
        if dt < 0 or dt > 0.2:
            dt = 0.016
        self.pacman_last_time = self.state.scene_time

        # Power pellet timer
        if self.pacman_power_timer > 0:
            self.pacman_power_timer = max(0.0, self.pacman_power_timer - dt)
        power_mode = self.pacman_power_timer > 0

        # Move Pac-Man on grid
        pac_tile = self._pacman_tile_from_pos(self.pacman_pos)
        pac_cx, pac_cy = self._pacman_tile_center(*pac_tile)
        at_center = abs(self.pacman_pos[0] - pac_cx) < 0.5 and abs(self.pacman_pos[1] - pac_cy) < 0.5
        if at_center:
            self.pacman_pos[0] = float(pac_cx)
            self.pacman_pos[1] = float(pac_cy)
            dirs = self._pacman_available_dirs(*pac_tile)
            if dirs:
                reverse = (-self.pacman_dir[0], -self.pacman_dir[1])
                if self.pacman_dir not in dirs:
                    self.pacman_dir = random.choice(dirs)
                elif len(dirs) >= 3 and random.random() < 0.35:
                    turn_dirs = [d for d in dirs if d != reverse] or dirs
                    self.pacman_dir = random.choice(turn_dirs)

            if pac_tile in self.pacman_open_tiles and pac_tile not in self.pacman_eaten:
                self.pacman_eaten.add(pac_tile)
                if pac_tile in self.pacman_power_tiles:
                    self.pacman_power_timer = 6.0

            if len(self.pacman_eaten) >= len(self.pacman_open_tiles):
                self._reset_pacman_scene()

        self.pacman_pos[0] += self.pacman_dir[0] * self.pacman_speed * dt
        self.pacman_pos[1] += self.pacman_dir[1] * self.pacman_speed * dt

        # Move ghosts
        pac_tile = self._pacman_tile_from_pos(self.pacman_pos)
        for ghost in self.pacman_ghosts:
            ghost_tile = self._pacman_tile_from_pos(ghost["pos"])
            ghost_cx, ghost_cy = self._pacman_tile_center(*ghost_tile)
            at_center = abs(ghost["pos"][0] - ghost_cx) < 0.5 and abs(ghost["pos"][1] - ghost_cy) < 0.5
            if at_center:
                ghost["pos"][0] = float(ghost_cx)
                ghost["pos"][1] = float(ghost_cy)
                dirs = self._pacman_available_dirs(*ghost_tile)
                if dirs:
                    reverse = (-ghost["dir"][0], -ghost["dir"][1])
                    if len(dirs) > 1:
                        dirs = [d for d in dirs if d != reverse] or dirs

                    target = pac_tile
                    if ghost["personality"] == "pink":
                        target = (pac_tile[0] + self.pacman_dir[0] * 2,
                                  pac_tile[1] + self.pacman_dir[1] * 2)
                    elif ghost["personality"] == "cyan":
                        target = (pac_tile[0] + self.pacman_dir[0] * 4,
                                  pac_tile[1] + self.pacman_dir[1] * 4)
                    elif ghost["personality"] == "orange":
                        if self._pacman_manhattan(ghost_tile, pac_tile) > 6:
                            target = pac_tile
                        else:
                            target = ghost["scatter"]

                    if not self._pacman_is_open(*target):
                        target = pac_tile

                    if power_mode:
                        ghost["dir"] = max(
                            dirs,
                            key=lambda d: self._pacman_manhattan(
                                (ghost_tile[0] + d[0], ghost_tile[1] + d[1]), pac_tile
                            )
                        )
                    else:
                        ghost["dir"] = min(
                            dirs,
                            key=lambda d: self._pacman_manhattan(
                                (ghost_tile[0] + d[0], ghost_tile[1] + d[1]), target
                            )
                        )

            ghost_speed = ghost["speed"] * (0.7 if power_mode else 1.0)
            ghost["pos"][0] += ghost["dir"][0] * ghost_speed * dt
            ghost["pos"][1] += ghost["dir"][1] * ghost_speed * dt

            if power_mode:
                dx = ghost["pos"][0] - self.pacman_pos[0]
                dy = ghost["pos"][1] - self.pacman_pos[1]
                if dx * dx + dy * dy < (tile * 0.4) ** 2:
                    sx, sy = self._pacman_tile_center(*ghost["scatter"])
                    ghost["pos"] = [float(sx), float(sy)]
                    ghost["dir"] = (-ghost["dir"][0], -ghost["dir"][1])

        # Draw Pac-Man
        pac_x = int(self.pacman_pos[0])
        pac_y = int(self.pacman_pos[1])
        radius = 5
        mouth_open = int(t * 8) % 2 == 0
        dir_angle = 0.0
        if self.pacman_dir == (-1, 0):
            dir_angle = math.pi
        elif self.pacman_dir == (0, -1):
            dir_angle = -math.pi / 2
        elif self.pacman_dir == (0, 1):
            dir_angle = math.pi / 2

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    if mouth_open:
                        angle = math.atan2(dy, dx)
                        diff = math.atan2(math.sin(angle - dir_angle), math.cos(angle - dir_angle))
                        if abs(diff) < math.pi / 6 and (dx * self.pacman_dir[0] + dy * self.pacman_dir[1]) > 0:
                            continue
                    npx, npy = pac_x + dx, pac_y + dy
                    if 0 <= npx < 128 and 0 <= npy < 128:
                        buffer[npy, npx] = (255, 255, 0)

        eye_offset = (-2, -2)
        if self.pacman_dir == (-1, 0):
            eye_offset = (2, -2)
        elif self.pacman_dir == (0, -1):
            eye_offset = (-2, 2)
        elif self.pacman_dir == (0, 1):
            eye_offset = (-2, -2)
        ex, ey = pac_x + eye_offset[0], pac_y + eye_offset[1]
        if 0 <= ex < 128 and 0 <= ey < 128:
            buffer[ey, ex] = (0, 0, 0)

        # Draw ghosts
        for ghost in self.pacman_ghosts:
            gx, gy = int(ghost["pos"][0]), int(ghost["pos"][1])
            if power_mode:
                blink = power_mode and self.pacman_power_timer < 1.5 and int(t * 8) % 2 == 0
                color = (200, 200, 255) if blink else (0, 0, 200)
            else:
                color = ghost["color"]

            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dy <= 0:
                        if dx * dx + dy * dy <= radius * radius:
                            npx, npy = gx + dx, gy + dy
                            if 0 <= npx < 128 and 0 <= npy < 128:
                                buffer[npy, npx] = color
                    else:
                        if abs(dx) <= radius:
                            wave = (dx + dy + int(t * 8)) % 4 < 2
                            if wave:
                                npx, npy = gx + dx, gy + dy
                                if 0 <= npx < 128 and 0 <= npy < 128:
                                    buffer[npy, npx] = color

            if not power_mode:
                pupil_dx = ghost["dir"][0]
                pupil_dy = ghost["dir"][1]
                for ex in (-2, 2):
                    eye_x = gx + ex
                    eye_y = gy - 2
                    if 0 <= eye_x < 128 and 0 <= eye_y < 128:
                        buffer[eye_y, eye_x] = (255, 255, 255)
                        px = eye_x + pupil_dx
                        py = eye_y + pupil_dy
                        if 0 <= px < 128 and 0 <= py < 128:
                            buffer[py, px] = (0, 0, 120)

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

    def _render_divoom_gallery(self, buffer: NDArray[np.uint8]) -> None:
        """Render Divoom GIF animation - pixel art from Divoom gallery."""
        if not self.divoom_gifs:
            # Fallback to plasma if no GIFs loaded
            self._render_plasma(buffer)
            return

        # Get current GIF and frame
        current_gif = self.divoom_gifs[self.divoom_gif_index]
        current_frame = current_gif[self.divoom_frame_index]

        # Copy frame to buffer
        buffer[:] = current_frame

        # Update frame timing
        delta = 16.67  # Approximate 60fps
        self.divoom_frame_time += delta
        if self.divoom_frame_time >= self.divoom_frame_duration:
            self.divoom_frame_time = 0
            self.divoom_frame_index = (self.divoom_frame_index + 1) % len(current_gif)

        # Update GIF timing (play each GIF twice before moving on)
        self.divoom_gif_time += delta
        if self.divoom_gif_time >= self.divoom_gif_duration:
            self.divoom_gif_time = 0
            self.divoom_frame_index = 0
            self.divoom_gif_play_count += 1
            # Move to next GIF after playing twice
            if self.divoom_gif_play_count >= self.divoom_gif_plays_required:
                self.divoom_gif_play_count = 0
                self.divoom_gif_index = (self.divoom_gif_index + 1) % len(self.divoom_gifs)

    def _render_saga_live(self, buffer: NDArray[np.uint8]) -> None:
        """Render SAGA LIVE video frame."""
        if not self._cv2_available or not self.saga_video_capture:
            # Fallback to plasma if video not available
            self._render_plasma(buffer)
            return

        import cv2

        if not self.saga_video_capture.isOpened():
            self._render_plasma(buffer)
            return

        ret, frame = self.saga_video_capture.read()
        if not ret:
            # Video ended - loop it
            self.saga_video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.saga_video_capture.read()
            if not ret:
                self._render_plasma(buffer)
                return

        # Convert BGR to RGB and resize if needed
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if frame.shape[0] != 128 or frame.shape[1] != 128:
            frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_AREA)

        buffer[:] = frame

    def _render_camera_effects(self, buffer: NDArray[np.uint8]) -> None:
        """Render camera with currently selected effect."""
        effect = self.state.camera_effect
        if effect == CameraEffect.MIRROR:
            self._render_camera(buffer)
        elif effect == CameraEffect.NEON_TUNNEL:
            self._render_neon_tunnel(buffer)
        elif effect == CameraEffect.GLITCH_GRID:
            self._render_glitch_grid(buffer)
        elif effect == CameraEffect.FIRE_SILHOUETTE:
            self._render_fire_silhouette(buffer)
        elif effect == CameraEffect.MATRIX_RAIN:
            self._render_matrix_rain(buffer)
        elif effect == CameraEffect.STARFIELD_3D:
            self._render_starfield_3d(buffer)
        else:
            self._render_camera(buffer)

    def _load_poster_slideshow(self) -> None:
        """Load event posters for slideshow with date extraction."""
        if not self._pil_available:
            return

        from PIL import Image
        import re

        # Load from 2025video folder
        assets_dir = Path(__file__).parent.parent.parent.parent / "assets" / "videos" / "2025video"
        if not assets_dir.exists():
            logger.warning(f"Poster directory not found: {assets_dir}")
            return

        # Get all image files (sorted by name/date)
        image_files = sorted(
            list(assets_dir.glob("*.jpg")) +
            list(assets_dir.glob("*.png"))
        )

        self.poster_images = []
        self.poster_dates = []

        for img_path in image_files:
            try:
                img = Image.open(img_path).convert('RGB')
                # Same resize as VideoMode - direct 128x128
                img = img.resize((128, 128), Image.Resampling.LANCZOS)
                self.poster_images.append(np.array(img, dtype=np.uint8))

                # Extract date from filename (format: YYYY-MM-DD_*.jpg)
                match = re.match(r'(\d{4})-(\d{2})-(\d{2})', img_path.stem)
                if match:
                    year, month, day = match.groups()
                    date_str = f"{day}.{month}.{year[2:]}"  # DD.MM.YY
                    self.poster_dates.append(date_str)
                else:
                    self.poster_dates.append("")

                logger.debug(f"Loaded poster: {img_path.name}")
            except Exception as e:
                logger.warning(f"Failed to load poster {img_path.name}: {e}")

        # Keep sorted order (by date in filename)
        self.poster_index = 0
        self.poster_time = 0.0
        logger.info(f"Loaded {len(self.poster_images)} posters for slideshow")

    def _render_poster_slideshow(self, buffer: NDArray[np.uint8]) -> None:
        """Render fast poster slideshow."""
        if not self.poster_images:
            # Fallback to snowfall if no posters
            self._render_snowfall(buffer)
            return

        # Use scene_time directly to calculate poster index
        # This ensures smooth cycling through ALL posters
        t = self.state.scene_time
        self.poster_index = int(t / self.poster_interval) % len(self.poster_images)

        # Render current poster
        buffer[:] = self.poster_images[self.poster_index]

    def _render_divoom_ticker(self, buffer: NDArray[np.uint8], t: float) -> None:
        """Render special NYE ticker for Divoom Gallery with static text and animations."""
        # Alternating text every 5 seconds
        cycle = int(t / 5000) % 2
        if cycle == 0:
            text = "VNVNC"
            color = (255, 215, 0)  # Gold
        else:
            text = "2026"
            color = (255, 50, 50)  # Red for NYE

        # Render static centered text with pulse effect
        render_ticker_static(buffer, text, t, color, TextEffect.PULSE)

        # Add snowflake decorations at edges
        snow_color = (200, 220, 255)  # Light blue
        t_sec = t / 1000

        # Animated snowflakes on left and right
        for i in range(2):
            # Left snowflake
            x_left = 1 + int(math.sin(t_sec * 2 + i) * 1)
            y_left = 1 + i * 3
            if 0 <= x_left < buffer.shape[1] and 0 <= y_left < buffer.shape[0]:
                buffer[y_left, x_left] = snow_color

            # Right snowflake
            x_right = buffer.shape[1] - 2 + int(math.sin(t_sec * 2 + i + 1) * 1)
            y_right = 1 + i * 3
            if 0 <= x_right < buffer.shape[1] and 0 <= y_right < buffer.shape[0]:
                buffer[y_right, x_right] = snow_color

        # Add subtle sparkles
        if random.random() < 0.3:
            sparkle_x = random.randint(0, buffer.shape[1] - 1)
            sparkle_y = random.randint(0, buffer.shape[0] - 1)
            brightness = random.randint(150, 255)
            buffer[sparkle_y, sparkle_x] = (brightness, brightness, brightness)

    def _render_ticker_static_winter(self, buffer: NDArray[np.uint8], text: str, color: tuple, t: float) -> None:
        """Render static ticker text with winter sparkle effects and scrolling for long text."""
        from artifact.graphics.text_utils import draw_centered_text, draw_text

        # Approximate character width at scale=1 (including spacing)
        char_width = 6
        text_width = len(text) * char_width
        ticker_width = buffer.shape[1]  # 48 pixels

        if text_width <= ticker_width:
            # Short text - just center it
            draw_centered_text(buffer, text, 0, color, scale=1)
        else:
            # Long text - horizontal scroll
            # Scroll speed: complete scroll in ~2.5 seconds (fits within 3s display time)
            scroll_duration = 2500  # ms
            pause_at_start = 300  # ms pause before scrolling
            pause_at_end = 200  # ms pause at end

            # Calculate scroll position
            t_in_display = t % 3000  # Time within this text's display cycle

            if t_in_display < pause_at_start:
                # Pause at start - show beginning
                x_offset = 0
            elif t_in_display > (scroll_duration + pause_at_start):
                # Pause at end - show end
                x_offset = text_width - ticker_width
            else:
                # Scrolling
                scroll_progress = (t_in_display - pause_at_start) / scroll_duration
                scroll_progress = min(1.0, max(0.0, scroll_progress))
                # Ease in-out for smooth scrolling
                if scroll_progress < 0.5:
                    eased = 2 * scroll_progress * scroll_progress
                else:
                    eased = 1 - pow(-2 * scroll_progress + 2, 2) / 2
                x_offset = int(eased * (text_width - ticker_width))

            # Draw text at offset position
            draw_text(buffer, text, -x_offset, 0, color, scale=1)

        # Add winter sparkles - random twinkling pixels
        t_sec = t / 1000
        num_sparkles = 3
        for i in range(num_sparkles):
            # Deterministic but animated sparkle positions
            phase = t_sec * 2 + i * 2.1
            if math.sin(phase) > 0.7:  # Only show some of the time
                sparkle_x = int((math.sin(phase * 0.7 + i) * 0.5 + 0.5) * (buffer.shape[1] - 1))
                sparkle_y = int((math.cos(phase * 0.5 + i * 1.3) * 0.5 + 0.5) * (buffer.shape[0] - 1))
                brightness = int(200 + 55 * math.sin(phase * 3))
                if 0 <= sparkle_x < buffer.shape[1] and 0 <= sparkle_y < buffer.shape[0]:
                    buffer[sparkle_y, sparkle_x] = (brightness, brightness, brightness)

    def _render_ticker_flip(self, buffer: NDArray[np.uint8], old_text: str, new_text: str,
                            old_color: tuple, new_color: tuple, progress: float, t: float) -> None:
        """Render vertical flip transition between two texts."""
        from artifact.graphics.text_utils import draw_centered_text

        h, w = buffer.shape[:2]

        # Eased progress for smooth animation
        eased = 1 - (1 - progress) ** 2  # Ease out quad

        if eased < 0.5:
            # First half: old text slides up and out
            offset = int(eased * 2 * h)  # 0 to h
            # Draw old text sliding up
            temp = np.zeros_like(buffer)
            draw_centered_text(temp, old_text, 0, old_color, scale=1)
            # Shift up
            if offset < h:
                buffer[0:h-offset, :, :] = temp[offset:h, :, :]
            # Fade effect
            fade = 1.0 - eased * 2
            buffer[:] = (buffer * fade).astype(np.uint8)
        else:
            # Second half: new text slides in from bottom
            offset = int((1 - (eased - 0.5) * 2) * h)  # h to 0
            # Draw new text
            temp = np.zeros_like(buffer)
            draw_centered_text(temp, new_text, 0, new_color, scale=1)
            # Shift down (slide in from bottom)
            if offset > 0 and offset < h:
                buffer[offset:h, :, :] = temp[0:h-offset, :, :]
            elif offset <= 0:
                buffer[:] = temp
            # Fade in effect
            fade = (eased - 0.5) * 2
            buffer[:] = (buffer * fade).astype(np.uint8)

    # =========================================================================
    # TICKER DISPLAY RENDERING
    # =========================================================================

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render unified ticker with vertical flip animation - same for all idle scenes."""
        clear(buffer)
        t = self.state.time  # Use global time for consistent animation

        # Special case: POSTER_SLIDESHOW shows dates
        if self.state.current_scene == IdleScene.POSTER_SLIDESHOW and self.poster_dates:
            idx = self.poster_index % len(self.poster_dates)
            date_text = self.poster_dates[idx] if self.poster_dates[idx] else "АФИШИ"
            color = (255, 200, 100)  # Gold/amber
            from artifact.graphics.text_utils import draw_centered_text
            draw_centered_text(buffer, date_text, 0, color, scale=1)
            return

        # Unified rotating texts for all idle modes (horizontal scroll for longer ones)
        texts = [
            "VNVNC",
            "WINTER SAGA",
            "26.12-11.01",
            "HAPPY NEW YEAR",
            "VNVNC <3",
            "С НОВЫМ ГОДОМ",
        ]

        # Colors cycle with texts - winter/festive palette
        colors = [
            (255, 100, 200),   # Pink
            (100, 200, 255),   # Ice blue
            (255, 215, 0),     # Gold
            (100, 255, 150),   # Mint
            (255, 150, 200),   # Light pink
            (200, 220, 255),   # Snow white-blue
        ]

        # Timing: 3 seconds per text, with 0.3s transition
        cycle_time = 3000  # ms per text
        transition_time = 300  # ms for flip animation
        total_cycle = len(texts) * cycle_time

        # Calculate current and next text index
        cycle_ms = t % total_cycle
        current_idx = int(cycle_ms // cycle_time)
        next_idx = (current_idx + 1) % len(texts)

        # Time within current text's cycle
        time_in_cycle = cycle_ms % cycle_time

        current_text = texts[current_idx]
        current_color = colors[current_idx]
        next_text = texts[next_idx]
        next_color = colors[next_idx]

        # Render based on transition state
        if time_in_cycle > (cycle_time - transition_time):
            # In transition - vertical flip effect
            progress = (time_in_cycle - (cycle_time - transition_time)) / transition_time
            self._render_ticker_flip(buffer, current_text, next_text, current_color, next_color, progress, t)
        else:
            # Static display with sparkle effects
            self._render_ticker_static_winter(buffer, current_text, current_color, t)

    # =========================================================================
    # LCD DISPLAY TEXT
    # =========================================================================

    def get_lcd_text(self) -> str:
        """Get LCD text for current scene."""
        scene = self.state.current_scene
        t = self.state.scene_time
        idx = int(t / 2000) % 3

        texts = {
            IdleScene.VNVNC_ENTRANCE: ["  ДОБРО       ", " ПОЖАЛОВАТЬ  ", " НАЖМИ СТАРТ "],
            IdleScene.CAMERA_EFFECTS: ["МАГИЯ ЗЕРКАЛА", " КТО ТЫ?     ", " НАЖМИ СТАРТ "],
            IdleScene.DIVOOM_GALLERY: [" С НОВЫМ    ", " ГОДОМ 2026!", " НАЖМИ СТАРТ "],
            IdleScene.SAGA_LIVE: ["WINTER SAGA ", "26.12-11.01 ", " НАЖМИ СТАРТ "],
            IdleScene.POSTER_SLIDESHOW: ["   АФИШИ    ", "  СОБЫТИЙ   ", " НАЖМИ СТАРТ "],
            IdleScene.DNA_HELIX: ["   СПИРАЛЬ  ", "   ЖИЗНИ    ", " НАЖМИ СТАРТ "],
            IdleScene.SNOWFALL: ["   ЗИМНЯЯ   ", "   СКАЗКА   ", " НАЖМИ СТАРТ "],
            IdleScene.FIREPLACE: ["   УЮТНЫЙ   ", "   КАМИН    ", " НАЖМИ СТАРТ "],
            IdleScene.HYPERCUBE: [" ГИПЕРКУБ   ", "    4D      ", " НАЖМИ СТАРТ "],
        }
        scene_texts = texts.get(scene, ["    VNVNC    ", " НАЖМИ СТАРТ ", "    ★★★★    "])
        return scene_texts[idx].center(16)[:16]

    def reset(self) -> None:
        """Reset animation state."""
        self._close_camera()
        self._stop_saga_video()  # Stop video and its audio
        self.state = SceneState()
        # DIVOOM_GALLERY is FIRST (New Year special!), then VNVNC_ENTRANCE, then shuffle the rest
        self.scenes = []
        # Divoom Gallery first if we have GIFs (New Year celebration!)
        if self.divoom_gifs:
            self.scenes.append(IdleScene.DIVOOM_GALLERY)
        self.scenes.append(IdleScene.VNVNC_ENTRANCE)
        other_scenes = [s for s in IdleScene if s not in (IdleScene.VNVNC_ENTRANCE, IdleScene.DIVOOM_GALLERY)]
        random.shuffle(other_scenes)
        self.scenes.extend(other_scenes)
        self.scene_index = 0
        self.state.current_scene = self.scenes[0]
        self.eye_x = 0.0
        self.eye_y = 0.0
        self.eye_target_x = 0.0
        self.eye_target_y = 0.0
        self.eye_target_time = 0.0
        self.blink = 0.0

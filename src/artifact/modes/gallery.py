"""Photo Gallery Mode - Endless slideshow of club photos with effects.

Features:
- Fetches 50-100 random photos from VNVNC Yandex Disk gallery
- Multiple slideshow transition effects (fade, slide, zoom, photo wall, etc.)
- Christmas snowfall animation overlay
- Square crop to 128x128
- Background music from 2025 video
- Navigate with left/right, load more at end
- Background preloading for instant start
"""

import asyncio
import logging
import math
import random
import threading
import urllib.parse
import urllib.request
import json
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
from io import BytesIO

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text
from artifact.audio.engine import get_audio_engine
from artifact.animation.santa_runner import SantaRunner

logger = logging.getLogger(__name__)

# Yandex Disk API endpoint (same as vnvnc-modern gallery)
API_BASE = "https://d5d621jmge79dusl8rkh.kf69zffa.apigw.yandexcloud.net/api/yandex-disk"

# Number of photos to fetch per batch
PHOTOS_PER_BATCH = 100  # Minimum 50, target 100
PRELOAD_BATCH_SIZE = 50  # Photos to preload on exit for next session


class GalleryPhase(Enum):
    """Phase within GalleryMode."""
    LOADING = auto()     # Loading photos
    VIEWING = auto()     # Viewing slideshow
    ERROR = auto()       # Error state


class TransitionEffect(Enum):
    """Slideshow transition effects."""
    NONE = auto()           # Instant switch (no transition)
    FADE = auto()           # Cross-fade
    SLIDE_LEFT = auto()     # Slide from right to left
    SLIDE_RIGHT = auto()    # Slide from left to right
    SLIDE_UP = auto()       # Slide from bottom to top
    SLIDE_DOWN = auto()     # Slide from top to bottom
    ZOOM_IN = auto()        # Zoom into next photo
    ZOOM_OUT = auto()       # Zoom out to next photo
    PIXELATE = auto()       # Pixelate dissolve
    PHOTO_WALL = auto()     # Show multiple photos in grid (special mode)
    BLINDS_H = auto()       # Horizontal blinds
    BLINDS_V = auto()       # Vertical blinds
    SPIRAL = auto()         # Spiral reveal
    DISSOLVE = auto()       # Random pixel dissolve
    GLITCH = auto()         # Glitchy RGB split transition
    WIPE_CIRCLE = auto()    # Circular wipe from center
    HEART = auto()          # Heart-shaped reveal (romantic!)
    FLASH = auto()          # Flash to white then reveal


# Effects that work well for single photo transitions
SINGLE_PHOTO_EFFECTS = [
    TransitionEffect.FADE,
    TransitionEffect.SLIDE_LEFT,
    TransitionEffect.SLIDE_RIGHT,
    TransitionEffect.SLIDE_UP,
    TransitionEffect.SLIDE_DOWN,
    TransitionEffect.ZOOM_IN,
    TransitionEffect.ZOOM_OUT,
    TransitionEffect.PIXELATE,
    TransitionEffect.BLINDS_H,
    TransitionEffect.BLINDS_V,
    TransitionEffect.SPIRAL,
    TransitionEffect.DISSOLVE,
    TransitionEffect.GLITCH,
    TransitionEffect.WIPE_CIRCLE,
    TransitionEffect.HEART,
    TransitionEffect.FLASH,
]


@dataclass
class PhotoItem:
    """A photo item from the gallery."""
    id: str
    src: str              # Thumbnail/preview URL
    title: str
    date: Optional[str] = None


@dataclass
class GalleryState:
    """State for gallery session."""
    phase: GalleryPhase = GalleryPhase.LOADING
    photos: List[PhotoItem] = field(default_factory=list)
    photo_frames: List[NDArray[np.uint8]] = field(default_factory=list)
    current_index: int = 0
    prev_index: int = -1
    loading_progress: float = 0.0
    error_message: str = ""
    # Transition state
    transition_effect: TransitionEffect = TransitionEffect.FADE
    transition_progress: float = 1.0  # 0 = start, 1 = complete
    transition_duration: float = 800.0  # ms
    in_photo_wall: bool = False
    photo_wall_timer: float = 0.0
    photo_wall_duration: float = 6000.0  # Show wall for 6 seconds
    # Snowfall animation
    snowflakes: List[Dict[str, float]] = field(default_factory=list)
    # Dissolve mask (for dissolve effect)
    dissolve_mask: Optional[NDArray[np.float32]] = None


# =============================================================================
# Gallery Preloader Service - Singleton for background photo loading
# =============================================================================

class GalleryPreloader:
    """Background service that preloads gallery photos.

    This runs independently and keeps photos ready for instant gallery start.
    Call start() when the app loads, and the gallery mode will use preloaded photos.
    """

    _instance: Optional['GalleryPreloader'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'GalleryPreloader':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._photos: List[PhotoItem] = []
        self._frames: List[NDArray[np.uint8]] = []
        self._loading = False
        self._ready = False
        self._progress = 0.0
        self._error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._available_dates: List[str] = []
        self._dates_fetched = False

        logger.info("GalleryPreloader initialized")

    @property
    def is_ready(self) -> bool:
        """Check if photos are preloaded and ready."""
        return self._ready and len(self._frames) > 0

    @property
    def is_loading(self) -> bool:
        """Check if currently loading."""
        return self._loading

    @property
    def progress(self) -> float:
        """Get loading progress (0-1)."""
        return self._progress

    @property
    def photos(self) -> List[PhotoItem]:
        """Get preloaded photo metadata."""
        return self._photos.copy()

    @property
    def frames(self) -> List[NDArray[np.uint8]]:
        """Get preloaded photo frames."""
        return self._frames.copy()

    @property
    def error(self) -> Optional[str]:
        """Get error message if loading failed."""
        return self._error

    def start(self, count: int = PHOTOS_PER_BATCH) -> None:
        """Start preloading photos in background.

        Args:
            count: Number of photos to preload
        """
        if self._loading:
            logger.debug("Preloader already loading, skipping")
            return

        self._loading = True
        self._ready = False
        self._progress = 0.0
        self._error = None

        self._thread = threading.Thread(
            target=self._load_photos,
            args=(count,),
            daemon=True,
            name="GalleryPreloader"
        )
        self._thread.start()
        logger.info(f"Started preloading {count} gallery photos")

    def take_photos(self) -> tuple[List[PhotoItem], List[NDArray[np.uint8]]]:
        """Take preloaded photos (clears the preloader).

        Returns:
            Tuple of (photos, frames) - may be empty if not ready
        """
        if not self._ready:
            return [], []

        photos = self._photos
        frames = self._frames

        # Clear preloaded data
        self._photos = []
        self._frames = []
        self._ready = False

        logger.info(f"Took {len(frames)} preloaded photos")
        return photos, frames

    def preload_for_next(self, count: int = PRELOAD_BATCH_SIZE) -> None:
        """Preload photos for next gallery session.

        Call this when exiting gallery mode.
        """
        if self._loading:
            return

        # Start preloading in background
        self.start(count)

    def _fetch_dates(self) -> List[str]:
        """Fetch available photo dates from API."""
        if self._dates_fetched and self._available_dates:
            return self._available_dates

        try:
            dates_url = f"{API_BASE}/dates"
            req = urllib.request.Request(dates_url, headers={'User-Agent': 'VNVNC-Arcade/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            self._available_dates = data.get('dates', [])
            self._dates_fetched = True
            logger.info(f"Fetched {len(self._available_dates)} photo dates")
            return self._available_dates
        except Exception as e:
            logger.warning(f"Failed to fetch dates: {e}")
            return []

    def _load_photos(self, count: int) -> None:
        """Load photos (runs in background thread)."""
        try:
            # Get available dates
            dates = self._fetch_dates()
            if not dates:
                raise ValueError("No photo dates available")

            # Pick random dates and fetch photos
            all_photos = []
            random.shuffle(dates)

            for date in dates[:30]:  # Try more dates to get 50+ photos
                if len(all_photos) >= count:
                    break

                photos_url = f"{API_BASE}/photos?date={date}&limit=50"
                try:
                    req = urllib.request.Request(photos_url, headers={'User-Agent': 'VNVNC-Arcade/1.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode('utf-8'))

                    for p in data.get('photos', []):
                        all_photos.append(PhotoItem(
                            id=p.get('id', ''),
                            src=p.get('src', ''),
                            title=p.get('title', ''),
                            date=p.get('date'),
                        ))

                    self._progress = min(0.3, len(all_photos) / count * 0.3)

                except Exception as e:
                    logger.debug(f"Failed to fetch photos for {date}: {e}")
                    continue

            if not all_photos:
                raise ValueError("No photos found")

            # Shuffle and limit
            random.shuffle(all_photos)
            all_photos = all_photos[:count]

            logger.info(f"Found {len(all_photos)} photos, downloading...")

            # Download and process photos
            photos = []
            frames = []

            for i, photo in enumerate(all_photos):
                try:
                    frame = self._download_photo(photo.src)
                    if frame is not None:
                        photos.append(photo)
                        frames.append(frame)

                    self._progress = 0.3 + (i / len(all_photos)) * 0.7

                except Exception as e:
                    logger.debug(f"Failed to download photo {photo.id}: {e}")
                    continue

            if not frames:
                raise ValueError("No photos could be loaded")

            # Store results
            self._photos = photos
            self._frames = frames
            self._ready = True
            self._progress = 1.0

            logger.info(f"Preloaded {len(frames)} gallery photos")

        except Exception as e:
            logger.error(f"Preloader failed: {e}")
            self._error = str(e)
        finally:
            self._loading = False

    def _download_photo(self, url: str) -> Optional[NDArray[np.uint8]]:
        """Download and process a photo to 128x128."""
        if not url:
            return None

        try:
            from PIL import Image

            # The src URL from the API is already proxied, use it directly
            req = urllib.request.Request(url, headers={'User-Agent': 'VNVNC-Arcade/1.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                img_data = resp.read()

            if len(img_data) < 100:
                return None

            img = Image.open(BytesIO(img_data))
            img = img.convert('RGB')

            # Center crop to square
            w, h = img.size
            if w > h:
                left = (w - h) // 2
                img = img.crop((left, 0, left + h, h))
            elif h > w:
                top = (h - w) // 2
                img = img.crop((0, top, w, top + w))

            img = img.resize((128, 128), Image.Resampling.LANCZOS)
            return np.array(img, dtype=np.uint8)

        except Exception as e:
            logger.debug(f"Failed to download: {e}")
            return None


def get_gallery_preloader() -> GalleryPreloader:
    """Get the singleton gallery preloader instance."""
    return GalleryPreloader()


def start_gallery_preloader() -> None:
    """Start the gallery preloader (call at app startup)."""
    preloader = get_gallery_preloader()
    preloader.start()


# =============================================================================
# Gallery Mode
# =============================================================================

class GalleryMode(BaseMode):
    """Photo gallery mode - endless slideshow of club photos.

    Controls:
    - LEFT: Previous photo
    - RIGHT: Next photo (loads more at end of batch)
    - CENTER: Also next photo
    - BACK: Return to menu
    """

    name = "gallery"
    display_name = "ГАЛЕРЕЯ"
    description = "Фотографии с вечеринок"
    icon = "📷"
    style = "arcade"
    requires_camera = False
    requires_ai = False
    estimated_duration = 300

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._state = GalleryState()
        self._audio = get_audio_engine()
        self._time = 0.0
        self._auto_advance_timer = 0.0
        self._auto_advance_interval = 3000.0  # 3 seconds per photo
        self._photos_since_wall = 0  # Counter to trigger photo wall occasionally
        self._preloader = get_gallery_preloader()

        # Santa runner minigame for loading screen
        self._santa_runner: Optional[SantaRunner] = None

        # Music mute state
        self._music_muted = False

        # Initialize snowflakes
        self._init_snowflakes()

    def _init_snowflakes(self, count: int = 50) -> None:
        """Initialize snowfall particles."""
        self._state.snowflakes = []
        for _ in range(count):
            self._state.snowflakes.append({
                'x': random.uniform(0, 128),
                'y': random.uniform(-20, 128),
                'speed': random.uniform(15, 40),
                'size': random.choice([1, 1, 1, 2]),
                'drift': random.uniform(-0.5, 0.5),
                'phase': random.uniform(0, 6.28),
            })

    def on_enter(self) -> None:
        """Initialize mode and start loading photos."""
        self._state = GalleryState()
        self._time = 0.0
        self._auto_advance_timer = 0.0
        self._photos_since_wall = 0
        self._init_snowflakes()

        # Stop idle music and start gallery music
        self._audio.stop_idle_music()
        self._start_audio()

        self.change_phase(ModePhase.INTRO)

        # Try to use preloaded photos first
        if self._preloader.is_ready:
            photos, frames = self._preloader.take_photos()
            if frames:
                logger.info(f"Using {len(frames)} preloaded photos")
                self._state.photos = photos
                self._state.photo_frames = frames
                self._state.phase = GalleryPhase.VIEWING
                self._state.current_index = 0
                self.change_phase(ModePhase.ACTIVE)
                return

        # Check if preloader is still loading - wait for it
        if self._preloader.is_loading:
            logger.info("Waiting for preloader to finish...")
            self._state.phase = GalleryPhase.LOADING
            # Initialize Santa runner minigame for the waiting screen
            self._santa_runner = SantaRunner()
            self._santa_runner.reset()
            # We'll check preloader progress in on_update
            return

        # No preloaded photos - start loading fresh
        logger.info("No preloaded photos, loading fresh")
        self._start_loading()

        logger.info("GalleryMode entered")

    def on_exit(self) -> None:
        """Cleanup resources and preload for next session."""
        self._stop_audio()

        # Preload photos for next session
        self._preloader.preload_for_next(PRELOAD_BATCH_SIZE)

        logger.info("GalleryMode exited, started preloading for next session")

    def _start_audio(self) -> None:
        """Start playing gallery background music."""
        try:
            import pygame
            import pygame.mixer

            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)

            # Use the 2025 video audio
            audio_path = Path(__file__).parent.parent.parent.parent / "assets" / "videos" / "2025video" / "lightson_128x128.wav"

            if audio_path.exists():
                pygame.mixer.music.stop()
                pygame.mixer.music.load(str(audio_path))
                pygame.mixer.music.set_volume(0.7)
                pygame.mixer.music.play(loops=-1)  # Loop forever
                logger.info(f"Gallery music started: {audio_path.name}")
            else:
                logger.warning(f"Gallery audio not found: {audio_path}")

        except Exception as e:
            logger.warning(f"Failed to start gallery audio: {e}")

    def _stop_audio(self) -> None:
        """Stop audio playback."""
        try:
            import pygame.mixer
            pygame.mixer.music.stop()
        except Exception:
            pass

    def _toggle_music_mute(self) -> None:
        """Toggle music mute/unmute."""
        try:
            import pygame.mixer
            self._music_muted = not self._music_muted
            if self._music_muted:
                pygame.mixer.music.set_volume(0.0)
                logger.info("Gallery music muted")
            else:
                pygame.mixer.music.set_volume(0.7)
                logger.info("Gallery music unmuted")
            self._audio.play_ui_click()
        except Exception as e:
            logger.warning(f"Failed to toggle music mute: {e}")

    def _start_loading(self) -> None:
        """Start loading photos in background."""
        self._state.phase = GalleryPhase.LOADING
        self._state.loading_progress = 0.0

        # Initialize Santa runner minigame for the loading screen
        self._santa_runner = SantaRunner()
        self._santa_runner.reset()

        try:
            thread = threading.Thread(target=self._load_photos_sync, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"Failed to start loading thread: {e}")
            self._state.phase = GalleryPhase.ERROR
            self._state.error_message = "Ошибка загрузки"

    def _load_photos_sync(self) -> None:
        """Load photos synchronously (runs in thread)."""
        try:
            # First, get available dates
            dates_url = f"{API_BASE}/dates"
            logger.info(f"Fetching dates from {dates_url}")

            req = urllib.request.Request(dates_url, headers={'User-Agent': 'VNVNC-Arcade/1.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                dates_data = json.loads(resp.read().decode('utf-8'))

            dates = dates_data.get('dates', [])
            if not dates:
                raise ValueError("No dates available")

            logger.info(f"Found {len(dates)} dates")

            # Pick random dates and fetch photos
            all_photos = []
            random.shuffle(dates)

            for date in dates[:30]:  # Try up to 30 dates to get 50+ photos
                if len(all_photos) >= PHOTOS_PER_BATCH:
                    break

                photos_url = f"{API_BASE}/photos?date={date}&limit=50"
                try:
                    req = urllib.request.Request(photos_url, headers={'User-Agent': 'VNVNC-Arcade/1.0'})
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        photos_data = json.loads(resp.read().decode('utf-8'))

                    photos = photos_data.get('photos', [])
                    for p in photos:
                        all_photos.append(PhotoItem(
                            id=p.get('id', ''),
                            src=p.get('src', ''),  # This is the thumbnail URL
                            title=p.get('title', ''),
                            date=p.get('date'),
                        ))

                    self._state.loading_progress = min(0.3, len(all_photos) / PHOTOS_PER_BATCH * 0.3)

                except Exception as e:
                    logger.warning(f"Failed to fetch photos for {date}: {e}")
                    continue

            if not all_photos:
                raise ValueError("No photos found")

            # Shuffle and limit
            random.shuffle(all_photos)
            all_photos = all_photos[:PHOTOS_PER_BATCH]

            logger.info(f"Found {len(all_photos)} photos, downloading...")

            # Download and process photos
            self._state.photos = all_photos
            self._state.photo_frames = []

            for i, photo in enumerate(all_photos):
                try:
                    frame = self._download_and_process_photo(photo.src)
                    if frame is not None:
                        self._state.photo_frames.append(frame)

                    self._state.loading_progress = 0.3 + (i / len(all_photos)) * 0.7

                except Exception as e:
                    logger.warning(f"Failed to download photo {photo.id}: {e}")
                    continue

            if not self._state.photo_frames:
                raise ValueError("No photos could be loaded")

            logger.info(f"Loaded {len(self._state.photo_frames)} photo frames")
            self._state.phase = GalleryPhase.VIEWING
            self._state.current_index = 0
            self.change_phase(ModePhase.ACTIVE)

        except Exception as e:
            logger.error(f"Photo loading failed: {e}")
            self._state.phase = GalleryPhase.ERROR
            self._state.error_message = f"Ошибка: {str(e)[:20]}"

    def _download_and_process_photo(self, url: str) -> Optional[NDArray[np.uint8]]:
        """Download photo and process to 128x128 square."""
        if not url:
            return None

        try:
            from PIL import Image

            # The src URL from the API is already proxied, use it directly
            req = urllib.request.Request(url, headers={'User-Agent': 'VNVNC-Arcade/1.0'})
            with urllib.request.urlopen(req, timeout=15) as resp:
                img_data = resp.read()

            if len(img_data) < 100:
                return None

            img = Image.open(BytesIO(img_data))
            img = img.convert('RGB')

            # Center crop to square
            w, h = img.size
            if w > h:
                left = (w - h) // 2
                img = img.crop((left, 0, left + h, h))
            elif h > w:
                top = (h - w) // 2
                img = img.crop((0, top, w, top + w))

            # Resize to 128x128
            img = img.resize((128, 128), Image.Resampling.LANCZOS)

            return np.array(img, dtype=np.uint8)

        except Exception as e:
            logger.debug(f"Failed to process photo from {url[:50]}...: {e}")
            return None

    def _load_more_photos(self) -> None:
        """Load more photos when reaching end of batch."""
        if self._state.phase == GalleryPhase.LOADING:
            return

        logger.info("Loading more photos...")
        self._start_loading()

    def _start_transition(self, new_index: int, effect: Optional[TransitionEffect] = None) -> None:
        """Start a transition to a new photo."""
        if not self._state.photo_frames:
            return

        self._state.prev_index = self._state.current_index
        self._state.current_index = new_index % len(self._state.photo_frames)
        self._state.transition_progress = 0.0

        # Choose random effect if not specified
        if effect is None:
            # Occasionally show photo wall (every 8-12 photos)
            self._photos_since_wall += 1
            if self._photos_since_wall >= random.randint(8, 12) and len(self._state.photo_frames) >= 9:
                self._photos_since_wall = 0
                self._state.in_photo_wall = True
                self._state.photo_wall_timer = 0.0
                self._state.transition_effect = TransitionEffect.PHOTO_WALL
            else:
                self._state.transition_effect = random.choice(SINGLE_PHOTO_EFFECTS)
        else:
            self._state.transition_effect = effect

        # Generate dissolve mask for dissolve effect
        if self._state.transition_effect == TransitionEffect.DISSOLVE:
            self._state.dissolve_mask = np.random.random((128, 128)).astype(np.float32)

        # Vary transition duration
        self._state.transition_duration = random.uniform(600, 1200)

    def on_input(self, event: Event) -> bool:
        """Handle input events."""
        if self._state.phase == GalleryPhase.ERROR:
            self.complete(ModeResult(
                mode_name=self.name,
                success=False,
                display_text="Ошибка загрузки",
            ))
            return True

        # Handle asterisk to mute/unmute music
        if event.type == EventType.KEYPAD_INPUT and event.data.get("key") == "*":
            self._toggle_music_mute()
            return True

        # Handle jump for Santa runner during loading
        if self._state.phase == GalleryPhase.LOADING:
            if event.type == EventType.BUTTON_PRESS and self._santa_runner:
                self._santa_runner.handle_jump()
                self._audio.play_ui_click()
                return True
            return False

        # Skip photo wall on any input
        if self._state.in_photo_wall:
            self._state.in_photo_wall = False
            return True

        if event.type == EventType.ARCADE_LEFT:
            self._prev_photo()
            return True

        elif event.type == EventType.ARCADE_RIGHT:
            self._next_photo()
            return True

        elif event.type == EventType.BUTTON_PRESS:
            self._next_photo()
            return True

        elif event.type == EventType.BACK:
            self.complete(ModeResult(
                mode_name=self.name,
                success=True,
                display_text="Галерея",
            ))
            return True

        return False

    def _prev_photo(self) -> None:
        """Go to previous photo."""
        if self._state.photo_frames:
            new_idx = (self._state.current_index - 1) % len(self._state.photo_frames)
            self._start_transition(new_idx)
            self._auto_advance_timer = 0.0
            self._audio.play_ui_move()

    def _next_photo(self) -> None:
        """Go to next photo, load more if at end."""
        if not self._state.photo_frames:
            return

        if self._state.current_index >= len(self._state.photo_frames) - 1:
            self._load_more_photos()
            new_idx = 0
        else:
            new_idx = self._state.current_index + 1

        self._start_transition(new_idx)
        self._auto_advance_timer = 0.0
        self._audio.play_ui_move()

    def on_update(self, delta_ms: float) -> None:
        """Update animation state."""
        self._time += delta_ms

        # Update snowfall
        self._update_snowflakes(delta_ms)

        # Update Santa runner minigame during loading
        if self._state.phase == GalleryPhase.LOADING and self._santa_runner:
            self._santa_runner.update(delta_ms)

        # Check if preloader finished while we were waiting
        if self._state.phase == GalleryPhase.LOADING and not self._state.photo_frames:
            if self._preloader.is_ready:
                photos, frames = self._preloader.take_photos()
                if frames:
                    logger.info(f"Preloader finished, using {len(frames)} photos")
                    self._state.photos = photos
                    self._state.photo_frames = frames
                    self._state.phase = GalleryPhase.VIEWING
                    self._state.current_index = 0
                    self.change_phase(ModePhase.ACTIVE)
                    return
            elif self._preloader.is_loading:
                # Update progress from preloader
                self._state.loading_progress = self._preloader.progress
            elif self._preloader.error:
                # Preloader failed, start our own loading
                if not hasattr(self, '_fallback_started'):
                    self._fallback_started = True
                    self._start_loading()

        # Update transition
        if self._state.transition_progress < 1.0:
            self._state.transition_progress += delta_ms / self._state.transition_duration
            self._state.transition_progress = min(1.0, self._state.transition_progress)

        # Update photo wall timer
        if self._state.in_photo_wall:
            self._state.photo_wall_timer += delta_ms
            if self._state.photo_wall_timer >= self._state.photo_wall_duration:
                self._state.in_photo_wall = False

        # Auto-advance in viewing mode
        if self._state.phase == GalleryPhase.VIEWING and not self._state.in_photo_wall:
            self._auto_advance_timer += delta_ms
            if self._auto_advance_timer >= self._auto_advance_interval:
                self._auto_advance_timer = 0.0
                if self._state.photo_frames:
                    new_idx = (self._state.current_index + 1) % len(self._state.photo_frames)
                    self._start_transition(new_idx)

    def _update_snowflakes(self, delta_ms: float) -> None:
        """Update snowfall animation."""
        dt = delta_ms / 1000.0

        for flake in self._state.snowflakes:
            flake['y'] += flake['speed'] * dt
            flake['x'] += flake['drift'] + math.sin(self._time / 500 + flake['phase']) * 0.3

            if flake['y'] > 130:
                flake['y'] = -5
                flake['x'] = random.uniform(0, 128)
            if flake['x'] < -5:
                flake['x'] = 133
            elif flake['x'] > 133:
                flake['x'] = -5

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        if self._state.phase == GalleryPhase.LOADING:
            self._render_loading(buffer)
        elif self._state.phase == GalleryPhase.ERROR:
            self._render_error(buffer)
        else:
            self._render_slideshow(buffer)

    def _render_loading(self, buffer: NDArray[np.uint8]) -> None:
        """Render Santa runner minigame while loading photos."""
        # Render the Santa runner game (uses its own gradient sky background)
        if self._santa_runner:
            self._santa_runner.render(buffer, background=None)

            # Add compact progress bar at the top
            bar_w, bar_h = 100, 4
            bar_x = (128 - bar_w) // 2
            bar_y = 2

            # Semi-transparent dark background for progress bar
            draw_rect(buffer, bar_x - 2, bar_y - 1, bar_w + 4, bar_h + 2, (20, 20, 40))

            # Progress bar fill (Christmas gradient: red to green)
            progress = self._state.loading_progress
            progress_width = int(bar_w * progress)
            if progress_width > 0:
                r = int(200 * (1 - progress))
                g = int(200 * progress)
                draw_rect(buffer, bar_x, bar_y, progress_width, bar_h, (r, g, 100))

            # Show compact status at bottom
            percent = int(progress * 100)
            # Semi-transparent dark strip for text
            draw_rect(buffer, 0, 118, 128, 10, (20, 20, 40))
            draw_centered_text(buffer, f"ЗАГРУЗКА ФОТО {percent}%", 119, (200, 200, 200), scale=1)

            # Add snowflakes overlay
            self._render_snowflakes(buffer, alpha=0.7)

        else:
            # Fallback to simple loading screen if no game
            for y in range(128):
                darkness = int(20 + y * 0.15)
                buffer[y, :, 0] = darkness
                buffer[y, :, 1] = darkness // 2
                buffer[y, :, 2] = darkness + 10

            self._render_snowflakes(buffer, alpha=0.5)
            draw_centered_text(buffer, "ГАЛЕРЕЯ", 30, (255, 200, 100), scale=2)
            draw_centered_text(buffer, "ЗАГРУЗКА...", 60, (200, 200, 200), scale=1)

    def _render_error(self, buffer: NDArray[np.uint8]) -> None:
        """Render error screen."""
        fill(buffer, (40, 20, 20))
        draw_centered_text(buffer, "ОШИБКА", 40, (255, 100, 100), scale=2)
        if self._state.error_message:
            draw_centered_text(buffer, self._state.error_message[:16], 70, (200, 150, 150), scale=1)
        draw_centered_text(buffer, "НАЖМИ КНОПКУ", 100, (150, 150, 150), scale=1)

    def _render_slideshow(self, buffer: NDArray[np.uint8]) -> None:
        """Render current photo with transition effect."""
        if not self._state.photo_frames:
            fill(buffer, (30, 30, 40))
            draw_centered_text(buffer, "НЕТ ФОТО", 60, (200, 200, 200), scale=2)
            return

        # Photo wall mode - special rendering
        if self._state.in_photo_wall:
            self._render_photo_wall(buffer)
            self._render_snowflakes(buffer, alpha=0.7)
            return

        # Get current and previous frames
        curr_idx = self._state.current_index % len(self._state.photo_frames)
        curr_frame = self._state.photo_frames[curr_idx]

        prev_frame = None
        if self._state.prev_index >= 0 and self._state.prev_index < len(self._state.photo_frames):
            prev_frame = self._state.photo_frames[self._state.prev_index]

        # Apply transition effect
        progress = self._state.transition_progress
        effect = self._state.transition_effect

        if progress >= 1.0 or prev_frame is None:
            # No transition - just show current photo
            buffer[:, :, :] = curr_frame
        else:
            # Apply transition effect
            self._apply_transition(buffer, prev_frame, curr_frame, progress, effect)

        # Apply vignette
        self._apply_vignette(buffer)

        # Render snowfall overlay
        self._render_snowflakes(buffer, alpha=1.0)


    def _apply_transition(self, buffer: NDArray, prev: NDArray, curr: NDArray,
                          progress: float, effect: TransitionEffect) -> None:
        """Apply transition effect between two frames."""
        # Ease function for smoother transitions
        t = self._ease_in_out(progress)

        if effect == TransitionEffect.FADE:
            # Cross-fade
            buffer[:, :, :] = (prev * (1 - t) + curr * t).astype(np.uint8)

        elif effect == TransitionEffect.SLIDE_LEFT:
            offset = int(128 * t)
            buffer[:, :128 - offset, :] = prev[:, offset:, :]
            buffer[:, 128 - offset:, :] = curr[:, :offset, :]

        elif effect == TransitionEffect.SLIDE_RIGHT:
            offset = int(128 * t)
            buffer[:, offset:, :] = prev[:, :128 - offset, :]
            buffer[:, :offset, :] = curr[:, 128 - offset:, :]

        elif effect == TransitionEffect.SLIDE_UP:
            offset = int(128 * t)
            buffer[:128 - offset, :, :] = prev[offset:, :, :]
            buffer[128 - offset:, :, :] = curr[:offset, :, :]

        elif effect == TransitionEffect.SLIDE_DOWN:
            offset = int(128 * t)
            buffer[offset:, :, :] = prev[:128 - offset, :, :]
            buffer[:offset, :, :] = curr[128 - offset:, :, :]

        elif effect == TransitionEffect.ZOOM_IN:
            # Zoom from center
            scale = 1.0 + t * 0.5  # Scale up to 1.5x
            self._render_zoomed(buffer, prev, scale, 1 - t)
            self._blend_frame(buffer, curr, t)

        elif effect == TransitionEffect.ZOOM_OUT:
            # Zoom out from large
            scale = 1.5 - t * 0.5  # Scale down from 1.5x
            self._render_zoomed(buffer, curr, scale, t)
            self._blend_frame(buffer, prev, 1 - t)

        elif effect == TransitionEffect.PIXELATE:
            # Pixelate transition
            block_size = max(1, int(16 * (1 - abs(t - 0.5) * 2)))  # Peak at middle
            if t < 0.5:
                self._render_pixelated(buffer, prev, block_size)
            else:
                self._render_pixelated(buffer, curr, block_size)

        elif effect == TransitionEffect.BLINDS_H:
            # Horizontal blinds
            num_blinds = 8
            blind_height = 128 // num_blinds
            for i in range(num_blinds):
                y_start = i * blind_height
                revealed = int(blind_height * t)
                if revealed > 0:
                    buffer[y_start:y_start + revealed, :, :] = curr[y_start:y_start + revealed, :, :]
                if blind_height - revealed > 0:
                    buffer[y_start + revealed:y_start + blind_height, :, :] = prev[y_start + revealed:y_start + blind_height, :, :]

        elif effect == TransitionEffect.BLINDS_V:
            # Vertical blinds
            num_blinds = 8
            blind_width = 128 // num_blinds
            for i in range(num_blinds):
                x_start = i * blind_width
                revealed = int(blind_width * t)
                if revealed > 0:
                    buffer[:, x_start:x_start + revealed, :] = curr[:, x_start:x_start + revealed, :]
                if blind_width - revealed > 0:
                    buffer[:, x_start + revealed:x_start + blind_width, :] = prev[:, x_start + revealed:x_start + blind_width, :]

        elif effect == TransitionEffect.SPIRAL:
            # Spiral reveal from center
            self._render_spiral(buffer, prev, curr, t)

        elif effect == TransitionEffect.DISSOLVE:
            # Random pixel dissolve
            if self._state.dissolve_mask is not None:
                mask = (self._state.dissolve_mask < t)[:, :, np.newaxis]
                buffer[:, :, :] = np.where(mask, curr, prev)
            else:
                buffer[:, :, :] = curr

        elif effect == TransitionEffect.GLITCH:
            # Glitchy RGB split
            self._render_glitch(buffer, prev, curr, t)

        elif effect == TransitionEffect.WIPE_CIRCLE:
            # Circular wipe from center
            y_coords = np.arange(128)[:, np.newaxis]
            x_coords = np.arange(128)[np.newaxis, :]
            dist = np.sqrt((x_coords - 64) ** 2 + (y_coords - 64) ** 2)
            max_dist = 90  # ~corner distance
            mask = (dist < max_dist * t)[:, :, np.newaxis]
            buffer[:, :, :] = np.where(mask, curr, prev)

        elif effect == TransitionEffect.HEART:
            # Heart-shaped reveal
            self._render_heart_reveal(buffer, prev, curr, t)

        elif effect == TransitionEffect.FLASH:
            # Flash to white then reveal
            if t < 0.3:
                # Fade to white
                white_t = t / 0.3
                buffer[:, :, :] = (prev * (1 - white_t) + 255 * white_t).astype(np.uint8)
            elif t < 0.5:
                # Pure white
                buffer[:, :, :] = 255
            else:
                # Fade from white to new image
                reveal_t = (t - 0.5) / 0.5
                buffer[:, :, :] = (255 * (1 - reveal_t) + curr * reveal_t).astype(np.uint8)

        else:
            # Default to instant
            buffer[:, :, :] = curr

    def _ease_in_out(self, t: float) -> float:
        """Smooth ease in-out function."""
        return t * t * (3 - 2 * t)

    def _render_zoomed(self, buffer: NDArray, frame: NDArray, scale: float, alpha: float) -> None:
        """Render a zoomed frame."""
        h, w = 128, 128
        new_size = int(128 * scale)

        # Calculate crop region from center
        offset = (new_size - 128) // 2

        try:
            from PIL import Image
            img = Image.fromarray(frame)
            img = img.resize((new_size, new_size), Image.Resampling.BILINEAR)
            cropped = np.array(img)[offset:offset + 128, offset:offset + 128]

            if alpha >= 1.0:
                buffer[:, :, :] = cropped
            else:
                buffer[:, :, :] = (buffer * (1 - alpha) + cropped * alpha).astype(np.uint8)
        except Exception:
            buffer[:, :, :] = frame

    def _blend_frame(self, buffer: NDArray, frame: NDArray, alpha: float) -> None:
        """Blend a frame onto the buffer."""
        if alpha > 0:
            buffer[:, :, :] = (buffer * (1 - alpha) + frame * alpha).astype(np.uint8)

    def _render_pixelated(self, buffer: NDArray, frame: NDArray, block_size: int) -> None:
        """Render pixelated version of frame."""
        if block_size <= 1:
            buffer[:, :, :] = frame
            return

        for y in range(0, 128, block_size):
            for x in range(0, 128, block_size):
                # Average color of block
                block = frame[y:y + block_size, x:x + block_size]
                avg_color = block.mean(axis=(0, 1)).astype(np.uint8)
                buffer[y:y + block_size, x:x + block_size] = avg_color

    def _render_spiral(self, buffer: NDArray, prev: NDArray, curr: NDArray, t: float) -> None:
        """Render spiral reveal effect."""
        y_coords = np.arange(128)[:, np.newaxis]
        x_coords = np.arange(128)[np.newaxis, :]

        # Calculate angle and distance from center
        dx = x_coords - 64
        dy = y_coords - 64
        angle = np.arctan2(dy, dx) + np.pi  # 0 to 2*pi
        dist = np.sqrt(dx ** 2 + dy ** 2)

        # Spiral threshold
        spiral_threshold = (angle / (2 * np.pi) + dist / 90) * 0.5
        mask = (spiral_threshold < t)[:, :, np.newaxis]

        buffer[:, :, :] = np.where(mask, curr, prev)

    def _render_glitch(self, buffer: NDArray, prev: NDArray, curr: NDArray, t: float) -> None:
        """Render glitchy RGB split transition."""
        # RGB channel offsets
        offset = int(10 * math.sin(t * 10) * (1 - t))

        if t < 0.5:
            # Glitch on prev
            buffer[:, :, 0] = np.roll(prev[:, :, 0], offset, axis=1)
            buffer[:, :, 1] = prev[:, :, 1]
            buffer[:, :, 2] = np.roll(prev[:, :, 2], -offset, axis=1)
        else:
            # Glitch on curr
            glitch_t = (t - 0.5) * 2
            buffer[:, :, 0] = np.roll(curr[:, :, 0], int(offset * (1 - glitch_t)), axis=1)
            buffer[:, :, 1] = curr[:, :, 1]
            buffer[:, :, 2] = np.roll(curr[:, :, 2], int(-offset * (1 - glitch_t)), axis=1)

        # Random horizontal line glitches
        if random.random() < 0.3:
            glitch_y = random.randint(0, 120)
            glitch_h = random.randint(2, 8)
            glitch_offset = random.randint(-20, 20)
            buffer[glitch_y:glitch_y + glitch_h, :, :] = np.roll(
                buffer[glitch_y:glitch_y + glitch_h, :, :], glitch_offset, axis=1
            )

    def _render_heart_reveal(self, buffer: NDArray, prev: NDArray, curr: NDArray, t: float) -> None:
        """Render heart-shaped reveal."""
        y_coords = np.arange(128)[:, np.newaxis] / 64 - 1  # -1 to 1
        x_coords = np.arange(128)[np.newaxis, :] / 64 - 1  # -1 to 1

        # Heart equation: (x^2 + y^2 - 1)^3 - x^2 * y^3 < 0
        # Adjusted for better shape
        x = x_coords * 1.2
        y = -y_coords * 1.2 + 0.2  # Flip and shift up

        heart = (x ** 2 + y ** 2 - 1) ** 3 - x ** 2 * y ** 3
        threshold = 0.5 - t * 1.5  # Expand from center

        mask = (heart < threshold)[:, :, np.newaxis]
        buffer[:, :, :] = np.where(mask, curr, prev)

    def _render_photo_wall(self, buffer: NDArray) -> None:
        """Render photo wall mode - 3x3 grid of photos."""
        if len(self._state.photo_frames) < 9:
            return

        # Pick 9 random photos (or sequential from current)
        indices = []
        start_idx = self._state.current_index
        for i in range(9):
            idx = (start_idx + i) % len(self._state.photo_frames)
            indices.append(idx)

        # Render 3x3 grid
        tile_size = 128 // 3  # ~42 pixels each

        for i, idx in enumerate(indices):
            row = i // 3
            col = i % 3

            x_start = col * tile_size + (col + 1)  # Small gaps
            y_start = row * tile_size + (row + 1)

            frame = self._state.photo_frames[idx]

            # Resize frame to tile size
            try:
                from PIL import Image
                img = Image.fromarray(frame)
                img = img.resize((tile_size - 2, tile_size - 2), Image.Resampling.BILINEAR)
                tile = np.array(img)

                h, w = tile.shape[:2]
                buffer[y_start:y_start + h, x_start:x_start + w, :] = tile
            except Exception:
                # Fallback - just copy scaled down
                step = 128 // (tile_size - 2)
                for ty in range(tile_size - 2):
                    for tx in range(tile_size - 2):
                        sy = min(ty * step, 127)
                        sx = min(tx * step, 127)
                        buffer[y_start + ty, x_start + tx, :] = frame[sy, sx, :]

        # Add subtle animation - pulsing border
        pulse = int(20 + 10 * math.sin(self._time / 200))
        border_color = (pulse, pulse, pulse + 20)

        # Top and bottom borders
        buffer[0, :, :] = border_color
        buffer[127, :, :] = border_color
        # Left and right borders
        buffer[:, 0, :] = border_color
        buffer[:, 127, :] = border_color

        # Grid lines
        for i in range(1, 3):
            pos = i * (128 // 3)
            buffer[pos, :, :] = border_color
            buffer[:, pos, :] = border_color

    def _apply_vignette(self, buffer: NDArray[np.uint8]) -> None:
        """Apply subtle vignette effect."""
        h, w = buffer.shape[:2]

        y_coords = np.arange(h)[:, np.newaxis]
        x_coords = np.arange(w)[np.newaxis, :]

        cy, cx = h / 2, w / 2
        dist = np.sqrt((x_coords - cx) ** 2 + (y_coords - cy) ** 2)
        max_dist = np.sqrt(cx ** 2 + cy ** 2)

        vignette = 1.0 - (dist / max_dist) ** 2 * 0.3
        vignette = np.clip(vignette, 0.7, 1.0)

        buffer[:, :, 0] = (buffer[:, :, 0] * vignette).astype(np.uint8)
        buffer[:, :, 1] = (buffer[:, :, 1] * vignette).astype(np.uint8)
        buffer[:, :, 2] = (buffer[:, :, 2] * vignette).astype(np.uint8)

    def _render_snowflakes(self, buffer: NDArray[np.uint8], alpha: float = 1.0) -> None:
        """Render snowfall overlay."""
        for flake in self._state.snowflakes:
            x = int(flake['x'])
            y = int(flake['y'])
            size = flake['size']

            brightness = int(200 + size * 25)

            if 0 <= x < 128 and 0 <= y < 128:
                if alpha < 1.0:
                    old = buffer[y, x]
                    new_r = int(old[0] * (1 - alpha) + brightness * alpha)
                    new_g = int(old[1] * (1 - alpha) + brightness * alpha)
                    new_b = int(old[2] * (1 - alpha) + brightness * alpha)
                    buffer[y, x] = (min(255, new_r), min(255, new_g), min(255, new_b))
                else:
                    buffer[y, x] = (brightness, brightness, brightness)

                if size >= 2:
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < 128 and 0 <= ny < 128:
                            dim = brightness // 2
                            if alpha < 1.0:
                                old = buffer[ny, nx]
                                buffer[ny, nx] = (
                                    min(255, int(old[0] + dim * alpha)),
                                    min(255, int(old[1] + dim * alpha)),
                                    min(255, int(old[2] + dim * alpha))
                                )
                            else:
                                buffer[ny, nx] = (dim, dim, dim)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, render_ticker_static, TickerEffect, TextEffect

        clear(buffer)

        if self._state.phase == GalleryPhase.LOADING:
            text = "ЗАГРУЗКА..."
            color = (255, 200, 100)
            render_ticker_static(buffer, text, self._time_in_phase, color, TextEffect.PULSE)
        elif self._state.phase == GalleryPhase.ERROR:
            text = "ОШИБКА"
            color = (255, 100, 100)
            render_ticker_static(buffer, text, self._time_in_phase, color, TextEffect.GLOW)
        else:
            text = "ФОТО С ВЕЧЕРИНОК VNVNC"
            color = (100, 200, 255)
            render_ticker_animated(buffer, text, self._time_in_phase, color, TickerEffect.SCROLL, speed=0.02)

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self._state.phase == GalleryPhase.LOADING:
            percent = int(self._state.loading_progress * 100)
            return f"ЗАГРУЗКА {percent}%".center(16)[:16]
        elif self._state.phase == GalleryPhase.ERROR:
            return "ОШИБКА СЕТИ".center(16)[:16]
        elif self._state.in_photo_wall:
            return "ФОТО СТЕНА".center(16)[:16]
        else:
            return "VNVNC ГАЛЕРЕЯ".center(16)[:16]

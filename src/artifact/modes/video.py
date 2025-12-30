"""Video Player Mode - Play videos and photo slideshows with audio.

Features:
- Selection menu to choose between 3 albums
- Album 1 (2025 WRAPPED): Video → auto-slideshow (audio continues), 4/6 to navigate slideshow
- Album 2 (SAGA): Video playback with looping audio
- Album 3 (LIVE АРХИВ): Playlist of randomized archive videos
"""

import logging
import random
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, field
from enum import Enum, auto

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.text_utils import draw_centered_text
from artifact.audio.engine import get_audio_engine
from artifact.utils.audio_utils import extract_audio_from_video

logger = logging.getLogger(__name__)


class PlaybackPhase(Enum):
    """Phase within VideoMode."""
    SELECTING = auto()   # In selection menu
    PLAYING = auto()     # Playing selected album


class ViewMode(Enum):
    """Current view mode within an album."""
    VIDEO = auto()
    SLIDESHOW = auto()


class AlbumType(Enum):
    """Type of album for different playback behavior."""
    STANDARD = auto()      # Single video + optional slideshow (album 1)
    VIDEO_ONLY = auto()    # Single video, no slideshow (album 2)
    PLAYLIST = auto()      # Multiple videos played in sequence (album 3)


@dataclass
class VideoAlbum:
    """A video album with optional slideshow images."""
    name: str
    display_name: str
    album_type: AlbumType = AlbumType.STANDARD
    video_path: Optional[Path] = None
    # For playlist albums (multiple videos)
    video_paths: List[Path] = field(default_factory=list)
    current_video_index: int = 0
    # For slideshows
    images: List[Path] = field(default_factory=list)
    image_frames: List[NDArray[np.uint8]] = field(default_factory=list)
    # Dates for each image (DD.MM.YY format)
    image_dates: List[str] = field(default_factory=list)


@dataclass
class VideoState:
    """State for video player session."""
    albums: List[VideoAlbum] = field(default_factory=list)
    selected_album: int = 0      # Currently highlighted in menu
    current_album: int = -1       # Actually playing (-1 = none)
    playback_phase: PlaybackPhase = PlaybackPhase.SELECTING
    view_mode: ViewMode = ViewMode.VIDEO
    # Video state
    video_capture: object = None
    video_playing: bool = True
    video_finished: bool = False  # Track if video naturally ended
    video_loop_mode: bool = False  # If True, video loops forever (press 0)
    video_playback_time: float = 0.0  # Time spent playing video
    # Slideshow state
    slideshow_index: int = 0
    slideshow_paused: bool = False
    slideshow_time: float = 0.0
    slideshow_interval: float = 1500.0  # 1.5 seconds per image


# Auto-slideshow timeout for 2025 WRAPPED (20 seconds)
AUTO_SLIDESHOW_TIMEOUT = 20000.0  # ms


class VideoMode(BaseMode):
    """Video player mode - play videos and photo slideshows.

    Controls:
    - In menu: LEFT/RIGHT to select, CENTER to confirm
    - In album 1: LEFT/RIGHT to navigate slideshow, BACK to return to menu
    - In albums 2/3: BACK to return to menu
    """

    name = "video"
    display_name = "ВИДЕО"
    description = "Видео и фото плеер"
    icon = "▶"
    style = "arcade"
    requires_camera = False
    requires_ai = False
    estimated_duration = 300

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._state = VideoState()
        self._cv2_available = False
        self._pil_available = False
        self._pygame_mixer_available = False
        self._current_audio_path: Optional[Path] = None
        self._selection_pulse = 0.0  # For selection animation

    def on_enter(self) -> None:
        """Initialize mode and show selection menu."""
        self._state = VideoState()
        self._check_dependencies()
        self._load_albums()
        self._selection_pulse = 0.0

        # Stop ALL audio from the engine - we take over audio
        audio = get_audio_engine()
        audio.stop_idle_music()
        audio.stop_all()  # Stop everything

        # Start in selection mode (INTRO phase)
        self._state.playback_phase = PlaybackPhase.SELECTING
        self.change_phase(ModePhase.INTRO)
        logger.info(f"VideoMode entered - {len(self._state.albums)} albums available")

    def on_exit(self) -> None:
        """Cleanup video and audio resources."""
        self._stop_video()
        self._stop_audio()

    def _check_dependencies(self) -> None:
        """Check available libraries."""
        try:
            from PIL import Image
            self._pil_available = True
        except ImportError:
            logger.warning("PIL not available")

        try:
            import cv2
            self._cv2_available = True
        except ImportError:
            logger.warning("OpenCV not available")

        try:
            import pygame.mixer
            self._pygame_mixer_available = True
        except ImportError:
            logger.warning("pygame.mixer not available")

    def _load_albums(self) -> None:
        """Load all video albums."""
        assets_dir = Path(__file__).parent.parent.parent.parent / "assets" / "videos"

        # Album 1: 2025 WRAPPED (video + slideshow with continuous audio)
        wrapped_dir = assets_dir / "2025video"
        if wrapped_dir.exists():
            album = VideoAlbum(
                name="2025_wrapped",
                display_name="2025 WRAPPED",
                album_type=AlbumType.STANDARD
            )
            # Find video
            for video_file in wrapped_dir.glob("*.mp4"):
                album.video_path = video_file
                break
            # Find images (sorted)
            image_files = sorted(
                list(wrapped_dir.glob("*.jpg")) +
                list(wrapped_dir.glob("*.png"))
            )
            album.images = image_files
            self._load_album_images(album)
            if album.video_path or album.image_frames:
                self._state.albums.append(album)
                logger.info(f"Loaded 2025 WRAPPED: video={album.video_path is not None}, images={len(album.image_frames)}")

        # Album 2: SAGA (video only, no slideshow)
        saga_video = assets_dir / "saga-squarecrop_128x128.mp4"
        if saga_video.exists():
            album = VideoAlbum(
                name="saga",
                display_name="САГА",
                album_type=AlbumType.VIDEO_ONLY,
                video_path=saga_video
            )
            self._state.albums.append(album)
            logger.info("Loaded SAGA video")

        # Album 3: LIVE АРХИВ (randomized playlist)
        archive_dir = assets_dir / "live_archive"
        if archive_dir.exists():
            video_files = list(archive_dir.glob("*.mp4"))
            if video_files:
                random.shuffle(video_files)
                album = VideoAlbum(
                    name="live_archive",
                    display_name="LIVE АРХИВ",
                    album_type=AlbumType.PLAYLIST,
                    video_paths=video_files,
                    current_video_index=0
                )
                self._state.albums.append(album)
                logger.info(f"Loaded LIVE АРХИВ: {len(video_files)} videos")

    def _load_album_images(self, album: VideoAlbum) -> None:
        """Load and resize images for an album, extracting dates from filenames."""
        if not self._pil_available or not album.images:
            return

        from PIL import Image
        import re

        for img_path in album.images:
            try:
                img = Image.open(img_path).convert('RGB')
                img = img.resize((128, 128), Image.Resampling.LANCZOS)
                album.image_frames.append(np.array(img, dtype=np.uint8))

                # Extract date from filename (format: YYYY-MM-DD_*.jpg)
                match = re.match(r'(\d{4})-(\d{2})-(\d{2})', img_path.stem)
                if match:
                    year, month, day = match.groups()
                    # Format as DD.MM.YY
                    date_str = f"{day}.{month}.{year[2:]}"
                    album.image_dates.append(date_str)
                else:
                    # Fallback - just use filename
                    album.image_dates.append(img_path.stem[:10])

            except Exception as e:
                logger.warning(f"Failed to load image {img_path.name}: {e}")

    def _start_album_playback(self, album_idx: int) -> None:
        """Start playing the selected album."""
        if album_idx >= len(self._state.albums):
            return

        self._state.current_album = album_idx
        self._state.playback_phase = PlaybackPhase.PLAYING
        self._state.video_finished = False
        self._state.video_loop_mode = False  # Reset loop mode
        self._state.video_playback_time = 0.0  # Reset playback timer

        album = self._state.albums[album_idx]

        if album.album_type == AlbumType.PLAYLIST:
            # Playlist - play videos in sequence
            self._state.view_mode = ViewMode.VIDEO
            album.current_video_index = 0
            if album.video_paths:
                video_path = album.video_paths[0]
                self._start_video(video_path)
                self._start_audio(video_path)
                logger.info(f"Starting playlist: {video_path.name}")
        elif album.video_path:
            # Standard or video-only - start video
            self._state.view_mode = ViewMode.VIDEO
            self._start_video(album.video_path)
            self._start_audio(album.video_path)
            logger.info(f"Starting video: {album.video_path.name}")
        elif album.image_frames:
            # No video, start slideshow directly
            self._state.view_mode = ViewMode.SLIDESHOW
            self._state.slideshow_index = 0

        self.change_phase(ModePhase.ACTIVE)

    def _start_video(self, path: Path) -> None:
        """Start video playback."""
        if not self._cv2_available:
            return

        import cv2
        self._stop_video()
        self._state.video_capture = cv2.VideoCapture(str(path))
        self._state.video_playing = True
        self._state.video_finished = False

    def _stop_video(self) -> None:
        """Stop video playback."""
        if self._state.video_capture:
            self._state.video_capture.release()
            self._state.video_capture = None

    def _start_audio(self, video_path: Path) -> None:
        """Extract and play audio from video (looped)."""
        try:
            import pygame
            import pygame.mixer

            # Ensure mixer is initialized
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=2048)
                logger.info("Initialized pygame.mixer for video audio")

            # Stop any existing music first
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass

            # Only extract if we have a different video
            if self._current_audio_path != video_path:
                logger.info(f"Extracting audio from {video_path.name}...")
                audio_path = extract_audio_from_video(video_path)

                if audio_path and audio_path.exists():
                    logger.info(f"Loading audio: {audio_path}")
                    pygame.mixer.music.load(str(audio_path))
                    pygame.mixer.music.set_volume(0.8)
                    pygame.mixer.music.play(loops=-1)
                    self._current_audio_path = video_path
                    logger.info(f"Audio playing from {audio_path.name}")
                else:
                    logger.error(f"Audio extraction failed for {video_path.name}")
                    self._current_audio_path = None
            else:
                # Same video, just resume
                if not pygame.mixer.music.get_busy():
                    pygame.mixer.music.play(loops=-1)
                    logger.info("Resumed audio playback")

        except Exception as e:
            logger.exception(f"Failed to start audio: {e}")
            self._current_audio_path = None

    def _stop_audio(self) -> None:
        """Stop audio playback."""
        if self._pygame_mixer_available:
            try:
                import pygame.mixer
                pygame.mixer.music.stop()
                self._current_audio_path = None
            except Exception:
                pass

    def _get_video_frame(self) -> Optional[NDArray[np.uint8]]:
        """Get current frame from video."""
        if not self._cv2_available or not self._state.video_capture:
            return None

        import cv2

        if not self._state.video_capture.isOpened():
            return None

        ret, frame = self._state.video_capture.read()
        if not ret:
            # Video ended
            album = self._state.albums[self._state.current_album]

            if album.album_type == AlbumType.PLAYLIST:
                # Playlist - advance to next video
                self._state.video_playing = False
                self._state.video_finished = True
                return None
            elif album.album_type == AlbumType.VIDEO_ONLY:
                # Video-only - always loop
                self._state.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._state.video_capture.read()
                if not ret:
                    return None
            elif self._state.video_loop_mode:
                # Standard album with loop mode - loop forever
                self._state.video_capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._state.video_capture.read()
                if not ret:
                    return None
            else:
                # Standard album - video ended, switch to slideshow
                self._state.video_finished = True
                return None

        # Convert BGR to RGB and resize
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if frame.shape[0] != 128 or frame.shape[1] != 128:
            frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_AREA)
        return frame

    def _advance_playlist(self) -> None:
        """Advance to next video in playlist."""
        album = self._state.albums[self._state.current_album]
        if album.album_type != AlbumType.PLAYLIST or not album.video_paths:
            return

        album.current_video_index = (album.current_video_index + 1) % len(album.video_paths)
        self._stop_video()
        video_path = album.video_paths[album.current_video_index]
        self._start_video(video_path)
        self._start_audio(video_path)
        self._state.video_finished = False
        logger.info(f"Playlist: {album.current_video_index + 1}/{len(album.video_paths)}")

    def _switch_to_slideshow(self) -> None:
        """Switch to slideshow mode (for album 1)."""
        album = self._state.albums[self._state.current_album]
        if not album.image_frames:
            return

        self._stop_video()
        self._state.view_mode = ViewMode.SLIDESHOW
        self._state.slideshow_index = 0
        self._state.slideshow_time = 0.0
        # Audio keeps playing!
        logger.info("Switched to slideshow (audio continues)")

    def _return_to_menu(self) -> None:
        """Return to selection menu."""
        self._stop_video()
        self._stop_audio()
        self._state.playback_phase = PlaybackPhase.SELECTING
        self._state.current_album = -1
        self._state.view_mode = ViewMode.VIDEO
        self.change_phase(ModePhase.INTRO)
        logger.info("Returned to selection menu")

    def on_input(self, event: Event) -> bool:
        """Handle input based on current phase."""
        if self._state.playback_phase == PlaybackPhase.SELECTING:
            return self._handle_selection_input(event)
        else:
            return self._handle_playback_input(event)

    def _handle_selection_input(self, event: Event) -> bool:
        """Handle input in selection menu."""
        if not self._state.albums:
            return False

        if event.type == EventType.ARCADE_LEFT:
            # Previous album
            self._state.selected_album = (self._state.selected_album - 1) % len(self._state.albums)
            return True
        elif event.type == EventType.ARCADE_RIGHT:
            # Next album
            self._state.selected_album = (self._state.selected_album + 1) % len(self._state.albums)
            return True
        elif event.type == EventType.BUTTON_PRESS:
            # Confirm selection - start playback
            self._start_album_playback(self._state.selected_album)
            return True
        elif event.type == EventType.KEYPAD_INPUT:
            # Direct selection via numpad 1-3
            key = event.data.get("key", "")
            if key in ("1", "2", "3"):
                idx = int(key) - 1
                if idx < len(self._state.albums):
                    self._state.selected_album = idx
                    self._start_album_playback(idx)
                    return True

        return False

    def _handle_playback_input(self, event: Event) -> bool:
        """Handle input during playback."""
        if self._state.current_album < 0:
            return False

        album = self._state.albums[self._state.current_album]

        # BACK returns to menu
        if event.type == EventType.BACK:
            self._return_to_menu()
            return True

        # Keypad 0 enables loop mode for 2025 WRAPPED (STANDARD album)
        if event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "0" and album.album_type == AlbumType.STANDARD:
                if self._state.view_mode == ViewMode.VIDEO and not self._state.video_loop_mode:
                    self._state.video_loop_mode = True
                    logger.info("Loop mode enabled - video will loop forever")
                    return True

        # Album 1 (STANDARD): LEFT/RIGHT navigate slideshow
        if album.album_type == AlbumType.STANDARD:
            if event.type == EventType.ARCADE_LEFT:
                # Navigate slideshow backward
                if self._state.view_mode != ViewMode.SLIDESHOW:
                    self._switch_to_slideshow()
                if album.image_frames:
                    self._state.slideshow_index = (self._state.slideshow_index - 1) % len(album.image_frames)
                    self._state.slideshow_time = 0.0
                return True
            elif event.type == EventType.ARCADE_RIGHT:
                # Navigate slideshow forward
                if self._state.view_mode != ViewMode.SLIDESHOW:
                    self._switch_to_slideshow()
                if album.image_frames:
                    self._state.slideshow_index = (self._state.slideshow_index + 1) % len(album.image_frames)
                    self._state.slideshow_time = 0.0
                return True

        # Album 3 (PLAYLIST): LEFT/RIGHT could skip videos
        if album.album_type == AlbumType.PLAYLIST:
            if event.type == EventType.ARCADE_LEFT:
                # Previous video in playlist
                album.current_video_index = (album.current_video_index - 1) % len(album.video_paths)
                self._stop_video()
                video_path = album.video_paths[album.current_video_index]
                self._start_video(video_path)
                self._start_audio(video_path)
                return True
            elif event.type == EventType.ARCADE_RIGHT:
                # Next video in playlist
                self._advance_playlist()
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        """Update video/slideshow playback."""
        self._selection_pulse += delta_ms * 0.003

        if self._state.playback_phase == PlaybackPhase.SELECTING:
            return  # Nothing to update in menu

        if self._state.current_album < 0:
            return

        album = self._state.albums[self._state.current_album]

        # Track video playback time for auto-slideshow timeout
        if self._state.view_mode == ViewMode.VIDEO:
            self._state.video_playback_time += delta_ms

            # Check for auto-slideshow timeout (only for STANDARD albums not in loop mode)
            if (album.album_type == AlbumType.STANDARD and
                not self._state.video_loop_mode and
                album.image_frames and
                self._state.video_playback_time >= AUTO_SLIDESHOW_TIMEOUT):
                logger.info("Auto-slideshow timeout - switching to slideshow")
                self._switch_to_slideshow()

        # Check for video end and handle accordingly
        if self._state.view_mode == ViewMode.VIDEO:
            if self._state.video_finished:
                if album.album_type == AlbumType.PLAYLIST:
                    self._advance_playlist()
                elif album.album_type == AlbumType.STANDARD and album.image_frames:
                    # Switch to slideshow automatically (video ended naturally)
                    self._switch_to_slideshow()
                else:
                    self._state.video_finished = False

        # Update slideshow
        if self._state.view_mode == ViewMode.SLIDESHOW:
            self._state.slideshow_time += delta_ms
            if self._state.slideshow_time >= self._state.slideshow_interval:
                self._state.slideshow_time = 0.0
                if album.image_frames:
                    self._state.slideshow_index = (self._state.slideshow_index + 1) % len(album.image_frames)

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render current state to main display."""
        fill(buffer, (0, 0, 0))

        if not self._state.albums:
            draw_centered_text(buffer, "НЕТ ВИДЕО", 50, (255, 255, 255), scale=2)
            draw_centered_text(buffer, "Добавьте в", 75, (150, 150, 150), scale=1)
            draw_centered_text(buffer, "assets/videos/", 90, (150, 150, 150), scale=1)
            return

        if self._state.playback_phase == PlaybackPhase.SELECTING:
            self._render_selection_menu(buffer)
        else:
            self._render_playback(buffer)

    def _render_selection_menu(self, buffer: NDArray[np.uint8]) -> None:
        """Render beautiful album selection menu with borders and snowfall."""
        import math

        t = self._selection_pulse

        # Animated snowfall background
        self._render_snowfall_bg(buffer, t)

        # Draw decorative border
        border_color = (100, 150, 200)  # Ice blue
        # Top border with sparkle
        for x in range(128):
            brightness = int(80 + 40 * math.sin(x * 0.2 + t * 2))
            buffer[0, x] = (brightness, brightness + 20, brightness + 50)
            buffer[1, x] = (brightness // 2, brightness // 2 + 10, brightness // 2 + 25)
        # Bottom border
        for x in range(128):
            brightness = int(80 + 40 * math.sin(x * 0.2 - t * 2))
            buffer[126, x] = (brightness // 2, brightness // 2 + 10, brightness // 2 + 25)
            buffer[127, x] = (brightness, brightness + 20, brightness + 50)
        # Side borders
        for y in range(128):
            brightness = int(60 + 30 * math.sin(y * 0.15 + t))
            buffer[y, 0] = (brightness, brightness + 15, brightness + 40)
            buffer[y, 1] = (brightness // 2, brightness // 2 + 8, brightness // 2 + 20)
            buffer[y, 126] = (brightness // 2, brightness // 2 + 8, brightness // 2 + 20)
            buffer[y, 127] = (brightness, brightness + 15, brightness + 40)

        # Title with glow effect
        draw_centered_text(buffer, "ВИДЕО", 18, (255, 220, 150), scale=2)

        # Calculate animation pulse for selection
        pulse = 0.5 + 0.5 * math.sin(t * 3)
        sel_brightness = int(100 + 155 * pulse)

        # Album options with beautiful styling
        start_y = 45
        item_height = 26

        for i, album in enumerate(self._state.albums):
            y = start_y + i * item_height
            is_selected = (i == self._state.selected_album)

            if is_selected:
                # Glowing selection box
                glow_color = (sel_brightness // 3, sel_brightness // 2, sel_brightness)
                # Outer glow
                draw_rect(buffer, 6, y - 4, 116, 22, (glow_color[0] // 2, glow_color[1] // 2, glow_color[2] // 2))
                # Inner box
                draw_rect(buffer, 8, y - 2, 112, 18, glow_color)
                # Highlight line at top
                draw_line(buffer, 10, y - 2, 118, y - 2, (255, 255, 255))
                text_color = (255, 255, 255)
            else:
                # Subtle box for unselected
                draw_rect(buffer, 10, y - 1, 108, 16, (30, 40, 50))
                text_color = (150, 150, 160)

            # Draw name only (no number prefix - numpad 1-3 works for selection)
            draw_centered_text(buffer, album.display_name[:12], y + 8, text_color, scale=1)

    def _render_snowfall_bg(self, buffer: NDArray[np.uint8], t: float) -> None:
        """Render animated snowfall background."""
        import math

        # Dark blue gradient background
        for y in range(128):
            darkness = int(15 + y * 0.1)
            buffer[y, :, 0] = darkness // 2
            buffer[y, :, 1] = darkness // 2 + 5
            buffer[y, :, 2] = darkness + 10

        # Animated snowflakes
        num_flakes = 30
        for i in range(num_flakes):
            # Deterministic but animated positions
            phase = i * 1.7
            speed = 0.5 + (i % 5) * 0.2
            x = int((math.sin(phase + t * 0.3) * 0.5 + 0.5) * 120 + 4)
            y = int((t * speed * 0.02 + phase * 0.3) % 1.0 * 128)

            # Varying sizes and brightness
            size = 1 + (i % 3)
            brightness = 150 + (i % 4) * 25

            # Draw snowflake (small cross or dot)
            if 0 <= x < 128 and 0 <= y < 128:
                buffer[y, x] = (brightness, brightness, brightness)
                if size > 1 and x > 0:
                    buffer[y, x - 1] = (brightness // 2, brightness // 2, brightness // 2)
                if size > 1 and x < 127:
                    buffer[y, x + 1] = (brightness // 2, brightness // 2, brightness // 2)

    def _render_playback(self, buffer: NDArray[np.uint8]) -> None:
        """Render current playback."""
        if self._state.current_album < 0:
            return

        album = self._state.albums[self._state.current_album]

        if self._state.view_mode == ViewMode.VIDEO:
            frame = self._get_video_frame()
            if frame is not None:
                buffer[:, :, :] = frame
            else:
                # Video loading or error - show album name
                draw_centered_text(buffer, "▶", 50, (255, 100, 100), scale=3)
                draw_centered_text(buffer, album.display_name[:12], 95, (200, 200, 200), scale=1)
        else:
            # Slideshow
            if album.image_frames:
                idx = self._state.slideshow_index % len(album.image_frames)
                buffer[:, :, :] = album.image_frames[idx]

                # Progress indicator at bottom
                num_images = len(album.image_frames)
                indicator_width = 128 // num_images
                current_x = (self._state.slideshow_index % num_images) * indicator_width
                draw_rect(buffer, current_x, 126, indicator_width, 2, (255, 200, 100))
            else:
                draw_centered_text(buffer, "?", 50, (255, 100, 100), scale=3)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display with scrolling for long text."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import draw_text
        import math

        clear(buffer)  # ALWAYS clear buffer first!

        if not self._state.albums:
            draw_centered_text(buffer, "ВИДЕО", 1, (255, 255, 255), scale=1)
            return

        if self._state.playback_phase == PlaybackPhase.SELECTING:
            # In menu - show current selection with scrolling for long names
            album = self._state.albums[self._state.selected_album]
            text = album.display_name
            color = (255, 200, 100)
            self._render_ticker_text(buffer, text, color)
        else:
            album = self._state.albums[self._state.current_album]

            if self._state.view_mode == ViewMode.VIDEO:
                if album.album_type == AlbumType.PLAYLIST:
                    idx = album.current_video_index + 1
                    total = len(album.video_paths)
                    text = f"#{idx}/{total}"
                    color = (100, 200, 255)
                    self._render_ticker_text(buffer, text, color)
                elif self._state.video_loop_mode:
                    # Loop mode - show "VNVNC 2026" with scrolling
                    text = "VNVNC 2026"
                    color = (100, 255, 150)  # Mint green
                    self._render_ticker_text(buffer, text, color)
                elif album.album_type == AlbumType.STANDARD and album.image_frames:
                    # Show awesome loading bar for countdown to slideshow
                    self._render_countdown_bar(buffer)
                else:
                    text = album.display_name
                    color = (255, 100, 100)
                    self._render_ticker_text(buffer, text, color)
            else:
                # Slideshow - show date in DD.MM.YY format
                idx = self._state.slideshow_index % len(album.image_frames)
                if album.image_dates and idx < len(album.image_dates):
                    text = album.image_dates[idx]
                else:
                    text = f"{idx + 1}/{len(album.image_frames)}"
                color = (255, 200, 100)
                self._render_ticker_text(buffer, text, color)

    def _render_ticker_text(self, buffer: NDArray[np.uint8], text: str, color: tuple) -> None:
        """Render ticker text with horizontal scrolling for long text."""
        from artifact.graphics.text_utils import draw_text

        char_width = 6
        text_width = len(text) * char_width
        ticker_width = buffer.shape[1]  # 48 pixels

        if text_width <= ticker_width:
            # Short text - center it
            x = (ticker_width - text_width) // 2
            draw_text(buffer, text, x, 1, color, scale=1)
        else:
            # Long text - smooth scroll back and forth
            t = self._selection_pulse * 1000  # Convert to ms-like value
            scroll_period = 3000  # 3 seconds for full scroll cycle

            # Ping-pong scroll: 0 -> max -> 0
            cycle_pos = (t % scroll_period) / scroll_period
            # Ease in-out
            if cycle_pos < 0.5:
                progress = 2 * cycle_pos
                eased = 2 * progress * progress if progress < 0.5 else 1 - pow(-2 * progress + 2, 2) / 2
            else:
                progress = 2 * (1 - cycle_pos)
                eased = 2 * progress * progress if progress < 0.5 else 1 - pow(-2 * progress + 2, 2) / 2

            max_offset = text_width - ticker_width
            x_offset = int(eased * max_offset)
            draw_text(buffer, text, -x_offset, 1, color, scale=1)

    def _render_countdown_bar(self, buffer: NDArray[np.uint8]) -> None:
        """Render animated countdown bar in cyan/teal blue style."""
        import math

        h, w = buffer.shape[:2]  # 8x48
        progress = min(1.0, self._state.video_playback_time / AUTO_SLIDESHOW_TIMEOUT)
        t = self._selection_pulse

        # Fill width based on progress
        fill_width = int(progress * w)

        # Cyan/teal color palette
        for x in range(w):
            for y in range(h):
                if x < fill_width:
                    # Filled portion - animated cyan/teal gradient
                    # Base cyan color with wave animation
                    wave = math.sin(x * 0.2 + t * 4 + y * 0.3) * 0.25 + 0.75

                    # Gradient from teal to cyan across the bar
                    grad = x / max(fill_width, 1)
                    r = int(20 * wave)
                    g = int((180 + 50 * grad) * wave)
                    b = int((200 + 55 * grad) * wave)

                    # Bright leading edge glow
                    if x >= fill_width - 4:
                        edge_factor = 1 - (fill_width - 1 - x) / 4
                        r = min(255, int(r + 80 * edge_factor))
                        g = min(255, int(g + 75 * edge_factor))
                        b = min(255, int(b + 55 * edge_factor))

                    buffer[y, x] = (r, g, b)
                else:
                    # Unfilled portion - dark blue background
                    # Subtle shimmer effect
                    shimmer = math.sin(x * 0.4 + t * 2 + y * 0.5) * 0.5 + 0.5
                    if shimmer > 0.92:
                        buffer[y, x] = (15, 40, 50)
                    else:
                        buffer[y, x] = (5, 15, 25)

        # Add bright cyan particles floating along filled area
        num_particles = 4
        for i in range(num_particles):
            if fill_width > 5:
                particle_x = int((math.sin(t * 1.5 + i * 1.7) * 0.4 + 0.5) * fill_width)
                particle_y = int((math.sin(t * 2.3 + i * 2.5) * 0.5 + 0.5) * (h - 1))
                if 0 <= particle_x < w and 0 <= particle_y < h:
                    buffer[particle_y, particle_x] = (150, 255, 255)

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if not self._state.albums:
            return "   НЕТ ВИДЕО   "

        if self._state.playback_phase == PlaybackPhase.SELECTING:
            album = self._state.albums[self._state.selected_album]
            idx = self._state.selected_album + 1
            total = len(self._state.albums)
            # Format: "1/3 NAME" - up to 12 chars for name
            name = album.display_name[:12]
            return f"{idx}/{total} {name}".center(16)[:16]

        album = self._state.albums[self._state.current_album]

        if self._state.view_mode == ViewMode.SLIDESHOW:
            idx = self._state.slideshow_index % len(album.image_frames)
            if album.image_dates and idx < len(album.image_dates):
                # Show date in DD.MM.YY format
                return album.image_dates[idx].center(16)[:16]
            else:
                img_total = len(album.image_frames)
                return f"{idx + 1}/{img_total} ФОТО".center(16)[:16]

        if album.album_type == AlbumType.PLAYLIST:
            vid_idx = album.current_video_index + 1
            vid_total = len(album.video_paths)
            return f"{vid_idx}/{vid_total} ВИДЕО".center(16)[:16]

        # Show loop mode indicator
        if self._state.video_loop_mode:
            return "VNVNC 2026".center(16)[:16]

        return album.display_name[:14].center(16)[:16]

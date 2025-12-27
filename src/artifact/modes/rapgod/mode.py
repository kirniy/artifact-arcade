"""RapGod mode - AI-generated rap tracks from selected words.

User flow:
1. Select 4 words from slot-machine style UI
2. Optionally add a "joker" rule
3. AI generates Russian lyrics (Gemini 3.0 Flash)
4. Suno API generates the actual track with vocals
5. Audio preview plays, QR code shown for download
6. Receipt printed with track title, hook, and download link
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import random
import math
import numpy as np

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.graphics.primitives import fill, draw_rect, clear
from artifact.graphics.text_utils import (
    draw_centered_text,
    draw_animated_text,
    draw_button_labels,
    draw_text,
    TextEffect,
)
from artifact.graphics.fonts import load_font
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase

from artifact.modes.rapgod.wordbank import WordBank, WordSelection, GENRES, SUB_GENRES, MOODS, VIBES
from artifact.modes.rapgod.lyrics import LyricsGenerator, GeneratedLyrics
from artifact.modes.rapgod.suno import get_suno_client, SunoClient, TrackStatus
from artifact.modes.rapgod.audio import (
    AudioPlayer,
    upload_to_selectel,
    format_duration,
)
from artifact.modes.rapgod.runner import RunnerGame
from artifact.utils.s3_upload import generate_qr_image as generate_qr_numpy
from artifact.utils.camera import floyd_steinberg_dither, create_viewfinder_overlay
from artifact.utils.camera_service import camera_service

logger = logging.getLogger(__name__)


class RapGodPhase:
    """Sub-phases within RapGod mode."""

    INTRO = "intro"              # Welcome animation
    GENRE_SELECT = "genre"       # Pick trap/drill/cloud/boombap/phonk
    SUBGENRE_SELECT = "subgenre" # Pick sub-genre variation
    MOOD_SELECT = "mood"         # Pick emotional mood
    VIBE_SELECT = "vibe"         # Pick overall atmosphere
    WORD_SELECT = "words"        # Select 4 words + joker (slot-machine style)
    CAMERA_PREP = "camera_prep"  # Show camera preview
    CAMERA_CAPTURE = "capture"   # Countdown and capture
    PROCESSING = "processing"    # Generating lyrics + music
    PREVIEW = "preview"          # Playing audio, showing QR
    RESULT = "result"            # Final display


# Colors for different genres (matching GENRES in wordbank)
GENRE_COLORS = {
    "trap": (255, 50, 100),     # Hot pink
    "drill": (100, 100, 255),   # Blue
    "cloud": (200, 150, 255),   # Lavender
    "boombap": (255, 180, 50),  # Gold
    "phonk": (150, 50, 200),    # Purple
    "hyperpop": (255, 100, 255), # Magenta
    "rage": (255, 0, 50),       # Red
    "plugg": (100, 200, 150),   # Teal
}

# Custom progress messages for rap generation
RAPGOD_MESSAGES = {
    ProgressPhase.INITIALIZING: [
        "Запуск студии...",
        "Включаю микрофон...",
    ],
    ProgressPhase.ANALYZING: [
        "Придумываю тему...",
        "Ищу вдохновение...",
        "Ловлю вайб...",
    ],
    ProgressPhase.GENERATING_TEXT: [
        "Пишу текст...",
        "Рифмую строки...",
        "Качаю флоу...",
        "Дописываю панчи...",
    ],
    ProgressPhase.GENERATING_IMAGE: [
        "Варю бит...",
        "Записываю вокал...",
        "Сводим трек...",
        "Мастерим звук...",
    ],
    ProgressPhase.FINALIZING: [
        "Мастеринг...",
        "Почти готово...",
        "Релиз скоро...",
    ],
}


class RapGodMode(BaseMode):
    """AI rap track generator from user-selected words."""

    name = "rap_god"
    display_name = "RAP GOD"
    description = "Сгенерируй трек из случайных слов!"
    icon = "MIC"

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Services
        self._wordbank = WordBank()
        self._lyrics_gen = LyricsGenerator()
        self._suno = get_suno_client()
        self._audio_player = AudioPlayer()

        # State
        self._sub_phase = RapGodPhase.INTRO
        self._genre = "trap"
        self._genre_index = 0
        self._genres = list(GENRES.keys())

        # Vibe selector state
        self._sub_genre: Optional[str] = None
        self._sub_genre_index = 0
        self._mood: Optional[str] = None
        self._mood_index = 0
        self._vibe: Optional[str] = None
        self._vibe_index = 0

        # Word selection state - simple 3-option picker
        self._current_slot = 0  # 0-3 for 4 word slots, then 4 = joker slot
        self._slot_options: List[List[str]] = []  # 3 options per slot
        self._option_index = 0  # Current highlighted option (0-2)
        self._selected_words: List[str] = []  # Final selected words (4)
        self._joker_options: List[str] = []  # 3 joker options
        self._joker_text: Optional[str] = None  # Selected joker rule

        # Camera state
        self._camera_frame: Optional[np.ndarray] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0

        # Generation state
        self._lyrics: Optional[GeneratedLyrics] = None
        self._task_id: Optional[str] = None
        self._audio_url: Optional[str] = None
        self._audio_bytes: Optional[bytes] = None
        self._download_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None
        self._generation_task: Optional[asyncio.Task] = None
        self._generation_error: Optional[str] = None  # Error message if failed
        self._track_still_processing: bool = False  # True if Suno timed out but still running

        # Progress tracking
        self._progress_tracker = SmartProgressTracker(mode_theme="rapgod")
        self._progress_tracker.set_custom_messages(RAPGOD_MESSAGES)

        # Runner mini-game (during processing)
        self._runner = RunnerGame()

        # Particles
        self._particles = ParticleSystem()

        # UI state
        self._result_view = "qr"  # "qr" or "lyrics"

        # Font
        self._font = load_font("cyrillic")

    def on_enter(self) -> None:
        """Initialize mode."""
        logger.info("RapGod mode entered")
        self._sub_phase = RapGodPhase.INTRO
        self._reset_selection()

        # Reset camera state
        self._camera_frame = None
        self._photo_data = None
        self._camera_countdown = 0.0
        self._flash_alpha = 0.0

    def _reset_selection(self) -> None:
        """Reset word selection state for 3-option picker."""
        self._current_slot = 0
        self._option_index = 0
        self._slot_options = []
        self._selected_words = []
        self._joker_text = None

        # Generate 3 options per slot from different categories
        for i in range(4):
            options = self._wordbank.get_slot_options(i)
            self._slot_options.append(options)

        # Generate 3 joker options (including "skip" option)
        all_jokers = self._wordbank.get_all_jokers()
        random.shuffle(all_jokers)
        self._joker_options = ["БЕЗ ДЖОКЕРА"] + all_jokers[:2]

    def on_exit(self) -> None:
        """Cleanup on mode exit."""
        # Cancel any pending generation
        if self._generation_task and not self._generation_task.done():
            self._generation_task.cancel()

        # Stop audio
        asyncio.create_task(self._audio_player.stop())

        logger.info("RapTrack mode exited")

    def on_update(self, delta_ms: int) -> None:
        """Update mode state each frame."""
        # Update particles
        self._particles.update(delta_ms)

        # Update camera preview in camera phases
        if self._sub_phase in (RapGodPhase.CAMERA_PREP, RapGodPhase.CAMERA_CAPTURE):
            self._update_camera_preview()
            # Decay flash
            if self._flash_alpha > 0:
                self._flash_alpha = max(0, self._flash_alpha - delta_ms / 300)

        # Handle camera capture countdown
        if self._sub_phase == RapGodPhase.CAMERA_CAPTURE:
            self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)
            if self._camera_countdown <= 0 and self._photo_data is None:
                self._do_capture()
            # After flash, start processing
            if self._time_in_phase > 3500:
                self._start_generation()

        # Update progress tracker and runner game during processing
        if self._sub_phase == RapGodPhase.PROCESSING:
            self._progress_tracker.update(delta_ms)

            # Update runner game
            self._update_runner_camera()
            self._runner.update(delta_ms)

            # Check if generation is complete
            if self._generation_task and self._generation_task.done():
                try:
                    self._generation_task.result()  # Check for exceptions
                except Exception as e:
                    logger.error(f"Generation failed: {e}")

                self._on_generation_complete()

        # Auto-advance from intro after 2 seconds
        if self._sub_phase == RapGodPhase.INTRO:
            if self._time_in_phase > 2000:
                self._sub_phase = RapGodPhase.GENRE_SELECT

        # Auto-advance from camera prep after 2 seconds
        if self._sub_phase == RapGodPhase.CAMERA_PREP:
            if self._time_in_phase > 2000:
                self._sub_phase = RapGodPhase.CAMERA_CAPTURE
                self._time_in_phase = 0
                self._camera_countdown = 3.0

    def on_input(self, event: Event) -> bool:
        """Handle user input."""
        if event.type == EventType.BUTTON_PRESS:
            return self._handle_button(event.data.get("button", ""))

        if event.type == EventType.ARCADE_LEFT:
            return self._handle_left()

        if event.type == EventType.ARCADE_RIGHT:
            return self._handle_right()

        if event.type == EventType.ARCADE_UP:
            return self._handle_up()

        if event.type == EventType.ARCADE_DOWN:
            return self._handle_down()

        return False

    def _handle_button(self, button: str) -> bool:
        """Handle button press."""
        if button in ("enter", "select", "start"):
            return self._handle_confirm()
        if button == "back":
            return self._handle_back()
        return False

    def _handle_confirm(self) -> bool:
        """Handle confirm/enter action - select current option or jump in game."""
        # During processing, confirm = jump in runner game
        if self._sub_phase == RapGodPhase.PROCESSING:
            if self._runner.is_game_over:
                self._runner.reset()
            else:
                self._runner.jump()
            return True

        if self._sub_phase == RapGodPhase.INTRO:
            self._sub_phase = RapGodPhase.GENRE_SELECT
            return True

        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre = self._genres[self._genre_index]
            # Move to sub-genre selection
            self._sub_genre_index = 0
            self._sub_phase = RapGodPhase.SUBGENRE_SELECT
            return True

        if self._sub_phase == RapGodPhase.SUBGENRE_SELECT:
            sub_genres = SUB_GENRES.get(self._genre, [])
            if sub_genres and self._sub_genre_index < len(sub_genres):
                self._sub_genre = sub_genres[self._sub_genre_index]["id"]
            # Move to mood selection
            self._mood_index = 0
            self._sub_phase = RapGodPhase.MOOD_SELECT
            return True

        if self._sub_phase == RapGodPhase.MOOD_SELECT:
            if self._mood_index < len(MOODS):
                self._mood = MOODS[self._mood_index]["id"]
            # Move to vibe selection
            self._vibe_index = 0
            self._sub_phase = RapGodPhase.VIBE_SELECT
            return True

        if self._sub_phase == RapGodPhase.VIBE_SELECT:
            if self._vibe_index < len(VIBES):
                self._vibe = VIBES[self._vibe_index]["id"]
            # Move to word selection
            self._option_index = 0
            self._sub_phase = RapGodPhase.WORD_SELECT
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            if self._current_slot < 4:
                # Select word from current slot
                options = self._slot_options[self._current_slot]
                if self._option_index < len(options):
                    word = options[self._option_index]
                    self._selected_words.append(word)
                    self._current_slot += 1
                    self._option_index = 0  # Reset for next slot

                    # Move to joker slot after 4 words
                    if self._current_slot >= 4:
                        self._current_slot = 4  # Joker slot
            else:
                # Joker slot (4) - select and proceed
                joker = self._joker_options[self._option_index] if self._option_index < len(self._joker_options) else "БЕЗ ДЖОКЕРА"
                if joker != "БЕЗ ДЖОКЕРА":
                    self._joker_text = joker
                # All done - move to camera
                self._sub_phase = RapGodPhase.CAMERA_PREP
                self._time_in_phase = 0
            return True

        if self._sub_phase == RapGodPhase.CAMERA_PREP:
            # Skip to capture immediately on confirm
            self._sub_phase = RapGodPhase.CAMERA_CAPTURE
            self._time_in_phase = 0
            self._camera_countdown = 3.0
            return True

        if self._sub_phase == RapGodPhase.PREVIEW:
            # Move to final result
            self._sub_phase = RapGodPhase.RESULT
            self.change_phase(ModePhase.RESULT)
            return True

        if self._sub_phase == RapGodPhase.RESULT:
            # Finish mode
            self._finish()
            return True

        return False

    def _handle_back(self) -> bool:
        """Handle back action - go to previous slot."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._sub_phase = RapGodPhase.INTRO
            return True

        if self._sub_phase == RapGodPhase.SUBGENRE_SELECT:
            self._sub_phase = RapGodPhase.GENRE_SELECT
            return True

        if self._sub_phase == RapGodPhase.MOOD_SELECT:
            self._sub_phase = RapGodPhase.SUBGENRE_SELECT
            return True

        if self._sub_phase == RapGodPhase.VIBE_SELECT:
            self._sub_phase = RapGodPhase.MOOD_SELECT
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            if self._current_slot == 4:
                # At joker slot - go back to word slot 3
                self._current_slot = 3
                if self._selected_words:
                    self._selected_words.pop()
                self._option_index = 0
            elif self._current_slot > 0:
                # Go back to previous word slot
                self._current_slot -= 1
                if self._selected_words:
                    self._selected_words.pop()
                self._option_index = 0
            else:
                # At first slot - go back to vibe
                self._sub_phase = RapGodPhase.VIBE_SELECT
            return True

        if self._sub_phase == RapGodPhase.CAMERA_PREP:
            # Go back to joker slot
            self._sub_phase = RapGodPhase.WORD_SELECT
            self._current_slot = 4
            self._joker_text = None
            self._option_index = 0
            return True

        return False

    def _handle_left(self) -> bool:
        """Handle left arrow - get new options for current slot."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre_index = (self._genre_index - 1) % len(self._genres)
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            # Get new options for current slot
            if self._current_slot < 4:
                self._slot_options[self._current_slot] = self._wordbank.get_slot_options(
                    self._current_slot + random.randint(0, 100)
                )
                self._option_index = 0
            else:
                # Shuffle joker options
                all_jokers = self._wordbank.get_all_jokers()
                random.shuffle(all_jokers)
                self._joker_options = ["БЕЗ ДЖОКЕРА"] + all_jokers[:2]
                self._option_index = 0
            return True

        if self._sub_phase == RapGodPhase.RESULT:
            self._result_view = "lyrics" if self._result_view == "qr" else "qr"
            return True

        return False

    def _handle_right(self) -> bool:
        """Handle right arrow - get new options (same as left)."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre_index = (self._genre_index + 1) % len(self._genres)
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            # Get new options (same as left)
            return self._handle_left()

        if self._sub_phase == RapGodPhase.RESULT:
            self._result_view = "lyrics" if self._result_view == "qr" else "qr"
            return True

        return False

    def _handle_up(self) -> bool:
        """Handle up arrow - move selection up."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre_index = (self._genre_index - 1) % len(self._genres)
            return True

        if self._sub_phase == RapGodPhase.SUBGENRE_SELECT:
            sub_genres = SUB_GENRES.get(self._genre, [])
            if sub_genres:
                self._sub_genre_index = (self._sub_genre_index - 1) % len(sub_genres)
            return True

        if self._sub_phase == RapGodPhase.MOOD_SELECT:
            self._mood_index = (self._mood_index - 1) % len(MOODS)
            return True

        if self._sub_phase == RapGodPhase.VIBE_SELECT:
            self._vibe_index = (self._vibe_index - 1) % len(VIBES)
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            if self._current_slot < 4:
                max_options = len(self._slot_options[self._current_slot])
            else:
                max_options = len(self._joker_options)
            self._option_index = (self._option_index - 1) % max_options
            return True
        return False

    def _handle_down(self) -> bool:
        """Handle down arrow - move selection down."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre_index = (self._genre_index + 1) % len(self._genres)
            return True

        if self._sub_phase == RapGodPhase.SUBGENRE_SELECT:
            sub_genres = SUB_GENRES.get(self._genre, [])
            if sub_genres:
                self._sub_genre_index = (self._sub_genre_index + 1) % len(sub_genres)
            return True

        if self._sub_phase == RapGodPhase.MOOD_SELECT:
            self._mood_index = (self._mood_index + 1) % len(MOODS)
            return True

        if self._sub_phase == RapGodPhase.VIBE_SELECT:
            self._vibe_index = (self._vibe_index + 1) % len(VIBES)
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            if self._current_slot < 4:
                max_options = len(self._slot_options[self._current_slot])
            else:
                max_options = len(self._joker_options)
            self._option_index = (self._option_index + 1) % max_options
            return True
        return False

    def _update_camera_preview(self) -> None:
        """Update camera preview from shared camera service."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None:
                dithered = floyd_steinberg_dither(frame, target_size=(128, 128))
                self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()
        except Exception:
            pass

    def _update_runner_camera(self) -> None:
        """Update runner game with camera frame for player sprite."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None:
                self._runner.update_camera(frame)
        except Exception:
            pass

    def _do_capture(self) -> None:
        """Capture photo for AI analysis."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            self._flash_alpha = 1.0
            logger.info(f"Photo captured: {len(self._photo_data)} bytes")

    def _start_generation(self) -> None:
        """Start the lyrics + music generation pipeline."""
        self._sub_phase = RapGodPhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)

        # Create word selection with all vibe settings
        selection = WordSelection(
            words=self._selected_words.copy(),
            joker=self._joker_text,
            genre=self._genre,
            sub_genre=self._sub_genre,
            mood=self._mood,
            vibe=self._vibe,
        )

        # Start async generation
        self._progress_tracker.start()

        # Reset runner game for mini-game during processing
        self._runner.reset()

        self._generation_task = asyncio.create_task(
            self._run_generation(selection)
        )

    async def _run_generation(self, selection: WordSelection) -> None:
        """Run the full generation pipeline."""
        try:
            # Phase 1: Generate lyrics with Gemini 3.0 Flash
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)

            logger.info(f"Generating lyrics for words: {selection.words}, has_photo: {self._photo_data is not None}")
            self._lyrics = await self._lyrics_gen.generate_lyrics(
                selection,
                photo_data=self._photo_data,
            )

            if not self._lyrics:
                logger.error("Lyrics generation failed")
                return

            logger.info(f"Lyrics generated: {self._lyrics.title}")

            # Phase 2: Generate music with Suno API
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            if self._suno.is_available:
                # Combine hook and verse for the track
                full_lyrics = f"{self._lyrics.hook}\n\n{self._lyrics.verse1}"
                if self._lyrics.verse2:
                    full_lyrics += f"\n\n{self._lyrics.verse2}"

                # Build style prompt using the full vibe selection
                style = selection.get_style_prompt()

                logger.info(f"Generating track with Suno: {self._lyrics.title}")
                self._task_id = await self._suno.generate_track(
                    lyrics=full_lyrics,
                    title=self._lyrics.title,
                    style=style,
                )

                if self._task_id:
                    # Wait for completion
                    def on_progress(pct: float):
                        self._progress_tracker.set_phase_progress(pct)

                    track = await self._suno.wait_for_completion(
                        self._task_id,
                        timeout=180.0,  # 3 minutes - Suno can be slow
                        on_progress=on_progress,
                    )

                    if track.status == TrackStatus.COMPLETED and track.audio_url:
                        self._audio_url = track.audio_url
                        logger.info(f"Track ready: {self._audio_url}")

                        # Download audio
                        self._audio_bytes = await self._suno.download_audio(
                            self._audio_url
                        )
                    elif track.status == TrackStatus.PROCESSING:
                        # Timed out but still generating
                        self._track_still_processing = True
                        logger.warning(f"Track still processing: {self._task_id}")
                    elif track.status == TrackStatus.FAILED:
                        self._generation_error = track.error or "Ошибка генерации"
                        logger.error(f"Track generation failed: {track.error}")
            else:
                logger.warning("Suno API not available, skipping music generation")
                self._generation_error = "Suno API недоступен"

            # Phase 3: Upload to Selectel S3 for QR sharing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

            if self._audio_bytes:
                self._download_url = await upload_to_selectel(self._audio_bytes)

                if self._download_url:
                    # Generate larger QR code for better scannability (70px)
                    self._qr_image = generate_qr_numpy(self._download_url, size=70)

            self._progress_tracker.complete()
            logger.info("Generation complete!")

        except Exception as e:
            logger.error(f"Generation error: {e}")
            self._progress_tracker.complete()

    def _on_generation_complete(self) -> None:
        """Handle generation completion."""
        self._sub_phase = RapGodPhase.PREVIEW

        # Burst particles for celebration
        sparkle_config = ParticlePresets.sparkle(64, 64)
        sparkle_config.color = GENRE_COLORS.get(self._genre, (255, 100, 200))
        sparkle_config.burst = 50
        emitter = self._particles.add_emitter("celebration", sparkle_config)
        emitter.burst(50)

        # Start audio preview
        if self._audio_bytes:
            asyncio.create_task(
                self._audio_player.play_preview(self._audio_bytes, duration_sec=15.0)
            )

    def _finish(self) -> None:
        """Complete the mode and prepare result."""
        # Build print data
        print_data: Dict[str, Any] = {
            "type": "rapgod",
            "timestamp": datetime.now().isoformat(),
            "words": self._selected_words,
            "genre": self._genre,
        }

        if self._lyrics:
            print_data["song_title"] = self._lyrics.title
            print_data["artist"] = self._lyrics.artist
            print_data["hook"] = self._lyrics.hook
            print_data["bpm"] = self._lyrics.bpm
            print_data["one_liner"] = self._lyrics.one_liner

        if self._download_url:
            print_data["download_url"] = self._download_url
        elif self._audio_url:
            print_data["download_url"] = self._audio_url

        # Add status info for receipt
        if self._track_still_processing:
            print_data["status"] = "processing"
            print_data["status_message"] = "Трек ещё готовится - попробуй ссылку позже!"
        elif self._generation_error:
            print_data["status"] = "failed"
            print_data["status_message"] = f"Ошибка: {self._generation_error}"
        else:
            print_data["status"] = "complete"

        # Create result
        display_text = self._lyrics.hook if self._lyrics else "Трек готовится..."
        ticker_text = f"RAP GOD: {self._lyrics.title}" if self._lyrics else "ARTIFACT BEATS"

        result = ModeResult(
            mode_name=self.name,
            success=bool(self._lyrics),  # Success if we at least have lyrics
            display_text=display_text,
            ticker_text=ticker_text,
            lcd_text=" RAP GOD ".center(16)[:16],
            should_print=True,
            print_data=print_data,
        )

        self.complete(result)

    # =========================================================================
    # RENDERING
    # =========================================================================

    def render_main(self, buffer: np.ndarray) -> None:
        """Render to 128x128 main display."""
        genre_color = GENRE_COLORS.get(self._genre, (255, 100, 200))

        # Dark background with genre tint
        bg = (20, 15, 30)
        fill(buffer, bg)

        if self._sub_phase == RapGodPhase.INTRO:
            self._render_intro(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._render_genre_select(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.SUBGENRE_SELECT:
            self._render_subgenre_select(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.MOOD_SELECT:
            self._render_mood_select(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.VIBE_SELECT:
            self._render_vibe_select(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.WORD_SELECT:
            self._render_word_select(buffer, genre_color)

        elif self._sub_phase in (RapGodPhase.CAMERA_PREP, RapGodPhase.CAMERA_CAPTURE):
            self._render_camera(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.PROCESSING:
            self._render_processing(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.PREVIEW:
            self._render_preview(buffer, genre_color)

        elif self._sub_phase == RapGodPhase.RESULT:
            self._render_result(buffer, genre_color)

        # Render particles on top
        self._particles.render(buffer)

    def _render_intro(self, buffer: np.ndarray, color: tuple) -> None:
        """Render intro screen."""
        # Pulsing title
        pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 300)
        title_color = tuple(int(c * pulse) for c in color)

        draw_animated_text(
            buffer, "RAP GOD",
            y=40,
            base_color=title_color,
            time_ms=self._time_in_phase,
            effect=TextEffect.GLOW,
            scale=2,
        )

        draw_centered_text(
            buffer, "Создай свой трек",
            y=70,
            color=(150, 150, 150),
            scale=1,
        )

        draw_centered_text(
            buffer, "из случайных слов!",
            y=82,
            color=(150, 150, 150),
            scale=1,
        )

        # Hint
        if self._time_in_phase > 1000:
            draw_centered_text(
                buffer, "НАЖМИ ENTER",
                y=105,
                color=(100, 100, 100),
                scale=1,
            )

    def _render_genre_select(self, buffer: np.ndarray, color: tuple) -> None:
        """Render genre selection."""
        draw_centered_text(
            buffer, "ВЫБЕРИ ЖАНР",
            y=15,
            color=(200, 200, 200),
            scale=1,
        )

        # Show all genres, highlight current
        y_start = 35
        for i, genre_key in enumerate(self._genres):
            genre_info = GENRES[genre_key]
            genre_color = GENRE_COLORS[genre_key]

            is_selected = (i == self._genre_index)

            if is_selected:
                # Highlight box
                draw_rect(buffer, 10, y_start + i * 18 - 2, 108, 16,
                         color=(40, 35, 50), filled=True)

                draw_animated_text(
                    buffer, genre_info["name_ru"],
                    y=y_start + i * 18,
                    base_color=genre_color,
                    time_ms=self._time_in_phase,
                    effect=TextEffect.GLOW,
                    scale=1,
                )
            else:
                draw_centered_text(
                    buffer, genre_info["name_ru"],
                    y=y_start + i * 18,
                    color=(80, 80, 80),
                    scale=1,
                )

        # Button hints
        draw_button_labels(
            buffer,
            left_text="",
            right_text="OK",
            time_ms=self._time_in_phase,
            y=115,
        )

    def _render_subgenre_select(self, buffer: np.ndarray, color: tuple) -> None:
        """Render sub-genre selection."""
        draw_centered_text(
            buffer, "ПОДЖАНР",
            y=8,
            color=(200, 200, 200),
            scale=1,
        )

        # Show current genre at top
        genre_info = GENRES.get(self._genre, GENRES["trap"])
        draw_centered_text(
            buffer, genre_info["name_ru"],
            y=22,
            color=color,
            scale=1,
        )

        # Get sub-genres for current genre
        sub_genres = SUB_GENRES.get(self._genre, [])
        if not sub_genres:
            draw_centered_text(buffer, "НЕТ ВАРИАНТОВ", y=60, color=(100, 100, 100), scale=1)
            return

        # Show sub-genres with scrolling window (show 3 at a time)
        visible_count = 3
        start_idx = max(0, self._sub_genre_index - 1)
        end_idx = min(len(sub_genres), start_idx + visible_count)

        y_start = 42
        for i, idx in enumerate(range(start_idx, end_idx)):
            sg = sub_genres[idx]
            is_selected = (idx == self._sub_genre_index)
            y_pos = y_start + i * 26

            if is_selected:
                draw_rect(buffer, 8, y_pos - 2, 112, 22, color=(60, 40, 80), filled=True)
                draw_rect(buffer, 8, y_pos - 2, 112, 22, color=color, filled=False)
                draw_animated_text(
                    buffer, f"> {sg['name_ru']}",
                    y=y_pos,
                    base_color=color,
                    time_ms=self._time_in_phase,
                    effect=TextEffect.GLOW,
                    scale=1,
                )
                # Description
                draw_centered_text(buffer, sg["desc"][:20], y=y_pos + 12, color=(120, 120, 140), scale=1)
            else:
                draw_centered_text(buffer, sg["name_ru"], y=y_pos, color=(100, 100, 120), scale=1)

        # Navigation hints
        draw_centered_text(buffer, "↑↓ ВЫБРАТЬ", y=108, color=(100, 100, 120), scale=1)
        draw_button_labels(buffer, left_text="НАЗАД", right_text="OK", time_ms=self._time_in_phase, y=120)

    def _render_mood_select(self, buffer: np.ndarray, color: tuple) -> None:
        """Render mood selection."""
        draw_centered_text(
            buffer, "НАСТРОЕНИЕ",
            y=8,
            color=(200, 200, 200),
            scale=1,
        )

        # Show moods with scrolling window (show 4 at a time)
        visible_count = 4
        start_idx = max(0, self._mood_index - 1)
        end_idx = min(len(MOODS), start_idx + visible_count)

        y_start = 28
        for i, idx in enumerate(range(start_idx, end_idx)):
            m = MOODS[idx]
            is_selected = (idx == self._mood_index)
            y_pos = y_start + i * 22

            if is_selected:
                draw_rect(buffer, 8, y_pos - 2, 112, 18, color=(60, 40, 80), filled=True)
                draw_rect(buffer, 8, y_pos - 2, 112, 18, color=color, filled=False)
                draw_animated_text(
                    buffer, f"> {m['name_ru']}",
                    y=y_pos,
                    base_color=color,
                    time_ms=self._time_in_phase,
                    effect=TextEffect.GLOW,
                    scale=1,
                )
            else:
                draw_centered_text(buffer, m["name_ru"], y=y_pos, color=(100, 100, 120), scale=1)

        # Navigation hints
        draw_centered_text(buffer, "↑↓ ВЫБРАТЬ", y=108, color=(100, 100, 120), scale=1)
        draw_button_labels(buffer, left_text="НАЗАД", right_text="OK", time_ms=self._time_in_phase, y=120)

    def _render_vibe_select(self, buffer: np.ndarray, color: tuple) -> None:
        """Render vibe (atmosphere) selection."""
        draw_centered_text(
            buffer, "ВАЙБ",
            y=8,
            color=(200, 200, 200),
            scale=1,
        )

        # Show vibes with scrolling window (show 4 at a time)
        visible_count = 4
        start_idx = max(0, self._vibe_index - 1)
        end_idx = min(len(VIBES), start_idx + visible_count)

        y_start = 28
        for i, idx in enumerate(range(start_idx, end_idx)):
            v = VIBES[idx]
            is_selected = (idx == self._vibe_index)
            y_pos = y_start + i * 22

            if is_selected:
                draw_rect(buffer, 8, y_pos - 2, 112, 18, color=(60, 40, 80), filled=True)
                draw_rect(buffer, 8, y_pos - 2, 112, 18, color=color, filled=False)
                draw_animated_text(
                    buffer, f"> {v['name_ru']}",
                    y=y_pos,
                    base_color=color,
                    time_ms=self._time_in_phase,
                    effect=TextEffect.GLOW,
                    scale=1,
                )
            else:
                draw_centered_text(buffer, v["name_ru"], y=y_pos, color=(100, 100, 120), scale=1)

        # Navigation hints
        draw_centered_text(buffer, "↑↓ ВЫБРАТЬ", y=108, color=(100, 100, 120), scale=1)
        draw_button_labels(buffer, left_text="НАЗАД", right_text="OK", time_ms=self._time_in_phase, y=120)

    def _render_word_select(self, buffer: np.ndarray, color: tuple) -> None:
        """Render 3-option word selection."""
        # Title based on current slot
        if self._current_slot < 4:
            title = f"СЛОВО {self._current_slot + 1}/4"
            options = self._slot_options[self._current_slot] if self._current_slot < len(self._slot_options) else []
        else:
            title = "ДЖОКЕР"
            options = self._joker_options

        draw_centered_text(
            buffer, title,
            y=8,
            color=(200, 200, 200),
            scale=1,
        )

        # Show already selected words at top
        if self._selected_words:
            words_display = " ".join(self._selected_words[:4])
            # Truncate if too long
            if len(words_display) > 22:
                words_display = words_display[:20] + ".."
            draw_centered_text(
                buffer, words_display,
                y=22,
                color=(100, 200, 100),
                scale=1,
            )

        # Draw 3 options
        start_y = 42
        option_height = 22

        for i, option in enumerate(options[:3]):
            y_pos = start_y + i * option_height
            is_selected = (i == self._option_index)

            # Truncate option text
            display_text = option[:16] if len(option) > 16 else option

            if is_selected:
                # Highlight box
                draw_rect(buffer, 8, y_pos - 2, 112, 18, color=(60, 40, 80), filled=True)
                draw_rect(buffer, 8, y_pos - 2, 112, 18, color=color, filled=False)

                # Animated selected text
                draw_animated_text(
                    buffer, f"> {display_text}",
                    y=y_pos,
                    base_color=color,
                    time_ms=self._time_in_phase,
                    effect=TextEffect.GLOW,
                    scale=1,
                )
            else:
                # Dim unselected option
                draw_centered_text(
                    buffer, display_text,
                    y=y_pos,
                    color=(100, 100, 120),
                    scale=1,
                )

        # Instructions
        draw_centered_text(
            buffer, "↑↓ ВЫБРАТЬ",
            y=110,
            color=(120, 120, 140),
            scale=1,
        )

        # Button hints
        draw_button_labels(
            buffer,
            left_text="ЕЩЁ",
            right_text="OK",
            time_ms=self._time_in_phase,
            y=122,
        )

    def _render_camera(self, buffer: np.ndarray, color: tuple) -> None:
        """Render camera preview and capture screen."""
        # Show camera preview
        if self._camera_frame is not None:
            buffer[:] = self._camera_frame
        else:
            # No camera - show placeholder
            fill(buffer, (20, 15, 30))
            draw_centered_text(
                buffer, "КАМЕРА...",
                y=60,
                color=(100, 100, 100),
                scale=1,
            )

        # Flash effect
        if self._flash_alpha > 0:
            flash_color = (
                int(255 * self._flash_alpha),
                int(255 * self._flash_alpha),
                int(255 * self._flash_alpha),
            )
            # Blend flash with buffer
            alpha = self._flash_alpha
            buffer[:] = (buffer * (1 - alpha) + np.array(flash_color) * alpha).astype(np.uint8)

        if self._sub_phase == RapGodPhase.CAMERA_PREP:
            # Show instruction overlay (semi-transparent black)
            draw_rect(buffer, 0, 0, 128, 25, color=(0, 0, 0), filled=True)
            draw_centered_text(
                buffer, "ВСТАНЬ В КАДР!",
                y=8,
                color=color,
                scale=1,
            )

        elif self._sub_phase == RapGodPhase.CAMERA_CAPTURE:
            # Show countdown
            if self._camera_countdown > 0:
                countdown_num = int(self._camera_countdown) + 1
                # Pulse effect for countdown (clamped to 255)
                pulse = 1.0 + 0.3 * math.sin(self._time_in_phase / 100)
                pulse_color = tuple(min(255, int(c * pulse)) for c in color)
                draw_centered_text(
                    buffer, str(countdown_num),
                    y=50,
                    color=pulse_color,
                    scale=3,
                )
            else:
                # Just took photo
                draw_centered_text(
                    buffer, "ГОТОВО!",
                    y=55,
                    color=(100, 255, 100),
                    scale=2,
                )

    def _render_processing(self, buffer: np.ndarray, color: tuple) -> None:
        """Render processing/generation screen with runner mini-game."""
        # Render the runner game
        self._runner.render(buffer, color)

        # Overlay progress info at top
        progress = self._progress_tracker.get_progress()
        message = self._progress_tracker.get_message()

        # Semi-transparent header bar
        buffer[:12, :] = (buffer[:12, :].astype(np.float32) * 0.3).astype(np.uint8)

        # Progress message
        draw_centered_text(
            buffer, message[:20],
            y=2,
            color=(150, 150, 200),
            scale=1,
        )

        # Small progress bar at very top
        bar_w = int(128 * progress)
        if bar_w > 0:
            buffer[0, :bar_w] = color

    def _render_preview(self, buffer: np.ndarray, color: tuple) -> None:
        """Render audio preview with QR code."""
        # Title depends on status
        if self._audio_bytes:
            title = "ГОТОВО!"
            title_effect = TextEffect.RAINBOW
        elif self._track_still_processing:
            title = "ТЕКСТ ГОТОВ"
            title_effect = TextEffect.GLOW
        elif self._generation_error:
            title = "ОШИБКА"
            title_effect = TextEffect.NONE
        else:
            title = "ПОЧТИ..."
            title_effect = TextEffect.WAVE

        draw_animated_text(
            buffer, title,
            y=10,
            base_color=color,
            time_ms=self._time_in_phase,
            effect=title_effect,
            scale=2,
        )

        if self._lyrics:
            draw_centered_text(
                buffer, self._lyrics.title[:16],
                y=35,
                color=(200, 200, 200),
                scale=1,
            )

        # Show status based on generation result
        if self._audio_bytes:
            draw_centered_text(
                buffer, "ИГРАЕТ...",
                y=55,
                color=(100, 200, 100),
                scale=1,
            )
        elif self._track_still_processing:
            draw_centered_text(
                buffer, "Трек ещё готовится",
                y=50,
                color=(255, 200, 100),
                scale=1,
            )
            draw_centered_text(
                buffer, "Скоро будет на чеке!",
                y=64,
                color=(200, 150, 80),
                scale=1,
            )
        elif self._generation_error:
            draw_centered_text(
                buffer, "Не удалось создать",
                y=50,
                color=(255, 100, 100),
                scale=1,
            )
            draw_centered_text(
                buffer, "Текст на чеке!",
                y=64,
                color=(200, 100, 100),
                scale=1,
            )

        # QR code prompt (only if we have audio)
        if self._download_url:
            draw_centered_text(
                buffer, "СКАНИРУЙ QR",
                y=80,
                color=(150, 150, 200),
                scale=1,
            )
            draw_centered_text(
                buffer, "ДЛЯ СКАЧИВАНИЯ",
                y=92,
                color=(100, 100, 150),
                scale=1,
            )
        elif self._lyrics:
            # No audio but have lyrics - mention receipt
            draw_centered_text(
                buffer, "ТЕКСТ НА ЧЕКЕ",
                y=85,
                color=(150, 150, 150),
                scale=1,
            )

        # Continue hint
        draw_centered_text(
            buffer, "ENTER = ДАЛЕЕ",
            y=115,
            color=(80, 80, 80),
            scale=1,
        )

    def _render_result(self, buffer: np.ndarray, color: tuple) -> None:
        """Render final result with full-screen QR or lyrics."""
        if self._result_view == "qr" and self._qr_image is not None:
            # Full-screen QR code on white background
            fill(buffer, (255, 255, 255))

            # Scale QR to fill screen (max 110x110 to leave small border)
            qr_h, qr_w = self._qr_image.shape[:2]
            target_size = 110

            # Simple nearest-neighbor scale up
            if qr_w < target_size:
                scale_factor = target_size // qr_w
                scaled_qr = np.repeat(np.repeat(self._qr_image, scale_factor, axis=0), scale_factor, axis=1)
                qr_h, qr_w = scaled_qr.shape[:2]
            else:
                scaled_qr = self._qr_image

            # Center on screen
            x_offset = (128 - qr_w) // 2
            y_offset = (128 - qr_h) // 2

            # Draw QR
            buffer[y_offset:y_offset+qr_h, x_offset:x_offset+qr_w] = scaled_qr

            # Small hint at bottom (dark text on white)
            draw_centered_text(
                buffer, "◄ ► ТЕКСТ",
                y=118,
                color=(100, 100, 100),
                scale=1,
            )

        elif self._result_view == "qr" and self._qr_image is None:
            # No QR available - show URL as text
            draw_centered_text(
                buffer, "ТРЕК ГОТОВ!",
                y=40,
                color=color,
                scale=2,
            )

            if self._download_url:
                draw_centered_text(
                    buffer, "СМОТРИ ЧЕК!",
                    y=70,
                    color=(150, 150, 200),
                    scale=1,
                )
            elif self._audio_url:
                draw_centered_text(
                    buffer, "ССЫЛКА НА ЧЕКЕ",
                    y=70,
                    color=(150, 150, 200),
                    scale=1,
                )

            # Navigation hint
            draw_centered_text(
                buffer, "◄ ► ТЕКСТ",
                y=115,
                color=(100, 100, 100),
                scale=1,
            )

        else:
            # Show lyrics full screen
            draw_centered_text(
                buffer, "ТЕКСТ",
                y=5,
                color=color,
                scale=1,
            )

            if self._lyrics and self._lyrics.hook:
                # Show first few lines of hook
                lines = self._lyrics.hook.split("\n")[:6]
                for i, line in enumerate(lines):
                    draw_centered_text(
                        buffer, line[:22],
                        y=20 + i * 14,
                        color=(180, 180, 200),
                        scale=1,
                    )

            # Navigation hint
            draw_centered_text(
                buffer, "◄ ► QR",
                y=115,
                color=(100, 100, 100),
                scale=1,
            )

    def render_ticker(self, buffer: np.ndarray) -> None:
        """Render to 48x8 ticker display."""
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)

        if self._sub_phase == RapGodPhase.PROCESSING:
            text = self._progress_tracker.get_message()
            effect = TickerEffect.PULSE_SCROLL
        elif self._lyrics:
            text = f"RAP GOD: {self._lyrics.title} - {self._lyrics.one_liner}"
            effect = TickerEffect.RAINBOW_SCROLL
        else:
            text = "СТАНЬ RAP GOD!"
            effect = TickerEffect.WAVE_SCROLL

        color = GENRE_COLORS.get(self._genre, (255, 100, 200))

        render_ticker_animated(
            buffer, text,
            self._time_in_phase,
            color,
            effect=effect,
            speed=0.025,
        )

    def get_lcd_text(self) -> str:
        """Return 16-char LCD text."""
        if self._sub_phase == RapGodPhase.WORD_SELECT:
            if self._current_slot < 4:
                return f"СЛОВО {self._current_slot + 1}/4".center(16)[:16]
            else:
                return "ДЖОКЕР".center(16)[:16]
        elif self._sub_phase == RapGodPhase.PROCESSING:
            dots = "....."
            n = int(self._time_in_phase / 300) % 4
            return f"СОЗДАЁМ{dots[:n+1]}".center(16)[:16]
        elif self._lyrics:
            return self._lyrics.title[:16].center(16)[:16]
        else:
            return " RAP GOD ".center(16)[:16]

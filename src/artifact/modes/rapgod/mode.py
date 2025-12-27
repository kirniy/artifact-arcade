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

from artifact.modes.rapgod.wordbank import WordBank, WordSelection, GENRES
from artifact.modes.rapgod.lyrics import LyricsGenerator, GeneratedLyrics
from artifact.modes.rapgod.suno import get_suno_client, SunoClient, TrackStatus
from artifact.modes.rapgod.audio import (
    AudioPlayer,
    upload_to_selectel,
    format_duration,
)
from artifact.utils.s3_upload import generate_qr_image as generate_qr_numpy
from artifact.utils.camera import floyd_steinberg_dither, create_viewfinder_overlay
from artifact.utils.camera_service import camera_service

logger = logging.getLogger(__name__)


class RapGodPhase:
    """Sub-phases within RapGod mode."""

    INTRO = "intro"              # Welcome animation
    GENRE_SELECT = "genre"       # Pick trap/drill/cloud/boombap/phonk
    WORD_SELECT = "words"        # Select 4 words + joker (slot-machine style)
    CAMERA_PREP = "camera_prep"  # Show camera preview
    CAMERA_CAPTURE = "capture"   # Countdown and capture
    PROCESSING = "processing"    # Generating lyrics + music
    PREVIEW = "preview"          # Playing audio, showing QR
    RESULT = "result"            # Final display


# Colors for different genres
GENRE_COLORS = {
    "trap": (255, 50, 100),     # Hot pink
    "drill": (100, 100, 255),   # Blue
    "cloud": (200, 150, 255),   # Lavender
    "boombap": (255, 180, 50),  # Gold
    "phonk": (150, 50, 200),    # Purple
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

        # Word selection state - slot machine style
        self._current_slot = 0  # 0-3 for 4 word slots, then 4 = joker slot
        self._slot_words: List[List[str]] = []  # ~20 words per slot for scrolling
        self._slot_offsets: List[float] = [0.0, 0.0, 0.0, 0.0, 0.0]  # Scroll offset (5 slots: 4 words + joker)
        self._slot_stopped: List[bool] = [False, False, False, False, False]  # Whether stopped
        self._slot_speed: float = 25.0  # Pixels per second for scrolling (slow and readable)
        self._selected_words: List[str] = []  # Final selected words (4)
        self._joker_words: List[str] = []  # Joker rules for slot 5
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

        # Progress tracking
        self._progress_tracker = SmartProgressTracker(mode_theme="rapgod")
        self._progress_tracker.set_custom_messages(RAPGOD_MESSAGES)

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
        """Reset word selection state for slot machine."""
        self._current_slot = 0
        self._slot_words = []
        self._slot_offsets = [0.0, 0.0, 0.0, 0.0, 0.0]
        self._slot_stopped = [False, False, False, False, False]
        self._selected_words = []
        self._joker_text = None

        # Pre-generate 20 words per slot for scrolling effect
        for i in range(4):
            words = self._wordbank.get_words_by_category_index(i, count=20)
            self._slot_words.append(words)

        # Add joker rules as the 5th slot
        self._joker_words = self._wordbank.get_all_jokers()
        random.shuffle(self._joker_words)
        # Add "БЕЗ ДЖОКЕРА" as first option
        self._joker_words.insert(0, "БЕЗ ДЖОКЕРА")

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

        # Update slot machine animation in word select phase
        if self._sub_phase == RapGodPhase.WORD_SELECT:
            self._update_slot_animation(delta_ms)

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

        # Update progress tracker during processing
        if self._sub_phase == RapGodPhase.PROCESSING:
            self._progress_tracker.update(delta_ms)

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

    def _update_slot_animation(self, delta_ms: int) -> None:
        """Update slot machine scrolling animation."""
        # Only animate the current slot (and any not yet stopped)
        for i in range(5):
            if not self._slot_stopped[i]:
                # Scroll the slot - slow speed for readability
                speed = self._slot_speed  # 25 px/s for words
                if i == 4:  # Joker slot scrolls even slower
                    speed = 15.0
                self._slot_offsets[i] += speed * delta_ms / 1000.0

                # Wrap around based on number of items
                if i < 4:
                    num_items = len(self._slot_words[i]) if i < len(self._slot_words) else 20
                else:
                    num_items = len(self._joker_words) if self._joker_words else 12

                item_height = 16  # Pixels per item
                max_offset = num_items * item_height
                if self._slot_offsets[i] >= max_offset:
                    self._slot_offsets[i] -= max_offset

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
        """Handle confirm/enter action - STOPS the current slot."""
        if self._sub_phase == RapGodPhase.INTRO:
            self._sub_phase = RapGodPhase.GENRE_SELECT
            return True

        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre = self._genres[self._genre_index]
            self._sub_phase = RapGodPhase.WORD_SELECT
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            # STOP the current slot and lock in the word
            if self._current_slot < 4:
                # Word slot (0-3)
                if not self._slot_stopped[self._current_slot]:
                    self._slot_stopped[self._current_slot] = True
                    # Get the word at current offset
                    word = self._get_current_slot_word(self._current_slot)
                    self._selected_words.append(word)
                    self._current_slot += 1
            else:
                # Joker slot (4)
                if not self._slot_stopped[4]:
                    self._slot_stopped[4] = True
                    joker = self._get_current_joker()
                    if joker != "БЕЗ ДЖОКЕРА":
                        self._joker_text = joker
                    # All slots done - move to camera
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

    def _get_current_slot_word(self, slot_idx: int) -> str:
        """Get the word at the current scroll position for a slot."""
        if slot_idx >= len(self._slot_words):
            return "слово"

        words = self._slot_words[slot_idx]
        offset = self._slot_offsets[slot_idx]
        item_height = 16
        # Get index of word at center of display
        center_idx = int((offset + 40) / item_height) % len(words)
        return words[center_idx]

    def _get_current_joker(self) -> str:
        """Get the joker rule at the current scroll position."""
        if not self._joker_words:
            return "БЕЗ ДЖОКЕРА"

        offset = self._slot_offsets[4]
        item_height = 16
        center_idx = int((offset + 40) / item_height) % len(self._joker_words)
        return self._joker_words[center_idx]

    def _handle_back(self) -> bool:
        """Handle back action - re-spin the previous slot."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._sub_phase = RapGodPhase.INTRO
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            if self._current_slot > 0:
                # Go back to previous slot and re-spin it
                self._current_slot -= 1
                self._slot_stopped[self._current_slot] = False
                if self._selected_words:
                    self._selected_words.pop()
            elif self._current_slot == 0 and not self._slot_stopped[0]:
                # At first slot, not stopped - go back to genre
                self._sub_phase = RapGodPhase.GENRE_SELECT
            return True

        if self._sub_phase == RapGodPhase.CAMERA_PREP:
            # Go back to joker slot
            self._sub_phase = RapGodPhase.WORD_SELECT
            self._current_slot = 4
            self._slot_stopped[4] = False
            self._joker_text = None
            return True

        return False

    def _handle_left(self) -> bool:
        """Handle left arrow - reshuffle current slot words."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre_index = (self._genre_index - 1) % len(self._genres)
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            # Reshuffle current slot with new words
            if self._current_slot < 4:
                self._slot_words[self._current_slot] = self._wordbank.get_words_by_category_index(
                    self._current_slot + random.randint(0, 100), count=20
                )
                self._slot_offsets[self._current_slot] = 0.0
            else:
                # Reshuffle joker rules
                random.shuffle(self._joker_words)
                self._slot_offsets[4] = 0.0
            return True

        if self._sub_phase == RapGodPhase.RESULT:
            # Toggle view
            self._result_view = "lyrics" if self._result_view == "qr" else "qr"
            return True

        return False

    def _handle_right(self) -> bool:
        """Handle right arrow - shuffle/new words in word select."""
        if self._sub_phase == RapGodPhase.GENRE_SELECT:
            self._genre_index = (self._genre_index + 1) % len(self._genres)
            return True

        if self._sub_phase == RapGodPhase.WORD_SELECT:
            # Shuffle current slot with new words (same as LEFT)
            if self._current_slot < 4:
                self._slot_words[self._current_slot] = self._wordbank.get_words_by_category_index(
                    self._current_slot + random.randint(0, 100), count=20
                )
                self._slot_offsets[self._current_slot] = 0.0
            else:
                # Reshuffle joker rules
                random.shuffle(self._joker_words)
                self._slot_offsets[4] = 0.0
            return True

        if self._sub_phase == RapGodPhase.RESULT:
            # Toggle view
            self._result_view = "lyrics" if self._result_view == "qr" else "qr"
            return True

        return False

    def _handle_up(self) -> bool:
        """Handle up arrow - speed up current slot temporarily."""
        if self._sub_phase == RapGodPhase.WORD_SELECT:
            # Nudge the slot offset backward (scroll up)
            if not self._slot_stopped[self._current_slot]:
                self._slot_offsets[self._current_slot] -= 8.0
                if self._slot_offsets[self._current_slot] < 0:
                    # Wrap around
                    if self._current_slot < 4:
                        num_items = len(self._slot_words[self._current_slot])
                    else:
                        num_items = len(self._joker_words)
                    self._slot_offsets[self._current_slot] += num_items * 16
            return True
        return False

    def _handle_down(self) -> bool:
        """Handle down arrow - nudge slot forward."""
        if self._sub_phase == RapGodPhase.WORD_SELECT:
            # Nudge the slot offset forward (scroll down)
            if not self._slot_stopped[self._current_slot]:
                self._slot_offsets[self._current_slot] += 8.0
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

        # Create word selection (joker already set or None)
        selection = WordSelection(
            words=self._selected_words.copy(),
            joker=self._joker_text,
            genre=self._genre,
        )

        # Start async generation
        self._progress_tracker.start()
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

                # Build style prompt
                genre_info = GENRES.get(selection.genre, GENRES["trap"])
                bpm = random.randint(*genre_info["bpm_range"])
                style = f"russian {selection.genre}, {genre_info['mood']}, {bpm} bpm, club banger"

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
                        timeout=90.0,
                        on_progress=on_progress,
                    )

                    if track.status == TrackStatus.COMPLETED and track.audio_url:
                        self._audio_url = track.audio_url
                        logger.info(f"Track ready: {self._audio_url}")

                        # Download audio
                        self._audio_bytes = await self._suno.download_audio(
                            self._audio_url
                        )
            else:
                logger.warning("Suno API not available, skipping music generation")

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

        # Create result
        display_text = self._lyrics.hook if self._lyrics else "Трек готовится..."
        ticker_text = f"RAP GOD: {self._lyrics.title}" if self._lyrics else "ARTIFACT BEATS"

        result = ModeResult(
            mode_name=self.name,
            success=True,
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

    def _render_word_select(self, buffer: np.ndarray, color: tuple) -> None:
        """Render slot machine style word selection."""
        # Title based on current slot
        if self._current_slot < 4:
            title = f"СЛОВО {self._current_slot + 1}/4"
            is_joker_slot = False
        else:
            title = "ДЖОКЕР"
            is_joker_slot = True

        draw_centered_text(
            buffer, title,
            y=8,
            color=(200, 200, 200),
            scale=1,
        )

        # Show already selected words at top
        if self._selected_words:
            words_display = " | ".join(self._selected_words[:4])
            draw_centered_text(
                buffer, words_display[:24],
                y=20,
                color=(100, 80, 120),
                scale=1,
            )

        # Draw slot machine window (centered area where words scroll)
        slot_y = 35
        slot_height = 70
        slot_width = 118

        # Background for slot window
        draw_rect(buffer, 5, slot_y, slot_width, slot_height, color=(25, 20, 35), filled=True)

        # Draw scrolling words/jokers
        if is_joker_slot:
            self._render_slot_items(buffer, self._joker_words, 4, slot_y, slot_height, color)
        else:
            if self._current_slot < len(self._slot_words):
                self._render_slot_items(
                    buffer, self._slot_words[self._current_slot],
                    self._current_slot, slot_y, slot_height, color
                )

        # Center highlight bar (the "selected" position)
        center_y = slot_y + slot_height // 2 - 8
        draw_rect(buffer, 5, center_y, slot_width, 16, color=(60, 40, 80), filled=True)

        # Re-render the center word on top of highlight
        if is_joker_slot:
            center_word = self._get_current_joker()
        else:
            center_word = self._get_current_slot_word(self._current_slot)

        # Truncate long joker rules
        display_word = center_word[:18] if len(center_word) > 18 else center_word

        draw_animated_text(
            buffer, display_word,
            y=center_y + 2,
            base_color=color,
            time_ms=self._time_in_phase,
            effect=TextEffect.GLOW if not self._slot_stopped[self._current_slot] else TextEffect.NONE,
            scale=1,
        )

        # Border around slot
        draw_rect(buffer, 5, slot_y, slot_width, slot_height, color=(80, 60, 100), filled=False)

        # Status indicator
        if self._slot_stopped[self._current_slot]:
            status = "ВЫБРАНО!"
            status_color = (100, 255, 100)
        else:
            status = "ЖМЕШЬ = СТОП"
            status_color = (150, 150, 150)

        draw_centered_text(buffer, status, y=108, color=status_color, scale=1)

        # Button hints
        draw_button_labels(
            buffer,
            left_text="НАЗАД",
            right_text="ЕЩЁ",
            time_ms=self._time_in_phase,
            y=120,
        )

    def _render_slot_items(
        self, buffer: np.ndarray, items: List[str],
        slot_idx: int, slot_y: int, slot_height: int, color: tuple
    ) -> None:
        """Render scrolling items in a slot machine window."""
        if not items:
            return

        offset = self._slot_offsets[slot_idx]
        item_height = 16
        num_items = len(items)

        # Calculate visible range
        center_y = slot_y + slot_height // 2

        for i in range(num_items):
            # Calculate y position for this item
            item_offset = (i * item_height - offset) % (num_items * item_height)
            if item_offset > num_items * item_height // 2:
                item_offset -= num_items * item_height

            y_pos = int(center_y + item_offset - 6)

            # Only render if visible in window
            if slot_y < y_pos < slot_y + slot_height - 8:
                # Fade based on distance from center
                dist = abs(y_pos - center_y)
                alpha = max(0.4, 1.0 - dist / 50)

                # Skip center item (we render it separately with glow)
                if dist > 8:
                    # Brighter base color for readability (0.7 instead of 0.5)
                    item_color = tuple(min(255, int(c * alpha * 0.8)) for c in color)
                    item_text = items[i][:16]  # Truncate
                    draw_centered_text(buffer, item_text, y=y_pos, color=item_color, scale=1)

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
        """Render processing/generation screen."""
        # Get current progress
        progress = self._progress_tracker.get_progress()
        message = self._progress_tracker.get_message()

        # Animated title
        draw_animated_text(
            buffer, "СОЗДАЁМ ТРЕК",
            y=20,
            base_color=color,
            time_ms=self._time_in_phase,
            effect=TextEffect.WAVE,
            scale=1,
        )

        # Progress message
        draw_centered_text(
            buffer, message,
            y=50,
            color=(150, 150, 200),
            scale=1,
        )

        # Progress bar
        bar_x, bar_y = 20, 75
        bar_w, bar_h = 88, 8

        # Background
        draw_rect(buffer, bar_x, bar_y, bar_w, bar_h, color=(40, 40, 50), filled=True)

        # Fill
        fill_w = int(bar_w * progress)
        if fill_w > 0:
            # Pulsing fill color
            pulse = 0.8 + 0.2 * math.sin(self._time_in_phase / 150)
            fill_color = tuple(int(c * pulse) for c in color)
            draw_rect(buffer, bar_x, bar_y, fill_w, bar_h, color=fill_color, filled=True)

        # Percentage
        pct_text = f"{int(progress * 100)}%"
        draw_centered_text(
            buffer, pct_text,
            y=95,
            color=(100, 100, 100),
            scale=1,
        )

    def _render_preview(self, buffer: np.ndarray, color: tuple) -> None:
        """Render audio preview with QR code."""
        draw_animated_text(
            buffer, "ГОТОВО!",
            y=10,
            base_color=color,
            time_ms=self._time_in_phase,
            effect=TextEffect.RAINBOW,
            scale=2,
        )

        if self._lyrics:
            draw_centered_text(
                buffer, self._lyrics.title[:16],
                y=35,
                color=(200, 200, 200),
                scale=1,
            )

        # Show "playing" indicator
        if self._audio_bytes:
            bars = "▶ ▮▮▮▮"  # Playing indicator
            draw_centered_text(
                buffer, "ИГРАЕТ...",
                y=55,
                color=(100, 200, 100),
                scale=1,
            )

        # QR code prompt
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

        # Continue hint
        draw_centered_text(
            buffer, "ENTER = ДАЛЕЕ",
            y=115,
            color=(80, 80, 80),
            scale=1,
        )

    def _render_result(self, buffer: np.ndarray, color: tuple) -> None:
        """Render final result."""
        if self._result_view == "qr" and self._qr_image is not None:
            # Show QR code (already numpy array from generate_qr_numpy)
            qr_h, qr_w = self._qr_image.shape[:2]
            x_offset = (128 - qr_w) // 2
            y_offset = 20

            # Draw black background behind QR for contrast
            draw_rect(buffer, x_offset - 2, y_offset - 2, qr_w + 4, qr_h + 4, (0, 0, 0), filled=True)
            buffer[y_offset:y_offset+qr_h, x_offset:x_offset+qr_w] = self._qr_image

            draw_centered_text(
                buffer, "СКАЧАЙ ТРЕК",
                y=5,
                color=color,
                scale=1,
            )

            if self._lyrics:
                # Show title below QR
                title_y = y_offset + qr_h + 5
                draw_centered_text(
                    buffer, self._lyrics.title[:18],
                    y=title_y,
                    color=(150, 150, 150),
                    scale=1,
                )

            # Navigation hint - show option to view lyrics
            draw_button_labels(
                buffer,
                left_text="ТЕКСТ",
                right_text="ТЕКСТ",
                time_ms=self._time_in_phase,
                y=115,
            )

        elif self._result_view == "qr" and self._qr_image is None:
            # No QR available - show URL as text
            draw_centered_text(
                buffer, "ТРЕК ГОТОВ!",
                y=30,
                color=color,
                scale=1,
            )

            if self._download_url:
                # Truncate URL for display
                url_short = self._download_url.split("/")[-1][:16]
                draw_centered_text(
                    buffer, url_short,
                    y=55,
                    color=(150, 150, 200),
                    scale=1,
                )
            elif self._audio_url:
                draw_centered_text(
                    buffer, "СМОТРИ ЧЕК!",
                    y=55,
                    color=(150, 150, 200),
                    scale=1,
                )

            # Navigation hint
            draw_button_labels(
                buffer,
                left_text="ТЕКСТ",
                right_text="ТЕКСТ",
                time_ms=self._time_in_phase,
                y=115,
            )

        else:
            # Show lyrics
            draw_centered_text(
                buffer, "ТЕКСТ ТРЕКА",
                y=5,
                color=color,
                scale=1,
            )

            if self._lyrics and self._lyrics.hook:
                # Show first few lines of hook
                lines = self._lyrics.hook.split("\n")[:5]
                for i, line in enumerate(lines):
                    draw_centered_text(
                        buffer, line[:22],
                        y=20 + i * 14,
                        color=(180, 180, 200),
                        scale=1,
                    )

            # Navigation hint - show option to view QR
            draw_button_labels(
                buffer,
                left_text="QR",
                right_text="QR",
                time_ms=self._time_in_phase,
                y=115,
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

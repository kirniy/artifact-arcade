"""Photobooth Mode - AI Photo Booth with QR sharing.

Photo booth flow:
1. Button press → Countdown (3-2-1)
2. Camera flash → Take photo
3. AI generates themed 2x2 photo booth grid
4. Show preview → Upload to S3 gallery → QR code to gallery page

Supports multiple themes (set PHOTOBOOTH_THEME env var):
- boilingroom: Raw analog concert photography, red & black palette
- tripvenice: 3D Sims-style Venetian carnival, gold & burgundy palette
- malchishnik: High-noise analogue party realism, warm film palette
- loveintheair: Romantic warm-toned illustrated card style
- feyphoria: Art toy + fantasy doodle theme
- fiesta: Realistic Spanish-style party realism with doodle overlays
- vnvnc-bday: 9-year birthday editorial poster theme with premium emblem refs
"""

import logging
import io
import os
import asyncio
import hashlib
from collections import OrderedDict
from typing import Optional, Type
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
from PIL import Image as PILImage
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.text_utils import (
    draw_centered_text,
    draw_text,
    render_idle_style_ticker_text,
)
from artifact.utils.camera_service import camera_service
from artifact.telegram.events import append_bot_event

# When enabled, the completed photobooth image is sent to the print manager.
# Keep this environment-controlled so local/dev runs can stay digital-only.
PRINTING_ENABLED = os.getenv("PHOTOBOOTH_PRINTING_ENABLED", "true").lower() not in {
    "0",
    "false",
    "no",
    "off",
}
USE_AI_GENERATION = True  # Toggle AI generation vs local Polaroid fallback
from artifact.utils.s3_upload import (
    AsyncUploader,
    UploadResult,
    generate_qr_image,
    pre_generate_upload_info,
)
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.animation.santa_runner import SantaRunner
from artifact.audio.engine import get_audio_engine
from artifact.utils.hdmi_capture import hdmi_capture_service
from artifact.modes.photobooth_themes import (
    PhotoboothMenuVariant,
    PhotoboothTheme,
    get_current_theme,
    get_theme_by_id,
)

logger = logging.getLogger(__name__)
MOSCOW_TZ = timezone(timedelta(hours=3))
RUSSIAN_WEEKDAYS = (
    "ПОНЕДЕЛЬНИК",
    "ВТОРНИК",
    "СРЕДА",
    "ЧЕТВЕРГ",
    "ПЯТНИЦА",
    "СУББОТА",
    "ВОСКРЕСЕНЬЕ",
)


def photobooth_ai_enabled() -> bool:
    """Return whether photobooth sessions may call an AI image provider."""
    return os.getenv("PHOTOBOOTH_AI_ENABLED", "true").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def get_moscow_party_stamp(
    theme: PhotoboothTheme, now: Optional[datetime] = None
) -> tuple[str, str]:
    """Return the footer date/time strings for a theme in Moscow time."""
    if now is None:
        now = datetime.now(MOSCOW_TZ)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=MOSCOW_TZ)
    else:
        now = now.astimezone(MOSCOW_TZ)

    footer_date = now
    rollover_hour = theme.party_date_rollover_hour
    if rollover_hour is not None and now.hour < rollover_hour:
        footer_date = now - timedelta(days=1)

    if theme.ai_style_key == "2k17":
        footer_label = footer_date.strftime("%d.%m.2017")
    elif theme.footer_date_mode == "weekday_ru":
        footer_label = RUSSIAN_WEEKDAYS[footer_date.weekday()]
    else:
        footer_label = footer_date.strftime("%d.%m")

    return footer_label, now.strftime("%H:%M")


@dataclass
class PhotoboothState:
    """State for photobooth session."""

    countdown: int = 3
    countdown_timer: float = 0.0
    photo_bytes: Optional[bytes] = None  # Original captured photo
    photo_frame: Optional[NDArray[np.uint8]] = None  # Original photo for preview
    # AI generates TWO images:
    # - Square (1:1) for LED display
    # - Vertical (9:16) for label printing
    ai_display_bytes: Optional[bytes] = None  # 1:1 square for LED display
    ai_display_frame: Optional[NDArray[np.uint8]] = None  # Decoded frame for display
    ai_label_bytes: Optional[bytes] = None  # 9:16 vertical for label printing
    photo_path: Optional[str] = None
    qr_url: Optional[str] = None
    qr_image: Optional[NDArray[np.uint8]] = None
    is_printing: bool = False
    is_uploading: bool = False
    is_generating: bool = False  # AI generation in progress
    flash_timer: float = 0.0
    pre_flash_timer: float = 0.0  # Flash BEFORE capture to light up subjects
    show_result: bool = False
    result_view: str = "photo"  # "photo" or "qr"
    generation_progress: float = 0.0  # 0.0 to 1.0
    bot_source_photo_path: Optional[str] = None
    waiting_finish_timer: float = 0.0
    waiting_finish_from_seconds: int = 0
    awaiting_camera_selection: bool = False
    selected_camera_id: str = "primary"
    source_has_visible_face: Optional[bool] = None
    source_identity_face_count: Optional[int] = None


class PhotoboothMode(BaseMode):
    """AI Photo Booth - generates themed photo booth grids.

    Supports multiple themes via PHOTOBOOTH_THEME environment variable:
    - boilingroom: BOILING ROOM underground party (red & black)
    - tripvenice: TRIP:VENICE carnival masquerade (gold & burgundy, 3D style)

    Flow:
    1. Countdown timer with visual + audio feedback
    2. Photo capture
    3. AI generates themed 2x2 photo booth grid
    4. Upload to S3 gallery for sharing
    5. Show unified gallery QR code
    """

    name = "photobooth"
    display_name = "ФОТО\nБУДКА"
    icon = "camera"
    style = "arcade"
    requires_camera = True
    requires_ai = True
    estimated_duration = 30
    theme_id_override: Optional[str] = None
    ai_style_key_override: Optional[str] = None
    prompt_variation_index: Optional[int] = None
    menu_display_name_override: Optional[str] = None
    menu_description_override: Optional[str] = None
    menu_color_override: Optional[tuple[int, int, int]] = None
    description = "Фоткайся на память!"

    BEEP_TIME = 0.2
    COUNTDOWN_SECONDS = 3
    FLASH_DURATION = 0.5
    RESULT_DURATION = 120.0  # 2 minutes to scan QR before auto-return to idle
    WAITING_COPY = (
        ("НЕ УХОДИ", "ФОТО ПЕЧАТАЕТСЯ"),
        ("СТОЙ ТУТ", "ОСТАЛОСЬ НЕДОЛГО"),
        ("Я НЕ ЗАВИС", "ФОТО УЖЕ В ПУТИ"),
        ("ЖДИ ТУТ", "ФОТО БУДЕТ ГОТОВО"),
    )
    WAITING_COUNTDOWN_SECONDS = 120
    WAITING_BG = (0, 0, 0)
    WAITING_TEXT = (255, 255, 255)
    WAITING_ACCENT = (255, 40, 40)
    WAITING_DIM = (70, 70, 70)
    WAITING_FINISH_SPIN_SECONDS = 0.85
    CAMERA_1_LABEL = "CAM1: СПЕРЕДИ"
    CAMERA_2_LABEL = "CAM2: СЗАДИ"

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._state = PhotoboothState()
        self._working = False
        self._uploader = AsyncUploader()
        self._caricature_service = CaricatureService()
        self._ai_task: Optional[asyncio.Task] = None
        self._progress_tracker = SmartProgressTracker(mode_theme="photobooth")
        self._santa_runner: Optional[SantaRunner] = None
        self._audio = get_audio_engine()
        self._logo_frame: Optional[NDArray[np.uint8]] = None
        self._theme_reference_images: list[tuple[bytes, str]] = []

        # Load theme configuration.
        if self.theme_id_override:
            self._theme = get_theme_by_id(self.theme_id_override)
        else:
            self._theme = get_current_theme()
        logger.info(f"Photobooth using theme: {self._theme.id} ({self._theme.event_name})")

        selector_flag = os.getenv("PHOTOBOOTH_CAMERA_SELECTOR_ENABLED", "auto").lower()
        if selector_flag == "auto":
            self._camera_selector_enabled = self._theme.ai_style_key == "2k17"
        else:
            self._camera_selector_enabled = selector_flag in {"1", "true", "yes", "on"}
        self._camera2_ai_enabled = os.getenv(
            "PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED", "false"
        ).lower() in {"1", "true", "yes", "on"}
        self._ai_enabled = photobooth_ai_enabled()
        if not self._ai_enabled:
            logger.warning(
                "Photobooth AI is disabled; all cameras will capture, upload, and print raw photos"
            )

        # Theme-derived properties
        self.description = self._theme.description
        self.THEME_CHROME = self._theme.theme_chrome
        self.TICKER_COLOR = self._theme.ticker_color or self._theme.theme_chrome
        self.THEME_RED = self._theme.theme_red
        self.THEME_BLACK = self._theme.theme_black

        self._load_logo()

    def _load_logo(self) -> None:
        """Load theme logo for display overlay."""
        self._theme_reference_images = []
        try:
            logo_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "..",
                "assets",
                "images",
                self._theme.logo_filename,
            )
            logo_path = os.path.normpath(logo_path)
            if os.path.exists(logo_path):
                img = PILImage.open(logo_path).convert("RGBA")
                # Resize to 80x80 for 128x128 display
                img = img.resize((80, 80), PILImage.Resampling.LANCZOS)
                self._logo_rgba = np.array(img, dtype=np.uint8)
                logger.info(f"Loaded {self._theme.id} logo: {self._theme.logo_filename}")

                reference_filenames: list[str] = list(self._theme.reference_image_filenames)
                if self._theme.ai_style_key in {
                    "brainrot",
                    "wedding",
                    "whatsapp",
                    "slavic_soul",
                    "slavic_tales",
                    "banya_chic",
                    "vnvnc_bday",
                    "mtv_night",
                    "shadow_kingdom",
                    "circus_maximus",
                    "candy_shop",
                    "street_heat",
                }:
                    reference_filenames.insert(0, self._theme.logo_filename)

                seen_filenames: set[str] = set()
                for reference_filename in reference_filenames:
                    if reference_filename in seen_filenames:
                        continue
                    seen_filenames.add(reference_filename)
                    reference_path = os.path.join(
                        os.path.dirname(__file__),
                        "..",
                        "..",
                        "..",
                        "assets",
                        "images",
                        reference_filename,
                    )
                    reference_path = os.path.normpath(reference_path)
                    if not os.path.exists(reference_path):
                        logger.warning(
                            "Reference asset not found for %s: %s",
                            self._theme.id,
                            reference_filename,
                        )
                        continue
                    with open(reference_path, "rb") as reference_file:
                        reference_bytes = reference_file.read()
                        expected_sha256 = self._theme.required_reference_sha256
                        if expected_sha256:
                            actual_sha256 = hashlib.sha256(reference_bytes).hexdigest()
                            if actual_sha256 != expected_sha256:
                                logger.error(
                                    "Rejected non-canonical reference for %s: %s (sha256=%s)",
                                    self._theme.id,
                                    reference_filename,
                                    actual_sha256,
                                )
                                continue
                        mime_type = (
                            "image/png" if reference_path.lower().endswith(".png") else "image/jpeg"
                        )
                        if self._theme.id == "spiderverse":
                            original_size = len(reference_bytes)
                            with PILImage.open(io.BytesIO(reference_bytes)) as source:
                                emblem = source.convert("RGBA")
                            emblem.thumbnail((1024, 1024), PILImage.Resampling.LANCZOS)
                            background = PILImage.new("RGBA", emblem.size, "white")
                            background.alpha_composite(emblem)
                            compressed = io.BytesIO()
                            background.convert("RGB").save(compressed, "JPEG", quality=88, optimize=True)
                            reference_bytes = compressed.getvalue()
                            mime_type = "image/jpeg"
                            logger.info("SPIDERVERSE reference compressed: %d -> %d bytes", original_size, len(reference_bytes))
                        self._theme_reference_images.append((reference_bytes, mime_type))
                logger.info(
                    "Loaded %d theme reference asset(s) for %s: %s",
                    len(self._theme_reference_images),
                    self._theme.id,
                    ", ".join(seen_filenames) if seen_filenames else "none",
                )
            else:
                logger.warning(f"Logo not found: {logo_path}")
                self._logo_rgba = None
        except Exception as e:
            logger.warning(f"Failed to load logo: {e}")
            self._logo_rgba = None
            self._theme_reference_images = []

    def _blit_logo(self, buffer: NDArray[np.uint8], x: int, y: int) -> None:
        """Blit RGBA logo onto buffer with alpha compositing."""
        if self._logo_rgba is None:
            return
        h, w = self._logo_rgba.shape[:2]
        # Clip to buffer bounds
        y1, y2 = max(0, y), min(128, y + h)
        x1, x2 = max(0, x), min(128, x + w)
        sy, sx = y1 - y, x1 - x
        alpha = (
            self._logo_rgba[sy : sy + (y2 - y1), sx : sx + (x2 - x1), 3:4].astype(np.float32)
            / 255.0
        )
        rgb = self._logo_rgba[sy : sy + (y2 - y1), sx : sx + (x2 - x1), :3].astype(np.float32)
        bg = buffer[y1:y2, x1:x2].astype(np.float32)
        buffer[y1:y2, x1:x2] = (rgb * alpha + bg * (1.0 - alpha)).astype(np.uint8)

    def on_enter(self) -> None:
        """Initialize mode."""
        self._state = PhotoboothState()
        self._working = False
        self._ai_task = None
        self._progress_tracker.reset()
        self._state.awaiting_camera_selection = self._camera_selector_enabled
        self._state.selected_camera_id = "primary"
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        """Cleanup."""
        self._working = False
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

    def on_input(self, event: Event) -> bool:
        """Handle button press - adapted from buttonPress()."""
        # Handle LEFT/RIGHT for photo/QR toggle during result
        if self._state.show_result:
            if event.type == EventType.ARCADE_LEFT or event.type == EventType.ARCADE_RIGHT:
                # Toggle between photo and qr view
                if self._state.result_view == "photo":
                    self._state.result_view = "qr"
                else:
                    self._state.result_view = "photo"
                return True

        # Handle input for Santa runner during AI generation
        if self._state.is_generating:
            if event.type == EventType.BUTTON_PRESS:
                # Jump on button press
                if self._santa_runner:
                    self._santa_runner.handle_jump()
                    self._audio.play_ui_click()
                return True
            elif event.type in (EventType.ARCADE_LEFT, EventType.ARCADE_RIGHT):
                # Shoot on left/right arrows
                if self._santa_runner:
                    if self._santa_runner.handle_shoot():
                        self._audio.play_ui_click()
                return True

        if self.phase == ModePhase.ACTIVE and self._state.awaiting_camera_selection:
            if event.type in (
                EventType.BUTTON_PRESS,
                EventType.ARCADE_LEFT,
                EventType.ARCADE_RIGHT,
                EventType.KEYPAD_INPUT,
            ):
                return self._handle_camera_selection_input(event)
            return False

        if event.type not in (EventType.BUTTON_PRESS, EventType.KEYPAD_INPUT):
            return False

        # Allow exit during result phase (must check BEFORE _working flag)
        if self._state.show_result:
            # Button press during result = complete session (print and exit)
            self._complete_session()
            return True

        # Prevent re-entry while working (from raspi-photo-booth Working flag)
        if self._working:
            return True

        if self.phase == ModePhase.ACTIVE:
            # Start countdown
            self._working = True
            self._start_countdown()
            return True

        return False

    def _handle_camera_selection_input(self, event: Event) -> bool:
        """Switch/confirm the live camera preview before countdown."""
        if event.type == EventType.ARCADE_LEFT:
            self._state.selected_camera_id = "primary"
            self._audio.play_ui_click()
            return True
        if event.type == EventType.ARCADE_RIGHT:
            self._state.selected_camera_id = "hdmi"
            self._audio.play_ui_click()
            return True
        if event.type == EventType.KEYPAD_INPUT:
            key = str(event.data.get("key", ""))
            if key == "1":
                self._state.selected_camera_id = "primary"
                return True
            if key == "2":
                self._state.selected_camera_id = "hdmi"
                return True
            return True

        if event.type == EventType.BUTTON_PRESS:
            if self._state.selected_camera_id == "hdmi" and not hdmi_capture_service.has_signal():
                logger.warning("Ignoring CAM2 selection: HDMI capture has no usable signal")
                self._audio.play_error()
                return True
            self._state.awaiting_camera_selection = False
            self._working = True
            self._start_countdown()
            return True

        return False

    def _start_countdown(self) -> None:
        """Start countdown sequence - adapted from countdown()."""
        self._state.countdown = self.COUNTDOWN_SECONDS
        self._state.countdown_timer = 1.0
        self.change_phase(ModePhase.PROCESSING)

    def on_update(self, delta_ms: float) -> None:
        """Per-frame update - handles countdown and flash."""
        if self.phase == ModePhase.PROCESSING:
            self._update_countdown(delta_ms)
        elif self.phase == ModePhase.RESULT:
            self._update_result(delta_ms)

    def _update_countdown(self, delta_ms: float) -> None:
        """Update countdown timer and AI generation progress."""
        # Handle flash timer
        if self._state.flash_timer > 0:
            self._state.flash_timer -= delta_ms / 1000.0

        # Handle countdown
        if self._state.countdown > 0:
            self._state.countdown_timer -= delta_ms / 1000.0

            if self._state.countdown_timer <= 0:
                if self._state.countdown > 1:
                    # Next countdown number
                    self._state.countdown -= 1
                    self._state.countdown_timer = 1.0
                else:
                    # Countdown finished - start pre-flash to light up subjects!
                    self._state.countdown = 0
                    self._state.pre_flash_timer = 0.15  # Flash screen for 150ms before capture
            return

        # Handle pre-flash (flash to light up subjects before capture)
        if self._state.pre_flash_timer > 0:
            self._state.pre_flash_timer -= delta_ms / 1000.0
            if self._state.pre_flash_timer <= 0:
                # Now capture with lit-up subjects!
                self._do_flash_and_capture()

        # Handle AI generation progress
        if self._state.is_generating:
            # Update progress tracker
            self._progress_tracker.update(delta_ms)
            self._state.generation_progress = self._progress_tracker.get_progress()

            # Update Santa runner minigame
            if self._santa_runner:
                self._santa_runner.update(delta_ms)

            # Check if AI task completed
            if self._ai_task and self._ai_task.done():
                try:
                    result = self._ai_task.result()
                    if result:
                        display_bytes, label_bytes = result
                        # Store display image (1:1 square for LED)
                        if display_bytes:
                            self._state.ai_display_bytes = display_bytes
                            self._state.ai_display_frame = self._decode_photo_frame(display_bytes)
                        # Store label image (9:16 vertical for printing)
                        if label_bytes:
                            self._state.ai_label_bytes = label_bytes
                        logger.info("AI photo booth generation completed (display + label)")
                        # Upload the LABEL image for QR (vertical format looks better when downloaded)
                        self._upload_ai_result_async()
                    else:
                        logger.error("AI generation returned no result")
                except Exception as e:
                    logger.error(f"AI generation failed: {e}")

                self._state.is_generating = False
                self._ai_task = None
                self._progress_tracker.complete()

                # Show result
                self._state.show_result = True
                self._state.countdown_timer = self.RESULT_DURATION
                elapsed_waiting_seconds = max(0, int(self._time_in_phase // 1000))
                self._state.waiting_finish_from_seconds = max(
                    0,
                    self.WAITING_COUNTDOWN_SECONDS - elapsed_waiting_seconds,
                )
                self._state.waiting_finish_timer = self.WAITING_FINISH_SPIN_SECONDS
                self.change_phase(ModePhase.RESULT)

                # Start printing IMMEDIATELY when result appears (if enabled)
                if PRINTING_ENABLED:
                    self._start_printing_now()

    def _do_flash_and_capture(self) -> None:
        """Flash, capture, and start AI generation."""
        self._state.flash_timer = self.FLASH_DURATION
        self._state.countdown = 0

        jpeg_bytes = self._capture_selected_camera_jpeg(quality=90)
        if jpeg_bytes:
            self._state.photo_bytes = jpeg_bytes
            self._state.photo_frame = self._decode_photo_frame(jpeg_bytes)

            if not self._ai_enabled:
                logger.info(
                    "Photobooth raw mode active; skipping AI and using captured photo directly"
                )
                self._finish_raw_capture_result()
                return

            if self._state.selected_camera_id == "hdmi" and not self._camera2_ai_enabled:
                logger.info("HDMI capture selected; skipping AI generation and using raw frame")
                self._finish_raw_capture_result()
                return

            # Start AI generation
            self._state.is_generating = True
            self._progress_tracker.start()
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            # Initialize loading animation for the waiting screen
            try:
                self._santa_runner = SantaRunner(theme=self._theme)
                self._santa_runner.reset()
            except Exception as e:
                logger.warning(f"Failed to create loading animation: {e}")
                self._santa_runner = None

            if USE_AI_GENERATION:
                self._ai_task = asyncio.create_task(self._generate_photobooth_grid())
                logger.info(f"Starting AI photo booth generation ({self._theme.event_name})")
            else:
                self._ai_task = asyncio.create_task(self._generate_local_polaroid())
                logger.info("Starting local Polaroid generation fallback")

            self.change_phase(ModePhase.PROCESSING)
        else:
            # No photo captured, go to error state
            logger.error("Photo capture failed")
            self._working = False
            self._state.awaiting_camera_selection = self._camera_selector_enabled
            self.change_phase(ModePhase.ACTIVE)

    def _capture_selected_camera_jpeg(self, quality: int = 90) -> Optional[bytes]:
        if self._state.selected_camera_id == "hdmi":
            return hdmi_capture_service.capture_jpeg(quality=quality)
        return camera_service.capture_jpeg(quality=quality)

    def _finish_raw_capture_result(self) -> None:
        """Finish a no-AI photobooth session for any selected camera."""
        self._state.ai_display_bytes = self._state.photo_bytes
        self._state.ai_display_frame = self._state.photo_frame
        self._state.ai_label_bytes = None
        self._state.is_generating = False
        self._state.show_result = True
        self._state.countdown_timer = self.RESULT_DURATION
        self._state.waiting_finish_timer = 0.0
        self._upload_raw_capture_async()
        self.change_phase(ModePhase.RESULT)
        if PRINTING_ENABLED:
            self._start_printing_now()

    def _decode_photo_frame(self, jpeg_bytes: bytes) -> Optional[NDArray[np.uint8]]:
        """Decode captured JPEG into a 128x128 RGB frame for preview."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(jpeg_bytes))
            img = img.convert("RGB")
            if img.size != (128, 128):
                resample = getattr(Image, "Resampling", Image).BILINEAR
                img = img.resize((128, 128), resample=resample)
            return np.array(img, dtype=np.uint8)
        except Exception:
            return None

    def _build_identity_face_references(self) -> list[tuple[bytes, str]]:
        """Create ordered face crops to reinforce likeness without changing group layout."""
        if not self._state.photo_bytes:
            self._state.source_identity_face_count = None
            return []
        try:
            import cv2

            image = PILImage.open(io.BytesIO(self._state.photo_bytes)).convert("RGB")
            frame = np.array(image)
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            equalized = cv2.equalizeHist(gray)
            min_side = max(28, min(gray.shape[:2]) // 18)
            cascade_dir = Path(cv2.data.haarcascades)
            candidates: list[tuple[int, int, int, int]] = []
            for cascade_name, detection_image in (
                ("haarcascade_frontalface_default.xml", equalized),
                ("haarcascade_frontalface_alt2.xml", gray),
            ):
                detector = cv2.CascadeClassifier(str(cascade_dir / cascade_name))
                if detector.empty():
                    continue
                detections = detector.detectMultiScale(
                    detection_image,
                    scaleFactor=1.07,
                    minNeighbors=3,
                    minSize=(min_side, min_side),
                    flags=cv2.CASCADE_SCALE_IMAGE,
                )
                candidates.extend(tuple(int(value) for value in face) for face in detections)

            def overlap_ratio(
                a: tuple[int, int, int, int], b: tuple[int, int, int, int]
            ) -> float:
                ax, ay, aw, ah = a
                bx, by, bw, bh = b
                ix0, iy0 = max(ax, bx), max(ay, by)
                ix1, iy1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
                intersection = max(0, ix1 - ix0) * max(0, iy1 - iy0)
                if not intersection:
                    return 0.0
                return intersection / float(min(aw * ah, bw * bh))

            unique_faces: list[tuple[int, int, int, int]] = []
            for face in sorted(candidates, key=lambda item: item[2] * item[3], reverse=True):
                if any(overlap_ratio(face, existing) > 0.45 for existing in unique_faces):
                    continue
                unique_faces.append(face)
            unique_faces.sort(key=lambda item: item[0] + item[2] / 2)

            references: list[tuple[bytes, str]] = []
            for x, y, width, height in unique_faces[:5]:
                center_x = x + width / 2
                center_y = y + height / 2
                crop_side = max(width, height) * 2.0
                x0 = max(0, int(center_x - crop_side / 2))
                y0 = max(0, int(center_y - crop_side * 0.46))
                x1 = min(image.width, int(center_x + crop_side / 2))
                y1 = min(image.height, int(center_y + crop_side * 0.54))
                crop = image.crop((x0, y0, x1, y1))
                crop.thumbnail((640, 640), PILImage.Resampling.LANCZOS)
                encoded = io.BytesIO()
                crop.save(encoded, format="JPEG", quality=96, subsampling=0)
                references.append((encoded.getvalue(), "image/jpeg"))

            self._state.source_identity_face_count = len(references)
            logger.info("Built %d ordered identity face reference crop(s)", len(references))
            return references
        except Exception as e:
            self._state.source_identity_face_count = None
            logger.warning("Could not build identity face reference crops: %s", e)
            return []

    def _get_selected_preview_frame(self) -> Optional[NDArray[np.uint8]]:
        if self._state.selected_camera_id == "hdmi":
            # HDMICaptureService crop-fills 16:9 capture-card video into the 128x128 LED preview.
            return hdmi_capture_service.get_frame(timeout=0)
        return camera_service.get_frame(timeout=0)

    def _get_caricature_styles(self) -> tuple:
        """Get the CaricatureStyle enums for current theme.

        Returns:
            Tuple of (display_style, label_style) for 1:1 and 9:16 formats
        """
        ai_style_key = self.ai_style_key_override or self._theme.ai_style_key
        if ai_style_key == "bigcitylife":
            return (
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_BIGCITYLIFE,  # 9:16 vertical for label
            )
        elif ai_style_key == "fiesta":
            return (
                CaricatureStyle.PHOTOBOOTH_FIESTA_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_FIESTA,  # 9:16 vertical for label
            )
        elif ai_style_key == "feyphoria":
            return (
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_FEYPHORIA,  # 9:16 vertical for label
            )
        elif ai_style_key == "malchishnik":
            return (
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK,  # 9:16 vertical for label
            )
        elif ai_style_key == "loveintheair":
            return (
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR,  # 9:16 vertical for label
            )
        elif ai_style_key == "tripvenice":
            return (
                CaricatureStyle.PHOTOBOOTH_VENICE_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_VENICE,  # 9:16 vertical for label
            )
        elif ai_style_key == "slavic_soul":
            return (
                CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_SOUL,
            )
        elif ai_style_key == "slavic_tales":
            return (
                CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SLAVIC_TALES,
            )
        elif ai_style_key == "banya_chic":
            return (
                CaricatureStyle.PHOTOBOOTH_BANYA_CHIC_SQUARE,
                CaricatureStyle.PHOTOBOOTH_BANYA_CHIC,
            )
        elif ai_style_key == "vnvnc_bday":
            return (
                CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY_SQUARE,
                CaricatureStyle.PHOTOBOOTH_VNVNC_BDAY,
            )
        elif ai_style_key == "circus_maximus":
            return (
                CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS_SQUARE,
                CaricatureStyle.PHOTOBOOTH_CIRCUS_MAXIMUS,
            )
        elif ai_style_key == "mtv_night":
            return (
                CaricatureStyle.PHOTOBOOTH_MTV_NIGHT_SQUARE,
                CaricatureStyle.PHOTOBOOTH_MTV_NIGHT,
            )
        elif ai_style_key == "shadow_kingdom":
            return (
                CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SHADOW_KINGDOM,
            )
        elif ai_style_key == "candy_shop":
            return (
                CaricatureStyle.PHOTOBOOTH_CANDY_SHOP_SQUARE,
                CaricatureStyle.PHOTOBOOTH_CANDY_SHOP,
            )
        elif ai_style_key == "street_heat":
            return (
                CaricatureStyle.PHOTOBOOTH_STREET_HEAT_SQUARE,
                CaricatureStyle.PHOTOBOOTH_STREET_HEAT,
            )
        elif ai_style_key == "office_core":
            return (
                CaricatureStyle.PHOTOBOOTH_OFFICE_CORE_SQUARE,
                CaricatureStyle.PHOTOBOOTH_OFFICE_CORE,
            )
        elif ai_style_key == "2k17":
            return (
                CaricatureStyle.PHOTOBOOTH_2K17_SQUARE,
                CaricatureStyle.PHOTOBOOTH_2K17,
            )
        elif ai_style_key == "summer_camp":
            return (
                CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SUMMER_CAMP,
            )
        elif ai_style_key == "alye_parusa":
            return (
                CaricatureStyle.PHOTOBOOTH_ALYE_PARUSA_SQUARE,
                CaricatureStyle.PHOTOBOOTH_ALYE_PARUSA,
            )
        elif ai_style_key == "jara":
            return (
                CaricatureStyle.PHOTOBOOTH_JARA_SQUARE,
                CaricatureStyle.PHOTOBOOTH_JARA,
            )
        elif ai_style_key == "sunset_palms":
            return (
                CaricatureStyle.PHOTOBOOTH_SUNSET_PALMS_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SUNSET_PALMS,
            )
        elif ai_style_key == "spiderverse":
            return (
                CaricatureStyle.PHOTOBOOTH_SPIDERVERSE_SQUARE,
                CaricatureStyle.PHOTOBOOTH_SPIDERVERSE,
            )
        elif ai_style_key == "world_cup_final":
            return (
                CaricatureStyle.PHOTOBOOTH_WORLD_CUP_FINAL_SQUARE,
                CaricatureStyle.PHOTOBOOTH_WORLD_CUP_FINAL,
            )
        elif ai_style_key == "vse_svoi":
            return (
                CaricatureStyle.PHOTOBOOTH_VSE_SVOI_SQUARE,
                CaricatureStyle.PHOTOBOOTH_VSE_SVOI,
            )
        elif ai_style_key == "brainrot":
            return (
                CaricatureStyle.PHOTOBOOTH_BRAINROT_SQUARE,
                CaricatureStyle.PHOTOBOOTH_BRAINROT,
            )
        elif ai_style_key == "wedding":
            return (
                CaricatureStyle.PHOTOBOOTH_WEDDING_SQUARE,
                CaricatureStyle.PHOTOBOOTH_WEDDING,
            )
        elif ai_style_key == "whatsapp":
            return (
                CaricatureStyle.PHOTOBOOTH_WHATSAPP_SQUARE,
                CaricatureStyle.PHOTOBOOTH_WHATSAPP,
            )
        else:
            # Default to boilingroom styles
            return (
                CaricatureStyle.PHOTOBOOTH_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH,  # 9:16 vertical for label
            )

    async def _generate_local_polaroid(self) -> Optional[tuple]:
        """Generate a local Polaroid-style image from the captured photo."""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io
            from datetime import datetime, timezone, timedelta
            import urllib.request

            if not self._state.photo_bytes:
                return None

            photo = Image.open(io.BytesIO(self._state.photo_bytes))

            # Target dimensions (9:16 aspect ratio)
            canvas_w, canvas_h = 900, 1600
            canvas = Image.new("RGB", (canvas_w, canvas_h), "#FDFDFB")  # Off-white Polaroid paper

            # Target photo size (maintain aspect ratio 3:4)
            margin = 55
            target_photo_w = canvas_w - (2 * margin)
            target_photo_h = int(target_photo_w * (4 / 3))

            photo_aspect = photo.width / photo.height
            if photo_aspect > (3 / 4):
                new_w = int(photo.height * (3 / 4))
                offset = (photo.width - new_w) // 2
                photo = photo.crop((offset, 0, offset + new_w, photo.height))
            elif photo_aspect < (3 / 4):
                new_h = int(photo.width * (4 / 3))
                offset = (photo.height - new_h) // 2
                photo = photo.crop((0, offset, photo.width, offset + new_h))

            photo = photo.resize((target_photo_w, target_photo_h), Image.Resampling.LANCZOS)
            canvas.paste(photo, (margin, margin))

            draw = ImageDraw.Draw(canvas)

            try:
                font_path = os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "..",
                    "..",
                    "assets",
                    "fonts",
                    "Caveat-Bold.ttf",
                )
                font_path = os.path.normpath(font_path)
                font_size = 110

                # Fetch font if it doesn't exist
                if not os.path.exists(font_path):
                    os.makedirs(os.path.dirname(font_path), exist_ok=True)
                    urllib.request.urlretrieve(
                        "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat-Bold.ttf",
                        font_path,
                    )

                font = ImageFont.truetype(font_path, font_size)
            except Exception as e:
                logger.warning(f"Could not load custom font, using default: {e}")
                font = ImageFont.load_default()

            def get_text_width(f, t):
                if hasattr(f, "getbbox"):
                    return f.getbbox(t)[2] - f.getbbox(t)[0]
                elif hasattr(f, "getlength"):
                    return int(f.getlength(t))
                return f.getsize(t)[0]

            footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)

            text_y_row1 = margin + target_photo_h + 100
            text_y_row2 = text_y_row1 + 130
            text_color = "#202022"  # Marker ink

            # Left text: VNVNC.RU
            draw.text((margin + 20, text_y_row1), "VNVNC.RU", font=font, fill=text_color)

            # Right text: Time
            time_w = get_text_width(font, moscow_time)
            draw.text(
                (canvas_w - margin - 20 - time_w, text_y_row1),
                moscow_time,
                font=font,
                fill=text_color,
            )

            # Bottom row left: footer date (may roll back after midnight for overnight parties)
            draw.text((margin + 20, text_y_row2), footer_date_str, font=font, fill=text_color)

            # Bottom row right: Конюшенная 2В
            venue_str = "КОНЮШЕННАЯ 2В"
            venue_w = get_text_width(font, venue_str)
            draw.text(
                (canvas_w - margin - 20 - venue_w, text_y_row2),
                venue_str,
                font=font,
                fill=text_color,
            )

            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            label_bytes = buf.getvalue()

            # Instead of cropping, pad the 9:16 image to 1:1 for the display
            display_canvas = Image.new(
                "RGB", (canvas_h, canvas_h), "#000000"
            )  # 1600x1600 black background
            offset_x = (canvas_h - canvas_w) // 2
            display_canvas.paste(canvas, (offset_x, 0))

            display_buf = io.BytesIO()
            display_canvas.save(display_buf, format="PNG")
            display_bytes = display_buf.getvalue()

            # Artificial delay for user experience
            await asyncio.sleep(2.0)

            return (display_bytes, label_bytes)

        except Exception as e:
            logger.error(f"Local Polaroid generation failed: {e}")
            return None

    async def _generate_photobooth_grid(self) -> Optional[tuple]:
        """Generate AI photo booth image from captured photo.

        Generates ONE image in 9:16 vertical (label) format.
        A center-cropped 1:1 version is created for the LED display.

        Returns:
            Tuple of (display_bytes, label_bytes) or None on error
        """
        if not self._state.photo_bytes:
            logger.error("No photo bytes for AI generation")
            return None

        try:
            display_style, label_style = self._get_caricature_styles()
            logger.info(f"Generating photo booth with theme {self._theme.id}: {label_style.value}")

            # Themes with footer timestamps need the live Moscow time injected.
            personality_context = None
            ai_style_key = self.ai_style_key_override or self._theme.ai_style_key
            timestamp_theme_keys = {
                "boilingroom",
                "malchishnik",
                "feyphoria",
                "bigcitylife",
                "brainrot",
                "wedding",
                "whatsapp",
                "slavic_soul",
                "slavic_tales",
                "banya_chic",
                "vnvnc_bday",
                "mtv_night",
                "shadow_kingdom",
                "circus_maximus",
                "candy_shop",
                "street_heat",
                "office_core",
                "2k17",
                "summer_camp",
                "alye_parusa",
                "jara",
                "sunset_palms",
                "spiderverse",
                "world_cup_final",
                "vse_svoi",
            }
            if ai_style_key in timestamp_theme_keys:
                footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                if ai_style_key in {
                    "slavic_soul",
                    "slavic_tales",
                    "banya_chic",
                    "vnvnc_bday",
                    "mtv_night",
                    "shadow_kingdom",
                    "circus_maximus",
                    "candy_shop",
                    "street_heat",
                }:
                    personality_context = (
                        f"REAL MOSCOW RUSSIAN WEEKDAY LABEL FOR THIS PHOTO: {footer_date_str}. "
                        f"REAL MOSCOW TIME FOR THIS PHOTO: {moscow_time}. "
                        f"Use exactly '{footer_date_str}' as the footer day-of-week in Russian, "
                        f"use exactly '{moscow_time}' as the footer time, and do not show any numeric date."
                    )
                elif ai_style_key in {
                    "boilingroom",
                    "office_core",
                    "summer_camp",
                    "2k17",
                    "alye_parusa",
                    "jara",
                    "sunset_palms",
                    "world_cup_final",
                    "vse_svoi",
                }:
                    if ai_style_key == "boilingroom":
                        personality_context = (
                            "Image 2 is the canonical exact BOILING ROOM emblem. Faithfully model-render its "
                            "chrome circular ring and condensed two-line BOILING / ROOM geometry as part of the "
                            "illustrated poster; never paste or replace it. Rotoscope every face from the source "
                            "as a fixed underdrawing with exact individual geometry, hairline, expression and "
                            "natural asymmetry; never average or beautify faces. Do not render date, time, venue, "
                            "VNVNC.RU, pseudo-text, or any readable words beyond the emblem itself. Continue the "
                            "actual source-photo venue as a second fixed underdrawing: preserve its recognizable "
                            "walls, ceiling, practical lights, furniture, plants, decor, objects and background "
                            "people instead of inventing a generic club. Render that real environment with lifted "
                            "exposure, bright cream/coral/scarlet/chrome tones, readable shadow detail and at least "
                            "65% light or mid-tone area; avoid crushed blacks, muddy maroon fog, dark empty walls "
                            "and replacement scenery. Continue the source-faithful illustrated venue and light paper "
                            "texture full bleed to the bottom with no empty bar or placeholder. Keep faces out of "
                            "the lowest 13%; the app overlays one "
                            "compact verified information card there."
                        )
                    elif ai_style_key == "jara":
                        personality_context = (
                            "Do not render footer text inside the AI artwork. Continue the illustrated pool, "
                            "foam, water, and props full bleed to the bottom edge with no empty cyan band or "
                            "blank footer rectangle. Keep faces out of the lowest 13%; the app overlays one "
                            "compact floating information card there."
                        )
                    elif ai_style_key == "vnvnc_bday":
                        personality_context = (
                            "Preserve the source photograph as two fixed underdrawings: first, rotoscope every "
                            "face with exact individual geometry, hairline, expression, age cues and natural "
                            "asymmetry; second, preserve the recognizable real venue behind the people, including "
                            "its walls, ceiling, practical lights, furniture, plants, decor, objects and background "
                            "people. Re-render that actual scene as a bright high-key luxury birthday illustration "
                            "with lifted cream, pearl, chrome, papaya, coral and lacquer-red tones. At least 70% of "
                            "the background must be light or mid-tone with readable shadow detail. Never use a black "
                            "void, dark empty wall, crushed blacks, muddy burgundy fog or replacement scenery. Keep "
                            "all people equally recognizable and do not average, beautify or invent faces. Use "
                            "exactly the supplied Russian weekday and time in the elegant footer, with no numeric date."
                        )
                    elif ai_style_key == "sunset_palms":
                        personality_context = (
                            "Image 2 is the canonical exact SUNSET PALMS emblem. Faithfully reproduce its "
                            "orange-coral oval sunset, horizon bars, two black palms, exact SUNSΞT geometry "
                            "including the stylized E, and PALMS tracking as one model-native flat 2D "
                            "illustrated lockup in the top 18-21%. Never paste or simplify it. Its own SUNSET "
                            "PALMS wording is the only readable text allowed. Rotoscope every face from the "
                            "source underdrawing with exact individual geometry, hairline, expression and "
                            "asymmetry; never average or beautify faces. Use a bright high-key hand-inked "
                            "papaya/apricot/coral screenprint sunset with restrained cel shading, halftone texture, "
                            "spacious edge palms, sparse accents, handpan and at most two percussion props. "
                            "No dark canopy, storm sky, brown cast, object pile or empty bar. Keep faces out of the lowest "
                            "13%, where the app adds one compact information card."
                        )
                    elif ai_style_key == "spiderverse":
                        personality_context = (
                            "Image 2 is the canonical exact SPIDERVERSE event emblem. Integrate its complete "
                            "curved badge, web texture, dimensional letters and exact word once near the top. "
                            "Treat every face and the visible real venue as fixed underdrawings. Preserve exact "
                            "identity, group layout and recognizable background while translating the "
                            "whole source into bright dimensional graphic-novel animation with scarlet, cobalt, "
                            "warm ivory, ink contours, halftone texture, print separation and layered parallax. "
                            "THERMAL PRINT PRIORITY: relight the recognizable real room as a high-key pale "
                            "cream/light-blue daylight interior; preserve objects but not dark source exposure. "
                            "Keep at least 75% of the background near-white or pale color, with bright faces "
                            "and luminous red/blue suit panels. No large dark fills, dark navy masses, vignette "
                            "or all-over grain; only sparse halftone shadows and crisp fine outlines. "
                            "Keep the digital artwork FULL COLOR, never grayscale or monochrome. "
                            "Replace clothing from the neck down with fitted red-and-deep-blue technical-fabric "
                            "athletic suits with raised black web lattice, blue side panels and integrated gloves. "
                            "Keep every exact face and hairstyle fully uncovered: no masks, hoods, helmets, face "
                            "paint, copied chest emblems, franchise references or extra text. "
                            "Keep faces out of the lowest 13%, where the app adds a verified footer."
                        )
                    elif ai_style_key == "world_cup_final":
                        personality_context = (
                            "Image 2 is the official original event emblem. Integrate that emblem into the "
                            "illustrated top broadcast lockup yourself; do not leave a blank placeholder. Render "
                            "the exact Russian title 'ЧЕМПИОНАТ МИРА 2026' and the exact match line "
                            "'ИСПАНИЯ × АРГЕНТИНА'. Do not add any other title, score, date, time, address, "
                            "sponsor, badge, or fake logo. Continue the illustrated stadium, crowd, pitch, "
                            "confetti, and ribbons full bleed with no empty band or blank rectangle. Keep faces "
                            "out of the lowest 13%; the app overlays only one compact information card there."
                        )
                    elif ai_style_key == "vse_svoi":
                        personality_context = (
                            "Image 2 is the canonical exact silver VNVNC chain pendant used only by the app for "
                            "one deterministic hero pendant. Do not put pendants, necklaces, chains, medallions, "
                            "badges, VNVNC jewelry, or VNVNC lettering on any person. Leave the central top 38% "
                            "as clean venue background with no model-rendered "
                            "logo or pendant because the app composites the huge exact master there. Reframe the intact group "
                            "lower as one unit while preserving every relative position and overlap. Rotoscope every face from "
                            "the source as a fixed underdrawing with exact individual geometry, hairline, expression "
                            "and natural asymmetry; never average or beautify faces. Preserve the actual source-photo "
                            "venue as a second fixed underdrawing: its walls, ceiling, practical lights, furniture, "
                            "plants, decor, objects and background people. Use the current bright BOILING ROOM 2D "
                            "visual language with lifted cream/coral/scarlet/chrome exposure and at least 65% light "
                            "or mid-tone area. Pendant VNVNC geometry is the only readable AI lettering. Do not "
                            "render ВСЕ СВОИ, captions, paragraphs, prompt text, instructions, white text panels, "
                            "date, time, venue, garment lettering, pseudo-text or any extra words. Continue the real "
                            "illustrated venue full bleed and keep faces out of the lowest 13%, where the app adds "
                            "one compact verified information card."
                        )
                    else:
                        personality_context = (
                            "Do not render footer text inside the AI artwork. "
                            "Leave the bottom 12-15% as clean empty space matching the theme background; "
                            "the app will stamp VNVNC.RU, the Russian weekday, Moscow time, and venue after generation."
                        )
                else:
                    personality_context = (
                        f"Photo taken on {footer_date_str} at {moscow_time} Moscow time. "
                        f"Use the club-night date exactly as '{footer_date_str}' and the time exactly as '{moscow_time}' "
                        f"in the handwritten caption or footer area at the bottom of the image."
                    )

            # Generate only the label (9:16) image
            if self._theme.required_reference_sha256 and not self._theme_reference_images:
                raise RuntimeError(
                    f"{self._theme.event_name} generation refused: canonical emblem reference is missing or invalid"
                )
            generation_reference_images = list(self._theme_reference_images)
            if ai_style_key in {"boilingroom", "sunset_palms", "spiderverse", "vse_svoi"}:
                generation_reference_images.extend(self._build_identity_face_references())
            label_result = await self._caricature_service.generate_caricature(
                reference_photo=self._state.photo_bytes,
                style=label_style,  # 9:16 vertical
                personality_context=personality_context,
                # ЖАРА remains deterministic; emblem-native themes deliberately
                # give the canonical original asset to the model for integration.
                extra_reference_images=(
                    None if ai_style_key == "jara" else generation_reference_images or None
                ),
                prompt_variation_index=self.prompt_variation_index,
            )

            if label_result and label_result.image_data:
                label_bytes = label_result.image_data
                if ai_style_key == "2k17":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_2k17_footer(label_bytes, footer_date_str, moscow_time)
                elif ai_style_key == "boilingroom":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_boilingroom_footer(
                        label_bytes, footer_date_str, moscow_time
                    )
                elif ai_style_key == "vse_svoi":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_vse_svoi_pendants(label_bytes)
                    label_bytes = self._stamp_boilingroom_footer(
                        label_bytes, footer_date_str, moscow_time
                    )
                elif ai_style_key in {"office_core", "summer_camp"}:
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_white_theme_footer(
                        label_bytes, footer_date_str, moscow_time
                    )
                elif ai_style_key == "alye_parusa":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_alye_parusa_footer(
                        label_bytes, footer_date_str, moscow_time
                    )
                elif ai_style_key == "jara":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_jara_logo(label_bytes)
                    label_bytes = self._stamp_jara_footer(label_bytes, footer_date_str, moscow_time)
                elif ai_style_key == "world_cup_final":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_world_cup_final_footer(
                        label_bytes, footer_date_str, moscow_time
                    )
                elif ai_style_key == "sunset_palms":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_sunset_palms_footer(
                        label_bytes, footer_date_str, moscow_time
                    )
                elif ai_style_key == "spiderverse":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_spiderverse_footer(
                        label_bytes, footer_date_str, moscow_time
                    )
                logger.info(f"Label image generated: {len(label_bytes)} bytes")

                # Create center-cropped 1:1 version for LED display
                display_bytes = self._crop_to_square(label_bytes)

                return (display_bytes, label_bytes)
            else:
                logger.error("AI image generation failed")
                return None

        except Exception as e:
            logger.error(f"AI photo booth generation failed: {e}")
            return None

    def _crop_to_square(self, image_bytes: bytes) -> bytes:
        """Crop a 9:16 image to 1:1 square for the LED display."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes))
            w, h = img.size

            # Most themes read best as a center crop. The football poster has
            # a model-rendered emblem/title above the faces, so bias its crop
            # upward enough to keep both branding and guests on the main screen.
            if w < h:
                if getattr(self._theme, "ai_style_key", None) in {
                    "world_cup_final",
                    "sunset_palms",
                    "spiderverse",
                    "vse_svoi",
                }:
                    offset = int((h - w) * 0.06)
                else:
                    offset = (h - w) // 2
                img = img.crop((0, offset, w, offset + w))
            elif h < w:
                offset = (w - h) // 2
                img = img.crop((offset, 0, offset + h, h))

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to crop to square: {e}")
            return image_bytes

    def _stamp_vse_svoi_pendants(self, image_bytes: bytes) -> bytes:
        """Composite the exact pendant without altering generated artwork."""
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            w, h = img.size

            pendant_path = Path(__file__).resolve().parents[3] / "assets" / "images" / "vnvnc-pendant.png"
            pendant = Image.open(pendant_path).convert("RGBA")
            pendant_rgb = np.asarray(pendant.convert("RGB"), dtype=np.uint8)
            alpha = pendant_rgb.max(axis=2)
            alpha = np.clip((alpha.astype(np.int16) - 4) * 3, 0, 255).astype(np.uint8)
            pendant.putalpha(Image.fromarray(alpha, mode="L"))
            bbox = pendant.getbbox()
            if bbox:
                pendant = pendant.crop(bbox)

            def resized_pendant(target_w: int) -> Image.Image:
                target_w = max(24, target_w)
                target_h = max(24, round(pendant.height * target_w / pendant.width))
                return pendant.resize((target_w, target_h), Image.Resampling.LANCZOS)

            # The hero pendant is always deterministic: exact source pixels,
            # centered, with its chain entering from beyond the top edge.
            hero = resized_pendant(int(w * 0.43))
            hero_x = (w - hero.width) // 2
            hero_y = -max(2, int(hero.height * 0.025))
            shadow_alpha = hero.getchannel("A")
            shadow = Image.new("RGBA", hero.size, (0, 0, 0, 0))
            shadow.putalpha(shadow_alpha.point(lambda value: int(value * 0.55)))
            img.alpha_composite(shadow, (hero_x + max(3, w // 180), hero_y + max(5, h // 220)))
            img.alpha_composite(hero, (hero_x, hero_y))

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning("Failed to stamp ВСЕ СВОИ pendants: %s", e)
            return image_bytes

    def _stamp_boilingroom_footer(
        self, image_bytes: bytes, footer_date: str, moscow_time: str
    ) -> bytes:
        """Overlay one compact chrome/red club-pass card on full-bleed artwork."""
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            w, h = img.size
            margin_x = max(22, int(w * 0.035))
            margin_bottom = max(22, int(h * 0.022))
            card_h = max(132, int(h * 0.108))
            x0, x1 = margin_x, w - margin_x
            y0, y1 = h - margin_bottom - card_h, h - margin_bottom
            radius = max(14, int(card_h * 0.14))

            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                (x0, y0 + 9, x1, y1 + 9), radius=radius, fill=(0, 0, 0, 175)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(max(7, int(w * 0.012))))
            img = Image.alpha_composite(img, shadow)

            panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=radius,
                fill=(8, 8, 10, 234),
                outline=(205, 205, 210, 220),
                width=max(2, w // 300),
            )
            rail_y = y0 + max(6, int(card_h * 0.05))
            panel_draw.line(
                (x0 + radius, rail_y, x1 - radius, rail_y),
                fill=(139, 0, 0, 255),
                width=max(4, int(card_h * 0.035)),
            )
            img = Image.alpha_composite(img, panel)
            draw = ImageDraw.Draw(img)

            def load_font(size: int):
                for font_path in (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                ):
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.044)))
            time_font = load_font(max(27, int(w * 0.041)))
            sub_font = load_font(max(19, int(w * 0.028)))

            def text_width(font, text: str) -> int:
                box = draw.textbbox((0, 0), text, font=font)
                return box[2] - box[0]

            pad_x = max(22, int(w * 0.038))
            row1_y = y0 + max(23, int(card_h * 0.19))
            row2_y = y0 + max(82, int(card_h * 0.64))
            chrome = (224, 224, 228, 255)
            white = (255, 255, 255, 255)
            muted = (184, 184, 190, 255)
            red = (139, 0, 0, 255)
            venue = "КОНЮШЕННАЯ 2В"

            draw.text((x0 + pad_x, row1_y), "VNVNC.RU", font=main_font, fill=chrome)
            time_box = draw.textbbox((0, 0), moscow_time, font=time_font)
            time_w = time_box[2] - time_box[0]
            time_h = time_box[3] - time_box[1]
            pill_pad_x = max(17, int(w * 0.023))
            pill_pad_y = max(8, int(card_h * 0.075))
            pill_w = time_w + pill_pad_x * 2
            pill_h = time_h + pill_pad_y * 2
            pill_x = x1 - pad_x - pill_w
            pill_y = row1_y - max(4, int(card_h * 0.025))
            draw.rounded_rectangle(
                (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                radius=pill_h // 2,
                fill=red,
            )
            draw.text(
                (pill_x + pill_pad_x - time_box[0], pill_y + pill_pad_y - time_box[1]),
                moscow_time,
                font=time_font,
                fill=white,
            )
            draw.text((x0 + pad_x, row2_y), footer_date.upper(), font=sub_font, fill=muted)
            draw.text(
                (x1 - pad_x - text_width(sub_font, venue), row2_y),
                venue,
                font=sub_font,
                fill=muted,
            )

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp Boiling Room footer: {e}")
            return image_bytes

    def _stamp_white_theme_footer(
        self, image_bytes: bytes, footer_date: str, moscow_time: str
    ) -> bytes:
        """Paint deterministic white-theme footer text over the AI image."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = img.size
            footer_h = max(int(h * 0.13), 150)
            y0 = h - footer_h
            draw = ImageDraw.Draw(img)

            draw.rectangle((0, y0, w, h), fill=(255, 255, 255))
            draw.line((0, y0, w, y0), fill=(20, 20, 20), width=max(2, w // 300))

            def load_font(size: int):
                font_candidates = (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Menlo.ttc",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                    "/Library/Fonts/Arial Unicode.ttf",
                )
                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.047)))
            sub_font = load_font(max(22, int(w * 0.034)))

            def text_bbox(font, text: str):
                return draw.textbbox((0, 0), text, font=font)

            margin_x = max(24, int(w * 0.055))
            row1_y = y0 + max(18, int(footer_h * 0.18))
            row2_y = y0 + max(78, int(footer_h * 0.57))
            ink = (16, 22, 32)
            accent = tuple(self._theme.theme_chrome) if self._theme.theme_chrome else (25, 83, 205)
            secondary = tuple(self._theme.theme_red) if self._theme.theme_red else (210, 34, 34)

            brand = "VNVNC.RU"
            time_text = moscow_time
            weekday = footer_date
            venue = "КОНЮШЕННАЯ 2В"

            draw.text((margin_x, row1_y), brand, font=main_font, fill=accent)

            time_box = text_bbox(main_font, time_text)
            draw.text(
                (w - margin_x - (time_box[2] - time_box[0]), row1_y),
                time_text,
                font=main_font,
                fill=secondary,
            )

            draw.text((margin_x, row2_y), weekday, font=sub_font, fill=ink)

            venue_box = text_bbox(sub_font, venue)
            venue_w = venue_box[2] - venue_box[0]
            draw.text((w - margin_x - venue_w, row2_y), venue, font=sub_font, fill=ink)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp white-theme footer: {e}")
            return image_bytes

    def _stamp_alye_parusa_footer(
        self, image_bytes: bytes, footer_date: str, moscow_time: str
    ) -> bytes:
        """Paint deterministic Алые Паруса footer text over the AI image."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = img.size
            footer_h = max(int(h * 0.14), 160)
            y0 = h - footer_h
            draw = ImageDraw.Draw(img)

            black = (0, 0, 0)
            white = (255, 255, 255)
            scarlet = tuple(self._theme.theme_red) if self._theme.theme_red else (218, 34, 28)

            draw.rectangle((0, y0, w, h), fill=black)
            border = max(3, w // 220)
            draw.line((0, y0, w, y0), fill=scarlet, width=border)
            draw.line(
                (0, y0 + border + 4, w, y0 + border + 4), fill=white, width=max(1, border // 2)
            )

            def load_font(size: int):
                font_candidates = (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Menlo.ttc",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                    "/Library/Fonts/Arial Unicode.ttf",
                )
                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.047)))
            sub_font = load_font(max(22, int(w * 0.034)))

            def text_width(font, text: str) -> int:
                box = draw.textbbox((0, 0), text, font=font)
                return box[2] - box[0]

            margin_x = max(24, int(w * 0.055))
            row1_y = y0 + max(22, int(footer_h * 0.19))
            row2_y = y0 + max(82, int(footer_h * 0.59))

            brand = "VNVNC.RU"
            time_text = moscow_time
            weekday = footer_date
            venue = "КОНЮШЕННАЯ 2В"

            draw.text((margin_x, row1_y), brand, font=main_font, fill=white)
            draw.text(
                (w - margin_x - text_width(main_font, time_text), row1_y),
                time_text,
                font=main_font,
                fill=scarlet,
            )
            draw.text((margin_x, row2_y), weekday, font=sub_font, fill=scarlet)
            draw.text(
                (w - margin_x - text_width(sub_font, venue), row2_y),
                venue,
                font=sub_font,
                fill=white,
            )

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp Alye Parusa footer: {e}")
            return image_bytes

    def _stamp_jara_footer(self, image_bytes: bytes, footer_date: str, moscow_time: str) -> bytes:
        """Overlay one compact pool-pass info card on the full-bleed artwork."""
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            w, h = img.size
            margin_x = max(22, int(w * 0.035))
            margin_bottom = max(22, int(h * 0.022))
            card_h = max(132, int(h * 0.108))
            x0, x1 = margin_x, w - margin_x
            y0, y1 = h - margin_bottom - card_h, h - margin_bottom
            radius = max(20, int(card_h * 0.18))

            # A soft floating shadow keeps the card legible without creating a
            # second full-width bar or erasing the generated pool scene.
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            shadow_draw = ImageDraw.Draw(shadow)
            shadow_offset = max(7, int(h * 0.006))
            shadow_draw.rounded_rectangle(
                (x0, y0 + shadow_offset, x1, y1 + shadow_offset),
                radius=radius,
                fill=(0, 48, 92, 105),
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(max(8, int(w * 0.014))))
            img = Image.alpha_composite(img, shadow)

            # Frost the actual artwork under the card, then tint it pearl-aqua.
            card_mask = Image.new("L", img.size, 0)
            ImageDraw.Draw(card_mask).rounded_rectangle((x0, y0, x1, y1), radius=radius, fill=255)
            frosted = img.filter(ImageFilter.GaussianBlur(max(5, int(w * 0.009))))
            img = Image.composite(frosted, img, card_mask)
            panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=radius,
                fill=(238, 253, 255, 232),
                outline=(255, 255, 255, 245),
                width=max(2, w // 300),
            )
            img = Image.alpha_composite(img, panel)
            draw = ImageDraw.Draw(img)

            ink = (4, 61, 91, 255)
            muted = (20, 111, 139, 255)
            white = (255, 255, 255, 255)
            red = tuple(self._theme.theme_chrome) if self._theme.theme_chrome else (255, 54, 35)
            pink = tuple(self._theme.theme_red) if self._theme.theme_red else (255, 86, 160)

            # A slim hot-to-pink accent reads as event branding, not a divider.
            accent_y = y0 + max(6, int(card_h * 0.055))
            accent_x0 = x0 + radius
            accent_x1 = x1 - radius
            accent_w = max(1, accent_x1 - accent_x0)
            accent_thickness = max(4, int(card_h * 0.035))
            for offset in range(accent_w):
                mix = offset / max(1, accent_w - 1)
                color = tuple(int(red[i] * (1.0 - mix) + pink[i] * mix) for i in range(3)) + (255,)
                draw.line(
                    (accent_x0 + offset, accent_y, accent_x0 + offset, accent_y + accent_thickness),
                    fill=color,
                )

            def load_font(size: int):
                font_candidates = (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                    "/Library/Fonts/Arial Unicode.ttf",
                )
                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.044)))
            time_font = load_font(max(27, int(w * 0.041)))
            sub_font = load_font(max(19, int(w * 0.028)))

            def text_width(font, text: str) -> int:
                box = draw.textbbox((0, 0), text, font=font)
                return box[2] - box[0]

            pad_x = max(22, int(w * 0.038))
            row1_y = y0 + max(23, int(card_h * 0.19))
            row2_y = y0 + max(82, int(card_h * 0.64))
            venue = "КОНЮШЕННАЯ 2В"

            draw.text((x0 + pad_x, row1_y), "VNVNC.RU", font=main_font, fill=ink)

            time_box = draw.textbbox((0, 0), moscow_time, font=time_font)
            time_w = time_box[2] - time_box[0]
            time_h = time_box[3] - time_box[1]
            pill_pad_x = max(17, int(w * 0.023))
            pill_pad_y = max(8, int(card_h * 0.075))
            pill_w = time_w + pill_pad_x * 2
            pill_h = time_h + pill_pad_y * 2
            pill_x = x1 - pad_x - pill_w
            pill_y = row1_y - max(4, int(card_h * 0.025))
            draw.rounded_rectangle(
                (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                radius=pill_h // 2,
                fill=red + (255,),
            )
            draw.text(
                (pill_x + pill_pad_x - time_box[0], pill_y + pill_pad_y - time_box[1]),
                moscow_time,
                font=time_font,
                fill=white,
            )

            draw.text((x0 + pad_x, row2_y), footer_date.upper(), font=sub_font, fill=muted)
            draw.text(
                (x1 - pad_x - text_width(sub_font, venue), row2_y),
                venue,
                font=sub_font,
                fill=muted,
            )

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp Jara footer: {e}")
            return image_bytes

    def _stamp_jara_logo(self, image_bytes: bytes) -> bytes:
        """Composite the deterministic supplied masthead and exact ЖАРА emblem."""
        try:
            from pathlib import Path
            from PIL import Image, ImageDraw, ImageFilter, ImageOps

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            asset_dir = Path(__file__).resolve().parents[3] / "assets" / "images"

            # Gemini occasionally puts malformed letters, a white rectangle, or
            # bland empty cyan behind the reserved logo. Replace that model-
            # controlled zone with the top of the user's supplied tropical art.
            # Posterizing it keeps the masthead compatible with the 2D portrait,
            # while a feathered lower edge preserves the generated scene below.
            masthead_path = asset_dir / "jara-style-reference.png"
            if masthead_path.exists():
                w, h = img.size
                masthead_end = max(1, int(h * 0.30))
                solid_end = max(1, int(h * 0.25))
                reference = Image.open(masthead_path).convert("RGB")
                reference = reference.crop(
                    (0, 0, reference.width, max(1, int(reference.height * 0.26)))
                )
                masthead = ImageOps.fit(
                    reference,
                    (w, masthead_end),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5),
                )
                masthead = (
                    ImageOps.posterize(masthead, 5).filter(ImageFilter.SMOOTH).convert("RGBA")
                )

                layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
                layer.paste(masthead, (0, 0))
                mask = Image.new("L", img.size, 0)
                mask_draw = ImageDraw.Draw(mask)
                mask_draw.rectangle((0, 0, w, solid_end), fill=255)
                feather_h = max(1, masthead_end - solid_end)
                for row in range(solid_end, masthead_end):
                    alpha = int(255 * (masthead_end - row) / feather_h)
                    mask_draw.line((0, row, w, row), fill=alpha)
                img = Image.composite(layer, img, mask)

            logo_path = asset_dir / "jara-logo-transparent.png"
            logo = Image.open(logo_path).convert("RGBA")
            alpha_bbox = logo.getchannel("A").getbbox()
            if alpha_bbox:
                logo = logo.crop(alpha_bbox)

            target_w = max(220, int(img.width * 0.62))
            target_h = max(1, int(logo.height * target_w / logo.width))
            logo = logo.resize((target_w, target_h), Image.Resampling.LANCZOS)
            x = (img.width - target_w) // 2
            y = max(24, int(img.height * 0.035))

            shadow_alpha = logo.getchannel("A").filter(
                ImageFilter.GaussianBlur(max(4, img.width // 120))
            )
            shadow = Image.new("RGBA", logo.size, (0, 50, 85, 0))
            shadow.putalpha(shadow_alpha.point(lambda value: int(value * 0.42)))
            img.alpha_composite(shadow, (x, y + max(4, img.height // 350)))
            img.alpha_composite(logo, (x, y))

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp Jara logo: {e}")
            return image_bytes

    def _stamp_world_cup_final_logo(self, image_bytes: bytes) -> bytes:
        """Compatibility no-op: World Cup branding belongs to the image model."""
        # Kept temporarily for callers from older deployments. It must never
        # composite an emblem or title over newly generated artwork.
        return image_bytes

        # Legacy implementation is intentionally unreachable until it can be
        # removed after every deployed machine has updated.
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            w, h = img.size
            margin_x = max(22, int(w * 0.035))
            x0, x1 = margin_x, w - margin_x
            y0 = max(20, int(h * 0.022))
            card_h = max(190, int(h * 0.165))
            y1 = y0 + card_h
            radius = max(22, int(card_h * 0.13))

            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                (x0, y0 + 8, x1, y1 + 8), radius=radius, fill=(0, 0, 18, 150)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(max(8, int(w * 0.014))))
            img = Image.alpha_composite(img, shadow)

            panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=radius,
                fill=(7, 21, 47, 238),
                outline=(244, 197, 66, 245),
                width=max(2, w // 260),
            )
            # Two team-color rails make the panel read like a live broadcast
            # graphic rather than an empty generic header bar.
            rail_y = y0 + max(6, int(card_h * 0.045))
            rail_h = max(5, int(card_h * 0.035))
            mid = (x0 + x1) // 2
            panel_draw.rounded_rectangle(
                (x0 + radius, rail_y, mid - 8, rail_y + rail_h),
                radius=rail_h // 2,
                fill=(117, 200, 245, 255),
            )
            panel_draw.rounded_rectangle(
                (mid + 8, rail_y, x1 - radius, rail_y + rail_h),
                radius=rail_h // 2,
                fill=(229, 41, 47, 255),
            )
            img = Image.alpha_composite(img, panel)
            draw = ImageDraw.Draw(img)

            def load_font(size: int):
                for font_path in (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                ):
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            def centered_text(text: str, center_x: int, y: int, font, fill_color) -> None:
                box = draw.textbbox((0, 0), text, font=font)
                draw.text((center_x - (box[2] - box[0]) // 2, y), text, font=font, fill=fill_color)

            title_font = load_font(max(25, int(w * 0.041)))
            team_font = load_font(max(25, int(w * 0.038)))
            small_font = load_font(max(18, int(w * 0.025)))
            white = (255, 255, 255, 255)
            gold = (244, 197, 66, 255)

            centered_text(
                "WORLD CUP 2026", w // 2, y0 + max(22, int(card_h * 0.12)), title_font, white
            )

            emblem_path = (
                Path(__file__).resolve().parents[3]
                / "assets"
                / "images"
                / "world-cup-final-emblem.png"
            )
            emblem = Image.open(emblem_path).convert("RGBA")
            bbox = emblem.getchannel("A").getbbox()
            if bbox:
                emblem = emblem.crop(bbox)
            emblem_h = max(76, int(card_h * 0.48))
            emblem_w = max(1, int(emblem.width * emblem_h / emblem.height))
            emblem = emblem.resize((emblem_w, emblem_h), Image.Resampling.LANCZOS)
            emblem_x = (w - emblem_w) // 2
            emblem_y = y0 + max(56, int(card_h * 0.31))
            img.alpha_composite(emblem, (emblem_x, emblem_y))
            draw = ImageDraw.Draw(img)

            team_y = y0 + max(92, int(card_h * 0.48))
            left_center = (x0 + w // 2 - emblem_w // 2) // 2
            right_center = (w // 2 + emblem_w // 2 + x1) // 2
            centered_text("SPAIN", left_center, team_y, team_font, (255, 255, 255, 255))
            centered_text("ARGENTINA", right_center, team_y, team_font, (117, 200, 245, 255))
            centered_text(
                "FINAL • SUNDAY NIGHT", w // 2, y1 - max(33, int(card_h * 0.18)), small_font, gold
            )

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp World Cup final logo: {e}")
            return image_bytes

    def _stamp_world_cup_final_footer(
        self, image_bytes: bytes, footer_date: str, moscow_time: str
    ) -> bytes:
        """Overlay one compact night-stadium information card over full-bleed art."""
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            w, h = img.size
            margin_x = max(22, int(w * 0.035))
            margin_bottom = max(22, int(h * 0.022))
            card_h = max(132, int(h * 0.108))
            x0, x1 = margin_x, w - margin_x
            y0, y1 = h - margin_bottom - card_h, h - margin_bottom
            radius = max(20, int(card_h * 0.18))

            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                (x0, y0 + 8, x1, y1 + 8), radius=radius, fill=(0, 0, 18, 155)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(max(8, int(w * 0.014))))
            img = Image.alpha_composite(img, shadow)

            panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=radius,
                fill=(7, 21, 47, 235),
                outline=(255, 255, 255, 170),
                width=max(2, w // 300),
            )
            mid = (x0 + x1) // 2
            rail_y = y0 + max(6, int(card_h * 0.05))
            rail_h = max(4, int(card_h * 0.035))
            panel_draw.line(
                (x0 + radius, rail_y, mid - 5, rail_y), fill=(117, 200, 245, 255), width=rail_h
            )
            panel_draw.line(
                (mid - 5, rail_y, mid + 5, rail_y), fill=(244, 197, 66, 255), width=rail_h
            )
            panel_draw.line(
                (mid + 5, rail_y, x1 - radius, rail_y), fill=(229, 41, 47, 255), width=rail_h
            )
            img = Image.alpha_composite(img, panel)
            draw = ImageDraw.Draw(img)

            def load_font(size: int):
                for font_path in (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                ):
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.044)))
            time_font = load_font(max(27, int(w * 0.041)))
            sub_font = load_font(max(19, int(w * 0.028)))

            def text_width(font, text: str) -> int:
                box = draw.textbbox((0, 0), text, font=font)
                return box[2] - box[0]

            pad_x = max(22, int(w * 0.038))
            row1_y = y0 + max(23, int(card_h * 0.19))
            row2_y = y0 + max(82, int(card_h * 0.64))
            venue = "КОНЮШЕННАЯ 2В"
            white = (255, 255, 255, 255)
            blue = (117, 200, 245, 255)
            gold = (244, 197, 66, 255)
            red = (229, 41, 47, 255)

            draw.text((x0 + pad_x, row1_y), "VNVNC.RU", font=main_font, fill=white)
            time_box = draw.textbbox((0, 0), moscow_time, font=time_font)
            time_w = time_box[2] - time_box[0]
            time_h = time_box[3] - time_box[1]
            pill_pad_x = max(17, int(w * 0.023))
            pill_pad_y = max(8, int(card_h * 0.075))
            pill_w = time_w + pill_pad_x * 2
            pill_h = time_h + pill_pad_y * 2
            pill_x = x1 - pad_x - pill_w
            pill_y = row1_y - max(4, int(card_h * 0.025))
            draw.rounded_rectangle(
                (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                radius=pill_h // 2,
                fill=red,
                outline=gold,
                width=max(2, w // 350),
            )
            draw.text(
                (pill_x + pill_pad_x - time_box[0], pill_y + pill_pad_y - time_box[1]),
                moscow_time,
                font=time_font,
                fill=white,
            )
            draw.text((x0 + pad_x, row2_y), footer_date.upper(), font=sub_font, fill=blue)
            draw.text(
                (x1 - pad_x - text_width(sub_font, venue), row2_y),
                venue,
                font=sub_font,
                fill=gold,
            )

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp World Cup final footer: {e}")
            return image_bytes

    def _stamp_sunset_palms_footer(
        self, image_bytes: bytes, footer_date: str, moscow_time: str
    ) -> bytes:
        """Overlay one compact sunset-glass information card; never overlay the emblem."""
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            w, h = img.size
            margin_x = max(22, int(w * 0.035))
            margin_bottom = max(22, int(h * 0.022))
            card_h = max(132, int(h * 0.108))
            x0, x1 = margin_x, w - margin_x
            y0, y1 = h - margin_bottom - card_h, h - margin_bottom
            radius = max(20, int(card_h * 0.18))

            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                (x0, y0 + 9, x1, y1 + 9), radius=radius, fill=(30, 10, 38, 150)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(max(8, int(w * 0.014))))
            img = Image.alpha_composite(img, shadow)

            panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
            panel_draw = ImageDraw.Draw(panel)
            panel_draw.rounded_rectangle(
                (x0, y0, x1, y1),
                radius=radius,
                fill=(54, 27, 67, 232),
                outline=(255, 221, 174, 185),
                width=max(2, w // 300),
            )
            rail_y = y0 + max(6, int(card_h * 0.05))
            rail_h = max(4, int(card_h * 0.035))
            rail_x0, rail_x1 = x0 + radius, x1 - radius
            third = (rail_x1 - rail_x0) // 3
            panel_draw.line(
                (rail_x0, rail_y, rail_x0 + third, rail_y),
                fill=(255, 177, 87, 255),
                width=rail_h,
            )
            panel_draw.line(
                (rail_x0 + third, rail_y, rail_x0 + 2 * third, rail_y),
                fill=(242, 91, 117, 255),
                width=rail_h,
            )
            panel_draw.line(
                (rail_x0 + 2 * third, rail_y, rail_x1, rail_y),
                fill=(116, 55, 126, 255),
                width=rail_h,
            )
            img = Image.alpha_composite(img, panel)
            draw = ImageDraw.Draw(img)

            def load_font(size: int):
                for font_path in (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                ):
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.044)))
            time_font = load_font(max(27, int(w * 0.041)))
            sub_font = load_font(max(19, int(w * 0.028)))

            def text_width(font, text: str) -> int:
                box = draw.textbbox((0, 0), text, font=font)
                return box[2] - box[0]

            pad_x = max(22, int(w * 0.038))
            row1_y = y0 + max(23, int(card_h * 0.19))
            row2_y = y0 + max(82, int(card_h * 0.64))
            venue = "КОНЮШЕННАЯ 2В"
            cream = (255, 244, 224, 255)
            amber = (255, 177, 87, 255)
            coral = (242, 91, 117, 255)
            apricot = (255, 205, 146, 255)

            draw.text((x0 + pad_x, row1_y), "VNVNC.RU", font=main_font, fill=cream)
            time_box = draw.textbbox((0, 0), moscow_time, font=time_font)
            time_w = time_box[2] - time_box[0]
            time_h = time_box[3] - time_box[1]
            pill_pad_x = max(17, int(w * 0.023))
            pill_pad_y = max(8, int(card_h * 0.075))
            pill_w = time_w + pill_pad_x * 2
            pill_h = time_h + pill_pad_y * 2
            pill_x = x1 - pad_x - pill_w
            pill_y = row1_y - max(4, int(card_h * 0.025))
            draw.rounded_rectangle(
                (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                radius=pill_h // 2,
                fill=coral,
                outline=amber,
                width=max(2, w // 350),
            )
            draw.text(
                (pill_x + pill_pad_x - time_box[0], pill_y + pill_pad_y - time_box[1]),
                moscow_time,
                font=time_font,
                fill=cream,
            )
            draw.text((x0 + pad_x, row2_y), footer_date.upper(), font=sub_font, fill=apricot)
            draw.text(
                (x1 - pad_x - text_width(sub_font, venue), row2_y),
                venue,
                font=sub_font,
                fill=amber,
            )

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp Sunset Palms footer: {e}")
            return image_bytes

    def _stamp_spiderverse_footer(
        self, image_bytes: bytes, footer_date: str, moscow_time: str
    ) -> bytes:
        """Overlay a compact scarlet suit-and-web information card."""
        try:
            from PIL import Image, ImageDraw, ImageFilter, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
            w, h = img.size
            margin_x = max(22, int(w * 0.035))
            margin_bottom = max(22, int(h * 0.022))
            card_h = max(140, int(h * 0.112))
            x0, x1 = margin_x, w - margin_x
            y0, y1 = h - margin_bottom - card_h, h - margin_bottom
            radius = max(20, int(card_h * 0.18))
            navy = (8, 22, 58, 255)
            scarlet = (190, 18, 36, 242)
            bright_red = (238, 34, 51, 255)
            ivory = (255, 244, 220, 255)
            cyan = (35, 194, 214, 255)

            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                (x0, y0 + 10, x1, y1 + 10), radius=radius, fill=(2, 5, 18, 190)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(max(7, int(w * 0.012))))
            img = Image.alpha_composite(img, shadow)

            panel = Image.new("RGBA", img.size, (0, 0, 0, 0))
            pd = ImageDraw.Draw(panel)
            pd.rounded_rectangle(
                (x0, y0, x1, y1), radius=radius, fill=scarlet,
                outline=navy, width=max(9, int(w * 0.012)),
            )
            inset = max(8, int(w * 0.011))
            pd.rounded_rectangle(
                (x0 + inset, y0 + inset, x1 - inset, y1 - inset),
                radius=max(10, radius - inset), outline=ivory, width=max(2, w // 320),
            )

            # Suit-web geometry grows from both upper corners but stays behind text.
            web_width = max(2, w // 380)
            for anchor_x, direction in ((x0 + inset, 1), (x1 - inset, -1)):
                anchor_y = y0 + inset
                reach_x = int((x1 - x0) * 0.34)
                for fraction in (0.34, 0.67, 1.0):
                    pd.line(
                        (anchor_x, anchor_y, anchor_x + direction * int(reach_x * fraction), y1 - inset),
                        fill=(8, 22, 58, 150), width=web_width,
                    )
                for ring in (0.35, 0.62, 0.9):
                    rw = int(reach_x * ring)
                    rh = int(card_h * ring)
                    box = (anchor_x - rw, anchor_y - rh, anchor_x + rw, anchor_y + rh)
                    if direction > 0:
                        pd.arc(box, 0, 90, fill=(8, 22, 58, 150), width=web_width)
                    else:
                        pd.arc(box, 90, 180, fill=(8, 22, 58, 150), width=web_width)

            rail_y = y0 + max(7, int(card_h * 0.055))
            pd.line((x0 + radius, rail_y, x1 - radius, rail_y), fill=bright_red, width=max(5, int(card_h * 0.035)))
            pd.line((x0 + radius, rail_y + max(5, int(card_h * 0.04)), x1 - radius, rail_y + max(5, int(card_h * 0.04))), fill=cyan, width=max(2, int(card_h * 0.014)))
            img = Image.alpha_composite(img, panel)
            draw = ImageDraw.Draw(img)

            def load_font(size: int):
                for font_path in (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                ):
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.044)))
            time_font = load_font(max(27, int(w * 0.041)))
            sub_font = load_font(max(19, int(w * 0.028)))
            text_width = lambda font, text: draw.textbbox((0, 0), text, font=font)[2]
            pad_x = max(28, int(w * 0.045))
            row1_y = y0 + max(28, int(card_h * 0.22))
            row2_y = y0 + max(88, int(card_h * 0.66))
            venue = "КОНЮШЕННАЯ 2В"

            draw.text((x0 + pad_x, row1_y), "VNVNC.RU", font=main_font, fill=ivory)
            time_box = draw.textbbox((0, 0), moscow_time, font=time_font)
            time_w, time_h = time_box[2] - time_box[0], time_box[3] - time_box[1]
            pill_pad_x, pill_pad_y = max(17, int(w * 0.023)), max(8, int(card_h * 0.07))
            pill_w, pill_h = time_w + pill_pad_x * 2, time_h + pill_pad_y * 2
            pill_x, pill_y = x1 - pad_x - pill_w, row1_y - max(4, int(card_h * 0.025))
            draw.rounded_rectangle(
                (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                radius=pill_h // 2, fill=navy, outline=ivory, width=max(2, w // 350),
            )
            draw.text(
                (pill_x + pill_pad_x - time_box[0], pill_y + pill_pad_y - time_box[1]),
                moscow_time, font=time_font, fill=ivory,
            )
            draw.text((x0 + pad_x, row2_y), footer_date.upper(), font=sub_font, fill=ivory)
            draw.text((x1 - pad_x - text_width(sub_font, venue), row2_y), venue, font=sub_font, fill=ivory)

            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp SPIDERVERSE footer: {e}")
            return image_bytes

    def _stamp_2k17_footer(self, image_bytes: bytes, footer_date: str, moscow_time: str) -> bytes:
        """Paint deterministic 2K17 black-label footer text over the AI image."""
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            w, h = img.size
            footer_h = max(int(h * 0.15), 170)
            y0 = h - footer_h
            draw = ImageDraw.Draw(img)

            draw.rectangle((0, y0, w, h), fill=(255, 255, 255))

            def load_font(size: int):
                font_candidates = (
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
                    "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
                    "/System/Library/Fonts/SFNSMono.ttf",
                    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
                    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
                    "/Library/Fonts/Arial Unicode.ttf",
                )
                for font_path in font_candidates:
                    if os.path.exists(font_path):
                        return ImageFont.truetype(font_path, size)
                return ImageFont.load_default()

            main_font = load_font(max(28, int(w * 0.047)))
            sub_font = load_font(max(24, int(w * 0.038)))

            def label_size(font, text: str, pad_x: int, pad_y: int) -> tuple[int, int]:
                box = draw.textbbox((0, 0), text, font=font)
                return (box[2] - box[0] + pad_x * 2, box[3] - box[1] + pad_y * 2)

            def draw_label(
                x: int, y: int, text: str, font, pad_x: int, pad_y: int
            ) -> tuple[int, int]:
                label_w, label_h = label_size(font, text, pad_x, pad_y)
                draw.rectangle((x, y, x + label_w, y + label_h), fill=(0, 0, 0))
                box = draw.textbbox((0, 0), text, font=font)
                text_x = x + pad_x - box[0]
                text_y = y + pad_y - box[1]
                draw.text((text_x, text_y), text, font=font, fill=(255, 255, 255))
                return label_w, label_h

            margin_x = max(22, int(w * 0.05))
            pad_x = max(14, int(w * 0.018))
            pad_y = max(8, int(footer_h * 0.045))
            gap_y = max(10, int(footer_h * 0.07))

            brand = "VNVNC.RU"
            time_text = moscow_time
            weekday = footer_date
            venue = "КОНЮШЕННАЯ 2В"

            row1_y = y0 + max(18, int(footer_h * 0.12))
            row2_y = row1_y + label_size(main_font, brand, pad_x, pad_y)[1] + gap_y

            brand_w, _ = draw_label(margin_x, row1_y, brand, main_font, pad_x, pad_y)
            time_w, _ = label_size(main_font, time_text, pad_x, pad_y)
            if margin_x + brand_w + max(10, int(w * 0.025)) + time_w <= w - margin_x:
                draw_label(w - margin_x - time_w, row1_y, time_text, main_font, pad_x, pad_y)

            weekday_w, _ = draw_label(margin_x, row2_y, weekday, sub_font, pad_x, pad_y)
            venue_w, _ = label_size(sub_font, venue, pad_x, pad_y)
            if margin_x + weekday_w + max(10, int(w * 0.025)) + venue_w <= w - margin_x:
                draw_label(w - margin_x - venue_w, row2_y, venue, sub_font, pad_x, pad_y)
            else:
                row3_y = row2_y + label_size(sub_font, weekday, pad_x, pad_y)[1] + gap_y
                if row3_y + label_size(sub_font, venue, pad_x, pad_y)[1] <= h - max(
                    8, int(footer_h * 0.04)
                ):
                    draw_label(margin_x, row3_y, venue, sub_font, pad_x, pad_y)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp 2K17 footer: {e}")
            return image_bytes

    def _upload_ai_result_async(self) -> None:
        """Upload AI-generated photo booth image for gallery sharing.

        Gallery uploads must stay full-color AI artwork. Printing is handled
        separately by the print manager, which may render a monochrome RP80
        receipt, but that print artifact must never replace the gallery image.
        """
        # Get image for upload
        caricature_bytes = (
            self._state.ai_label_bytes or self._state.ai_display_bytes or self._state.photo_bytes
        )

        if not caricature_bytes:
            logger.warning("No image bytes available for upload")
            return

        if self._should_skip_public_gallery_upload():
            source_photo_path = self._persist_bot_source_photo("faceless")
            logger.warning(
                "Skipping public photobooth gallery upload: no visible guest face in source photo"
            )
            append_bot_event(
                "photobooth_photo",
                {
                    "mode": self.name,
                    "theme_id": getattr(self._theme, "id", ""),
                    "theme_name": getattr(self._theme, "event_name", ""),
                    "camera_id": self._state.selected_camera_id,
                    "result_bytes": len(
                        self._state.ai_label_bytes or self._state.ai_display_bytes or b""
                    ),
                    "source_photo_bytes": len(self._state.photo_bytes or b""),
                    "source_photo_path": source_photo_path,
                    "success": False,
                    "skipped": True,
                    "error": "No visible guest face in source photo; public gallery upload skipped",
                },
            )
            return

        logger.info("Uploading photo booth image...")
        self._state.is_uploading = True

        pre_info = pre_generate_upload_info("photobooth", "png")
        self._state.qr_url = pre_info.short_url
        self._state.qr_image = generate_qr_image(pre_info.short_url)
        source_photo_path = self._persist_bot_source_photo(pre_info.short_id)

        logger.info("Uploading full-color AI image: %d bytes", len(caricature_bytes))
        self._uploader.upload_bytes(
            caricature_bytes,
            prefix="photobooth",
            extension="png",
            content_type="image/png",
            callback=self._on_upload_complete,
            pre_info=pre_info,
            metadata={"source_photo_path": source_photo_path} if source_photo_path else None,
        )

    def _upload_raw_capture_async(self) -> None:
        """Upload the unprocessed camera photo for gallery sharing."""
        if not self._state.photo_bytes:
            logger.warning("No raw capture bytes available for upload")
            return

        logger.info("Uploading raw photobooth capture...")
        self._state.is_uploading = True

        pre_info = pre_generate_upload_info("photobooth", "jpg")
        self._state.qr_url = pre_info.short_url
        self._state.qr_image = generate_qr_image(pre_info.short_url)
        source_photo_path = self._persist_bot_source_photo(pre_info.short_id)

        self._uploader.upload_bytes(
            self._state.photo_bytes,
            prefix="photobooth",
            extension="jpg",
            content_type="image/jpeg",
            callback=self._on_upload_complete,
            pre_info=pre_info,
            metadata={"source_photo_path": source_photo_path} if source_photo_path else None,
        )

    def _upload_photo_async(self) -> None:
        """Upload photo for QR sharing using shared AsyncUploader."""
        if not self._state.photo_bytes:
            logger.warning("No photo bytes available, skipping upload")
            return

        logger.info("Starting async photo upload via AsyncUploader")
        self._state.is_uploading = True

        self._uploader.upload_bytes(
            self._state.photo_bytes,
            prefix="photo",
            extension="jpg",
            content_type="image/jpeg",
            callback=self._on_upload_complete,
        )

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle upload completion callback."""
        self._state.is_uploading = False
        photo_event = {
            "mode": self.name,
            "theme_id": getattr(self._theme, "id", ""),
            "theme_name": getattr(self._theme, "event_name", ""),
            "camera_id": self._state.selected_camera_id,
            "result_bytes": len(self._state.ai_label_bytes or self._state.ai_display_bytes or b""),
            "source_photo_bytes": len(self._state.photo_bytes or b""),
            "source_photo_path": self._state.bot_source_photo_path,
        }
        if result.success:
            self._state.qr_url = result.short_url or result.url  # Prefer short URL for QR/printing
            self._state.qr_image = result.qr_image
            logger.info(f"Photo uploaded successfully: {self._state.qr_url}")
            append_bot_event(
                "photobooth_photo",
                {
                    **photo_event,
                    "success": True,
                    "url": result.url,
                    "short_url": result.short_url,
                    "short_id": result.short_id,
                },
            )
        else:
            logger.error(f"Photo upload failed: {result.error}")
            append_bot_event(
                "photobooth_photo",
                {
                    **photo_event,
                    "success": False,
                    "error": result.error,
                },
            )

    def _persist_bot_source_photo(self, short_id: str) -> Optional[str]:
        """Persist the raw camera JPEG so the Telegram bot can send it with the result."""
        if self._state.bot_source_photo_path:
            return self._state.bot_source_photo_path
        if not self._state.photo_bytes:
            return None

        try:
            data_dir = Path(os.environ.get("ARCADE_DATA_DIR", "/home/kirniy/modular-arcade/data"))
            source_dir = data_dir / "bot_source_photos"
            source_dir.mkdir(parents=True, exist_ok=True)
            path = source_dir / f"source_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{short_id}.jpg"
            path.write_bytes(self._state.photo_bytes)
            try:
                path.chmod(0o666)
            except OSError:
                pass
            self._state.bot_source_photo_path = str(path)
            return self._state.bot_source_photo_path
        except Exception as e:
            logger.warning("Failed to persist source photo for Telegram bot: %s", e)
            return None

    def _should_skip_public_gallery_upload(self) -> bool:
        """Skip only when strict faceless filtering is explicitly enabled."""
        # Haar cascades are not reliable enough under tilted, magenta/green
        # club lighting to be a default publication gate. A false rejection
        # loses a paid/generated guest photo, while an occasional empty frame
        # is recoverable. Production therefore fails open; operators may opt
        # into strict filtering explicitly after validating their lighting.
        if os.getenv("PHOTOBOOTH_SKIP_FACELESS_GALLERY", "false").lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            return False
        if self._state.selected_camera_id != "primary":
            return False
        if self._state.source_has_visible_face is None:
            self._state.source_has_visible_face = self._source_photo_has_visible_face()
        return self._state.source_has_visible_face is False

    def _source_photo_has_visible_face(self) -> bool:
        """Return False only when all conservative face checks miss."""
        if not self._state.photo_bytes:
            return True
        if (self._state.source_identity_face_count or 0) > 0:
            logger.info(
                "Photobooth source face check passed using %d identity reference crop(s)",
                self._state.source_identity_face_count,
            )
            return True
        try:
            import cv2

            image = PILImage.open(io.BytesIO(self._state.photo_bytes)).convert("RGB")
            frame = np.array(image)
            gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
            cascade_dir = Path(cv2.data.haarcascades)
            strict_min_side = max(36, min(gray.shape[:2]) // 10)
            fallback_min_side = max(24, min(gray.shape[:2]) // 20)
            detection_passes = [
                (
                    "strict frontal",
                    cascade_dir / "haarcascade_frontalface_default.xml",
                    cv2.equalizeHist(gray),
                    strict_min_side,
                    4,
                ),
                (
                    "raw frontal",
                    cascade_dir / "haarcascade_frontalface_default.xml",
                    gray,
                    fallback_min_side,
                    3,
                ),
                (
                    "alternate frontal",
                    cascade_dir / "haarcascade_frontalface_alt2.xml",
                    gray,
                    fallback_min_side,
                    3,
                ),
                (
                    "left profile",
                    cascade_dir / "haarcascade_profileface.xml",
                    gray,
                    fallback_min_side,
                    3,
                ),
                (
                    "right profile",
                    cascade_dir / "haarcascade_profileface.xml",
                    cv2.flip(gray, 1),
                    fallback_min_side,
                    3,
                ),
            ]
            loaded_detector = False
            for pass_name, classifier_path, pass_image, min_side, min_neighbors in detection_passes:
                if not classifier_path.exists():
                    continue
                detector = cv2.CascadeClassifier(str(classifier_path))
                if detector.empty():
                    continue
                loaded_detector = True
                faces = detector.detectMultiScale(
                    pass_image,
                    scaleFactor=1.08,
                    minNeighbors=min_neighbors,
                    minSize=(min_side, min_side),
                    flags=cv2.CASCADE_SCALE_IMAGE,
                )
                if len(faces) > 0:
                    logger.info(
                        "Photobooth source face check passed (%s) with %d face(s)",
                        pass_name,
                        len(faces),
                    )
                    return True

            if not loaded_detector:
                logger.warning(
                    "Photobooth source face detectors unavailable; allowing gallery upload"
                )
                return True
            logger.warning("Photobooth source face check found no visible faces")
            return False
        except Exception as e:
            logger.warning(
                "Photobooth source face check unavailable; allowing gallery upload: %s", e
            )
            return True

    def _start_printing_now(self) -> None:
        """Start printing immediately when result screen appears.

        This is called as soon as AI generation completes, so the label
        prints while the user views the result and QR code.
        """
        if self._state.is_printing:
            return  # Already printing

        image_for_print = (
            self._state.ai_label_bytes or self._state.ai_display_bytes or self._state.photo_bytes
        )
        if not image_for_print:
            logger.warning("No image available for printing")
            return

        self._state.is_printing = True
        logger.info("Starting print immediately on result screen")

        # Emit print event directly
        print_data = {
            "type": "photobooth",
            "caricature": image_for_print,
            "photo": self._state.photo_bytes,
            "qr_url": self._state.qr_url,
            "short_url": self._state.qr_url,  # Explicitly pass for footer display
            "qr_image": self._state.qr_image,
        }
        self.context.event_bus.emit(
            Event(EventType.PRINT_START, data=print_data, source="photobooth")
        )

    def _update_result(self, delta_ms: float) -> None:
        """Update result display timer."""
        self._state.countdown_timer -= delta_ms / 1000.0

        if self._state.flash_timer > 0:
            self._state.flash_timer -= delta_ms / 1000.0
        if self._state.waiting_finish_timer > 0:
            self._state.waiting_finish_timer = max(
                0.0,
                self._state.waiting_finish_timer - delta_ms / 1000.0,
            )

        if self._state.countdown_timer <= 0:
            # Auto-return to ready state
            self._complete_session()

    def _complete_session(self) -> None:
        """Complete the session.

        Printing already started when result screen appeared,
        so should_print=False to avoid double printing.
        """
        result = ModeResult(
            mode_name=self.name,
            success=True,
            data={
                "qr_url": self._state.qr_url,
            },
            display_text="ФОТО ГОТОВО!",
            ticker_text="СКАЧАЙ ПО QR!",
            should_print=False,  # Already printed when result screen appeared
            skip_manager_result=True,  # Photobooth has its own result display, skip manager's
            print_data=None,  # No need - already printed
        )
        self.complete(result)
        self._working = False

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        # Pre-flash: bright white screen to light up subjects BEFORE capture
        if self._state.pre_flash_timer > 0:
            fill(buffer, (160, 160, 170))  # Dimmer flash to avoid overexposure
            return

        if self._state.flash_timer > 0:
            # Flash effect (from flashOn)
            fill(buffer, (160, 160, 170))
            return

        if self._state.is_generating:
            # Show AI generation progress
            self._render_generating(buffer)
            return

        if self._state.show_result and self._state.waiting_finish_timer > 0:
            self._render_waiting_screen(buffer)
            return

        if self._state.show_result:
            # Show result with QR code
            self._render_result(buffer)
            return

        # Get selected camera background for active/countdown states
        frame = self._get_selected_preview_frame()
        if frame is not None and frame.shape[:2] == (128, 128):
            np.copyto(buffer, frame)
        else:
            fill(buffer, (20, 15, 30))

        if self.phase == ModePhase.ACTIVE and self._state.awaiting_camera_selection:
            self._render_camera_selector(buffer)

        elif self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            # Show countdown number - big and centered
            self._render_countdown(buffer)

        elif self.phase == ModePhase.ACTIVE:
            # Show "press button" prompt
            self._render_ready(buffer)

    def _render_countdown(self, buffer: NDArray[np.uint8]) -> None:
        """Render countdown number with theme colors."""
        # Keep the live preview visible while tinting all four frame edges with
        # the active theme instead of the old hard-coded red channel.
        frame_tint = np.asarray(self.THEME_CHROME, dtype=np.uint16) // 3
        for edge in (buffer[:4, :, :], buffer[-4:, :, :], buffer[:, :4, :], buffer[:, -4:, :]):
            edge[:] = np.minimum(edge.astype(np.uint16) + frame_tint, 255).astype(np.uint8)

        # Big countdown number in chrome with black outline for visibility
        num_str = str(self._state.countdown)
        for ox in [-2, -1, 0, 1, 2]:
            for oy in [-2, -1, 0, 1, 2]:
                if ox != 0 or oy != 0:
                    draw_centered_text(buffer, num_str, 40 + oy, self.THEME_BLACK, scale=5)
        draw_centered_text(buffer, num_str, 40, self.THEME_CHROME, scale=5)

    def _render_camera_selector(self, buffer: NDArray[np.uint8]) -> None:
        """Render live camera selector over the currently selected preview."""
        selected_hdmi = self._state.selected_camera_id == "hdmi"
        label = self.CAMERA_2_LABEL if selected_hdmi else self.CAMERA_1_LABEL
        accent = self.THEME_CHROME if not selected_hdmi else self.THEME_RED
        dim = (120, 120, 120)

        draw_rect(buffer, 3, 3, 122, 14, (0, 0, 0))
        draw_centered_text(buffer, label, 6, (255, 255, 255), scale=1)

        draw_rect(buffer, 0, 92, 128, 36, (0, 0, 0))
        draw_text(buffer, "1", 12, 105, self.THEME_CHROME if not selected_hdmi else dim, scale=2)
        draw_text(buffer, "2", 104, 105, self.THEME_RED if selected_hdmi else dim, scale=2)
        draw_centered_text(buffer, "ЖМИ", 96, (255, 255, 255), scale=1)
        draw_centered_text(buffer, "ВЫБРАТЬ", 116, accent, scale=1)

        if selected_hdmi and not hdmi_capture_service.has_signal():
            draw_rect(buffer, 10, 38, 108, 28, (0, 0, 0))
            draw_centered_text(buffer, "НЕТ HDMI", 43, (255, 28, 0), scale=1)
            draw_centered_text(buffer, "ЖМИ 1", 55, (255, 224, 23), scale=1)
        elif (
            selected_hdmi
            and hdmi_capture_service.wall_is_owner()
            and not hdmi_capture_service.has_fresh_shared_frame()
        ):
            draw_rect(buffer, 13, 45, 102, 20, (0, 0, 0))
            draw_centered_text(buffer, "ЖДУ HDMI", 51, (255, 224, 23), scale=1)

    def _render_waiting_screen(self, buffer: NDArray[np.uint8]) -> None:
        """Render a full-screen waiting state with stable high-contrast text."""
        time_ms = int(self._time_in_phase)
        if self._state.waiting_finish_timer > 0:
            finish_progress = 1.0 - (
                self._state.waiting_finish_timer / self.WAITING_FINISH_SPIN_SECONDS
            )
            finish_progress = min(1.0, max(0.0, finish_progress))
            seconds_left = max(
                0, int(round(self._state.waiting_finish_from_seconds * (1.0 - finish_progress)))
            )
            countdown_progress = min(1.0, 1.0 - (seconds_left / self.WAITING_COUNTDOWN_SECONDS))
        else:
            elapsed_seconds = max(0, time_ms // 1000)
            seconds_left = max(0, self.WAITING_COUNTDOWN_SECONDS - elapsed_seconds)
            countdown_progress = min(1.0, elapsed_seconds / self.WAITING_COUNTDOWN_SECONDS)
        countdown_text = f"{seconds_left // 60}:{seconds_left % 60:02d}"
        message_index = (time_ms // 3500) % len(self.WAITING_COPY)
        main_text, second_text = self.WAITING_COPY[message_index]

        fill(buffer, self.WAITING_BG)
        draw_rect(buffer, 0, 0, 128, 2, self.WAITING_ACCENT)
        draw_rect(buffer, 0, 126, 128, 2, self.WAITING_ACCENT)
        draw_rect(buffer, 0, 0, 2, 128, self.WAITING_ACCENT)
        draw_rect(buffer, 126, 0, 2, 128, self.WAITING_ACCENT)

        draw_centered_text(buffer, main_text, 10, self.WAITING_TEXT, scale=2)
        draw_centered_text(buffer, countdown_text, 34, self.WAITING_TEXT, scale=4)
        draw_centered_text(buffer, "ДО ПЕЧАТИ", 68, self.WAITING_TEXT, scale=1)
        draw_centered_text(buffer, second_text, 81, self.WAITING_ACCENT, scale=1)
        draw_centered_text(buffer, "НЕ НАЖИМАЙ КНОПКИ", 93, self.WAITING_TEXT, scale=1)
        draw_centered_text(buffer, "ОСТАВАЙСЯ РЯДОМ", 104, self.WAITING_TEXT, scale=1)

        bar_x = 10
        bar_y = 113
        bar_w = 108
        bar_h = 7
        fill_w = max(4, int(bar_w * countdown_progress))
        draw_rect(buffer, bar_x, bar_y, bar_w, bar_h, self.WAITING_DIM)
        draw_rect(buffer, bar_x, bar_y, fill_w, bar_h, self.WAITING_ACCENT)

    def _render_generating(self, buffer: NDArray[np.uint8]) -> None:
        """Render the full-screen waiting state while AI is generating."""
        self._render_waiting_screen(buffer)

    def _render_ready(self, buffer: NDArray[np.uint8]) -> None:
        """Render ready state."""
        # Always show camera preview with small logo overlay
        if self._logo_rgba is not None:
            try:
                small = PILImage.fromarray(self._logo_rgba).resize(
                    (32, 32), PILImage.Resampling.LANCZOS
                )
                small_arr = np.array(small, dtype=np.uint8)
                alpha = small_arr[:, :, 3:4].astype(np.float32) / 255.0
                rgb = small_arr[:, :, :3].astype(np.float32)
                y1, x1 = 2, 128 - 34
                bg = buffer[y1 : y1 + 32, x1 : x1 + 32].astype(np.float32)
                buffer[y1 : y1 + 32, x1 : x1 + 32] = (rgb * alpha + bg * (1.0 - alpha)).astype(
                    np.uint8
                )
            except Exception:
                pass

        # Semi-transparent overlay for text
        ready_band = buffer[-24:, :, :]
        ready_band[:] = (ready_band.astype(np.float32) * 0.35).astype(np.uint8)
        ready_tint = np.asarray(self.THEME_BLACK, dtype=np.uint16) // 2
        ready_band[:] = np.minimum(ready_band.astype(np.uint16) + ready_tint, 255).astype(np.uint8)
        draw_rect(buffer, 0, 126, 128, 2, self.THEME_CHROME)

        # Instruction text
        draw_centered_text(buffer, "ЖМИ", 115, self.THEME_CHROME, scale=1)

    def _render_result(self, buffer: NDArray[np.uint8]) -> None:
        """Render result screen - full screen AI photo or QR."""
        if self._state.result_view == "photo":
            # Full screen AI-generated photo booth (1:1 square for display)
            if self._state.ai_display_frame is not None:
                np.copyto(buffer, self._state.ai_display_frame)
            elif self._state.photo_frame is not None:
                # Fallback to original photo if AI failed
                np.copyto(buffer, self._state.photo_frame)
            else:
                fill(buffer, self.THEME_BLACK)
                draw_centered_text(buffer, "ФОТО", 55, self.THEME_CHROME, scale=1)

            # Download hint overlay at bottom
            result_band = buffer[-28:, :, :]
            result_band[:] = (result_band.astype(np.float32) * 0.3).astype(np.uint8)
            result_tint = np.asarray(self.THEME_BLACK, dtype=np.uint16) // 2
            result_band[:] = np.minimum(result_band.astype(np.uint16) + result_tint, 255).astype(
                np.uint8
            )
            draw_rect(buffer, 0, 100, 128, 2, self.THEME_CHROME)

            # Animated diagonal arrow pointing down-right (↘)
            arrow_color = self.THEME_CHROME
            # Pulsing animation - arrow bounces toward corner
            bounce = int(3 * abs(((self._time_in_phase // 150) % 10) - 5) / 5)
            ax, ay = 118 + bounce, 108 + bounce  # Arrow tip position (bottom-right area)

            # Larger arrow with thicker lines
            for offset in range(-1, 2):  # Draw 3 lines for thickness
                draw_line(buffer, ax - 18 + offset, ay - 14, ax + offset, ay, arrow_color)  # Shaft
                draw_line(
                    buffer, ax + offset, ay, ax - 6 + offset, ay - 2, arrow_color
                )  # Arrowhead left
                draw_line(
                    buffer, ax + offset, ay, ax - 2 + offset, ay - 6, arrow_color
                )  # Arrowhead top

            draw_text(buffer, "СКАНИРУЙ КОД", 4, 102, self.THEME_CHROME, scale=1)
            draw_text(buffer, "ЧЕРЕЗ 2-3 МИН ОБНОВИ", 4, 110, (200, 180, 255), scale=1)
            draw_text(buffer, "НАЙДЕШЬ ФОТО", 4, 118, (200, 180, 255), scale=1)

        elif self._state.result_view == "qr":
            # Full screen QR code
            fill(buffer, (255, 255, 255))  # White background for QR

            if self._state.qr_image is not None:
                qr_h, qr_w = self._state.qr_image.shape[:2]
                target_size = 120
                if qr_h != target_size or qr_w != target_size:
                    from PIL import Image

                    qr_img = Image.fromarray(self._state.qr_image)
                    qr_img = qr_img.resize((target_size, target_size), Image.Resampling.NEAREST)
                    qr_scaled = np.array(qr_img, dtype=np.uint8)
                else:
                    qr_scaled = self._state.qr_image

                qr_h, qr_w = qr_scaled.shape[:2]
                x_offset = (128 - qr_w) // 2
                y_offset = (128 - qr_h) // 2
                buffer[y_offset : y_offset + qr_h, x_offset : x_offset + qr_w] = qr_scaled
            elif self._state.is_uploading:
                fill(buffer, self.THEME_RED)
                draw_centered_text(buffer, "UPLOAD", 50, self.THEME_CHROME, scale=1)
                draw_centered_text(buffer, "QR...", 65, self.THEME_CHROME, scale=1)
            else:
                fill(buffer, self.THEME_RED)
                draw_centered_text(buffer, "QR", 50, self.THEME_CHROME, scale=1)
                draw_centered_text(buffer, "ЖДИТЕ", 65, self.THEME_CHROME, scale=1)

            # Hint stays on ticker/LCD for full-screen QR

    def _get_ticker_presentation(self) -> tuple[str, tuple[int, int, int]]:
        """Return ticker copy and color for the current user journey state."""
        if self.phase == ModePhase.ACTIVE and self._state.awaiting_camera_selection:
            text = "СЗАДИ" if self._state.selected_camera_id == "hdmi" else "СПЕРЕДИ"
            return text, self.TICKER_COLOR
        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            return str(self._state.countdown), self.TICKER_COLOR
        if self._state.is_generating:
            text = "ЖДИ" if int(self._time_in_phase // 3000) % 2 == 0 else "НЕ УХОДИ"
            return text, self.TICKER_COLOR
        if self._state.show_result:
            if self._state.result_view == "qr":
                return "QR", self.TICKER_COLOR
            text = "ФОТО" if int(self._time_in_phase // 3000) % 2 == 0 else "НА ЧЕКЕ"
            return text, self.TICKER_COLOR
        return self._theme.ticker_idle_text_at(self._time_in_phase), self.TICKER_COLOR

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render every photobooth state through the idle ticker renderer."""
        fill(buffer, (0, 0, 0))
        text, color = self._get_ticker_presentation()
        render_idle_style_ticker_text(
            buffer,
            text,
            color,
            self._time_in_phase,
            compact_static=getattr(self._theme, "ticker_compact_static", False),
            x_offset=(
                getattr(self._theme, "ticker_x_offset", 0)
                if text == self._theme.ticker_idle
                else 0
            ),
            safe_left=getattr(self._theme, "ticker_safe_left", 0),
        )

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self.phase == ModePhase.ACTIVE and self._state.awaiting_camera_selection:
            if self._state.selected_camera_id == "hdmi":
                return self.CAMERA_2_LABEL[:16].ljust(16)
            return self.CAMERA_1_LABEL[:16].ljust(16)
        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            return f" {self._theme.lcd_prefix}: {self._state.countdown}   "[:16].ljust(16)
        elif self._state.show_result:
            return "    ГОТОВО!   "[:16]
        else:
            return "      ЖМИ     "[:16]


PHOTOBOOTH_MENU_REGISTRY: "OrderedDict[str, Optional[str]]" = OrderedDict(
    [
        ("classic", None),
        ("boilingroom", "boilingroom"),
        ("slavic_soul", "slavic_soul"),
        ("slavic_tales", "slavic_tales"),
        ("banya_chic", "banya_chic"),
        ("brainrot", "brainrot"),
        ("wedding", "wedding"),
        ("whatsapp", "whatsapp"),
        ("mtv_night", "mtv-night"),
        ("shadow_kingdom", "shadow-kingdom"),
        ("candy_shop", "candy-shop"),
        ("street_heat", "street-heat"),
        ("office_core", "office-core"),
        ("2k17", "2k17"),
        ("summer_camp", "summer-camp"),
        ("alye-parusa", "alye-parusa"),
        ("alye_parusa", "alye-parusa"),
        ("jara", "jara"),
        ("world_cup_final", "world-cup-final"),
        ("world-cup-final", "world-cup-final"),
        ("sunset_palms", "sunset-palms"),
        ("sunset-palms", "sunset-palms"),
        ("spiderverse", "spiderverse"),
        ("vse_svoi", "vse-svoi"),
        ("vse-svoi", "vse-svoi"),
    ]
)

DEFAULT_PHOTOBOOTH_MENU_MODES = ("brainrot", "wedding", "whatsapp")


def _get_theme_menu_display_name(theme: PhotoboothTheme) -> str:
    return theme.menu_display_name or theme.event_name


def _get_theme_menu_description(theme: PhotoboothTheme) -> str:
    return theme.menu_description or theme.description or theme.event_name


def _build_theme_photobooth_mode(slot_index: int, theme_id: str) -> Type[PhotoboothMode]:
    theme = get_theme_by_id(theme_id)
    class_name = f"PhotoboothMenuMode{slot_index}"
    return type(
        class_name,
        (PhotoboothMode,),
        {
            "name": f"photobooth_mode_{slot_index}",
            "display_name": _get_theme_menu_display_name(theme),
            "description": _get_theme_menu_description(theme),
            "theme_id_override": theme.id,
        },
    )


def _build_current_theme_variant_mode(
    slot_index: int,
    theme: PhotoboothTheme,
    variant: PhotoboothMenuVariant,
) -> Type[PhotoboothMode]:
    class_name = f"PhotoboothCurrentThemeVariantMode{slot_index}"
    return type(
        class_name,
        (PhotoboothMode,),
        {
            "name": f"photobooth_mode_{slot_index}",
            "display_name": variant.display_name,
            "description": variant.description,
            "theme_id_override": theme.id,
            "ai_style_key_override": theme.ai_style_key,
            "prompt_variation_index": variant.prompt_variation_index,
            "menu_display_name_override": variant.display_name,
            "menu_description_override": variant.description,
            "menu_color_override": variant.color,
        },
    )


def _append_classic_photobooth_modes(
    resolved: list[Type[PhotoboothMode]],
    themed_slot_index: int,
) -> int:
    current_theme = get_current_theme()
    if current_theme.menu_variants:
        for variant in current_theme.menu_variants:
            resolved.append(
                _build_current_theme_variant_mode(themed_slot_index, current_theme, variant)
            )
            themed_slot_index += 1
        return themed_slot_index

    if PhotoboothMode.name not in {mode_cls.name for mode_cls in resolved}:
        resolved.append(PhotoboothMode)
    return themed_slot_index


def get_configured_photobooth_modes() -> list[Type[PhotoboothMode]]:
    """Return photobooth variants to register in menu order.

    Configure with PHOTOBOOTH_MENU_MODES as a comma-separated list of theme ids.
    Stable registered mode names stay generic (`photobooth`, `photobooth_mode_1`, ...),
    while labels/descriptions are derived from the selected theme automatically.

    Example:
        PHOTOBOOTH_MENU_MODES=classic
        PHOTOBOOTH_MENU_MODES=slavic_soul,slavic_tales,banya_chic
        PHOTOBOOTH_MENU_MODES=classic,slavic_soul
    """
    raw = os.environ.get("PHOTOBOOTH_MENU_MODES", ",".join(DEFAULT_PHOTOBOOTH_MENU_MODES))
    requested = [item.strip().lower() for item in raw.split(",") if item.strip()]
    if not requested:
        requested = list(DEFAULT_PHOTOBOOTH_MENU_MODES)

    resolved: list[Type[PhotoboothMode]] = []
    seen_theme_ids: set[str] = set()
    themed_slot_index = 1

    for key in requested:
        if key == "classic":
            themed_slot_index = _append_classic_photobooth_modes(resolved, themed_slot_index)
            continue

        theme_id = PHOTOBOOTH_MENU_REGISTRY.get(key)
        if theme_id is None:
            logger.warning("Unknown PHOTOBOOTH_MENU_MODES entry: %s", key)
            continue
        if theme_id in seen_theme_ids:
            continue

        resolved.append(_build_theme_photobooth_mode(themed_slot_index, theme_id))
        seen_theme_ids.add(theme_id)
        themed_slot_index += 1

    if not resolved:
        logger.warning(
            "PHOTOBOOTH_MENU_MODES=%r resolved to no modes, falling back to %s",
            raw,
            DEFAULT_PHOTOBOOTH_MENU_MODES,
        )
        resolved = [
            _build_theme_photobooth_mode(index, PHOTOBOOTH_MENU_REGISTRY[key])
            for index, key in enumerate(DEFAULT_PHOTOBOOTH_MENU_MODES, start=1)
            if PHOTOBOOTH_MENU_REGISTRY.get(key)
        ]

    return resolved

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
PRINTING_ENABLED = os.getenv("PHOTOBOOTH_PRINTING_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
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


def get_moscow_party_stamp(theme: PhotoboothTheme, now: Optional[datetime] = None) -> tuple[str, str]:
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

        # Theme-derived properties
        self.description = self._theme.description
        self.THEME_CHROME = self._theme.theme_chrome
        self.THEME_RED = self._theme.theme_red
        self.THEME_BLACK = self._theme.theme_black

        self._load_logo()

    def _load_logo(self) -> None:
        """Load theme logo for display overlay."""
        self._theme_reference_images = []
        try:
            logo_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "assets", "images", self._theme.logo_filename
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
                        os.path.dirname(__file__), "..", "..", "..", "assets", "images", reference_filename
                    )
                    reference_path = os.path.normpath(reference_path)
                    if not os.path.exists(reference_path):
                        logger.warning("Reference asset not found for %s: %s", self._theme.id, reference_filename)
                        continue
                    with open(reference_path, "rb") as reference_file:
                        mime_type = "image/png" if reference_path.lower().endswith(".png") else "image/jpeg"
                        self._theme_reference_images.append((reference_file.read(), mime_type))
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
        alpha = self._logo_rgba[sy:sy+(y2-y1), sx:sx+(x2-x1), 3:4].astype(np.float32) / 255.0
        rgb = self._logo_rgba[sy:sy+(y2-y1), sx:sx+(x2-x1), :3].astype(np.float32)
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

            if self._state.selected_camera_id == "hdmi" and not self._camera2_ai_enabled:
                logger.info("HDMI capture selected; skipping AI generation and uploading raw frame")
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
        """Finish a no-AI HDMI capture-card photobooth session."""
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
            canvas = Image.new('RGB', (canvas_w, canvas_h), '#FDFDFB') # Off-white Polaroid paper
            
            # Target photo size (maintain aspect ratio 3:4)
            margin = 55
            target_photo_w = canvas_w - (2 * margin)
            target_photo_h = int(target_photo_w * (4/3))
            
            photo_aspect = photo.width / photo.height
            if photo_aspect > (3/4):
                new_w = int(photo.height * (3/4))
                offset = (photo.width - new_w) // 2
                photo = photo.crop((offset, 0, offset + new_w, photo.height))
            elif photo_aspect < (3/4):
                new_h = int(photo.width * (4/3))
                offset = (photo.height - new_h) // 2
                photo = photo.crop((0, offset, photo.width, offset + new_h))
                
            photo = photo.resize((target_photo_w, target_photo_h), Image.Resampling.LANCZOS)
            canvas.paste(photo, (margin, margin))
            
            draw = ImageDraw.Draw(canvas)
            
            try:
                font_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "assets", "fonts", "Caveat-Bold.ttf")
                font_path = os.path.normpath(font_path)
                font_size = 110
                
                # Fetch font if it doesn't exist
                if not os.path.exists(font_path):
                    os.makedirs(os.path.dirname(font_path), exist_ok=True)
                    urllib.request.urlretrieve('https://github.com/google/fonts/raw/main/ofl/caveat/Caveat-Bold.ttf', font_path)
                    
                font = ImageFont.truetype(font_path, font_size)
            except Exception as e:
                logger.warning(f"Could not load custom font, using default: {e}")
                font = ImageFont.load_default()
                
            def get_text_width(f, t):
                if hasattr(f, 'getbbox'): return f.getbbox(t)[2] - f.getbbox(t)[0]
                elif hasattr(f, 'getlength'): return int(f.getlength(t))
                return f.getsize(t)[0]

            footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
            
            text_y_row1 = margin + target_photo_h + 100
            text_y_row2 = text_y_row1 + 130
            text_color = "#202022"  # Marker ink
            
            # Left text: VNVNC.RU
            draw.text((margin + 20, text_y_row1), "VNVNC.RU", font=font, fill=text_color)
            
            # Right text: Time
            time_w = get_text_width(font, moscow_time)
            draw.text((canvas_w - margin - 20 - time_w, text_y_row1), moscow_time, font=font, fill=text_color)
            
            # Bottom row left: footer date (may roll back after midnight for overnight parties)
            draw.text((margin + 20, text_y_row2), footer_date_str, font=font, fill=text_color)
            
            # Bottom row right: Конюшенная 2В
            venue_str = "КОНЮШЕННАЯ 2В"
            venue_w = get_text_width(font, venue_str)
            draw.text((canvas_w - margin - 20 - venue_w, text_y_row2), venue_str, font=font, fill=text_color)
            
            buf = io.BytesIO()
            canvas.save(buf, format="PNG")
            label_bytes = buf.getvalue()
            
            # Instead of cropping, pad the 9:16 image to 1:1 for the display
            display_canvas = Image.new('RGB', (canvas_h, canvas_h), '#000000') # 1600x1600 black background
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
                elif ai_style_key in {"office_core", "summer_camp", "2k17", "alye_parusa"}:
                    personality_context = (
                        "Do not render footer text inside the AI artwork. "
                        "Leave the bottom 12-15% as clean empty space matching the theme background; "
                        "the app will stamp VNVNC.RU, the Russian weekday, Moscow time, and venue after generation."
                    )
                else:
                    personality_context = (
                        f"Photo taken at {moscow_time} Moscow time. "
                        f"Include exactly '{moscow_time}' in the handwritten caption "
                        f"or footer area at the bottom of the image."
                    )

            # Generate only the label (9:16) image
            label_result = await self._caricature_service.generate_caricature(
                reference_photo=self._state.photo_bytes,
                style=label_style,  # 9:16 vertical
                personality_context=personality_context,
                extra_reference_images=self._theme_reference_images or None,
                prompt_variation_index=self.prompt_variation_index,
            )

            if label_result and label_result.image_data:
                label_bytes = label_result.image_data
                if ai_style_key == "2k17":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_2k17_footer(label_bytes, footer_date_str, moscow_time)
                elif ai_style_key in {"office_core", "summer_camp"}:
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_white_theme_footer(label_bytes, footer_date_str, moscow_time)
                elif ai_style_key == "alye_parusa":
                    footer_date_str, moscow_time = get_moscow_party_stamp(self._theme)
                    label_bytes = self._stamp_alye_parusa_footer(label_bytes, footer_date_str, moscow_time)
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
        """Center-crop a 9:16 image to 1:1 square for LED display."""
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            w, h = img.size

            # Center-crop to square
            if w < h:
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

    def _stamp_white_theme_footer(self, image_bytes: bytes, footer_date: str, moscow_time: str) -> bytes:
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
            draw.text((w - margin_x - (time_box[2] - time_box[0]), row1_y), time_text, font=main_font, fill=secondary)

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

    def _stamp_alye_parusa_footer(self, image_bytes: bytes, footer_date: str, moscow_time: str) -> bytes:
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
            draw.line((0, y0 + border + 4, w, y0 + border + 4), fill=white, width=max(1, border // 2))

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
            draw.text((w - margin_x - text_width(main_font, time_text), row1_y), time_text, font=main_font, fill=scarlet)
            draw.text((margin_x, row2_y), weekday, font=sub_font, fill=scarlet)
            draw.text((w - margin_x - text_width(sub_font, venue), row2_y), venue, font=sub_font, fill=white)

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Failed to stamp Alye Parusa footer: {e}")
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

            def draw_label(x: int, y: int, text: str, font, pad_x: int, pad_y: int) -> tuple[int, int]:
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
                if row3_y + label_size(sub_font, venue, pad_x, pad_y)[1] <= h - max(8, int(footer_h * 0.04)):
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
        caricature_bytes = self._state.ai_label_bytes or self._state.ai_display_bytes or self._state.photo_bytes

        if not caricature_bytes:
            logger.warning("No image bytes available for upload")
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
        """Upload the unprocessed HDMI capture-card photo for gallery sharing."""
        if not self._state.photo_bytes:
            logger.warning("No raw HDMI capture bytes available for upload")
            return

        logger.info("Uploading raw HDMI capture photo...")
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
            callback=self._on_upload_complete
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

    def _start_printing_now(self) -> None:
        """Start printing immediately when result screen appears.

        This is called as soon as AI generation completes, so the label
        prints while the user views the result and QR code.
        """
        if self._state.is_printing:
            return  # Already printing

        image_for_print = self._state.ai_label_bytes or self._state.ai_display_bytes or self._state.photo_bytes
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
        self.context.event_bus.emit(Event(
            EventType.PRINT_START,
            data=print_data,
            source="photobooth"
        ))

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
        # Keep camera at 100% visibility - just add subtle tint to edges
        # Add thin vignette border for branding without obscuring camera
        buffer[:4, :, 0] = np.minimum(buffer[:4, :, 0].astype(np.uint16) + 60, 255).astype(np.uint8)
        buffer[-4:, :, 0] = np.minimum(buffer[-4:, :, 0].astype(np.uint16) + 60, 255).astype(np.uint8)
        buffer[:, :4, 0] = np.minimum(buffer[:, :4, 0].astype(np.uint16) + 60, 255).astype(np.uint8)
        buffer[:, -4:, 0] = np.minimum(buffer[:, -4:, 0].astype(np.uint16) + 60, 255).astype(np.uint8)

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
        elif selected_hdmi and hdmi_capture_service.wall_is_owner() and not hdmi_capture_service.has_fresh_shared_frame():
            draw_rect(buffer, 13, 45, 102, 20, (0, 0, 0))
            draw_centered_text(buffer, "ЖДУ HDMI", 51, (255, 224, 23), scale=1)

    def _render_waiting_screen(self, buffer: NDArray[np.uint8]) -> None:
        """Render a full-screen waiting state with stable high-contrast text."""
        time_ms = int(self._time_in_phase)
        if self._state.waiting_finish_timer > 0:
            finish_progress = 1.0 - (self._state.waiting_finish_timer / self.WAITING_FINISH_SPIN_SECONDS)
            finish_progress = min(1.0, max(0.0, finish_progress))
            seconds_left = max(0, int(round(self._state.waiting_finish_from_seconds * (1.0 - finish_progress))))
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
                small = PILImage.fromarray(self._logo_rgba).resize((32, 32), PILImage.Resampling.LANCZOS)
                small_arr = np.array(small, dtype=np.uint8)
                alpha = small_arr[:, :, 3:4].astype(np.float32) / 255.0
                rgb = small_arr[:, :, :3].astype(np.float32)
                y1, x1 = 2, 128 - 34
                bg = buffer[y1:y1+32, x1:x1+32].astype(np.float32)
                buffer[y1:y1+32, x1:x1+32] = (rgb * alpha + bg * (1.0 - alpha)).astype(np.uint8)
            except Exception:
                pass

        # Semi-transparent overlay for text
        buffer[-24:, :, :] = (buffer[-24:, :, :].astype(np.float32) * 0.4).astype(np.uint8)
        buffer[-24:, :, 0] = np.minimum(buffer[-24:, :, 0].astype(np.uint16) + 40, 255).astype(np.uint8)

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
            buffer[-28:, :, :] = (buffer[-28:, :, :].astype(np.float32) * 0.3).astype(np.uint8)
            buffer[-28:, :, 0] = np.minimum(buffer[-28:, :, 0].astype(np.uint16) + 30, 255).astype(np.uint8)

            # Animated diagonal arrow pointing down-right (↘)
            arrow_color = self.THEME_CHROME
            # Pulsing animation - arrow bounces toward corner
            bounce = int(3 * abs(((self._time_in_phase // 150) % 10) - 5) / 5)
            ax, ay = 118 + bounce, 108 + bounce  # Arrow tip position (bottom-right area)

            # Larger arrow with thicker lines
            for offset in range(-1, 2):  # Draw 3 lines for thickness
                draw_line(buffer, ax - 18 + offset, ay - 14, ax + offset, ay, arrow_color)  # Shaft
                draw_line(buffer, ax + offset, ay, ax - 6 + offset, ay - 2, arrow_color)   # Arrowhead left
                draw_line(buffer, ax + offset, ay, ax - 2 + offset, ay - 6, arrow_color)   # Arrowhead top

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
                buffer[y_offset:y_offset + qr_h, x_offset:x_offset + qr_w] = qr_scaled
            elif self._state.is_uploading:
                fill(buffer, self.THEME_RED)
                draw_centered_text(buffer, "UPLOAD", 50, self.THEME_CHROME, scale=1)
                draw_centered_text(buffer, "QR...", 65, self.THEME_CHROME, scale=1)
            else:
                fill(buffer, self.THEME_RED)
                draw_centered_text(buffer, "QR", 50, self.THEME_CHROME, scale=1)
                draw_centered_text(buffer, "ЖДИТЕ", 65, self.THEME_CHROME, scale=1)

            # Hint stays on ticker/LCD for full-screen QR

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        fill(buffer, (0, 0, 0))

        if self.phase == ModePhase.ACTIVE and self._state.awaiting_camera_selection:
            ticker_text = "СЗАДИ" if self._state.selected_camera_id == "hdmi" else "СПЕРЕДИ"
            render_idle_style_ticker_text(buffer, ticker_text, (255, 255, 255), self._time_in_phase)
        elif self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            render_idle_style_ticker_text(buffer, str(self._state.countdown), (255, 255, 255), self._time_in_phase)
        elif self._state.is_generating:
            render_idle_style_ticker_text(buffer, "НЕ УХОДИ", (255, 40, 40), self._time_in_phase)
        elif self._state.show_result:
            if self._state.result_view == "qr":
                render_idle_style_ticker_text(buffer, "QR", (255, 255, 255), self._time_in_phase)
            else:
                render_idle_style_ticker_text(buffer, "ГОТОВО", (255, 255, 255), self._time_in_phase)
        else:
            render_idle_style_ticker_text(buffer, self._theme.ticker_idle, (255, 255, 255), self._time_in_phase)

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
    ]
)

DEFAULT_PHOTOBOOTH_MENU_MODES = ("2k17",)


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
            resolved.append(_build_current_theme_variant_mode(themed_slot_index, current_theme, variant))
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

"""Photobooth Mode - AI Photo Booth with QR sharing.

Photo booth flow:
1. Button press → Countdown (3-2-1)
2. Camera flash → Take photo
3. AI generates themed 2x2 photo booth grid
4. Show preview → Upload to S3 gallery → QR code to gallery page

Supports multiple themes (set PHOTOBOOTH_THEME env var):
- boilingroom: Raw analog concert photography, red & black palette
- tripvenice: 3D Sims-style Venetian carnival, gold & burgundy palette
"""

# When True, prints labels on thermal printer. When False, digital-only mode.
PRINTING_ENABLED = False
USE_AI_GENERATION = True  # Toggle AI generation vs local Polaroid fallback

import logging
import io
import os
import asyncio
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import numpy as np
from PIL import Image as PILImage
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.text_utils import draw_centered_text, draw_text
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult, pre_generate_upload_info, generate_qr_image
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.animation.santa_runner import SantaRunner
from artifact.audio.engine import get_audio_engine
from artifact.printing.label_receipt import LabelReceiptGenerator
from artifact.modes.photobooth_themes import get_current_theme, PhotoboothTheme

logger = logging.getLogger(__name__)


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

    BEEP_TIME = 0.2
    COUNTDOWN_SECONDS = 3
    FLASH_DURATION = 0.5
    RESULT_DURATION = 60.0  # 60 seconds to scan QR

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

        # Load theme configuration
        self._theme: PhotoboothTheme = get_current_theme()
        logger.info(f"Photobooth using theme: {self._theme.id} ({self._theme.event_name})")

        # Theme-derived properties
        self.description = self._theme.description
        self.THEME_CHROME = self._theme.theme_chrome
        self.THEME_RED = self._theme.theme_red
        self.THEME_BLACK = self._theme.theme_black

        self._load_logo()

    def _load_logo(self) -> None:
        """Load theme logo for display overlay."""
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
            else:
                logger.warning(f"Logo not found: {logo_path}")
                self._logo_rgba = None
        except Exception as e:
            logger.warning(f"Failed to load logo: {e}")
            self._logo_rgba = None

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
                # Reset timer on toggle to give more time
                self._state.countdown_timer = self.RESULT_DURATION
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
                self.change_phase(ModePhase.RESULT)

                # Start printing IMMEDIATELY when result appears (if enabled)
                if PRINTING_ENABLED:
                    self._start_printing_now()

    def _do_flash_and_capture(self) -> None:
        """Flash, capture, and start AI generation."""
        self._state.flash_timer = self.FLASH_DURATION
        self._state.countdown = 0

        # Capture photo using camera_service
        jpeg_bytes = camera_service.capture_jpeg(quality=90)
        if jpeg_bytes:
            self._state.photo_bytes = jpeg_bytes
            self._state.photo_frame = self._decode_photo_frame(jpeg_bytes)

            # Start AI generation
            self._state.is_generating = True
            self._progress_tracker.start()
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)

            # Initialize loading animation for the waiting screen
            try:
                self._santa_runner = SantaRunner()
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
            self.change_phase(ModePhase.ACTIVE)

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

    def _get_caricature_styles(self) -> tuple:
        """Get the CaricatureStyle enums for current theme.

        Returns:
            Tuple of (display_style, label_style) for 1:1 and 9:16 formats
        """
        if self._theme.ai_style_key == "malchishnik":
            return (
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_MALCHISHNIK,  # 9:16 vertical for label
            )
        elif self._theme.ai_style_key == "loveintheair":
            return (
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_LOVEINTHEAIR,  # 9:16 vertical for label
            )
        elif self._theme.ai_style_key == "tripvenice":
            return (
                CaricatureStyle.PHOTOBOOTH_VENICE_SQUARE,  # 1:1 square for display
                CaricatureStyle.PHOTOBOOTH_VENICE,  # 9:16 vertical for label
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

            moscow_tz = timezone(timedelta(hours=3))
            moscow_time = datetime.now(moscow_tz).strftime("%H:%M")
            
            text_y_row1 = margin + target_photo_h + 100
            text_y_row2 = text_y_row1 + 130
            text_color = "#202022"  # Marker ink
            
            # Left text: VNVNC.RU
            draw.text((margin + 20, text_y_row1), "VNVNC.RU", font=font, fill=text_color)
            
            # Right text: Time
            time_w = get_text_width(font, moscow_time)
            draw.text((canvas_w - margin - 20 - time_w, text_y_row1), moscow_time, font=font, fill=text_color)
            
            # Bottom row left: 20.02-22.02
            date_str = "20.02-22.02"
            draw.text((margin + 20, text_y_row2), date_str, font=font, fill=text_color)
            
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

            # For malchishnik theme, pass Moscow time so it appears in the Polaroid caption
            personality_context = None
            if self._theme.ai_style_key == "malchishnik":
                moscow_tz = timezone(timedelta(hours=3))
                moscow_time = datetime.now(moscow_tz).strftime("%H:%M")
                personality_context = (
                    f"Photo taken at {moscow_time} Moscow time. "
                    f"Include exactly '{moscow_time} МСК' in the handwritten caption "
                    f"area at the bottom of the Polaroid."
                )

            # Generate only the label (9:16) image
            label_result = await self._caricature_service.generate_caricature(
                reference_photo=self._state.photo_bytes,
                style=label_style,  # 9:16 vertical
                personality_context=personality_context,
            )

            if label_result and label_result.image_data:
                label_bytes = label_result.image_data
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

    def _upload_ai_result_async(self) -> None:
        """Upload AI-generated photo booth image for gallery sharing.

        When PRINTING_ENABLED=False (digital-only mode):
        - Uploads raw AI image directly (no label footer/QR baked in)
        - Sets unified gallery QR code for display

        When PRINTING_ENABLED=True:
        - Renders label with footer + QR, uploads the label preview
        """
        # Get image for upload
        caricature_bytes = self._state.ai_label_bytes or self._state.ai_display_bytes or self._state.photo_bytes

        if not caricature_bytes:
            logger.warning("No image bytes available for upload")
            return

        logger.info("Uploading photo booth image...")
        self._state.is_uploading = True

        # Set unified gallery QR code (same for everyone)
        gallery_url = "https://vnvnc.ru/gallery/photobooth"
        self._state.qr_url = gallery_url
        self._state.qr_image = generate_qr_image(gallery_url)

        if not PRINTING_ENABLED:
            # Digital-only mode: upload raw AI image (clean, no footer)
            self._uploader.upload_bytes(
                caricature_bytes,
                prefix="photobooth",
                extension="png",
                content_type="image/png",
                callback=self._on_upload_complete,
            )
        else:
            # Printing mode: render label with footer + QR
            try:
                pre_info = pre_generate_upload_info("photobooth", "png")
                logger.info(f"Pre-generated short URL: {pre_info.short_url}")

                label_gen = LabelReceiptGenerator()
                print_data = {
                    "caricature": caricature_bytes,
                    "photo": self._state.photo_bytes,
                    "qr_url": pre_info.short_url,
                    "short_url": pre_info.short_url,
                    "date": datetime.now().strftime("%d.%m.%Y"),
                }

                receipt = label_gen.generate_receipt("photobooth", print_data)
                label_png = receipt.preview_image

                if label_png:
                    self._uploader.upload_bytes(
                        label_png,
                        prefix="photobooth",
                        extension="png",
                        content_type="image/png",
                        callback=self._on_upload_complete,
                        pre_info=pre_info,
                    )
                else:
                    logger.warning("Label render failed, uploading raw image")
                    self._uploader.upload_bytes(
                        caricature_bytes,
                        prefix="photobooth",
                        extension="png",
                        content_type="image/png",
                        callback=self._on_upload_complete,
                    )
            except Exception as e:
                logger.error(f"Label render/upload failed: {e}")
                self._uploader.upload_bytes(
                    caricature_bytes,
                    prefix="photobooth",
                    extension="png",
                    content_type="image/png",
                    callback=self._on_upload_complete,
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
        if result.success:
            self._state.qr_url = result.short_url or result.url  # Prefer short URL for QR/printing
            self._state.qr_image = result.qr_image
            logger.info(f"Photo uploaded successfully: {self._state.qr_url}")
        else:
            logger.error(f"Photo upload failed: {result.error}")

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

        if self._state.show_result:
            # Show result with QR code
            self._render_result(buffer)
            return

        # Get camera background for active/countdown states
        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            np.copyto(buffer, frame)
        else:
            fill(buffer, (20, 15, 30))

        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
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

    def _render_generating(self, buffer: NDArray[np.uint8]) -> None:
        """Render Santa runner minigame while AI is generating, with captured photo as background."""
        # Render the Santa runner game with captured photo as background
        if self._santa_runner:
            self._santa_runner.render(buffer, background=self._state.photo_frame)

            # Add compact progress bar at the top
            bar_w, bar_h = 100, 4
            bar_x = (128 - bar_w) // 2
            bar_y = 2

            # Semi-transparent dark background for progress bar
            draw_rect(buffer, bar_x - 2, bar_y - 1, bar_w + 4, bar_h + 2, self.THEME_RED)

            # Use the SmartProgressTracker's render method for the progress bar
            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=self.THEME_CHROME,
                bg_color=self.THEME_BLACK,
                time_ms=self._time_in_phase
            )

            # Show compact status at bottom
            status_message = self._progress_tracker.get_message()
            # Semi-transparent dark strip for text
            draw_rect(buffer, 0, 104, 128, 24, self.THEME_BLACK)
            draw_centered_text(buffer, status_message, 106, self.THEME_CHROME, scale=1)
            # Website message
            draw_centered_text(buffer, "ФОТО БУДЕТ НА САЙТЕ", 116, self.THEME_RED, scale=1)

        else:
            # Fallback to simple generating screen if no game
            fill(buffer, self.THEME_BLACK)
            draw_centered_text(buffer, "ГЕНЕРАЦИЯ", 50, self.THEME_CHROME, scale=1)
            draw_centered_text(buffer, "ФОТО БУДЕТ НА САЙТЕ", 65, self.THEME_RED, scale=1)

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
        fill(buffer, self.THEME_BLACK)

        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            # Show countdown on ticker
            text = f"   {self._state.countdown}   "
            draw_centered_text(buffer, text, 1, self.THEME_CHROME, scale=1)
        elif self._state.is_generating:
            # Use Santa Runner's ticker progress bar (cycles continuously)
            if self._santa_runner:
                self._santa_runner.render_ticker(buffer, self._state.generation_progress, self._time_in_phase)
        elif self._state.show_result:
            if self._state.result_view == "qr":
                draw_centered_text(buffer, "QR", 1, self.THEME_CHROME, scale=1)
            else:
                draw_centered_text(buffer, "ГОТОВО", 1, self.THEME_CHROME, scale=1)
        else:
            draw_centered_text(buffer, self._theme.ticker_idle, 1, self.THEME_CHROME, scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            return f" {self._theme.lcd_prefix}: {self._state.countdown}   "[:16].ljust(16)
        elif self._state.show_result:
            return "    ГОТОВО!   "[:16]
        else:
            return "      ЖМИ     "[:16]

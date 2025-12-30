"""Photobooth Mode - AI Christmas Photo Booth with QR sharing.

Photo booth flow:
1. Button press → Countdown (3-2-1)
2. Camera flash → Take photo
3. AI generates Christmas-themed 2x2 photo booth grid
4. Show preview → Print + QR code

Uses Gemini 2.0 Flash for image generation to create festive
photo booth strips with "VNVNC 2026" Christmas branding.
"""

import logging
import io
import asyncio
from typing import Optional
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.animation.santa_runner import SantaRunner
from artifact.audio.engine import get_audio_engine

logger = logging.getLogger(__name__)


@dataclass
class PhotoboothState:
    """State for photobooth session."""
    countdown: int = 3
    countdown_timer: float = 0.0
    photo_bytes: Optional[bytes] = None  # Original captured photo
    photo_frame: Optional[NDArray[np.uint8]] = None  # Original photo for preview
    ai_result_bytes: Optional[bytes] = None  # AI-generated Christmas grid
    ai_result_frame: Optional[NDArray[np.uint8]] = None  # AI result for display
    photo_path: Optional[str] = None
    qr_url: Optional[str] = None
    qr_image: Optional[NDArray[np.uint8]] = None
    is_printing: bool = False
    is_uploading: bool = False
    is_generating: bool = False  # AI generation in progress
    flash_timer: float = 0.0
    show_result: bool = False
    result_view: str = "photo"  # "photo" or "qr"
    generation_progress: float = 0.0  # 0.0 to 1.0


class PhotoboothMode(BaseMode):
    """AI Christmas Photo Booth - generates festive photo booth grids.

    Flow:
    1. Countdown timer with visual + audio feedback
    2. Photo capture
    3. AI generates Christmas-themed 2x2 photo booth grid with VNVNC 2026 branding
    4. Upload to S3 for QR code sharing
    5. Thermal printing of the AI-generated result
    """

    name = "photobooth"
    display_name = "ФОТОЗОНА"
    description = "Новогоднее фото с AI!"
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

        # Handle jump input for Santa runner during AI generation
        if self._state.is_generating and event.type == EventType.BUTTON_PRESS:
            if self._santa_runner:
                self._santa_runner.handle_jump()
                self._audio.play_ui_click()
            return True

        if event.type not in (EventType.BUTTON_PRESS, EventType.KEYPAD_INPUT):
            return False

        # Prevent re-entry while working (from raspi-photo-booth Working flag)
        if self._working:
            return True

        if self.phase == ModePhase.ACTIVE and not self._state.show_result:
            # Start countdown
            self._working = True
            self._start_countdown()
            return True

        elif self._state.show_result:
            # Button press = take another photo
            self._state = PhotoboothState()
            self._working = False
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
                    # Countdown finished - take photo!
                    self._do_flash_and_capture()
            return

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
                        self._state.ai_result_bytes = result
                        self._state.ai_result_frame = self._decode_photo_frame(result)
                        logger.info("AI Christmas grid generation completed")
                        # Upload the AI result for QR
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

            # Initialize Santa runner minigame for the waiting screen
            self._santa_runner = SantaRunner()
            self._santa_runner.reset()

            self._ai_task = asyncio.create_task(self._generate_christmas_grid())
            logger.info("Starting AI Christmas photo booth generation")

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

    async def _generate_christmas_grid(self) -> Optional[bytes]:
        """Generate AI Christmas photo booth grid from captured photo."""
        if not self._state.photo_bytes:
            logger.error("No photo bytes for AI generation")
            return None

        try:
            logger.info("Calling CaricatureService for Christmas photo booth grid generation")

            # Generate the Christmas photo booth grid using CaricatureService
            result = await self._caricature_service.generate_caricature(
                reference_photo=self._state.photo_bytes,
                style=CaricatureStyle.PHOTOBOOTH,
            )

            if result and result.image_data:
                logger.info(f"AI generation successful, got {len(result.image_data)} bytes")
                return result.image_data
            else:
                logger.error("AI generation returned no result")
                return None

        except Exception as e:
            logger.error(f"AI Christmas grid generation failed: {e}")
            return None

    def _upload_ai_result_async(self) -> None:
        """Upload AI-generated result for QR sharing."""
        # Prefer AI result, fall back to original photo
        upload_bytes = self._state.ai_result_bytes or self._state.photo_bytes
        if not upload_bytes:
            logger.warning("No image bytes available for upload")
            return

        logger.info("Starting async AI result upload via AsyncUploader")
        self._state.is_uploading = True

        self._uploader.upload_bytes(
            upload_bytes,
            prefix="photobooth",
            extension="png" if self._state.ai_result_bytes else "jpg",
            content_type="image/png" if self._state.ai_result_bytes else "image/jpeg",
            callback=self._on_upload_complete
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
            self._state.qr_url = result.url
            self._state.qr_image = result.qr_image
            logger.info(f"Photo uploaded successfully: {self._state.qr_url}")
        else:
            logger.error(f"Photo upload failed: {result.error}")

    def _update_result(self, delta_ms: float) -> None:
        """Update result display timer."""
        self._state.countdown_timer -= delta_ms / 1000.0

        if self._state.flash_timer > 0:
            self._state.flash_timer -= delta_ms / 1000.0

        if self._state.countdown_timer <= 0:
            # Auto-return to ready state
            self._complete_session()

    def _complete_session(self) -> None:
        """Complete the session."""
        result = ModeResult(
            mode_name=self.name,
            success=True,
            data={
                "photo_path": self._state.photo_path,
                "qr_url": self._state.qr_url,
            },
            display_text="ФОТО ГОТОВО!",
            ticker_text="ФОТОБУДКА",
            should_print=self._state.photo_path is not None,
            print_data={
                "caricature": self._state.photo_bytes,
                "qr_url": self._state.qr_url,
                "qr_image": self._state.qr_image,
            }
        )
        self.complete(result)
        self._working = False

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        if self._state.flash_timer > 0:
            # Flash effect (from flashOn)
            fill(buffer, (255, 255, 255))
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
        """Render countdown number."""
        # Dim camera background
        buffer[:, :, :] = (buffer.astype(np.float32) * 0.3).astype(np.uint8)

        # Big countdown number
        num_str = str(self._state.countdown)
        draw_centered_text(buffer, num_str, 40, (255, 255, 0), scale=6)

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
            draw_rect(buffer, bar_x - 2, bar_y - 1, bar_w + 4, bar_h + 2, (20, 20, 40))

            # Use the SmartProgressTracker's render method for the progress bar
            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=(100, 255, 100),  # Christmas green
                bg_color=(40, 40, 40),
                time_ms=self._time_in_phase
            )

            # Show compact status at bottom
            status_message = self._progress_tracker.get_message()
            # Semi-transparent dark strip for text
            draw_rect(buffer, 0, 118, 128, 10, (20, 20, 40))
            draw_centered_text(buffer, status_message, 119, (200, 200, 200), scale=1)

        else:
            # Fallback to simple generating screen if no game
            fill(buffer, (15, 20, 35))
            draw_centered_text(buffer, "СОЗДАЕМ...", 55, (100, 255, 100), scale=2)

    def _render_ready(self, buffer: NDArray[np.uint8]) -> None:
        """Render ready state."""
        # Semi-transparent overlay
        overlay = buffer.copy()
        buffer[:20, :, :] = (overlay[:20, :, :].astype(np.float32) * 0.5).astype(np.uint8)
        buffer[-20:, :, :] = (overlay[-20:, :, :].astype(np.float32) * 0.5).astype(np.uint8)

        # Title and instruction
        draw_centered_text(buffer, "ФОТОБУДКА", 4, (255, 200, 100), scale=1)
        draw_centered_text(buffer, "НАЖМИ", 110, (200, 200, 200), scale=1)
        draw_centered_text(buffer, "КНОПКУ", 120, (200, 200, 200), scale=1)

    def _render_result(self, buffer: NDArray[np.uint8]) -> None:
        """Render result screen - full screen AI photo or QR."""
        if self._state.result_view == "photo":
            # Full screen AI-generated Christmas photo booth grid
            if self._state.ai_result_frame is not None:
                np.copyto(buffer, self._state.ai_result_frame)
            elif self._state.photo_frame is not None:
                # Fallback to original photo if AI failed
                np.copyto(buffer, self._state.photo_frame)
            else:
                fill(buffer, (10, 10, 20))
                draw_centered_text(buffer, "ФОТО", 55, (100, 100, 100), scale=2)

            # Small hint at bottom
            draw_centered_text(buffer, "◄ ► QR", 118, (150, 150, 150), scale=1)

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
                fill(buffer, (20, 20, 30))
                draw_centered_text(buffer, "ЗАГРУЗКА", 50, (200, 200, 100), scale=1)
                draw_centered_text(buffer, "QR...", 65, (200, 200, 100), scale=1)
            else:
                fill(buffer, (20, 20, 30))
                draw_centered_text(buffer, "QR", 50, (100, 100, 100), scale=2)
                draw_centered_text(buffer, "НЕ ГОТОВ", 75, (100, 100, 100), scale=1)

            # Hint stays on ticker/LCD for full-screen QR

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        fill(buffer, (0, 0, 0))

        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            # Show countdown on ticker
            text = f"   {self._state.countdown}   "
            draw_centered_text(buffer, text, 1, (255, 255, 0), scale=1)
        elif self._state.is_generating:
            # Show generation progress on ticker
            pct = int(self._state.generation_progress * 100)
            draw_centered_text(buffer, f"AI {pct}%", 1, (255, 100, 100), scale=1)
        elif self._state.show_result:
            if self._state.result_view == "qr":
                draw_centered_text(buffer, "QR", 1, (100, 255, 100), scale=1)
            else:
                draw_centered_text(buffer, "ГОТОВО", 1, (100, 255, 100), scale=1)
        else:
            draw_centered_text(buffer, "ФОТО", 1, (255, 150, 50), scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self.phase == ModePhase.PROCESSING and self._state.countdown > 0:
            return f" ОТСЧЕТ: {self._state.countdown} "[:16].ljust(16)
        elif self._state.show_result:
            return "    ГОТОВО    "[:16]
        else:
            return "   ФОТОБУДКА   "[:16]

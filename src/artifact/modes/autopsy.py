"""Autopsy Mode - Medical X-ray style dissection.

The AI analyzes user "anatomy" and generates a medical report + X-ray illustration.
Style: Clinical, green/black, medical scan animations.
"""

import asyncio
import logging
from typing import Optional, Tuple
from datetime import datetime
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.utils.camera import create_viewfinder_overlay
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult, pre_generate_upload_info, generate_qr_image
import numpy as np

logger = logging.getLogger(__name__)


class AutopsyPhase:
    INTRO = "intro"
    SCAN_PREP = "scan_prep"   # "Stand still for scan"
    SCANNING = "scanning"     # Moving bar animation over camera feed
    PROCESSING = "processing" # "Analysing organs..."
    RESULT = "result"


# =============================================================================
# AI PROMPTS
# =============================================================================

AUTOPSY_SYSTEM_PROMPT = """Ты - медицинский ИИ-диагност в киберпанк-клинике.
Твоя задача - провести шуточный "анализ организма" по фото.

Придумай смешные, абсурдные диагнозы или особенности строения тела.
Примеры:
- "Обнаружен избыток кофеина в крови (99%). Сердце работает на чистом энтузиазме."
- "В мозгу найден чип 5G. Связь с космосом стабильная."
- "Скелет состоит из адамантия. Рекомендуется смазка суставов WD-40."

Format:
DIAGNOSIS: [Твой весёлый диагноз]
ID_CODE: [Случайный код, типа SUBJ-8392]
"""

class AutopsyMode(BaseMode):
    """Medical Dissection Mode."""

    name = "autopsy"
    display_name = "ВСКРЫТИЕ"
    description = "Медицинский скан"
    icon = "+"
    style = "medical"
    requires_camera = True
    requires_ai = True
    estimated_duration = 55

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._gemini_client = get_gemini_client()
        self._caricature_service = CaricatureService()
        self._sub_phase = AutopsyPhase.INTRO
        
        # Camera
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None
        self._photo_data: Optional[bytes] = None
        
        # Data
        self._diagnosis: str = ""
        self._id_code: str = ""
        self._xray_image: Optional[Caricature] = None
        
        # Animation
        self._scan_line_y: float = 0.0
        self._processing_text: str = "INIT SYSTEM..."
        self._ai_task: Optional[asyncio.Task] = None

        # Progress tracker for AI processing
        self._progress_tracker = SmartProgressTracker(mode_theme="autopsy")

        # Result view state
        self._result_view: str = "text"  # "text" or "image"
        self._text_scroll_complete: bool = False
        self._text_view_time: float = 0.0
        self._scroll_duration: float = 0.0

        # Colors
        self._green = (0, 255, 50)
        self._dark_green = (0, 50, 10)

        # S3 upload for QR sharing
        self._uploader = AsyncUploader()
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None
        self._short_url: Optional[str] = None

    @property
    def is_ai_available(self) -> bool:
        return self._gemini_client.is_available

    def on_enter(self) -> None:
        self._sub_phase = AutopsyPhase.INTRO
        self._photo_data = None
        self._diagnosis = ""
        self._id_code = "UNKNOWN"
        self._xray_image = None
        self._scan_line_y = 0.0
        self._result_view = "text"
        self._text_scroll_complete = False
        self._text_view_time = 0.0
        self._scroll_duration = 0.0

        # Reset QR state
        self._qr_url = None
        self._qr_image = None
        self._short_url = None

        # Reset progress tracker
        self._progress_tracker.reset()

        # Use shared camera service (always running)
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera service ready for Autopsy")

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        if self._sub_phase in (AutopsyPhase.SCAN_PREP, AutopsyPhase.SCANNING):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            if self._time_in_phase > 2000:
                self._sub_phase = AutopsyPhase.SCAN_PREP
                self.change_phase(ModePhase.ACTIVE)
                self._time_in_phase = 0

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == AutopsyPhase.SCAN_PREP:
                if self._time_in_phase > 2000:
                    self._start_scan()

            elif self._sub_phase == AutopsyPhase.SCANNING:
                # Animate scan line
                self._scan_line_y = (self._time_in_phase / 3000) * 128
                if self._time_in_phase > 3000:
                    self._do_capture()
                    self._start_processing()

        elif self.phase == ModePhase.PROCESSING:
            if int(self._time_in_phase / 500) % 2 == 0:
                self._processing_text = "ANALYZING..."
            else:
                self._processing_text = "PROCESSING..."

            if self._ai_task and self._ai_task.done():
                self._on_ai_complete()

        elif self.phase == ModePhase.RESULT:
            # Calculate scroll duration on first entry
            if self._diagnosis and self._scroll_duration == 0:
                from artifact.graphics.text_utils import calculate_scroll_duration, MAIN_DISPLAY_WIDTH
                from artifact.graphics.fonts import load_font
                font = load_font("cyrillic")
                rect = (4, 28, MAIN_DISPLAY_WIDTH - 8, 72)
                self._scroll_duration = calculate_scroll_duration(
                    self._diagnosis, rect, font, scale=1, line_spacing=2, scroll_interval_ms=1600
                )
                self._scroll_duration = max(3000, self._scroll_duration + 2000)

            # Track time in text view
            if self._result_view == "text":
                self._text_view_time += delta_ms
                if not self._text_scroll_complete and self._text_view_time >= self._scroll_duration:
                    self._text_scroll_complete = True
                    if self._xray_image:
                        self._result_view = "image"

            if self._time_in_phase > 45000:
                self._finish()

    def on_input(self, event: Event) -> bool:
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT:
                if self._result_view == "image" or not self._xray_image:
                    self._finish()
                    return True
                else:
                    if self._xray_image:
                        self._result_view = "image"
                        self._text_scroll_complete = True
                    else:
                        self._finish()
                    return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.RESULT:
                self._result_view = "text"
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.RESULT and self._xray_image:
                self._result_view = "image"
                return True

        return False

    def _start_scan(self) -> None:
        self._sub_phase = AutopsyPhase.SCANNING
        self._time_in_phase = 0
        logger.info("Scanning started")

    def _do_capture(self) -> None:
        """Capture photo for AI analysis from shared camera service."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            logger.info("Scan capture complete")

    def _update_camera_preview(self) -> None:
        """Update camera preview - clean B&W grayscale (no dithering)."""
        try:
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.size > 0:
                # Simple B&W grayscale conversion - cleaner than dithering
                if len(frame.shape) == 3:
                    gray = (0.299 * frame[:, :, 0] + 0.587 * frame[:, :, 1] + 0.114 * frame[:, :, 2]).astype(np.uint8)
                else:
                    gray = frame
                # Resize if needed
                if gray.shape != (128, 128):
                    from PIL import Image
                    img = Image.fromarray(gray)
                    img = img.resize((128, 128), Image.Resampling.BILINEAR)
                    gray = np.array(img, dtype=np.uint8)
                # Convert to RGB (grayscale in all 3 channels)
                self._camera_frame = np.stack([gray, gray, gray], axis=-1)
                self._camera = True
        except Exception:
            pass

    def _start_processing(self) -> None:
        self._sub_phase = AutopsyPhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)

        # Start progress tracker
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        self._ai_task = asyncio.create_task(self._run_ai())

    async def _run_ai(self) -> None:
        try:
            if not self._photo_data:
                self._diagnosis = "ERROR: SUBJECT NOT FOUND"
                return

            async def get_text():
                res = await self._gemini_client.generate_with_image(
                    prompt="Medical scan analysis. Be funny and sci-fi.",
                    image_data=self._photo_data,
                    model=GeminiModel.FLASH_VISION,
                    system_instruction=AUTOPSY_SYSTEM_PROMPT
                )
                return self._parse_response(res) if res else ("Unknown Organism", "ERR-404")

            async def get_image():
                return await self._caricature_service.generate_caricature(
                    reference_photo=self._photo_data,
                    style=CaricatureStyle.MEDICAL,
                    personality_context="X-ray medical scan"
                )

            # Advance to text generation
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)
            self._diagnosis, self._id_code = await get_text()

            # Advance to image generation
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)
            self._xray_image = await get_image()

            # Upload rendered LABEL (not just xray) for QR sharing - like photobooth
            if self._xray_image and self._xray_image.image_data:
                logger.info("Starting autopsy label upload for QR sharing")
                # Pre-generate URL NOW so it's available for printing
                pre_info = pre_generate_upload_info("autopsy", "png")
                self._qr_url = pre_info.short_url
                self._qr_image = generate_qr_image(pre_info.short_url)
                self._short_url = pre_info.short_url
                logger.info(f"Pre-generated QR URL for autopsy: {self._qr_url}")

                # Generate the full label preview (like photobooth does)
                from artifact.printing.label_receipt import LabelReceiptGenerator
                label_gen = LabelReceiptGenerator()
                temp_print_data = {
                    "type": "autopsy",
                    "diagnosis": self._diagnosis,
                    "id": self._id_code,
                    "scan_image": self._xray_image.image_data,
                    "qr_url": pre_info.short_url,
                    "short_url": pre_info.short_url,
                    "timestamp": datetime.now().isoformat()
                }
                receipt = label_gen.generate_receipt("autopsy", temp_print_data)
                label_png = receipt.preview_image if receipt else None

                # Upload rendered label (or fallback to xray)
                upload_data = label_png if label_png else self._xray_image.image_data
                self._uploader.upload_bytes(
                    upload_data,
                    prefix="autopsy",
                    extension="png",
                    content_type="image/png",
                    callback=self._on_upload_complete,
                    pre_info=pre_info,
                )

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)

        except Exception as e:
            logger.error(f"AI Failure: {e}")
            self._diagnosis = "SYSTEM FAILURE"

    def _parse_response(self, text: str) -> Tuple[str, str]:
        diag = ""
        code = "SUBJ-001"
        for line in text.strip().split("\n"):
            if line.startswith("DIAGNOSIS:"): diag = line[10:].strip()
            elif line.startswith("ID_CODE:"): code = line[8:].strip()
        if not diag: diag = text[:100]
        return diag, code

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle completion of S3 upload for QR sharing."""
        if result.success:
            self._qr_url = result.short_url or result.url  # Prefer short URL for QR/printing
            self._qr_image = result.qr_image
            self._short_url = result.short_url
            logger.info(f"Autopsy xray uploaded: {self._qr_url}")
        else:
            logger.error(f"Autopsy xray upload failed: {result.error}")

    def _on_ai_complete(self) -> None:
        # Complete progress tracker
        self._progress_tracker.complete()

        self._sub_phase = AutopsyPhase.RESULT
        self.change_phase(ModePhase.RESULT)

    def on_exit(self) -> None:
        """Cleanup - don't stop shared camera service."""
        self._camera = None
        self._camera_frame = None
        if self._ai_task:
            self._ai_task.cancel()

    def _finish(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=self._diagnosis,
            ticker_text=f"SUBJECT: {self._id_code}",
            lcd_text=" SCAN COMPLETE ".center(16),
            should_print=True,
            print_data={
                "type": "autopsy",
                "diagnosis": self._diagnosis,
                "id": self._id_code,
                "scan_image": self._xray_image.image_data if self._xray_image else None,
                "timestamp": datetime.now().isoformat(),
                "qr_url": self._qr_url,
                "qr_image": self._qr_image,
                "short_url": self._short_url
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        from artifact.graphics.primitives import fill, draw_line, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, wrap_text, render_scrolling_text_area

        # Background - dark medical green
        fill(buffer, (0, 20, 5))

        # Grid lines
        for i in range(0, 128, 16):
            draw_line(buffer, 0, i, 128, i, (0, 50, 20))
            draw_line(buffer, i, 0, i, 128, (0, 50, 20))

        if self._sub_phase == AutopsyPhase.INTRO:
            draw_centered_text(buffer, "MEDICAL SCAN", 50, self._green, scale=1)
            draw_centered_text(buffer, "INITIALIZING...", 70, self._green)

        elif self._sub_phase in (AutopsyPhase.SCAN_PREP, AutopsyPhase.SCANNING):
            if self._camera_frame is not None:
                # Render frame with green tint
                import numpy as np
                # Check shape
                if self._camera_frame.shape == (128, 128, 3):
                    # Manual tint copy
                    # For performance in sim, maybe just direct copy and trust simulator dither
                    np.copyto(buffer, self._camera_frame)
            
            # Scan line overlay
            if self._sub_phase == AutopsyPhase.SCANNING:
                y = int(self._scan_line_y)
                draw_line(buffer, 0, y, 128, y, self._green)
                # Glow area
                for i in range(1, 5):
                     if 0 <= y-i < 128: draw_line(buffer, 0, y-i, 128, y-i, (0, 100, 20))

        elif self._sub_phase == AutopsyPhase.PROCESSING:
            # Update progress tracker
            self._progress_tracker.update(delta_ms=16)

            # Render medical-themed loading animation
            self._progress_tracker.render_loading_animation(
                buffer, style="tech", time_ms=self._time_in_phase
            )

            # Status message
            status_message = self._progress_tracker.get_message()
            draw_centered_text(buffer, status_message, 78, self._green, scale=1)

            # Progress bar
            bar_x, bar_y, bar_w, bar_h = 14, 92, 100, 10
            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=self._green,
                bg_color=(0, 30, 10),
                border_color=(0, 100, 30)
            )

        elif self._sub_phase == AutopsyPhase.RESULT:
            if self._result_view == "image" and self._xray_image and self._xray_image.image_data:
                # Image view - show X-ray
                try:
                    from PIL import Image
                    from io import BytesIO
                    import numpy as np

                    img = Image.open(BytesIO(self._xray_image.image_data))
                    img = img.convert("RGB")
                    img = img.resize((120, 100), Image.Resampling.LANCZOS)
                    img_array = np.array(img)
                    buffer[5:105, 4:124] = img_array

                    # Hint at bottom
                    if int(self._time_in_phase / 500) % 2 == 0:
                        draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 112, (100, 200, 100), scale=1)
                    else:
                        draw_centered_text(buffer, "◄ ТЕКСТ", 112, (100, 100, 120), scale=1)
                except Exception as e:
                    self._result_view = "text"
            else:
                # Text view - diagnosis
                draw_centered_text(buffer, self._id_code, 10, self._green)
                render_scrolling_text_area(
                    buffer,
                    self._diagnosis,
                    (4, 28, 120, 72),
                    (200, 255, 200),
                    self._text_view_time,  # Use text_view_time for scrolling
                    scale=1,
                    line_spacing=2,
                    scroll_interval_ms=1600,
                )

                # Hint at bottom
                if self._xray_image:
                    if int(self._time_in_phase / 600) % 2 == 0:
                        draw_centered_text(buffer, "СНИМОК ►", 110, (100, 150, 200), scale=1)
                    else:
                        draw_centered_text(buffer, "НАЖМИ", 110, (100, 100, 120), scale=1)
                else:
                    if int(self._time_in_phase / 600) % 2 == 0:
                        draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 110, (100, 200, 100), scale=1)

    def render_ticker(self, buffer) -> None:
        """Render ticker display with phase-specific messages."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import draw_centered_text

        clear(buffer)  # Always clear to prevent rainbow persistence

        if self._sub_phase == AutopsyPhase.INTRO:
            draw_centered_text(buffer, "ВСКРЫТИЕ", 2, self._green)
        elif self._sub_phase == AutopsyPhase.SCAN_PREP:
            draw_centered_text(buffer, "СКАН", 2, self._green)
        elif self._sub_phase == AutopsyPhase.SCANNING:
            pct = int((self._scan_line_y / 128) * 100)
            draw_centered_text(buffer, f"СКАН {pct}%", 2, self._green)
        elif self._sub_phase == AutopsyPhase.PROCESSING:
            dots = "." * (int(self._time_in_phase / 400) % 4)
            draw_centered_text(buffer, f"АНАЛИЗ{dots}", 2, self._green)
        elif self._sub_phase == AutopsyPhase.RESULT:
            draw_centered_text(buffer, self._id_code[:8], 2, self._green)

    def get_lcd_text(self) -> str:
        """Return LCD text based on current phase."""
        if self._sub_phase == AutopsyPhase.INTRO:
            return "  MED SCAN INIT "
        elif self._sub_phase == AutopsyPhase.SCAN_PREP:
            return "   STAND STILL  "
        elif self._sub_phase == AutopsyPhase.SCANNING:
            pct = int((self._scan_line_y / 128) * 100)
            return f" SCANNING {pct:3d}% ".center(16)
        elif self._sub_phase == AutopsyPhase.PROCESSING:
            pct = int((self._time_in_phase / 8000) * 100)
            pct = min(99, pct)
            return f" ANALYZING {pct:2d}% ".center(16)
        elif self._sub_phase == AutopsyPhase.RESULT:
            return " SCAN COMPLETE  "
        return "    AUTOPSY     "

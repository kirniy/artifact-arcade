"""Roast Me Mode - AI generates a funny roast + doodle.

The AI analyzes the user's photo to generate a lighthearted "roast" 
and a messy doodle caricature.
Style: Graffiti, chaotic, fun.
"""

import asyncio
import logging
from typing import Optional, Tuple, List
from datetime import datetime
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.animation.santa_runner import SantaRunner
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.utils.camera import create_viewfinder_overlay
from artifact.utils.camera_service import camera_service
from artifact.utils.s3_upload import AsyncUploader, UploadResult, pre_generate_upload_info, generate_qr_image
from artifact.audio.engine import get_audio_engine

import numpy as np

logger = logging.getLogger(__name__)


class RoastPhase:
    INTRO = "intro"
    CAMERA_PREP = "camera_prep"
    CAMERA_CAPTURE = "capture"
    PROCESSING = "processing"
    REVEAL = "reveal"
    RESULT = "result"


# =============================================================================
# AI PROMPTS
# =============================================================================

ROAST_SYSTEM_PROMPT = """Ты - безбашенный комик с Roast Battle для ВЗРОСЛЫХ (18+). Без цензуры, без жалости!

ТВОЯ МИССИЯ: Выдать ЖЁСТКУЮ но СМЕШНУЮ прожарку. Это взрослое шоу, а не детский утренник!

ПРАВИЛА ПРОЖАРКИ (18+):
- Будь ЖЁСТКИМ, дерзким, без цензуры - как пьяный друг в баре
- Цепляйся за ВСЕ: лицо, тело, одежду, позу, вайб, энергию
- Матерись сколько хочешь! Но НЕ начинай каждый раз с "Бля" - это банально
- НЕ СДЕРЖИВАЙСЯ - человек СОЗНАТЕЛЬНО пришёл на прожарку!
- Цель - РАССМЕШИТЬ. Жёстко но с любовью.

ВАЖНО О СТИЛЕ:
- НИКОГДА не начинай с "Бля" или "Братан" - придумай что-то новое
- Каждая прожарка должна начинаться ПО-РАЗНОМУ
- Будь КРЕАТИВНЫМ в структуре предложений
- Пиши уникально для ЭТОГО человека

ФОРМАТ ОТВЕТА (СТРОГО!):
ROAST: [2-3 предложения прожарки. МАКСИМУМ 180-200 символов! Уникальный стиль!]
VIBE: [Прозвище 2-3 слова - дерзкое, смешное, УНИКАЛЬНОЕ для этого человека]
ICON: [Одно слово: fire/star/crown/skull/ghost/robot/brain/gamepad/bolt/gem/trophy]

КРИТИЧЕСКИ ВАЖНО:
- Лимит 180-200 символов на прожарку!
- Каждый ответ должен быть УНИКАЛЬНЫМ
- НЕ используй одинаковые начала предложений
- Прозвище придумай СПЕЦИАЛЬНО для этого лица
"""

class RoastMeMode(BaseMode):
    """Roast Me Mode."""

    name = "roast"
    display_name = "ПРОЖАРКА"
    description = "Смешной разбор"
    icon = "!"
    style = "roast"
    requires_camera = True
    requires_ai = True
    estimated_duration = 50

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._gemini_client = get_gemini_client()
        self._caricature_service = CaricatureService()
        self._sub_phase = RoastPhase.INTRO
        
        # Camera
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._flash_alpha: float = 0.0
        
        # Data
        self._roast_text: str = ""
        self._vibe_score: str = ""  # Creative role/title like "Главный клоун вечеринки"
        self._vibe_icon: str = "star"  # Icon name for the role
        self._doodle_image: Optional[Caricature] = None
        
        # Animations
        self._particles = ParticleSystem()
        self._shake_amount: float = 0.0
        self._ai_task: Optional[asyncio.Task] = None
        self._processing_progress: float = 0.0
        self._progress_tracker = SmartProgressTracker(mode_theme="roast")

        # Display mode for result screen (0 = image full screen, 1 = text)
        self._display_mode: int = 1  # Start with text view

        # Text pagination (no scrolling!)
        self._text_pages: List[List[str]] = []
        self._text_page_index: int = 0

        # Colors
        self._red = (255, 50, 50)
        self._yellow = (255, 200, 0)

        # Audio engine
        self._audio = get_audio_engine()
        self._last_countdown_tick: int = 0

        # S3 upload for QR sharing
        self._uploader = AsyncUploader()
        self._qr_url: Optional[str] = None
        self._qr_image: Optional[np.ndarray] = None

        # Santa runner minigame for processing screen
        self._santa_runner: Optional[SantaRunner] = None

    @property
    def is_ai_available(self) -> bool:
        return self._gemini_client.is_available

    def on_enter(self) -> None:
        self._sub_phase = RoastPhase.INTRO
        self._photo_data = None
        self._roast_text = ""
        self._vibe_score = ""
        self._vibe_icon = "star"
        self._doodle_image = None
        self._shake_amount = 0.0
        self._flash_alpha = 0.0
        self._display_mode = 1  # Start with text view
        self._text_pages = []
        self._text_page_index = 0
        self._progress_tracker.reset()

        # Reset QR upload state
        self._qr_url = None
        self._qr_image = None

        # Use shared camera service (always running)
        self._camera = camera_service.is_running
        if self._camera:
            logger.info("Camera service ready for Roast")

        fire = ParticlePresets.fire(x=64, y=120)
        fire.color = self._red
        self._particles.add_emitter("fire", fire)

        self.change_phase(ModePhase.INTRO)

    def on_update(self, delta_ms: float) -> None:
        self._particles.update(delta_ms)
        self._shake_amount = max(0, self._shake_amount - delta_ms/200)

        if self._sub_phase in (RoastPhase.CAMERA_PREP, RoastPhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            if self._time_in_phase > 2000:
                self._sub_phase = RoastPhase.CAMERA_PREP
                self.change_phase(ModePhase.ACTIVE)
                self._time_in_phase = 0

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == RoastPhase.CAMERA_PREP:
                if self._time_in_phase > 2000:
                    self._start_capture()
            
            elif self._sub_phase == RoastPhase.CAMERA_CAPTURE:
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                # Countdown tick sounds
                current_tick = int(self._camera_countdown) + 1
                if current_tick != self._last_countdown_tick and current_tick >= 1 and current_tick <= 3:
                    self._audio.play_countdown_tick()
                    self._last_countdown_tick = current_tick

                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_capture()
                    self._audio.play_camera_shutter()

                if self._time_in_phase > 3500:
                    self._start_processing()

        elif self.phase == ModePhase.PROCESSING:
            # Update smart progress tracker
            self._progress_tracker.update(delta_ms)

            # Update Santa runner minigame
            if self._santa_runner:
                self._santa_runner.update(delta_ms)

            if self._ai_task and self._ai_task.done():
                self._on_ai_complete()
            else:
                # Use smart progress tracker for visual feedback
                self._processing_progress = self._progress_tracker.get_progress()

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == RoastPhase.REVEAL:
                if self._time_in_phase > 2000:
                    self._shake_amount = 5.0 # Impact!
                    self._sub_phase = RoastPhase.RESULT
                    self._time_in_phase = 0
                    # Pre-paginate roast text (no scrolling!)
                    if self._roast_text and not self._text_pages:
                        from artifact.graphics.text_utils import smart_wrap_text, MAIN_DISPLAY_WIDTH
                        lines = smart_wrap_text(self._roast_text, MAIN_DISPLAY_WIDTH - 8, font=None, scale=1)
                        lines_per_page = 10  # More lines for fullscreen
                        self._text_pages = []
                        for i in range(0, len(lines), lines_per_page):
                            self._text_pages.append(lines[i:i + lines_per_page])
                        if not self._text_pages:
                            self._text_pages = [["..."]]
                        self._text_page_index = 0
            elif self._sub_phase == RoastPhase.RESULT:
                if self._time_in_phase > 45000:
                    self._finish()

    def on_input(self, event: Event) -> bool:
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.PROCESSING:
                # Play Santa runner minigame while waiting - JUMP!
                if self._santa_runner:
                    self._santa_runner.handle_jump()
                    self._audio.play_ui_click()
                return True
            if self.phase == ModePhase.RESULT and self._sub_phase == RoastPhase.RESULT:
                self._finish()
                return True

        elif event.type in (EventType.ARCADE_LEFT, EventType.ARCADE_RIGHT):
            if self.phase == ModePhase.PROCESSING:
                # Shoot in Santa runner during processing
                if self._santa_runner:
                    if self._santa_runner.handle_shoot():
                        self._audio.play_ui_click()
                return True

        if event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.RESULT and self._sub_phase == RoastPhase.RESULT:
                self._audio.play_ui_move()
                # Navigate pages first, then views
                if self._display_mode == 1 and len(self._text_pages) > 1 and self._text_page_index > 0:
                    self._text_page_index -= 1
                else:
                    self._cycle_display_mode(-1)
                    if self._display_mode == 1:
                        self._text_page_index = len(self._text_pages) - 1 if self._text_pages else 0
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.RESULT and self._sub_phase == RoastPhase.RESULT:
                self._audio.play_ui_move()
                # Navigate pages first, then views
                if self._display_mode == 1 and len(self._text_pages) > 1 and self._text_page_index < len(self._text_pages) - 1:
                    self._text_page_index += 1
                else:
                    self._cycle_display_mode(1)
                    if self._display_mode == 1:
                        self._text_page_index = 0
                return True

        return False

    def _start_capture(self) -> None:
        self._sub_phase = RoastPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0

    def _do_capture(self) -> None:
        """Capture photo for AI analysis from shared camera service."""
        self._photo_data = camera_service.capture_jpeg(quality=90)
        if self._photo_data:
            self._flash_alpha = 1.0
            
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
                bw_frame = np.stack([gray, gray, gray], axis=-1)
                self._camera_frame = create_viewfinder_overlay(bw_frame, self._time_in_phase).copy()
                self._camera = True
        except Exception:
            pass

    def _get_display_modes(self):
        modes = [1]  # text
        if self._doodle_image:
            modes.append(0)  # image
            if self._qr_image is not None or self._uploader.is_uploading:
                modes.append(2)  # qr
        return modes

    def _cycle_display_mode(self, direction: int) -> None:
        modes = self._get_display_modes()
        if not modes:
            return
        try:
            idx = modes.index(self._display_mode)
        except ValueError:
            idx = 0
        self._display_mode = modes[(idx + direction) % len(modes)]

    def _display_nav_hint(self) -> Optional[str]:
        modes = self._get_display_modes()
        if len(modes) < 2:
            return None
        try:
            idx = modes.index(self._display_mode)
        except ValueError:
            idx = 0
        labels = {1: "ТЕКСТ", 0: "ФОТО", 2: "QR"}
        left_view = modes[(idx - 1) % len(modes)]
        right_view = modes[(idx + 1) % len(modes)]
        return f"◄ {labels[left_view]}  ► {labels[right_view]}"

    def _render_qr_view(self, buffer) -> None:
        """Render full-screen QR view."""
        from artifact.graphics.primitives import fill
        from artifact.graphics.text_utils import draw_centered_text

        fill(buffer, (255, 255, 255))

        if self._qr_image is not None:
            qr_h, qr_w = self._qr_image.shape[:2]
            target_size = 120
            if qr_h != target_size or qr_w != target_size:
                from PIL import Image
                qr_img = Image.fromarray(self._qr_image)
                qr_img = qr_img.resize((target_size, target_size), Image.Resampling.NEAREST)
                qr_scaled = np.array(qr_img, dtype=np.uint8)
            else:
                qr_scaled = self._qr_image

            qr_h, qr_w = qr_scaled.shape[:2]
            x_offset = (128 - qr_w) // 2
            y_offset = (128 - qr_h) // 2
            buffer[y_offset:y_offset + qr_h, x_offset:x_offset + qr_w] = qr_scaled
        elif self._uploader.is_uploading:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "ЗАГРУЗКА", 50, (200, 200, 100), scale=1)
            draw_centered_text(buffer, "QR...", 65, (200, 200, 100), scale=1)
        else:
            fill(buffer, (20, 20, 30))
            draw_centered_text(buffer, "QR", 50, (100, 100, 100), scale=2)
            draw_centered_text(buffer, "НЕ ГОТОВ", 75, (100, 100, 100), scale=1)

        # Hint stays on ticker/LCD for full-screen QR

    def _start_processing(self) -> None:
        self._sub_phase = RoastPhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)

        # Start smart progress tracker
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

        # Initialize Santa runner minigame for the waiting screen
        self._santa_runner = SantaRunner()
        self._santa_runner.reset()

        self._ai_task = asyncio.create_task(self._run_ai())

        e = self._particles.get_emitter("fire")
        if e: e.burst(50)

    async def _run_ai(self) -> None:
        try:
            if not self._photo_data:
                self._roast_text = "Слишком страшный для фото..."
                return

            async def get_text():
                res = await self._gemini_client.generate_with_image(
                    prompt="Прожарь этого человека по полной! Смотри на фото и выдай огненный roast!",
                    image_data=self._photo_data,
                    model=GeminiModel.FLASH_VISION,
                    system_instruction=ROAST_SYSTEM_PROMPT
                )
                logger.info(f"Roast AI response: {res[:200] if res else 'None'}...")
                if res:
                    return self._parse_response(res)
                else:
                    logger.error("Roast AI returned empty response!")
                    return ("ИИ не смог тебя прожарить - видимо, ты слишком идеален. Или камера сломалась.", "Загадочная личность", "star")

            async def get_image():
                logger.info("Starting caricature generation for roast...")
                result = await self._caricature_service.generate_caricature(
                    reference_photo=self._photo_data,
                    style=CaricatureStyle.ROAST,
                    personality_context="Mean roast doodle"
                )
                if result:
                    logger.info(f"Caricature generated: {len(result.image_data)} bytes")
                else:
                    logger.warning("Caricature generation returned None")
                return result

            # Advance to text generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_TEXT)
            self._roast_text, self._vibe_score, self._vibe_icon = await get_text()

            # Advance to image generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)
            self._doodle_image = await get_image()

            # Upload rendered LABEL (not just doodle) for QR sharing - like photobooth
            if self._doodle_image and self._doodle_image.image_data:
                logger.info("Starting label upload for QR sharing")
                # Pre-generate URL NOW so it's available for printing
                pre_info = pre_generate_upload_info("roast", "png")
                self._qr_url = pre_info.short_url
                self._qr_image = generate_qr_image(pre_info.short_url)
                logger.info(f"Pre-generated QR URL for roast: {self._qr_url}")

                # Generate the full label preview (like photobooth does)
                from artifact.printing.label_receipt import LabelReceiptGenerator
                label_gen = LabelReceiptGenerator()
                temp_print_data = {
                    "type": "roast",
                    "roast": self._roast_text,
                    "vibe": self._vibe_score,
                    "vibe_icon": self._vibe_icon,
                    "doodle": self._doodle_image.image_data,
                    "qr_url": pre_info.short_url,
                    "short_url": pre_info.short_url,
                    "photo": self._photo_data,
                    "timestamp": datetime.now().isoformat()
                }
                receipt = label_gen.generate_receipt("roast", temp_print_data)
                label_png = receipt.preview_image if receipt else None

                # Upload rendered label (or fallback to doodle)
                upload_data = label_png if label_png else self._doodle_image.image_data
                self._uploader.upload_bytes(
                    upload_data,
                    prefix="roast",
                    extension="png",
                    content_type="image/png",
                    callback=self._on_upload_complete,
                    pre_info=pre_info,
                )

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)
            logger.info(f"Roast complete - text: '{self._roast_text[:50]}...', vibe: {self._vibe_score}, has_image: {self._doodle_image is not None}")

        except Exception as e:
            logger.error(f"AI Failure: {e}")
            self._roast_text = "Ты сломал мой ИИ своей красотой."

    def _parse_response(self, text: str) -> Tuple[str, str, str]:
        """Parse AI response, handling multi-line ROAST content.

        Returns: (roast_text, vibe_role, icon_name)
        """
        roast_lines = []
        vibe = "ЗАГАДОЧНАЯ ЛИЧНОСТЬ"
        icon = "star"  # Default icon
        in_roast = False

        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("ROAST:"):
                in_roast = True
                content = line[6:].strip()
                if content:
                    roast_lines.append(content)
            elif line.upper().startswith("VIBE:"):
                in_roast = False
                vibe = line[5:].strip()
                # Remove quotes if present
                vibe = vibe.strip('"\'')
                # Force uppercase (fixes AI capitalizing every word in Russian)
                vibe = vibe.upper()
            elif line.upper().startswith("ICON:"):
                in_roast = False
                icon_raw = line[5:].strip().lower()
                # Validate icon is in our list
                valid_icons = {"fire", "star", "crown", "skull", "ghost", "robot", "brain",
                              "gamepad", "music", "gift", "bolt", "gem", "heart", "eye", "trophy"}
                if icon_raw in valid_icons:
                    icon = icon_raw
            elif in_roast and line:
                # Continue collecting roast text
                roast_lines.append(line)

        roast = " ".join(roast_lines).strip()

        # If no structured response, use the whole text
        if not roast:
            # Clean up any markdown or extra formatting
            clean_text = text.replace("**", "").replace("*", "").strip()
            roast = clean_text[:300] if len(clean_text) > 300 else clean_text

        logger.info(f"Parsed roast: {roast[:100]}... vibe: {vibe}, icon: {icon}")
        return roast, vibe, icon

    def _on_upload_complete(self, result: UploadResult) -> None:
        """Handle completion of S3 upload for QR sharing."""
        if result.success:
            self._qr_url = result.short_url or result.url  # Prefer short URL for QR/printing
            self._qr_image = result.qr_image
            logger.info(f"Roast doodle uploaded successfully: {self._qr_url}")
        else:
            logger.error(f"Roast doodle upload failed: {result.error}")

    def _on_ai_complete(self) -> None:
        self._progress_tracker.complete()
        self._audio.play_success()
        logger.info("AI complete, finishing mode - manager handles result display")
        # Skip mode's result phase - manager's result view is cleaner
        self._finish()

    def on_exit(self) -> None:
        """Cleanup - don't stop shared camera service."""
        self._camera = None
        self._camera_frame = None
        if self._ai_task:
            self._ai_task.cancel()
        self._particles.clear_all()

    def _finish(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=self._roast_text,
            ticker_text=f"ВАЙБ: {self._vibe_score}",
            lcd_text=" ПРОЖАРКА ".center(16),
            should_print=True,
            print_data={
                "type": "roast",
                "roast": self._roast_text,
                "vibe": self._vibe_score,
                "vibe_icon": self._vibe_icon,
                "doodle": self._doodle_image.image_data if self._doodle_image else None,
                "qr_url": self._qr_url,
                "short_url": self._qr_url,  # Explicitly pass for footer display
                "qr_image": self._qr_image,
                "photo": self._photo_data,
                "timestamp": datetime.now().isoformat()
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        from artifact.graphics.primitives import fill, draw_rect
        from artifact.graphics.text_utils import (
            draw_centered_text, draw_animated_text, TextEffect,
            smart_wrap_text, MAIN_DISPLAY_WIDTH
        )

        shake_x = int(random.uniform(-1, 1) * self._shake_amount * 2)
        shake_y = int(random.uniform(-1, 1) * self._shake_amount * 2)

        fill(buffer, (10, 5, 5)) # Dark background

        if self._sub_phase == RoastPhase.INTRO:
            draw_animated_text(buffer, "ПРОЖАРКА", 64, self._red, self._time_in_phase, TextEffect.GLITCH, scale=2)

        elif self._sub_phase in (RoastPhase.CAMERA_PREP, RoastPhase.CAMERA_CAPTURE):
            # SIMPLE APPROACH (copied from photobooth - WORKS!)
            # Get camera frame and copy directly to buffer
            frame = camera_service.get_frame(timeout=0)
            if frame is not None and frame.shape[:2] == (128, 128):
                np.copyto(buffer, frame)
            else:
                # Fallback when no camera
                fill(buffer, (30, 15, 15))  # Dark red background
                draw_centered_text(buffer, "ПРОЖАРКА", 50, self._red, scale=2)
                draw_centered_text(buffer, "КАМЕРА", 75, self._yellow, scale=1)

            if self._sub_phase == RoastPhase.CAMERA_CAPTURE and self._camera_countdown > 0:
                # Dim camera background with red tint (like photobooth does with green)
                buffer[:, :, :] = (buffer.astype(np.float32) * 0.3).astype(np.uint8)
                buffer[:, :, 0] = np.minimum(buffer[:, :, 0].astype(np.uint16) + 20, 255).astype(np.uint8)

                # Big countdown number in yellow
                cnt = int(math.ceil(self._camera_countdown))
                draw_centered_text(buffer, str(cnt), 40, self._yellow, scale=5)
            elif self._sub_phase == RoastPhase.CAMERA_PREP:
                # Show "press button" prompt with semi-transparent overlay at bottom
                buffer[-24:, :, :] = (buffer[-24:, :, :].astype(np.float32) * 0.4).astype(np.uint8)
                buffer[-24:, :, 0] = np.minimum(buffer[-24:, :, 0].astype(np.uint16) + 40, 255).astype(np.uint8)
                draw_centered_text(buffer, "ЖМИ", 115, self._yellow, scale=1)

        elif self._sub_phase == RoastPhase.PROCESSING:
            # Render Santa runner minigame while AI is processing, with camera as background
            # Get live camera frame for background
            camera_bg = camera_service.get_frame(timeout=0)

            # Render the Santa runner game with camera background
            if self._santa_runner:
                self._santa_runner.render(buffer, background=camera_bg)

                # Add compact progress bar at the top
                bar_w, bar_h = 100, 4
                bar_x = (128 - bar_w) // 2
                bar_y = 2

                # Semi-transparent dark background for progress bar
                draw_rect(buffer, bar_x - 2, bar_y - 1, bar_w + 4, bar_h + 2, (20, 20, 40))

                # Use the SmartProgressTracker's render method for the progress bar
                self._progress_tracker.render_progress_bar(
                    buffer, bar_x, bar_y, bar_w, bar_h,
                    bar_color=self._red,
                    bg_color=(40, 40, 40),
                    time_ms=self._time_in_phase
                )

                # Show compact status at bottom
                status_message = self._progress_tracker.get_message()
                # Semi-transparent dark strip for text
                draw_rect(buffer, 0, 118, 128, 10, (20, 20, 40))
                draw_centered_text(buffer, status_message, 119, (200, 200, 200), scale=1)

            else:
                # Fallback to simple processing screen if no game
                fill(buffer, (10, 5, 5))
                draw_centered_text(buffer, "ГОТОВЛЮ...", 55, self._red, scale=2)

        elif self._sub_phase == RoastPhase.REVEAL:
             draw_centered_text(buffer, "ПОЛУЧАЙ!", 64, self._red, scale=2)

        elif self._sub_phase == RoastPhase.RESULT:
            # Display mode: 0 = image, 1 = text, 2 = qr
            if self._display_mode == 2:
                self._render_qr_view(buffer)
            else:
                if self._display_mode == 0 and self._doodle_image and self._doodle_image.image_data:
                    # MODE 0: FULLSCREEN caricature/doodle (128x128)
                    try:
                        from PIL import Image
                        from io import BytesIO
                        # NOTE: numpy is imported at module level as 'np'

                        img = Image.open(BytesIO(self._doodle_image.image_data))
                        img = img.convert("RGB")
                        # FULLSCREEN - fill entire 128x128 display
                        img = img.resize((128, 128), Image.Resampling.LANCZOS)
                        img_array = np.array(img)

                        # Fill entire buffer
                        buffer[:128, :128] = img_array

                        nav_hint = self._display_nav_hint()

                        if nav_hint and int(self._time_in_phase / 500) % 2 != 0:
                            draw_centered_text(buffer, nav_hint, 114, (100, 100, 120), scale=1)
                        elif self._uploader.is_uploading and self._qr_image is None:
                            draw_centered_text(buffer, "ЗАГРУЗКА...", 114, (150, 150, 150), scale=1)
                        else:
                            draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 114, (100, 200, 100), scale=1)

                    except Exception as e:
                        logger.error(f"Failed to render caricature: {e}")
                        # Fallback to text mode
                        self._display_mode = 1

                if self._display_mode == 1 or not (self._doodle_image and self._doodle_image.image_data):
                    # MODE 1: Full screen text with PAGINATION (no scrolling!)
                    # Compact title with page indicator
                    total_pages = len(self._text_pages) if self._text_pages else 1
                    page_idx = min(self._text_page_index, total_pages - 1) if self._text_pages else 0

                    if total_pages > 1:
                        left_arrow = "◄" if page_idx > 0 else " "
                        right_arrow = "►" if page_idx < total_pages - 1 else " "
                        title_text = f"{left_arrow} {self._vibe_score[:8]} {page_idx + 1}/{total_pages} {right_arrow}"
                        draw_centered_text(buffer, title_text, 3+shake_y, self._yellow, scale=1)
                    else:
                        draw_centered_text(buffer, self._vibe_score, 3+shake_y, self._yellow, scale=2)

                    # Render current text page - FULLSCREEN
                    if self._text_pages:
                        page_lines = self._text_pages[page_idx]
                        y = 18 if total_pages > 1 else 24
                        line_height = 8
                        for i, line in enumerate(page_lines):
                            pulse = 0.9 + 0.1 * math.sin(self._time_in_phase / 400 + i * 0.3)
                            color = tuple(int(255 * pulse) for _ in range(3))
                            draw_centered_text(buffer, line, y+shake_y, color, scale=1)
                            y += line_height
                    else:
                        draw_centered_text(buffer, "...", 50+shake_y, (100, 100, 100), scale=1)

                    # No bottom hints - fullscreen text!

        self._particles.render(buffer)

        if self._flash_alpha > 0:
            a = int(255 * self._flash_alpha)
            fill(buffer, (a, a, a))
            self._flash_alpha = max(0, self._flash_alpha - 0.1)

    def render_ticker(self, buffer) -> None:
        """Render ticker display with phase-specific messages."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_static, render_ticker_animated, TickerEffect, TextEffect

        clear(buffer)  # Always clear the buffer!

        if self._sub_phase == RoastPhase.INTRO:
            render_ticker_animated(
                buffer, "ПРОЖАРКА",
                self._time_in_phase, self._red,
                TickerEffect.PULSE_SCROLL, speed=0.03
            )

        elif self._sub_phase == RoastPhase.CAMERA_PREP:
            render_ticker_static(buffer, "КАМЕРА", self._time_in_phase, self._yellow, TextEffect.GLOW)

        elif self._sub_phase == RoastPhase.CAMERA_CAPTURE:
            cnt = int(self._camera_countdown) + 1
            render_ticker_static(buffer, f"ФОТО: {cnt}", self._time_in_phase, self._yellow, TextEffect.GLOW)

        elif self._sub_phase == RoastPhase.PROCESSING:
            # Use Santa Runner's ticker progress bar (cycles continuously)
            if self._santa_runner:
                progress = self._progress_tracker.get_progress()
                self._santa_runner.render_ticker(buffer, progress, self._time_in_phase)
                return  # Skip other rendering

        elif self._sub_phase == RoastPhase.REVEAL:
            render_ticker_animated(
                buffer, "ПОЛУЧАЙ!",
                self._time_in_phase, self._red,
                TickerEffect.PULSE_SCROLL, speed=0.05
            )

        elif self._sub_phase == RoastPhase.RESULT:
            render_ticker_static(buffer, f"ВАЙБ: {self._vibe_score[:8]}", self._time_in_phase, self._yellow, TextEffect.GLOW)

    def get_lcd_text(self) -> str:
        """Get LCD text with phase-specific animation."""
        if self._sub_phase == RoastPhase.INTRO:
            return " * ПРОЖАРКА * ".center(16)[:16]
        elif self._sub_phase == RoastPhase.CAMERA_PREP:
            eye = "*" if int(self._time_in_phase / 300) % 2 == 0 else "o"
            return f" {eye} КАМЕРА {eye} ".center(16)[:16]
        elif self._sub_phase == RoastPhase.CAMERA_CAPTURE:
            cnt = int(self._camera_countdown) + 1
            return f" * ФОТО: {cnt} * ".center(16)[:16]
        elif self._sub_phase == RoastPhase.PROCESSING:
            spinner = "-\\|/"
            spin = spinner[int(self._time_in_phase / 200) % 4]
            return f" {spin} ГОТОВЛЮ {spin} ".center(16)[:16]
        elif self._sub_phase == RoastPhase.REVEAL:
            return " ! ПОЛУЧАЙ ! ".center(16)[:16]
        elif self._sub_phase == RoastPhase.RESULT:
            return f" {self._vibe_score[:10]} ".center(16)[:16]
        return " * ПРОЖАРКА * ".center(16)[:16]

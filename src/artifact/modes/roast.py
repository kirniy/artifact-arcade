"""Roast Me Mode - AI generates a funny roast + doodle.

The AI analyzes the user's photo to generate a lighthearted "roast" 
and a messy doodle caricature.
Style: Graffiti, chaotic, fun.
"""

import asyncio
import logging
from typing import Optional, Tuple
from datetime import datetime
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets
from artifact.graphics.progress import SmartProgressTracker, ProgressPhase
from artifact.ai.client import get_gemini_client, GeminiModel
from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle
from artifact.simulator.mock_hardware.camera import SimulatorCamera, create_camera

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
- Матерись если надо (умеренно, для акцента, не в каждом слове)
- Шути про возраст, внешность, стиль жизни - всё честно
- НЕ СДЕРЖИВАЙСЯ - человек СОЗНАТЕЛЬНО пришёл на прожарку!
- Но помни: цель - РАССМЕШИТЬ, а не обидеть. Жёстко но с любовью.

ПРИМЕРЫ ВЗРОСЛЫХ ПРОЖАРОК:
- "Бля, чел, ты выглядишь как будто жизнь тебя уже прожарила до меня. Эти мешки под глазами - это не усталость, это багаж из всех твоих плохих решений. А причёска говорит 'мне похуй' громче любых слов. Уважаю честность!"
- "Братан, у тебя вайб 'мама до сих пор стирает'. Этот свитер видел больше разочарований чем твой тиндер. А взгляд такой, будто ты только что осознал что твоя личность - это не личность, а набор мемов из 2019."
- "О, классика! Выражение лица 'я не как все' у человека который выглядит как каждый второй в метро. Твой стиль кричит 'я пытался' - и это грустнее чем если бы ты не пытался вообще."

ФОРМАТ ОТВЕТА (СТРОГО!):
ROAST: [3-5 предложений убойной прожарки с конкретными деталями С ФОТО]
VIBE: [ОДНО слово: ДУШНИЛА/КРАШ/ЗУМЕР/БУМЕР/NPC/СИГМА/ЧИЛГАЙ/ТОКСИК/КРИНЖ/БАЗИРОВАННЫЙ/ВАНИЛЬКА/ХАОС]
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
        self._vibe_score: str = ""
        self._doodle_image: Optional[Caricature] = None
        
        # Animations
        self._particles = ParticleSystem()
        self._shake_amount: float = 0.0
        self._ai_task: Optional[asyncio.Task] = None
        self._processing_progress: float = 0.0
        self._progress_tracker = SmartProgressTracker(mode_theme="roast")

        # Display mode for result screen (0 = image full screen, 1 = text)
        self._display_mode: int = 1  # Start with text view

        # Text scroll tracking
        self._text_scroll_complete: bool = False
        self._text_view_time: float = 0.0
        self._scroll_duration: float = 0.0

        # Colors
        self._red = (255, 50, 50)
        self._yellow = (255, 200, 0)

    @property
    def is_ai_available(self) -> bool:
        return self._gemini_client.is_available

    def on_enter(self) -> None:
        self._sub_phase = RoastPhase.INTRO
        self._photo_data = None
        self._roast_text = ""
        self._vibe_score = ""
        self._doodle_image = None
        self._shake_amount = 0.0
        self._flash_alpha = 0.0
        self._display_mode = 1  # Start with text view
        self._text_scroll_complete = False
        self._text_view_time = 0.0
        self._scroll_duration = 0.0
        self._progress_tracker.reset()

        self._camera = create_camera(resolution=(640, 480))
        if self._camera.open():
            logger.info("Camera opened for Roast")

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
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_capture()
                
                if self._time_in_phase > 3500:
                    self._start_processing()

        elif self.phase == ModePhase.PROCESSING:
            # Update smart progress tracker
            self._progress_tracker.update(delta_ms)

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
                    # Calculate scroll duration
                    if self._roast_text and self._scroll_duration == 0:
                        from artifact.graphics.text_utils import calculate_scroll_duration, MAIN_DISPLAY_WIDTH
                        from artifact.graphics.fonts import load_font
                        font = load_font("cyrillic")
                        rect = (4, 10, MAIN_DISPLAY_WIDTH - 8, 100)
                        self._scroll_duration = calculate_scroll_duration(
                            self._roast_text, rect, font, scale=1, line_spacing=2, scroll_interval_ms=1400
                        )
                        self._scroll_duration = max(3000, self._scroll_duration + 2000)
            elif self._sub_phase == RoastPhase.RESULT:
                # Track time in text view
                if self._display_mode == 1:  # text view
                    self._text_view_time += delta_ms
                    if not self._text_scroll_complete and self._text_view_time >= self._scroll_duration:
                        self._text_scroll_complete = True
                        if self._doodle_image:
                            self._display_mode = 0  # Switch to image

                if self._time_in_phase > 45000:
                    self._finish()

    def on_input(self, event: Event) -> bool:
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT and self._sub_phase == RoastPhase.RESULT:
                # In image view or no image - print immediately
                if self._display_mode == 0 or not self._doodle_image:
                    self._finish()
                    return True
                # In text view - switch to image first
                else:
                    if self._doodle_image:
                        self._display_mode = 0
                        self._text_scroll_complete = True
                    else:
                        self._finish()
                    return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.RESULT and self._sub_phase == RoastPhase.RESULT:
                self._display_mode = 1  # text view
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.RESULT and self._sub_phase == RoastPhase.RESULT and self._doodle_image:
                self._display_mode = 0  # image view
                return True

        return False

    def _start_capture(self) -> None:
        self._sub_phase = RoastPhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0

    def _do_capture(self) -> None:
        if self._camera and self._camera.is_open:
            self._photo_data = self._camera.capture_jpeg(quality=90)
            self._flash_alpha = 1.0
            
    def _update_camera_preview(self) -> None:
        if not self._camera: return
        try:
             from artifact.simulator.mock_hardware.camera import floyd_steinberg_dither, create_viewfinder_overlay
             frame = self._camera.capture_frame()
             if frame is not None:
                 dithered = floyd_steinberg_dither(frame, target_size=(128, 128))
                 self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()
        except Exception: pass

    def _start_processing(self) -> None:
        self._sub_phase = RoastPhase.PROCESSING
        self.change_phase(ModePhase.PROCESSING)

        # Start smart progress tracker
        self._progress_tracker.start()
        self._progress_tracker.advance_to_phase(ProgressPhase.ANALYZING)

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
                    return ("ИИ не смог тебя прожарить - видимо, ты слишком идеален. Или камера сломалась.", "ЗАГАДКА")

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
            self._roast_text, self._vibe_score = await get_text()

            # Advance to image generation phase
            self._progress_tracker.advance_to_phase(ProgressPhase.GENERATING_IMAGE)
            self._doodle_image = await get_image()

            # Advance to finalizing
            self._progress_tracker.advance_to_phase(ProgressPhase.FINALIZING)
            logger.info(f"Roast complete - text: '{self._roast_text[:50]}...', vibe: {self._vibe_score}, has_image: {self._doodle_image is not None}")

        except Exception as e:
            logger.error(f"AI Failure: {e}")
            self._roast_text = "Ты сломал мой ИИ своей красотой."

    def _parse_response(self, text: str) -> Tuple[str, str]:
        """Parse AI response, handling multi-line ROAST content."""
        roast_lines = []
        vibe = "СТРАННЫЙ"
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
                vibe = line[5:].strip().upper()
            elif in_roast and line:
                # Continue collecting roast text
                roast_lines.append(line)

        roast = " ".join(roast_lines).strip()

        # If no structured response, use the whole text
        if not roast:
            # Clean up any markdown or extra formatting
            clean_text = text.replace("**", "").replace("*", "").strip()
            roast = clean_text[:300] if len(clean_text) > 300 else clean_text

        logger.info(f"Parsed roast: {roast[:100]}... vibe: {vibe}")
        return roast, vibe

    def _on_ai_complete(self) -> None:
        self._progress_tracker.complete()
        self._sub_phase = RoastPhase.REVEAL
        self.change_phase(ModePhase.RESULT)

    def on_exit(self) -> None:
        if self._camera: self._camera.close()
        if self._ai_task: self._ai_task.cancel()
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
                "doodle": self._doodle_image.image_data if self._doodle_image else None,
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
             if self._camera_frame is not None:
                if self._camera_frame.shape == (128, 128, 3):
                    import numpy as np
                    np.copyto(buffer, self._camera_frame)
             
             if self._sub_phase == RoastPhase.CAMERA_CAPTURE:
                 cnt = math.ceil(self._camera_countdown)
                 draw_centered_text(buffer, str(cnt), 64+shake_x, self._yellow, scale=3)

        elif self._sub_phase == RoastPhase.PROCESSING:
            # Animated processing screen with flames and smart progress
            from artifact.graphics.primitives import draw_circle

            # Pulsing background
            pulse = 0.5 + 0.3 * math.sin(self._time_in_phase / 200)
            bg_intensity = int(20 * pulse)
            fill(buffer, (bg_intensity + 10, 5, 5))

            # Render flames-style loading animation from progress tracker
            self._progress_tracker.render_loading_animation(buffer, style="flames", time_ms=self._time_in_phase)

            # Multiple flame layers (additional visual effect)
            flame_colors = [(255, 50, 50), (255, 100, 0), (255, 200, 0)]
            for i, color in enumerate(flame_colors):
                flame_y = 85 - i * 12
                wave = math.sin(self._time_in_phase / 150 + i)
                for x in range(20, 108, 10):
                    flame_height = int(25 + 10 * math.sin(self._time_in_phase / 100 + x / 10) + wave * 5)
                    for y in range(flame_y, flame_y - flame_height, -4):
                        if 0 <= y < 128:
                            alpha = (flame_y - y) / flame_height
                            c = tuple(int(v * alpha) for v in color)
                            draw_circle(buffer, x + int(wave * 3), y, 2, c)

            # Processing text with glow
            glow_pulse = 0.7 + 0.3 * math.sin(self._time_in_phase / 150)
            text_color = tuple(int(c * glow_pulse) for c in self._red)
            draw_centered_text(buffer, "ГОТОВЛЮ", 30+shake_y, text_color, scale=2)
            draw_centered_text(buffer, "ОГОНЬ", 50+shake_y, self._yellow, scale=2)

            # Smart progress bar
            bar_w, bar_h = 100, 8
            bar_x = (128 - bar_w) // 2
            bar_y = 92

            self._progress_tracker.render_progress_bar(
                buffer, bar_x, bar_y, bar_w, bar_h,
                bar_color=self._red,
                bg_color=(40, 40, 40),
                time_ms=self._time_in_phase
            )

            # Show phase-specific status message from tracker
            status_message = self._progress_tracker.get_message()
            draw_centered_text(buffer, status_message, 106, (200, 200, 200), scale=1)

        elif self._sub_phase == RoastPhase.REVEAL:
             draw_centered_text(buffer, "ПОЛУЧАЙ!", 64, self._red, scale=2)

        elif self._sub_phase == RoastPhase.RESULT:
            # Display mode: 0 = full screen image, 1 = full screen text
            if self._display_mode == 0 and self._doodle_image and self._doodle_image.image_data:
                # MODE 0: Full screen caricature/doodle
                try:
                    from PIL import Image
                    from io import BytesIO
                    import numpy as np

                    img = Image.open(BytesIO(self._doodle_image.image_data))
                    img = img.convert("RGB")
                    # Fill the display (128x128) with slight margin
                    img = img.resize((120, 120), Image.Resampling.LANCZOS)
                    img_array = np.array(img)

                    # Center the image
                    buffer[4:124, 4:124] = img_array

                    # Show hint at bottom (using safe zone Y=114 for scale=1)
                    if int(self._time_in_phase / 500) % 2 == 0:
                        draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 114, (100, 200, 100), scale=1)
                    else:
                        draw_centered_text(buffer, "◄ ТЕКСТ", 114, (100, 100, 120), scale=1)

                except Exception as e:
                    logger.error(f"Failed to render caricature: {e}")
                    # Fallback to text mode
                    self._display_mode = 1

            if self._display_mode == 1 or not (self._doodle_image and self._doodle_image.image_data):
                # MODE 1: Full screen text (or fallback if no image)
                # Vibe score at top
                draw_centered_text(buffer, self._vibe_score, 15+shake_y, self._yellow, scale=2)

                # Roast text with scrolling
                lines = smart_wrap_text(self._roast_text, MAIN_DISPLAY_WIDTH - 8, font=None, scale=1)
                visible_lines = 7
                line_height = 12
                total_lines = len(lines)
                scroll_offset = 0
                if total_lines > visible_lines:
                    cycle = max(1, total_lines - visible_lines + 1)
                    step = int((self._time_in_phase / 2000) % cycle)
                    scroll_offset = step

                y = 38
                for line in lines[scroll_offset:scroll_offset + visible_lines]:
                    draw_centered_text(buffer, line, y+shake_y, (255, 255, 255))
                    y += line_height

                # Show hint at bottom (using safe zone Y=114 for scale=1)
                if self._doodle_image and self._doodle_image.image_data:
                    if int(self._time_in_phase / 600) % 2 == 0:
                        draw_centered_text(buffer, "ФОТО ►", 114, (100, 150, 200), scale=1)
                    else:
                        draw_centered_text(buffer, "НАЖМИ", 114, (100, 100, 120), scale=1)
                else:
                    if int(self._time_in_phase / 600) % 2 == 0:
                        draw_centered_text(buffer, "НАЖМИ = ПЕЧАТЬ", 114, (100, 200, 100), scale=1)

        self._particles.render(buffer)

        if self._flash_alpha > 0:
            a = int(255 * self._flash_alpha)
            fill(buffer, (a, a, a))
            self._flash_alpha = max(0, self._flash_alpha - 0.1)

    def render_ticker(self, buffer) -> None:
        """Render ticker display with phase-specific messages."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import draw_centered_text

        clear(buffer)  # Always clear the buffer!

        if self._sub_phase == RoastPhase.INTRO:
            draw_centered_text(buffer, "ПРОЖАРКА", 2, self._red)

        elif self._sub_phase == RoastPhase.CAMERA_PREP:
            draw_centered_text(buffer, "КАМЕРА", 2, self._yellow)

        elif self._sub_phase == RoastPhase.CAMERA_CAPTURE:
            cnt = int(self._camera_countdown) + 1
            draw_centered_text(buffer, f"ФОТО: {cnt}", 2, self._yellow)

        elif self._sub_phase == RoastPhase.PROCESSING:
            # Animated processing indicator
            dots = "." * (int(self._time_in_phase / 300) % 4)
            draw_centered_text(buffer, f"ГОТОВЛЮ{dots}", 2, self._red)

        elif self._sub_phase == RoastPhase.REVEAL:
            draw_centered_text(buffer, "ПОЛУЧАЙ!", 2, self._red)

        elif self._sub_phase == RoastPhase.RESULT:
            draw_centered_text(buffer, f"ВАЙБ: {self._vibe_score[:8]}", 2, self._yellow)

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

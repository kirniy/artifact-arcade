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

ROAST_SYSTEM_PROMPT = """Ты - стендап-комик с прожаркой (Roast).
Твоя задача - по фото человека придумать смешную, дерзкую "прожарку".

Правила:
- Будь дерзким, но не токсичным. Мы хотим посмеяться, а не довести до слёз.
- Используй иронию, сарказм, преувеличение.
- Цепляйся за детали внешности, стиль одежды, выражение лица.
- Можешь использовать сленг.

Примеры:
- "Эта причёска кричит 'Я только что проснулся', но костюм говорит 'Мне к 8:00 в офис'. Кризис идентичности?"
- "Взгляд как у кота, который уронил ёлку и ждёт наказания. В чём ты провинился?"

Format:
ROAST: [Твой текст прожарки (макс 2 предложения)]
VIBE: [Оценка вайба в одном слове, например 'ДУШНИЛА' или 'КРАШ']
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
            if self._ai_task and self._ai_task.done():
                self._on_ai_complete()
            else:
                 self._processing_progress = min(0.9, self._processing_progress + delta_ms / 6000)

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == RoastPhase.REVEAL:
                if self._time_in_phase > 2000:
                    self._shake_amount = 5.0 # Impact!
                    self._sub_phase = RoastPhase.RESULT
                    self._time_in_phase = 0
            elif self._sub_phase == RoastPhase.RESULT:
                if self._time_in_phase > 15000:
                    self._finish()

    def on_input(self, event: Event) -> bool:
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.RESULT:
                self._finish()
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
                    prompt="Roast this person's look!",
                    image_data=self._photo_data,
                    model=GeminiModel.FLASH_VISION,
                    system_instruction=ROAST_SYSTEM_PROMPT
                )
                return self._parse_response(res) if res else ("Скучный тип...", "НОРМ")

            async def get_image():
                return await self._caricature_service.generate_caricature(
                    reference_photo=self._photo_data,
                    style=CaricatureStyle.ROAST,
                    personality_context="Mean roast doodle"
                )

            self._roast_text, self._vibe_score = await get_text()
            self._doodle_image = await get_image()

        except Exception as e:
            logger.error(f"AI Failure: {e}")
            self._roast_text = "Ты сломал мой ИИ своей красотой."

    def _parse_response(self, text: str) -> Tuple[str, str]:
        roast = ""
        vibe = "СТРАННЫЙ"
        for line in text.strip().split("\n"):
            if line.startswith("ROAST:"): roast = line[6:].strip()
            elif line.startswith("VIBE:"): vibe = line[5:].strip()
        if not roast: roast = text[:100]
        return roast, vibe

    def _on_ai_complete(self) -> None:
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
            display_text=self._roast_text[:32],
            ticker_text=f"ВАЙБ: {self._vibe_score}",
            lcd_text=" ПРОЖАРКА ".center(16),
            should_print=True,
            print_data={
                "type": "roast",
                "roast": self._roast_text,
                "vibe": self._vibe_score,
                "doodle": self._doodle_image.image_data if self._doodle_image else None,
                "timestamp": datetime.now().isoformat()
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        from artifact.graphics.primitives import fill, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, wrap_text, draw_animated_text, TextEffect

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
             draw_centered_text(buffer, "ГОТОВЛЮ ОГОНЬ", 64, self._red, scale=1)

        elif self._sub_phase == RoastPhase.REVEAL:
             draw_centered_text(buffer, "ПОЛУЧАЙ!", 64, self._red, scale=2)

        elif self._sub_phase == RoastPhase.RESULT:
             draw_centered_text(buffer, self._vibe_score, 20+shake_y, self._yellow, scale=2)
             lines = wrap_text(self._roast_text, 18)
             y = 50
             for line in lines[:5]:
                 draw_centered_text(buffer, line, y+shake_y, (255, 255, 255))
                 y += 12

        self._particles.render(buffer)
        
        if self._flash_alpha > 0:
            a = int(255 * self._flash_alpha)
            fill(buffer, (a, a, a))
            self._flash_alpha = max(0, self._flash_alpha - 0.1)

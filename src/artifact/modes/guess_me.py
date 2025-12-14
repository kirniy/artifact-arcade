"""Guess Me Mode - AI guesses who you are + generates annotated illustration.

 

The AI analyzes the user's photo to guess their profession, hobby, or secret,

and generates a fun illustration with annotations.

"""

 

import asyncio

import logging

from typing import Optional, Tuple, List

from datetime import datetime

import random

import math

import numpy as np

 

from artifact.core.events import Event, EventType

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase

from artifact.animation.particles import ParticleSystem, ParticlePresets

from artifact.ai.client import get_gemini_client, GeminiModel

from artifact.ai.caricature import CaricatureService, Caricature, CaricatureStyle

from artifact.simulator.mock_hardware.camera import (

    SimulatorCamera, create_camera, floyd_steinberg_dither, create_viewfinder_overlay

)

 

logger = logging.getLogger(__name__)

 

 

class GuessPhase:

    """Sub-phases within Guess Me mode."""

    INTRO = "intro"              # "Who are you?" intro

    CAMERA_PREP = "camera_prep"  # "Look at camera"

    CAMERA_CAPTURE = "capture"   # Snap photo

    PROCESSING = "processing"    # AI guessing + drawing

    REVEAL = "reveal"            # Text guess reveal

    SHOW_IMAGE = "show_image"    # Image reveal

    RESULT = "result"            # Final Result

 

 

# =============================================================================

# AI PROMPTS

# =============================================================================

 

GUESS_SYSTEM_PROMPT = """Ты - проницательный ИИ в аркадном автомате.

Твоя задача - по фото человека УГАДАТЬ (придумать смешно) его профессию, хобби или тайну.

 

Стиль:

- Весёлый, ироничный, креативный

- Можно немного абсурдный (но в меру)

- Используй смайлики

- Кратко и ёмко

 

Примеры:

- "Ты точно работаешь в IT. Вижу этот взгляд, уставший от дебаггинга. Твоя тайна: ты всё ещё гуглишь, как центрировать div."

- "Хм... Похоже, ты профессиональный дегустатор кофе. Или просто не спал три дня. В любом случае, энергия бьёт ключом!"

- "Вижу ауру стартапера. В кармане питч-дек, в голове - единорог. Ищешь инвестора даже в очереди за кофе."

 

Format output as:

GUESS: [твоя догадка]

TITLE: [короткий титул, например "Король Дедлайнов"]

"""

 

class GuessMeMode(BaseMode):

    """Guess Me Mode - AI guesses user's persona + annotated drawing.

 

    Flow:

    1. Camera capture

    2. AI analyzes photo textually (Gemini 2.5 Flash)

    3. AI draws annotated illustration (Gemini 3.0 Pro / Imagen)

    4. Prints result (2:3 aspect ratio ideally, but we fit to printer)

    """

 

    name = "guess_me"

    display_name = "КТО Я?"

    description = "ИИ угадывает профессию"

    icon = "?"

    style = "pop"  # Vibrant pop art style

    requires_camera = True

    requires_ai = True

    estimated_duration = 50

 

    def __init__(self, context: ModeContext):

        super().__init__(context)

 

        # Services

        self._gemini_client = get_gemini_client()

        self._caricature_service = CaricatureService()

 

        # Sub-phase

        self._sub_phase = GuessPhase.INTRO

 

        # Camera

        self._camera: Optional[SimulatorCamera] = None

        self._camera_frame: Optional[bytes] = None

        self._photo_data: Optional[bytes] = None

        self._camera_countdown: float = 0.0

        self._flash_alpha: float = 0.0

 

        # Data

        self._guess_text: str = ""

        self._guess_title: str = ""

        self._illustration: Optional[Caricature] = None

 

        # Task

        self._ai_task: Optional[asyncio.Task] = None

        self._processing_progress: float = 0.0

 

        # Visuals

        self._particles = ParticleSystem()

        self._reveal_progress: float = 0.0

        self._primary = (255, 0, 100)   # Hot Pink

        self._secondary = (0, 255, 200) # Cyan

 

    @property

    def is_ai_available(self) -> bool:

        return self._gemini_client.is_available

 

    def on_enter(self) -> None:

        self._sub_phase = GuessPhase.INTRO

        self._photo_data = None

        self._guess_text = ""

        self._guess_title = ""

        self._illustration = None

        self._processing_progress = 0.0

        self._reveal_progress = 0.0

        self._flash_alpha = 0.0

 

        # Camera

        self._camera = create_camera(resolution=(640, 480))

        if self._camera.open():

            logger.info("Camera opened for Guess Me")

 

        # Particles

        confetti = ParticlePresets.confetti(x=64, y=64)

        self._particles.add_emitter("confetti", confetti)

 

        self.change_phase(ModePhase.INTRO)

        logger.info("Guess Me mode entered")

 

    def on_update(self, delta_ms: float) -> None:

        self._particles.update(delta_ms)

 

        # Update preview

        if self._sub_phase in (GuessPhase.CAMERA_PREP, GuessPhase.CAMERA_CAPTURE):

            self._update_camera_preview()

 

        # Phase logic

        if self.phase == ModePhase.INTRO:

            if self._time_in_phase > 2000:

                self._sub_phase = GuessPhase.CAMERA_PREP

                self.change_phase(ModePhase.ACTIVE)

                self._time_in_phase = 0

 

        elif self.phase == ModePhase.ACTIVE:

            if self._sub_phase == GuessPhase.CAMERA_PREP:

                if self._time_in_phase > 2000:

                    self._start_capture()

 

            elif self._sub_phase == GuessPhase.CAMERA_CAPTURE:

                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                if self._camera_countdown <= 0 and self._photo_data is None:

                    self._do_capture()

 

                if self._time_in_phase > 3500: # Wait for flash

                    self._start_processing()

 

        elif self.phase == ModePhase.PROCESSING:

            if self._ai_task and self._ai_task.done():

                self._on_ai_complete()

            else:

                self._processing_progress = min(0.95, self._processing_progress + delta_ms / 6000)

 

        elif self.phase == ModePhase.RESULT:

            # Logic for revealing guess then image

            if self._sub_phase == GuessPhase.REVEAL:

                if self._time_in_phase > 4000: # Show text for 4s

                    self._sub_phase = GuessPhase.SHOW_IMAGE

                    self._time_in_phase = 0

            elif self._sub_phase == GuessPhase.SHOW_IMAGE:

                if self._time_in_phase > 4000: # Show image for 4s

                    self._sub_phase = GuessPhase.RESULT # Then combined result

                    self._time_in_phase = 0

            elif self._sub_phase == GuessPhase.RESULT:

                if self._time_in_phase > 15000:

                    self._finish()

 

    def on_input(self, event: Event) -> bool:

        if event.type == EventType.BUTTON_PRESS:

            if self.phase == ModePhase.RESULT:

                self._finish()

                return True

        return False

 

    def _start_capture(self) -> None:

        self._sub_phase = GuessPhase.CAMERA_CAPTURE

        self._time_in_phase = 0

        self._camera_countdown = 3.0

 

    def _do_capture(self) -> None:

        if self._camera and self._camera.is_open:

            self._photo_data = self._camera.capture_jpeg(quality=90)

            self._flash_alpha = 1.0

            logger.info("Photo captured")

 

    def _update_camera_preview(self) -> None:

        if not self._camera: return

        frame = self._camera.capture_frame()

        if frame is not None:

            dithered = floyd_steinberg_dither(frame, target_size=(128, 128))

            self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()

 

    def _start_processing(self) -> None:

        self._sub_phase = GuessPhase.PROCESSING

        self.change_phase(ModePhase.PROCESSING)

        self._ai_task = asyncio.create_task(self._run_ai())

        

        emitter = self._particles.get_emitter("confetti")

        if emitter: emitter.burst(30)

 

    async def _run_ai(self) -> None:

        try:

            if not self._photo_data:

                self._guess_text = "Не удалось сделать фото :("

                self._guess_title = "Ошибка"

                return

 

            # Parallel generation

            async def get_text():

                response = await self._gemini_client.generate_with_image(

                    prompt="Кто этот человек? Угадай профессию/хобби!",

                    image_data=self._photo_data,

                    model=GeminiModel.FLASH_VISION,

                    system_instruction=GUESS_SYSTEM_PROMPT

                )

                return self._parse_response(response) if response else ("Загадочная личность...", "Незнакомец")

 

            async def get_image():

                return await self._caricature_service.generate_caricature(

                    reference_photo=self._photo_data,

                    style=CaricatureStyle.GUESS,

                    personality_context="Fun, annotated illustration"

                )

 

            text_res, img_res = await asyncio.gather(get_text(), get_image())

            self._guess_text, self._guess_title = text_res

            self._illustration = img_res

 

        except Exception as e:

            logger.error(f"AI Error: {e}")

            self._guess_text = "ИИ задумался о смысле жизни..."

            self._guess_title = "Сбой"

 

    def _parse_response(self, text: str) -> Tuple[str, str]:

        guess = ""

        title = "Угадываю..."

        for line in text.strip().split("\n"):

            if line.startswith("GUESS:"): guess = line[6:].strip()

            elif line.startswith("TITLE:"): title = line[6:].strip()

        if not guess: guess = text[:100]

        return guess, title

 

    def _on_ai_complete(self) -> None:

        self._processing_progress = 1.0

        self._sub_phase = GuessPhase.REVEAL

        self.change_phase(ModePhase.RESULT)

 

    def on_exit(self) -> None:

        if self._camera: self._camera.close()

        if self._ai_task: self._ai_task.cancel()

        self._particles.clear_all()

 

    def _finish(self) -> None:

        result = ModeResult(

            mode_name=self.name,

            success=True,

            display_text=self._guess_title,

            ticker_text=self._guess_title,

            lcd_text=" КТО Я? ".center(16),

            should_print=True,

            print_data={

                "type": "guess_me",

                "title": self._guess_title,

                "text": self._guess_text,

                "image": self._illustration.image_data if self._illustration else None,

                "timestamp": datetime.now().isoformat()

            }

        )

        self.complete(result)

 

    def render_main(self, buffer) -> None:

        from artifact.graphics.primitives import fill, draw_rect

        from artifact.graphics.text_utils import draw_centered_text, wrap_text

 

        fill(buffer, (20, 20, 40))

 

        if self._sub_phase == GuessPhase.INTRO:

            draw_centered_text(buffer, "КТО ТЫ?", 64, self._primary, scale=2)

 

        elif self._sub_phase in (GuessPhase.CAMERA_PREP, GuessPhase.CAMERA_CAPTURE):

            if self._camera_frame is not None:

                 if self._camera_frame.shape == (128, 128, 3):

                    import numpy as np

                    np.copyto(buffer, self._camera_frame)

            

            if self._sub_phase == GuessPhase.CAMERA_CAPTURE:

                cnt = math.ceil(self._camera_countdown)

                if cnt > 0:

                    draw_centered_text(buffer, str(cnt), 64, (255, 255, 255), scale=3)

 

        elif self._sub_phase == GuessPhase.PROCESSING:

            # Simple loading animation

            t = self._time_in_phase

            dots = "." * (int(t/300) % 4)

            draw_centered_text(buffer, f"АНАЛИЗ{dots}", 64, self._secondary, scale=1)

 

        elif self._sub_phase == GuessPhase.REVEAL:

            draw_centered_text(buffer, self._guess_title, 40, self._primary, scale=1)

            lines = wrap_text(self._guess_text, 18)

            for i, line in enumerate(lines[:4]):

                draw_centered_text(buffer, line, 60 + i*12, (255, 255, 255))

 

        elif self._sub_phase == GuessPhase.SHOW_IMAGE:

            # Only works if we have image, otherwise skip

            draw_centered_text(buffer, "ПОРТРЕТ", 64, self._secondary, scale=2)

 

        elif self._sub_phase == GuessPhase.RESULT:

             draw_centered_text(buffer, "ГОТОВО!", 64, (0, 255, 0), scale=2)

 

        self._particles.render(buffer)

        

        if self._flash_alpha > 0:

            a = int(255 * self._flash_alpha)

            fill(buffer, (a, a, a))

            self._flash_alpha = max(0, self._flash_alpha - 0.1)


"""Roulette mode - Spinning wheel of fortune with winner portrait.

A classic arcade-style spinning wheel with various outcomes.
Uses arcade visual style with flashing lights and dramatic spin animation.
After winning, takes photo and generates winner portrait.
"""

import asyncio
import logging
from typing import List, Tuple, Optional
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


class RoulettePhase:
    """Sub-phases within the Roulette mode."""
    INTRO = "intro"
    READY = "ready"           # Waiting for spin
    SPINNING = "spinning"     # Wheel spinning
    WIN_REVEAL = "win_reveal" # Show winning segment
    CAMERA_PREP = "camera_prep"
    CAMERA_CAPTURE = "capture"
    GENERATING = "generating" # AI portrait generation
    RESULT = "result"         # Final result with portrait


# Party wheel segments - more exciting prizes and dares!
# Each has: (Russian text, symbol for wheel, color, rarity)
# Rarity: 1=common, 2=uncommon, 3=rare, 4=legendary
WHEEL_SEGMENTS = [
    ("ШОТИК!", "🥃", (46, 204, 113), 1),          # Shot - Green
    ("ТАНЦУЙ!", "💃", (241, 196, 15), 1),          # Dance - Yellow
    ("ОБНИМИ!", "🤗", (52, 152, 219), 1),          # Hug dare - Blue
    ("СКИДКА 15%", "💰", (155, 89, 182), 2),       # Discount - Purple
    ("ПОЦЕЛУЙ!", "💋", (231, 76, 60), 2),          # Kiss dare - Red
    ("КОКТЕЙЛЬ!", "🍹", (230, 126, 34), 2),        # Free cocktail - Orange
    ("ФОТО+ШАРЖ", "📸", (149, 165, 200), 3),       # Photo + caricature - Blue-gray
    ("ДЖЕКПОТ!", "⭐", (255, 215, 0), 4),          # Jackpot - Gold!
    ("КОМПЛИМЕНТ", "💝", (255, 150, 200), 1),      # Give compliment - Pink
    ("СЕЛФИ!", "🤳", (100, 200, 255), 1),          # Selfie - Light blue
    ("ЕЩЁ РАЗ!", "🔄", (200, 200, 200), 2),        # Spin again - Silver
    ("ЖЕЛАНИЕ!", "✨", (255, 180, 100), 3),        # Make a wish - Orange-gold
]

# Fun outcomes for each segment (what gets printed on receipt)
OUTCOMES_RU = {
    "ШОТИК!": [
        "Бармен ждёт тебя!",
        "Один шот за счёт колеса!",
        "Выпей за фортуну!",
        "Шот-шот-шот!",
    ],
    "ТАНЦУЙ!": [
        "Покажи свои движения!",
        "Танцуй как никто не смотрит!",
        "На танцпол, звезда!",
        "Твой момент славы!",
    ],
    "ОБНИМИ!": [
        "Обними того, кто рядом!",
        "Тёплые обнимашки!",
        "Раздай обнимашки!",
        "Мир нуждается в объятиях!",
    ],
    "СКИДКА 15%": [
        "Скидка 15% в баре!",
        "Покажи этот чек бармену!",
        "VIP статус активирован!",
        "Экономия = ещё один коктейль!",
    ],
    "ПОЦЕЛУЙ!": [
        "Поцелуй того, кто рядом!",
        "Найди кого-то милого!",
        "Романтика в воздухе!",
        "Чмок-чмок!",
    ],
    "КОКТЕЙЛЬ!": [
        "Бесплатный коктейль!",
        "Покажи бармену этот чек!",
        "Колесо угощает!",
        "Твой напиток ждёт!",
    ],
    "ФОТО+ШАРЖ": [
        "Бесплатное фото и шарж!",
        "Ты выиграл портрет!",
        "ИИ нарисует тебя!",
        "Попозируй на камеру!",
    ],
    "ДЖЕКПОТ!": [
        "★ ДЖЕКПОТ! ★",
        "ТЫ ВЫИГРАЛ ГЛАВНЫЙ ПРИЗ!",
        "Покажи бармену СЕЙЧАС!",
        "Сегодня твой день!",
    ],
    "КОМПЛИМЕНТ": [
        "Скажи комплимент незнакомцу!",
        "Сделай чей-то вечер лучше!",
        "Добрые слова = добрая карма!",
        "Подари улыбку!",
    ],
    "СЕЛФИ!": [
        "Сделай селфи с машиной!",
        "Запости в сторис!",
        "Поза для Instagram!",
        "Улыбочку! 📸",
    ],
    "ЕЩЁ РАЗ!": [
        "Крути ещё раз БЕСПЛАТНО!",
        "Удача дала второй шанс!",
        "Ещё одна попытка!",
        "Фортуна улыбается!",
    ],
    "ЖЕЛАНИЕ!": [
        "Загадай желание!",
        "Шепни вселенной мечту!",
        "Желание исполнится!",
        "Магия уже работает!",
    ],
}

# Legacy compatibility - map old segments
LEGACY_OUTCOMES = {
    "УДАЧА": [
        "Удача улыбнётся тебе сегодня",
        "Фортуна на твоей стороне",
        "Жди счастливого случая",
    ],
    "ЛЮБОВЬ": [
        "Любовь уже близко",
        "Сердце найдёт свой путь",
        "Романтика в воздухе",
    ],
    "БОГАТСТВО": [
        "Финансовый успех впереди",
        "Деньги придут неожиданно",
        "Инвестиции окупятся",
    ],
    "ЗДОРОВЬЕ": [
        "Здоровье укрепится",
        "Энергия наполнит тебя",
        "Тело и дух в гармонии",
    ],
    "УСПЕХ": [
        "Успех уже на горизонте",
        "Твои усилия вознаградятся",
        "Победа будет твоей",
    ],
    "ПРИКЛЮЧЕНИЕ": [
        "Приключение ждёт тебя",
        "Новые горизонты откроются",
        "Путешествие изменит всё",
    ],
    "МУДРОСТЬ": [
        "Мудрость придёт к тебе",
        "Ответы станут ясными",
        "Знание - твоя сила",
    ],
    "СЧАСТЬЕ": [
        "Счастье уже здесь",
        "Радость наполнит дни",
        "Улыбка не сойдёт с лица",
    ],
}


class RouletteMode(BaseMode):
    """Roulette mode - Spin the wheel of fortune with winner portrait.

    Flow:
    1. Intro: Wheel appears with lights animation
    2. Active: "Press to spin" prompt
    3. Processing: Wheel spinning animation
    4. Win Reveal: Display winning segment
    5. Camera: Take winner photo
    6. AI Generation: Create winner portrait
    7. Result: Display portrait and prize
    """

    name = "roulette"
    display_name = "РУЛЕТКА"
    description = "Крути колесо судьбы"
    icon = "O"
    style = "arcade"
    requires_camera = True
    requires_ai = True
    estimated_duration = 35

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Sub-phase tracking
        self._sub_phase = RoulettePhase.INTRO

        # AI services
        self._gemini_client = get_gemini_client()
        self._caricature_service = CaricatureService()

        # Camera state
        self._camera: Optional[SimulatorCamera] = None
        self._camera_frame: Optional[bytes] = None
        self._photo_data: Optional[bytes] = None
        self._camera_countdown: float = 0.0
        self._camera_flash: float = 0.0

        # AI results
        self._winner_portrait: Optional[Caricature] = None
        self._ai_task: Optional[asyncio.Task] = None

        # Wheel state
        self._wheel_angle: float = 0.0
        self._wheel_velocity: float = 0.0
        self._target_segment: int = 0
        self._spinning: bool = False
        self._click_cooldown: float = 0.0  # For click sound timing

        # Result
        self._result_segment: str = ""
        self._result_outcome: str = ""
        self._result_rarity: int = 1
        self._display_mode: int = 0  # 0 = portrait, 1 = text

        # Animation
        self._light_phase: float = 0.0
        self._flash_alpha: float = 0.0
        self._pulse_phase: float = 0.0
        self._shake_amount: float = 0.0
        self._glow_intensity: float = 0.0
        self._celebration_time: float = 0.0

        # Particles
        self._particles = ParticleSystem()

        # Colors - more vibrant
        self._primary = (255, 215, 0)      # Gold
        self._secondary = (255, 50, 80)    # Vibrant red
        self._background = (15, 15, 35)    # Darker for contrast
        self._glow_color = (255, 200, 100) # Warm glow

    def on_enter(self) -> None:
        """Initialize roulette mode."""
        self._sub_phase = RoulettePhase.INTRO
        self._wheel_angle = random.random() * 360
        self._wheel_velocity = 0.0
        self._spinning = False
        self._result_segment = ""
        self._result_outcome = ""
        self._result_rarity = 1
        self._display_mode = 0
        self._flash_alpha = 0.0
        self._pulse_phase = 0.0
        self._shake_amount = 0.0
        self._glow_intensity = 0.0
        self._celebration_time = 0.0
        self._click_cooldown = 0.0

        # Reset camera state
        self._photo_data = None
        self._camera_frame = None
        self._camera_countdown = 0.0
        self._camera_flash = 0.0

        # Reset AI state
        self._winner_portrait = None
        self._ai_task = None

        # Initialize camera
        self._camera = create_camera(resolution=(640, 480))
        if self._camera.open():
            logger.info("Camera opened for Roulette mode")
        else:
            logger.warning("Could not open camera, using placeholder")

        # Setup particles - multiple emitters for layered effects
        sparkle_config = ParticlePresets.sparkle(x=64, y=64)
        sparkle_config.color = self._primary
        sparkle_config.emission_rate = 2.0
        self._particles.add_emitter("sparkles", sparkle_config)

        # Fire/celebration particles
        fire_config = ParticlePresets.fire(x=64, y=100)
        fire_config.color = (255, 150, 50)
        fire_config.emission_rate = 0.0  # Only burst on win
        self._particles.add_emitter("fire", fire_config)

        self.change_phase(ModePhase.INTRO)
        logger.info("Roulette mode entered")

    def on_update(self, delta_ms: float) -> None:
        """Update roulette mode."""
        self._particles.update(delta_ms)

        # Animate lights (faster when spinning)
        light_speed = 0.03 if self._spinning else 0.01
        self._light_phase += delta_ms * light_speed

        # Pulse animation
        self._pulse_phase += delta_ms * 0.005

        # Decay shake
        self._shake_amount = max(0, self._shake_amount - delta_ms / 200)

        # Click cooldown
        self._click_cooldown = max(0, self._click_cooldown - delta_ms)

        # Update camera preview during camera phases
        if self._sub_phase in (RoulettePhase.CAMERA_PREP, RoulettePhase.CAMERA_CAPTURE):
            self._update_camera_preview()

        if self.phase == ModePhase.INTRO:
            # Longer intro with glow fade-in - 2.5 seconds
            self._glow_intensity = min(1.0, self._time_in_phase / 1500)
            if self._time_in_phase > 2500:
                self._sub_phase = RoulettePhase.READY
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == RoulettePhase.READY:
                # Pulsing glow effect to attract attention
                self._glow_intensity = 0.5 + 0.5 * math.sin(self._pulse_phase)

            elif self._sub_phase == RoulettePhase.CAMERA_PREP:
                # Camera prep for 2 seconds
                if self._time_in_phase > 2000:
                    self._start_camera_capture()

            elif self._sub_phase == RoulettePhase.CAMERA_CAPTURE:
                # Countdown animation
                self._camera_countdown = max(0, 3.0 - self._time_in_phase / 1000)

                # Capture when countdown reaches 0
                if self._camera_countdown <= 0 and self._photo_data is None:
                    self._do_camera_capture()
                    self._camera_flash = 1.0

                # Flash effect after capture
                if self._time_in_phase > 3000:
                    self._camera_flash = max(0, 1.0 - (self._time_in_phase - 3000) / 500)

                    if self._time_in_phase > 3500:
                        self._start_ai_generation()

        elif self.phase == ModePhase.PROCESSING:
            if self._sub_phase == RoulettePhase.SPINNING:
                # Update wheel spin
                if self._spinning:
                    self._update_spin(delta_ms)
                    # Increase glow based on speed
                    self._glow_intensity = min(1.0, abs(self._wheel_velocity) / 800)

            elif self._sub_phase == RoulettePhase.GENERATING:
                # Check AI task progress
                if self._ai_task:
                    if self._ai_task.done():
                        self._on_ai_complete()

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == RoulettePhase.WIN_REVEAL:
                # Flash animation decay
                self._flash_alpha = max(0, self._flash_alpha - delta_ms / 800)

                # Celebration for 3 seconds then move to camera
                self._celebration_time += delta_ms
                if self._result_rarity >= 3:  # Rare or legendary
                    # Continuous particle bursts
                    if int(self._celebration_time / 300) > int((self._celebration_time - delta_ms) / 300):
                        fire = self._particles.get_emitter("fire")
                        if fire:
                            fire.burst(15)

                # After win reveal, move to camera
                if self._time_in_phase > 3000:
                    self._sub_phase = RoulettePhase.CAMERA_PREP
                    self.change_phase(ModePhase.ACTIVE)
                    self._time_in_phase = 0

            elif self._sub_phase == RoulettePhase.RESULT:
                # Final result with portrait - auto-complete after 20 seconds
                if self._time_in_phase > 20000:
                    self._finish()

    def _update_spin(self, delta_ms: float) -> None:
        """Update spinning wheel physics with click effects."""
        # Track segment changes for "click" effect
        old_segment = int((self._wheel_angle % 360) / (360 / len(WHEEL_SEGMENTS)))

        # Apply velocity
        self._wheel_angle += self._wheel_velocity * delta_ms / 1000

        # New segment check
        new_segment = int((self._wheel_angle % 360) / (360 / len(WHEEL_SEGMENTS)))
        if old_segment != new_segment and self._click_cooldown <= 0:
            # "Click" effect - small shake
            self._shake_amount = 0.5
            self._click_cooldown = 50  # 50ms between clicks

        # Apply friction (exponential decay) - slower for more drama
        friction = 0.988 if self._wheel_velocity > 200 else 0.975
        self._wheel_velocity *= friction

        # Check if stopped
        if abs(self._wheel_velocity) < 8:
            self._spinning = False
            self._on_spin_complete()

    def _on_spin_complete(self) -> None:
        """Handle spin completion with rarity-based celebration."""
        # Normalize angle
        self._wheel_angle = self._wheel_angle % 360

        # Calculate winning segment
        segment_angle = 360 / len(WHEEL_SEGMENTS)
        # Adjust for pointer at top (90 degrees)
        adjusted_angle = (self._wheel_angle + 90) % 360
        segment_idx = int(adjusted_angle / segment_angle)
        segment_idx = len(WHEEL_SEGMENTS) - 1 - segment_idx  # Reverse direction

        segment = WHEEL_SEGMENTS[segment_idx % len(WHEEL_SEGMENTS)]
        self._result_segment = segment[0]  # Russian name
        self._result_rarity = segment[3]   # Rarity level
        self._result_outcome = random.choice(OUTCOMES_RU.get(self._result_segment, ["Удача!"]))

        # Trigger effects based on rarity
        self._flash_alpha = 1.0
        self._celebration_time = 0.0

        sparkles = self._particles.get_emitter("sparkles")
        fire = self._particles.get_emitter("fire")

        if self._result_rarity >= 4:  # Legendary (Jackpot)
            # MASSIVE celebration
            if sparkles:
                sparkles.burst(100)
            if fire:
                fire.burst(50)
            self._shake_amount = 2.0
        elif self._result_rarity >= 3:  # Rare
            if sparkles:
                sparkles.burst(70)
            if fire:
                fire.burst(30)
            self._shake_amount = 1.5
        elif self._result_rarity >= 2:  # Uncommon
            if sparkles:
                sparkles.burst(50)
            self._shake_amount = 1.0
        else:  # Common
            if sparkles:
                sparkles.burst(30)
            self._shake_amount = 0.5

        # Move to win reveal phase (will transition to camera after)
        self._sub_phase = RoulettePhase.WIN_REVEAL
        self.change_phase(ModePhase.RESULT)
        self._time_in_phase = 0

        logger.info(f"Roulette spin complete: {self._result_segment} (rarity {self._result_rarity})")

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.ACTIVE and self._sub_phase == RoulettePhase.READY:
                self._start_spin()
                return True
            elif self.phase == ModePhase.RESULT and self._sub_phase == RoulettePhase.RESULT:
                # Toggle display mode or finish
                if self._winner_portrait:
                    self._display_mode = (self._display_mode + 1) % 2
                    if self._display_mode == 0:
                        # After full cycle, finish
                        self._finish()
                else:
                    self._finish()
                return True

        elif event.type == EventType.ARCADE_LEFT:
            if self.phase == ModePhase.RESULT and self._sub_phase == RoulettePhase.RESULT and self._winner_portrait:
                self._display_mode = 0  # Portrait view
                return True

        elif event.type == EventType.ARCADE_RIGHT:
            if self.phase == ModePhase.RESULT and self._sub_phase == RoulettePhase.RESULT and self._winner_portrait:
                self._display_mode = 1  # Text view
                return True

        return False

    def _start_spin(self) -> None:
        """Start the wheel spinning."""
        # Random initial velocity (fast enough for drama)
        self._wheel_velocity = random.uniform(800, 1200)
        self._spinning = True
        self._sub_phase = RoulettePhase.SPINNING

        # Burst particles
        sparkles = self._particles.get_emitter("sparkles")
        if sparkles:
            sparkles.burst(30)

        self.change_phase(ModePhase.PROCESSING)
        logger.info("Roulette wheel spinning")

    def on_exit(self) -> None:
        """Cleanup."""
        # Cancel any pending AI task
        if self._ai_task and not self._ai_task.done():
            self._ai_task.cancel()

        # Close camera
        if self._camera:
            self._camera.close()
            self._camera = None

        self._particles.clear_all()
        self.stop_animations()

    def _update_camera_preview(self) -> None:
        """Update the live camera preview frame with dithering."""
        if not self._camera or not self._camera.is_open:
            return

        try:
            frame = self._camera.capture_frame()
            if frame is not None and frame.size > 0:
                dithered = floyd_steinberg_dither(frame, target_size=(128, 128), threshold=120)
                self._camera_frame = create_viewfinder_overlay(dithered, self._time_in_phase).copy()
        except Exception as e:
            logger.warning(f"Camera preview update error: {e}")
            self._camera_frame = None

    def _start_camera_capture(self) -> None:
        """Start the camera capture sequence."""
        self._sub_phase = RoulettePhase.CAMERA_CAPTURE
        self._time_in_phase = 0
        self._camera_countdown = 3.0
        logger.info("Roulette camera capture started - countdown begins")

    def _do_camera_capture(self) -> None:
        """Actually capture the photo from camera."""
        if self._camera and self._camera.is_open:
            self._photo_data = self._camera.capture_jpeg(quality=90)
            if self._photo_data:
                logger.info(f"Roulette captured winner photo: {len(self._photo_data)} bytes")
            else:
                logger.warning("Failed to capture photo in Roulette mode")
        else:
            logger.warning("Camera not available for Roulette capture")
            self._photo_data = None

    def _start_ai_generation(self) -> None:
        """Start AI processing for winner portrait."""
        self._sub_phase = RoulettePhase.GENERATING
        self.change_phase(ModePhase.PROCESSING)

        # Start async AI task for portrait generation
        self._ai_task = asyncio.create_task(self._generate_winner_portrait())

        # Burst particles
        sparkles = self._particles.get_emitter("sparkles")
        if sparkles:
            sparkles.burst(50)

        logger.info("Roulette winner portrait generation started")

    async def _generate_winner_portrait(self) -> None:
        """Generate winner portrait using AI."""
        try:
            if self._photo_data:
                self._winner_portrait = await self._caricature_service.generate_caricature(
                    reference_photo=self._photo_data,
                    style=CaricatureStyle.ROULETTE,
                    personality_context=f"Выиграл: {self._result_segment} - {self._result_outcome}",
                )
                if self._winner_portrait:
                    logger.info("Roulette winner portrait generated successfully")
                else:
                    logger.warning("Roulette winner portrait generation returned None")
            else:
                logger.warning("No photo data for Roulette portrait generation")
                self._winner_portrait = None
        except Exception as e:
            logger.error(f"Roulette portrait generation failed: {e}")
            self._winner_portrait = None

    def _on_ai_complete(self) -> None:
        """Handle completion of AI processing."""
        self._sub_phase = RoulettePhase.RESULT
        self.change_phase(ModePhase.RESULT)
        self._time_in_phase = 0

        # Start with portrait view if available
        self._display_mode = 0 if self._winner_portrait else 1

        # Burst particles for reveal
        sparkles = self._particles.get_emitter("sparkles")
        fire = self._particles.get_emitter("fire")
        if sparkles:
            sparkles.burst(80)
        if fire:
            fire.burst(40)

        logger.info("Roulette AI complete, entering final result phase")

    def _render_camera_preview(self, buffer) -> None:
        """Render the camera preview to buffer."""
        try:
            if self._camera_frame is not None and isinstance(self._camera_frame, np.ndarray):
                if self._camera_frame.shape == buffer.shape:
                    np.copyto(buffer, self._camera_frame)
        except Exception as e:
            logger.debug(f"Camera frame render error: {e}")

    def _render_portrait(self, buffer) -> None:
        """Render the AI-generated winner portrait."""
        from artifact.graphics.primitives import draw_rect
        from artifact.graphics.text_utils import draw_centered_text
        from io import BytesIO

        if not self._winner_portrait:
            return

        try:
            from PIL import Image

            img = Image.open(BytesIO(self._winner_portrait.image_data))
            img = img.convert("RGB")

            display_size = 100
            img = img.resize((display_size, display_size), Image.Resampling.NEAREST)

            x_offset = (128 - display_size) // 2
            y_offset = 5

            for y in range(display_size):
                for x in range(display_size):
                    bx = x_offset + x
                    by = y_offset + y
                    if 0 <= bx < 128 and 0 <= by < 128:
                        pixel = img.getpixel((x, y))
                        buffer[by, bx] = pixel

            # Border with gold
            draw_rect(buffer, x_offset - 2, y_offset - 2, display_size + 4, display_size + 4, self._primary, filled=False)

            # Label with win result
            draw_centered_text(buffer, self._result_segment, 112, self._primary, scale=1)

        except Exception as e:
            logger.warning(f"Failed to render winner portrait: {e}")

    def _get_segment_color(self, segment_name: str) -> Tuple[int, int, int]:
        """Get the color for a wheel segment by name."""
        for name_ru, symbol, color, rarity in WHEEL_SEGMENTS:
            if name_ru == segment_name:
                return color
        return (255, 255, 255)  # Default white

    def _finish(self) -> None:
        """Complete the mode."""
        result = ModeResult(
            mode_name=self.name,
            success=True,
            display_text=f"{self._result_segment}: {self._result_outcome}",
            ticker_text=self._result_outcome,
            lcd_text=self._result_segment.center(16)[:16],
            should_print=True,
            print_data={
                "result": self._result_segment,
                "outcome": self._result_outcome,
                "rarity": self._result_rarity,
                "portrait": self._winner_portrait.image_data if self._winner_portrait else None,
                "category": "fortune_wheel",
                "type": "roulette"
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display with fullscreen wheel."""
        from artifact.graphics.primitives import fill, draw_circle, draw_line, draw_rect
        from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

        # Camera phases - show camera preview instead of wheel
        if self._sub_phase == RoulettePhase.CAMERA_PREP:
            self._render_camera_preview(buffer)
            draw_centered_text(buffer, "УЛЫБНИСЬ!", 10, self._primary, scale=1)
            draw_centered_text(buffer, "ПОБЕДИТЕЛЬ", 100, self._secondary, scale=2)
            self._particles.render(buffer)
            return

        if self._sub_phase == RoulettePhase.CAMERA_CAPTURE:
            self._render_camera_preview(buffer)

            # Countdown number
            if self._camera_countdown > 0:
                countdown_num = str(int(self._camera_countdown) + 1)
                scale = 4 + int((self._camera_countdown % 1) * 2)
                draw_centered_text(buffer, countdown_num, 45, (255, 255, 255), scale=scale)

                # Progress ring
                progress = 1.0 - (self._camera_countdown % 1)
                for angle_deg in range(0, int(360 * progress), 10):
                    rad = math.radians(angle_deg - 90)
                    px = int(64 + 45 * math.cos(rad))
                    py = int(64 + 45 * math.sin(rad))
                    draw_circle(buffer, px, py, 2, self._primary)

            # Flash effect
            if self._camera_flash > 0:
                buffer[:, :] = np.clip(
                    buffer.astype(np.int16) + int(255 * self._camera_flash),
                    0, 255
                ).astype(np.uint8)
                draw_centered_text(buffer, "ФОТО!", 60, (50, 50, 50), scale=2)

            self._particles.render(buffer)
            return

        # AI generation phase
        if self._sub_phase == RoulettePhase.GENERATING:
            fill(buffer, self._background)
            draw_centered_text(buffer, "СОЗДАЮ", 35, self._primary, scale=2)
            draw_centered_text(buffer, "ПОРТРЕТ", 60, self._secondary, scale=2)

            # Spinning animation
            dots_count = int(self._time_in_phase / 200) % 4
            draw_centered_text(buffer, "." * dots_count, 90, (255, 255, 255), scale=2)

            self._particles.render(buffer)
            return

        # Final result phase with portrait toggle
        if self._sub_phase == RoulettePhase.RESULT:
            fill(buffer, self._background)

            if self._display_mode == 0 and self._winner_portrait:
                # Portrait view
                self._render_portrait(buffer)
                if int(self._time_in_phase / 600) % 2 == 0:
                    draw_centered_text(buffer, "← →ТЕКСТ  ЖМИВЫХОД", 118, (80, 80, 100), scale=1)
            else:
                # Text view - show prize
                draw_centered_text(buffer, self._result_segment, 30, self._primary, scale=2)
                stars = "★" * self._result_rarity
                draw_centered_text(buffer, stars, 55, (255, 215, 0), scale=2)
                draw_centered_text(buffer, self._result_outcome[:20], 85, (255, 255, 255), scale=1)

                if self._winner_portrait:
                    if int(self._time_in_phase / 600) % 2 == 0:
                        draw_centered_text(buffer, "← ФОТО  ЖМИВЫХОД", 118, (80, 80, 100), scale=1)
                else:
                    if int(self._time_in_phase / 500) % 2 == 0:
                        draw_centered_text(buffer, "НАЖМИ ДЛЯ ВЫХОДА", 118, (80, 80, 100), scale=1)

            self._particles.render(buffer)
            return

        # Standard wheel rendering for other phases
        # Background
        fill(buffer, self._background)

        # Shake effect
        shake_x = int(random.uniform(-1, 1) * self._shake_amount * 3) if self._shake_amount > 0 else 0
        shake_y = int(random.uniform(-1, 1) * self._shake_amount * 3) if self._shake_amount > 0 else 0

        # Fullscreen wheel centered
        cx, cy = 64 + shake_x, 64 + shake_y
        wheel_radius = 60  # Maximum size (128x128 screen)

        # Draw outer glow
        if self._glow_intensity > 0:
            for r in range(wheel_radius + 4, wheel_radius, -1):
                glow_alpha = self._glow_intensity * 0.5
                glow_color = tuple(int(c * glow_alpha) for c in self._glow_color)
                draw_circle(buffer, cx, cy, r, glow_color, filled=False)

        # Draw Scale logic (fade in/out or 1.0)
        alpha = 1.0
        if self.phase == ModePhase.INTRO:
            alpha = min(1.0, self._time_in_phase / 1000)

        self._draw_wheel(buffer, cx, cy, wheel_radius, alpha)

        # Draw pointer at the TOP (12 o'clock)
        self._draw_pointer(buffer, 64, 0)

        # Win Reveal Overlay
        if self._sub_phase == RoulettePhase.WIN_REVEAL:
            bar_height = 30
            bar_y = 49

            # Dark transparent bg for readability
            for y in range(bar_y, bar_y + bar_height):
                for x in range(0, 128):
                    buffer[y, x] = tuple(int(c*0.8) for c in buffer[y, x])

            # Draw flashing win animation
            if self._flash_alpha > 0:
                segment_color = self._get_segment_color(self._result_segment)
                draw_rect(buffer, 0, bar_y, 128, bar_height, segment_color, filled=False)

            # Text
            draw_centered_text(buffer, self._result_segment, 55, (255, 255, 255), scale=1)
            # Rarity stars
            stars = "★" * self._result_rarity
            draw_centered_text(buffer, stars, 68, (255, 215, 0), scale=1)

        # Render particles (on top of everything)
        self._particles.render(buffer)

    def _draw_wheel(self, buffer, cx: int, cy: int, radius: int, alpha: float) -> None:
        """Draw filled wheel segments."""
        from artifact.graphics.primitives import draw_line, draw_circle
        
        segment_count = len(WHEEL_SEGMENTS)
        segment_angle = 360 / segment_count
        
        # Optimize rendering by pre-calculating or using larger steps
        # For simulator performance, we might want to be careful with pixel-by-pixel
        # But let's keep the quality high as requested.
        
        for i, (name_ru, symbol, color, rarity) in enumerate(WHEEL_SEGMENTS):
            start_angle = i * segment_angle + self._wheel_angle
            end_angle = start_angle + segment_angle
            
            # Adjust color brightness based on spin/rarity
            rad_color = tuple(int(c * alpha) for c in color)
            
            # Draw segment arc
            # Using simple ray-sweeping for filling wedge
            for a in range(int(start_angle), int(end_angle) + 1, 2): # Step 2 for speed
                rad = math.radians(a)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)
                
                # Draw rays from center to edge
                for r in range(0, radius + 1, 2): # Step 2 for speed
                    px = int(cx + r * cos_a)
                    py = int(cy + r * sin_a)
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = rad_color

        # Wheel Hub
        draw_circle(buffer, cx, cy, 10, (50, 50, 50))
        draw_circle(buffer, cx, cy, 8, (200, 180, 50)) # Gold hub

    def _draw_pointer(self, buffer, x: int, y: int) -> None:
        """Draw pointer triangular arrow at top center."""
        # Simple red triangle pointing down
        # x is center, y is top edge
        
        w = 8
        h = 12
        
        color = (255, 50, 50)
        outline = (255, 255, 255)
        
        # Scanline triangle fill
        for i in range(h):
            row_w = int(w * (1 - i/h))
            py = y + i
            for px in range(x - row_w, x + row_w + 1):
                if 0 <= px < 128 and 0 <= py < 128:
                    buffer[py, px] = color
                    
        # Highlight
        buffer[y, x] = outline

    def render_ticker(self, buffer) -> None:
        """Render ticker with phase-specific messages."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import draw_centered_text, render_ticker_animated, TickerEffect

        clear(buffer)

        if self.phase == ModePhase.INTRO:
            draw_centered_text(buffer, "▲ РУЛЕТКА ▲", 2, self._primary)

        elif self.phase == ModePhase.ACTIVE:
            if self._sub_phase == RoulettePhase.READY:
                # Blink arrows
                if int(self._time_in_phase / 500) % 2 == 0:
                    draw_centered_text(buffer, "▲ КРУТИ ▲", 2, self._secondary)
                else:
                    draw_centered_text(buffer, "  КРУТИ  ", 2, self._secondary)
            elif self._sub_phase == RoulettePhase.CAMERA_PREP:
                draw_centered_text(buffer, "▲ КАМЕРА ▲", 2, self._primary)
            elif self._sub_phase == RoulettePhase.CAMERA_CAPTURE:
                countdown = int(self._camera_countdown) + 1
                draw_centered_text(buffer, f"▲ ФОТО: {countdown} ▲", 2, self._primary)

        elif self.phase == ModePhase.PROCESSING:
            if self._sub_phase == RoulettePhase.SPINNING:
                draw_centered_text(buffer, "▲ КРУЧУ ▲", 2, self._primary)
            elif self._sub_phase == RoulettePhase.GENERATING:
                draw_centered_text(buffer, "▲ ПОРТРЕТ ▲", 2, self._primary)

        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == RoulettePhase.WIN_REVEAL:
                draw_centered_text(buffer, f"▲ {self._result_segment[:8]} ▲", 2, (0, 255, 0))
            else:
                # Final result
                draw_centered_text(buffer, f"▲ {self._result_segment[:8]} ▲", 2, self._primary)

    def get_lcd_text(self) -> str:
        """Get LCD text with phase-specific animation."""
        if self.phase == ModePhase.ACTIVE:
            if self._sub_phase == RoulettePhase.READY:
                frame = int(self._time_in_phase / 300) % 4
                arrows = ["<>", "<>", "><", "><"]
                return f" {arrows[frame]} КРУТИ {arrows[frame]} "[:16]
            elif self._sub_phase == RoulettePhase.CAMERA_PREP:
                eye = "*" if int(self._time_in_phase / 300) % 2 == 0 else "o"
                return f" {eye} КАМЕРА {eye} ".center(16)[:16]
            elif self._sub_phase == RoulettePhase.CAMERA_CAPTURE:
                countdown = int(self._camera_countdown) + 1
                return f" * ФОТО: {countdown} * ".center(16)[:16]
        elif self.phase == ModePhase.PROCESSING:
            if self._sub_phase == RoulettePhase.SPINNING:
                spinner = "-\\|/"
                spin = spinner[int(self._time_in_phase / 100) % 4]
                return f" {spin} КРУЧУ {spin} ".center(16)[:16]
            elif self._sub_phase == RoulettePhase.GENERATING:
                dots = "-\\|/"
                dot = dots[int(self._time_in_phase / 200) % 4]
                return f" {dot} ПОРТРЕТ {dot} ".center(16)[:16]
        elif self.phase == ModePhase.RESULT:
            if self._sub_phase == RoulettePhase.WIN_REVEAL:
                return f">{self._result_segment[:10]}<".center(16)[:16]
            else:
                # Final result
                return f"*{self._result_segment[:10]}*".center(16)[:16]
        return " * РУЛЕТКА * ".center(16)[:16]

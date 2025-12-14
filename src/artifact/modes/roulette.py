"""Roulette mode - Spinning wheel of fortune.

A classic arcade-style spinning wheel with various outcomes.
Uses arcade visual style with flashing lights and dramatic spin animation.
"""

from typing import List, Tuple
import random
import math

from artifact.core.events import Event, EventType
from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.animation.particles import ParticleSystem, ParticlePresets


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
    """Roulette mode - Spin the wheel of fortune.

    Flow:
    1. Intro: Wheel appears with lights animation
    2. Active: "Press to spin" prompt
    3. Processing: Wheel spinning animation
    4. Result: Display winning segment
    """

    name = "roulette"
    display_name = "РУЛЕТКА"
    description = "Крути колесо судьбы"
    icon = "O"
    style = "arcade"
    requires_camera = False
    requires_ai = False
    estimated_duration = 20

    def __init__(self, context: ModeContext):
        super().__init__(context)

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
        self._wheel_angle = random.random() * 360
        self._wheel_velocity = 0.0
        self._spinning = False
        self._result_segment = ""
        self._result_outcome = ""
        self._result_rarity = 1
        self._flash_alpha = 0.0
        self._pulse_phase = 0.0
        self._shake_amount = 0.0
        self._glow_intensity = 0.0
        self._celebration_time = 0.0
        self._click_cooldown = 0.0

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

        if self.phase == ModePhase.INTRO:
            # Longer intro with glow fade-in - 2.5 seconds
            self._glow_intensity = min(1.0, self._time_in_phase / 1500)
            if self._time_in_phase > 2500:
                self.change_phase(ModePhase.ACTIVE)

        elif self.phase == ModePhase.ACTIVE:
            # Pulsing glow effect to attract attention
            self._glow_intensity = 0.5 + 0.5 * math.sin(self._pulse_phase)

        elif self.phase == ModePhase.PROCESSING:
            # Update wheel spin
            if self._spinning:
                self._update_spin(delta_ms)
                # Increase glow based on speed
                self._glow_intensity = min(1.0, abs(self._wheel_velocity) / 800)

        elif self.phase == ModePhase.RESULT:
            # Flash animation decay
            self._flash_alpha = max(0, self._flash_alpha - delta_ms / 800)

            # Celebration time for rare wins
            self._celebration_time += delta_ms
            if self._result_rarity >= 3:  # Rare or legendary
                # Continuous particle bursts
                if int(self._celebration_time / 300) > int((self._celebration_time - delta_ms) / 300):
                    fire = self._particles.get_emitter("fire")
                    if fire:
                        fire.burst(15)

            # Auto-complete after 15 seconds (more time to celebrate)
            if self._time_in_phase > 15000:
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

        self.change_phase(ModePhase.RESULT)

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.ACTIVE:
                self._start_spin()
                return True
            elif self.phase == ModePhase.RESULT:
                self._finish()
                return True

        return False

    def _start_spin(self) -> None:
        """Start the wheel spinning."""
        # Random initial velocity (fast enough for drama)
        self._wheel_velocity = random.uniform(800, 1200)
        self._spinning = True

        # Burst particles
        sparkles = self._particles.get_emitter("sparkles")
        if sparkles:
            sparkles.burst(30)

        self.change_phase(ModePhase.PROCESSING)

    def on_exit(self) -> None:
        """Cleanup."""
        self._particles.clear_all()
        self.stop_animations()

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
                "category": "fortune_wheel",
                "type": "roulette"
            }
        )
        self.complete(result)

    def render_main(self, buffer) -> None:
        """Render main display with fullscreen wheel."""
        from artifact.graphics.primitives import fill, draw_circle, draw_line
        from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

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
        # Wheel is rendered, now pointer overlays it
        # Tip at (64, 4), pointing down to (64, 14)
        self._draw_pointer(buffer, 64, 0)

        # Result Overlay
        if self.phase == ModePhase.RESULT:
            # Result text over the wheel with shadow/bg
            # Semi-transparent bar
            from artifact.graphics.primitives import draw_rect
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
        """Render ticker with STATIC instructions and arrows."""
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import draw_centered_text, TickerEffect, TextEffect

        clear(buffer) # Black background
        
        # Static text centered
        # "LOOK HERE" with arrows pointing down to screen? 
        # Or arrows pointing up to wheel?
        # Assuming ticker is below screen, "LOOK UP" or just "LOOK HERE"
        
        if self.phase == ModePhase.ACTIVE:
            # Arrows pointing UP to the screen
            # ^^^ LOOK HERE ^^^
            
            # Blink arrows
            if int(self._time_in_phase / 500) % 2 == 0:
                 draw_centered_text(buffer, "▲ LOOK HERE ▲", 2, self._secondary)
            else:
                 draw_centered_text(buffer, "  LOOK HERE  ", 2, self._secondary)
                 
        elif self.phase == ModePhase.PROCESSING:
             draw_centered_text(buffer, "▲ SPINNING ▲", 2, self._primary)
             
        elif self.phase == ModePhase.RESULT:
             draw_centered_text(buffer, f"▲ {self._result_outcome[:10]} ▲", 2, (0, 255, 0))
             
        elif self.phase == ModePhase.INTRO:
             draw_centered_text(buffer, "▲ ROULETTE ▲", 2, self._primary)

    def get_lcd_text(self) -> str:
        """Get LCD text with spinning animation."""
        if self.phase == ModePhase.ACTIVE:
            # Animated prompt
            frame = int(self._time_in_phase / 300) % 4
            arrows = ["◄►", "◄►", "►◄", "►◄"]
            return f" {arrows[frame]} КРУТИ {arrows[frame]} "[:16]
        elif self.phase == ModePhase.PROCESSING:
            # Spinning animation
            spinner = "◐◓◑◒"
            spin = spinner[int(self._time_in_phase / 100) % 4]
            return f" {spin} КРУЧУ {spin} "[:16]
        elif self.phase == ModePhase.RESULT:
            # Show prize with emoji
            segment_info = None
            for name_ru, symbol, _ in WHEEL_SEGMENTS:
                if name_ru == self._result_segment:
                    segment_info = (name_ru, symbol)
                    break
            if segment_info:
                return f"►{segment_info[0][:10]}◄".center(16)[:16]
            return f"►{self._result_segment[:10]}◄".center(16)[:16]
        return " ◆ РУЛЕТКА ◆ ".center(16)

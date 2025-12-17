"""Tower Stack - Build the tallest tower on a live video backdrop.

Drop swinging blocks, balance them, grab bonuses, and set a high score.
"""

import math
import random
import logging
from typing import List, Optional
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

logger = logging.getLogger(__name__)


@dataclass
class Block:
    x: float
    y: float
    width: float
    color: tuple
    falling: bool = True
    vx: float = 0.0


class TowerStackMode(BaseMode):
    """Stack swinging blocks on camera background for max height."""

    name = "tower_stack"
    display_name = "БАШНЯ"
    icon = "tower"
    style = "arcade"
    description = "Строй башню на живом видео · попади в ритм и ловишь бонусы"

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._phase = ModePhase.INTRO
        self._time_ms = 0.0
        self._blocks: List[Block] = []
        self._swing_x = 64
        self._swing_dir = 1
        self._swing_speed = 60  # px/sec
        self._block_width = 50
        self._block_y = 10
        self._camera_frame: Optional[NDArray] = None
        self._score = 0
        self._streak = 0
        self._best_height = 0
        self._gravity = 140
        self._shake_timer = 0.0
        self._bonus_timer = 0.0
        self._time_left = 30000

        # Camera
        try:
            from artifact.simulator.mock_hardware.camera import create_camera
            self._camera = create_camera(resolution=(128, 128))
            self._camera.open()
        except Exception:
            self._camera = None

    def on_enter(self) -> None:
        self._phase = ModePhase.ACTIVE
        self._blocks.clear()
        self._swing_x = 64
        self._swing_dir = 1
        self._block_width = 50
        self._block_y = 10
        self._score = 0
        self._streak = 0
        self._best_height = 0
        self._shake_timer = 0
        self._bonus_timer = 0
        self._time_left = 30000
        self._time_ms = 0.0

    def on_exit(self) -> None:
        if hasattr(self, "_camera") and self._camera:
            try:
                self._camera.close()
            except Exception:
                pass

    def on_input(self, event: Event) -> bool:
        logger.debug(f"TowerStack on_input: {event.type}, phase={self.phase}")
        if self.phase != ModePhase.ACTIVE:
            logger.debug(f"TowerStack ignoring input - not in ACTIVE phase")
            return False

        if event.type == EventType.BUTTON_PRESS:
            logger.info("TowerStack: BUTTON_PRESS - dropping block!")
            self._drop_block()
            return True

        elif event.type == EventType.ARCADE_LEFT:
            self._swing_speed = max(40, self._swing_speed - 10)
            return True

        elif event.type == EventType.ARCADE_RIGHT:
            self._swing_speed = min(120, self._swing_speed + 10)
            return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        dt = delta_ms / 1000.0
        self._time_ms += delta_ms
        self._time_left -= delta_ms
        if self._time_left <= 0:
            self._complete()
            return

        # Swing the current block
        self._swing_x += self._swing_dir * self._swing_speed * dt
        if self._swing_x < 15 or self._swing_x > 113:
            self._swing_dir *= -1
            self._swing_x = max(15, min(113, self._swing_x))

        # Update falling blocks
        for block in self._blocks:
            if block.falling:
                block.y += self._gravity * dt
                block.x += block.vx * dt
                # Check collision with tower
                support_y = self._ground_y()
                for placed in reversed(self._blocks):
                    if placed is block or placed.falling:
                        continue
                    if block.y + 8 >= placed.y and abs(block.x - placed.x) < (block.width + placed.width) / 2:
                        support_y = placed.y
                        break
                if block.y + 8 >= support_y:
                    block.y = support_y - 8
                    block.falling = False
                    self._on_block_landed(block)

        # Shake timer
        self._shake_timer = max(0.0, self._shake_timer - delta_ms)
        self._bonus_timer = max(0.0, self._bonus_timer - delta_ms)

        # Capture camera frame for background
        if getattr(self, "_camera", None) and self._camera.is_open:
            try:
                frame = self._camera.capture_frame()
                if frame is not None:
                    if frame.shape[:2] != (128, 128):
                        try:
                            import cv2
                            frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_LINEAR)
                        except ImportError:
                            # Fallback to manual resize
                            from PIL import Image
                            img = Image.fromarray(frame)
                            img = img.resize((128, 128), Image.Resampling.BILINEAR)
                            frame = np.array(img)
                    self._camera_frame = frame
            except Exception as e:
                logger.warning(f"Camera capture error: {e}")

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        t = self._time_ms

        # Camera backdrop with color wash
        if self._camera_frame is not None:
            buffer[:] = (self._camera_frame * 0.6).astype(np.uint8)
            # Apply a gentle hue pulse for sci-fi vibe
            tint = 40 + int(20 * math.sin(t / 500))
            buffer[:] = np.clip(buffer.astype(np.int16) + tint, 0, 255).astype(np.uint8)
        else:
            fill(buffer, (20, 20, 40))

        # Shake effect on hit
        shake_x = shake_y = 0
        if self._shake_timer > 0:
            amp = int(2 * (self._shake_timer / 300))
            shake_x = random.randint(-amp, amp)
            shake_y = random.randint(-amp, amp)

        # Draw tower blocks
        for block in self._blocks:
            color = block.color
            w = int(block.width)
            x = int(block.x) - w // 2 + shake_x
            y = int(block.y) - 8 + shake_y
            draw_rect(buffer, x, y, w, 16, color, filled=True)
            draw_rect(buffer, x, y, w, 16, (0, 0, 0), filled=False, thickness=1)

        # Current swinging block preview
        preview_x = int(self._swing_x) + shake_x
        preview_w = int(self._block_width)
        draw_rect(buffer, preview_x - preview_w // 2, int(self._block_y) + shake_y, preview_w, 10, (255, 220, 120), filled=True)

        # HUD
        draw_centered_text(buffer, f"СЧЁТ {self._score:04d}", 4, (255, 255, 255), scale=1)
        draw_centered_text(buffer, f"ВЫС {self._best_height:02d}", 16, (180, 220, 255), scale=1)
        draw_centered_text(buffer, f"СЕРИЯ {self._streak}x", 28, (255, 200, 120), scale=1)

        # Timer bar
        time_pct = max(0.0, min(1.0, self._time_left / 30000))
        draw_rect(buffer, 10, 118, 108, 6, (30, 30, 50))
        draw_rect(buffer, 10, 118, int(108 * time_pct), 6, (0, 200, 140))

        # Bonus hint
        if self._bonus_timer > 0:
            draw_animated_text(buffer, "БОНУС!", 100, (255, 255, 0), t, TextEffect.PULSE, scale=1)
        else:
            draw_animated_text(buffer, "ЖМИ СТАРТ", 100, (255, 255, 255), t, TextEffect.PULSE, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)
        text = f"РЕКОРД ВЫС {self._best_height} · СЧЁТ {self._score}"
        render_ticker_animated(buffer, text, self._time_left, (0, 255, 180), TickerEffect.PULSE_SCROLL, speed=0.025)

    def get_lcd_text(self) -> str:
        return f"Башня {self._score:04d}"[:16]

    def _drop_block(self) -> None:
        # Create falling block at swing position
        color = random.choice([
            (255, 160, 120), (255, 200, 100), (120, 200, 255), (200, 120, 255)
        ])
        vx = random.uniform(-12, 12)
        block = Block(x=self._swing_x, y=self._block_y, width=self._block_width, color=color, vx=vx)
        self._blocks.append(block)
        # Shrink width slightly for next block to add challenge
        self._block_width = max(16, self._block_width - random.uniform(2, 5))

    def _on_block_landed(self, block: Block) -> None:
        # Determine overlap with previous top block
        top = self._top_block()
        overlap = block.width
        if top:
            diff = abs(block.x - top.x)
            overlap = max(0, (block.width + top.width) / 2 - diff)
        if overlap <= 4:
            # Big miss, penalty
            self._streak = 0
            self._shake_timer = 300
            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_ui_error()
        else:
            # Award points proportional to overlap and streak
            bonus = int(overlap * 2) + self._streak * 5
            self._score += bonus
            self._streak += 1
            self._best_height = max(self._best_height, len([b for b in self._blocks if not b.falling]))
            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_success()
            if self._streak % 5 == 0:
                # Bonus time and fireworks
                self._time_left = min(45000, self._time_left + 3000)
                self._bonus_timer = 800
                if hasattr(self.context, "audio") and self.context.audio:
                    self.context.audio.play_reward()

    def _top_block(self) -> Optional[Block]:
        placed = [b for b in self._blocks if not b.falling]
        return placed[-1] if placed else None

    def _ground_y(self) -> float:
        placed = [b for b in self._blocks if not b.falling]
        return placed[-1].y if placed else 120.0

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=True,
            data={
                "score": self._score,
                "height": self._best_height,
            },
            display_text=f"Башня выс {self._best_height} · Счёт {self._score}",
            ticker_text="ХОЧЕШЬ ЕЩЁ РАЗ?",
            lcd_text="Башня построена!",
            should_print=False,
        )
        self.complete(result)

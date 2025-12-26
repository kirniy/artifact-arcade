"""Towerbrock - Adapted from ongzh/Towerbrock."""

import math
import random
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.text_utils import draw_centered_text, draw_text, measure_text
from artifact.utils.camera_service import camera_service


class TowerbrockMode(BaseMode):
    name = "towerbrock"
    display_name = "TOWER"
    description = "Swing, drop, and stack the tower"
    icon = "tower"
    style = "arcade"
    requires_camera = True

    BLOCK_H = 8
    BASE_Y = 118
    START_W = 40
    ROPE_LEN = 28
    GRAVITY = 220.0
    START_LIVES = 3

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._tower: List[Tuple[float, float, float]] = []
        self._block_w = self.START_W
        self._angle = 0.0
        self._ang_vel = 0.0
        self._drop_x = 64.0
        self._drop_y = 20.0
        self._drop_vy = 0.0
        self._state = "swing"
        self._score = 0
        self._lives = self.START_LIVES
        self._game_over = False
        self._pivot_x = 64
        self._pivot_y = 6

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._tower = []
        base_y = self.BASE_Y - self.BLOCK_H
        self._tower.append((64.0, base_y, self.START_W))
        self._block_w = self.START_W
        self._score = 0
        self._lives = self.START_LIVES
        self._game_over = False
        self._reset_swing()

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            if self._game_over:
                self._reset()
                return True
            if self._state == "swing":
                self._state = "drop"
                self._drop_vy = 0.0
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return
        if self._game_over:
            return

        dt = delta_ms / 1000.0
        if self._state == "swing":
            # Simple pendulum
            self._ang_vel += -math.sin(self._angle) * 0.025
            self._ang_vel *= 0.995
            self._angle += self._ang_vel
            self._drop_x = self._pivot_x + self.ROPE_LEN * math.sin(self._angle)
            self._drop_y = self._pivot_y + self.ROPE_LEN * math.cos(self._angle)
        elif self._state == "drop":
            self._drop_vy += self.GRAVITY * dt
            self._drop_y += self._drop_vy * dt
            target_y = self._next_block_y()
            if self._drop_y >= target_y:
                self._land_block(target_y)

    def _next_block_y(self) -> float:
        last = self._tower[-1]
        return last[1] - self.BLOCK_H

    def _land_block(self, target_y: float) -> None:
        prev_x, prev_y, prev_w = self._tower[-1]
        left = max(prev_x - prev_w / 2, self._drop_x - self._block_w / 2)
        right = min(prev_x + prev_w / 2, self._drop_x + self._block_w / 2)
        overlap = right - left

        if overlap <= 0:
            self._lives -= 1
            if self._lives <= 0:
                self._game_over = True
                return
            self._reset_swing()
            return

        new_x = (left + right) / 2
        self._block_w = overlap
        self._tower.append((new_x, target_y, overlap))
        self._score += 1

        if target_y < 24:
            shifted = []
            for x, y, w in self._tower:
                shifted.append((x, y + self.BLOCK_H, w))
            self._tower = shifted

        self._reset_swing()

    def _reset_swing(self) -> None:
        self._angle = random.choice([-0.6, 0.6])
        self._ang_vel = 0.0
        self._drop_vy = 0.0
        self._drop_x = float(self._pivot_x)
        self._drop_y = float(self._pivot_y + self.ROPE_LEN)
        self._state = "swing"

    def _render_camera_background(self, buffer: NDArray[np.uint8]) -> None:
        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            dimmed = (frame.astype(np.float32) * 0.9).astype(np.uint8)
            np.copyto(buffer, dimmed)
        else:
            fill(buffer, (8, 8, 12))

    def _render_hud(self, buffer: NDArray[np.uint8]) -> None:
        score_text = f"SCORE {self._score}"
        lives_text = f"LIVES {self._lives}"
        score_w, _ = measure_text(score_text, scale=1)
        lives_w, _ = measure_text(lives_text, scale=1)

        draw_rect(buffer, 0, 0, score_w + 4, 9, (0, 0, 0), filled=True)
        draw_text(buffer, score_text, 2, 1, (240, 240, 240), scale=1)

        lives_x = max(0, 128 - lives_w - 4)
        draw_rect(buffer, lives_x, 0, lives_w + 4, 9, (0, 0, 0), filled=True)
        draw_text(buffer, lives_text, lives_x + 2, 1, (240, 200, 200), scale=1)

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        self._render_camera_background(buffer)
        self._render_hud(buffer)

        # Rope and hook
        if not self._game_over:
            draw_line(buffer, self._pivot_x, self._pivot_y, int(self._drop_x), int(self._drop_y), (160, 160, 160))
            draw_rect(buffer, self._pivot_x - 1, self._pivot_y - 1, 3, 3, (220, 80, 80), filled=True)

        # Tower blocks
        for i, (x, y, w) in enumerate(self._tower):
            color = (180, 180, 200) if i % 2 == 0 else (140, 160, 190)
            draw_rect(buffer, int(x - w / 2), int(y), int(w), self.BLOCK_H, color, filled=True)

        # Dropping block
        if not self._game_over:
            draw_rect(buffer, int(self._drop_x - self._block_w / 2), int(self._drop_y), int(self._block_w), self.BLOCK_H, (240, 220, 180), filled=True)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"S{self._score:02d} L{self._lives}", 1, (200, 200, 200), scale=1)

    def get_lcd_text(self) -> str:
        return f"TWR {self._score:02d} L{self._lives}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 6,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="TOWER",
        )
        self.complete(result)

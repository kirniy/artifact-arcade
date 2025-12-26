"""Stacks - Adapted from sherwynds/Stacks."""

import random
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text


class StacksMode(BaseMode):
    name = "stacks"
    display_name = "STACKS"
    description = "Stack without missing"
    icon = "stack"
    style = "arcade"

    BLOCK_H = 8
    BASE_Y = 120
    START_W = 96

    COLORS = [
        (213, 62, 79), (244, 109, 67), (253, 174, 97), (254, 224, 139),
        (255, 255, 191), (230, 245, 152), (171, 221, 164), (102, 194, 165),
        (50, 136, 189), (102, 194, 165), (171, 221, 164), (230, 245, 152),
        (255, 255, 191), (254, 224, 139), (253, 174, 97), (244, 109, 67),
    ]

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._stack: List[Tuple[int, int, int, Tuple[int, int, int]]] = []
        self._moving_x = 0.0
        self._moving_w = self.START_W
        self._moving_y = 0
        self._dir = 1
        self._speed = 70.0
        self._score = 0
        self._game_over = False

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._stack = []
        self._score = 0
        self._game_over = False
        base_x = (128 - self.START_W) // 2
        base_y = self.BASE_Y - self.BLOCK_H
        self._stack.append((base_x, base_y, self.START_W, self.COLORS[0]))
        self._moving_w = self.START_W
        self._moving_x = 0.0
        self._moving_y = base_y - self.BLOCK_H
        self._dir = 1
        self._speed = 70.0

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            if self._game_over:
                self._reset()
                return True
            self._place_block()
            return True

        return False

    def _place_block(self) -> None:
        prev_x, prev_y, prev_w, _prev_color = self._stack[-1]
        left = max(prev_x, int(self._moving_x))
        right = min(prev_x + prev_w, int(self._moving_x + self._moving_w))
        overlap = right - left

        if overlap <= 0:
            self._game_over = True
            return

        self._score += 1
        color = self.COLORS[self._score % len(self.COLORS)]
        self._stack.append((left, self._moving_y, overlap, color))

        self._moving_w = overlap
        self._moving_x = left
        self._moving_y -= self.BLOCK_H
        self._speed = min(140.0, self._speed + 3.0)

        if self._moving_y < 16:
            # Shift stack down to keep it visible
            shifted = []
            for x, y, w, col in self._stack:
                shifted.append((x, y + self.BLOCK_H, w, col))
            self._stack = shifted
            self._moving_y += self.BLOCK_H

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return
        if self._game_over:
            return

        dt = delta_ms / 1000.0
        self._moving_x += self._dir * self._speed * dt

        if self._moving_x <= 0:
            self._moving_x = 0
            self._dir = 1
        elif self._moving_x + self._moving_w >= 128:
            self._moving_x = 128 - self._moving_w
            self._dir = -1

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (6, 6, 10))

        draw_centered_text(buffer, f"SCORE {self._score}", 1, (220, 220, 220), scale=1)

        for x, y, w, color in self._stack:
            draw_rect(buffer, x, y, w, self.BLOCK_H, color, filled=True)

        if not self._game_over:
            draw_rect(buffer, int(self._moving_x), int(self._moving_y), int(self._moving_w), self.BLOCK_H, (240, 240, 240), filled=True)
        else:
            draw_centered_text(buffer, "GAME OVER", 52, (255, 80, 80), scale=1)
            draw_centered_text(buffer, "PRESS", 66, (220, 220, 220), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"STACK {self._score}", 1, (255, 200, 120), scale=1)

    def get_lcd_text(self) -> str:
        return f"STACK {self._score:02d}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 8,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="STACK",
        )
        self.complete(result)

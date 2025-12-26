"""Snake Classic - Adapted from techwithtim/Snake-Game."""

import random
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text


class SnakeClassicMode(BaseMode):
    name = "snake_classic"
    display_name = "SNAKE"
    description = "Classic snake"
    icon = "snake"
    style = "arcade"

    CELL = 6
    GRID_W = 20
    GRID_H = 18
    HUD_H = 10
    OFFSET_X = (128 - GRID_W * CELL) // 2
    OFFSET_Y = HUD_H

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._snake: List[Tuple[int, int]] = []
        self._direction = (1, 0)
        self._next_direction = (1, 0)
        self._food = (0, 0)
        self._score = 0
        self._game_over = False
        self._tick_ms = 140.0
        self._tick_timer = 0.0

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        mid_x = self.GRID_W // 2
        mid_y = self.GRID_H // 2
        self._snake = [(mid_x, mid_y), (mid_x - 1, mid_y)]
        self._direction = (1, 0)
        self._next_direction = (1, 0)
        self._score = 0
        self._game_over = False
        self._tick_timer = 0.0
        self._spawn_food()

    def _spawn_food(self) -> None:
        while True:
            pos = (random.randrange(0, self.GRID_W), random.randrange(0, self.GRID_H))
            if pos not in self._snake:
                self._food = pos
                return

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS and self._game_over:
            self._reset()
            return True

        new_dir = None
        if event.type == EventType.ARCADE_LEFT:
            new_dir = (-1, 0)
        elif event.type == EventType.ARCADE_RIGHT:
            new_dir = (1, 0)
        elif event.type == EventType.ARCADE_UP:
            new_dir = (0, -1)
        elif event.type == EventType.ARCADE_DOWN:
            new_dir = (0, 1)
        elif event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "4":
                new_dir = (-1, 0)
            elif key == "6":
                new_dir = (1, 0)
            elif key == "8":
                new_dir = (0, -1)
            elif key == "2":
                new_dir = (0, 1)

        if new_dir:
            dx, dy = new_dir
            cur_dx, cur_dy = self._direction
            if (dx, dy) != (-cur_dx, -cur_dy):
                self._next_direction = new_dir
            return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        if self._game_over:
            return

        self._tick_timer += delta_ms
        while self._tick_timer >= self._tick_ms:
            self._tick_timer -= self._tick_ms
            self._step()

    def _step(self) -> None:
        self._direction = self._next_direction
        dx, dy = self._direction
        head_x, head_y = self._snake[0]
        new_head = (head_x + dx, head_y + dy)

        if (new_head[0] < 0 or new_head[0] >= self.GRID_W or
                new_head[1] < 0 or new_head[1] >= self.GRID_H):
            self._game_over = True
            return

        if new_head in self._snake:
            self._game_over = True
            return

        self._snake.insert(0, new_head)
        if new_head == self._food:
            self._score += 1
            self._spawn_food()
        else:
            self._snake.pop()

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (10, 10, 15))

        # HUD
        draw_centered_text(buffer, f"SCORE {self._score:03d}", 1, (255, 255, 255), scale=1)

        # Food
        fx, fy = self._food
        draw_rect(
            buffer,
            self.OFFSET_X + fx * self.CELL + 1,
            self.OFFSET_Y + fy * self.CELL + 1,
            self.CELL - 2,
            self.CELL - 2,
            (255, 80, 80),
            filled=True,
        )

        # Snake
        for i, (sx, sy) in enumerate(self._snake):
            color = (120, 255, 120) if i == 0 else (80, 200, 100)
            draw_rect(
                buffer,
                self.OFFSET_X + sx * self.CELL + 1,
                self.OFFSET_Y + sy * self.CELL + 1,
                self.CELL - 2,
                self.CELL - 2,
                color,
                filled=True,
            )

        if self._game_over:
            draw_centered_text(buffer, "GAME OVER", 52, (255, 80, 80), scale=1)
            draw_centered_text(buffer, "PRESS", 66, (200, 200, 200), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"SCORE {self._score}", 1, (120, 255, 120), scale=1)

    def get_lcd_text(self) -> str:
        return f"SNAKE {self._score:03d}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 5,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="SNAKE",
        )
        self.complete(result)

"""Tiny Snake - Adapted from ternus/pygame-examples snake."""

import random
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text


class SnakeTinyMode(BaseMode):
    name = "snake_tiny"
    display_name = "SNAKE MINI"
    description = "Tiny snake with a rock trap"
    icon = "snake"
    style = "arcade"

    GRID = 16
    CELL = 7
    HUD_H = 8
    OFFSET_X = (128 - GRID * CELL) // 2
    OFFSET_Y = HUD_H + 2

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._snake: List[Tuple[int, int]] = []
        self._direction = (1, 0)
        self._next_direction = (1, 0)
        self._food = (0, 0)
        self._rock = (0, 0)
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
        mid = self.GRID // 2
        self._snake = [(mid, mid)]
        self._direction = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
        self._next_direction = self._direction
        self._score = 0
        self._game_over = False
        self._tick_timer = 0.0
        self._tick_ms = 140.0
        self._spawn_rock()
        self._spawn_food()

    def _spawn_food(self) -> None:
        while True:
            pos = (random.randrange(0, self.GRID), random.randrange(0, self.GRID))
            if pos not in self._snake and pos != self._rock:
                self._food = pos
                return

    def _spawn_rock(self) -> None:
        while True:
            pos = (random.randrange(0, self.GRID), random.randrange(0, self.GRID))
            if pos not in self._snake:
                self._rock = pos
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
        new_head = ((head_x + dx) % self.GRID, (head_y + dy) % self.GRID)

        if new_head in self._snake or new_head == self._rock:
            self._game_over = True
            return

        self._snake.insert(0, new_head)
        if new_head == self._food:
            self._score += 1
            self._spawn_food()
            self._tick_ms = max(70.0, 150.0 - self._score * 4.0)
        else:
            self._snake.pop()

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (12, 12, 16))

        draw_centered_text(buffer, f"SCORE {self._score:02d}", 1, (220, 220, 220), scale=1)

        # Rock
        rx, ry = self._rock
        draw_rect(
            buffer,
            self.OFFSET_X + rx * self.CELL + 1,
            self.OFFSET_Y + ry * self.CELL + 1,
            self.CELL - 2,
            self.CELL - 2,
            (140, 90, 40),
            filled=True,
        )

        # Food
        fx, fy = self._food
        draw_rect(
            buffer,
            self.OFFSET_X + fx * self.CELL + 1,
            self.OFFSET_Y + fy * self.CELL + 1,
            self.CELL - 2,
            self.CELL - 2,
            (255, 70, 70),
            filled=True,
        )

        # Snake
        for i, (sx, sy) in enumerate(self._snake):
            color = (100, 240, 140) if i == 0 else (60, 190, 110)
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
            draw_centered_text(buffer, "GAME OVER", 56, (255, 80, 80), scale=1)
            draw_centered_text(buffer, "PRESS", 68, (220, 220, 220), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"SNAKE {self._score}", 1, (100, 240, 140), scale=1)

    def get_lcd_text(self) -> str:
        return f"SNAKE {self._score:02d}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 6,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="SNAKE",
        )
        self.complete(result)

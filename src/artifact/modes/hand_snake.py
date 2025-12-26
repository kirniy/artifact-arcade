"""Hand Snake - Adapted from Interactive_Snake_Game with MediaPipe control."""

import random
from typing import List, Tuple, Optional

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text
from artifact.utils.camera_service import camera_service


class HandSnakeMode(BaseMode):
    name = "hand_snake"
    display_name = "HAND SNAKE"
    description = "Control snake with your hand"
    icon = "hand"
    style = "arcade"
    requires_camera = True

    GRID = 14
    CELL = 8
    HUD_H = 8
    OFFSET_X = (128 - GRID * CELL) // 2
    OFFSET_Y = HUD_H + 2

    CENTER_THRESH = 0.1
    UP_THRESH = 0.4
    DOWN_THRESH = 0.6
    LEFT_THRESH = 0.38
    RIGHT_THRESH = 0.65

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
        self._manual_timer = 0.0

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        mid = self.GRID // 2
        self._snake = [(mid, mid), (mid - 1, mid)]
        self._direction = (1, 0)
        self._next_direction = (1, 0)
        self._score = 0
        self._game_over = False
        self._tick_timer = 0.0
        self._manual_timer = 0.0
        self._spawn_food()

    def _spawn_food(self) -> None:
        while True:
            pos = (random.randrange(0, self.GRID), random.randrange(0, self.GRID))
            if pos not in self._snake:
                self._food = pos
                return

    def _set_direction(self, new_dir: Optional[Tuple[int, int]]) -> None:
        if not new_dir:
            return
        dx, dy = new_dir
        cur_dx, cur_dy = self._direction
        if (dx, dy) != (-cur_dx, -cur_dy):
            self._next_direction = new_dir

    def _hand_direction(self) -> Optional[Tuple[int, int]]:
        overlay = camera_service.get_hand_overlay()
        if not overlay:
            return None
        _bbox, landmarks = overlay
        if len(landmarks) <= 8:
            return None
        fx, fy = landmarks[8]

        if (0.5 - self.CENTER_THRESH < fx < 0.5 + self.CENTER_THRESH and
                0.5 - self.CENTER_THRESH < fy < 0.5 + self.CENTER_THRESH):
            return None
        if fy < self.UP_THRESH:
            return (0, -1)
        if fy > self.DOWN_THRESH:
            return (0, 1)
        if fx < self.LEFT_THRESH:
            return (-1, 0)
        if fx > self.RIGHT_THRESH:
            return (1, 0)
        return None

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
            self._set_direction(new_dir)
            self._manual_timer = 600.0
            return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        if self._game_over:
            return

        self._manual_timer = max(0.0, self._manual_timer - delta_ms)
        if self._manual_timer <= 0.0:
            self._set_direction(self._hand_direction())

        self._tick_timer += delta_ms
        while self._tick_timer >= self._tick_ms:
            self._tick_timer -= self._tick_ms
            self._step()

    def _step(self) -> None:
        self._direction = self._next_direction
        dx, dy = self._direction
        head_x, head_y = self._snake[0]
        new_head = ((head_x + dx) % self.GRID, (head_y + dy) % self.GRID)

        if new_head in self._snake:
            self._game_over = True
            return

        self._snake.insert(0, new_head)
        if new_head == self._food:
            self._score += 1
            self._spawn_food()
            self._tick_ms = max(70.0, 140.0 - self._score * 3.0)
        else:
            self._snake.pop()

    def _render_camera_background(self, buffer: NDArray[np.uint8]) -> None:
        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            dimmed = (frame.astype(np.float32) * 0.7).astype(np.uint8)
            np.copyto(buffer, dimmed)
        else:
            fill(buffer, (8, 10, 14))

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        self._render_camera_background(buffer)

        draw_centered_text(buffer, f"SCORE {self._score:02d}", 1, (220, 220, 220), scale=1)

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
            draw_centered_text(buffer, "GAME OVER", 56, (255, 80, 80), scale=1)
            draw_centered_text(buffer, "PRESS", 68, (220, 220, 220), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"HAND {self._score}", 1, (120, 255, 120), scale=1)

    def get_lcd_text(self) -> str:
        return f"HAND {self._score:02d}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 6,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="HAND",
        )
        self.complete(result)

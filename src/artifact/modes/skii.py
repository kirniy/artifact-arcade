"""Skii - Adapted from Skii-Source-Release."""

import math
import random
from typing import List

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.text_utils import draw_centered_text


class SkiiMode(BaseMode):
    name = "skii"
    display_name = "SKII"
    description = "Slalom downhill on the slope"
    icon = "ski"
    style = "arcade"

    PLAYER_Y = 94
    PLAYER_W = 6
    PLAYER_H = 8
    JUMP_DURATION = 420.0

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._player_x = 64.0
        self._move_dir = 0
        self._move_timer = 0.0
        self._jump_timer = 0.0
        self._scroll_speed = 38.0
        self._center_x = 64.0
        self._center_target = 64.0
        self._slope_width = 76.0
        self._obstacles: List[dict] = []
        self._spawn_timer = 0.0
        self._score = 0.0
        self._game_over = False

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._player_x = 64.0
        self._move_dir = 0
        self._move_timer = 0.0
        self._jump_timer = 0.0
        self._scroll_speed = 38.0
        self._center_x = 64.0
        self._center_target = 64.0
        self._slope_width = 76.0
        self._obstacles = []
        self._spawn_timer = 0.0
        self._score = 0.0
        self._game_over = False

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            if self._game_over:
                self._reset()
                return True
            self._jump_timer = self.JUMP_DURATION
            return True

        if event.type == EventType.ARCADE_LEFT:
            self._move_dir = -1
            self._move_timer = 160.0
            return True
        if event.type == EventType.ARCADE_RIGHT:
            self._move_dir = 1
            self._move_timer = 160.0
            return True
        if event.type == EventType.ARCADE_UP:
            self._jump_timer = self.JUMP_DURATION
            return True

        if event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "4":
                self._move_dir = -1
                self._move_timer = 160.0
                return True
            if key == "6":
                self._move_dir = 1
                self._move_timer = 160.0
                return True
            if key == "8" or key == "5":
                self._jump_timer = self.JUMP_DURATION
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return
        if self._game_over:
            return

        dt = delta_ms / 1000.0
        self._score += self._scroll_speed * dt * 0.3
        self._scroll_speed = min(90.0, self._scroll_speed + dt * 4.0)

        self._center_target += random.uniform(-1.5, 1.5)
        self._center_target = max(44.0, min(84.0, self._center_target))
        self._center_x += (self._center_target - self._center_x) * 0.02
        self._slope_width = max(54.0, 78.0 - (self._scroll_speed - 38.0) * 0.4)

        self._move_timer = max(0.0, self._move_timer - delta_ms)
        if self._move_timer <= 0:
            self._move_dir = 0
        self._player_x += self._move_dir * 90.0 * dt

        left_edge, right_edge = self._slope_edges()
        self._player_x = max(left_edge + 4.0, min(right_edge - 4.0, self._player_x))

        self._jump_timer = max(0.0, self._jump_timer - delta_ms)

        self._spawn_timer += delta_ms
        if self._spawn_timer >= 520.0:
            self._spawn_timer = 0.0
            self._spawn_obstacle()

        self._update_obstacles(dt, left_edge, right_edge)

    def _slope_edges(self) -> tuple[float, float]:
        half = self._slope_width / 2
        return self._center_x - half, self._center_x + half

    def _spawn_obstacle(self) -> None:
        left_edge, right_edge = self._slope_edges()
        x = random.uniform(left_edge + 6.0, right_edge - 6.0)
        self._obstacles.append({"x": x, "y": -10.0, "size": random.randint(5, 7)})

    def _update_obstacles(self, dt: float, left_edge: float, right_edge: float) -> None:
        for obs in list(self._obstacles):
            obs["y"] += self._scroll_speed * dt
            if obs["y"] > 140:
                self._obstacles.remove(obs)
                continue
            if self._jump_timer > 0:
                continue
            if abs(obs["x"] - self._player_x) < (obs["size"] + 3) and abs(obs["y"] - self.PLAYER_Y) < 6:
                self._game_over = True

        if self._player_x <= left_edge + 2 or self._player_x >= right_edge - 2:
            self._game_over = True

    def _jump_offset(self) -> float:
        if self._jump_timer <= 0:
            return 0.0
        phase = 1.0 - (self._jump_timer / self.JUMP_DURATION)
        return math.sin(phase * math.pi) * 10.0

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (200, 220, 240))

        left_edge, right_edge = self._slope_edges()
        draw_rect(buffer, int(left_edge), 0, int(right_edge - left_edge), 128, (230, 230, 235), filled=True)
        draw_line(buffer, int(left_edge), 0, int(left_edge), 127, (140, 160, 180))
        draw_line(buffer, int(right_edge), 0, int(right_edge), 127, (140, 160, 180))

        for obs in self._obstacles:
            self._draw_tree(buffer, int(obs["x"]), int(obs["y"]), obs["size"])

        jump_offset = self._jump_offset()
        self._draw_skier(buffer, int(self._player_x), int(self.PLAYER_Y - jump_offset))

        draw_centered_text(buffer, f"SCORE {int(self._score):03d}", 2, (40, 60, 80), scale=1)

        if self._game_over:
            draw_centered_text(buffer, "CRASH", 52, (255, 80, 80), scale=2)
            draw_centered_text(buffer, "PRESS", 72, (220, 220, 220), scale=1)

    def _draw_tree(self, buffer: NDArray[np.uint8], x: int, y: int, size: int) -> None:
        draw_rect(buffer, x - 1, y + size - 2, 2, 3, (120, 80, 40), filled=True)
        draw_rect(buffer, x - size // 2, y - size, size, size, (60, 120, 70), filled=True)

    def _draw_skier(self, buffer: NDArray[np.uint8], x: int, y: int) -> None:
        draw_rect(buffer, x - 2, y - 4, 4, 5, (40, 40, 60), filled=True)
        draw_line(buffer, x - 4, y + 4, x + 4, y + 2, (80, 80, 90))
        draw_line(buffer, x - 4, y + 6, x + 4, y + 4, (80, 80, 90))

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"SKII {int(self._score)}", 1, (180, 200, 220), scale=1)

    def get_lcd_text(self) -> str:
        return f"SKII {int(self._score)}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=int(self._score) >= 50,
            data={"score": int(self._score)},
            display_text=f"SCORE {int(self._score)}",
            ticker_text="SKII",
        )
        self.complete(result)

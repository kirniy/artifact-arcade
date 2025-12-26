"""Pong - Adapted from Mini-Games-with-Pygame Pong."""

import math
import random
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line, draw_circle
from artifact.graphics.text_utils import draw_centered_text


class PongMode(BaseMode):
    name = "pong"
    display_name = "PONG"
    description = "Classic pong duel"
    icon = "pong"
    style = "arcade"

    PADDLE_H = 24
    PADDLE_W = 4
    BALL_R = 2
    PLAYER_X = 8
    CPU_X = 128 - 8
    WIN_SCORE = 5

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._player_y = 64.0
        self._cpu_y = 64.0
        self._player_dir = 0
        self._player_dir_timer = 0.0
        self._ball_x = 64.0
        self._ball_y = 64.0
        self._ball_vx = 0.0
        self._ball_vy = 0.0
        self._ball_speed = 70.0
        self._serve_timer = 0.0
        self._score_player = 0
        self._score_cpu = 0
        self._game_over = False

    def on_enter(self) -> None:
        self._reset_match()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset_match(self) -> None:
        self._score_player = 0
        self._score_cpu = 0
        self._game_over = False
        self._reset_ball(serving_to_player=True)

    def _reset_ball(self, serving_to_player: bool) -> None:
        self._ball_x = 64.0
        self._ball_y = 64.0
        angle = random.uniform(-0.6, 0.6)
        direction = -1.0 if serving_to_player else 1.0
        self._ball_speed = 70.0
        self._ball_vx = math.cos(angle) * self._ball_speed * direction
        self._ball_vy = math.sin(angle) * self._ball_speed
        self._serve_timer = 800.0

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            if self._game_over:
                self._reset_match()
                return True
            if self._serve_timer > 0:
                self._serve_timer = 0.0
                return True

        if event.type == EventType.ARCADE_UP:
            self._player_dir = -1
            self._player_dir_timer = 160.0
            return True

        if event.type == EventType.ARCADE_DOWN:
            self._player_dir = 1
            self._player_dir_timer = 160.0
            return True

        if event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "8":
                self._player_dir = -1
                self._player_dir_timer = 160.0
                return True
            if key == "2":
                self._player_dir = 1
                self._player_dir_timer = 160.0
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        if self._game_over:
            return

        dt = delta_ms / 1000.0

        if self._serve_timer > 0:
            self._serve_timer = max(0.0, self._serve_timer - delta_ms)
            return

        # Player movement
        if self._player_dir_timer > 0:
            self._player_dir_timer = max(0.0, self._player_dir_timer - delta_ms)
        else:
            self._player_dir = 0

        self._player_y += self._player_dir * 90.0 * dt
        self._player_y = max(self.PADDLE_H / 2, min(128 - self.PADDLE_H / 2, self._player_y))

        # CPU movement
        target = self._ball_y
        if abs(target - self._cpu_y) > 2:
            step = 75.0 * dt
            if target > self._cpu_y:
                self._cpu_y += step
            else:
                self._cpu_y -= step
        self._cpu_y = max(self.PADDLE_H / 2, min(128 - self.PADDLE_H / 2, self._cpu_y))

        # Move ball
        self._ball_x += self._ball_vx * dt
        self._ball_y += self._ball_vy * dt

        # Wall bounce
        if self._ball_y <= self.BALL_R or self._ball_y >= 128 - self.BALL_R:
            self._ball_vy *= -1
            self._ball_y = max(self.BALL_R, min(128 - self.BALL_R, self._ball_y))

        # Paddle collisions
        self._check_paddle(self.PLAYER_X, self._player_y, is_left=True)
        self._check_paddle(self.CPU_X, self._cpu_y, is_left=False)

        # Score
        if self._ball_x < -4:
            self._score_cpu += 1
            self._reset_ball(serving_to_player=True)
        elif self._ball_x > 132:
            self._score_player += 1
            self._reset_ball(serving_to_player=False)

        if self._score_player >= self.WIN_SCORE or self._score_cpu >= self.WIN_SCORE:
            self._game_over = True

    def _check_paddle(self, px: int, py: float, is_left: bool) -> None:
        half_h = self.PADDLE_H / 2
        if is_left:
            if self._ball_x - self.BALL_R <= px + self.PADDLE_W:
                if abs(self._ball_y - py) <= half_h:
                    offset = (self._ball_y - py) / half_h
                    angle = offset * 0.7
                    self._ball_speed = min(140.0, self._ball_speed + 3.0)
                    self._ball_vx = math.cos(angle) * self._ball_speed
                    self._ball_vy = math.sin(angle) * self._ball_speed
                    self._ball_x = px + self.PADDLE_W + self.BALL_R
        else:
            if self._ball_x + self.BALL_R >= px - self.PADDLE_W:
                if abs(self._ball_y - py) <= half_h:
                    offset = (self._ball_y - py) / half_h
                    angle = math.pi - offset * 0.7
                    self._ball_speed = min(140.0, self._ball_speed + 3.0)
                    self._ball_vx = math.cos(angle) * self._ball_speed
                    self._ball_vy = math.sin(angle) * self._ball_speed
                    self._ball_x = px - self.PADDLE_W - self.BALL_R

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (8, 8, 12))

        # Center line
        for y in range(4, 124, 8):
            draw_rect(buffer, 62, y, 4, 4, (50, 50, 60), filled=True)

        # Paddles
        draw_rect(
            buffer,
            self.PLAYER_X,
            int(self._player_y - self.PADDLE_H / 2),
            self.PADDLE_W,
            self.PADDLE_H,
            (180, 220, 255),
            filled=True,
        )
        draw_rect(
            buffer,
            self.CPU_X - self.PADDLE_W,
            int(self._cpu_y - self.PADDLE_H / 2),
            self.PADDLE_W,
            self.PADDLE_H,
            (255, 160, 160),
            filled=True,
        )

        # Ball
        draw_circle(buffer, int(self._ball_x), int(self._ball_y), self.BALL_R, (240, 240, 240), filled=True)

        # Score
        draw_centered_text(buffer, f"{self._score_player}  {self._score_cpu}", 2, (220, 220, 220), scale=1)

        if self._serve_timer > 0 and not self._game_over:
            draw_centered_text(buffer, "PRESS", 58, (200, 200, 200), scale=1)

        if self._game_over:
            win = "YOU" if self._score_player > self._score_cpu else "CPU"
            draw_centered_text(buffer, f"WIN {win}", 52, (120, 240, 120), scale=2)
            draw_centered_text(buffer, "PRESS", 72, (220, 220, 220), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"PONG {self._score_player}:{self._score_cpu}", 1, (180, 220, 255), scale=1)

    def get_lcd_text(self) -> str:
        return f"PONG {self._score_player}-{self._score_cpu}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score_player > self._score_cpu,
            data={"player": self._score_player, "cpu": self._score_cpu},
            display_text=f"{self._score_player}:{self._score_cpu}",
            ticker_text="PONG",
        )
        self.complete(result)

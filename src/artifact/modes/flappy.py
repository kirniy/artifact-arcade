"""Flappy Bird - Adapted from Mini-Games-with-Pygame FlappyBird."""

import random
from typing import List, Dict

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_circle
from artifact.graphics.text_utils import draw_centered_text


class FlappyMode(BaseMode):
    name = "flappy"
    display_name = "FLAPPY"
    description = "Fly between the pipes"
    icon = "bird"
    style = "arcade"

    GRAVITY = 240.0
    FLAP = -120.0
    PIPE_SPEED = 40.0
    PIPE_GAP = 44
    PIPE_W = 14
    BIRD_X = 30
    BIRD_R = 4

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._bird_y = 64.0
        self._bird_vy = 0.0
        self._pipes: List[Dict[str, float]] = []
        self._spawn_timer = 0.0
        self._score = 0
        self._game_over = False

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._bird_y = 64.0
        self._bird_vy = 0.0
        self._pipes = []
        self._spawn_timer = 600.0
        self._score = 0
        self._game_over = False

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            if self._game_over:
                self._reset()
                return True
            self._bird_vy = self.FLAP
            return True

        if event.type == EventType.ARCADE_UP:
            if self._game_over:
                self._reset()
            else:
                self._bird_vy = self.FLAP
            return True

        if event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "5":
                if self._game_over:
                    self._reset()
                else:
                    self._bird_vy = self.FLAP
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return
        if self._game_over:
            return

        dt = delta_ms / 1000.0
        self._spawn_timer -= delta_ms
        if self._spawn_timer <= 0:
            gap_y = random.randint(24, 92)
            self._pipes.append({"x": 128.0, "gap_y": float(gap_y), "scored": False})
            self._spawn_timer = 1400.0

        # Update bird
        self._bird_vy += self.GRAVITY * dt
        self._bird_y += self._bird_vy * dt

        # Update pipes
        for pipe in self._pipes:
            pipe["x"] -= self.PIPE_SPEED * dt

        # Remove offscreen pipes
        self._pipes = [p for p in self._pipes if p["x"] > -self.PIPE_W]

        # Collision and scoring
        if self._bird_y < self.BIRD_R or self._bird_y > 124 - self.BIRD_R:
            self._game_over = True
            return

        for pipe in self._pipes:
            if self.BIRD_X + self.BIRD_R > pipe["x"] and self.BIRD_X - self.BIRD_R < pipe["x"] + self.PIPE_W:
                gap_top = pipe["gap_y"] - self.PIPE_GAP / 2
                gap_bottom = pipe["gap_y"] + self.PIPE_GAP / 2
                if self._bird_y - self.BIRD_R < gap_top or self._bird_y + self.BIRD_R > gap_bottom:
                    self._game_over = True
                    return

            if not pipe["scored"] and pipe["x"] + self.PIPE_W < self.BIRD_X - self.BIRD_R:
                pipe["scored"] = True
                self._score += 1

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (40, 80, 120))
        draw_rect(buffer, 0, 118, 128, 10, (60, 40, 20), filled=True)

        # Pipes
        for pipe in self._pipes:
            x = int(pipe["x"])
            gap_y = pipe["gap_y"]
            gap_top = int(gap_y - self.PIPE_GAP / 2)
            gap_bottom = int(gap_y + self.PIPE_GAP / 2)
            draw_rect(buffer, x, 0, self.PIPE_W, gap_top, (80, 200, 120), filled=True)
            draw_rect(buffer, x, gap_bottom, self.PIPE_W, 118 - gap_bottom, (80, 200, 120), filled=True)

        # Bird
        draw_circle(buffer, self.BIRD_X, int(self._bird_y), self.BIRD_R, (255, 220, 80), filled=True)
        draw_rect(buffer, self.BIRD_X + 2, int(self._bird_y) - 1, 2, 2, (20, 20, 20), filled=True)

        draw_centered_text(buffer, f"{self._score}", 2, (255, 255, 255), scale=1)

        if self._game_over:
            draw_centered_text(buffer, "GAME OVER", 52, (255, 80, 80), scale=1)
            draw_centered_text(buffer, "PRESS", 66, (220, 220, 220), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"FLAP {self._score}", 1, (255, 220, 80), scale=1)

    def get_lcd_text(self) -> str:
        return f"FLAPPY {self._score:02d}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 5,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="FLAPPY",
        )
        self.complete(result)

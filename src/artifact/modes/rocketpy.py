"""RocketPy - Adapted from scope-crepe/rocketpy."""

import math
import random
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_circle, draw_line
from artifact.graphics.text_utils import draw_centered_text


class RocketPyMode(BaseMode):
    name = "rocketpy"
    display_name = "ROCKET"
    description = "Dodge probes and grab coins"
    icon = "rocket"
    style = "arcade"

    ROCKET_W = 6
    ROCKET_H = 12
    GRAVITY = 120.0
    THRUST = 260.0
    BRAKE = 140.0
    MAX_V = 90.0
    LATERAL_SPEED = 90.0

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._started = False
        self._game_over = False
        self._rocket_x = 64.0
        self._rocket_y = 86.0
        self._rocket_vy = 0.0
        self._lateral_dir = 0
        self._lateral_timer = 0.0
        self._thrust_timer = 0.0
        self._brake_timer = 0.0
        self._probes: List[dict] = []
        self._coins: List[dict] = []
        self._probe_timer = 0.0
        self._coin_timer = 0.0
        self._next_probe = 900.0
        self._next_coin = 700.0
        self._dodged = 0
        self._coins_collected = 0
        self._score_time = 0.0
        self._stars = []

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._started = False
        self._game_over = False
        self._rocket_x = 64.0
        self._rocket_y = 86.0
        self._rocket_vy = 0.0
        self._lateral_dir = 0
        self._lateral_timer = 0.0
        self._thrust_timer = 0.0
        self._brake_timer = 0.0
        self._probes = []
        self._coins = []
        self._probe_timer = 0.0
        self._coin_timer = 0.0
        self._next_probe = 900.0
        self._next_coin = 700.0
        self._dodged = 0
        self._coins_collected = 0
        self._score_time = 0.0
        self._stars = [
            [random.randint(0, 127), random.randint(0, 127), random.uniform(12, 40)]
            for _ in range(30)
        ]

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            if self._game_over:
                self._reset()
                return True
            self._started = True
            self._thrust_timer = 140.0
            return True

        if event.type == EventType.ARCADE_LEFT:
            self._lateral_dir = -1
            self._lateral_timer = 200.0
            self._started = True
            return True
        if event.type == EventType.ARCADE_RIGHT:
            self._lateral_dir = 1
            self._lateral_timer = 200.0
            self._started = True
            return True
        if event.type == EventType.ARCADE_UP:
            self._thrust_timer = 140.0
            self._started = True
            return True
        if event.type == EventType.ARCADE_DOWN:
            self._brake_timer = 140.0
            self._started = True
            return True

        if event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "4":
                self._lateral_dir = -1
                self._lateral_timer = 200.0
                self._started = True
                return True
            if key == "6":
                self._lateral_dir = 1
                self._lateral_timer = 200.0
                self._started = True
                return True
            if key == "8":
                self._thrust_timer = 140.0
                self._started = True
                return True
            if key == "2":
                self._brake_timer = 140.0
                self._started = True
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        dt = delta_ms / 1000.0
        if not self._started:
            self._update_stars(dt, idle=True)
            return

        if self._game_over:
            self._update_stars(dt, idle=True)
            return

        self._score_time += delta_ms
        self._update_stars(dt, idle=False)

        self._lateral_timer = max(0.0, self._lateral_timer - delta_ms)
        self._thrust_timer = max(0.0, self._thrust_timer - delta_ms)
        self._brake_timer = max(0.0, self._brake_timer - delta_ms)

        if self._lateral_timer <= 0:
            self._lateral_dir = 0

        self._rocket_x += self._lateral_dir * self.LATERAL_SPEED * dt
        self._rocket_x = max(8.0, min(120.0, self._rocket_x))

        self._rocket_vy += self.GRAVITY * dt
        if self._thrust_timer > 0:
            self._rocket_vy -= self.THRUST * dt
        if self._brake_timer > 0:
            self._rocket_vy += self.BRAKE * dt

        self._rocket_vy = max(-self.MAX_V, min(self.MAX_V, self._rocket_vy))
        self._rocket_y += self._rocket_vy * dt
        self._rocket_y = max(10.0, min(118.0, self._rocket_y))

        self._probe_timer += delta_ms
        self._coin_timer += delta_ms
        if self._probe_timer >= self._next_probe:
            self._spawn_probe()
            self._probe_timer = 0.0
            self._next_probe = random.uniform(700.0, 1300.0)
        if self._coin_timer >= self._next_coin:
            self._spawn_coin()
            self._coin_timer = 0.0
            self._next_coin = random.uniform(500.0, 1000.0)

        self._update_probes(dt)
        self._update_coins(dt)

    def _update_stars(self, dt: float, idle: bool) -> None:
        speed = 12.0 if idle else 24.0
        for star in self._stars:
            star[1] += star[2] * dt * (speed / 20.0)
            if star[1] > 127:
                star[0] = random.randint(0, 127)
                star[1] = 0
                star[2] = random.uniform(12, 40)

    def _spawn_probe(self) -> None:
        side = random.choice([-1, 1])
        x = -6.0 if side == -1 else 134.0
        y = random.uniform(20.0, 108.0)
        speed = random.uniform(35.0, 70.0)
        vx = speed if side == -1 else -speed
        self._probes.append({"x": x, "y": y, "vx": vx, "r": random.randint(3, 5)})

    def _spawn_coin(self) -> None:
        x = random.uniform(14.0, 114.0)
        y = -8.0
        vy = random.uniform(30.0, 55.0)
        self._coins.append({"x": x, "y": y, "vy": vy, "r": 3})

    def _update_probes(self, dt: float) -> None:
        rocket_r = 6
        for probe in list(self._probes):
            probe["x"] += probe["vx"] * dt
            if probe["x"] < -12 or probe["x"] > 140:
                self._probes.remove(probe)
                self._dodged += 1
                continue
            if self._circle_hit(self._rocket_x, self._rocket_y, rocket_r, probe["x"], probe["y"], probe["r"] + 2):
                self._game_over = True
                return

    def _update_coins(self, dt: float) -> None:
        rocket_r = 5
        for coin in list(self._coins):
            coin["y"] += coin["vy"] * dt
            if coin["y"] > 140:
                self._coins.remove(coin)
                continue
            if self._circle_hit(self._rocket_x, self._rocket_y, rocket_r, coin["x"], coin["y"], coin["r"] + 2):
                self._coins_collected += 1
                self._coins.remove(coin)

    @staticmethod
    def _circle_hit(ax: float, ay: float, ar: float, bx: float, by: float, br: float) -> bool:
        return (ax - bx) ** 2 + (ay - by) ** 2 <= (ar + br) ** 2

    def _score(self) -> int:
        base = int(self._score_time / 200)
        return base + self._dodged * 5 + self._coins_collected * 8

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (6, 8, 14))

        for sx, sy, _speed in self._stars:
            if 0 <= int(sy) < 128:
                buffer[int(sy), int(sx)] = (150, 160, 180)

        for probe in self._probes:
            draw_circle(buffer, int(probe["x"]), int(probe["y"]), probe["r"], (200, 120, 200), filled=True)

        for coin in self._coins:
            draw_circle(buffer, int(coin["x"]), int(coin["y"]), coin["r"], (255, 220, 100), filled=True)
            draw_circle(buffer, int(coin["x"]), int(coin["y"]), coin["r"] - 1, (200, 120, 20), filled=False)

        self._render_rocket(buffer)

        draw_centered_text(buffer, f"SCORE {self._score()}", 1, (220, 220, 220), scale=1)

        if not self._started:
            draw_centered_text(buffer, "PRESS", 54, (200, 200, 200), scale=1)
            draw_centered_text(buffer, "TO LAUNCH", 66, (200, 200, 200), scale=1)

        if self._game_over:
            draw_centered_text(buffer, "CRASH", 52, (255, 80, 80), scale=2)
            draw_centered_text(buffer, "PRESS", 72, (220, 220, 220), scale=1)

    def _render_rocket(self, buffer: NDArray[np.uint8]) -> None:
        x = int(self._rocket_x - self.ROCKET_W / 2)
        y = int(self._rocket_y - self.ROCKET_H / 2)
        draw_rect(buffer, x, y, self.ROCKET_W, self.ROCKET_H, (200, 220, 255), filled=True)
        draw_rect(buffer, x + 1, y - 2, self.ROCKET_W - 2, 2, (255, 120, 120), filled=True)
        draw_rect(buffer, x - 1, y + 4, 2, 4, (160, 170, 200), filled=True)
        draw_rect(buffer, x + self.ROCKET_W - 1, y + 4, 2, 4, (160, 170, 200), filled=True)
        if self._thrust_timer > 0 and not self._game_over:
            draw_rect(buffer, x + 2, y + self.ROCKET_H, 2, 3, (255, 160, 40), filled=True)
            draw_rect(buffer, x + 1, y + self.ROCKET_H + 2, 4, 2, (255, 220, 120), filled=True)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"ROCKET {self._score()}", 1, (200, 220, 255), scale=1)

    def get_lcd_text(self) -> str:
        return f"ROCKET {self._score()}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score() > 50,
            data={"score": self._score()},
            display_text=f"SCORE {self._score()}",
            ticker_text="ROCKET",
        )
        self.complete(result)

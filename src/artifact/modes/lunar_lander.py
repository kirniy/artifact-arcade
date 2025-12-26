"""Lunar Lander - Adapted from ternus/pygame-examples lunarlander."""

from __future__ import annotations

import math
import random
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_line, draw_rect, draw_circle
from artifact.graphics.text_utils import draw_centered_text


class LunarLanderMode(BaseMode):
    name = "lunar_lander"
    display_name = "LANDER"
    description = "Land softly on the pad"
    icon = "moon"
    style = "arcade"

    GRAVITY = 70.0
    THRUST = 150.0
    ROT_STEP = 8.0
    MAX_SPEED = 120.0
    GROUND_Y = 118
    PAD_W = 30
    PAD_H = 4

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._ship_x = 64.0
        self._ship_y = 20.0
        self._ship_vx = 0.0
        self._ship_vy = 0.0
        self._angle = 0.0
        self._fuel = 100.0
        self._thrust_timer = 0.0
        self._stars: List[Tuple[int, int]] = []
        self._boulders: List[Tuple[int, int, int]] = []
        self._pad_x = 48
        self._crashed = False
        self._landed = False
        self._score = 0

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._ship_x = 64.0
        self._ship_y = 16.0
        self._ship_vx = 0.0
        self._ship_vy = 0.0
        self._angle = 0.0
        self._fuel = 100.0
        self._thrust_timer = 0.0
        self._crashed = False
        self._landed = False
        self._pad_x = random.randint(16, 128 - 16 - self.PAD_W)
        self._stars = [(random.randint(2, 126), random.randint(2, 70)) for _ in range(24)]
        self._boulders = []
        for _ in range(2):
            bx = random.randint(10, 118)
            br = random.randint(6, 10)
            self._boulders.append((bx, self.GROUND_Y - br, br))

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            if self._crashed or self._landed:
                self._reset()
                return True
            self._thrust_timer = 120.0
            return True

        if event.type == EventType.ARCADE_UP:
            self._thrust_timer = 120.0
            return True

        if event.type == EventType.ARCADE_LEFT:
            self._angle = (self._angle - self.ROT_STEP) % 360.0
            return True

        if event.type == EventType.ARCADE_RIGHT:
            self._angle = (self._angle + self.ROT_STEP) % 360.0
            return True

        if event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "8":
                self._thrust_timer = 120.0
                return True
            if key == "4":
                self._angle = (self._angle - self.ROT_STEP) % 360.0
                return True
            if key == "6":
                self._angle = (self._angle + self.ROT_STEP) % 360.0
                return True
            if key == "5" and (self._crashed or self._landed):
                self._reset()
                return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        if self._crashed or self._landed:
            return

        dt = delta_ms / 1000.0
        self._thrust_timer = max(0.0, self._thrust_timer - delta_ms)

        # Thrust
        if self._thrust_timer > 0.0 and self._fuel > 0.0:
            angle_rad = math.radians(self._angle)
            ax = math.sin(angle_rad) * self.THRUST
            ay = -math.cos(angle_rad) * self.THRUST
            self._ship_vx += ax * dt
            self._ship_vy += ay * dt
            self._fuel = max(0.0, self._fuel - 20.0 * dt)

        # Gravity
        self._ship_vy += self.GRAVITY * dt

        # Clamp velocities
        self._ship_vx = max(-self.MAX_SPEED, min(self.MAX_SPEED, self._ship_vx))
        self._ship_vy = max(-self.MAX_SPEED, min(self.MAX_SPEED, self._ship_vy))

        # Update position
        self._ship_x += self._ship_vx * dt
        self._ship_y += self._ship_vy * dt

        # Keep within screen bounds
        self._ship_x = max(6.0, min(122.0, self._ship_x))
        self._ship_y = max(6.0, min(130.0, self._ship_y))

        # Collision with boulders
        for bx, by, br in self._boulders:
            dist = math.hypot(self._ship_x - bx, self._ship_y - by)
            if dist <= br + 4:
                self._crashed = True
                return

        # Check landing / crash on ground
        if self._ship_y >= self.GROUND_Y - 2:
            on_pad = self._pad_x <= self._ship_x <= (self._pad_x + self.PAD_W)
            safe_angle = (self._angle <= 10.0) or (self._angle >= 350.0)
            safe_speed = abs(self._ship_vy) < 22.0 and abs(self._ship_vx) < 18.0
            if on_pad and safe_angle and safe_speed:
                self._landed = True
                self._score += 1
            else:
                self._crashed = True

    def _ship_points(self) -> List[Tuple[int, int]]:
        angle_rad = math.radians(self._angle)
        base = [(0, -7), (-5, 5), (5, 5)]
        points: List[Tuple[int, int]] = []
        for x, y in base:
            rx = x * math.cos(angle_rad) - y * math.sin(angle_rad)
            ry = x * math.sin(angle_rad) + y * math.cos(angle_rad)
            points.append((int(self._ship_x + rx), int(self._ship_y + ry)))
        return points

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (6, 10, 18))

        # Stars
        for sx, sy in self._stars:
            if 0 <= sx < 128 and 0 <= sy < 128:
                buffer[sy, sx] = (200, 200, 200)

        # Ground
        draw_rect(buffer, 0, self.GROUND_Y, 128, 128 - self.GROUND_Y, (20, 18, 16), filled=True)
        draw_rect(buffer, self._pad_x, self.GROUND_Y - self.PAD_H, self.PAD_W, self.PAD_H, (200, 160, 80), filled=True)

        # Boulders
        for bx, by, br in self._boulders:
            draw_circle(buffer, bx, by, br, (80, 80, 80), filled=True)

        # Ship
        p1, p2, p3 = self._ship_points()
        draw_line(buffer, p1[0], p1[1], p2[0], p2[1], (220, 220, 220))
        draw_line(buffer, p2[0], p2[1], p3[0], p3[1], (220, 220, 220))
        draw_line(buffer, p3[0], p3[1], p1[0], p1[1], (220, 220, 220))

        if self._thrust_timer > 0.0 and self._fuel > 0.0 and not (self._crashed or self._landed):
            angle_rad = math.radians(self._angle)
            fx = -math.sin(angle_rad) * 6
            fy = math.cos(angle_rad) * 6
            tail_x = int(self._ship_x + fx)
            tail_y = int(self._ship_y + fy)
            draw_line(buffer, tail_x, tail_y, tail_x + int(fx * 0.6), tail_y + int(fy * 0.6), (255, 120, 40))

        # HUD
        draw_centered_text(buffer, f"FUEL {int(self._fuel):03d}", 1, (200, 200, 200), scale=1)

        if self._crashed:
            draw_centered_text(buffer, "CRASH", 52, (255, 80, 80), scale=2)
            draw_centered_text(buffer, "PRESS", 72, (220, 220, 220), scale=1)
        elif self._landed:
            draw_centered_text(buffer, "LANDED", 52, (120, 240, 120), scale=2)
            draw_centered_text(buffer, "PRESS", 72, (220, 220, 220), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"LAND {self._score}", 1, (200, 160, 80), scale=1)

    def get_lcd_text(self) -> str:
        status = "OK"
        if self._crashed:
            status = "CRASH"
        elif self._landed:
            status = "LAND"
        return f"LANDER {status}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._landed,
            data={"score": self._score},
            display_text="LANDED" if self._landed else "CRASH",
            ticker_text="LANDER",
        )
        self.complete(result)

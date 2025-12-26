"""Ninja Fruit - Adapted from Ninja-Fruit-Like-Game-with-hand-gesture-and-opencv."""

import math
import random
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_circle, draw_line
from artifact.graphics.text_utils import draw_centered_text
from artifact.utils.camera_service import camera_service


class NinjaFruitMode(BaseMode):
    name = "ninja_fruit"
    display_name = "NINJA"
    description = "Slice the fruit with your hand"
    icon = "ninja"
    style = "arcade"
    requires_camera = True

    GRAVITY = 120.0
    SPAWN_MIN = 420.0
    SPAWN_MAX = 900.0
    FRUIT_RADIUS = 6

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._fruits: List[dict] = []
        self._particles: List[dict] = []
        self._spawn_timer = 0.0
        self._next_spawn = 600.0
        self._score = 0
        self._lives = 3
        self._game_over = False
        self._finger_pos: Optional[Tuple[float, float]] = None
        self._finger_prev: Optional[Tuple[float, float]] = None
        self._trail: List[Tuple[int, int]] = []

    def on_enter(self) -> None:
        self._reset()
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def _reset(self) -> None:
        self._fruits = []
        self._particles = []
        self._spawn_timer = 0.0
        self._next_spawn = random.uniform(self.SPAWN_MIN, self.SPAWN_MAX)
        self._score = 0
        self._lives = 3
        self._game_over = False
        self._finger_pos = None
        self._finger_prev = None
        self._trail = []

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS and self._game_over:
            self._reset()
            return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return
        if self._game_over:
            return

        dt = delta_ms / 1000.0
        self._spawn_timer += delta_ms

        if self._spawn_timer >= self._next_spawn:
            self._spawn_timer = 0.0
            self._next_spawn = random.uniform(self.SPAWN_MIN, self.SPAWN_MAX)
            self._spawn_fruits()

        self._update_fruits(dt)
        self._update_particles(dt)
        self._update_finger_trail()

    def _spawn_fruits(self) -> None:
        count = 2 if random.random() < 0.25 else 1
        for _ in range(count):
            is_bomb = random.random() < 0.12
            x = random.uniform(20.0, 108.0)
            y = 138.0
            vx = random.uniform(-30.0, 30.0)
            vy = random.uniform(-110.0, -80.0)
            self._fruits.append({
                "x": x,
                "y": y,
                "vx": vx,
                "vy": vy,
                "r": self.FRUIT_RADIUS,
                "bomb": is_bomb,
                "sliced": False,
            })

    def _update_fruits(self, dt: float) -> None:
        self._update_finger_position()
        for fruit in list(self._fruits):
            fruit["vy"] += self.GRAVITY * dt
            fruit["x"] += fruit["vx"] * dt
            fruit["y"] += fruit["vy"] * dt

            if fruit["y"] > 150:
                if not fruit["sliced"] and not fruit["bomb"]:
                    self._lives -= 1
                    if self._lives <= 0:
                        self._game_over = True
                self._fruits.remove(fruit)
                continue

            if not fruit["sliced"] and self._finger_prev and self._finger_pos:
                if self._segment_hit(
                    self._finger_prev,
                    self._finger_pos,
                    (fruit["x"], fruit["y"]),
                    fruit["r"] + 2
                ):
                    fruit["sliced"] = True
                    if fruit["bomb"]:
                        self._game_over = True
                        return
                    self._score += 1
                    self._spawn_slice_particles(fruit)
                    self._fruits.remove(fruit)

    def _update_particles(self, dt: float) -> None:
        for part in list(self._particles):
            part["life"] -= dt
            part["x"] += part["vx"] * dt
            part["y"] += part["vy"] * dt
            part["vy"] += 40.0 * dt
            if part["life"] <= 0:
                self._particles.remove(part)

    def _update_finger_position(self) -> None:
        overlay = camera_service.get_hand_overlay()
        if overlay is not None:
            _bbox, landmarks = overlay
            if len(landmarks) <= 8:
                self._finger_prev = None
                self._finger_pos = None
                return
            fx, fy = landmarks[8]
            x = float(fx * 128)
            y = float(fy * 128)
            self._finger_prev = self._finger_pos
            self._finger_pos = (x, y)
            return

        motion_x, confidence = camera_service.get_motion_position()
        motion_bbox = camera_service.get_motion_overlay()
        if motion_bbox is None or confidence < 0.05:
            self._finger_prev = None
            self._finger_pos = None
            return
        x1, y1, x2, y2 = motion_bbox
        x = float(motion_x * 128)
        y = float(((y1 + y2) * 0.5) * 128)
        self._finger_prev = self._finger_pos
        self._finger_pos = (x, y)

    def _update_finger_trail(self) -> None:
        if self._finger_pos is None:
            self._trail = []
            return
        self._trail.append((int(self._finger_pos[0]), int(self._finger_pos[1])))
        if len(self._trail) > 10:
            self._trail.pop(0)

    def _spawn_slice_particles(self, fruit: dict) -> None:
        for _ in range(8):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(20.0, 60.0)
            self._particles.append({
                "x": fruit["x"],
                "y": fruit["y"],
                "vx": math.cos(angle) * speed,
                "vy": math.sin(angle) * speed,
                "life": random.uniform(0.3, 0.6),
                "color": (255, 200, 120),
            })

    @staticmethod
    def _segment_hit(p1: Tuple[float, float], p2: Tuple[float, float], center: Tuple[float, float], radius: float) -> bool:
        ax, ay = p1
        bx, by = p2
        cx, cy = center
        dx = bx - ax
        dy = by - ay
        if dx == 0 and dy == 0:
            return (ax - cx) ** 2 + (ay - cy) ** 2 <= radius ** 2
        t = ((cx - ax) * dx + (cy - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        px = ax + t * dx
        py = ay + t * dy
        return (px - cx) ** 2 + (py - cy) ** 2 <= radius ** 2

    def _render_camera_background(self, buffer: NDArray[np.uint8]) -> None:
        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            dimmed = (frame.astype(np.float32) * 0.9).astype(np.uint8)
            np.copyto(buffer, dimmed)
        else:
            fill(buffer, (8, 8, 12))

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        self._render_camera_background(buffer)
        self._render_hand_overlay(buffer)

        for fruit in self._fruits:
            if fruit["bomb"]:
                draw_circle(buffer, int(fruit["x"]), int(fruit["y"]), fruit["r"], (180, 60, 60), filled=True)
                draw_line(buffer, int(fruit["x"] - 3), int(fruit["y"] - 3), int(fruit["x"] + 3), int(fruit["y"] + 3), (20, 20, 20))
                draw_line(buffer, int(fruit["x"] - 3), int(fruit["y"] + 3), int(fruit["x"] + 3), int(fruit["y"] - 3), (20, 20, 20))
            else:
                draw_circle(buffer, int(fruit["x"]), int(fruit["y"]), fruit["r"], (255, 180, 80), filled=True)
                draw_circle(buffer, int(fruit["x"]), int(fruit["y"]), fruit["r"] - 2, (200, 120, 40), filled=False)

        for part in self._particles:
            draw_rect(buffer, int(part["x"]), int(part["y"]), 2, 2, part["color"], filled=True)

        if len(self._trail) > 1:
            for i in range(1, len(self._trail)):
                x1, y1 = self._trail[i - 1]
                x2, y2 = self._trail[i]
                draw_line(buffer, x1, y1, x2, y2, (200, 255, 255))

        draw_centered_text(buffer, f"SCORE {self._score}", 1, (240, 240, 240), scale=1)
        draw_centered_text(buffer, f"LIVES {self._lives}", 10, (240, 200, 200), scale=1)

        if self._game_over:
            draw_centered_text(buffer, "GAME OVER", 52, (255, 80, 80), scale=1)
            draw_centered_text(buffer, "PRESS", 66, (220, 220, 220), scale=1)

    def _render_hand_overlay(self, buffer: NDArray[np.uint8]) -> None:
        overlay = camera_service.get_hand_overlay()
        if overlay is not None:
            bbox, landmarks = overlay
            x1, y1, x2, y2 = bbox
            px1 = int(x1 * 128)
            py1 = int(y1 * 128)
            px2 = int(x2 * 128)
            py2 = int(y2 * 128)
            draw_rect(buffer, px1, py1, max(1, px2 - px1), max(1, py2 - py1), (80, 255, 120), filled=False)

            for idx in (4, 8, 12, 16, 20):
                if idx < len(landmarks):
                    lx, ly = landmarks[idx]
                    draw_rect(buffer, int(lx * 128) - 1, int(ly * 128) - 1, 3, 3, (255, 255, 255), filled=True)
            return

        motion_bbox = camera_service.get_motion_overlay()
        if motion_bbox is None:
            return
        x1, y1, x2, y2 = motion_bbox
        px1 = int(x1 * 128)
        py1 = int(y1 * 128)
        px2 = int(x2 * 128)
        py2 = int(y2 * 128)
        draw_rect(buffer, px1, py1, max(1, px2 - px1), max(1, py2 - py1), (100, 180, 255), filled=False)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        draw_centered_text(buffer, f"NINJA {self._score}", 1, (255, 200, 120), scale=1)

    def get_lcd_text(self) -> str:
        return f"NINJA {self._score}".center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 5,
            data={"score": self._score},
            display_text=f"SCORE {self._score}",
            ticker_text="NINJA",
        )
        self.complete(result)

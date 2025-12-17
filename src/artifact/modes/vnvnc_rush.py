"""VNVNC RUSH - Dopamine micro-game.

Tap START when the pulse hits the hot zone, rack up streaks, and chase
the high score. Bright colors, juicy sounds, casino-like pacing.
"""

import math
import random
from typing import List
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import (
    draw_centered_text,
    draw_animated_text,
    TextEffect,
)


@dataclass
class TargetWindow:
    """A timing window to hit."""
    pos: float       # 0..1 along the track
    width: float     # 0..1 width
    life_ms: float   # remaining life
    value: int       # points for hit


class VNVNCRushMode(BaseMode):
    """Arcade dopamine hit: nail the pulse, keep the streak alive."""

    name = "vnvnc_rush"
    display_name = "RUSH"
    icon = "rush"
    style = "arcade"
    description = "Ударь по импульсу, держи серию, сорви джекпот"
    estimated_duration = 25

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._phase = ModePhase.INTRO
        self._time_left = 25000  # ms
        self._score = 0
        self._streak = 0
        self._best_streak = 0
        self._marker_pos = 0.5
        self._marker_vel = 0.35  # units per second
        self._targets: List[TargetWindow] = []
        self._spawn_cooldown = 0.0
        self._flash_timer = 0.0
        self._total_time = 0.0  # Total time elapsed for animations

    def on_enter(self) -> None:
        self._phase = ModePhase.INTRO
        self._time_left = 25000
        self._score = 0
        self._streak = 0
        self._best_streak = 0
        self._marker_pos = 0.5
        self._marker_vel = 0.35
        self._targets = []
        self._spawn_cooldown = 0.0
        self._flash_timer = 0.0
        self._total_time = 0.0
        self.change_phase(ModePhase.ACTIVE)
        self._spawn_target()

    def on_exit(self) -> None:
        pass

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if event.type == EventType.BUTTON_PRESS:
            hit = self._check_hit()
            if hit:
                self._score += hit.value
                self._streak += 1
                self._best_streak = max(self._best_streak, self._streak)
                self._flash_timer = 200
                if self.context.animation_engine:
                    self.context.animation_engine.trigger("celebrate", duration=400)
                self.context.audio.play_success()
            else:
                self._streak = 0
                self.context.audio.play_ui_error()
            return True

        elif event.type == EventType.ARCADE_LEFT:
            # Nudge marker left
            self._marker_vel -= 0.05
            self.context.audio.play_ui_move()
            return True

        elif event.type == EventType.ARCADE_RIGHT:
            # Nudge marker right
            self._marker_vel += 0.05
            self.context.audio.play_ui_move()
            return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        dt = delta_ms / 1000.0
        self._time_left -= delta_ms
        self._total_time += delta_ms
        if self._time_left <= 0:
            self._complete()
            return

        # Update marker
        self._marker_pos += self._marker_vel * dt
        if self._marker_pos < 0:
            self._marker_pos = 0
            self._marker_vel *= -0.85
        elif self._marker_pos > 1:
            self._marker_pos = 1
            self._marker_vel *= -0.85

        # Friction toward base speed
        self._marker_vel += (0.35 - self._marker_vel) * 0.05

        # Spawn targets regularly
        self._spawn_cooldown -= delta_ms
        if self._spawn_cooldown <= 0:
            self._spawn_target()

        # Update targets
        for tgt in self._targets:
            tgt.life_ms -= delta_ms
            tgt.width = max(0.06, tgt.width * 0.997)  # shrink slowly
        self._targets = [t for t in self._targets if t.life_ms > 0]

        # Flash decay
        self._flash_timer = max(0.0, self._flash_timer - delta_ms)

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        t = self._total_time

        # Background gradient pulse
        base = int(40 + 20 * math.sin(t / 300))
        fill(buffer, (base, base // 2, base + 10))

        # Flash overlay on hit
        if self._flash_timer > 0:
            alpha = min(180, int(255 * (self._flash_timer / 200)))
            buffer[:] = np.clip(buffer.astype(np.int16) + alpha, 0, 255).astype(np.uint8)

        # Track
        track_y = 72
        draw_rect(buffer, 10, track_y - 6, 108, 12, (10, 10, 20))

        # Targets
        for tgt in self._targets:
            x = int(10 + tgt.pos * 108)
            w = int(tgt.width * 108)
            col = (255, 180, 80) if tgt.value > 50 else (200, 120, 255)
            draw_rect(buffer, x - w // 2, track_y - 8, w, 16, col, filled=True)

        # Marker
        marker_x = int(10 + self._marker_pos * 108)
        draw_rect(buffer, marker_x - 2, track_y - 10, 4, 20, (0, 255, 180))

        # Score / streak
        draw_centered_text(buffer, f"СЧЁТ {self._score:04d}", 6, (255, 255, 255), scale=1)
        streak_text = f"СЕРИЯ {self._streak}x"
        draw_centered_text(buffer, streak_text, 20, (255, 210, 120), scale=1)

        # Timer bar
        time_pct = max(0.0, min(1.0, self._time_left / 25000))
        bar_w = int(108 * time_pct)
        draw_rect(buffer, 10, 118, 108, 6, (30, 30, 40))
        draw_rect(buffer, 10, 118, bar_w, 6, (0, 200, 120))

        # Prompt
        draw_animated_text(buffer, "ЖМИ СТАРТ", 100, (255, 255, 255), t, TextEffect.PULSE, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        from artifact.graphics.primitives import clear
        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect

        clear(buffer)
        text = f"РЕКОРД {self._best_streak}x · СЧЁТ {self._score}"
        render_ticker_animated(buffer, text, self._time_left, (255, 200, 0), TickerEffect.PULSE_SCROLL, speed=0.03)

    def get_lcd_text(self) -> str:
        return f"RUSH {self._score:04d}"[:16]

    def _spawn_target(self) -> None:
        pos = random.uniform(0.15, 0.85)
        width = random.uniform(0.08, 0.16)
        life = random.uniform(1600, 2600)
        value = 100 if width < 0.1 else 50
        self._targets.append(TargetWindow(pos=pos, width=width, life_ms=life, value=value))
        self._spawn_cooldown = random.uniform(500, 900)

    def _check_hit(self) -> TargetWindow | None:
        for tgt in list(self._targets):
            if abs(self._marker_pos - tgt.pos) <= tgt.width / 2:
                self._targets.remove(tgt)
                return tgt
        return None

    def _complete(self) -> None:
        self.phase = ModePhase.RESULT
        result = ModeResult(
            mode_name=self.name,
            success=True,
            data={
                "score": self._score,
                "streak": self._best_streak,
            },
            display_text=f"СЧЁТ {self._score} · СЕРИЯ {self._best_streak}x",
            ticker_text="СПАСИБО ЗА ИГРУ",
            lcd_text="RUSH ГОТОВО",
            should_print=False,
        )
        self.complete(result)

"""Brick Breaker - Camera-controlled classic arcade game.

Use your hand or body movement to control the paddle and break all the bricks!
The camera tracks horizontal motion to move the paddle left/right.
Neon arcade visuals with chiptune energy.
"""

import math
import random
import logging
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import draw_rect, draw_circle, draw_line
from artifact.graphics.text_utils import draw_centered_text, hsv_to_rgb

logger = logging.getLogger(__name__)


# Game constants
SCREEN_W, SCREEN_H = 128, 128
PADDLE_WIDTH = 32
PADDLE_HEIGHT = 5
PADDLE_Y = 118
BALL_RADIUS = 3
BRICK_ROWS = 5
BRICK_COLS = 8
BRICK_WIDTH = 14
BRICK_HEIGHT = 6
BRICK_TOP_OFFSET = 20
INITIAL_LIVES = 10
MAX_MISSES = 8  # Lose if you miss this many times in a row


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    speed: float = 0.9
    trail: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class Brick:
    x: int
    y: int
    width: int
    height: int
    color: Tuple[int, int, int]
    hits: int = 1
    destroyed: bool = False


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: Tuple[int, int, int]
    life: float
    size: float


@dataclass
class PowerUp:
    x: float
    y: float
    type: str  # "wide", "multi", "slow", "life"
    vy: float = 1.0
    pulse: float = 0.0


class BrickBreakerMode(BaseMode):
    """Camera-controlled Brick Breaker game with neon arcade visuals."""

    name = "brick_breaker"
    display_name = "КИРПИЧИ"
    description = "Разбей все кирпичи движением руки!"
    icon = "🧱"
    style = "arcade"
    requires_camera = True
    requires_ai = False
    estimated_duration = 120

    def __init__(self, context: ModeContext):
        super().__init__(context)

        # Use shared camera service (no more opening/closing!)
        self._motion_x = 0.5  # Normalized 0-1 position
        self._prev_motion_x = 0.5

        # Game state
        self.paddle_x = SCREEN_W // 2
        self.paddle_width = PADDLE_WIDTH
        self.balls: List[Ball] = []
        self.bricks: List[Brick] = []
        self.particles: List[Particle] = []
        self.powerups: List[PowerUp] = []

        self.score = 0
        self.lives = INITIAL_LIVES
        self.level = 1
        self.combo = 0
        self.max_combo = 0
        self.miss_count = 0  # Track consecutive misses

        # Animation state
        self._intro_time = 0.0
        self._game_over = False
        self._win = False
        self._paddle_vx = 0.0
        self._shake_timer = 0.0
        self._shake_intensity = 0.0
        self._flash_timer = 0.0
        self._manual_control_x = 0.5
        self._manual_control_timer = 0.0
        self._control_x = 0.5
        self._control_source = "motion"
        self._control_confidence = 0.0
        self._outro_time = 0.0
        self._paddle_vx = 0.0
        self._shake_timer = 0.0
        self._shake_intensity = 0.0
        self._flash_timer = 0.0
        self._flash_color = (255, 255, 255)
        self._manual_control_x = 0.5
        self._manual_control_timer = 0.0
        self._control_x = 0.5
        self._control_source = "motion"
        self._control_confidence = 0.0

        # Colors
        self.paddle_color = (20, 184, 166)  # Teal
        self.ball_color = (251, 191, 36)  # Gold
        self.bg_color = (15, 10, 30)

    def on_enter(self) -> None:
        """Initialize game."""
        self._reset_game()
        self._intro_time = 0.0
        self.change_phase(ModePhase.INTRO)

    def _reset_game(self) -> None:
        """Reset game state for new game."""
        self.paddle_x = SCREEN_W // 2
        self.paddle_width = PADDLE_WIDTH
        self.balls = []
        self.bricks = []
        self.particles = []
        self.powerups = []
        self.score = 0
        self.lives = INITIAL_LIVES
        self.combo = 0
        self.max_combo = 0
        self.miss_count = 0
        self._game_over = False
        self._win = False

        # Create initial ball
        self._spawn_ball()

        # Create bricks
        self._create_level()

    def _spawn_ball(self) -> None:
        """Spawn a new ball on the paddle."""
        angle = random.uniform(-0.5, 0.5) + math.pi * 1.5  # Upward with slight random
        speed = 0.7 + self.level * 0.03  # Slower ball speed
        self.balls.append(Ball(
            x=self.paddle_x,
            y=PADDLE_Y - 5,
            vx=math.cos(angle) * speed,
            vy=math.sin(angle) * speed,
            speed=speed
        ))

    def _create_level(self) -> None:
        """Create bricks for current level."""
        self.bricks = []
        start_x = (SCREEN_W - BRICK_COLS * (BRICK_WIDTH + 1)) // 2

        for row in range(BRICK_ROWS):
            for col in range(BRICK_COLS):
                # Skip some bricks randomly for variety
                if self.level > 1 and random.random() < 0.15:
                    continue

                x = start_x + col * (BRICK_WIDTH + 1)
                y = BRICK_TOP_OFFSET + row * (BRICK_HEIGHT + 1)

                # Color based on row
                hue = (row * 40 + self.level * 30) % 360
                color = hsv_to_rgb(hue, 0.8, 0.9)

                # Some bricks take multiple hits
                hits = 2 if row < 2 and random.random() < 0.3 else 1

                self.bricks.append(Brick(
                    x=x, y=y,
                    width=BRICK_WIDTH, height=BRICK_HEIGHT,
                    color=color, hits=hits
                ))

    def _update_camera(self, delta_ms: float) -> None:
        """Update paddle position from shared camera service."""
        from artifact.utils.camera_service import camera_service

        self._manual_control_timer = max(0.0, self._manual_control_timer - delta_ms)

        hand = camera_service.get_hand_position()
        if hand is not None:
            new_motion, confidence = hand
            self._control_source = "hand"
        else:
            new_motion, confidence = camera_service.get_motion_position()
            self._control_source = "motion"

        if self._manual_control_timer > 0:
            self._control_source = "manual"
            if hand is not None:
                new_motion = self._manual_control_x * 0.85 + new_motion * 0.15
            else:
                new_motion = self._manual_control_x
            confidence = max(confidence, 0.6)

        self._control_x = new_motion
        self._control_confidence = confidence

        # Smooth the movement
        alpha = 0.25 if confidence > 0.4 else 0.18
        self._motion_x = self._prev_motion_x * (1 - alpha) + new_motion * alpha
        self._prev_motion_x = self._motion_x

    def _manual_nudge(self, delta: float) -> None:
        if self._manual_control_timer <= 0:
            self._manual_control_x = self._motion_x
        self._manual_control_x = max(0.0, min(1.0, self._manual_control_x + delta))
        self._manual_control_timer = 900.0

    def on_update(self, delta_ms: float) -> None:
        """Update game state."""
        dt = delta_ms / 1000.0

        if self.phase == ModePhase.INTRO:
            self._intro_time += delta_ms
            if self._intro_time > 2000:
                self.change_phase(ModePhase.ACTIVE)
            return

        if self.phase == ModePhase.OUTRO:
            self._outro_time += delta_ms
            if self._outro_time > 3000:
                self._finish_game()
            return

        if self.phase != ModePhase.ACTIVE:
            return

        # Update camera and paddle
        self._update_camera(delta_ms)

        # Smooth paddle following (invert motion_x so paddle follows hand direction)
        prev_x = self.paddle_x
        target_x = int((1.0 - self._motion_x) * SCREEN_W)
        target_x = max(self.paddle_width // 2, min(SCREEN_W - self.paddle_width // 2, target_x))
        self.paddle_x += (target_x - self.paddle_x) * 0.2
        if dt > 0:
            self._paddle_vx = (self.paddle_x - prev_x) / dt
            self._paddle_vx = max(-320.0, min(320.0, self._paddle_vx))

        # Update balls
        self._update_balls(dt)

        # Update particles
        self._update_particles(dt)

        # Update powerups
        self._update_powerups(dt)

        # Impact timers
        self._shake_timer = max(0.0, self._shake_timer - delta_ms)
        self._flash_timer = max(0.0, self._flash_timer - delta_ms)
        if self._shake_timer == 0.0:
            self._shake_intensity = 0.0

        # Check win condition
        active_bricks = [b for b in self.bricks if not b.destroyed]
        if len(active_bricks) == 0:
            self._win = True
            self.change_phase(ModePhase.OUTRO)
            self._outro_time = 0.0

        # Check lose condition - either no lives OR too many misses
        if (len(self.balls) == 0 and self.lives <= 0) or self.miss_count >= MAX_MISSES:
            self._game_over = True
            self.change_phase(ModePhase.OUTRO)
            self._outro_time = 0.0

    def _update_balls(self, dt: float) -> None:
        """Update ball positions and collisions."""
        for ball in self.balls[:]:
            # Store trail
            ball.trail.append((ball.x, ball.y))
            if len(ball.trail) > 5:
                ball.trail.pop(0)

            # Move ball
            ball.x += ball.vx * 60 * dt
            ball.y += ball.vy * 60 * dt

            # Wall collisions
            if ball.x <= BALL_RADIUS:
                ball.x = BALL_RADIUS
                ball.vx = abs(ball.vx)
            elif ball.x >= SCREEN_W - BALL_RADIUS:
                ball.x = SCREEN_W - BALL_RADIUS
                ball.vx = -abs(ball.vx)

            if ball.y <= BALL_RADIUS:
                ball.y = BALL_RADIUS
                ball.vy = abs(ball.vy)

            # Ball lost
            if ball.y > SCREEN_H + BALL_RADIUS:
                self.balls.remove(ball)
                self.combo = 0
                self.miss_count += 1  # Track misses!
                self._flash_timer = 180
                self._flash_color = (255, 60, 60)
                self._shake_timer = max(self._shake_timer, 140)
                self._shake_intensity = max(self._shake_intensity, 2.5)

                if len(self.balls) == 0:
                    self.lives -= 1
                    if self.lives > 0 and self.miss_count < MAX_MISSES:
                        self._spawn_ball()
                continue

            # Paddle collision
            paddle_left = self.paddle_x - self.paddle_width // 2
            paddle_right = self.paddle_x + self.paddle_width // 2

            if (PADDLE_Y - BALL_RADIUS <= ball.y <= PADDLE_Y + PADDLE_HEIGHT
                    and paddle_left <= ball.x <= paddle_right
                    and ball.vy > 0):
                # Bounce angle based on where ball hit paddle
                relative_x = (ball.x - self.paddle_x) / (self.paddle_width / 2)
                spin = max(-0.6, min(0.6, self._paddle_vx / 260.0))
                angle = math.pi * 1.5 + relative_x * 0.85 + spin * 0.6
                ball.vx = math.cos(angle) * ball.speed
                ball.vy = math.sin(angle) * ball.speed
                ball.y = PADDLE_Y - BALL_RADIUS

                # Reset miss count on successful catch!
                self.miss_count = 0
                self._shake_timer = max(self._shake_timer, 70)
                self._shake_intensity = max(self._shake_intensity, 1.0)

                # Add particles
                for _ in range(5):
                    self.particles.append(Particle(
                        x=ball.x, y=ball.y,
                        vx=random.uniform(-50, 50),
                        vy=random.uniform(-80, -20),
                        color=self.paddle_color,
                        life=0.3,
                        size=2
                    ))

            # Brick collisions
            for brick in self.bricks:
                if brick.destroyed:
                    continue

                if self._ball_brick_collision(ball, brick):
                    brick.hits -= 1
                    self._flash_timer = 90
                    self._flash_color = brick.color
                    self._shake_timer = max(self._shake_timer, 90)
                    self._shake_intensity = max(self._shake_intensity, 1.5)
                    if brick.hits <= 0:
                        brick.destroyed = True
                        self.score += 10 * (self.combo + 1)
                        self.combo += 1
                        self.max_combo = max(self.max_combo, self.combo)

                        # Spawn particles
                        for _ in range(8):
                            self.particles.append(Particle(
                                x=brick.x + brick.width // 2,
                                y=brick.y + brick.height // 2,
                                vx=random.uniform(-100, 100),
                                vy=random.uniform(-100, 100),
                                color=brick.color,
                                life=0.5,
                                size=3
                            ))

                        # Random powerup
                        if random.random() < 0.22:
                            self.powerups.append(PowerUp(
                                x=brick.x + brick.width // 2,
                                y=brick.y + brick.height // 2,
                                type=random.choice(["wide", "multi", "slow", "life"])
                            ))
                    else:
                        for _ in range(4):
                            self.particles.append(Particle(
                                x=brick.x + brick.width // 2,
                                y=brick.y + brick.height // 2,
                                vx=random.uniform(-60, 60),
                                vy=random.uniform(-60, 60),
                                color=brick.color,
                                life=0.25,
                                size=2
                            ))
                    break

    def _ball_brick_collision(self, ball: Ball, brick: Brick) -> bool:
        """Check and handle ball-brick collision."""
        # Simple AABB collision
        if (ball.x + BALL_RADIUS > brick.x and
            ball.x - BALL_RADIUS < brick.x + brick.width and
            ball.y + BALL_RADIUS > brick.y and
            ball.y - BALL_RADIUS < brick.y + brick.height):

            # Determine collision side
            dx = ball.x - (brick.x + brick.width / 2)
            dy = ball.y - (brick.y + brick.height / 2)

            if abs(dx / brick.width) > abs(dy / brick.height):
                ball.vx = -ball.vx
            else:
                ball.vy = -ball.vy

            return True
        return False

    def _update_particles(self, dt: float) -> None:
        """Update particles."""
        for particle in self.particles[:]:
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vy += 200 * dt  # Gravity
            particle.life -= dt
            particle.size *= 0.98

            if particle.life <= 0:
                self.particles.remove(particle)

    def _update_powerups(self, dt: float) -> None:
        """Update powerups."""
        paddle_left = self.paddle_x - self.paddle_width // 2
        paddle_right = self.paddle_x + self.paddle_width // 2

        for powerup in self.powerups[:]:
            powerup.y += powerup.vy * 60 * dt
            powerup.pulse += dt * 6.0

            # Collect with paddle
            if (PADDLE_Y - 5 <= powerup.y <= PADDLE_Y + PADDLE_HEIGHT + 5
                    and paddle_left <= powerup.x <= paddle_right):
                self._apply_powerup(powerup.type)
                self.powerups.remove(powerup)
                continue

            # Fall off screen
            if powerup.y > SCREEN_H + 10:
                self.powerups.remove(powerup)

    def _apply_powerup(self, type: str) -> None:
        """Apply powerup effect."""
        if type == "wide":
            self.paddle_width = min(48, self.paddle_width + 8)
        elif type == "multi":
            # Add extra balls
            for ball in self.balls[:2]:
                new_ball = Ball(
                    x=ball.x, y=ball.y,
                    vx=ball.vx * random.choice([-1, 1]),
                    vy=-abs(ball.vy),
                    speed=ball.speed
                )
                self.balls.append(new_ball)
        elif type == "slow":
            for ball in self.balls:
                ball.speed *= 0.7
                ball.vx *= 0.7
                ball.vy *= 0.7
        elif type == "life":
            self.lives = min(5, self.lives + 1)
            self.miss_count = 0  # Reset misses on extra life

    def _finish_game(self) -> None:
        """End the game."""
        result = ModeResult(
            mode_name=self.name,
            success=self._win,
            data={
                "score": self.score,
                "max_combo": self.max_combo,
                "level": self.level,
                "lives_remaining": self.lives
            },
            display_text=f"СЧЁТ: {self.score}",
            ticker_text=f"КОМБО x{self.max_combo}" if self.max_combo > 1 else "ОТЛИЧНАЯ ИГРА!"
        )
        self.complete(result)

    def on_input(self, event: Event) -> bool:
        """Handle input events."""
        # Arrow keys + keypad 4/6 for paddle control
        if event.type == EventType.ARCADE_LEFT:
            self._manual_nudge(-0.08)
            return True
        elif event.type == EventType.ARCADE_RIGHT:
            self._manual_nudge(0.08)
            return True
        # Keypad 4 = left, 6 = right
        elif event.type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "4":
                self._manual_nudge(-0.08)
                return True
            elif key == "6":
                self._manual_nudge(0.08)
                return True
        elif event.type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.INTRO:
                self.change_phase(ModePhase.ACTIVE)
                return True
        return False

    def on_exit(self) -> None:
        """Cleanup - nothing to do, camera service is shared."""
        pass

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render game to main display with camera background."""
        # Render camera background
        self._render_camera_background(buffer)
        self._render_tracking_overlay(buffer)

        if self.phase == ModePhase.INTRO:
            self._render_intro(buffer)
            return

        if self.phase == ModePhase.OUTRO:
            self._render_outro(buffer)
            return

        # Screen shake for impacts
        shake_x = shake_y = 0
        if self._shake_timer > 0:
            strength = self._shake_intensity * (self._shake_timer / 180.0)
            amp = max(1, int(strength))
            shake_x = random.randint(-amp, amp)
            shake_y = random.randint(-amp, amp)

        # Render game elements on top of background
        self._render_bricks(buffer, shake_x, shake_y)
        self._render_particles(buffer, shake_x, shake_y)
        self._render_powerups(buffer, shake_x, shake_y)
        self._render_paddle(buffer, shake_x, shake_y)
        self._render_balls(buffer, shake_x, shake_y)

        # Impact flash
        if self._flash_timer > 0:
            intensity = self._flash_timer / 180.0
            for c in range(3):
                buffer[:, :, c] = np.clip(
                    buffer[:, :, c].astype(np.float32) + self._flash_color[c] * intensity * 0.25,
                    0, 255
                ).astype(np.uint8)
        self._render_hud(buffer)

    def _render_camera_background(self, buffer: NDArray[np.uint8]) -> None:
        """Render camera feed as background."""
        from artifact.utils.camera_service import camera_service

        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            # Slight dim to keep game elements visible
            dimmed = (frame.astype(np.float32) * 0.85).astype(np.uint8)
            np.copyto(buffer, dimmed)
        else:
            self._render_arcade_background(buffer)

    def _render_arcade_background(self, buffer: NDArray[np.uint8]) -> None:
        """Render a fallback neon background when camera is unavailable."""
        t_sec = self._time_in_mode / 1000.0
        horizon_y = 52

        # Base gradient
        for y in range(SCREEN_H):
            factor = y / SCREEN_H
            r = int(10 + 16 * factor)
            g = int(12 + 20 * factor)
            b = int(30 + 60 * (1 - factor))
            buffer[y, :] = [r, g, b]

        # Starfield
        for i in range(18):
            speed = 6 + (i % 4) * 2
            sx = int((i * 19 + t_sec * speed * 9) % SCREEN_W)
            sy = int((i * 13 + t_sec * speed * 5) % horizon_y)
            twinkle = 0.6 + 0.4 * math.sin(t_sec * 3 + i)
            color = (
                int(70 + 70 * twinkle),
                int(100 + 90 * twinkle),
                int(150 + 90 * twinkle),
            )
            draw_rect(buffer, sx, sy, 1, 1, color, filled=True)

        # Horizon glow
        draw_rect(buffer, 0, horizon_y, SCREEN_W, 1, (80, 120, 180))

        # Perspective grid
        grid_color = (40, 80, 120)
        phase = (t_sec * 0.6) % 1.0
        for i in range(7):
            pct = (i / 7 + phase) % 1.0
            y = int(horizon_y + (pct * pct) * (SCREEN_H - 1 - horizon_y))
            draw_line(buffer, 0, y, SCREEN_W - 1, y, grid_color)

        center_x = SCREEN_W // 2
        for i in range(-6, 7):
            top_x = center_x + i * 6
            bottom_x = center_x + i * 14
            draw_line(buffer, top_x, horizon_y, bottom_x, SCREEN_H - 1, grid_color)

        # Scanlines
        buffer[::2] = (buffer[::2].astype(np.float32) * 0.88).astype(np.uint8)

    def _render_tracking_overlay(self, buffer: NDArray[np.uint8]) -> None:
        """Render hand or motion tracking overlay."""
        from artifact.utils.camera_service import camera_service

        overlay = camera_service.get_hand_overlay()
        if overlay is not None:
            bbox, landmarks = overlay
            self._draw_bbox_overlay(buffer, bbox, (80, 255, 120))
            for idx in (0, 4, 8, 12, 16, 20):
                if idx < len(landmarks):
                    lx, ly = landmarks[idx]
                    px = int(lx * 128)
                    py = int(ly * 128)
                    draw_rect(buffer, px - 1, py - 1, 3, 3, (255, 255, 255), filled=True)
            return

        motion_bbox = camera_service.get_motion_overlay()
        if motion_bbox is not None:
            self._draw_bbox_overlay(buffer, motion_bbox, (100, 180, 255))

    def _draw_bbox_overlay(self, buffer: NDArray[np.uint8], bbox: tuple, color: tuple) -> None:
        x1, y1, x2, y2 = bbox
        px1 = int(x1 * 128)
        py1 = int(y1 * 128)
        px2 = int(x2 * 128)
        py2 = int(y2 * 128)
        w = max(1, px2 - px1)
        h = max(1, py2 - py1)
        draw_rect(buffer, px1, py1, w, h, color, filled=False)

    def _render_intro(self, buffer: NDArray[np.uint8]) -> None:
        """Render intro screen."""
        from artifact.utils.camera_service import camera_service

        t = self._intro_time / 1000

        # Title
        draw_centered_text(buffer, "КИРПИЧИ", 30, self.paddle_color, scale=2)
        draw_centered_text(buffer, "BRICK BREAKER", 55, (100, 100, 100), scale=1)

        # Instructions
        if int(t * 2) % 2 == 0:
            draw_centered_text(buffer, "ДВИГАЙ РУКОЙ", 80, self.ball_color, scale=1)
            draw_centered_text(buffer, "ИЛИ 4/6", 92, self.ball_color, scale=1)

        # Camera status
        if camera_service.has_camera:
            draw_centered_text(buffer, "КАМЕРА ОК", 110, (0, 255, 0), scale=1)
        else:
            draw_centered_text(buffer, "НЕТ КАМЕРЫ", 110, (255, 100, 0), scale=1)

    def _render_outro(self, buffer: NDArray[np.uint8]) -> None:
        """Render game over/win screen."""
        if self._win:
            draw_centered_text(buffer, "ПОБЕДА!", 30, self.ball_color, scale=2)
        else:
            draw_centered_text(buffer, "ИГРА", 25, (255, 50, 50), scale=2)
            draw_centered_text(buffer, "ОКОНЧЕНА", 45, (255, 50, 50), scale=2)

        draw_centered_text(buffer, f"СЧЁТ: {self.score}", 75, (255, 255, 255), scale=1)
        draw_centered_text(buffer, f"КОМБО: x{self.max_combo}", 90, self.paddle_color, scale=1)

    def _render_bricks(self, buffer: NDArray[np.uint8], offset_x: int = 0, offset_y: int = 0) -> None:
        """Render all bricks."""
        for brick in self.bricks:
            if brick.destroyed:
                continue

            # Darken if damaged
            color = brick.color
            if brick.hits > 1:
                color = tuple(min(255, int(c * 1.2)) for c in color)

            x = int(brick.x + offset_x)
            y = int(brick.y + offset_y)
            w, h = brick.width, brick.height

            draw_rect(buffer, x, y, w, h, color)

            # Highlight and shadow
            highlight = tuple(min(255, c + 40) for c in color)
            shadow = tuple(max(0, c - 40) for c in color)
            draw_rect(buffer, x, y, w, 1, highlight)
            draw_rect(buffer, x, y + h - 1, w, 1, shadow)
            draw_rect(buffer, x, y, 1, h, shadow)

            # Cracks for multi-hit bricks
            if brick.hits > 1:
                crack = (20, 20, 30)
                draw_rect(buffer, x + w // 2, y + 1, 1, max(1, h - 2), crack)
                draw_rect(buffer, x + 2, y + h // 2, max(1, w - 4), 1, crack)

    def _render_paddle(self, buffer: NDArray[np.uint8], offset_x: int = 0, offset_y: int = 0) -> None:
        """Render paddle."""
        px = int(self.paddle_x - self.paddle_width // 2 + offset_x)
        py = int(PADDLE_Y + offset_y)

        glow = tuple(int(c * 0.25) for c in self.paddle_color)
        draw_rect(buffer, px - 2, py - 2, self.paddle_width + 4, PADDLE_HEIGHT + 4, glow)
        draw_rect(buffer, px, py, self.paddle_width, PADDLE_HEIGHT, self.paddle_color)

        # Highlight and shadow
        highlight = tuple(min(255, c + 50) for c in self.paddle_color)
        shadow = tuple(max(0, c - 60) for c in self.paddle_color)
        draw_rect(buffer, px, py, self.paddle_width, 1, highlight)
        draw_rect(buffer, px, py + PADDLE_HEIGHT - 1, self.paddle_width, 1, shadow)

    def _render_balls(self, buffer: NDArray[np.uint8], offset_x: int = 0, offset_y: int = 0) -> None:
        """Render all balls with trails."""
        for ball in self.balls:
            bx = int(ball.x + offset_x)
            by = int(ball.y + offset_y)

            # Glow
            glow = tuple(int(c * 0.25) for c in self.ball_color)
            draw_circle(buffer, bx, by, BALL_RADIUS + 2, glow)

            # Trail
            for i, (tx, ty) in enumerate(ball.trail):
                alpha = i / len(ball.trail)
                size = int(BALL_RADIUS * alpha)
                color = tuple(int(c * alpha * 0.5) for c in self.ball_color)
                draw_circle(buffer, int(tx + offset_x), int(ty + offset_y), max(1, size), color)

            # Ball
            draw_circle(buffer, bx, by, BALL_RADIUS, self.ball_color)
            draw_circle(buffer, bx - 1, by - 1, 1, (255, 255, 255))

    def _render_particles(self, buffer: NDArray[np.uint8], offset_x: int = 0, offset_y: int = 0) -> None:
        """Render particles."""
        for p in self.particles:
            size = max(1, int(p.size))
            alpha = max(0.0, min(1.0, p.life / 0.5))
            color = tuple(int(c * alpha) for c in p.color)
            draw_rect(
                buffer,
                int(p.x + offset_x) - size // 2,
                int(p.y + offset_y) - size // 2,
                size,
                size,
                color
            )

    def _render_powerups(self, buffer: NDArray[np.uint8], offset_x: int = 0, offset_y: int = 0) -> None:
        """Render powerups."""
        colors = {
            "wide": (255, 200, 0),
            "multi": (0, 255, 200),
            "slow": (200, 100, 255),
            "life": (255, 100, 100)
        }
        for powerup in self.powerups:
            color = colors.get(powerup.type, (255, 255, 255))
            pulse = 1.0 + 0.15 * math.sin(powerup.pulse)
            size = max(6, int(8 * pulse))
            x0 = int(powerup.x + offset_x) - size // 2
            y0 = int(powerup.y + offset_y) - size // 2

            glow = tuple(int(c * 0.25) for c in color)
            draw_rect(buffer, x0 - 1, y0 - 1, size + 2, size + 2, glow)
            draw_rect(buffer, x0, y0, size, size, color)
            draw_rect(buffer, x0, y0, size, size, (10, 10, 20), filled=False)

            # Icon hints
            if powerup.type == "wide":
                draw_rect(buffer, x0 + 1, y0 + size // 2 - 1, size - 2, 2, (255, 255, 255))
            elif powerup.type == "multi":
                draw_rect(buffer, x0 + 2, y0 + 2, 2, 2, (255, 255, 255))
                draw_rect(buffer, x0 + size // 2 - 1, y0 + size // 2 - 1, 2, 2, (255, 255, 255))
                draw_rect(buffer, x0 + size - 4, y0 + size - 4, 2, 2, (255, 255, 255))
            elif powerup.type == "slow":
                draw_rect(buffer, x0 + 2, y0 + 1, size - 4, 1, (255, 255, 255))
                draw_rect(buffer, x0 + 2, y0 + size - 2, size - 4, 1, (255, 255, 255))
                draw_rect(buffer, x0 + size // 2 - 1, y0 + 2, 2, size - 4, (255, 255, 255))
            elif powerup.type == "life":
                draw_rect(buffer, x0 + 2, y0 + 2, 2, 2, (255, 255, 255))
                draw_rect(buffer, x0 + size - 4, y0 + 2, 2, 2, (255, 255, 255))
                draw_rect(buffer, x0 + size // 2 - 1, y0 + 3, 2, size - 4, (255, 255, 255))

    def _render_hud(self, buffer: NDArray[np.uint8]) -> None:
        """Render HUD."""
        # Score (top left)
        draw_centered_text(buffer, f"{self.score}", 2, (255, 255, 255), scale=1)

        # Lives (top right as hearts)
        for i in range(self.lives):
            draw_rect(buffer, 120 - i * 8, 2, 5, 5, (255, 50, 50))

        # Control indicator (hand/camera/manual)
        indicator_y = 16
        bar_x = 10
        bar_w = 108
        draw_rect(buffer, bar_x, indicator_y, bar_w, 1, (40, 50, 70))
        dot_x = bar_x + int(self._control_x * (bar_w - 1))
        if self._control_source == "manual":
            dot_color = (255, 200, 80)
        elif self._control_source == "hand":
            dot_color = (120, 255, 180)
        else:
            dot_color = (120, 180, 255)
        if self._control_confidence < 0.2:
            dot_color = (120, 120, 120)
        draw_rect(buffer, dot_x - 1, indicator_y - 1, 3, 3, dot_color)

        # Miss indicator (warn when getting close to losing)
        if self.miss_count >= MAX_MISSES - 2:
            miss_color = (255, 0, 0) if int(self._time_in_mode * 4) % 2 == 0 else (100, 0, 0)
            draw_centered_text(buffer, f"MISS:{self.miss_count}/{MAX_MISSES}", 10, miss_color, scale=1)
        elif self.combo > 1:
            draw_centered_text(buffer, f"x{self.combo}", 10, self.ball_color, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        from artifact.graphics.primitives import clear
        clear(buffer)

        if self.phase == ModePhase.ACTIVE:
            text = f"СЧЁТ: {self.score}  ЖИЗНИ: {self.lives}"
        elif self._win:
            text = "ПОБЕДА! ОТЛИЧНО!"
        elif self._game_over:
            text = "GAME OVER"
        else:
            text = "BRICK BREAKER"

        from artifact.graphics.text_utils import render_ticker_animated, TickerEffect
        render_ticker_animated(buffer, text, self._time_in_mode, self.paddle_color, TickerEffect.SCROLL)

    def get_lcd_text(self) -> str:
        """Get LCD text."""
        if self.phase == ModePhase.ACTIVE:
            return f"SCORE:{self.score:04d}".center(16)[:16]
        return self.display_name.center(16)[:16]

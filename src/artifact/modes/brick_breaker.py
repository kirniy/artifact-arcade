"""Brick Breaker - Camera-controlled classic arcade game.

Use your hand or body movement to control the paddle and break all the bricks!
The camera tracks horizontal motion to move the paddle left/right.
Camera background shows you in-game!
"""

import math
import random
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_circle
from artifact.graphics.text_utils import draw_centered_text, hsv_to_rgb

logger = logging.getLogger(__name__)


# Game constants
SCREEN_W, SCREEN_H = 128, 128
PADDLE_WIDTH = 24
PADDLE_HEIGHT = 4
PADDLE_Y = 118
BALL_RADIUS = 3
BRICK_ROWS = 6
BRICK_COLS = 8
BRICK_WIDTH = 14
BRICK_HEIGHT = 6
BRICK_TOP_OFFSET = 20
INITIAL_LIVES = 3
MAX_MISSES = 5  # Lose if you miss this many times in a row


@dataclass
class Ball:
    x: float
    y: float
    vx: float
    vy: float
    speed: float = 1.5
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


class BrickBreakerMode(BaseMode):
    """Camera-controlled Brick Breaker game with camera background."""

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
        self._outro_time = 0.0

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
        speed = 1.5 + self.level * 0.1
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

    def _update_camera(self) -> None:
        """Update paddle position from shared camera service."""
        from artifact.utils.camera_service import camera_service

        # Get motion position directly from camera service
        new_motion = camera_service.get_motion_x()

        # Smooth the movement
        alpha = 0.3
        self._motion_x = self._prev_motion_x * (1 - alpha) + new_motion * alpha
        self._prev_motion_x = self._motion_x

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
        self._update_camera()

        # Smooth paddle following
        target_x = int(self._motion_x * SCREEN_W)
        target_x = max(self.paddle_width // 2, min(SCREEN_W - self.paddle_width // 2, target_x))
        self.paddle_x += (target_x - self.paddle_x) * 0.2

        # Update balls
        self._update_balls(dt)

        # Update particles
        self._update_particles(dt)

        # Update powerups
        self._update_powerups(dt)

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
                angle = math.pi * 1.5 + relative_x * 0.8
                ball.vx = math.cos(angle) * ball.speed
                ball.vy = math.sin(angle) * ball.speed
                ball.y = PADDLE_Y - BALL_RADIUS

                # Reset miss count on successful catch!
                self.miss_count = 0

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
                        if random.random() < 0.15:
                            self.powerups.append(PowerUp(
                                x=brick.x + brick.width // 2,
                                y=brick.y + brick.height // 2,
                                type=random.choice(["wide", "multi", "slow", "life"])
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
        if event.event_type == EventType.ARCADE_LEFT:
            self._motion_x = max(0, self._motion_x - 0.08)
            return True
        elif event.event_type == EventType.ARCADE_RIGHT:
            self._motion_x = min(1, self._motion_x + 0.08)
            return True
        # Keypad 4 = left, 6 = right
        elif event.event_type == EventType.KEYPAD_INPUT:
            key = event.data.get("key", "")
            if key == "4":
                self._motion_x = max(0, self._motion_x - 0.08)
                return True
            elif key == "6":
                self._motion_x = min(1, self._motion_x + 0.08)
                return True
        elif event.event_type == EventType.BUTTON_PRESS:
            if self.phase == ModePhase.INTRO:
                self.change_phase(ModePhase.ACTIVE)
                return True
        return False

    def on_exit(self) -> None:
        """Cleanup - nothing to do, camera service is shared."""
        pass

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render game to main display with camera background."""
        # Render camera background (dimmed)
        self._render_camera_background(buffer)

        if self.phase == ModePhase.INTRO:
            self._render_intro(buffer)
            return

        if self.phase == ModePhase.OUTRO:
            self._render_outro(buffer)
            return

        # Render game elements on top of camera
        self._render_bricks(buffer)
        self._render_particles(buffer)
        self._render_powerups(buffer)
        self._render_paddle(buffer)
        self._render_balls(buffer)
        self._render_hud(buffer)

    def _render_camera_background(self, buffer: NDArray[np.uint8]) -> None:
        """Render dimmed camera feed as background - you can see yourself!"""
        from artifact.utils.camera_service import camera_service

        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            # Dim the camera feed (multiply by ~0.25 for dark background)
            dimmed = (frame.astype(np.float32) * 0.25).astype(np.uint8)
            np.copyto(buffer, dimmed)
        else:
            # Fallback to solid background
            fill(buffer, self.bg_color)

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

    def _render_bricks(self, buffer: NDArray[np.uint8]) -> None:
        """Render all bricks."""
        for brick in self.bricks:
            if brick.destroyed:
                continue

            # Darken if damaged
            color = brick.color
            if brick.hits > 1:
                color = tuple(min(255, int(c * 1.2)) for c in color)

            draw_rect(buffer, brick.x, brick.y, brick.width, brick.height, color)

            # Border
            draw_rect(buffer, brick.x, brick.y, brick.width, 1, (255, 255, 255))

    def _render_paddle(self, buffer: NDArray[np.uint8]) -> None:
        """Render paddle."""
        px = int(self.paddle_x - self.paddle_width // 2)
        draw_rect(buffer, px, PADDLE_Y, self.paddle_width, PADDLE_HEIGHT, self.paddle_color)

        # Highlight
        draw_rect(buffer, px, PADDLE_Y, self.paddle_width, 1, (200, 255, 255))

    def _render_balls(self, buffer: NDArray[np.uint8]) -> None:
        """Render all balls with trails."""
        for ball in self.balls:
            # Trail
            for i, (tx, ty) in enumerate(ball.trail):
                alpha = i / len(ball.trail)
                size = int(BALL_RADIUS * alpha)
                color = tuple(int(c * alpha * 0.5) for c in self.ball_color)
                draw_circle(buffer, int(tx), int(ty), max(1, size), color)

            # Ball
            draw_circle(buffer, int(ball.x), int(ball.y), BALL_RADIUS, self.ball_color)
            draw_circle(buffer, int(ball.x) - 1, int(ball.y) - 1, 1, (255, 255, 255))

    def _render_particles(self, buffer: NDArray[np.uint8]) -> None:
        """Render particles."""
        for p in self.particles:
            size = max(1, int(p.size))
            alpha = p.life / 0.5
            color = tuple(int(c * alpha) for c in p.color)
            draw_rect(buffer, int(p.x) - size//2, int(p.y) - size//2, size, size, color)

    def _render_powerups(self, buffer: NDArray[np.uint8]) -> None:
        """Render powerups."""
        colors = {
            "wide": (255, 200, 0),
            "multi": (0, 255, 200),
            "slow": (200, 100, 255),
            "life": (255, 100, 100)
        }
        for powerup in self.powerups:
            color = colors.get(powerup.type, (255, 255, 255))
            draw_rect(buffer, int(powerup.x) - 4, int(powerup.y) - 4, 8, 8, color)

    def _render_hud(self, buffer: NDArray[np.uint8]) -> None:
        """Render HUD."""
        # Score (top left)
        draw_centered_text(buffer, f"{self.score}", 2, (255, 255, 255), scale=1)

        # Lives (top right as hearts)
        for i in range(self.lives):
            draw_rect(buffer, 120 - i * 8, 2, 5, 5, (255, 50, 50))

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

"""Bar Runner - Addictive endless runner with arcade mechanics.

Jump, double-jump, and dash through obstacles. Collect drinks for combos.
Features lives, power-ups, near-miss bonuses, and progressive difficulty.
"""

import math
import random
import logging
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_line
from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect

logger = logging.getLogger(__name__)


class PlayerState(Enum):
    RUNNING = "running"
    JUMPING = "jumping"
    DOUBLE_JUMPING = "double_jumping"
    FALLING = "falling"
    DASHING = "dash"
    HIT = "hit"


@dataclass
class Obstacle:
    x: float
    y: float
    width: int
    height: int
    color: tuple
    type: str = "keg"  # keg, bottle, box
    passed: bool = False  # For near-miss detection


@dataclass
class Pickup:
    x: float
    y: float
    size: int
    color: tuple
    value: int
    type: str = "drink"  # drink, coin, star
    pulse: float = 0.0


@dataclass
class PowerUp:
    x: float
    y: float
    type: str  # "shield", "magnet", "double"
    pulse: float = 0.0


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple
    size: float


@dataclass
class FloatingText:
    x: float
    y: float
    text: str
    color: tuple
    life: float
    vy: float = -30.0


@dataclass
class FlyingEnemy:
    """Flying obstacle that moves in patterns."""
    x: float
    y: float
    vx: float
    vy: float
    width: int
    height: int
    color: tuple
    pattern: str  # "sine", "dive", "hover"
    phase: float = 0.0


@dataclass
class GroundGap:
    """Gap in the ground that player must jump over."""
    x: float
    width: int
    depth: int = 30


@dataclass
class StarBurst:
    """Background star for fever mode."""
    x: float
    y: float
    size: float
    speed: float
    color: tuple


class BarRunnerMode(BaseMode):
    """Addictive endless runner with proper game mechanics."""

    name = "bar_runner"
    display_name = "БЕГИ!"
    icon = "runner"
    style = "arcade"
    description = "Прыгай, уворачивайся, собирай!"

    # Physics constants - Tuned for snappy, responsive gameplay
    # Screen: 128x128, GROUND_Y at 100 gives 100px jump space
    # Jump heights balanced against:
    #   - Tallest obstacle: 28px (bottle)
    #   - Flying enemies: y=20-70
    #   - Ground gaps: 20-35px at 80-120px/s scroll
    GROUND_Y = 100
    GRAVITY = 850.0           # Higher = snappier falls, more responsive
    JUMP_FORCE = -340.0       # Single jump reaches ~68px (clears 28px obstacles easily)
    DOUBLE_JUMP_FORCE = -300.0  # Powerful rescue jump, reaches additional ~53px
    DASH_SPEED = 220.0        # Slightly faster dash
    DASH_DURATION = 180.0     # Slightly shorter for snappy feel

    # Air time calculations:
    #   Single jump peak: 340/850 = 0.4s, total air = 0.8s
    #   Double from peak: adds 0.35s, total potential = 1.15s
    #   Gap at 120px/s: 35px/120 = 0.29s (easily jumpable)

    # Player position
    PLAYER_X = 28
    PLAYER_WIDTH = 12         # Slightly wider hitbox for fairness
    PLAYER_HEIGHT = 16        # Slightly taller to match new sprite

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._time_ms = 0.0

        # Player state
        self._player_y = self.GROUND_Y
        self._player_vy = 0.0
        self._state = PlayerState.RUNNING
        self._can_double_jump = False
        self._dash_timer = 0.0
        self._invincible_timer = 0.0
        self._hit_timer = 0.0

        # Jump forgiveness mechanics for responsive feel
        self._coyote_timer = 0.0      # Time after leaving ground where jump still works
        self._jump_buffer = 0.0       # Time to remember jump input before landing
        self._jump_held = False       # Track if jump button is held (for variable height)
        self.COYOTE_TIME = 100.0      # 100ms coyote time
        self.JUMP_BUFFER_TIME = 120.0  # 120ms jump buffer

        # Game state
        self._lives = 3
        self._score = 0
        self._distance = 0.0
        self._combo = 0
        self._max_combo = 0
        self._combo_timer = 0.0
        self._multiplier = 1.0

        # Power-up states
        self._shield_active = False
        self._shield_timer = 0.0
        self._magnet_timer = 0.0
        self._double_points_timer = 0.0

        # Game objects
        self._obstacles: List[Obstacle] = []
        self._pickups: List[Pickup] = []
        self._powerups: List[PowerUp] = []
        self._particles: List[Particle] = []
        self._floating_texts: List[FloatingText] = []

        # Spawning
        self._obstacle_cd = 0.0
        self._pickup_cd = 0.0
        self._powerup_cd = 5000.0

        # Difficulty
        self._scroll_speed = 80.0
        self._base_speed = 80.0
        self._difficulty = 1.0

        # Visual effects
        self._shake_timer = 0.0
        self._shake_intensity = 0.0
        self._flash_timer = 0.0
        self._flash_color = (255, 255, 255)
        self._bg_offset = 0.0

        # Game over
        self._game_over = False
        self._game_over_timer = 0.0

        # Milestones
        self._last_milestone = 0
        self._milestone_text = ""
        self._milestone_timer = 0.0

        # Animation
        self._run_frame = 0.0
        self._trail_timer = 0.0

        # Fever mode
        self._fever_mode = False
        self._fever_timer = 0.0
        self._fever_multiplier = 1.0
        self._stars: List[StarBurst] = []

        # Flying enemies and gaps
        self._flying_enemies: List[FlyingEnemy] = []
        self._ground_gaps: List[GroundGap] = []
        self._flying_cd = 5000.0
        self._gap_cd = 8000.0

        # Tutorial
        self._tutorial_shown = False
        self._tutorial_timer = 0.0
        self._first_jump_done = False
        self._first_double_done = False

        # Achievements
        self._near_misses = 0
        self._perfect_jumps = 0

        # High score (session-based)
        self._high_score = 0
        self._is_new_high_score = False

        # Difficulty progression
        self._difficulty_name = "ЛЕГКО"

        # Bonus zone
        self._bonus_zone_active = False
        self._bonus_zone_timer = 0.0
        self._bonus_zone_x = 0.0
        self._next_bonus_zone = 3000.0  # Distance until next bonus zone

    def on_enter(self) -> None:
        self._time_ms = 0.0

        # Reset player
        self._player_y = self.GROUND_Y
        self._player_vy = 0.0
        self._state = PlayerState.RUNNING
        self._can_double_jump = False
        self._dash_timer = 0.0
        self._invincible_timer = 0.0
        self._hit_timer = 0.0

        # Reset game state
        self._lives = 3
        self._score = 0
        self._distance = 0.0
        self._combo = 0
        self._max_combo = 0
        self._combo_timer = 0.0
        self._multiplier = 1.0

        # Reset power-ups
        self._shield_active = False
        self._shield_timer = 0.0
        self._magnet_timer = 0.0
        self._double_points_timer = 0.0

        # Clear objects
        self._obstacles.clear()
        self._pickups.clear()
        self._powerups.clear()
        self._particles.clear()
        self._floating_texts.clear()

        # Reset spawning
        self._obstacle_cd = 1000.0
        self._pickup_cd = 500.0
        self._powerup_cd = 8000.0

        # Reset difficulty
        self._scroll_speed = 80.0
        self._base_speed = 80.0
        self._difficulty = 1.0

        # Reset effects
        self._shake_timer = 0.0
        self._flash_timer = 0.0
        self._bg_offset = 0.0

        # Reset game over
        self._game_over = False
        self._game_over_timer = 0.0

        # Reset milestones
        self._last_milestone = 0
        self._milestone_text = ""
        self._milestone_timer = 0.0

        self._run_frame = 0.0
        self._trail_timer = 0.0

        # Reset jump forgiveness
        self._coyote_timer = 0.0
        self._jump_buffer = 0.0
        self._jump_held = False

        # Reset fever mode
        self._fever_mode = False
        self._fever_timer = 0.0
        self._fever_multiplier = 1.0
        self._stars.clear()

        # Reset flying enemies and gaps
        self._flying_enemies.clear()
        self._ground_gaps.clear()
        self._flying_cd = 5000.0
        self._gap_cd = 8000.0

        # Reset tutorial
        self._tutorial_shown = False
        self._tutorial_timer = 3000.0
        self._first_jump_done = False
        self._first_double_done = False

        # Reset achievements
        self._near_misses = 0
        self._perfect_jumps = 0

        # High score persists
        self._is_new_high_score = False

        # Reset difficulty name
        self._difficulty_name = "ЛЕГКО"

        # Reset bonus zone
        self._bonus_zone_active = False
        self._bonus_zone_timer = 0.0
        self._bonus_zone_x = 0.0
        self._next_bonus_zone = 3000.0

        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        pass

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if self._game_over:
            return False

        if event.type == EventType.BUTTON_PRESS:
            return self._handle_jump()

        elif event.type == EventType.ARCADE_LEFT:
            # Dash/slide
            if self._dash_timer <= 0 and self._state != PlayerState.HIT:
                self._start_dash()
            return True

        elif event.type == EventType.ARCADE_RIGHT:
            # Speed boost (temporary)
            self._scroll_speed = min(self._base_speed * 1.5, self._scroll_speed + 20)
            return True

        return False

    def _handle_jump(self) -> bool:
        """Handle jump input with double-jump support, coyote time, and jump buffer."""
        if self._state == PlayerState.HIT:
            return True

        self._jump_held = True  # Track that jump is being held
        self._jump_buffer = self.JUMP_BUFFER_TIME  # Buffer the jump input

        # Can jump if: running, or within coyote time after leaving ground
        can_first_jump = (self._state == PlayerState.RUNNING or
                         (self._coyote_timer > 0 and self._state == PlayerState.FALLING))

        if can_first_jump:
            # First jump
            self._player_vy = self.JUMP_FORCE
            self._state = PlayerState.JUMPING
            self._can_double_jump = True
            self._coyote_timer = 0  # Used up coyote time
            self._jump_buffer = 0  # Clear buffer since we jumped
            self._spawn_jump_particles()

            # Tutorial tracking
            self._first_jump_done = True

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_ui_confirm()

            logger.info("BarRunner: JUMP!")
            return True

        elif self._can_double_jump and self._state in (PlayerState.JUMPING, PlayerState.DOUBLE_JUMPING, PlayerState.FALLING):
            # Double jump!
            self._player_vy = self.DOUBLE_JUMP_FORCE
            self._state = PlayerState.DOUBLE_JUMPING
            self._can_double_jump = False
            self._jump_buffer = 0  # Clear buffer since we jumped
            self._spawn_double_jump_particles()

            # Tutorial tracking
            self._first_double_done = True

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_ui_move()

            logger.info("BarRunner: DOUBLE JUMP!")
            return True

        return True

    def _handle_jump_release(self) -> None:
        """Handle releasing jump button - allows variable jump height."""
        self._jump_held = False
        # If ascending and jump released early, cut velocity for shorter jump
        if self._player_vy < -100 and self._state in (PlayerState.JUMPING, PlayerState.DOUBLE_JUMPING):
            self._player_vy *= 0.5  # Cut upward velocity for shorter jump

    def _start_dash(self) -> None:
        """Start a dash/slide."""
        self._dash_timer = self.DASH_DURATION
        self._state = PlayerState.DASHING
        self._spawn_dash_particles()

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_ui_back()

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        dt = delta_ms / 1000.0
        self._time_ms += delta_ms

        # Game over countdown
        if self._game_over:
            self._game_over_timer += delta_ms
            self._update_particles(dt)
            if self._game_over_timer > 2500:
                self._complete()
            return

        # Update distance and difficulty
        self._distance += self._scroll_speed * dt
        self._difficulty = 1.0 + self._distance / 5000.0
        self._base_speed = 80.0 + self._difficulty * 20.0

        # Gradually return to base speed
        speed_diff = self._base_speed - self._scroll_speed
        self._scroll_speed += speed_diff * 2.0 * dt

        # Physics
        self._update_player(dt, delta_ms)

        # Spawn objects
        self._update_spawning(delta_ms)

        # Update objects
        self._update_obstacles(dt)
        self._update_pickups(dt)
        self._update_powerups(dt)
        self._update_particles(dt)
        self._update_floating_texts(dt)

        # Collisions
        self._check_collisions()

        # Timers
        self._update_timers(delta_ms)

        # Background scroll
        self._bg_offset = (self._bg_offset + self._scroll_speed * dt) % 32

        # Animation
        self._run_frame += delta_ms * 0.01 * (self._scroll_speed / 80.0)

        # Trail particles while running fast
        self._trail_timer -= delta_ms
        if self._trail_timer <= 0 and self._scroll_speed > 100:
            self._spawn_trail_particle()
            self._trail_timer = 50

        # Milestones
        self._check_milestones()

        # Fever mode
        if self._fever_mode:
            self._fever_timer -= delta_ms
            if self._fever_timer <= 0:
                self._fever_mode = False
                self._fever_multiplier = 1.0
            else:
                # Spawn fever stars
                if random.random() < 0.4:
                    self._spawn_fever_star()

        # Update fever stars
        self._update_fever_stars(dt)

        # Update flying enemies
        self._update_flying_enemies(dt, delta_ms)

        # Update ground gaps
        self._update_ground_gaps(dt)

        # Spawn flying enemies (rare, increases with difficulty)
        self._flying_cd -= delta_ms
        if self._flying_cd <= 0 and self._difficulty > 1.5:
            self._spawn_flying_enemy()
            self._flying_cd = random.uniform(4000, 8000) / self._difficulty

        # Spawn ground gaps (rare)
        self._gap_cd -= delta_ms
        if self._gap_cd <= 0 and self._difficulty > 2.0:
            self._spawn_ground_gap()
            self._gap_cd = random.uniform(6000, 12000) / self._difficulty

        # Tutorial timer
        self._tutorial_timer = max(0.0, self._tutorial_timer - delta_ms)

        # Update difficulty name
        self._update_difficulty_name()

        # Bonus zone logic
        if self._bonus_zone_active:
            self._bonus_zone_timer -= delta_ms
            self._bonus_zone_x -= self._scroll_speed * dt
            if self._bonus_zone_timer <= 0 or self._bonus_zone_x < -50:
                self._bonus_zone_active = False
        else:
            # Check if we should start a bonus zone
            if self._distance >= self._next_bonus_zone:
                self._start_bonus_zone()
                self._next_bonus_zone = self._distance + 3000 + random.uniform(0, 2000)

        # Check for high score
        if self._score > self._high_score:
            if not self._is_new_high_score and self._high_score > 0:
                self._is_new_high_score = True
                self._floating_texts.append(FloatingText(
                    x=64, y=40,
                    text="НОВЫЙ РЕКОРД!",
                    color=(255, 215, 0),
                    life=1500
                ))
                self._flash_timer = 500
                self._flash_color = (255, 215, 0)
            self._high_score = self._score

    def _update_player(self, dt: float, delta_ms: float) -> None:
        """Update player physics with coyote time and jump buffer."""
        # Update jump forgiveness timers
        if self._coyote_timer > 0:
            self._coyote_timer -= delta_ms
        if self._jump_buffer > 0:
            self._jump_buffer -= delta_ms

        # Dash state
        if self._dash_timer > 0:
            self._dash_timer -= delta_ms
            if self._dash_timer <= 0:
                self._state = PlayerState.RUNNING if self._player_y >= self.GROUND_Y - 1 else PlayerState.FALLING
        else:
            # Gravity
            self._player_vy += self.GRAVITY * dt
            self._player_y += self._player_vy * dt

            # Ground collision
            if self._player_y >= self.GROUND_Y:
                self._player_y = self.GROUND_Y
                self._player_vy = 0.0

                was_airborne = self._state in (PlayerState.JUMPING, PlayerState.DOUBLE_JUMPING, PlayerState.FALLING)

                if was_airborne:
                    self._state = PlayerState.RUNNING
                    self._spawn_land_particles()

                    # Check jump buffer - if player pressed jump just before landing, jump!
                    if self._jump_buffer > 0:
                        self._handle_jump()

                    # Play landing sound
                    if hasattr(self.context, "audio") and self.context.audio:
                        self.context.audio.play_ui_back()

            elif self._player_vy > 0 and self._state != PlayerState.FALLING:
                # Just started falling - start coyote time
                if self._state == PlayerState.RUNNING:
                    self._coyote_timer = self.COYOTE_TIME
                self._state = PlayerState.FALLING

        # Hit recovery
        if self._hit_timer > 0:
            self._hit_timer -= delta_ms
            if self._hit_timer <= 0:
                self._state = PlayerState.RUNNING if self._player_y >= self.GROUND_Y - 1 else PlayerState.FALLING

    def _update_spawning(self, delta_ms: float) -> None:
        """Handle object spawning."""
        # Obstacles
        self._obstacle_cd -= delta_ms
        if self._obstacle_cd <= 0:
            self._spawn_obstacle()
            # Spawn rate increases with difficulty
            base_cd = max(400, 1200 - self._difficulty * 100)
            self._obstacle_cd = random.uniform(base_cd * 0.8, base_cd * 1.2)

        # Pickups
        self._pickup_cd -= delta_ms
        if self._pickup_cd <= 0:
            self._spawn_pickup()
            self._pickup_cd = random.uniform(600, 1200)

        # Power-ups (rare - spawn less frequently)
        self._powerup_cd -= delta_ms
        if self._powerup_cd <= 0:
            self._spawn_powerup()
            self._powerup_cd = random.uniform(20000, 35000)  # Much rarer: was 10-20s, now 20-35s

    def _update_obstacles(self, dt: float) -> None:
        """Update obstacles."""
        for obs in self._obstacles:
            obs.x -= self._scroll_speed * dt

            # Near-miss detection
            if not obs.passed and obs.x + obs.width < self.PLAYER_X - self.PLAYER_WIDTH / 2:
                obs.passed = True
                # Award near-miss bonus if we were close
                player_bottom = self._player_y
                player_top = self._player_y - self.PLAYER_HEIGHT
                obs_top = obs.y
                obs_bottom = obs.y + obs.height

                # Check if we were close vertically
                vertical_gap = min(abs(player_bottom - obs_top), abs(player_top - obs_bottom))
                if vertical_gap < 10:
                    self._award_near_miss()

        # Remove off-screen
        self._obstacles = [o for o in self._obstacles if o.x + o.width > -10]

    def _update_pickups(self, dt: float) -> None:
        """Update pickups with magnet effect."""
        player_center_y = self._player_y - self.PLAYER_HEIGHT / 2

        for pk in self._pickups:
            pk.x -= self._scroll_speed * dt
            pk.pulse += dt * 5

            # Magnet effect
            if self._magnet_timer > 0:
                dx = self.PLAYER_X - pk.x
                dy = player_center_y - pk.y
                dist = math.sqrt(dx * dx + dy * dy)
                if dist < 60 and dist > 1:
                    speed = 150.0
                    pk.x += (dx / dist) * speed * dt
                    pk.y += (dy / dist) * speed * dt

        # Remove off-screen
        self._pickups = [p for p in self._pickups if p.x + p.size > -10]

    def _update_powerups(self, dt: float) -> None:
        """Update power-ups."""
        for pu in self._powerups:
            pu.x -= self._scroll_speed * dt
            pu.pulse += dt * 4
            # Float up and down
            pu.y += math.sin(pu.pulse) * 0.5

        self._powerups = [p for p in self._powerups if p.x > -20]

    def _update_particles(self, dt: float) -> None:
        """Update particles."""
        for p in self._particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 200 * dt  # gravity
            p.life -= dt * 1000
            p.size = max(0.5, p.size * 0.98)

        self._particles = [p for p in self._particles if p.life > 0]

    def _update_floating_texts(self, dt: float) -> None:
        """Update floating score texts."""
        for ft in self._floating_texts:
            ft.y += ft.vy * dt
            ft.life -= dt * 1000

        self._floating_texts = [ft for ft in self._floating_texts if ft.life > 0]

    def _update_timers(self, delta_ms: float) -> None:
        """Update all timers."""
        self._shake_timer = max(0.0, self._shake_timer - delta_ms)
        self._flash_timer = max(0.0, self._flash_timer - delta_ms)
        self._invincible_timer = max(0.0, self._invincible_timer - delta_ms)
        self._shield_timer = max(0.0, self._shield_timer - delta_ms)
        self._magnet_timer = max(0.0, self._magnet_timer - delta_ms)
        self._double_points_timer = max(0.0, self._double_points_timer - delta_ms)
        self._milestone_timer = max(0.0, self._milestone_timer - delta_ms)

        # Combo decay
        if self._combo > 0:
            self._combo_timer -= delta_ms
            if self._combo_timer <= 0:
                self._combo = 0
                self._multiplier = 1.0

        # Shield deactivation
        if self._shield_timer <= 0:
            self._shield_active = False

    def _check_collisions(self) -> None:
        """Check all collisions."""
        if self._invincible_timer > 0:
            return

        # Player hitbox
        px1 = self.PLAYER_X - self.PLAYER_WIDTH / 2
        px2 = self.PLAYER_X + self.PLAYER_WIDTH / 2

        # Different hitbox when dashing (shorter)
        if self._state == PlayerState.DASHING:
            py1 = self._player_y - 6
            py2 = self._player_y
        else:
            py1 = self._player_y - self.PLAYER_HEIGHT
            py2 = self._player_y

        # Check ground gaps - player falls if over gap and on ground
        if self._state == PlayerState.RUNNING and self._is_over_gap():
            self._player_vy = 50  # Start falling
            self._state = PlayerState.FALLING

        # Flying enemies
        for enemy in self._flying_enemies:
            ex1, ex2 = enemy.x, enemy.x + enemy.width
            ey1, ey2 = enemy.y, enemy.y + enemy.height

            if px2 > ex1 and px1 < ex2 and py2 > ey1 and py1 < ey2:
                self._handle_flying_enemy_hit(enemy)
                break

        # Obstacles
        for obs in self._obstacles:
            if obs.passed:
                continue

            ox1, ox2 = obs.x, obs.x + obs.width
            oy1, oy2 = obs.y, obs.y + obs.height

            if px2 > ox1 and px1 < ox2 and py2 > oy1 and py1 < oy2:
                self._handle_obstacle_hit(obs)
                break

        # Pickups
        for pk in list(self._pickups):
            pkx1, pkx2 = pk.x, pk.x + pk.size
            pky1, pky2 = pk.y, pk.y + pk.size

            if px2 > pkx1 and px1 < pkx2 and py2 > pky1 and py1 < pky2:
                self._collect_pickup(pk)
                self._pickups.remove(pk)

        # Power-ups
        for pu in list(self._powerups):
            pux1, pux2 = pu.x - 8, pu.x + 8
            puy1, puy2 = pu.y - 8, pu.y + 8

            if px2 > pux1 and px1 < pux2 and py2 > puy1 and py1 < puy2:
                self._collect_powerup(pu)
                self._powerups.remove(pu)

    def _handle_flying_enemy_hit(self, enemy: FlyingEnemy) -> None:
        """Handle hitting a flying enemy."""
        # Remove the enemy
        if enemy in self._flying_enemies:
            self._flying_enemies.remove(enemy)

        # Same damage logic as obstacles
        if self._shield_active:
            self._shield_active = False
            self._shield_timer = 0
            self._spawn_shield_break_particles()

            self._floating_texts.append(FloatingText(
                x=self.PLAYER_X, y=self._player_y - 20,
                text="ЩИТ!", color=(100, 200, 255), life=600
            ))

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_ui_back()
            return

        # Take damage
        self._lives -= 1
        self._combo = 0
        self._multiplier = 1.0

        self._shake_timer = 400
        self._shake_intensity = 5
        self._flash_timer = 200
        self._flash_color = (255, 50, 50)
        self._invincible_timer = 1500
        self._hit_timer = 300
        self._state = PlayerState.HIT

        self._player_vy = -150
        self._spawn_hit_particles()

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_failure()

        logger.info(f"Flying enemy hit! Lives: {self._lives}")

        if self._lives <= 0:
            self._game_over = True
            self._game_over_timer = 0

    def _handle_obstacle_hit(self, obs: Obstacle) -> None:
        """Handle hitting an obstacle."""
        # Shield absorbs hit
        if self._shield_active:
            self._shield_active = False
            self._shield_timer = 0
            self._spawn_shield_break_particles()
            obs.passed = True

            self._floating_texts.append(FloatingText(
                x=self.PLAYER_X, y=self._player_y - 20,
                text="ЩИТ!", color=(100, 200, 255), life=600
            ))

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_ui_back()
            return

        # Take damage
        self._lives -= 1
        self._combo = 0
        self._multiplier = 1.0

        self._shake_timer = 400
        self._shake_intensity = 5
        self._flash_timer = 200
        self._flash_color = (255, 50, 50)
        self._invincible_timer = 1500
        self._hit_timer = 300
        self._state = PlayerState.HIT

        # Knockback
        self._player_vy = -150

        # Spawn hit particles
        self._spawn_hit_particles()

        obs.passed = True

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_failure()

        logger.info(f"Hit! Lives: {self._lives}")

        if self._lives <= 0:
            self._game_over = True
            self._game_over_timer = 0

    def _collect_pickup(self, pk: Pickup) -> None:
        """Collect a pickup."""
        # Calculate points
        base_points = pk.value
        if self._double_points_timer > 0:
            base_points *= 2

        # Apply fever multiplier
        fever_mult = self._fever_multiplier if self._fever_mode else 1.0
        points = int(base_points * self._multiplier * fever_mult)
        self._score += points

        # Update combo
        self._combo += 1
        self._combo_timer = 2000  # 2 seconds to maintain combo
        self._max_combo = max(self._max_combo, self._combo)

        # Update multiplier based on combo
        if self._combo >= 10:
            self._multiplier = 3.0
        elif self._combo >= 5:
            self._multiplier = 2.0
        elif self._combo >= 3:
            self._multiplier = 1.5
        else:
            self._multiplier = 1.0

        # Activate fever mode on combo 15!
        if self._combo == 15 and not self._fever_mode:
            self._activate_fever_mode()

        # Visual feedback
        if self._fever_mode:
            color = (255, 150, 50)
            self._floating_texts.append(FloatingText(
                x=pk.x, y=pk.y, text=f"🔥+{points}", color=color, life=500
            ))
        else:
            color = (255, 255, 100) if self._combo >= 5 else (255, 200, 100)
            self._floating_texts.append(FloatingText(
                x=pk.x, y=pk.y, text=f"+{points}", color=color, life=500
            ))

        self._spawn_pickup_particles(pk.x, pk.y, pk.color)

        if self._combo >= 5 and self._combo % 5 == 0:
            self._flash_timer = 100
            self._flash_color = (255, 255, 150) if not self._fever_mode else (255, 150, 50)
            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_reward()
        else:
            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_success()

    def _collect_powerup(self, pu: PowerUp) -> None:
        """Collect a power-up."""
        if pu.type == "shield":
            self._shield_active = True
            self._shield_timer = 4000  # Reduced from 8s to 4s
            text = "ЩИТ!"
            color = (100, 200, 255)
        elif pu.type == "magnet":
            self._magnet_timer = 4000  # Reduced from 6s to 4s
            text = "МАГНИТ!"
            color = (255, 100, 255)
        elif pu.type == "double":
            self._double_points_timer = 5000  # Reduced from 8s to 5s
            text = "x2 ОЧКИ!"
            color = (255, 255, 100)
        else:
            return

        self._floating_texts.append(FloatingText(
            x=pu.x, y=pu.y, text=text, color=color, life=800
        ))

        self._flash_timer = 200
        self._flash_color = color
        self._spawn_powerup_particles(pu.x, pu.y)

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_reward()

    def _award_near_miss(self) -> None:
        """Award bonus for near-miss."""
        fever_mult = self._fever_multiplier if self._fever_mode else 1.0
        bonus = int(50 * self._multiplier * fever_mult)
        self._score += bonus
        self._near_misses += 1

        self._floating_texts.append(FloatingText(
            x=self.PLAYER_X + 15, y=self._player_y - 25,
            text=f"БЛИЗКО! +{bonus}", color=(255, 150, 100), life=600
        ))

        # Sound for near miss
        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_score_up()

        # Achievement: 10 near-misses
        if self._near_misses == 10:
            self._floating_texts.append(FloatingText(
                x=64, y=40,
                text="МАСТЕР УКЛОНОВ!",
                color=(255, 200, 100), life=1200
            ))
            self._score += 500
            self._flash_timer = 300
            self._flash_color = (255, 200, 100)

            # Achievement sound!
            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_success()

    def _check_milestones(self) -> None:
        """Check for score milestones."""
        milestone_interval = 1000
        current_milestone = (self._score // milestone_interval) * milestone_interval

        if current_milestone > self._last_milestone and current_milestone > 0:
            self._last_milestone = current_milestone
            self._milestone_text = f"{current_milestone}!"
            self._milestone_timer = 1500

            self._flash_timer = 300
            self._flash_color = (255, 220, 100)

            # Bonus life every 5000
            if current_milestone % 5000 == 0:
                self._lives = min(5, self._lives + 1)
                self._milestone_text = f"+ЖИЗНЬ!"

                if hasattr(self.context, "audio") and self.context.audio:
                    self.context.audio.play_reward()

    def _spawn_obstacle(self) -> None:
        """Spawn a new obstacle."""
        obs_types = ["keg", "bottle", "box"]
        obs_type = random.choice(obs_types)

        if obs_type == "keg":
            width = random.randint(14, 20)
            height = random.randint(16, 22)
            color = (180, 80, 60)
        elif obs_type == "bottle":
            width = random.randint(8, 12)
            height = random.randint(20, 28)
            color = (100, 180, 100)
        else:  # box
            width = random.randint(16, 24)
            height = random.randint(14, 18)
            color = (160, 140, 100)

        self._obstacles.append(Obstacle(
            x=140, y=self.GROUND_Y - height,
            width=width, height=height,
            color=color, type=obs_type
        ))

    def _spawn_pickup(self) -> None:
        """Spawn a new pickup."""
        # Sometimes spawn in air, sometimes on ground path
        if random.random() < 0.6:
            y = random.randint(self.GROUND_Y - 45, self.GROUND_Y - 20)
        else:
            y = self.GROUND_Y - 10

        pk_type = random.choices(
            ["drink", "coin", "star"],
            weights=[0.6, 0.3, 0.1]
        )[0]

        if pk_type == "drink":
            color = random.choice([(255, 160, 220), (120, 255, 200), (255, 210, 120)])
            value = 100
            size = 8
        elif pk_type == "coin":
            color = (255, 220, 100)
            value = 50
            size = 6
        else:  # star
            color = (255, 255, 200)
            value = 200
            size = 10

        self._pickups.append(Pickup(
            x=140, y=y, size=size, color=color, value=value, type=pk_type
        ))

    def _spawn_powerup(self) -> None:
        """Spawn a power-up."""
        pu_type = random.choice(["shield", "magnet", "double"])
        y = random.randint(self.GROUND_Y - 50, self.GROUND_Y - 25)
        self._powerups.append(PowerUp(x=140, y=y, type=pu_type))

    # Particle spawning methods
    def _spawn_jump_particles(self) -> None:
        for _ in range(8):
            self._particles.append(Particle(
                x=self.PLAYER_X + random.uniform(-5, 5),
                y=self._player_y,
                vx=random.uniform(-40, 40),
                vy=random.uniform(20, 60),
                life=300, max_life=300,
                color=(200, 200, 200),
                size=random.uniform(2, 4)
            ))

    def _spawn_double_jump_particles(self) -> None:
        for _ in range(12):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(40, 80)
            self._particles.append(Particle(
                x=self.PLAYER_X,
                y=self._player_y - self.PLAYER_HEIGHT / 2,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=400, max_life=400,
                color=(255, 200, 100),
                size=random.uniform(2, 5)
            ))

    def _spawn_dash_particles(self) -> None:
        for _ in range(6):
            self._particles.append(Particle(
                x=self.PLAYER_X + random.uniform(-3, 3),
                y=self._player_y - random.uniform(0, 6),
                vx=random.uniform(-80, -40),
                vy=random.uniform(-20, 20),
                life=200, max_life=200,
                color=(150, 200, 255),
                size=random.uniform(3, 5)
            ))

    def _spawn_land_particles(self) -> None:
        for _ in range(6):
            self._particles.append(Particle(
                x=self.PLAYER_X + random.uniform(-8, 8),
                y=self.GROUND_Y,
                vx=random.uniform(-30, 30),
                vy=random.uniform(-40, -10),
                life=200, max_life=200,
                color=(150, 140, 130),
                size=random.uniform(2, 3)
            ))

    def _spawn_hit_particles(self) -> None:
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 120)
            self._particles.append(Particle(
                x=self.PLAYER_X,
                y=self._player_y - self.PLAYER_HEIGHT / 2,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 30,
                life=500, max_life=500,
                color=(255, 100, 100),
                size=random.uniform(2, 5)
            ))

    def _spawn_shield_break_particles(self) -> None:
        for _ in range(20):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(60, 100)
            self._particles.append(Particle(
                x=self.PLAYER_X,
                y=self._player_y - self.PLAYER_HEIGHT / 2,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=400, max_life=400,
                color=(100, 200, 255),
                size=random.uniform(3, 6)
            ))

    def _spawn_pickup_particles(self, x: float, y: float, color: tuple) -> None:
        for _ in range(8):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(30, 70)
            self._particles.append(Particle(
                x=x, y=y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 20,
                life=300, max_life=300,
                color=color,
                size=random.uniform(2, 4)
            ))

    def _spawn_powerup_particles(self, x: float, y: float) -> None:
        for _ in range(15):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(50, 100)
            self._particles.append(Particle(
                x=x, y=y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed,
                life=500, max_life=500,
                color=random.choice([(255, 255, 100), (100, 255, 200), (255, 100, 255)]),
                size=random.uniform(3, 6)
            ))

    def _spawn_trail_particle(self) -> None:
        self._particles.append(Particle(
            x=self.PLAYER_X - 5,
            y=self._player_y - self.PLAYER_HEIGHT / 2 + random.uniform(-3, 3),
            vx=random.uniform(-20, -10),
            vy=random.uniform(-5, 5),
            life=150, max_life=150,
            color=(255, 230, 150),
            size=random.uniform(1, 3)
        ))

    # Fever mode methods
    def _spawn_fever_star(self) -> None:
        """Spawn a fever mode background star."""
        colors = [
            (255, 100, 100), (255, 200, 100), (255, 255, 100),
            (100, 255, 100), (100, 255, 255), (100, 100, 255),
            (255, 100, 255)
        ]
        self._stars.append(StarBurst(
            x=130,
            y=random.uniform(10, 90),
            size=random.uniform(2, 6),
            speed=random.uniform(80, 150),
            color=random.choice(colors)
        ))

    def _update_fever_stars(self, dt: float) -> None:
        """Update fever stars."""
        for star in self._stars:
            star.x -= star.speed * dt
            star.size = max(0.5, star.size - dt)

        self._stars = [s for s in self._stars if s.x > -10 and s.size > 0.5]

    def _activate_fever_mode(self) -> None:
        """Activate fever mode for bonus scoring."""
        self._fever_mode = True
        self._fever_timer = 6000  # 6 seconds
        self._fever_multiplier = 2.0

        self._floating_texts.append(FloatingText(
            x=64, y=50,
            text="ОГОНЬ!",
            color=(255, 150, 50),
            life=1000
        ))

        # Play jackpot sound for fever mode!
        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_jackpot()

        self._flash_timer = 500
        self._flash_color = (255, 150, 50)

        # Spawn lots of stars
        for _ in range(15):
            self._spawn_fever_star()

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_reward()

    # Flying enemy methods
    def _spawn_flying_enemy(self) -> None:
        """Spawn a flying enemy."""
        pattern = random.choice(["sine", "dive", "hover"])

        if pattern == "dive":
            y = 20
            vy = 30
        else:
            y = random.randint(40, 70)
            vy = 0

        self._flying_enemies.append(FlyingEnemy(
            x=140,
            y=y,
            vx=-self._scroll_speed * 1.2,
            vy=vy,
            width=12,
            height=10,
            color=(255, 80, 120),
            pattern=pattern
        ))

    def _update_flying_enemies(self, dt: float, delta_ms: float) -> None:
        """Update flying enemies."""
        for enemy in self._flying_enemies:
            enemy.x += enemy.vx * dt
            enemy.phase += delta_ms * 0.005

            if enemy.pattern == "sine":
                enemy.y += math.sin(enemy.phase) * 40 * dt
            elif enemy.pattern == "dive":
                enemy.vy += 100 * dt
                enemy.y += enemy.vy * dt
            elif enemy.pattern == "hover":
                enemy.y += math.sin(enemy.phase * 2) * 20 * dt

        self._flying_enemies = [e for e in self._flying_enemies if e.x > -20]

    # Ground gap methods
    def _spawn_ground_gap(self) -> None:
        """Spawn a gap in the ground."""
        width = random.randint(20, 35)
        self._ground_gaps.append(GroundGap(
            x=140,
            width=width
        ))

    def _update_ground_gaps(self, dt: float) -> None:
        """Update ground gaps."""
        for gap in self._ground_gaps:
            gap.x -= self._scroll_speed * dt

        self._ground_gaps = [g for g in self._ground_gaps if g.x + g.width > -10]

    def _is_over_gap(self) -> bool:
        """Check if player is over a gap."""
        px = self.PLAYER_X
        for gap in self._ground_gaps:
            if gap.x < px < gap.x + gap.width:
                return True
        return False

    def _update_difficulty_name(self) -> None:
        """Update difficulty name based on current speed/distance."""
        if self._difficulty >= 3.0:
            self._difficulty_name = "БЕЗУМИЕ"
        elif self._difficulty >= 2.5:
            self._difficulty_name = "МАСТЕР"
        elif self._difficulty >= 2.0:
            self._difficulty_name = "СЛОЖНО"
        elif self._difficulty >= 1.5:
            self._difficulty_name = "СРЕДНЕ"
        else:
            self._difficulty_name = "ЛЕГКО"

    def _start_bonus_zone(self) -> None:
        """Start a bonus zone with extra pickups."""
        self._bonus_zone_active = True
        self._bonus_zone_timer = 5000  # 5 seconds
        self._bonus_zone_x = 128.0

        self._floating_texts.append(FloatingText(
            x=64, y=50,
            text="БОНУС ЗОНА!",
            color=(255, 215, 0),
            life=1000
        ))

        self._flash_timer = 300
        self._flash_color = (255, 215, 0)

        # Spawn extra pickups in the bonus zone
        for i in range(8):
            self._pickups.append(Pickup(
                x=140 + i * 15,
                y=random.randint(self.GROUND_Y - 45, self.GROUND_Y - 15),
                size=10,
                color=(255, 215, 0),  # Gold pickups
                value=200,
                type="star"
            ))

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_reward()

    def _draw_starfield(self, buffer: NDArray[np.uint8], t_sec: float, max_y: int) -> None:
        max_y = max(6, min(120, max_y))
        for i in range(18):
            speed = 4 + (i % 4) * 2
            sx = int((i * 23 + t_sec * speed * 12) % 128)
            sy = int((i * 17 + t_sec * speed * 6) % max_y)
            twinkle = 0.6 + 0.4 * math.sin(t_sec * 3 + i)
            color = (
                int(60 + 60 * twinkle),
                int(90 + 80 * twinkle),
                int(140 + 100 * twinkle),
            )
            draw_rect(buffer, sx, sy, 1, 1, color, filled=True)
            if i % 6 == 0 and sx + 1 < 128:
                draw_rect(buffer, sx + 1, sy, 1, 1, (180, 200, 255), filled=True)

    def _draw_neon_grid(
        self,
        buffer: NDArray[np.uint8],
        t_sec: float,
        horizon_y: int,
        floor_y: int,
        grid_color: tuple,
        glow_color: tuple,
    ) -> None:
        horizon_y = max(8, min(110, horizon_y))
        floor_y = max(horizon_y + 4, min(127, floor_y))
        phase = (t_sec * 0.6 * (self._scroll_speed / 80.0)) % 1.0
        lines = 7
        for i in range(lines):
            pct = (i / lines + phase) % 1.0
            y = int(horizon_y + (pct * pct) * (floor_y - horizon_y))
            draw_line(buffer, 0, y, 127, y, grid_color)

        center_x = 64
        for i in range(-6, 7):
            top_x = center_x + i * 6
            bottom_x = center_x + i * 14
            draw_line(buffer, top_x, horizon_y, bottom_x, floor_y, grid_color)

        draw_rect(buffer, 0, horizon_y, 128, 1, glow_color)

    def _draw_speed_streaks(self, buffer: NDArray[np.uint8], t_sec: float, max_y: int) -> None:
        if self._scroll_speed < 110:
            return
        max_y = max(8, max_y)
        for i in range(7):
            sx = int((t_sec * 90 + i * 23) % 128)
            sy = int(8 + (i * 14) % max_y)
            length = 4 + (i % 3)
            draw_rect(buffer, sx, sy, length, 1, (90, 130, 200), filled=True)

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        t = self._time_ms
        t_sec = t / 1000.0
        horizon_y = 42
        floor_y = self.GROUND_Y + 6

        # Fever mode background
        if self._fever_mode:
            hue = (t / 20) % 360
            for y in range(128):
                factor = y / 128
                r = int(40 + 30 * math.sin(math.radians(hue + y * 2)))
                g = int(20 + 20 * math.sin(math.radians(hue + 120 + y * 2)))
                b = int(50 + 30 * math.sin(math.radians(hue + 240 + y * 2)))
                buffer[y, :] = [r, g, b]
        else:
            # Background with parallax
            for y in range(128):
                factor = y / 128
                r = int(18 + 18 * factor + 8 * math.sin(t / 1200 + y * 0.12))
                g = int(20 + 20 * factor)
                b = int(40 + 50 * (1 - factor))
                buffer[y, :] = [r, g, b]

        # Neon sky details
        self._draw_starfield(buffer, t_sec, horizon_y)

        # Background buildings (parallax)
        building_offset = int(self._bg_offset * 0.3) % 64
        for i in range(5):
            bx = i * 35 - building_offset
            bh = 30 + (i * 17) % 25
            by = self.GROUND_Y - bh
            draw_rect(buffer, bx, by, 25, bh, (35, 30, 45), filled=True)

        # Neon grid floor
        self._draw_neon_grid(buffer, t_sec, horizon_y, floor_y, (40, 70, 110), (90, 140, 200))

        # Scanline effect (background only)
        buffer[::2] = (buffer[::2].astype(np.float32) * 0.88).astype(np.uint8)

        # Speed streaks in the sky
        self._draw_speed_streaks(buffer, t_sec, horizon_y - 6)

        # Flash effect
        if self._flash_timer > 0:
            intensity = self._flash_timer / 300
            for c in range(3):
                buffer[:, :, c] = np.clip(
                    buffer[:, :, c].astype(np.float32) + self._flash_color[c] * intensity * 0.2,
                    0, 255
                ).astype(np.uint8)

        # Shake
        shake_x = shake_y = 0
        if self._shake_timer > 0:
            amp = int(self._shake_intensity * self._shake_timer / 400)
            shake_x = random.randint(-amp, amp)
            shake_y = random.randint(-amp, amp)

        # Draw fever stars (background)
        for star in self._stars:
            sx = int(star.x) + shake_x
            sy = int(star.y) + shake_y
            if 0 < sx < 127 and 0 < sy < 127:
                size = max(1, int(star.size))
                draw_rect(buffer, sx, sy, size, size, star.color, filled=True)

        # Ground with moving pattern (with gaps)
        ground_y = self.GROUND_Y + shake_y + 4

        # Draw ground segments, skipping gaps
        for x in range(0, 128, 4):
            is_gap = False
            for gap in self._ground_gaps:
                if gap.x < x + shake_x < gap.x + gap.width:
                    is_gap = True
                    break
            if not is_gap:
                draw_rect(buffer, x, ground_y, 4, 30, (35, 30, 45))

        # Ground line (with gaps)
        for x in range(0, 128, 2):
            is_gap = False
            for gap in self._ground_gaps:
                if gap.x < x + shake_x < gap.x + gap.width:
                    is_gap = True
                    break
            if not is_gap:
                draw_rect(buffer, x, self.GROUND_Y + shake_y + 2, 2, 2, (110, 140, 200))

        # Draw gap depths (dark pit)
        for gap in self._ground_gaps:
            gx = int(gap.x) + shake_x
            if -gap.width < gx < 128:
                draw_rect(buffer, gx, self.GROUND_Y + shake_y + 4, gap.width, gap.depth, (15, 10, 20))
                # Gap edge highlights
                draw_rect(buffer, gx, self.GROUND_Y + shake_y + 2, 2, gap.depth, (50, 40, 60))
                draw_rect(buffer, gx + gap.width - 2, self.GROUND_Y + shake_y + 2, 2, gap.depth, (50, 40, 60))

        # Moving ground tiles (with gaps)
        tile_offset = int(self._bg_offset) % 16
        for i in range(-1, 10):
            tx = i * 16 - tile_offset
            is_gap = False
            for gap in self._ground_gaps:
                if gap.x < tx + shake_x + 7 < gap.x + gap.width:
                    is_gap = True
                    break
            if not is_gap:
                draw_rect(buffer, tx, ground_y + 4, 14, 2, (60, 70, 90))

        # Obstacles - Fun recognizable shapes!
        for obs in self._obstacles:
            x = int(obs.x) + shake_x
            y = int(obs.y) + shake_y
            w, h = obs.width, obs.height

            # Shadow
            draw_rect(buffer, x + 2, y + h - 2, w, 4, (20, 15, 25))

            if obs.type == "keg":
                # Wooden barrel/keg
                barrel_color = (139, 90, 43)  # Brown wood
                band_color = (100, 100, 100)  # Metal bands

                # Main barrel body (rounded look)
                draw_rect(buffer, x + 1, y, w - 2, h, barrel_color, filled=True)
                draw_rect(buffer, x, y + 2, w, h - 4, barrel_color, filled=True)

                # Metal bands
                draw_rect(buffer, x, y + 2, w, 2, band_color)
                draw_rect(buffer, x, y + h - 4, w, 2, band_color)

                # Wood grain lines
                draw_rect(buffer, x + w // 3, y + 1, 1, h - 2, (100, 60, 30))
                draw_rect(buffer, x + 2 * w // 3, y + 1, 1, h - 2, (100, 60, 30))

                # Highlight
                draw_rect(buffer, x + 1, y + 1, w - 2, 2, (180, 130, 80))

            elif obs.type == "bottle":
                # Green glass bottle
                bottle_color = (60, 140, 60)
                glass_shine = (120, 200, 120)

                # Bottle body (wider at bottom)
                draw_rect(buffer, x + 2, y + h - 8, w - 4, 8, bottle_color, filled=True)
                # Neck
                draw_rect(buffer, x + w // 2 - 2, y, 4, h - 6, bottle_color, filled=True)
                # Cap
                draw_rect(buffer, x + w // 2 - 2, y, 4, 3, (180, 150, 50))

                # Glass shine
                draw_rect(buffer, x + 3, y + h - 7, 2, 5, glass_shine)
                draw_rect(buffer, x + w // 2 - 1, y + 3, 1, h - 10, glass_shine)

            else:  # box/crate
                # Wooden crate
                crate_color = (160, 120, 70)
                dark_wood = (100, 70, 40)

                # Main body
                draw_rect(buffer, x, y, w, h, crate_color, filled=True)

                # Planks pattern
                draw_rect(buffer, x, y + h // 3, w, 1, dark_wood)
                draw_rect(buffer, x, y + 2 * h // 3, w, 1, dark_wood)
                draw_rect(buffer, x + w // 2, y, 1, h, dark_wood)

                # Cross pattern (X mark)
                for i in range(min(w, h) // 2):
                    draw_rect(buffer, x + i, y + i, 2, 2, dark_wood)
                    draw_rect(buffer, x + w - i - 2, y + i, 2, 2, dark_wood)

                # Corner nails
                nail_color = (80, 80, 90)
                draw_rect(buffer, x + 1, y + 1, 2, 2, nail_color)
                draw_rect(buffer, x + w - 3, y + 1, 2, 2, nail_color)
                draw_rect(buffer, x + 1, y + h - 3, 2, 2, nail_color)
                draw_rect(buffer, x + w - 3, y + h - 3, 2, 2, nail_color)

                # Highlight
                draw_rect(buffer, x, y, w, 2, (200, 160, 100))

            # Outline
            draw_rect(buffer, x, y, w, h, (0, 0, 0), filled=False)

        # Pickups - Recognizable collectibles!
        for pk in self._pickups:
            x = int(pk.x) + shake_x
            y = int(pk.y) + shake_y
            pulse = 1.0 + 0.15 * math.sin(pk.pulse * 3)
            size = int(pk.size * pulse)

            if pk.type == "drink":
                # Shot glass with amber liquid
                liquid_color = (200, 140, 60)  # Amber/whiskey color
                glass_color = (220, 220, 240)  # Clear glass
                glass_dark = (160, 160, 180)  # Glass shadow

                # Shot glass shape: wider at top, narrower at bottom
                # Base (narrow)
                base_w = max(4, size // 2)
                base_x = x + (size - base_w) // 2
                draw_rect(buffer, base_x, y + size - 2, base_w, 2, glass_dark, filled=True)

                # Glass body (tapered)
                for row in range(size - 2):
                    # Taper from top (wider) to bottom (narrower)
                    row_width = base_w + int((size - base_w) * (1 - row / (size - 2)))
                    row_x = x + (size - row_width) // 2
                    # Glass outline
                    if row < size - 3:
                        draw_rect(buffer, row_x, y + row, 1, 1, glass_color)
                        draw_rect(buffer, row_x + row_width - 1, y + row, 1, 1, glass_color)

                # Liquid inside (fills most of glass)
                liquid_top = y + 2
                liquid_bottom = y + size - 3
                for row in range(liquid_top, liquid_bottom):
                    rel_row = row - y
                    row_width = base_w + int((size - base_w) * (1 - rel_row / (size - 2))) - 2
                    row_x = x + (size - row_width) // 2
                    if row_width > 0:
                        draw_rect(buffer, row_x, row, row_width, 1, liquid_color, filled=True)

                # Glass rim at top (thin white line)
                rim_w = size - 2
                rim_x = x + 1
                draw_rect(buffer, rim_x, y, rim_w, 1, (255, 255, 255))

                # Shine on left side
                for row in range(size - 4):
                    rel_row = row + 2
                    row_width = base_w + int((size - base_w) * (1 - rel_row / (size - 2)))
                    shine_x = x + (size - row_width) // 2 + 1
                    if 0 <= shine_x < 128:
                        draw_rect(buffer, shine_x, y + rel_row, 1, 1, (255, 255, 255))

            elif pk.type == "coin":
                # Golden coin
                coin_color = (255, 215, 0)
                shine = (255, 255, 150)
                dark = (200, 160, 0)

                # Coin body (circular effect)
                cx, cy = x + size // 2, y + size // 2
                r = size // 2

                # Main circle
                for dy in range(-r, r + 1):
                    dx_max = int(math.sqrt(r * r - dy * dy))
                    draw_rect(buffer, cx - dx_max, cy + dy, dx_max * 2, 1, coin_color)

                # Inner circle (darker)
                r2 = r - 2
                if r2 > 0:
                    for dy in range(-r2, r2 + 1):
                        dx_max = int(math.sqrt(r2 * r2 - dy * dy))
                        draw_rect(buffer, cx - dx_max, cy + dy, dx_max * 2, 1, dark)

                # $ symbol in center
                draw_rect(buffer, cx - 1, cy - 2, 2, 5, shine)
                draw_rect(buffer, cx - 2, cy - 1, 1, 1, shine)
                draw_rect(buffer, cx + 1, cy + 1, 1, 1, shine)

                # Shine sparkle
                if int(t / 200) % 3 == 0:
                    draw_rect(buffer, cx - r + 1, cy - 1, 2, 2, (255, 255, 255))

            else:  # star
                # Sparkly star
                star_color = (255, 255, 100)
                bright = (255, 255, 255)

                cx, cy = x + size // 2, y + size // 2
                s = size // 2

                # Star shape (5 points)
                # Center
                draw_rect(buffer, cx - 1, cy - 1, 3, 3, star_color, filled=True)
                # Top point
                draw_rect(buffer, cx, cy - s, 1, s - 1, star_color)
                # Bottom point
                draw_rect(buffer, cx, cy + 2, 1, s - 1, star_color)
                # Left point
                draw_rect(buffer, cx - s, cy, s - 1, 1, star_color)
                # Right point
                draw_rect(buffer, cx + 2, cy, s - 1, 1, star_color)
                # Diagonal arms
                for i in range(s - 1):
                    draw_rect(buffer, cx - s + i + 1, cy - s + i + 1, 1, 1, star_color)
                    draw_rect(buffer, cx + s - i - 1, cy - s + i + 1, 1, 1, star_color)
                    draw_rect(buffer, cx - s + i + 1, cy + s - i - 1, 1, 1, star_color)
                    draw_rect(buffer, cx + s - i - 1, cy + s - i - 1, 1, 1, star_color)

                # Sparkle animation
                sparkle_phase = (t / 100 + pk.pulse) % (2 * math.pi)
                if sparkle_phase < 1.0:
                    draw_rect(buffer, cx, cy - s - 1, 1, 2, bright)
                    draw_rect(buffer, cx, cy + s, 1, 2, bright)

        # Power-ups - Distinctive icons!
        for pu in self._powerups:
            x = int(pu.x) + shake_x
            y = int(pu.y) + shake_y
            pulse = 1.0 + 0.2 * math.sin(pu.pulse * 2)
            size = int(10 * pulse)

            if pu.type == "shield":
                # Shield icon - blue with white border
                color = (100, 200, 255)
                glow = (50, 120, 180)

                # Glow
                draw_rect(buffer, x - size - 2, y - size - 2, size * 2 + 4, size * 2 + 4, glow, filled=True)

                # Shield shape (pointed bottom)
                draw_rect(buffer, x - size + 2, y - size, size * 2 - 4, size, color, filled=True)
                for i in range(size):
                    w = size * 2 - 4 - i * 2
                    if w > 0:
                        draw_rect(buffer, x - w // 2, y + i, w, 1, color)

                # Shield inner highlight
                draw_rect(buffer, x - size + 4, y - size + 2, size - 4, size - 4, (150, 220, 255))

                # White cross/emblem
                draw_rect(buffer, x - 1, y - size + 3, 2, size, (255, 255, 255))
                draw_rect(buffer, x - size + 4, y - 2, size * 2 - 8, 2, (255, 255, 255))

            elif pu.type == "magnet":
                # Magnet icon - horseshoe shape
                color = (255, 100, 255)
                glow = (180, 50, 180)

                # Glow
                draw_rect(buffer, x - size - 2, y - size - 2, size * 2 + 4, size * 2 + 4, glow, filled=True)

                # Horseshoe magnet
                # Left arm (red)
                draw_rect(buffer, x - size + 2, y - size + 2, 4, size + 4, (255, 80, 80), filled=True)
                # Right arm (blue)
                draw_rect(buffer, x + size - 6, y - size + 2, 4, size + 4, (80, 80, 255), filled=True)
                # Top connection
                draw_rect(buffer, x - size + 2, y - size + 2, size * 2 - 4, 4, color, filled=True)

                # Magnetic field lines
                for i in range(3):
                    ly = y + 2 + i * 3
                    if ly < y + size:
                        draw_rect(buffer, x - size + 6 + i, ly, size * 2 - 12 - i * 2, 1, (255, 200, 255))

            else:  # double points (2x)
                # 2x multiplier icon
                color = (255, 255, 100)
                glow = (180, 180, 50)

                # Glow
                draw_rect(buffer, x - size - 2, y - size - 2, size * 2 + 4, size * 2 + 4, glow, filled=True)

                # Background circle
                for dy in range(-size, size + 1):
                    dx_max = int(math.sqrt(size * size - dy * dy))
                    draw_rect(buffer, x - dx_max, y + dy, dx_max * 2, 1, color)

                # "2X" text
                # "2"
                draw_rect(buffer, x - 6, y - 4, 4, 1, (0, 0, 0))
                draw_rect(buffer, x - 3, y - 3, 1, 2, (0, 0, 0))
                draw_rect(buffer, x - 6, y - 1, 4, 1, (0, 0, 0))
                draw_rect(buffer, x - 6, y, 1, 2, (0, 0, 0))
                draw_rect(buffer, x - 6, y + 2, 4, 1, (0, 0, 0))
                # "X"
                draw_rect(buffer, x + 1, y - 3, 1, 1, (0, 0, 0))
                draw_rect(buffer, x + 4, y - 3, 1, 1, (0, 0, 0))
                draw_rect(buffer, x + 2, y - 1, 2, 2, (0, 0, 0))
                draw_rect(buffer, x + 1, y + 1, 1, 2, (0, 0, 0))
                draw_rect(buffer, x + 4, y + 1, 1, 2, (0, 0, 0))

        # Flying enemies - Bat/bird creatures!
        for enemy in self._flying_enemies:
            ex = int(enemy.x) + shake_x
            ey = int(enemy.y) + shake_y
            w, h = enemy.width, enemy.height

            # Shadow on ground
            shadow_w = int(w * 1.5)
            draw_rect(buffer, ex - (shadow_w - w) // 2, self.GROUND_Y + shake_y - 2, shadow_w, 3, (30, 20, 35))

            # Wing flap animation
            wing_phase = enemy.phase * 4
            wing_up = int(6 * math.sin(wing_phase))

            if enemy.pattern == "dive":
                # Angry red hawk/falcon
                body_color = (180, 60, 60)
                wing_color = (220, 80, 80)
                beak_color = (255, 200, 100)

                # Body (oval-ish)
                draw_rect(buffer, ex + 2, ey + 2, w - 4, h - 2, body_color, filled=True)
                draw_rect(buffer, ex, ey + 3, w, h - 4, body_color, filled=True)

                # Wings
                # Left wing
                for i in range(5):
                    wy = ey + 3 - wing_up + i
                    ww = 6 - i
                    draw_rect(buffer, ex - ww - 1, wy, ww, 2, wing_color)
                # Right wing
                for i in range(5):
                    wy = ey + 3 + wing_up + i
                    ww = 6 - i
                    draw_rect(buffer, ex + w + 1, wy, ww, 2, wing_color)

                # Head
                draw_rect(buffer, ex + w - 3, ey + 1, 4, 4, body_color, filled=True)
                # Beak
                draw_rect(buffer, ex + w, ey + 3, 3, 2, beak_color)
                # Angry eye
                draw_rect(buffer, ex + w - 2, ey + 2, 2, 2, (255, 255, 255))
                draw_rect(buffer, ex + w - 1, ey + 2, 1, 1, (200, 50, 50))
                # Angry eyebrow
                draw_rect(buffer, ex + w - 3, ey + 1, 3, 1, (100, 30, 30))

            elif enemy.pattern == "sine":
                # Purple bat
                body_color = (100, 60, 120)
                wing_color = (140, 80, 160)
                ear_color = (80, 40, 100)

                # Body
                draw_rect(buffer, ex + 2, ey + 2, w - 4, h - 2, body_color, filled=True)

                # Wings (bat-style with points)
                for i in range(6):
                    wy = ey + 2 - wing_up + abs(i - 2)
                    ww = 6 - abs(i - 3)
                    if ww > 0:
                        draw_rect(buffer, ex - ww - 1, wy + i, ww, 1, wing_color)
                        draw_rect(buffer, ex + w + 1, wy + i, ww, 1, wing_color)

                # Wing membrane detail
                draw_rect(buffer, ex - 4, ey + 4 - wing_up, 1, 3, (60, 30, 80))
                draw_rect(buffer, ex + w + 3, ey + 4 + wing_up, 1, 3, (60, 30, 80))

                # Ears
                draw_rect(buffer, ex + 2, ey, 2, 3, ear_color)
                draw_rect(buffer, ex + w - 4, ey, 2, 3, ear_color)

                # Face
                # Eyes (glowing)
                draw_rect(buffer, ex + 3, ey + 3, 2, 2, (255, 100, 100))
                draw_rect(buffer, ex + w - 5, ey + 3, 2, 2, (255, 100, 100))
                # Fangs
                draw_rect(buffer, ex + 4, ey + h - 2, 1, 2, (255, 255, 255))
                draw_rect(buffer, ex + w - 5, ey + h - 2, 1, 2, (255, 255, 255))

            else:  # hover - green bee/wasp
                body_color = (180, 180, 50)
                wing_color = (200, 220, 255)
                stripe_color = (40, 40, 0)

                # Body with stripes
                draw_rect(buffer, ex + 1, ey + 2, w - 2, h - 2, body_color, filled=True)
                # Stripes
                for i in range(3):
                    draw_rect(buffer, ex + 2 + i * 4, ey + 2, 2, h - 2, stripe_color)

                # Wings (transparent-ish, fast flapping)
                wing_flap = int(3 * math.sin(wing_phase * 2))
                # Left wing
                draw_rect(buffer, ex - 3, ey + wing_flap, 5, 4, wing_color)
                draw_rect(buffer, ex - 2, ey + 1 + wing_flap, 3, 2, (255, 255, 255))
                # Right wing
                draw_rect(buffer, ex + w - 2, ey - wing_flap, 5, 4, wing_color)
                draw_rect(buffer, ex + w - 1, ey + 1 - wing_flap, 3, 2, (255, 255, 255))

                # Head
                draw_rect(buffer, ex + w - 2, ey + 2, 3, 4, (60, 60, 20))
                # Eyes
                draw_rect(buffer, ex + w, ey + 3, 2, 2, (255, 100, 100))
                # Stinger
                draw_rect(buffer, ex - 2, ey + h // 2, 3, 2, (80, 80, 80))

        # Particles
        for p in self._particles:
            px = int(p.x) + shake_x
            py = int(p.y) + shake_y
            if 0 < px < 127 and 0 < py < 127:
                alpha = p.life / p.max_life
                size = max(1, int(p.size))
                color = tuple(int(c * alpha) for c in p.color)
                draw_rect(buffer, px, py, size, size, color, filled=True)

        # Player - Fun character sprite!
        px = int(self.PLAYER_X) + shake_x
        py = int(self._player_y) + shake_y

        # Player shadow (oval)
        shadow_y = self.GROUND_Y + shake_y + 2
        shadow_scale = max(0.3, 1.0 - (self.GROUND_Y - self._player_y) / 50)
        shadow_w = int(12 * shadow_scale)
        shadow_h = max(2, int(4 * shadow_scale))
        draw_rect(buffer, px - shadow_w // 2, shadow_y, shadow_w, shadow_h, (20, 15, 30))

        # Invincibility flash
        show_player = True
        if self._invincible_timer > 0:
            show_player = int(t / 80) % 2 == 0

        if show_player:
            # Animation phase
            run_phase = self._run_frame
            bob = int(2 * abs(math.sin(run_phase * 2)))  # Body bob

            # Colors based on state
            if self._state == PlayerState.HIT:
                skin = (255, 180, 180)
                shirt = (255, 80, 80)
                pants = (180, 60, 60)
            elif self._state == PlayerState.DASHING:
                skin = (200, 220, 255)
                shirt = (100, 150, 255)
                pants = (60, 100, 200)
            else:
                skin = (255, 220, 180)
                shirt = (255, 100, 100)  # Red shirt
                pants = (80, 80, 180)    # Blue pants

            # Squash and stretch
            stretch = 1.0 + self._player_vy * 0.0008
            stretch = max(0.8, min(1.2, stretch))

            if self._state == PlayerState.DASHING:
                # Sliding pose - horizontal
                # Body (horizontal)
                draw_rect(buffer, px - 7, py - 6, 14, 6, shirt, filled=True)
                # Head
                draw_rect(buffer, px + 4, py - 8, 5, 5, skin, filled=True)
                # Hair
                draw_rect(buffer, px + 5, py - 9, 4, 2, (80, 50, 30))
                # Legs stretched back
                draw_rect(buffer, px - 9, py - 5, 5, 3, pants, filled=True)
                # Eye
                draw_rect(buffer, px + 7, py - 7, 1, 1, (40, 40, 40))
            else:
                body_y = py - bob

                # Legs (animated)
                leg_phase = math.sin(run_phase * 2.5)
                left_leg_y = body_y - 4 + int(2 * leg_phase)
                right_leg_y = body_y - 4 - int(2 * leg_phase)

                if self._state in [PlayerState.JUMPING, PlayerState.DOUBLE_JUMPING, PlayerState.FALLING]:
                    # Legs tucked in air
                    left_leg_y = body_y - 3
                    right_leg_y = body_y - 3
                    draw_rect(buffer, px - 4, left_leg_y, 3, 4, pants)
                    draw_rect(buffer, px + 1, right_leg_y, 3, 4, pants)
                    # Shoes
                    draw_rect(buffer, px - 4, left_leg_y + 3, 3, 2, (60, 40, 30))
                    draw_rect(buffer, px + 1, right_leg_y + 3, 3, 2, (60, 40, 30))
                else:
                    # Running legs
                    draw_rect(buffer, px - 3, left_leg_y, 2, 5, pants)
                    draw_rect(buffer, px + 1, right_leg_y, 2, 5, pants)
                    # Shoes
                    draw_rect(buffer, px - 3, left_leg_y + 4, 3, 2, (60, 40, 30))
                    draw_rect(buffer, px + 1, right_leg_y + 4, 3, 2, (60, 40, 30))

                # Body (torso)
                torso_h = int(6 * stretch)
                draw_rect(buffer, px - 4, body_y - 10, 8, torso_h, shirt, filled=True)

                # Arms (animated)
                arm_swing = int(3 * math.sin(run_phase * 2.5))
                if self._state in [PlayerState.JUMPING, PlayerState.DOUBLE_JUMPING]:
                    # Arms up in air
                    draw_rect(buffer, px - 6, body_y - 12, 2, 4, skin)
                    draw_rect(buffer, px + 4, body_y - 12, 2, 4, skin)
                else:
                    # Swinging arms
                    draw_rect(buffer, px - 5, body_y - 9 + arm_swing, 2, 4, skin)
                    draw_rect(buffer, px + 3, body_y - 9 - arm_swing, 2, 4, skin)

                # Head
                head_y = body_y - 16
                draw_rect(buffer, px - 3, head_y, 6, 6, skin, filled=True)

                # Hair (spiky)
                hair_color = (80, 50, 30)
                draw_rect(buffer, px - 3, head_y - 2, 6, 3, hair_color)
                draw_rect(buffer, px - 2, head_y - 3, 2, 2, hair_color)
                draw_rect(buffer, px + 1, head_y - 3, 2, 2, hair_color)

                # Face
                # Eyes
                eye_y = head_y + 2
                draw_rect(buffer, px - 2, eye_y, 2, 2, (255, 255, 255))
                draw_rect(buffer, px + 1, eye_y, 2, 2, (255, 255, 255))
                # Pupils (look forward/up based on state)
                pupil_offset = 0 if self._state == PlayerState.RUNNING else -1
                draw_rect(buffer, px - 1, eye_y + pupil_offset, 1, 1, (40, 40, 40))
                draw_rect(buffer, px + 2, eye_y + pupil_offset, 1, 1, (40, 40, 40))

                # Mouth (smile or O based on state)
                if self._state in [PlayerState.JUMPING, PlayerState.DOUBLE_JUMPING]:
                    # Excited O mouth
                    draw_rect(buffer, px, head_y + 4, 2, 2, (200, 100, 100))
                else:
                    # Smile
                    draw_rect(buffer, px - 1, head_y + 5, 3, 1, (200, 100, 100))

                # Double jump sparkles
                if self._state == PlayerState.DOUBLE_JUMPING:
                    for i in range(4):
                        sx = px + int(8 * math.cos(t / 50 + i * 1.57))
                        sy = body_y - 8 + int(6 * math.sin(t / 50 + i * 1.57))
                        if 0 < sx < 127 and 0 < sy < 127:
                            draw_rect(buffer, sx, sy, 2, 2, (255, 255, 100))

        # Shield effect
        if self._shield_active:
            shield_pulse = 0.5 + 0.5 * math.sin(t / 100)
            shield_color = (int(100 * shield_pulse), int(200 * shield_pulse), 255)
            # Draw shield bubble
            for angle in range(0, 360, 30):
                rad = math.radians(angle)
                sx = px + int(12 * math.cos(rad + t / 200))
                sy = py - self.PLAYER_HEIGHT // 2 + int(10 * math.sin(rad + t / 200))
                if 0 < sx < 127 and 0 < sy < 127:
                    buffer[sy, sx] = shield_color

        # Floating texts
        for ft in self._floating_texts:
            fx = int(ft.x) + shake_x
            fy = int(ft.y) + shake_y
            alpha = ft.life / 600
            color = tuple(int(c * alpha) for c in ft.color)
            # Simple text (would need proper text rendering)
            draw_centered_text(buffer, ft.text, fy, color, scale=1)

        # HUD
        # Score
        score_color = (255, 215, 0) if self._is_new_high_score else (255, 255, 255)
        draw_centered_text(buffer, f"СЧЁТ {self._score:05d}", 2, score_color, scale=1)

        # High score (if exists)
        if self._high_score > 0:
            draw_rect(buffer, 2, 11, 45, 7, (30, 30, 50))
            hs_text = f"HS:{self._high_score}"
            from artifact.graphics.text_utils import draw_text
            draw_text(buffer, hs_text, 3, 12, (150, 150, 200), scale=1)

        # Lives
        for i in range(self._lives):
            draw_rect(buffer, 4 + i * 10, 2, 8, 8, (255, 80, 100), filled=True)

        # Distance and difficulty
        diff_colors = {
            "ЛЕГКО": (100, 255, 100),
            "СРЕДНЕ": (255, 255, 100),
            "СЛОЖНО": (255, 180, 100),
            "МАСТЕР": (255, 100, 100),
            "БЕЗУМИЕ": (255, 100, 255),
        }
        diff_color = diff_colors.get(self._difficulty_name, (255, 255, 255))
        draw_rect(buffer, 80, 2, 46, 8, (30, 30, 50))
        from artifact.graphics.text_utils import draw_text
        draw_text(buffer, f"{int(self._distance)}м", 82, 3, diff_color, scale=1)

        # Combo
        if self._combo >= 2:
            combo_color = (255, 255, 100) if int(t / 150) % 2 == 0 else (255, 200, 50)
            draw_centered_text(buffer, f"x{self._combo} КОМБО", 14, combo_color, scale=1)

        # Bonus zone indicator
        if self._bonus_zone_active:
            bonus_pct = self._bonus_zone_timer / 5000
            bar_width = int(50 * bonus_pct)
            draw_rect(buffer, 39, 24, bar_width, 4, (255, 215, 0))
            draw_centered_text(buffer, "БОНУС!", 20, (255, 215, 0), scale=1)

        # Fever mode indicator
        if self._fever_mode:
            fever_pct = self._fever_timer / 6000
            bar_width = int(60 * fever_pct)
            hue = (t / 5) % 360
            fever_color = (
                int(128 + 127 * math.sin(math.radians(hue))),
                int(128 + 127 * math.sin(math.radians(hue + 120))),
                int(128 + 127 * math.sin(math.radians(hue + 240)))
            )
            draw_rect(buffer, 34, 24, bar_width, 4, fever_color)
            draw_centered_text(buffer, "ОГОНЬ!", 20, fever_color, scale=1)

        # Active power-ups indicators (durations match new shorter times)
        indicator_y = 118
        if self._shield_timer > 0:
            pct = self._shield_timer / 4000  # Updated to match new 4s duration
            draw_rect(buffer, 4, indicator_y, int(25 * pct), 3, (100, 200, 255))

        if self._magnet_timer > 0:
            pct = self._magnet_timer / 4000  # Updated to match new 4s duration
            draw_rect(buffer, 35, indicator_y, int(25 * pct), 3, (255, 100, 255))

        if self._double_points_timer > 0:
            pct = self._double_points_timer / 5000  # Updated to match new 5s duration
            draw_rect(buffer, 66, indicator_y, int(25 * pct), 3, (255, 255, 100))

        # Milestone text
        if self._milestone_timer > 0:
            alpha = min(1.0, self._milestone_timer / 300)
            color = (int(255 * alpha), int(220 * alpha), int(100 * alpha))
            draw_centered_text(buffer, self._milestone_text, 50, color, scale=2)

        # Game over
        if self._game_over:
            buffer[:] = (buffer * 0.4).astype(np.uint8)

            bob = int(3 * math.sin(t / 200))
            draw_centered_text(buffer, "ИГРА", 40 + bob, (255, 80, 80), scale=2)
            draw_centered_text(buffer, "ОКОНЧЕНА", 60 + bob, (255, 80, 80), scale=2)

            draw_centered_text(buffer, f"СЧЁТ: {self._score}", 85, (255, 255, 255), scale=1)
            draw_centered_text(buffer, f"ДИСТ: {int(self._distance)}м", 97, (200, 200, 200), scale=1)

            if self._max_combo >= 3:
                draw_centered_text(buffer, f"МАКС КОМБО: {self._max_combo}x", 109, (255, 200, 100), scale=1)
        else:
            # Tutorial hints for new players
            if self._tutorial_timer > 0 and not self._first_jump_done:
                alpha = min(1.0, self._tutorial_timer / 500)
                hint_color = (int(200 * alpha), int(255 * alpha), int(200 * alpha))
                draw_centered_text(buffer, "ЖМАКАЙ ДЛЯ", 50, hint_color, scale=1)
                draw_centered_text(buffer, "ПРЫЖКА!", 60, hint_color, scale=1)
            elif self._tutorial_timer > 0 and self._first_jump_done and not self._first_double_done:
                alpha = min(1.0, self._tutorial_timer / 500)
                hint_color = (int(255 * alpha), int(200 * alpha), int(100 * alpha))
                draw_centered_text(buffer, "ЖМАКАЙ В", 50, hint_color, scale=1)
                draw_centered_text(buffer, "ВОЗДУХЕ!", 60, hint_color, scale=1)
            else:
                draw_animated_text(buffer, "ЖМАКАЙ", 108, (150, 150, 150), t, TextEffect.PULSE, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker as extension of main display - shows sky area above the game."""
        from artifact.graphics.primitives import clear, draw_rect

        clear(buffer)

        # Ticker is 48x8 pixels - shows the sky above the main game view
        t = self._time_ms
        t_sec = t / 1000.0

        # Sky background
        if self._fever_mode:
            # Rainbow cycling for fever mode
            hue = (t / 15) % 360
            for y in range(8):
                r = int(60 + 50 * math.sin(math.radians(hue + y * 25)))
                g = int(60 + 50 * math.sin(math.radians(hue + 120 + y * 25)))
                b = int(60 + 50 * math.sin(math.radians(hue + 240 + y * 25)))
                buffer[y, :] = [r, g, b]
        else:
            # Normal sky gradient (deep blue to neon haze)
            for y in range(8):
                factor = y / 8
                r = int(12 + 10 * factor)
                g = int(18 + 18 * factor)
                b = int(35 + 45 * (1 - factor))
                buffer[y, :] = [r, g, b]

            # Subtle star twinkles
            for i in range(6):
                sx = int((i * 9 + t_sec * (6 + i)) % 48)
                sy = i % 4
                twinkle = 0.6 + 0.4 * math.sin(t_sec * 3 + i)
                color = (int(80 * twinkle), int(120 * twinkle), int(180 * twinkle))
                draw_rect(buffer, sx, sy, 1, 1, color, filled=True)

            # Horizon glow line
            draw_rect(buffer, 0, 7, 48, 1, (60, 100, 160))

        # Draw fever stars that extend into ticker area (stars move right to left)
        for star in self._stars:
            # Map from main screen (128 wide) to ticker (48 wide)
            ticker_x = int(star.x * 48 / 128)
            # Stars in upper area of screen map to ticker
            if star.y < 20:  # Stars in top 20px of main can show on ticker
                ticker_y = int((star.y / 20) * 8)  # Map 0-20 to 0-8
                if 0 <= ticker_x < 48 and 0 <= ticker_y < 8:
                    size = max(1, int(star.size * 48 / 128))
                    draw_rect(buffer, ticker_x, ticker_y, size, size, star.color, filled=True)

        # Scanline effect
        buffer[::2] = (buffer[::2].astype(np.float32) * 0.9).astype(np.uint8)

        # Draw flying enemies that extend above main screen
        for enemy in self._flying_enemies:
            if enemy.y < 0:  # Enemy above main display
                ticker_x = int(enemy.x * 48 / 128)
                ticker_y = int((enemy.y + 8))  # Map -8..0 to 0..8
                if 0 <= ticker_x < 48 and 0 <= ticker_y < 8:
                    # Draw simple shape for enemy in ticker
                    size = max(2, int(enemy.width * 48 / 128 / 2))
                    color = enemy.color
                    draw_rect(buffer, ticker_x, ticker_y, size, size, color, filled=True)

        # Draw particles that go above main screen
        for p in self._particles:
            if p.y < 0:  # Particle above main display
                ticker_x = int(p.x * 48 / 128)
                ticker_y = int((p.y + 8))  # Map -8..0 to 0..8
                if 0 <= ticker_x < 48 and 0 <= ticker_y < 8:
                    alpha = p.life / p.max_life
                    size = max(1, int(p.size * 48 / 128))
                    color = tuple(int(c * alpha) for c in p.color)
                    draw_rect(buffer, ticker_x, ticker_y, size, size, color, filled=True)

        # Compact HUD on ticker: score on right, combo on left
        digit_color = (150, 255, 200) if not self._game_over else (255, 100, 100)

        # Score (right side)
        score_text = f"{self._score:04d}"
        digit_x = 30
        for ch in score_text[-4:]:
            self._draw_tiny_digit(buffer, ch, digit_x, 2, digit_color)
            digit_x += 4

        # Combo indicator (left side)
        if self._combo >= 2:
            combo_color = (255, 220, 100) if int(t / 150) % 2 == 0 else (255, 180, 50)
            self._draw_tiny_digit(buffer, 'x', 2, 2, combo_color)
            self._draw_tiny_digit(buffer, str(min(9, self._combo)), 6, 2, combo_color)

        # Fever indicator (pulsing bar at bottom of ticker)
        if self._fever_mode:
            fever_pct = self._fever_timer / 6000
            bar_width = int(48 * fever_pct)
            hue = (t / 10) % 360
            fever_color = (
                int(200 + 55 * math.sin(math.radians(hue))),
                int(100 + 100 * math.sin(math.radians(hue + 120))),
                int(100 + 100 * math.sin(math.radians(hue + 240)))
            )
            draw_rect(buffer, 0, 7, bar_width, 1, fever_color)

    def _draw_tiny_digit(self, buffer: NDArray[np.uint8], char: str, x: int, y: int, color: tuple) -> None:
        """Draw a tiny 3x5 digit on the ticker display."""
        # Simple 3x5 pixel font for digits
        patterns = {
            '0': [(0,0),(1,0),(2,0),(0,1),(2,1),(0,2),(2,2),(0,3),(2,3),(0,4),(1,4),(2,4)],
            '1': [(1,0),(1,1),(1,2),(1,3),(1,4)],
            '2': [(0,0),(1,0),(2,0),(2,1),(0,2),(1,2),(2,2),(0,3),(0,4),(1,4),(2,4)],
            '3': [(0,0),(1,0),(2,0),(2,1),(1,2),(2,2),(2,3),(0,4),(1,4),(2,4)],
            '4': [(0,0),(2,0),(0,1),(2,1),(0,2),(1,2),(2,2),(2,3),(2,4)],
            '5': [(0,0),(1,0),(2,0),(0,1),(0,2),(1,2),(2,2),(2,3),(0,4),(1,4),(2,4)],
            '6': [(0,0),(1,0),(2,0),(0,1),(0,2),(1,2),(2,2),(0,3),(2,3),(0,4),(1,4),(2,4)],
            '7': [(0,0),(1,0),(2,0),(2,1),(2,2),(2,3),(2,4)],
            '8': [(0,0),(1,0),(2,0),(0,1),(2,1),(0,2),(1,2),(2,2),(0,3),(2,3),(0,4),(1,4),(2,4)],
            '9': [(0,0),(1,0),(2,0),(0,1),(2,1),(0,2),(1,2),(2,2),(2,3),(0,4),(1,4),(2,4)],
            'x': [(0,0),(2,0),(1,1),(1,2),(0,3),(2,3),(0,4),(2,4)],
        }
        if char in patterns:
            for dx, dy in patterns[char]:
                px, py = x + dx, y + dy
                if 0 <= px < 48 and 0 <= py < 8:
                    buffer[py, px] = color

    def get_lcd_text(self) -> str:
        if self._game_over:
            return f"KONEC {self._score:05d}"[:16]
        return f"BEGI {self._score:05d}"[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._score >= 500,
            data={
                "score": self._score,
                "distance": int(self._distance),
                "max_combo": self._max_combo,
            },
            display_text=f"СЧЁТ {self._score} ДИСТ {int(self._distance)}м",
            ticker_text="ЕЩЁ РАЗ?",
            lcd_text=f"BEGI {self._score:05d}",
            should_print=False,
        )
        self.complete(result)

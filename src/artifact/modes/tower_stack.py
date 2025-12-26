"""Tower Stack - Classic arcade tower builder.

Stack blocks perfectly, climb higher, don't miss!
Inspired by classic stacker arcade games with proper physics.
"""

import math
import random
import logging
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text, draw_animated_text, TextEffect
from artifact.utils.camera_service import camera_service

logger = logging.getLogger(__name__)


class PlacementQuality(Enum):
    PERFECT = "PERFECT"
    GREAT = "GREAT"
    GOOD = "GOOD"
    OK = "OK"
    MISS = "MISS"


@dataclass
class StackedBlock:
    """A block placed on the tower."""
    x: float  # Center X
    width: float
    y: float  # Top Y in world coords
    color: tuple
    height: int = 10


@dataclass
class FallingPiece:
    """Piece that fell off - animates down."""
    x: float
    y: float
    width: float
    height: int
    color: tuple
    vy: float = 0.0
    vx: float = 0.0
    rotation: float = 0.0
    rot_speed: float = 0.0


@dataclass
class Particle:
    """Visual effect particle."""
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple
    size: float = 2.0


@dataclass
class PowerUp:
    """Collectible power-up."""
    x: float
    y: float
    type: str  # "wide", "slow", "life"
    pulse: float = 0.0


@dataclass
class BonusBlock:
    """Special bonus block that gives extra rewards."""
    x: float
    y: float
    width: float
    type: str  # "gold", "rainbow", "bomb"
    pulse: float = 0.0
    collected: bool = False


@dataclass
class StarBurst:
    """Background star effect for fever mode."""
    x: float
    y: float
    size: float
    speed: float
    color: tuple


class TowerStackMode(BaseMode):
    """Classic tower stacking with proper physics and addictive mechanics."""

    name = "tower_stack"
    display_name = "БАШНЯ"
    icon = "tower"
    style = "arcade"
    description = "Строй башню ровно, не промахнись!"

    # Constants
    BLOCK_HEIGHT = 10
    GROUND_Y = 115
    INITIAL_WIDTH = 50
    MIN_WIDTH = 6
    SWING_Y = 15  # Y position of swinging block

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._time_ms = 0.0

        # Tower state
        self._tower: List[StackedBlock] = []
        self._falling_pieces: List[FallingPiece] = []
        self._particles: List[Particle] = []
        self._powerups: List[PowerUp] = []

        # Swinging block state
        self._swing_x = 64.0
        self._swing_dir = 1
        self._swing_speed = 70.0
        self._current_width = self.INITIAL_WIDTH
        self._next_block_y = self.GROUND_Y - self.BLOCK_HEIGHT

        # Camera
        self._camera_y = 0.0
        self._target_camera_y = 0.0

        # Game state
        self._lives = 3
        self._score = 0
        self._streak = 0
        self._max_streak = 0
        self._best_height = 0
        self._combo_multiplier = 1.0
        self._game_over = False
        self._game_over_timer = 0.0
        self._placement_text = ""
        self._placement_timer = 0.0

        # Power-up states
        self._slow_mo_timer = 0.0
        self._wide_block_timer = 0.0

        # Visual effects
        self._shake_timer = 0.0
        self._shake_intensity = 0.0
        self._flash_timer = 0.0
        self._flash_color = (255, 255, 255)
        self._bg_pulse = 0.0

        # Fever mode (activated on high streaks)
        self._fever_mode = False
        self._fever_timer = 0.0
        self._fever_multiplier = 1.0
        self._stars: List[StarBurst] = []

        # Bonus blocks
        self._bonus_blocks: List[BonusBlock] = []
        self._next_bonus_height = 5  # Spawn bonus at this tower height

        # Tutorial
        self._tutorial_shown = False
        self._tutorial_timer = 0.0

        # Achievements/milestones
        self._perfect_streak = 0
        self._total_perfects = 0
        self._consecutive_hits = 0  # Non-miss placements in a row (for alt fever trigger)
        self._recent_misses = 0  # Misses in last 3 placements (for catch-up)
        self._last_milestone = 0  # Last celebrated height milestone

        # High score (session-based)
        self._high_score = 0
        self._is_new_high_score = False

        # Difficulty progression
        self._difficulty_level = 1
        self._difficulty_name = "ЛЕГКО"

        # Bonus stages
        self._bonus_stage = False
        self._bonus_timer = 0.0
        self._bonus_blocks_placed = 0

        # Camera background (uses shared camera service)
        self._camera_frame: Optional[NDArray] = None
        self._camera = camera_service.is_running

    def on_enter(self) -> None:
        self._time_ms = 0.0

        # Clear everything
        self._tower.clear()
        self._falling_pieces.clear()
        self._particles.clear()
        self._powerups.clear()

        # Foundation block
        foundation = StackedBlock(
            x=64.0,
            width=self.INITIAL_WIDTH,
            y=self.GROUND_Y - self.BLOCK_HEIGHT,
            color=(80, 80, 100),
            height=self.BLOCK_HEIGHT
        )
        self._tower.append(foundation)

        # Reset swing
        self._swing_x = 64.0
        self._swing_dir = 1
        self._swing_speed = 70.0
        self._current_width = self.INITIAL_WIDTH
        self._next_block_y = self.GROUND_Y - 2 * self.BLOCK_HEIGHT

        # Reset camera
        self._camera_y = 0.0
        self._target_camera_y = 0.0

        # Reset game state
        self._lives = 3
        self._score = 0
        self._streak = 0
        self._max_streak = 0
        self._best_height = 0
        self._combo_multiplier = 1.0
        self._game_over = False
        self._game_over_timer = 0.0
        self._placement_text = ""
        self._placement_timer = 0.0

        # Reset power-ups
        self._slow_mo_timer = 0.0
        self._wide_block_timer = 0.0

        # Reset effects
        self._shake_timer = 0.0
        self._flash_timer = 0.0
        self._bg_pulse = 0.0

        # Reset fever mode
        self._fever_mode = False
        self._fever_timer = 0.0
        self._fever_multiplier = 1.0
        self._stars.clear()

        # Reset bonus blocks
        self._bonus_blocks.clear()
        self._next_bonus_height = 5

        # Reset tutorial
        self._tutorial_shown = False
        self._tutorial_timer = 2000.0

        # Reset achievements
        self._perfect_streak = 0
        self._total_perfects = 0

        # High score persists across games
        self._is_new_high_score = False

        # Reset difficulty
        self._difficulty_level = 1
        self._difficulty_name = "ЛЕГКО"

        # Reset bonus stage
        self._bonus_stage = False
        self._bonus_timer = 0.0
        self._bonus_blocks_placed = 0

        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        """Cleanup - don't stop shared camera service."""
        self._camera = None
        self._camera_frame = None

    def on_input(self, event: Event) -> bool:
        if self.phase != ModePhase.ACTIVE:
            return False

        if self._game_over:
            return False

        if event.type == EventType.BUTTON_PRESS:
            logger.info("TowerStack: DROP!")
            self._drop_block()
            return True

        elif event.type == EventType.ARCADE_LEFT:
            self._swing_speed = max(40.0, self._swing_speed - 15)
            return True

        elif event.type == EventType.ARCADE_RIGHT:
            self._swing_speed = min(180.0, self._swing_speed + 15)
            return True

        return False

    def on_update(self, delta_ms: float) -> None:
        if self.phase != ModePhase.ACTIVE:
            return

        # Slow-mo effect
        time_scale = 0.4 if self._slow_mo_timer > 0 else 1.0
        dt = (delta_ms / 1000.0) * time_scale
        self._time_ms += delta_ms

        # Game over countdown
        if self._game_over:
            self._game_over_timer += delta_ms
            if self._game_over_timer > 2500:
                self._complete()
            # Still update falling pieces for visual
            self._update_falling_pieces(dt)
            self._update_particles(dt)
            return

        # Swing the block
        actual_speed = self._swing_speed
        if self._slow_mo_timer > 0:
            actual_speed *= 0.4

        self._swing_x += self._swing_dir * actual_speed * dt

        # Bounce off edges with some margin for block width
        half_w = self._current_width / 2
        if self._swing_x - half_w <= 5:
            self._swing_x = 5 + half_w
            self._swing_dir = 1
        elif self._swing_x + half_w >= 123:
            self._swing_x = 123 - half_w
            self._swing_dir = -1

        # Update falling pieces
        self._update_falling_pieces(dt)

        # Update particles
        self._update_particles(dt)

        # Update power-ups
        self._update_powerups(dt)

        # Decay timers
        self._shake_timer = max(0.0, self._shake_timer - delta_ms)
        self._flash_timer = max(0.0, self._flash_timer - delta_ms)
        self._placement_timer = max(0.0, self._placement_timer - delta_ms)
        self._slow_mo_timer = max(0.0, self._slow_mo_timer - delta_ms)
        self._wide_block_timer = max(0.0, self._wide_block_timer - delta_ms)
        self._tutorial_timer = max(0.0, self._tutorial_timer - delta_ms)

        # Fever mode timer and effects
        if self._fever_mode:
            self._fever_timer -= delta_ms
            if self._fever_timer <= 0:
                self._fever_mode = False
                self._fever_multiplier = 1.0
            else:
                # Spawn fever stars
                if random.random() < 0.3:
                    self._spawn_fever_star()

        # Update fever stars
        self._update_fever_stars(dt)

        # Update bonus blocks
        self._update_bonus_blocks(dt)

        # Smooth camera scroll
        camera_diff = self._target_camera_y - self._camera_y
        self._camera_y += camera_diff * 4.0 * dt

        # Background pulse
        self._bg_pulse = (self._bg_pulse + delta_ms * 0.003) % (2 * math.pi)

        # Spawn power-ups occasionally (increased rate)
        if random.random() < 0.0008 * delta_ms and len(self._powerups) < 3:
            self._spawn_powerup()

        # Update difficulty based on tower height
        self._update_difficulty()

        # Bonus stage timer
        if self._bonus_stage:
            self._bonus_timer -= delta_ms
            if self._bonus_timer <= 0:
                self._end_bonus_stage()

        # Check for high score
        if self._score > self._high_score:
            if not self._is_new_high_score and self._high_score > 0:
                self._is_new_high_score = True
                self._placement_text = "НОВЫЙ РЕКОРД!"
                self._placement_timer = 1500
                self._flash_timer = 500
                self._flash_color = (255, 215, 0)
            self._high_score = self._score

        # Update camera frame
        self._update_camera()

    def _update_falling_pieces(self, dt: float) -> None:
        gravity = 500.0
        for piece in self._falling_pieces:
            piece.vy += gravity * dt
            piece.y += piece.vy * dt
            piece.x += piece.vx * dt
            piece.rotation += piece.rot_speed * dt

        # Remove off-screen pieces (keep pieces until they fall well below ground)
        self._falling_pieces = [p for p in self._falling_pieces if p.y < self.GROUND_Y + 150]

    def _update_particles(self, dt: float) -> None:
        for p in self._particles:
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 150 * dt  # gravity
            p.life -= dt * 1000
            p.size = max(0.5, p.size - dt * 2)

        self._particles = [p for p in self._particles if p.life > 0]

    def _update_powerups(self, dt: float) -> None:
        for pu in self._powerups:
            pu.pulse += dt * 5
            # Float up and down gently
            pu.y += math.sin(pu.pulse) * 0.2

        # Check collection with swinging block
        for pu in list(self._powerups):
            pu_screen_y = pu.y + self._camera_y
            swing_screen_y = self.SWING_Y

            # More generous collection zone
            x_dist = abs(pu.x - self._swing_x)
            y_dist = abs(pu_screen_y - swing_screen_y)

            if x_dist < (self._current_width / 2 + 12) and y_dist < 20:
                self._collect_powerup(pu)
                self._powerups.remove(pu)
                continue

            # Remove power-ups that are too far off screen
            if pu_screen_y < -50 or pu_screen_y > 180:
                self._powerups.remove(pu)

    def _update_fever_stars(self, dt: float) -> None:
        """Update fever mode background stars."""
        for star in self._stars:
            star.y += star.speed * dt
            star.size = max(0.5, star.size - dt * 2)

        # Remove dead stars
        self._stars = [s for s in self._stars if s.y < 140 and s.size > 0.5]

    def _update_bonus_blocks(self, dt: float) -> None:
        """Update bonus blocks animation."""
        for bb in self._bonus_blocks:
            bb.pulse += dt * 6

    def _spawn_fever_star(self) -> None:
        """Spawn a fever mode background star."""
        colors = [
            (255, 100, 100), (255, 200, 100), (255, 255, 100),
            (100, 255, 100), (100, 255, 255), (100, 100, 255),
            (255, 100, 255)
        ]
        self._stars.append(StarBurst(
            x=random.uniform(0, 128),
            y=-10,
            size=random.uniform(3, 8),
            speed=random.uniform(40, 100),
            color=random.choice(colors)
        ))

    def _activate_fever_mode(self) -> None:
        """Activate fever mode for bonus scoring."""
        self._fever_mode = True
        self._fever_timer = 5000  # 5 seconds
        self._fever_multiplier = 2.0
        self._placement_text = "🔥 РЕЖИМ ОГНЯ! 🔥"
        self._placement_timer = 1000
        self._flash_timer = 500
        self._flash_color = (255, 150, 50)

        # Spawn lots of stars
        for _ in range(20):
            self._spawn_fever_star()

        # Play jackpot sound for fever mode!
        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_jackpot()

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_reward()

    def _celebrate_milestone(self, height: int) -> None:
        """Celebrate reaching a height milestone."""
        milestone_names = {
            5: "НОВИЧОК!",
            10: "ВЫСОТА 10!",
            15: "ОПЫТНЫЙ!",
            20: "МАСТЕР!",
            25: "ЭКСПЕРТ!",
            30: "ЛЕГЕНДА!"
        }

        self._placement_text = milestone_names.get(height, f"ВЫСОТА {height}!")
        self._placement_timer = 2000  # Longer celebration

        # Big flash effect
        self._flash_timer = 600
        self._flash_color = (255, 255, 100)

        # Lots of celebration particles
        self._spawn_celebration(64, 64, 40)

        # Brief slow-motion effect by reducing speed temporarily
        self._swing_speed = max(60.0, self._swing_speed * 0.85)

        # Play jackpot sound for milestones
        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_jackpot()

    def _spawn_bonus_block(self) -> None:
        """Spawn a bonus block at current position."""
        bb_type = random.choices(
            ["gold", "rainbow", "bomb"],
            weights=[0.5, 0.3, 0.2]
        )[0]

        self._bonus_blocks.append(BonusBlock(
            x=random.uniform(30, 98),
            y=self._next_block_y,
            width=20,
            type=bb_type
        ))

    def _update_difficulty(self) -> None:
        """Update difficulty based on tower height."""
        height = len(self._tower) - 1

        if height >= 30:
            self._difficulty_level = 5
            self._difficulty_name = "БЕЗУМИЕ"
        elif height >= 20:
            self._difficulty_level = 4
            self._difficulty_name = "МАСТЕР"
        elif height >= 15:
            self._difficulty_level = 3
            self._difficulty_name = "СЛОЖНО"
        elif height >= 10:
            self._difficulty_level = 2
            self._difficulty_name = "СРЕДНЕ"
        else:
            self._difficulty_level = 1
            self._difficulty_name = "ЛЕГКО"

        # Trigger bonus stage every 10 levels
        if height > 0 and height % 10 == 0 and not self._bonus_stage:
            self._start_bonus_stage()

    def _start_bonus_stage(self) -> None:
        """Start a bonus stage with increased rewards."""
        self._bonus_stage = True
        self._bonus_timer = 8000  # 8 seconds
        self._bonus_blocks_placed = 0

        self._placement_text = "БОНУС РАУНД!"
        self._placement_timer = 1500
        self._flash_timer = 500
        self._flash_color = (255, 215, 0)

        # Slow down and widen block for bonus
        self._swing_speed = max(40, self._swing_speed - 30)

        # Play bonus start sound!
        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_jackpot()
        self._current_width = min(self.INITIAL_WIDTH, self._current_width + 15)

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_reward()

    def _end_bonus_stage(self) -> None:
        """End the bonus stage."""
        self._bonus_stage = False

        # Award bonus based on blocks placed
        bonus = self._bonus_blocks_placed * 100
        self._score += bonus

        self._placement_text = f"БОНУС +{bonus}!"
        self._placement_timer = 1000

        self._spawn_celebration(64, 64, 30)

        # Play success sound for bonus completion!
        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_success()

    def _update_camera(self) -> None:
        """Update camera frame from shared camera service."""
        frame = camera_service.get_frame(timeout=0)
        if frame is not None:
            if frame.shape[:2] != (128, 128):
                try:
                    import cv2
                    frame = cv2.resize(frame, (128, 128), interpolation=cv2.INTER_LINEAR)
                except ImportError:
                    from PIL import Image
                    img = Image.fromarray(frame)
                    img = img.resize((128, 128), Image.Resampling.BILINEAR)
                    frame = np.array(img)
            self._camera_frame = frame
            self._camera = True

    def _drop_block(self) -> None:
        """Drop the swinging block."""
        if not self._tower:
            return

        top_block = self._tower[-1]

        # Calculate overlap
        swing_left = self._swing_x - self._current_width / 2
        swing_right = self._swing_x + self._current_width / 2
        top_left = top_block.x - top_block.width / 2
        top_right = top_block.x + top_block.width / 2

        overlap_left = max(swing_left, top_left)
        overlap_right = min(swing_right, top_right)
        overlap_width = overlap_right - overlap_left

        # Complete miss?
        if overlap_width <= 0:
            self._handle_miss()
            return

        # Create falling pieces for overhangs
        if swing_left < top_left:
            overhang = top_left - swing_left
            self._create_falling_piece(
                x=swing_left + overhang / 2,
                width=overhang,
                vx=-40 - random.uniform(0, 20),
                rot_speed=random.uniform(-5, -2)
            )

        if swing_right > top_right:
            overhang = swing_right - top_right
            self._create_falling_piece(
                x=top_right + overhang / 2,
                width=overhang,
                vx=40 + random.uniform(0, 20),
                rot_speed=random.uniform(2, 5)
            )

        # Evaluate placement quality
        overlap_center = (overlap_left + overlap_right) / 2
        center_diff = abs(overlap_center - top_block.x)
        width_ratio = overlap_width / top_block.width

        quality = self._evaluate_placement(width_ratio, center_diff)
        self._apply_placement_rewards(quality, overlap_width)

        # Create the stacked block
        height_idx = len(self._tower) % 10
        colors = [
            (255, 90, 90), (255, 150, 80), (255, 220, 80), (180, 255, 80),
            (80, 255, 150), (80, 220, 255), (80, 150, 255), (150, 80, 255),
            (220, 80, 255), (255, 80, 180)
        ]
        block_color = colors[height_idx]

        new_block = StackedBlock(
            x=overlap_center,
            width=overlap_width,
            y=self._next_block_y,
            color=block_color
        )
        self._tower.append(new_block)

        # Update stats
        self._best_height = max(self._best_height, len(self._tower) - 1)

        # Prepare next block
        self._current_width = overlap_width

        # Wide block power-up active?
        if self._wide_block_timer > 0:
            self._current_width = min(self.INITIAL_WIDTH, self._current_width + 10)

        self._next_block_y -= self.BLOCK_HEIGHT

        # Update camera
        blocks_on_screen = 8
        if len(self._tower) > blocks_on_screen:
            self._target_camera_y = -((len(self._tower) - blocks_on_screen) * self.BLOCK_HEIGHT)

        # Too narrow = game over (but with rescue mechanic)
        if self._current_width < self.MIN_WIDTH:
            self._handle_miss()

    def _evaluate_placement(self, width_ratio: float, center_diff: float) -> PlacementQuality:
        """Evaluate how good the block placement was."""
        if width_ratio >= 0.98 and center_diff < 1:
            return PlacementQuality.PERFECT
        elif width_ratio >= 0.90 and center_diff < 3:
            return PlacementQuality.GREAT
        elif width_ratio >= 0.75:
            return PlacementQuality.GOOD
        elif width_ratio >= 0.5:
            return PlacementQuality.OK
        else:
            return PlacementQuality.MISS

    def _apply_placement_rewards(self, quality: PlacementQuality, overlap_width: float) -> None:
        """Apply rewards based on placement quality."""
        base_score = int(overlap_width * 2)

        # Apply fever multiplier if active
        fever_mult = self._fever_multiplier if self._fever_mode else 1.0

        # Track consecutive hits for alternative fever trigger
        self._consecutive_hits += 1
        self._recent_misses = max(0, self._recent_misses - 1)  # Decay recent misses

        # Quality-based speed increase (gentler curve)
        # PERFECT: +0.5 speed, GREAT: +0.7, GOOD: +0.9, OK: +1.1
        speed_increments = {
            PlacementQuality.PERFECT: 0.5,
            PlacementQuality.GREAT: 0.7,
            PlacementQuality.GOOD: 0.9,
            PlacementQuality.OK: 1.1
        }
        speed_inc = speed_increments.get(quality, 0.8)

        # Catch-up mechanic: if struggling (recent misses), reduce speed increase
        if self._recent_misses >= 2:
            speed_inc *= 0.5
            self._swing_speed = max(60.0, self._swing_speed - 5)  # Also reduce current speed

        self._swing_speed = min(160.0, self._swing_speed + speed_inc)  # Lower cap too

        # Check for milestone celebrations
        height = len(self._tower)
        if height in [5, 10, 15, 20, 25, 30] and height > self._last_milestone:
            self._celebrate_milestone(height)
            self._last_milestone = height

        if quality == PlacementQuality.PERFECT:
            self._streak += 1
            self._perfect_streak += 1
            self._total_perfects += 1
            self._combo_multiplier = min(5.0, 1.0 + self._streak * 0.5)
            score = int(base_score * 3 * self._combo_multiplier * fever_mult)
            self._score += score

            # Different text for fever mode
            if self._fever_mode:
                self._placement_text = f"ИДЕАЛЬНО! +{score}"
            else:
                self._placement_text = f"ИДЕАЛЬНО! +{score}"
            self._placement_timer = 1500  # Longer display time

            self._flash_timer = 300
            self._flash_color = (255, 255, 150) if not self._fever_mode else (255, 150, 50)

            self._spawn_celebration(self._swing_x, self.SWING_Y + self.BLOCK_HEIGHT, 30)

            # Restore more width on perfect! (+8 instead of +5)
            self._current_width = min(self.INITIAL_WIDTH, self._current_width + 8)

            # Rescue mechanic: if dangerously narrow, give extra help
            if self._current_width < 20:
                self._current_width = min(self.INITIAL_WIDTH, self._current_width + 5)

            # Activate fever mode on 3 perfect streak (was 5)
            # OR 8 consecutive non-misses
            if (self._perfect_streak >= 3 or self._consecutive_hits >= 8) and not self._fever_mode:
                self._activate_fever_mode()

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_reward()

        elif quality == PlacementQuality.GREAT:
            self._streak += 1
            self._perfect_streak = 0  # Reset perfect streak on non-perfect
            self._combo_multiplier = min(4.0, 1.0 + self._streak * 0.3)
            score = int(base_score * 2 * self._combo_multiplier * fever_mult)
            self._score += score

            if self._fever_mode:
                self._placement_text = f"ОТЛИЧНО! +{score}"
            else:
                self._placement_text = f"ОТЛИЧНО! +{score}"
            self._placement_timer = 1200  # Longer display

            self._flash_timer = 200
            self._flash_color = (200, 255, 150)

            # Alternative fever: 8 consecutive hits
            if self._consecutive_hits >= 8 and not self._fever_mode:
                self._activate_fever_mode()

            self._spawn_celebration(self._swing_x, self.SWING_Y + self.BLOCK_HEIGHT, 15)

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_success()

        elif quality == PlacementQuality.GOOD:
            self._streak += 1
            self._perfect_streak = 0
            self._combo_multiplier = min(3.0, 1.0 + self._streak * 0.2)
            score = int(base_score * 1.5 * self._combo_multiplier * fever_mult)
            self._score += score

            self._placement_text = f"ХОРОШО +{score}"
            self._placement_timer = 1000  # Extended from 500ms

            self._spawn_celebration(self._swing_x, self.SWING_Y + self.BLOCK_HEIGHT, 8)

            # Alternative fever: 8 consecutive hits works for GOOD too
            if self._consecutive_hits >= 8 and not self._fever_mode:
                self._activate_fever_mode()

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_ui_confirm()

        elif quality == PlacementQuality.OK:
            self._streak = 0
            self._perfect_streak = 0
            self._combo_multiplier = 1.0
            self._score += int(base_score * fever_mult)

            self._placement_text = f"+{int(base_score * fever_mult)}"
            self._placement_timer = 800  # Extended from 400ms

            self._shake_timer = 100
            self._shake_intensity = 2

            if hasattr(self.context, "audio") and self.context.audio:
                self.context.audio.play_ui_move()

        self._max_streak = max(self._max_streak, self._streak)

        # Check if we should spawn a bonus block
        tower_height = len(self._tower)
        if tower_height >= self._next_bonus_height:
            self._spawn_bonus_block()
            self._next_bonus_height += 5 + random.randint(0, 3)

        # Track bonus stage progress
        if self._bonus_stage:
            self._bonus_blocks_placed += 1

    def _handle_miss(self) -> None:
        """Handle a complete miss."""
        self._lives -= 1
        self._streak = 0
        self._perfect_streak = 0
        self._combo_multiplier = 1.0

        # Track for catch-up mechanic
        self._consecutive_hits = 0
        self._recent_misses = min(3, self._recent_misses + 1)

        self._shake_timer = 500
        self._shake_intensity = 5

        self._flash_timer = 300
        self._flash_color = (255, 50, 50)

        self._placement_text = "МИМО!"
        self._placement_timer = 1000

        # Create falling block
        self._create_falling_piece(
            x=self._swing_x,
            width=self._current_width,
            vx=self._swing_dir * 30,
            rot_speed=self._swing_dir * 3
        )

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_failure()

        logger.info(f"Miss! Lives: {self._lives}")

        if self._lives <= 0:
            self._game_over = True
            self._game_over_timer = 0
            self._placement_text = "ИГРА ОКОНЧЕНА"
            self._placement_timer = 3000
        else:
            # Reset block width
            if self._tower:
                self._current_width = self._tower[-1].width

    def _create_falling_piece(self, x: float, width: float, vx: float, rot_speed: float) -> None:
        """Create a falling piece animation."""
        height_idx = len(self._tower) % 10
        colors = [
            (255, 90, 90), (255, 150, 80), (255, 220, 80), (180, 255, 80),
            (80, 255, 150), (80, 220, 255), (80, 150, 255), (150, 80, 255),
            (220, 80, 255), (255, 80, 180)
        ]

        # Start at the swinging block's screen position, converted to world coords
        # SWING_Y is screen y=15, convert to world: screen_y - camera_y = world_y
        # But we want: world_y + camera_y = screen_y, so world_y = screen_y - camera_y
        start_y = self.SWING_Y - self._camera_y

        piece = FallingPiece(
            x=x,
            y=start_y,
            width=width,
            height=self.BLOCK_HEIGHT,
            color=colors[height_idx],
            vy=50,  # Start with some downward velocity
            vx=vx,
            rotation=0,
            rot_speed=rot_speed
        )
        self._falling_pieces.append(piece)
        logger.info(f"Created falling piece at world y={start_y}, screen y={start_y + self._camera_y}")

        # Sound for falling piece
        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_ui_back()

    def _spawn_celebration(self, x: float, y: float, count: int) -> None:
        """Spawn celebration particles."""
        for _ in range(count):
            angle = random.uniform(0, 2 * math.pi)
            speed = random.uniform(40, 120)
            self._particles.append(Particle(
                x=x + random.uniform(-15, 15),
                y=y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed - 80,
                life=random.uniform(400, 800),
                max_life=800,
                color=random.choice([
                    (255, 255, 100), (255, 200, 50), (100, 255, 200),
                    (255, 100, 200), (100, 200, 255), (255, 255, 255)
                ]),
                size=random.uniform(2, 5)
            ))

    def _spawn_powerup(self) -> None:
        """Spawn a random power-up near the swinging block."""
        pu_type = random.choice(["wide", "slow", "life"])
        x = random.uniform(25, 103)
        # Spawn at fixed screen position near swing area (world coords)
        # The power-up should appear in the swing zone
        world_y = self.SWING_Y - self._camera_y + random.uniform(-10, 10)

        self._powerups.append(PowerUp(x=x, y=world_y, type=pu_type))

    def _collect_powerup(self, pu: PowerUp) -> None:
        """Collect a power-up."""
        if pu.type == "wide":
            self._wide_block_timer = 5000
            self._current_width = min(self.INITIAL_WIDTH, self._current_width + 15)
            self._placement_text = "ШИРОКИЙ БЛОК!"
        elif pu.type == "slow":
            self._slow_mo_timer = 4000
            self._placement_text = "ЗАМЕДЛЕНИЕ!"
        elif pu.type == "life":
            self._lives = min(5, self._lives + 1)
            self._placement_text = "+1 ЖИЗНЬ!"

        self._placement_timer = 800
        self._flash_timer = 200
        self._flash_color = (100, 255, 200)

        self._spawn_celebration(pu.x, pu.y + self._camera_y, 12)

        if hasattr(self.context, "audio") and self.context.audio:
            self.context.audio.play_reward()

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        t = self._time_ms

        # Fever mode background effect
        if self._fever_mode:
            # Rainbow cycling background
            hue = (t / 20) % 360
            r = int(128 + 40 * math.sin(math.radians(hue)))
            g = int(128 + 40 * math.sin(math.radians(hue + 120)))
            b = int(128 + 40 * math.sin(math.radians(hue + 240)))
            for y in range(128):
                factor = y / 128
                buffer[y, :] = [
                    int(r * 0.2 * (1 - factor)),
                    int(g * 0.2 * (1 - factor)),
                    int(b * 0.3 + 20 * factor)
                ]
        # Background
        elif self._camera_frame is not None:
            # Styled camera - dark with color tint
            styled = (self._camera_frame * 0.25).astype(np.uint8)
            # Height-based tint
            height_factor = min(1.0, len(self._tower) / 15)
            pulse = 0.5 + 0.5 * math.sin(self._bg_pulse)

            # Add purple/blue tint that shifts with height
            tint_r = int(15 + 10 * height_factor * pulse)
            tint_g = int(10 + 5 * pulse)
            tint_b = int(30 + 20 * height_factor)

            styled[:, :, 0] = np.clip(styled[:, :, 0].astype(np.int16) + tint_r, 0, 255).astype(np.uint8)
            styled[:, :, 1] = np.clip(styled[:, :, 1].astype(np.int16) + tint_g, 0, 255).astype(np.uint8)
            styled[:, :, 2] = np.clip(styled[:, :, 2].astype(np.int16) + tint_b, 0, 255).astype(np.uint8)
            buffer[:] = styled
        else:
            # Gradient background
            for y in range(128):
                factor = y / 128
                r = int(25 + 15 * factor + 5 * math.sin(self._bg_pulse))
                g = int(20 + 10 * factor)
                b = int(50 - 20 * factor)
                buffer[y, :] = [r, g, b]

        # Flash effect
        if self._flash_timer > 0:
            intensity = self._flash_timer / 300
            for c in range(3):
                buffer[:, :, c] = np.clip(
                    buffer[:, :, c].astype(np.float32) + self._flash_color[c] * intensity * 0.3,
                    0, 255
                ).astype(np.uint8)

        # Shake
        shake_x = shake_y = 0
        if self._shake_timer > 0:
            amp = int(self._shake_intensity * self._shake_timer / 500)
            shake_x = random.randint(-amp, amp)
            shake_y = random.randint(-amp, amp)

        # Draw ground
        ground_screen_y = int(self.GROUND_Y + self._camera_y) + shake_y
        if ground_screen_y < 128:
            # Ground gradient
            for y in range(max(0, ground_screen_y), 128):
                darkness = (y - ground_screen_y) / 20
                color = (int(40 - 10 * darkness), int(35 - 8 * darkness), int(55 - 12 * darkness))
                buffer[y, :] = color
            # Ground line
            if 0 <= ground_screen_y < 128:
                draw_rect(buffer, 0, ground_screen_y, 128, 2, (100, 90, 130))

        # Draw tower
        for block in self._tower:
            screen_y = int(block.y + self._camera_y) + shake_y
            screen_x = int(block.x - block.width / 2) + shake_x
            w = int(block.width)
            h = block.height

            if -h < screen_y < 128:
                # Block body with gradient
                draw_rect(buffer, screen_x, screen_y, w, h, block.color, filled=True)

                # Highlight (top)
                highlight = tuple(min(255, c + 50) for c in block.color)
                draw_rect(buffer, screen_x, screen_y, w, 2, highlight, filled=True)

                # Shadow (bottom)
                shadow = tuple(max(0, c - 50) for c in block.color)
                draw_rect(buffer, screen_x, screen_y + h - 2, w, 2, shadow, filled=True)

                # Outline
                draw_rect(buffer, screen_x, screen_y, w, h, (0, 0, 0), filled=False)

        # Draw falling pieces
        for piece in self._falling_pieces:
            screen_y = int(piece.y + self._camera_y) + shake_y
            screen_x = int(piece.x - piece.width / 2) + shake_x
            w = int(piece.width)

            if -piece.height < screen_y < 140:
                draw_rect(buffer, screen_x, screen_y, w, piece.height, piece.color, filled=True)
                draw_rect(buffer, screen_x, screen_y, w, piece.height, (0, 0, 0), filled=False)

        # Draw particles
        for p in self._particles:
            screen_y = int(p.y + self._camera_y) + shake_y
            screen_x = int(p.x) + shake_x

            if 0 < screen_x < 127 and 0 < screen_y < 127:
                alpha = p.life / p.max_life
                size = max(1, int(p.size))
                color = tuple(int(c * alpha) for c in p.color)
                draw_rect(buffer, screen_x, screen_y, size, size, color, filled=True)

        # Draw fever stars (background effect)
        for star in self._stars:
            sx = int(star.x)
            sy = int(star.y)
            if 0 < sx < 127 and 0 < sy < 127:
                size = max(1, int(star.size))
                draw_rect(buffer, sx, sy, size, size, star.color, filled=True)

        # Draw bonus blocks
        for bb in self._bonus_blocks:
            if bb.collected:
                continue
            screen_y = int(bb.y + self._camera_y) + shake_y
            screen_x = int(bb.x - bb.width / 2) + shake_x

            if -20 < screen_y < 128:
                pulse = 1.0 + 0.3 * math.sin(bb.pulse)
                w = int(bb.width * pulse)
                h = 8

                if bb.type == "gold":
                    color = (255, 220, 50)
                    glow = (255, 200, 0)
                elif bb.type == "rainbow":
                    hue = (t / 10 + bb.pulse * 30) % 360
                    color = (
                        int(128 + 127 * math.sin(math.radians(hue))),
                        int(128 + 127 * math.sin(math.radians(hue + 120))),
                        int(128 + 127 * math.sin(math.radians(hue + 240)))
                    )
                    glow = color
                else:  # bomb
                    color = (255, 80, 80)
                    glow = (255, 50, 50)

                # Glow
                draw_rect(buffer, screen_x - 2, screen_y - 2, w + 4, h + 4,
                         tuple(int(c * 0.5) for c in glow), filled=True)
                # Body
                draw_rect(buffer, screen_x, screen_y, w, h, color, filled=True)
                # Sparkle
                if int(t / 100) % 2 == 0:
                    draw_rect(buffer, screen_x + w // 2, screen_y, 2, 2, (255, 255, 255))

        # Draw power-ups with distinctive icons
        for pu in self._powerups:
            screen_y = int(pu.y + self._camera_y) + shake_y
            screen_x = int(pu.x) + shake_x

            if 0 < screen_y < 128:
                pulse = 1.0 + 0.2 * math.sin(pu.pulse * 2)
                size = int(8 * pulse)
                cx, cy = screen_x, screen_y

                if pu.type == "wide":
                    # Double arrow icon (wide block)
                    color = (100, 255, 100)
                    glow = (50, 180, 50)
                    # Background glow
                    draw_rect(buffer, cx - size - 2, cy - size // 2 - 2, size * 2 + 4, size + 4, glow, filled=True)
                    # Main body
                    draw_rect(buffer, cx - size, cy - size // 2, size * 2, size, color, filled=True)
                    # Left arrow head
                    for i in range(3):
                        draw_rect(buffer, cx - size - 2 + i, cy - 1 - i, 2, 2 + i * 2, (255, 255, 255), filled=True)
                    # Right arrow head
                    for i in range(3):
                        draw_rect(buffer, cx + size - i, cy - 1 - i, 2, 2 + i * 2, (255, 255, 255), filled=True)
                    # Center line
                    draw_rect(buffer, cx - size + 2, cy - 1, size * 2 - 4, 2, (255, 255, 255), filled=True)

                elif pu.type == "slow":
                    # Hourglass/clock icon (slow-mo)
                    color = (100, 200, 255)
                    glow = (50, 120, 180)
                    # Background glow
                    draw_rect(buffer, cx - size // 2 - 2, cy - size - 2, size + 4, size * 2 + 4, glow, filled=True)
                    # Top triangle
                    for i in range(size):
                        w = size - i
                        draw_rect(buffer, cx - w // 2, cy - size + i, w, 1, color, filled=True)
                    # Bottom triangle (inverted)
                    for i in range(size):
                        w = i + 1
                        draw_rect(buffer, cx - w // 2, cy + i, w, 1, color, filled=True)
                    # Center pinch
                    draw_rect(buffer, cx - 1, cy - 1, 2, 2, (255, 255, 255), filled=True)
                    # Border
                    draw_rect(buffer, cx - size // 2, cy - size, size, 1, (255, 255, 255), filled=True)
                    draw_rect(buffer, cx - size // 2, cy + size - 1, size, 1, (255, 255, 255), filled=True)

                else:  # life - heart icon
                    color = (255, 100, 150)
                    glow = (180, 50, 80)
                    # Background glow
                    draw_rect(buffer, cx - size // 2 - 2, cy - size // 2 - 2, size + 4, size + 4, glow, filled=True)
                    # Heart shape (pixel art)
                    # Top bumps
                    draw_rect(buffer, cx - size // 2 + 1, cy - size // 2, size // 2 - 1, size // 3, color, filled=True)
                    draw_rect(buffer, cx + 1, cy - size // 2, size // 2 - 1, size // 3, color, filled=True)
                    # Middle body
                    draw_rect(buffer, cx - size // 2, cy - size // 3, size, size // 2, color, filled=True)
                    # Bottom point
                    for i in range(size // 2):
                        w = size - i * 2
                        if w > 0:
                            draw_rect(buffer, cx - w // 2, cy + size // 6 + i, w, 1, color, filled=True)
                    # Plus sign overlay
                    draw_rect(buffer, cx - 1, cy - size // 3, 2, size // 2 + 2, (255, 255, 255), filled=True)
                    draw_rect(buffer, cx - size // 3, cy - 1, size // 2 + 2, 2, (255, 255, 255), filled=True)

                # Sparkle effect
                sparkle_phase = (t / 100 + pu.pulse) % (2 * math.pi)
                if sparkle_phase < 0.5:
                    sx = cx + int(6 * math.cos(pu.pulse * 3))
                    sy = cy + int(6 * math.sin(pu.pulse * 3))
                    draw_rect(buffer, sx, sy, 2, 2, (255, 255, 255), filled=True)

        # Draw swinging block
        if not self._game_over:
            swing_y = self.SWING_Y + shake_y
            swing_x = int(self._swing_x - self._current_width / 2) + shake_x
            w = int(self._current_width)

            # Pulsing glow
            pulse = 0.7 + 0.3 * math.sin(t / 80)
            glow_color = (int(255 * pulse), int(230 * pulse), int(100 * pulse))

            # Glow effect
            glow_size = 2
            draw_rect(buffer, swing_x - glow_size, swing_y - glow_size,
                     w + glow_size * 2, self.BLOCK_HEIGHT + glow_size * 2,
                     (80, 70, 50), filled=True)

            # Block
            draw_rect(buffer, swing_x, swing_y, w, self.BLOCK_HEIGHT, glow_color, filled=True)
            draw_rect(buffer, swing_x, swing_y, w, self.BLOCK_HEIGHT, (0, 0, 0), filled=False)

            # Guide lines to show target area
            if self._tower:
                top = self._tower[-1]
                top_screen_y = int(top.y + self._camera_y) + shake_y
                guide_left = int(top.x - top.width / 2) + shake_x
                guide_right = int(top.x + top.width / 2) + shake_x

                # Dashed vertical lines
                for y in range(swing_y + self.BLOCK_HEIGHT + 2, top_screen_y, 3):
                    if 0 < y < 128:
                        if 0 < guide_left < 128:
                            buffer[y, guide_left] = [80, 80, 100]
                        if 0 < guide_right < 128:
                            buffer[y, guide_right] = [80, 80, 100]

        # HUD
        # Score (top left)
        score_color = (255, 215, 0) if self._is_new_high_score else (255, 255, 255)
        draw_centered_text(buffer, f"СЧЁТ {self._score:05d}", 2, score_color, scale=1)

        # High score (if exists)
        if self._high_score > 0:
            draw_rect(buffer, 2, 11, 40, 7, (30, 30, 50))
            hs_text = f"HS:{self._high_score}"
            # Draw manually at left
            from artifact.graphics.text_utils import draw_text
            draw_text(buffer, hs_text, 3, 12, (150, 150, 200), scale=1)

        # Lives (top right area) - draw as hearts
        lives_x = 100
        for i in range(self._lives):
            draw_rect(buffer, lives_x + i * 9, 2, 7, 7, (255, 80, 100), filled=True)

        # Height and difficulty
        height = len(self._tower) - 1
        diff_colors = {
            1: (100, 255, 100),  # Easy - green
            2: (255, 255, 100),  # Medium - yellow
            3: (255, 180, 100),  # Hard - orange
            4: (255, 100, 100),  # Master - red
            5: (255, 100, 255),  # Insane - purple
        }
        diff_color = diff_colors.get(self._difficulty_level, (255, 255, 255))
        draw_centered_text(buffer, f"ВЫС {height} · {self._difficulty_name}", 12, diff_color, scale=1)

        # Bonus stage indicator
        if self._bonus_stage:
            bonus_pct = self._bonus_timer / 8000
            bar_width = int(50 * bonus_pct)
            draw_rect(buffer, 39, 22, bar_width, 4, (255, 215, 0))
            draw_centered_text(buffer, "БОНУС!", 18, (255, 215, 0), scale=1)

        # Streak/combo indicator
        if self._streak >= 2:
            combo_color = (255, 255, 100) if int(t / 150) % 2 == 0 else (255, 200, 50)
            draw_centered_text(buffer, f"x{self._streak} КОМБО", 22, combo_color, scale=1)

        # Fever mode indicator
        if self._fever_mode:
            fever_pct = self._fever_timer / 5000
            bar_width = int(60 * fever_pct)
            # Rainbow bar
            hue = (t / 5) % 360
            fever_color = (
                int(128 + 127 * math.sin(math.radians(hue))),
                int(128 + 127 * math.sin(math.radians(hue + 120))),
                int(128 + 127 * math.sin(math.radians(hue + 240)))
            )
            draw_rect(buffer, 34, 32, bar_width, 4, fever_color)
            draw_centered_text(buffer, "ОГОНЬ!", 28, fever_color, scale=1)

        # Placement feedback text
        if self._placement_timer > 0:
            alpha = min(1.0, self._placement_timer / 200)
            y_offset = int(5 * (1 - self._placement_timer / 800))
            color = (int(255 * alpha), int(255 * alpha), int(100 * alpha))
            draw_centered_text(buffer, self._placement_text, 40 - y_offset, color, scale=1)

        # Power-up indicators
        indicator_y = 118
        if self._slow_mo_timer > 0:
            pct = self._slow_mo_timer / 4000
            draw_rect(buffer, 4, indicator_y, int(30 * pct), 4, (100, 200, 255))

        if self._wide_block_timer > 0:
            pct = self._wide_block_timer / 5000
            draw_rect(buffer, 94, indicator_y, int(30 * pct), 4, (100, 255, 100))

        # Game over overlay
        if self._game_over:
            # Darken
            buffer[:] = (buffer * 0.4).astype(np.uint8)

            # Game over text with animation
            bob = int(3 * math.sin(t / 200))
            draw_centered_text(buffer, "ИГРА", 45 + bob, (255, 80, 80), scale=2)
            draw_centered_text(buffer, "ОКОНЧЕНА", 65 + bob, (255, 80, 80), scale=2)

            draw_centered_text(buffer, f"ВЫСОТА: {self._best_height}", 88, (255, 255, 255), scale=1)
            draw_centered_text(buffer, f"СЧЁТ: {self._score}", 100, (255, 255, 255), scale=1)

            if self._max_streak >= 3:
                draw_centered_text(buffer, f"МАКС КОМБО: {self._max_streak}x", 112, (255, 200, 100), scale=1)
        else:
            # Tutorial hint for new players
            if self._tutorial_timer > 0 and len(self._tower) <= 2:
                alpha = min(1.0, self._tutorial_timer / 500)
                hint_color = (int(200 * alpha), int(255 * alpha), int(200 * alpha))
                draw_centered_text(buffer, "ЛОВИ МОМЕНТ!", 55, hint_color, scale=1)
                draw_centered_text(buffer, "ЖМАКАЙ КНОПКУ", 65, hint_color, scale=1)
            else:
                # Regular hint
                draw_animated_text(buffer, "ЖМАКАЙ", 108, (150, 150, 150), t, TextEffect.PULSE, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker as extension of main display - shows area above the main screen."""
        from artifact.graphics.primitives import clear, draw_rect

        clear(buffer)

        # Ticker is 48x8 pixels - show as extension above main display
        # The ticker represents the sky/upper area above the main game view
        # Map main display x (0-127) to ticker x (0-47) by scaling: ticker_x = main_x * 48 / 128

        t = self._time_ms

        # Background gradient (sky)
        if self._fever_mode:
            # Rainbow cycling for fever mode
            hue = (t / 20) % 360
            for y in range(8):
                r = int(80 + 40 * math.sin(math.radians(hue + y * 20)))
                g = int(80 + 40 * math.sin(math.radians(hue + 120 + y * 20)))
                b = int(80 + 40 * math.sin(math.radians(hue + 240 + y * 20)))
                buffer[y, :] = [r, g, b]
        else:
            # Normal sky gradient (darker at top)
            for y in range(8):
                factor = y / 8
                pulse = 0.5 + 0.5 * math.sin(self._bg_pulse)
                r = int(15 + 10 * factor + 5 * pulse)
                g = int(10 + 15 * factor)
                b = int(40 + 20 * factor)
                buffer[y, :] = [r, g, b]

        # Draw fever stars that extend into ticker area
        for star in self._stars:
            if star.y < 0:  # Star is above main display
                # Map to ticker coordinates
                ticker_x = int(star.x * 48 / 128)
                ticker_y = int((star.y + 8) * 8 / 8)  # y=-8 maps to ticker y=0
                if 0 <= ticker_x < 47 and 0 <= ticker_y < 8:
                    size = max(1, int(star.size * 48 / 128))
                    color = star.color
                    draw_rect(buffer, ticker_x, ticker_y, size, size, color, filled=True)

        # Draw particles that extend into ticker area
        for p in self._particles:
            screen_y = p.y + self._camera_y
            if screen_y < 0:  # Particle above main display
                ticker_x = int(p.x * 48 / 128)
                ticker_y = int((screen_y + 8))  # Map -8..0 to 0..8
                if 0 <= ticker_x < 47 and 0 <= ticker_y < 8:
                    alpha = p.life / p.max_life
                    size = max(1, int(p.size * 48 / 128))
                    color = tuple(int(c * alpha) for c in p.color)
                    draw_rect(buffer, ticker_x, ticker_y, size, size, color, filled=True)

        # Show score on ticker if not in fever mode (small indicator)
        if not self._fever_mode:
            # Draw small score indicator on right side
            score_text = f"{self._score:04d}"
            # Simple 3x5 digit rendering (very small for ticker)
            digit_x = 30
            digit_color = (150, 255, 200) if not self._game_over else (255, 100, 100)
            for ch in score_text[-4:]:
                self._draw_tiny_digit(buffer, ch, digit_x, 2, digit_color)
                digit_x += 4

        # Streak indicator on left
        if self._streak >= 2:
            streak_color = (255, 220, 100) if int(t / 150) % 2 == 0 else (255, 180, 50)
            # Draw small 'x' and number
            self._draw_tiny_digit(buffer, 'x', 2, 2, streak_color)
            self._draw_tiny_digit(buffer, str(min(9, self._streak)), 6, 2, streak_color)

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
            return f"KONEC VYS{self._best_height:02d}"[:16]
        return f"BASH VYS{len(self._tower) - 1:02d}"[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._best_height >= 5,
            data={
                "score": self._score,
                "height": self._best_height,
                "max_streak": self._max_streak,
            },
            display_text=f"ВЫС {self._best_height} СЧЁТ {self._score}",
            ticker_text="ЕЩЁ РАЗ?",
            lcd_text=f"VYS{self._best_height:02d} OK",
            should_print=False,
        )
        self.complete(result)

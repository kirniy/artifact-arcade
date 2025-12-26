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
from artifact.graphics.text_utils import draw_text, measure_text
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
    display_name = "TOWER"
    icon = "tower"
    style = "arcade"
    description = "Stack the tower as high as you can"
    requires_camera = True

    # Constants
    BLOCK_HEIGHT = 10
    GROUND_Y = 115
    INITIAL_WIDTH = 50
    MIN_WIDTH = 6
    SWING_Y = 15  # Y position of swinging block
    CAMERA_TARGET_Y = 70  # Keep next block landing around this screen Y
    DROP_GRAVITY = 1600.0
    DROP_MAX_SPEED = 900.0
    DROP_SNAP = 2

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

        # Drop animation state (screen coordinates)
        self._dropping = False
        self._drop_x = 0.0
        self._drop_width = 0.0
        self._drop_y = 0.0
        self._drop_target_y = 0.0
        self._drop_vy = 0.0
        self._lock_flash_timer = 0.0
        self._lock_flash_block: Optional[StackedBlock] = None

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
        self._dropping = False
        self._drop_x = self._swing_x
        self._drop_width = self._current_width
        self._drop_y = self.SWING_Y
        self._drop_target_y = self.SWING_Y
        self._drop_vy = 0.0
        self._lock_flash_timer = 0.0
        self._lock_flash_block = None

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
            if self._dropping:
                return True
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

        dt = delta_ms / 1000.0
        self._time_ms += delta_ms

        if self._game_over:
            self._game_over_timer += delta_ms
            if self._game_over_timer > 2500:
                self._complete()
            self._update_falling_pieces(dt)
            return

        if self._dropping:
            self._update_drop(dt)
        else:
            actual_speed = self._swing_speed
            self._swing_x += self._swing_dir * actual_speed * dt

            half_w = self._current_width / 2
            if self._swing_x - half_w <= 5:
                self._swing_x = 5 + half_w
                self._swing_dir = 1
            elif self._swing_x + half_w >= 123:
                self._swing_x = 123 - half_w
                self._swing_dir = -1

        self._update_falling_pieces(dt)

        if not self._dropping:
            camera_diff = self._target_camera_y - self._camera_y
            self._camera_y += camera_diff * 4.0 * dt

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

    def _update_drop(self, dt: float) -> None:
        """Animate the dropping block with a crisp, Tetris-like fall."""
        target_y = self._drop_target_y

        self._drop_vy = min(self._drop_vy + self.DROP_GRAVITY * dt, self.DROP_MAX_SPEED)
        self._drop_y += self._drop_vy * dt

        if self.DROP_SNAP > 1:
            self._drop_y = round(self._drop_y / self.DROP_SNAP) * self.DROP_SNAP

        if self._drop_y >= target_y:
            self._drop_y = target_y
            self._dropping = False
            self._resolve_drop()

    def _drop_block(self) -> None:
        """Start the drop animation for the swinging block."""
        if not self._tower or self._dropping:
            return

        self._dropping = True
        self._drop_x = self._swing_x
        self._drop_width = self._current_width
        self._drop_y = self.SWING_Y
        self._drop_vy = 0.0
        self._drop_target_y = self._next_block_y + self._camera_y

    def _resolve_drop(self) -> None:
        """Finalize block placement after the drop animation."""
        if not self._tower:
            return

        top_block = self._tower[-1]
        drop_x = self._drop_x
        drop_width = self._drop_width

        # Calculate overlap
        swing_left = drop_x - drop_width / 2
        swing_right = drop_x + drop_width / 2
        top_left = top_block.x - top_block.width / 2
        top_right = top_block.x + top_block.width / 2

        overlap_left = max(swing_left, top_left)
        overlap_right = min(swing_right, top_right)
        overlap_width = overlap_right - overlap_left

        # Complete miss?
        if overlap_width <= 0:
            self._handle_miss()
            return

        # Evaluate placement quality
        overlap_center = (overlap_left + overlap_right) / 2
        center_diff = abs(overlap_center - top_block.x)
        width_ratio = overlap_width / top_block.width

        quality = self._evaluate_placement(width_ratio, center_diff)

        # Perfect snap: align to the block below for that classic stacker feel
        if quality == PlacementQuality.PERFECT:
            overlap_left = top_left
            overlap_right = top_right
            overlap_width = top_block.width
            overlap_center = top_block.x
        else:
            # Create falling pieces for overhangs
            if swing_left < top_left:
                overhang = top_left - swing_left
                self._create_falling_piece(
                    x=swing_left + overhang / 2,
                    width=overhang,
                    vx=-40 - random.uniform(0, 20),
                    rot_speed=random.uniform(-5, -2),
                    start_world_y=self._next_block_y
                )

            if swing_right > top_right:
                overhang = swing_right - top_right
                self._create_falling_piece(
                    x=top_right + overhang / 2,
                    width=overhang,
                    vx=40 + random.uniform(0, 20),
                    rot_speed=random.uniform(2, 5),
                    start_world_y=self._next_block_y
                )

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
        self._lock_flash_block = new_block
        self._lock_flash_timer = 160

        # Update stats
        self._best_height = max(self._best_height, len(self._tower) - 1)

        # Prepare next block
        self._current_width = overlap_width

        self._next_block_y -= self.BLOCK_HEIGHT

        # Update camera
        blocks_on_screen = 8
        if len(self._tower) > blocks_on_screen:
            self._target_camera_y = max(0.0, self.CAMERA_TARGET_Y - self._next_block_y)
        else:
            self._target_camera_y = 0.0

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
        """Apply simplified rewards based on placement quality."""
        base_score = max(1, int(overlap_width))

        if quality == PlacementQuality.PERFECT:
            multiplier = 3.0
            self._streak += 1
            self._current_width = min(self.INITIAL_WIDTH, self._current_width + 6)
        elif quality == PlacementQuality.GREAT:
            multiplier = 2.0
            self._streak += 1
        elif quality == PlacementQuality.GOOD:
            multiplier = 1.5
            self._streak += 1
        else:
            multiplier = 1.0
            self._streak = 0

        self._score += int(base_score * multiplier)
        self._max_streak = max(self._max_streak, self._streak)

        speed_increments = {
            PlacementQuality.PERFECT: 1.0,
            PlacementQuality.GREAT: 0.8,
            PlacementQuality.GOOD: 0.6,
            PlacementQuality.OK: 0.4,
            PlacementQuality.MISS: 0.0,
        }
        self._swing_speed = min(140.0, self._swing_speed + speed_increments.get(quality, 0.4))

    def _handle_miss(self) -> None:
        """Handle a complete miss."""
        self._lives -= 1
        self._streak = 0
        self._perfect_streak = 0
        self._combo_multiplier = 1.0

        self._consecutive_hits = 0
        self._recent_misses = min(3, self._recent_misses + 1)

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
        else:
            # Reset block width
            if self._tower:
                self._current_width = self._tower[-1].width

    def _create_falling_piece(
        self,
        x: float,
        width: float,
        vx: float,
        rot_speed: float,
        start_world_y: Optional[float] = None
    ) -> None:
        """Create a falling piece animation."""
        height_idx = len(self._tower) % 10
        colors = [
            (255, 90, 90), (255, 150, 80), (255, 220, 80), (180, 255, 80),
            (80, 255, 150), (80, 220, 255), (80, 150, 255), (150, 80, 255),
            (220, 80, 255), (255, 80, 180)
        ]

        # Start at either the swing height or the placed block height (world coords)
        if start_world_y is None:
            # SWING_Y is screen y=15, convert to world: world_y = screen_y - camera_y
            start_y = self.SWING_Y - self._camera_y
        else:
            start_y = start_world_y

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

    def _draw_block(self, buffer: NDArray[np.uint8], x: int, y: int, w: int,
                    h: int, color: tuple, outline: bool = True) -> None:
        """Draw a block with Tetris-style highlights."""
        draw_rect(buffer, x, y, w, h, color, filled=True)

        highlight = tuple(min(255, c + 60) for c in color)
        shadow = tuple(max(0, c - 50) for c in color)
        # Top and left highlights
        draw_rect(buffer, x, y, w, 1, highlight, filled=True)
        draw_rect(buffer, x, y, 1, h, highlight, filled=True)
        # Bottom and right shadows
        draw_rect(buffer, x, y + h - 1, w, 1, shadow, filled=True)
        draw_rect(buffer, x + w - 1, y, 1, h, shadow, filled=True)

        if outline:
            draw_rect(buffer, x, y, w, h, (0, 0, 0), filled=False)

    def _render_camera_background(self, buffer: NDArray[np.uint8]) -> None:
        if self._camera_frame is not None:
            dimmed = (self._camera_frame.astype(np.float32) * 0.35).astype(np.uint8)
            np.copyto(buffer, dimmed)
        else:
            fill(buffer, (8, 8, 12))

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        self._render_camera_background(buffer)
        shake_x = 0
        shake_y = 0

        # Draw ground
        ground_screen_y = int(self.GROUND_Y + self._camera_y) + shake_y
        if 0 <= ground_screen_y < 128:
            draw_rect(buffer, 0, ground_screen_y, 128, 1, (50, 50, 60))

        # Draw tower
        for block in self._tower:
            screen_y = int(block.y + self._camera_y) + shake_y
            screen_x = int(block.x - block.width / 2) + shake_x
            w = int(block.width)
            h = block.height

            if -h < screen_y < 128:
                self._draw_block(buffer, screen_x, screen_y, w, h, block.color, outline=True)

        # Draw falling pieces
        for piece in self._falling_pieces:
            screen_y = int(piece.y + self._camera_y) + shake_y
            screen_x = int(piece.x - piece.width / 2) + shake_x
            w = int(piece.width)

            if -piece.height < screen_y < 140:
                self._draw_block(buffer, screen_x, screen_y, w, piece.height, piece.color, outline=True)

        # Draw swinging or dropping block
        if not self._game_over:
            if self._dropping:
                drop_y = int(self._drop_y) + shake_y
                drop_x = int(self._drop_x - self._drop_width / 2) + shake_x
                drop_w = int(self._drop_width)
                self._draw_block(buffer, drop_x, drop_y, drop_w, self.BLOCK_HEIGHT, (230, 210, 120), outline=True)
            else:
                swing_y = self.SWING_Y + shake_y
                swing_x = int(self._swing_x - self._current_width / 2) + shake_x
                w = int(self._current_width)
                self._draw_block(buffer, swing_x, swing_y, w, self.BLOCK_HEIGHT, (230, 210, 120), outline=True)

        score_text = f"SCORE {self._score}"
        lives_text = f"LIVES {self._lives}"
        lives_w, _ = measure_text(lives_text, scale=1)

        draw_rect(buffer, 0, 0, 64, 9, (0, 0, 0))
        draw_text(buffer, score_text, 2, 1, (240, 240, 240), scale=1)

        lives_x = max(0, 128 - lives_w - 4)
        draw_rect(buffer, lives_x, 0, lives_w + 4, 9, (0, 0, 0))
        draw_text(buffer, lives_text, lives_x + 2, 1, (240, 200, 200), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, (0, 0, 0))
        text = f"S{self._score % 1000:03d} L{self._lives}"
        text_w, _ = measure_text(text, scale=1)
        x = max(0, (48 - text_w) // 2)
        draw_text(buffer, text, x, 0, (200, 200, 200), scale=1)

    def get_lcd_text(self) -> str:
        text = f"TOWER S{self._score:03d} L{self._lives}"
        return text.center(16)[:16]

    def _complete(self) -> None:
        result = ModeResult(
            mode_name=self.name,
            success=self._best_height >= 5,
            data={
                "score": self._score,
                "height": self._best_height,
                "max_streak": self._max_streak,
            },
            display_text=f"SCORE {self._score}",
            ticker_text="TOWER",
            lcd_text=f"SCORE {self._score}",
            should_print=False,
        )
        self.complete(result)

"""Golden Snitch Catcher Mini-Game - Harry Potter themed game.

A fun mini-game to play while waiting for AI processing.
Features a Seeker catching Golden Snitches while avoiding Bludgers!
The Sorting Hat watches and ponders in the corner.
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


# =============================================================================
# Color Palette - Harry Potter Theme
# =============================================================================

# Golden Snitch colors
GOLD_BRIGHT = (255, 215, 0)
GOLD_DARK = (218, 165, 32)
GOLD_SHINE = (255, 255, 150)
WING_WHITE = (255, 255, 255)
WING_SILVER = (200, 200, 220)

# Bludger colors
BLUDGER_DARK = (40, 40, 50)
BLUDGER_MID = (60, 60, 70)
BLUDGER_LIGHT = (80, 80, 90)

# Seeker/Player colors
ROBE_DARK = (100, 50, 30)
ROBE_MID = (140, 80, 50)
SKIN = (255, 200, 160)
HAIR_DARK = (40, 30, 20)
BROOM_BROWN = (120, 80, 40)
BROOM_STRAW = (200, 160, 100)

# Sorting Hat colors
HAT_BROWN = (80, 50, 30)
HAT_DARK = (50, 30, 20)
HAT_BAND = (40, 25, 15)

# Sky/Background
SKY_DARK = (20, 25, 50)
SKY_MID = (40, 50, 90)
CLOUD_GRAY = (70, 80, 100)

# Stars
STAR_BRIGHT = (255, 255, 200)
STAR_DIM = (150, 150, 180)

TRANS = None  # Transparent


# =============================================================================
# Pixel Art Sprites
# =============================================================================

# Golden Snitch Animation Frames (10x6)
SNITCH_FRAMES = [
    # Frame 1: Mid
    [
        [TRANS, TRANS, WING_SILVER, WING_WHITE, TRANS, TRANS, TRANS, TRANS, WING_WHITE, WING_SILVER],
        [TRANS, WING_WHITE, WING_WHITE, GOLD_SHINE, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_SHINE, WING_WHITE, WING_WHITE],
        [WING_SILVER, WING_WHITE, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, WING_WHITE, WING_SILVER],
        [TRANS, WING_WHITE, WING_WHITE, GOLD_DARK, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_DARK, WING_WHITE, WING_WHITE, TRANS],
        [TRANS, TRANS, WING_SILVER, WING_WHITE, GOLD_DARK, GOLD_DARK, WING_WHITE, WING_SILVER, TRANS, TRANS],
        [TRANS, TRANS, TRANS, WING_SILVER, TRANS, TRANS, WING_SILVER, TRANS, TRANS, TRANS],
    ],
    # Frame 2: Up
    [
        [WING_SILVER, WING_WHITE, WING_WHITE, TRANS, TRANS, TRANS, TRANS, WING_WHITE, WING_WHITE, WING_SILVER],
        [TRANS, WING_WHITE, GOLD_SHINE, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_SHINE, WING_WHITE, TRANS],
        [TRANS, TRANS, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, TRANS, TRANS],
        [TRANS, TRANS, GOLD_DARK, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_DARK, TRANS, TRANS],
        [TRANS, TRANS, TRANS, GOLD_DARK, GOLD_DARK, GOLD_DARK, GOLD_DARK, TRANS, TRANS, TRANS],
        [TRANS, TRANS, TRANS, TRANS, GOLD_DARK, GOLD_DARK, TRANS, TRANS, TRANS, TRANS],
    ],
    # Frame 3: Mid (Same as 1)
    [
        [TRANS, TRANS, WING_SILVER, WING_WHITE, TRANS, TRANS, TRANS, TRANS, WING_WHITE, WING_SILVER],
        [TRANS, WING_WHITE, WING_WHITE, GOLD_SHINE, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_SHINE, WING_WHITE, WING_WHITE],
        [WING_SILVER, WING_WHITE, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, WING_WHITE, WING_SILVER],
        [TRANS, WING_WHITE, WING_WHITE, GOLD_DARK, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_DARK, WING_WHITE, WING_WHITE, TRANS],
        [TRANS, TRANS, WING_SILVER, WING_WHITE, GOLD_DARK, GOLD_DARK, WING_WHITE, WING_SILVER, TRANS, TRANS],
        [TRANS, TRANS, TRANS, WING_SILVER, TRANS, TRANS, WING_SILVER, TRANS, TRANS, TRANS],
    ],
    # Frame 4: Down
    [
        [TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
        [TRANS, TRANS, TRANS, GOLD_SHINE, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_SHINE, TRANS, TRANS],
        [TRANS, TRANS, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, TRANS, TRANS],
        [TRANS, WING_WHITE, GOLD_DARK, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_DARK, WING_WHITE, TRANS],
        [WING_WHITE, WING_WHITE, WING_SILVER, GOLD_DARK, GOLD_DARK, GOLD_DARK, GOLD_DARK, WING_SILVER, WING_WHITE, WING_WHITE],
        [WING_SILVER, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, WING_SILVER],
    ],
]

# Bludger (8x8) - menace
BLUDGER = [
    [TRANS, TRANS, BLUDGER_DARK, BLUDGER_DARK, BLUDGER_DARK, BLUDGER_DARK, TRANS, TRANS],
    [TRANS, BLUDGER_DARK, BLUDGER_MID, BLUDGER_MID, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK, TRANS],
    [BLUDGER_DARK, BLUDGER_MID, BLUDGER_LIGHT, BLUDGER_LIGHT, BLUDGER_MID, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK],
    [BLUDGER_DARK, BLUDGER_MID, BLUDGER_LIGHT, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK, BLUDGER_MID, BLUDGER_DARK],
    [BLUDGER_DARK, BLUDGER_MID, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK],
    [BLUDGER_DARK, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK, BLUDGER_MID, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK],
    [TRANS, BLUDGER_DARK, BLUDGER_MID, BLUDGER_MID, BLUDGER_MID, BLUDGER_MID, BLUDGER_DARK, TRANS],
    [TRANS, TRANS, BLUDGER_DARK, BLUDGER_DARK, BLUDGER_DARK, BLUDGER_DARK, TRANS, TRANS],
]

# Seeker Frames (12x10) - player sprite with robe animation
SEEKER_FRAMES = [
    # Frame 1: Normal
    [
        [TRANS, TRANS, TRANS, TRANS, HAIR_DARK, HAIR_DARK, HAIR_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
        [TRANS, TRANS, TRANS, HAIR_DARK, HAIR_DARK, HAIR_DARK, HAIR_DARK, HAIR_DARK, TRANS, TRANS, TRANS, TRANS],
        [TRANS, TRANS, TRANS, SKIN, SKIN, SKIN, SKIN, TRANS, TRANS, TRANS, TRANS, TRANS],
        [TRANS, TRANS, ROBE_MID, SKIN, SKIN, SKIN, ROBE_MID, TRANS, TRANS, TRANS, TRANS, TRANS],
        [TRANS, ROBE_MID, ROBE_MID, ROBE_DARK, ROBE_MID, ROBE_MID, ROBE_MID, ROBE_MID, TRANS, TRANS, TRANS, TRANS],
        [TRANS, ROBE_MID, ROBE_DARK, ROBE_DARK, ROBE_DARK, ROBE_DARK, ROBE_MID, TRANS, TRANS, TRANS, TRANS, TRANS],
        [BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_STRAW, BROOM_STRAW, BROOM_STRAW],
        [TRANS, TRANS, TRANS, TRANS, ROBE_DARK, ROBE_DARK, TRANS, TRANS, TRANS, BROOM_STRAW, BROOM_STRAW, TRANS],
        [TRANS, TRANS, TRANS, TRANS, ROBE_DARK, TRANS, ROBE_DARK, TRANS, TRANS, TRANS, BROOM_STRAW, TRANS],
        [TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    ],
    # Frame 2: Robe Flapping Back
    [
        [TRANS, TRANS, TRANS, TRANS, HAIR_DARK, HAIR_DARK, HAIR_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
        [TRANS, TRANS, TRANS, HAIR_DARK, HAIR_DARK, HAIR_DARK, HAIR_DARK, HAIR_DARK, TRANS, TRANS, TRANS, TRANS],
        [TRANS, TRANS, TRANS, SKIN, SKIN, SKIN, SKIN, TRANS, TRANS, TRANS, TRANS, TRANS],
        [TRANS, TRANS, ROBE_MID, SKIN, SKIN, SKIN, ROBE_MID, TRANS, TRANS, TRANS, TRANS, TRANS],
        [TRANS, ROBE_MID, ROBE_MID, ROBE_DARK, ROBE_MID, ROBE_MID, ROBE_MID, ROBE_MID, TRANS, TRANS, TRANS, TRANS],
        [TRANS, ROBE_MID, ROBE_DARK, ROBE_DARK, ROBE_DARK, ROBE_DARK, ROBE_MID, TRANS, TRANS, TRANS, TRANS, TRANS],
        [BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_BROWN, BROOM_STRAW, BROOM_STRAW, BROOM_STRAW],
        [TRANS, TRANS, TRANS, ROBE_DARK, ROBE_DARK, ROBE_DARK, ROBE_DARK, TRANS, TRANS, BROOM_STRAW, BROOM_STRAW, TRANS],
        [TRANS, TRANS, ROBE_DARK, ROBE_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, BROOM_STRAW, TRANS],
        [TRANS, ROBE_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    ],
]

# Sorting Hat (16x18) - watching in corner
SORTING_HAT = [
    [TRANS, TRANS, TRANS, TRANS, TRANS, HAT_DARK, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, HAT_DARK, HAT_BROWN, HAT_DARK, HAT_DARK, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_DARK, HAT_BAND, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_DARK, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS],
    [TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, HAT_DARK, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, HAT_DARK, HAT_DARK, HAT_DARK, HAT_DARK, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
]

# Sorting Hat thinking animation (eyes closed)
SORTING_HAT_THINK = [
    [TRANS, TRANS, TRANS, TRANS, TRANS, HAT_DARK, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BAND, HAT_BROWN, HAT_BROWN, HAT_BAND, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, HAT_DARK, HAT_BROWN, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_DARK, HAT_BAND, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_BAND, HAT_DARK, TRANS, TRANS, TRANS],
    [HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS],
    [TRANS, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, HAT_DARK, HAT_DARK, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_BROWN, HAT_DARK, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, HAT_DARK, HAT_DARK, HAT_DARK, HAT_DARK, HAT_DARK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
]


# =============================================================================
# Game Objects
# =============================================================================

class EntityType(Enum):
    """Types of entities in the game."""
    SNITCH = auto()
    BLUDGER = auto()


@dataclass
class FlyingEntity:
    """A flying entity in the game (snitch or bludger)."""
    x: float
    y: float
    vx: float  # Horizontal velocity
    vy: float  # Vertical velocity
    entity_type: EntityType
    collected: bool = False
    frame: int = 0  # Animation frame
    # Trail history (last 5 positions) for snitches
    trail: List[Tuple[float, float]] = field(default_factory=list)

    @property
    def width(self) -> int:
        return 10 if self.entity_type == EntityType.SNITCH else 8

    @property
    def height(self) -> int:
        return 6 if self.entity_type == EntityType.SNITCH else 8


@dataclass
class Star:
    """A background star."""
    x: float
    y: float
    brightness: float
    twinkle_speed: float
    depth: float = 1.0  # For parallax (0.5 = far, 1.0 = near)


@dataclass
class Cloud:
    """A background cloud."""
    x: float
    y: float
    width: int
    speed: float = 10.0


@dataclass
class Sparkle:
    """A sparkle effect when catching snitch."""
    x: float
    y: float
    life: float
    vx: float
    vy: float
    color: Tuple[int, int, int]
    size: int = 1


@dataclass
class GameState:
    """State of the Snitch Catcher game."""
    # Player position
    player_x: float = 64.0  # Center of 128px screen
    player_y: float = 90.0  # Near bottom
    target_x: float = 64.0  # Target position for smooth movement
    player_frame: int = 0   # Seeker animation frame

    # Score
    snitches_caught: int = 0
    bludger_hits: int = 0

    # Game entities
    entities: List[FlyingEntity] = field(default_factory=list)
    stars: List[Star] = field(default_factory=list)
    clouds: List[Cloud] = field(default_factory=list)
    sparkles: List[Sparkle] = field(default_factory=list)

    # Timing
    spawn_timer: float = 0.0
    time_played: float = 0.0
    hat_think_timer: float = 0.0  # For hat animation

    # Animation
    entity_anim_timer: float = 0.0
    player_anim_timer: float = 0.0


class SnitchCatcher:
    """Golden Snitch Catcher mini-game.

    A side-scrolling game where the player moves left/right to catch
    Golden Snitches while avoiding Bludgers. The Sorting Hat watches
    and ponders in the corner.

    Usage:
        catcher = SnitchCatcher()

        # In update loop:
        catcher.update(delta_ms)
        catcher.move_left()  # or move_right()

        # In render loop:
        catcher.render(buffer)  # Renders to 128x128 buffer
    """

    # Game constants
    GROUND_Y = 110  # Y position where player flies
    PLAYER_SPEED = 120.0  # Pixels per second
    SPAWN_INTERVAL = 800.0  # ms between spawns

    def __init__(self):
        self._state = GameState()
        self._init_environment()

    def _init_environment(self) -> None:
        """Initialize background elements."""
        # Create stars
        for _ in range(40):
            self._state.stars.append(Star(
                x=random.uniform(0, 128),
                y=random.uniform(0, 80),
                brightness=random.uniform(0.3, 1.0),
                twinkle_speed=random.uniform(1.0, 3.0),
                depth=random.uniform(0.2, 0.8)
            ))

        # Create clouds
        for i in range(3):
            self._state.clouds.append(Cloud(
                x=i * 50 + random.randint(0, 20),
                y=random.randint(60, 80),
                width=random.randint(20, 35),
                speed=random.uniform(5.0, 15.0)
            ))

    def reset(self) -> None:
        """Reset the game."""
        self._state = GameState()
        self._init_environment()
        # Spawn initial snitches immediately so game feels active
        for _ in range(3):
            self._spawn_entity()

    @property
    def snitches_caught(self) -> int:
        """Get number of snitches caught."""
        return self._state.snitches_caught

    @property
    def bludger_hits(self) -> int:
        """Get number of bludger hits."""
        return self._state.bludger_hits

    def move_left(self) -> None:
        """Move player left."""
        self._state.target_x = max(10, self._state.target_x - 25)

    def move_right(self) -> None:
        """Move player right."""
        self._state.target_x = min(118, self._state.target_x + 25)

    def handle_jump(self) -> None:
        """Handle jump input - move player up temporarily."""
        # Move player up for catching higher snitches
        self._state.player_y = max(30, self._state.player_y - 20)

    def handle_catch(self) -> bool:
        """Handle catch input - try to catch nearest snitch.

        Returns:
            True if a snitch was caught.
        """
        # Find nearest snitch within catch range
        catch_range = 25
        nearest_snitch = None
        nearest_dist = float('inf')

        for entity in self._state.entities:
            if entity.collected or entity.entity_type != EntityType.SNITCH:
                continue

            dx = entity.x - self._state.player_x
            dy = entity.y - self._state.player_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < catch_range and dist < nearest_dist:
                nearest_dist = dist
                nearest_snitch = entity

        if nearest_snitch:
            nearest_snitch.collected = True
            self._state.snitches_caught += 1
            # Create golden sparkles
            for _ in range(12):
                self._state.sparkles.append(Sparkle(
                    x=nearest_snitch.x,
                    y=nearest_snitch.y,
                    life=random.uniform(300, 600),
                    vx=random.uniform(-80, 80),
                    vy=random.uniform(-100, -20),
                    color=random.choice([GOLD_BRIGHT, GOLD_SHINE, WING_WHITE])
                ))
            return True

        return False

    def handle_jump(self) -> None:
        """Handle jump input - move player up temporarily."""
        self._state.player_y = max(30, self._state.player_y - 20)

    def handle_catch(self) -> bool:
        """Handle catch input - try to catch nearest snitch."""
        catch_range = 25
        nearest_snitch = None
        nearest_dist = float('inf')

        for entity in self._state.entities:
            if entity.collected or entity.entity_type != EntityType.SNITCH:
                continue

            dx = entity.x - self._state.player_x
            dy = entity.y - self._state.player_y
            dist = (dx * dx + dy * dy) ** 0.5

            if dist < catch_range and dist < nearest_dist:
                nearest_dist = dist
                nearest_snitch = entity

        if nearest_snitch:
            nearest_snitch.collected = True
            self._state.snitches_caught += 1
            # Create golden sparkles
            for _ in range(12):
                self._state.sparkles.append(Sparkle(
                    x=nearest_snitch.x,
                    y=nearest_snitch.y,
                    life=random.uniform(300, 600),
                    vx=random.uniform(-80, 80),
                    vy=random.uniform(-100, -20),
                    color=random.choice([GOLD_BRIGHT, GOLD_SHINE, WING_WHITE]),
                    size=random.choice([1, 2])
                ))
            return True

        return False

    def update(self, delta_ms: float) -> None:
        """Update game state."""
        dt = delta_ms / 1000.0
        self._state.time_played += delta_ms

        # Smooth player movement towards target (X axis)
        diff = self._state.target_x - self._state.player_x
        movement = diff * 8.0 * dt
        self._state.player_x += movement

        # Parallax factor based on player movement
        parallax_shift = -movement * 0.5

        # Player Animation
        self._state.player_anim_timer += delta_ms
        base_anim_speed = 200
        if abs(movement) > 0.5:
             base_anim_speed = 100
        
        if self._state.player_anim_timer > base_anim_speed:
            self._state.player_anim_timer = 0
            self._state.player_frame = (self._state.player_frame + 1) % len(SEEKER_FRAMES)

        # Return player to ground level after jump (Y axis)
        ground_y = 110
        if self._state.player_y < ground_y:
            self._state.player_y += 60 * dt
            self._state.player_y = min(self._state.player_y, ground_y)

        # Update entity animation
        self._state.entity_anim_timer += delta_ms
        if self._state.entity_anim_timer > 90:
            self._state.entity_anim_timer = 0
            for entity in self._state.entities:
                if entity.entity_type == EntityType.SNITCH:
                     entity.frame = (entity.frame + 1) % len(SNITCH_FRAMES)

        # Update hat thinking animation
        self._state.hat_think_timer += delta_ms

        # Spawn new entities
        self._state.spawn_timer += delta_ms
        if self._state.spawn_timer >= self.SPAWN_INTERVAL:
            self._state.spawn_timer = 0
            self._spawn_entity()

        # Update entities
        for entity in self._state.entities:
            entity.x += entity.vx * dt + parallax_shift
            entity.y += entity.vy * dt
            
            # Record trail
            if entity.entity_type == EntityType.SNITCH:
                entity.trail.append((entity.x, entity.y))
                if len(entity.trail) > 4:
                    entity.trail.pop(0)

            # Bounce
            if entity.entity_type == EntityType.SNITCH:
                if entity.x < 5 or entity.x > 118:
                    entity.vx *= -1
                if entity.y < 20 or entity.y > 85:
                    entity.vy *= -1

                # Random direction changes
                if random.random() < 0.02:
                    entity.vx += random.uniform(-30, 30)
                    entity.vy += random.uniform(-20, 20)
                    entity.vx = max(-80, min(80, entity.vx))
                    entity.vy = max(-40, min(40, entity.vy))

        # Remove off-screen entities
        self._state.entities = [
            e for e in self._state.entities
            if not e.collected and -20 < e.x < 148 and -20 < e.y < 140
        ]

        # Update sparkles
        for sparkle in self._state.sparkles:
            sparkle.x += sparkle.vx * dt + parallax_shift
            sparkle.y += sparkle.vy * dt
            sparkle.life -= delta_ms
            sparkle.vy += 100 * dt
        self._state.sparkles = [s for s in self._state.sparkles if s.life > 0]

        # Update stars (Parallax)
        for star in self._state.stars:
            star.x += parallax_shift * star.depth * 0.1
            if star.x < 0: star.x += 128
            if star.x > 128: star.x -= 128
            
            star.brightness = 0.3 + 0.7 * abs(math.sin(
                self._state.time_played / 1000.0 * star.twinkle_speed
            ))

        # Update clouds (Parallax)
        for cloud in self._state.clouds:
            cloud.x -= cloud.speed * dt - parallax_shift * 0.8
            if cloud.x < -cloud.width:
                cloud.x = 140
                cloud.y = random.randint(60, 80)

        # Check collisions
        self._check_collisions()

    def _spawn_entity(self) -> None:
        """Spawn a new flying entity."""
        # 70% chance snitch, 30% chance bludger
        is_snitch = random.random() < 0.7

        if is_snitch:
            # Snitches appear from sides and move erratically
            from_left = random.random() < 0.5
            entity = FlyingEntity(
                x=-10 if from_left else 138,
                y=random.uniform(25, 75),
                vx=random.uniform(20, 50) * (1 if from_left else -1),
                vy=random.uniform(-20, 20),
                entity_type=EntityType.SNITCH
            )
        else:
            # Bludgers fall from top
            entity = FlyingEntity(
                x=random.uniform(20, 108),
                y=-10,
                vx=random.uniform(-20, 20),
                vy=random.uniform(40, 70),
                entity_type=EntityType.BLUDGER
            )

        self._state.entities.append(entity)

    def _check_collisions(self) -> None:
        """Check for collisions between player and entities."""
        player_left = self._state.player_x - 6
        player_right = self._state.player_x + 6
        player_top = self._state.player_y - 5
        player_bottom = self._state.player_y + 5

        for entity in self._state.entities:
            if entity.collected:
                continue

            entity_left = entity.x - entity.width / 2
            entity_right = entity.x + entity.width / 2
            entity_top = entity.y - entity.height / 2
            entity_bottom = entity.y + entity.height / 2

            # AABB collision
            if (player_right > entity_left and player_left < entity_right and
                player_bottom > entity_top and player_top < entity_bottom):

                entity.collected = True

                if entity.entity_type == EntityType.SNITCH:
                    self._state.snitches_caught += 1
                    # Create golden sparkles
                    for _ in range(12):
                        self._state.sparkles.append(Sparkle(
                            x=entity.x,
                            y=entity.y,
                            life=random.uniform(300, 600),
                            vx=random.uniform(-80, 80),
                            vy=random.uniform(-100, -20),
                            color=random.choice([GOLD_BRIGHT, GOLD_SHINE, WING_WHITE]),
                            size=random.choice([1, 2])
                        ))
                else:
                    self._state.bludger_hits += 1
                    # Create dark sparkles
                    for _ in range(8):
                        self._state.sparkles.append(Sparkle(
                            x=entity.x,
                            y=entity.y,
                            life=random.uniform(200, 400),
                            vx=random.uniform(-60, 60),
                            vy=random.uniform(-80, 0),
                            color=random.choice([BLUDGER_LIGHT, BLUDGER_MID, (150, 50, 50)]),
                            size=2
                        ))

    def render(self, buffer: NDArray[np.uint8], background: Optional[NDArray[np.uint8]] = None) -> None:
        """Render the game to buffer."""
        # Background
        if background is not None and background.shape == buffer.shape:
            # Use camera frame as background (dimmed for visibility)
            np.copyto(buffer, (background.astype(np.float32) * 0.3).astype(np.uint8))
            # Add slight blue tint for night feel
            buffer[:, :, 2] = np.clip(buffer[:, :, 2].astype(np.int16) + 20, 0, 255).astype(np.uint8)
        else:
            # Gradient night sky
            for y in range(128):
                ratio = y / 128.0
                r = int(SKY_DARK[0] + (SKY_MID[0] - SKY_DARK[0]) * ratio)
                g = int(SKY_DARK[1] + (SKY_MID[1] - SKY_DARK[1]) * ratio)
                b = int(SKY_DARK[2] + (SKY_MID[2] - SKY_DARK[2]) * ratio)
                buffer[y, :, 0] = r
                buffer[y, :, 1] = g
                buffer[y, :, 2] = b

            for cloud in self._state.clouds:
                self._render_cloud(buffer, int(cloud.x), int(cloud.y), cloud.width)

        # Render stars (always visible)
        for star in self._state.stars:
            x, y = int(star.x), int(star.y)
            if 0 <= x < 128 and 0 <= y < 80:
                brightness = int(255 * star.brightness)
                buffer[y, x] = (brightness, brightness, min(255, brightness + 50))

        # Render entities
        for entity in self._state.entities:
            if not entity.collected:
                # Ghost trails for snitches
                if entity.entity_type == EntityType.SNITCH and entity.trail:
                    for i, (tx, ty) in enumerate(entity.trail):
                        alpha = (i + 1) / (len(entity.trail) + 1) * 0.5
                        # Draw trail as small golden dots
                        self._draw_pixel(buffer, int(tx), int(ty), tuple(int(c*alpha) for c in GOLD_DARK))

                # Sprite
                if entity.entity_type == EntityType.SNITCH:
                    sprite = SNITCH_FRAMES[entity.frame % len(SNITCH_FRAMES)]
                else:
                    sprite = BLUDGER
                self._render_sprite_centered(buffer, sprite, int(entity.x), int(entity.y))

        # Render sparkles
        for sparkle in self._state.sparkles:
            x, y = int(sparkle.x), int(sparkle.y)
            alpha = sparkle.life / 600.0
            color = tuple(int(c * alpha) for c in sparkle.color)
            
            if sparkle.size == 1:
                self._draw_pixel(buffer, x, y, color)
            else:
                self._draw_pixel(buffer, x, y, color)
                self._draw_pixel(buffer, x+1, y, color)
                self._draw_pixel(buffer, x, y+1, color)
                self._draw_pixel(buffer, x+1, y+1, color)

        # Render player (seeker on broom) - Animated
        seeker_sprite = SEEKER_FRAMES[self._state.player_frame % len(SEEKER_FRAMES)]
        self._render_sprite_centered(buffer, seeker_sprite, int(self._state.player_x), int(self._state.player_y))

        # Render Sorting Hat in top-left corner with thinking animation
        hat_sprite = SORTING_HAT_THINK if int(self._state.hat_think_timer / 500) % 2 == 0 else SORTING_HAT
        self._render_sprite(buffer, hat_sprite, 2, 2)

        # Render score
        self._render_score(buffer)

    def _draw_pixel(self, buffer, x, y, color):
        if 0 <= x < 128 and 0 <= y < 128:
            buffer[y, x] = color

    def _render_sprite(self, buffer: NDArray, sprite: List[List], x: int, y: int) -> None:
        """Render a sprite to the buffer."""
        for row_idx, row in enumerate(sprite):
            for col_idx, pixel in enumerate(row):
                if pixel is not None:
                    px = x + col_idx
                    py = y + row_idx
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = pixel

    def _render_sprite_centered(self, buffer: NDArray, sprite: List[List], cx: int, cy: int) -> None:
        """Render a sprite centered at position."""
        h = len(sprite)
        w = len(sprite[0]) if sprite else 0
        self._render_sprite(buffer, sprite, cx - w // 2, cy - h // 2)

    def _render_cloud(self, buffer: NDArray, x: int, y: int, width: int) -> None:
        """Render a wispy cloud."""
        height = width // 3
        for dy in range(height):
            for dx in range(width):
                # Circular cloud shape
                cx, cy = width // 2, height // 2
                dist = math.sqrt((dx - cx) ** 2 + (dy - cy) ** 2 * 2)
                if dist < width // 2:
                    px, py = x + dx, y + dy
                    if 0 <= px < 128 and 0 <= py < 128:
                        # Semi-transparent cloud
                        alpha = 1.0 - (dist / (width // 2))
                        old = buffer[py, px]
                        new_r = int(old[0] * (1 - alpha * 0.3) + CLOUD_GRAY[0] * alpha * 0.3)
                        new_g = int(old[1] * (1 - alpha * 0.3) + CLOUD_GRAY[1] * alpha * 0.3)
                        new_b = int(old[2] * (1 - alpha * 0.3) + CLOUD_GRAY[2] * alpha * 0.3)
                        buffer[py, px] = (new_r, new_g, new_b)

    def _render_score(self, buffer: NDArray) -> None:
        """Render score at top-right."""
        from artifact.graphics.text_utils import draw_text

        # Snitches caught (gold text)
        snitch_text = f"{self._state.snitches_caught}"
        draw_text(buffer, snitch_text, 110, 4, GOLD_BRIGHT, scale=1)

        # Small snitch icon
        buffer[3:5, 103:107] = [GOLD_BRIGHT, GOLD_DARK, GOLD_DARK, GOLD_BRIGHT]
        buffer[5:7, 103:107] = [GOLD_DARK, GOLD_BRIGHT, GOLD_BRIGHT, GOLD_DARK]

    def render_ticker(self, buffer: NDArray, progress: float = 0.0) -> None:
        """Render game info on ticker display (48x8).

        Args:
            buffer: The 48x8 RGB ticker buffer
            progress: Progress value from 0.0 to 1.0 (from AI processing)
        """
        from artifact.graphics.primitives import fill

        # Clear ticker
        fill(buffer, (0, 0, 0))

        # Animated golden snitch pattern
        time_offset = int(self._state.time_played / 50) % 48
        for i in range(6):
            x = (time_offset + i * 8) % 48
            # Small golden dots moving across
            buffer[3:5, x:min(x + 2, 48)] = GOLD_BRIGHT

        # Progress bar overlay
        bar_w = int(44 * progress)
        if bar_w > 0:
            for x in range(bar_w):
                ratio = x / 44
                r = int(200 + 55 * ratio)
                g = int(150 + 65 * ratio)
                b = int(50 * (1 - ratio))
                buffer[1:7, 2 + x, 0] = r
                buffer[1:7, 2 + x, 1] = g
                buffer[1:7, 2 + x, 2] = b


# Singleton instance for easy access
_snitch_catcher: Optional[SnitchCatcher] = None


def get_snitch_catcher() -> SnitchCatcher:
    """Get or create the Snitch Catcher game instance."""
    global _snitch_catcher
    if _snitch_catcher is None:
        _snitch_catcher = SnitchCatcher()
    return _snitch_catcher


def reset_snitch_catcher() -> SnitchCatcher:
    """Reset and return the Snitch Catcher game."""
    global _snitch_catcher
    _snitch_catcher = SnitchCatcher()
    return _snitch_catcher

"""Santa Runner Mini-Game - Chrome Dino style game with Christmas theme.

A fun mini-game to play while waiting for AI processing.
Features Santa Claus running through a snowy landscape,
jumping over presents, snowmen, and Christmas trees!
"""

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray


# =============================================================================
# Pixel Art Sprites (each row is a line of pixels, using color tuples)
# =============================================================================

# Santa colors
SANTA_RED = (220, 50, 50)
SANTA_WHITE = (255, 255, 255)
SANTA_SKIN = (255, 200, 160)
SANTA_BLACK = (40, 40, 40)
SANTA_BELT = (80, 60, 40)
SANTA_GOLD = (255, 200, 0)
TRANS = None  # Transparent

# Santa running frame 1 (12x14)
SANTA_RUN1 = [
    [TRANS, TRANS, TRANS, SANTA_WHITE, SANTA_WHITE, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_SKIN, SANTA_SKIN, SANTA_SKIN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_SKIN, SANTA_WHITE, SANTA_SKIN, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_WHITE, SANTA_WHITE, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS],
    [SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_BELT, SANTA_GOLD, SANTA_BELT, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS],
    [TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_RED, SANTA_RED, TRANS, SANTA_RED, SANTA_RED, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_RED, SANTA_RED, TRANS, TRANS, SANTA_RED, SANTA_RED, TRANS, TRANS, TRANS, TRANS],
    [TRANS, SANTA_BLACK, SANTA_BLACK, TRANS, TRANS, TRANS, TRANS, SANTA_BLACK, SANTA_BLACK, TRANS, TRANS, TRANS],
]

# Santa running frame 2 (12x14) - legs swapped
SANTA_RUN2 = [
    [TRANS, TRANS, TRANS, SANTA_WHITE, SANTA_WHITE, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_SKIN, SANTA_SKIN, SANTA_SKIN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_SKIN, SANTA_WHITE, SANTA_SKIN, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_WHITE, SANTA_WHITE, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS],
    [SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_BELT, SANTA_GOLD, SANTA_BELT, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS],
    [TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_RED, SANTA_RED, SANTA_RED, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_RED, SANTA_RED, TRANS, SANTA_RED, SANTA_RED, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, SANTA_BLACK, SANTA_BLACK, TRANS, TRANS, SANTA_BLACK, SANTA_BLACK, TRANS, TRANS, TRANS, TRANS, TRANS],
]

# Santa jumping (12x14)
SANTA_JUMP = [
    [TRANS, TRANS, TRANS, SANTA_WHITE, SANTA_WHITE, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_SKIN, SANTA_SKIN, SANTA_SKIN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_WHITE, SANTA_SKIN, SANTA_WHITE, SANTA_SKIN, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_WHITE, SANTA_WHITE, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS],
    [SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_BELT, SANTA_GOLD, SANTA_BELT, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS],
    [TRANS, SANTA_WHITE, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_RED, SANTA_WHITE, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SANTA_RED, TRANS, SANTA_RED, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SANTA_RED, TRANS, TRANS, TRANS, SANTA_RED, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, SANTA_BLACK, SANTA_BLACK, TRANS, TRANS, SANTA_BLACK, SANTA_BLACK, TRANS, TRANS, TRANS, TRANS, TRANS],
]

# Obstacle colors
PRESENT_RED = (200, 50, 50)
PRESENT_GREEN = (50, 150, 50)
PRESENT_GOLD = (255, 200, 0)
PRESENT_BLUE = (50, 100, 200)
SNOWMAN_WHITE = (255, 255, 255)
SNOWMAN_ORANGE = (255, 150, 50)
SNOWMAN_BLACK = (30, 30, 30)
TREE_GREEN = (40, 120, 40)
TREE_DARK = (30, 90, 30)
TREE_BROWN = (100, 70, 40)
TREE_STAR = (255, 220, 50)
CANDY_RED = (220, 50, 50)
CANDY_WHITE = (255, 255, 255)

# Present box (8x8)
PRESENT = [
    [TRANS, PRESENT_GOLD, PRESENT_GOLD, PRESENT_GOLD, PRESENT_GOLD, PRESENT_GOLD, PRESENT_GOLD, TRANS],
    [PRESENT_GOLD, PRESENT_GOLD, TRANS, PRESENT_GOLD, PRESENT_GOLD, TRANS, PRESENT_GOLD, PRESENT_GOLD],
    [PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED],
    [PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED],
    [PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED],
    [PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED],
    [PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED],
    [PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED, PRESENT_GOLD, PRESENT_RED, PRESENT_RED],
]

# Snowman (10x12)
SNOWMAN = [
    [TRANS, TRANS, TRANS, SNOWMAN_BLACK, SNOWMAN_BLACK, SNOWMAN_BLACK, SNOWMAN_BLACK, TRANS, TRANS, TRANS],
    [TRANS, TRANS, SNOWMAN_BLACK, SNOWMAN_BLACK, SNOWMAN_BLACK, SNOWMAN_BLACK, SNOWMAN_BLACK, SNOWMAN_BLACK, TRANS, TRANS],
    [TRANS, TRANS, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS],
    [TRANS, SNOWMAN_WHITE, SNOWMAN_BLACK, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_BLACK, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS],
    [TRANS, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_ORANGE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS],
    [TRANS, TRANS, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS, TRANS],
    [TRANS, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS],
    [SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_BLACK, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS],
    [SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_BLACK, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS],
    [TRANS, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_BLACK, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS],
    [TRANS, TRANS, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, SNOWMAN_WHITE, SNOWMAN_WHITE, SNOWMAN_WHITE, TRANS, TRANS, TRANS, TRANS],
]

# Christmas tree (10x14)
TREE = [
    [TRANS, TRANS, TRANS, TRANS, TREE_STAR, TREE_STAR, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, TREE_STAR, TREE_STAR, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, TREE_GREEN, TREE_GREEN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TREE_GREEN, TREE_GREEN, PRESENT_RED, TREE_GREEN, TREE_GREEN, TREE_GREEN, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TRANS, TRANS],
    [TRANS, TREE_GREEN, TREE_GREEN, PRESENT_GOLD, TREE_GREEN, TREE_GREEN, PRESENT_BLUE, TREE_GREEN, TREE_GREEN, TRANS],
    [TRANS, TRANS, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TRANS, TRANS],
    [TRANS, TREE_GREEN, TREE_GREEN, TREE_GREEN, PRESENT_RED, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TRANS],
    [TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN, TREE_GREEN],
    [TRANS, TRANS, TRANS, TRANS, TREE_BROWN, TREE_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, TREE_BROWN, TREE_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TREE_BROWN, TREE_BROWN, TREE_BROWN, TREE_BROWN, TRANS, TRANS, TRANS],
]

# Candy cane (5x12)
CANDY_CANE = [
    [TRANS, CANDY_RED, CANDY_RED, CANDY_RED, TRANS],
    [CANDY_RED, CANDY_WHITE, CANDY_WHITE, CANDY_RED, CANDY_RED],
    [CANDY_RED, TRANS, TRANS, TRANS, CANDY_WHITE],
    [CANDY_WHITE, TRANS, TRANS, TRANS, TRANS],
    [CANDY_RED, TRANS, TRANS, TRANS, TRANS],
    [CANDY_WHITE, TRANS, TRANS, TRANS, TRANS],
    [CANDY_RED, TRANS, TRANS, TRANS, TRANS],
    [CANDY_WHITE, TRANS, TRANS, TRANS, TRANS],
    [CANDY_RED, TRANS, TRANS, TRANS, TRANS],
    [CANDY_WHITE, TRANS, TRANS, TRANS, TRANS],
    [CANDY_RED, TRANS, TRANS, TRANS, TRANS],
    [CANDY_WHITE, TRANS, TRANS, TRANS, TRANS],
]

# Star collectible (5x5)
STAR = [
    [TRANS, TRANS, TREE_STAR, TRANS, TRANS],
    [TRANS, TREE_STAR, TREE_STAR, TREE_STAR, TRANS],
    [TREE_STAR, TREE_STAR, TREE_STAR, TREE_STAR, TREE_STAR],
    [TRANS, TREE_STAR, TREE_STAR, TREE_STAR, TRANS],
    [TRANS, TREE_STAR, TRANS, TREE_STAR, TRANS],
]


class ObstacleType(Enum):
    """Types of obstacles."""
    PRESENT = auto()
    SNOWMAN = auto()
    TREE = auto()
    CANDY_CANE = auto()


OBSTACLE_SPRITES = {
    ObstacleType.PRESENT: PRESENT,
    ObstacleType.SNOWMAN: SNOWMAN,
    ObstacleType.TREE: TREE,
    ObstacleType.CANDY_CANE: CANDY_CANE,
}


@dataclass
class Obstacle:
    """An obstacle in the game."""
    x: float
    type: ObstacleType

    @property
    def width(self) -> int:
        sprite = OBSTACLE_SPRITES[self.type]
        return len(sprite[0]) if sprite else 8

    @property
    def height(self) -> int:
        sprite = OBSTACLE_SPRITES[self.type]
        return len(sprite) if sprite else 8


@dataclass
class Collectible:
    """A collectible star."""
    x: float
    y: float
    collected: bool = False


@dataclass
class Snowflake:
    """A snowflake particle."""
    x: float
    y: float
    speed: float
    size: int


@dataclass
class Cloud:
    """A background cloud."""
    x: float
    y: float
    width: int


@dataclass
class GameState:
    """State of the Santa runner game."""
    # Santa position and physics
    santa_y: float = 0.0
    santa_vy: float = 0.0
    is_jumping: bool = False
    run_frame: int = 0
    run_timer: float = 0.0

    # Game state
    score: int = 0
    high_score: int = 0
    game_over: bool = False
    game_over_timer: float = 0.0
    speed: float = 60.0  # Pixels per second

    # Entities
    obstacles: List[Obstacle] = field(default_factory=list)
    collectibles: List[Collectible] = field(default_factory=list)
    snowflakes: List[Snowflake] = field(default_factory=list)
    clouds: List[Cloud] = field(default_factory=list)

    # Timing
    spawn_timer: float = 0.0
    spawn_interval: float = 1500.0  # ms between obstacles
    distance: float = 0.0
    time_played: float = 0.0


class SantaRunner:
    """Santa Runner mini-game.

    A Chrome dinosaur-style endless runner with Santa Claus.
    Jump over presents, snowmen, and Christmas trees!

    Usage:
        runner = SantaRunner()

        # In update loop:
        runner.update(delta_ms)
        runner.handle_jump()  # Call when jump button pressed

        # In render loop:
        runner.render(buffer)  # Renders to 128x128 buffer
    """

    # Game constants
    GROUND_Y = 100  # Y position of ground
    SANTA_X = 20    # Santa's X position (fixed)
    GRAVITY = 600.0  # Pixels per second squared
    JUMP_VELOCITY = -200.0  # Initial jump velocity

    def __init__(self):
        self._state = GameState()
        self._init_environment()

    def _init_environment(self) -> None:
        """Initialize background elements."""
        # Create initial snowflakes
        for _ in range(30):
            self._state.snowflakes.append(Snowflake(
                x=random.uniform(0, 128),
                y=random.uniform(0, 100),
                speed=random.uniform(20, 50),
                size=random.choice([1, 1, 2])
            ))

        # Create initial clouds
        for i in range(3):
            self._state.clouds.append(Cloud(
                x=i * 50 + random.randint(0, 20),
                y=random.randint(10, 30),
                width=random.randint(15, 25)
            ))

    def reset(self) -> None:
        """Reset the game."""
        old_high_score = self._state.high_score
        self._state = GameState()
        self._state.high_score = old_high_score
        self._init_environment()

    @property
    def is_game_over(self) -> bool:
        """Check if game is over."""
        return self._state.game_over

    @property
    def score(self) -> int:
        """Get current score."""
        return self._state.score

    @property
    def high_score(self) -> int:
        """Get high score."""
        return self._state.high_score

    def handle_jump(self) -> bool:
        """Handle jump input. Returns True if jump was triggered."""
        if self._state.game_over:
            # Restart after brief delay
            if self._state.game_over_timer > 500:
                self.reset()
            return False

        if not self._state.is_jumping:
            self._state.is_jumping = True
            self._state.santa_vy = self.JUMP_VELOCITY
            return True
        return False

    def update(self, delta_ms: float) -> None:
        """Update game state."""
        if self._state.game_over:
            self._state.game_over_timer += delta_ms
            return

        dt = delta_ms / 1000.0
        self._state.time_played += delta_ms

        # Update score based on distance
        self._state.distance += self._state.speed * dt
        self._state.score = int(self._state.distance / 10)

        # Increase speed over time (max 150)
        self._state.speed = min(150.0, 60.0 + self._state.time_played / 1000.0 * 2)

        # Update Santa physics
        if self._state.is_jumping:
            self._state.santa_vy += self.GRAVITY * dt
            self._state.santa_y += self._state.santa_vy * dt

            if self._state.santa_y >= 0:
                self._state.santa_y = 0
                self._state.santa_vy = 0
                self._state.is_jumping = False

        # Update run animation
        self._state.run_timer += delta_ms
        if self._state.run_timer > 150:
            self._state.run_timer = 0
            self._state.run_frame = 1 - self._state.run_frame

        # Spawn obstacles
        self._state.spawn_timer += delta_ms
        if self._state.spawn_timer >= self._state.spawn_interval:
            self._state.spawn_timer = 0
            self._spawn_obstacle()
            # Decrease spawn interval over time (min 800ms)
            self._state.spawn_interval = max(800.0, 1500.0 - self._state.time_played / 1000.0 * 20)

        # Update obstacles
        for obs in self._state.obstacles:
            obs.x -= self._state.speed * dt

        # Remove off-screen obstacles
        self._state.obstacles = [o for o in self._state.obstacles if o.x > -20]

        # Update collectibles
        for col in self._state.collectibles:
            col.x -= self._state.speed * dt
        self._state.collectibles = [c for c in self._state.collectibles if c.x > -10 and not c.collected]

        # Update snowflakes
        for flake in self._state.snowflakes:
            flake.y += flake.speed * dt
            flake.x -= self._state.speed * dt * 0.2  # Slight horizontal drift
            if flake.y > 105:
                flake.y = -5
                flake.x = random.uniform(0, 140)
            if flake.x < -5:
                flake.x = 133

        # Update clouds
        for cloud in self._state.clouds:
            cloud.x -= self._state.speed * dt * 0.3
            if cloud.x < -cloud.width:
                cloud.x = 128 + random.randint(0, 20)
                cloud.y = random.randint(10, 30)
                cloud.width = random.randint(15, 25)

        # Check collisions
        self._check_collisions()

        # Check collectible pickups
        self._check_collectibles()

    def _spawn_obstacle(self) -> None:
        """Spawn a new obstacle."""
        # Choose random obstacle type with weights
        weights = [4, 2, 2, 3]  # present, snowman, tree, candy cane
        obstacle_type = random.choices(list(ObstacleType), weights=weights)[0]

        self._state.obstacles.append(Obstacle(
            x=140.0,
            type=obstacle_type
        ))

        # Sometimes spawn a collectible star above the obstacle
        if random.random() < 0.3:
            self._state.collectibles.append(Collectible(
                x=145.0,
                y=self.GROUND_Y - 35 - random.randint(0, 15)
            ))

    def _check_collisions(self) -> None:
        """Check for collisions with obstacles."""
        santa_left = self.SANTA_X
        santa_right = self.SANTA_X + 10
        santa_top = self.GROUND_Y - 12 + int(self._state.santa_y)
        santa_bottom = self.GROUND_Y + int(self._state.santa_y)

        for obs in self._state.obstacles:
            obs_left = obs.x
            obs_right = obs.x + obs.width
            obs_top = self.GROUND_Y - obs.height
            obs_bottom = self.GROUND_Y

            # AABB collision
            if (santa_right > obs_left + 2 and santa_left < obs_right - 2 and
                santa_bottom > obs_top + 2 and santa_top < obs_bottom):
                self._game_over()
                return

    def _check_collectibles(self) -> None:
        """Check for collectible pickups."""
        santa_x = self.SANTA_X + 5
        santa_y = self.GROUND_Y - 6 + int(self._state.santa_y)

        for col in self._state.collectibles:
            if not col.collected:
                dist = math.sqrt((santa_x - col.x) ** 2 + (santa_y - col.y) ** 2)
                if dist < 10:
                    col.collected = True
                    self._state.score += 10  # Bonus for collecting star

    def _game_over(self) -> None:
        """Handle game over."""
        self._state.game_over = True
        self._state.game_over_timer = 0
        if self._state.score > self._state.high_score:
            self._state.high_score = self._state.score

    def render(self, buffer: NDArray[np.uint8], background: Optional[NDArray[np.uint8]] = None) -> None:
        """Render the game to buffer.

        Args:
            buffer: The 128x128 RGB buffer to render to
            background: Optional camera frame to use as background (dimmed).
                        If None, uses default gradient sky.
        """
        if background is not None and background.shape == buffer.shape:
            # Use camera frame as background (dimmed for visibility)
            np.copyto(buffer, (background.astype(np.float32) * 0.4).astype(np.uint8))

            # Draw semi-transparent ground line at bottom for visual reference
            buffer[self.GROUND_Y:self.GROUND_Y + 2, :, :] = np.clip(
                buffer[self.GROUND_Y:self.GROUND_Y + 2, :, :].astype(np.int16) + 60,
                0, 255
            ).astype(np.uint8)
        else:
            # Clear with gradient sky (dark blue to lighter)
            for y in range(self.GROUND_Y):
                darkness = int(20 + y * 0.3)
                buffer[y, :, 0] = darkness // 2
                buffer[y, :, 1] = darkness // 2
                buffer[y, :, 2] = darkness + 20

            # Ground (white snow)
            buffer[self.GROUND_Y:, :, 0] = 240
            buffer[self.GROUND_Y:, :, 1] = 245
            buffer[self.GROUND_Y:, :, 2] = 255

            # Add some ground texture (darker patches)
            for x in range(0, 128, 8):
                offset = int((self._state.distance / 3 + x) % 16)
                if offset < 4:
                    buffer[self.GROUND_Y + 2:self.GROUND_Y + 4, x:x + 3, 0] = 220
                    buffer[self.GROUND_Y + 2:self.GROUND_Y + 4, x:x + 3, 1] = 225
                    buffer[self.GROUND_Y + 2:self.GROUND_Y + 4, x:x + 3, 2] = 235

            # Render clouds (only on default background)
            for cloud in self._state.clouds:
                self._render_cloud(buffer, int(cloud.x), int(cloud.y), cloud.width)

        # Render snowflakes (always)
        for flake in self._state.snowflakes:
            x, y = int(flake.x), int(flake.y)
            if 0 <= x < 128 and 0 <= y < 100:
                buffer[y, x] = (255, 255, 255)
                if flake.size >= 2 and x + 1 < 128:
                    buffer[y, x + 1] = (255, 255, 255)

        # Render obstacles
        for obs in self._state.obstacles:
            sprite = OBSTACLE_SPRITES[obs.type]
            self._render_sprite(buffer, sprite, int(obs.x), self.GROUND_Y - len(sprite))

        # Render collectibles
        for col in self._state.collectibles:
            if not col.collected:
                self._render_sprite(buffer, STAR, int(col.x), int(col.y))

        # Render Santa
        santa_y = self.GROUND_Y - 12 + int(self._state.santa_y)
        if self._state.is_jumping:
            sprite = SANTA_JUMP
        elif self._state.run_frame == 0:
            sprite = SANTA_RUN1
        else:
            sprite = SANTA_RUN2
        self._render_sprite(buffer, sprite, self.SANTA_X, santa_y)

        # Render score
        self._render_score(buffer)

        # Game over overlay
        if self._state.game_over:
            self._render_game_over(buffer)

    def _render_sprite(self, buffer: NDArray, sprite: List[List], x: int, y: int) -> None:
        """Render a sprite to the buffer."""
        for row_idx, row in enumerate(sprite):
            for col_idx, pixel in enumerate(row):
                if pixel is not None:
                    px = x + col_idx
                    py = y + row_idx
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = pixel

    def _render_cloud(self, buffer: NDArray, x: int, y: int, width: int) -> None:
        """Render a simple cloud."""
        cloud_color = (60, 70, 90)
        height = width // 3

        for dy in range(height):
            for dx in range(width):
                # Circular cloud shape
                cx, cy = width // 2, height // 2
                dist = math.sqrt((dx - cx) ** 2 + (dy - cy) ** 2 * 3)
                if dist < width // 2:
                    px, py = x + dx, y + dy
                    if 0 <= px < 128 and 0 <= py < 100:
                        buffer[py, px] = cloud_color

    def _render_score(self, buffer: NDArray) -> None:
        """Render score at top of screen (below progress bar area)."""
        from artifact.graphics.text_utils import draw_text

        # Score in top-right, positioned below progress bar (y=10 to avoid overlap)
        score_text = f"{self._state.score:04d}"
        draw_text(buffer, score_text, 95, 10, (255, 255, 255), scale=1)

        # High score indicator if beaten
        if self._state.score > 0 and self._state.score >= self._state.high_score:
            draw_text(buffer, "HI", 80, 10, (255, 200, 0), scale=1)

    def _render_game_over(self, buffer: NDArray) -> None:
        """Render game over overlay."""
        from artifact.graphics.text_utils import draw_centered_text

        # Semi-transparent overlay
        buffer[:, :, :] = (buffer[:, :, :] * 0.5).astype(np.uint8)

        # Game over text
        draw_centered_text(buffer, "GAME OVER", 45, (255, 100, 100), scale=2)
        draw_centered_text(buffer, f"SCORE: {self._state.score}", 70, (255, 255, 255), scale=1)

        if self._state.score >= self._state.high_score and self._state.score > 0:
            draw_centered_text(buffer, "NEW HIGH SCORE!", 82, (255, 220, 0), scale=1)

        # Blink "press to restart"
        if int(self._state.game_over_timer / 400) % 2 == 0:
            draw_centered_text(buffer, "PRESS TO PLAY", 100, (200, 200, 200), scale=1)


# Singleton instance for easy access across modes
_santa_runner: Optional[SantaRunner] = None


def get_santa_runner() -> SantaRunner:
    """Get or create the Santa runner game instance."""
    global _santa_runner
    if _santa_runner is None:
        _santa_runner = SantaRunner()
    return _santa_runner


def reset_santa_runner() -> SantaRunner:
    """Reset and return the Santa runner game."""
    global _santa_runner
    _santa_runner = SantaRunner()
    return _santa_runner

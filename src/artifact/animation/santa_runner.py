"""Beach Runner Mini-Game - Chrome Dino style game with Brazil/tropical theme.

A fun mini-game to play while waiting for AI processing.
Features a colorful parrot running through a tropical beach,
jumping over coconuts, crabs, and beach umbrellas!
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

# Parrot colors (tropical bird)
PARROT_GREEN = (50, 200, 80)
PARROT_YELLOW = (255, 220, 50)
PARROT_RED = (230, 60, 60)
PARROT_BLUE = (50, 150, 255)
PARROT_ORANGE = (255, 150, 50)
PARROT_WHITE = (255, 255, 255)
PARROT_BLACK = (30, 30, 30)
PARROT_BEAK = (255, 180, 50)
TRANS = None  # Transparent

# Parrot running frame 1 (12x12)
PARROT_RUN1 = [
    [TRANS, TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_YELLOW, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_GREEN, PARROT_WHITE, PARROT_BLACK, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BEAK, PARROT_BEAK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_RED, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [PARROT_RED, PARROT_RED, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_RED, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_ORANGE, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_ORANGE, TRANS, PARROT_ORANGE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_ORANGE, PARROT_ORANGE, TRANS, PARROT_ORANGE, PARROT_ORANGE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
]

# Parrot running frame 2 (12x12) - wings flap
PARROT_RUN2 = [
    [TRANS, TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_YELLOW, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_GREEN, PARROT_WHITE, PARROT_BLACK, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BEAK, PARROT_BEAK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [PARROT_RED, PARROT_RED, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [PARROT_RED, PARROT_RED, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_ORANGE, PARROT_ORANGE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_ORANGE, TRANS, TRANS, PARROT_ORANGE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_ORANGE, TRANS, TRANS, PARROT_ORANGE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
]

# Parrot jumping (12x12) - wings spread
PARROT_JUMP = [
    [TRANS, TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_YELLOW, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_GREEN, PARROT_WHITE, PARROT_BLACK, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BEAK, PARROT_BEAK, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [PARROT_RED, PARROT_RED, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS, TRANS],
    [PARROT_RED, PARROT_RED, PARROT_RED, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS],
    [TRANS, PARROT_RED, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, PARROT_BLUE, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_GREEN, PARROT_GREEN, PARROT_GREEN, PARROT_BLUE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, PARROT_ORANGE, PARROT_ORANGE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, PARROT_ORANGE, TRANS, TRANS, PARROT_ORANGE, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS],
]

# Beach/tropical obstacle colors
COCONUT_BROWN = (139, 90, 43)
COCONUT_DARK = (100, 60, 30)
CRAB_RED = (220, 80, 60)
CRAB_ORANGE = (255, 140, 80)
UMBRELLA_RED = (230, 50, 50)
UMBRELLA_WHITE = (255, 255, 255)
UMBRELLA_YELLOW = (255, 220, 50)
PALM_GREEN = (50, 140, 50)
PALM_DARK = (30, 100, 30)
PALM_BROWN = (120, 80, 40)
BUCKET_BLUE = (80, 150, 255)
BUCKET_YELLOW = (255, 220, 80)

# Coconut (8x8)
COCONUT = [
    [TRANS, TRANS, COCONUT_BROWN, COCONUT_BROWN, COCONUT_BROWN, COCONUT_BROWN, TRANS, TRANS],
    [TRANS, COCONUT_BROWN, COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN, COCONUT_BROWN, TRANS],
    [COCONUT_BROWN, COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN, COCONUT_BROWN],
    [COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN],
    [COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN],
    [COCONUT_BROWN, COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN, COCONUT_BROWN],
    [TRANS, COCONUT_BROWN, COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN, COCONUT_BROWN, TRANS],
    [TRANS, TRANS, COCONUT_BROWN, COCONUT_BROWN, COCONUT_BROWN, COCONUT_BROWN, TRANS, TRANS],
]

# Crab (10x6)
CRAB = [
    [TRANS, CRAB_RED, TRANS, TRANS, TRANS, TRANS, TRANS, TRANS, CRAB_RED, TRANS],
    [CRAB_RED, CRAB_RED, TRANS, CRAB_ORANGE, CRAB_ORANGE, CRAB_ORANGE, CRAB_ORANGE, TRANS, CRAB_RED, CRAB_RED],
    [TRANS, TRANS, CRAB_ORANGE, CRAB_RED, CRAB_RED, CRAB_RED, CRAB_RED, CRAB_ORANGE, TRANS, TRANS],
    [TRANS, CRAB_ORANGE, CRAB_RED, CRAB_RED, CRAB_RED, CRAB_RED, CRAB_RED, CRAB_RED, CRAB_ORANGE, TRANS],
    [TRANS, CRAB_ORANGE, TRANS, CRAB_ORANGE, TRANS, TRANS, CRAB_ORANGE, TRANS, CRAB_ORANGE, TRANS],
    [CRAB_ORANGE, TRANS, TRANS, TRANS, CRAB_ORANGE, CRAB_ORANGE, TRANS, TRANS, TRANS, CRAB_ORANGE],
]

# Beach umbrella (10x12)
UMBRELLA = [
    [TRANS, TRANS, TRANS, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, TRANS, TRANS, TRANS],
    [TRANS, TRANS, UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_RED, TRANS, TRANS],
    [TRANS, UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_WHITE, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_WHITE, UMBRELLA_RED, TRANS],
    [UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_WHITE, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_WHITE, UMBRELLA_RED],
    [UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_RED, UMBRELLA_WHITE, UMBRELLA_RED],
    [TRANS, TRANS, TRANS, TRANS, PALM_BROWN, PALM_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, PALM_BROWN, PALM_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, PALM_BROWN, PALM_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, PALM_BROWN, PALM_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, PALM_BROWN, PALM_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, PALM_BROWN, PALM_BROWN, TRANS, TRANS, TRANS, TRANS],
    [TRANS, TRANS, TRANS, TRANS, PALM_BROWN, PALM_BROWN, TRANS, TRANS, TRANS, TRANS],
]

# Beach bucket (8x8)
BUCKET = [
    [TRANS, BUCKET_YELLOW, BUCKET_YELLOW, BUCKET_YELLOW, BUCKET_YELLOW, BUCKET_YELLOW, BUCKET_YELLOW, TRANS],
    [BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE],
    [BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE],
    [BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE],
    [BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE],
    [TRANS, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, TRANS],
    [TRANS, TRANS, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, BUCKET_BLUE, TRANS, TRANS],
    [TRANS, TRANS, TRANS, BUCKET_BLUE, BUCKET_BLUE, TRANS, TRANS, TRANS],
]

# Collectible star (beach ball style) (6x6)
STAR = [
    [TRANS, (255, 200, 50), (255, 200, 50), (255, 200, 50), (255, 200, 50), TRANS],
    [(255, 200, 50), (255, 100, 100), (255, 255, 255), (255, 255, 255), (100, 200, 255), (255, 200, 50)],
    [(255, 200, 50), (255, 255, 255), (255, 100, 100), (100, 200, 255), (255, 255, 255), (255, 200, 50)],
    [(255, 200, 50), (255, 255, 255), (100, 200, 255), (255, 100, 100), (255, 255, 255), (255, 200, 50)],
    [(255, 200, 50), (100, 200, 255), (255, 255, 255), (255, 255, 255), (255, 100, 100), (255, 200, 50)],
    [TRANS, (255, 200, 50), (255, 200, 50), (255, 200, 50), (255, 200, 50), TRANS],
]

# Projectile - coconut (small) (4x4)
PROJECTILE = [
    [TRANS, COCONUT_BROWN, COCONUT_BROWN, TRANS],
    [COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN],
    [COCONUT_BROWN, COCONUT_DARK, COCONUT_DARK, COCONUT_BROWN],
    [TRANS, COCONUT_BROWN, COCONUT_BROWN, TRANS],
]


class ObstacleType(Enum):
    """Types of obstacles."""
    COCONUT = auto()
    CRAB = auto()
    UMBRELLA = auto()
    BUCKET = auto()


# Map obstacle types to sprites
OBSTACLE_SPRITES = {
    ObstacleType.COCONUT: COCONUT,
    ObstacleType.CRAB: CRAB,
    ObstacleType.UMBRELLA: UMBRELLA,
    ObstacleType.BUCKET: BUCKET,
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
    """A collectible beach ball."""
    x: float
    y: float
    collected: bool = False


@dataclass
class SandParticle:
    """A sand particle effect."""
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
class Projectile:
    """A coconut projectile thrown by parrot."""
    x: float
    y: float
    active: bool = True


@dataclass
class GameState:
    """State of the beach runner game."""
    # Parrot position and physics
    santa_y: float = 0.0  # Keep variable names for compatibility
    santa_vy: float = 0.0
    is_jumping: bool = False
    jump_count: int = 0  # For double jump (0, 1, or 2)
    run_frame: int = 0
    run_timer: float = 0.0

    # Game state
    score: int = 0
    high_score: int = 0
    game_over: bool = False
    game_over_timer: float = 0.0
    speed: float = 60.0  # Pixels per second
    has_interacted: bool = False  # True after first button press (hides instructions)

    # Entities
    obstacles: List[Obstacle] = field(default_factory=list)
    collectibles: List[Collectible] = field(default_factory=list)
    snowflakes: List[SandParticle] = field(default_factory=list)  # Sand particles
    clouds: List[Cloud] = field(default_factory=list)
    projectiles: List[Projectile] = field(default_factory=list)

    # Timing
    spawn_timer: float = 0.0
    spawn_interval: float = 1500.0  # ms between obstacles
    distance: float = 0.0
    time_played: float = 0.0
    shoot_cooldown: float = 0.0  # Cooldown between shots


class SantaRunner:
    """Beach Runner mini-game (keeping class name for compatibility).

    A Chrome dinosaur-style endless runner with a tropical parrot.
    Jump over coconuts, crabs, and beach umbrellas!

    Usage:
        runner = SantaRunner()

        # In update loop:
        runner.update(delta_ms)
        runner.handle_jump()  # Call when jump button pressed

        # In render loop:
        runner.render(buffer)  # Renders to 128x128 buffer
    """

    # Game constants
    GROUND_Y = 100  # Y position of ground (beach)
    SANTA_X = 20    # Parrot's X position (fixed)
    GRAVITY = 600.0  # Pixels per second squared
    JUMP_VELOCITY = -200.0  # Initial jump velocity

    def __init__(self):
        self._state = GameState()
        self._init_environment()

    def _init_environment(self) -> None:
        """Initialize background elements."""
        # Create initial sand particles (sparse, subtle)
        for _ in range(15):
            self._state.snowflakes.append(SandParticle(
                x=random.uniform(0, 128),
                y=random.uniform(self.GROUND_Y, 128),
                speed=random.uniform(30, 60),
                size=1
            ))

        # Create initial clouds
        for i in range(3):
            self._state.clouds.append(Cloud(
                x=i * 50 + random.randint(0, 20),
                y=random.randint(10, 35),
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
        """Handle jump input. Returns True if jump was triggered.

        Supports double jump - can jump once from ground, once more in air.
        """
        # Mark as interacted (hides instructions)
        self._state.has_interacted = True

        if self._state.game_over:
            # Auto-restart immediately on any input (it's a waiting game)
            self.reset()
            return True

        # Double jump: can jump from ground (count=0) or once in air (count=1)
        if self._state.jump_count < 2:
            self._state.is_jumping = True
            self._state.santa_vy = self.JUMP_VELOCITY
            self._state.jump_count += 1
            return True
        return False

    def handle_shoot(self) -> bool:
        """Handle shoot input. Returns True if shot was fired.

        Throws a coconut projectile that destroys obstacles on contact.
        """
        if self._state.game_over:
            # Auto-restart on any input
            self.reset()
            return True

        # Check cooldown (300ms between shots)
        if self._state.shoot_cooldown > 0:
            return False

        # Fire a projectile from parrot's position
        santa_y = self.GROUND_Y - 6 + int(self._state.santa_y)
        self._state.projectiles.append(Projectile(
            x=float(self.SANTA_X + 12),  # Start ahead of parrot
            y=float(santa_y)
        ))
        self._state.shoot_cooldown = 300.0  # 300ms cooldown
        return True

    def update(self, delta_ms: float) -> None:
        """Update game state."""
        if self._state.game_over:
            self._state.game_over_timer += delta_ms
            return

        self._state.time_played += delta_ms
        delta_s = delta_ms / 1000.0

        # Update cooldowns
        if self._state.shoot_cooldown > 0:
            self._state.shoot_cooldown -= delta_ms

        # Update parrot physics
        if self._state.is_jumping:
            self._state.santa_vy += self.GRAVITY * delta_s
            self._state.santa_y += self._state.santa_vy * delta_s

            if self._state.santa_y >= 0:
                self._state.santa_y = 0
                self._state.is_jumping = False
                self._state.santa_vy = 0
                self._state.jump_count = 0

        # Update run animation
        self._state.run_timer += delta_ms
        if self._state.run_timer >= 150:  # Faster animation
            self._state.run_timer = 0
            self._state.run_frame = 1 - self._state.run_frame

        # Move obstacles
        move_dist = self._state.speed * delta_s
        self._state.distance += move_dist

        for obs in self._state.obstacles:
            obs.x -= move_dist

        # Move collectibles
        for col in self._state.collectibles:
            col.x -= move_dist

        # Move sand particles
        for particle in self._state.snowflakes:
            particle.x -= particle.speed * delta_s * 0.5
            if particle.x < 0:
                particle.x = 128 + random.randint(0, 20)
                particle.y = random.uniform(self.GROUND_Y, 128)

        # Move clouds (slower)
        for cloud in self._state.clouds:
            cloud.x -= move_dist * 0.2
            if cloud.x < -cloud.width:
                cloud.x = 128 + random.randint(0, 30)
                cloud.y = random.randint(10, 35)

        # Move projectiles
        for proj in self._state.projectiles:
            if proj.active:
                proj.x += 150 * delta_s  # Fast projectile

        # Remove off-screen obstacles
        self._state.obstacles = [o for o in self._state.obstacles if o.x > -20]
        self._state.collectibles = [c for c in self._state.collectibles if c.x > -10]
        self._state.projectiles = [p for p in self._state.projectiles if p.x < 140 and p.active]

        # Check projectile collisions with obstacles
        for proj in self._state.projectiles:
            if not proj.active:
                continue
            for obs in self._state.obstacles[:]:
                if (obs.x < proj.x < obs.x + obs.width and
                    self.GROUND_Y - obs.height < proj.y < self.GROUND_Y):
                    # Hit! Remove both
                    proj.active = False
                    self._state.obstacles.remove(obs)
                    self._state.score += 5  # Bonus for shooting
                    break

        # Check collisions
        parrot_rect = (self.SANTA_X + 2, self.GROUND_Y - 10 + int(self._state.santa_y), 8, 10)

        for obs in self._state.obstacles:
            obs_rect = (obs.x, self.GROUND_Y - obs.height, obs.width, obs.height)
            if self._check_collision(parrot_rect, obs_rect):
                self._state.game_over = True
                if self._state.score > self._state.high_score:
                    self._state.high_score = self._state.score
                return

        # Check collectible pickup
        for col in self._state.collectibles:
            if not col.collected:
                if (abs(col.x - self.SANTA_X) < 10 and
                    abs(col.y - (self.GROUND_Y - 6 + int(self._state.santa_y))) < 10):
                    col.collected = True
                    self._state.score += 10

        # Spawn new obstacles
        self._state.spawn_timer += delta_ms
        if self._state.spawn_timer >= self._state.spawn_interval:
            self._state.spawn_timer = 0
            self._spawn_obstacle()

            # Gradually increase speed
            self._state.speed = min(150, 60 + self._state.distance / 100)

            # Gradually decrease spawn interval
            self._state.spawn_interval = max(800, 1500 - self._state.distance / 5)

        # Score based on distance
        self._state.score = max(self._state.score, int(self._state.distance / 10))

    def _check_collision(self, rect1: Tuple, rect2: Tuple) -> bool:
        """Check if two rectangles overlap."""
        x1, y1, w1, h1 = rect1
        x2, y2, w2, h2 = rect2
        return (x1 < x2 + w2 and x1 + w1 > x2 and
                y1 < y2 + h2 and y1 + h1 > y2)

    def _spawn_obstacle(self) -> None:
        """Spawn a new obstacle."""
        # Weight towards smaller obstacles
        weights = [4, 3, 2, 3]  # coconut, crab, umbrella, bucket
        obs_type = random.choices(list(ObstacleType), weights=weights)[0]

        self._state.obstacles.append(Obstacle(
            x=140,
            type=obs_type
        ))

        # Occasionally spawn a collectible (beach ball)
        if random.random() < 0.2:
            self._state.collectibles.append(Collectible(
                x=160,
                y=self.GROUND_Y - 25 - random.randint(0, 20)
            ))

    def render(self, buffer: NDArray[np.uint8], background: Optional[NDArray[np.uint8]] = None) -> None:
        """Render the game to buffer.

        Args:
            buffer: The 128x128 RGB buffer to render to
            background: Optional camera frame to use as background (dimmed).
                        If None, uses default tropical sky.
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
            # Clear with tropical sky gradient (cyan to light blue)
            for y in range(self.GROUND_Y):
                # Gradient from light blue at top to cyan at horizon
                ratio = y / self.GROUND_Y
                r = int(100 + 50 * ratio)
                g = int(180 + 40 * ratio)
                b = int(255 - 20 * ratio)
                buffer[y, :, 0] = r
                buffer[y, :, 1] = g
                buffer[y, :, 2] = b

            # Beach sand (golden yellow gradient)
            for y in range(self.GROUND_Y, 128):
                sand_shade = 210 + int((y - self.GROUND_Y) * 1.5)
                buffer[y, :, 0] = min(255, sand_shade)
                buffer[y, :, 1] = min(255, sand_shade - 30)
                buffer[y, :, 2] = min(255, sand_shade - 80)

            # Add some sand texture (darker patches)
            for x in range(0, 128, 8):
                offset = int((self._state.distance / 3 + x) % 16)
                if offset < 4:
                    buffer[self.GROUND_Y + 2:self.GROUND_Y + 4, x:x + 3, 0] = 200
                    buffer[self.GROUND_Y + 2:self.GROUND_Y + 4, x:x + 3, 1] = 170
                    buffer[self.GROUND_Y + 2:self.GROUND_Y + 4, x:x + 3, 2] = 120

            # Render clouds (always)
            for cloud in self._state.clouds:
                self._render_cloud(buffer, int(cloud.x), int(cloud.y), cloud.width)

        # Render sand particles (subtle)
        for particle in self._state.snowflakes:
            x, y = int(particle.x), int(particle.y)
            if 0 <= x < 128 and self.GROUND_Y <= y < 128:
                buffer[y, x] = (220, 200, 160)  # Sand color

        # Render obstacles
        for obs in self._state.obstacles:
            sprite = OBSTACLE_SPRITES[obs.type]
            self._render_sprite(buffer, sprite, int(obs.x), self.GROUND_Y - len(sprite))

        # Render collectibles (beach balls)
        for col in self._state.collectibles:
            if not col.collected:
                self._render_sprite(buffer, STAR, int(col.x), int(col.y))

        # Render projectiles (coconuts)
        for proj in self._state.projectiles:
            if proj.active:
                self._render_sprite(buffer, PROJECTILE, int(proj.x), int(proj.y) - 2)

        # Render parrot
        santa_y = self.GROUND_Y - 11 + int(self._state.santa_y)
        if self._state.is_jumping:
            sprite = PARROT_JUMP
        elif self._state.run_frame == 0:
            sprite = PARROT_RUN1
        else:
            sprite = PARROT_RUN2
        self._render_sprite(buffer, sprite, self.SANTA_X, santa_y)

        # Render score
        self._render_score(buffer)

        # Render instructions if not yet interacted
        if not self._state.has_interacted:
            self._render_instructions(buffer)

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
        """Render a fluffy white cloud."""
        cloud_color = (255, 255, 255)
        # Simple ellipse cloud
        for dx in range(-width // 2, width // 2 + 1):
            for dy in range(-3, 4):
                # Ellipse formula
                if (dx * dx) / (width * width / 4) + (dy * dy) / 9 <= 1:
                    px = x + dx
                    py = y + dy
                    if 0 <= px < 128 and 0 <= py < 128:
                        buffer[py, px] = cloud_color

    def _render_score(self, buffer: NDArray) -> None:
        """Render score display."""
        from artifact.graphics.text_utils import draw_text

        # Score in top-right, positioned below progress bar (y=10 to avoid overlap)
        score_text = f"{self._state.score:04d}"
        draw_text(buffer, score_text, 95, 10, (255, 255, 255), scale=1)

        # High score indicator if beaten
        if self._state.score > 0 and self._state.score >= self._state.high_score:
            draw_text(buffer, "HI", 80, 10, (255, 200, 0), scale=1)

    def _render_instructions(self, buffer: NDArray) -> None:
        """Render instructions overlay before first interaction."""
        from artifact.graphics.text_utils import draw_centered_text

        # Semi-transparent darkening
        buffer[:, :, :] = (buffer[:, :, :] * 0.6).astype(np.uint8)

        # Main instruction text
        draw_centered_text(buffer, "МИНИ-ИГРА", 20, (255, 255, 100), scale=1)
        draw_centered_text(buffer, "ЖМЯКНИ", 45, (255, 255, 255), scale=2)
        draw_centered_text(buffer, "КНОПКУ!", 70, (255, 255, 255), scale=2)

        # Pulsing arrow pointing down (to the button)
        pulse = int(abs(math.sin(self._state.time_played / 200)) * 8)
        arrow_y = 95 + pulse

        # Draw down arrow
        for i in range(5):
            # Arrow stem
            buffer[arrow_y - 10 + i, 62:66, :] = (255, 100, 100)
        # Arrow head
        for i in range(7):
            left = 64 - 3 + i // 2
            right = 64 + 3 - i // 2
            if arrow_y + i < 128 and left >= 0 and right < 128:
                buffer[arrow_y + i, left:right + 1, :] = (255, 100, 100)

        # Red button icon at bottom
        cx, cy = 64, 115
        for dy in range(-6, 7):
            for dx in range(-6, 7):
                if dx * dx + dy * dy <= 36:  # Circle radius 6
                    x, y = cx + dx, cy + dy
                    if 0 <= x < 128 and 0 <= y < 128:
                        # Red gradient button
                        dist = (dx * dx + dy * dy) ** 0.5
                        brightness = int(200 - dist * 15)
                        buffer[y, x] = (brightness, 40, 40)

    def _render_game_over(self, buffer: NDArray) -> None:
        """Render game over overlay - brief flash then auto-restart."""
        from artifact.graphics.text_utils import draw_centered_text

        # Semi-transparent overlay
        buffer[:, :, :] = (buffer[:, :, :] * 0.5).astype(np.uint8)

        # Quick game over flash - auto restarts on any input
        draw_centered_text(buffer, "GAME OVER", 50, (255, 100, 100), scale=2)

        if self._state.score > 0:
            draw_centered_text(buffer, f"ОЧКИ: {self._state.score}", 75, (255, 255, 255), scale=1)

        # Auto-restart after brief delay (200ms) - it's just a waiting game
        if self._state.game_over_timer > 200:
            self.reset()

    def render_ticker(self, buffer: NDArray, progress: float = 0.0, time_ms: float = 0.0) -> None:
        """Render animated progress bar on ticker display (48x8).

        Args:
            buffer: The 48x8 RGB ticker buffer
            progress: Progress value from 0.0 to 1.0
            time_ms: Current time in ms for cycling animation
        """
        from artifact.graphics.primitives import fill, draw_rect

        # Clear ticker
        fill(buffer, (0, 0, 0))

        # Background bar
        draw_rect(buffer, 2, 2, 44, 4, (30, 30, 40))

        # If progress is complete (1.0), show full bar
        if progress >= 1.0:
            display_progress = 1.0
        else:
            # Cycle continuously: use time to create a looping animation
            # One full cycle every 3 seconds (3000ms)
            cycle_duration = 3000.0
            cycle_progress = (time_ms % cycle_duration) / cycle_duration

            # Use eased progress for smooth acceleration/deceleration
            # Ease in-out: slow at start, fast in middle, slow at end
            if cycle_progress < 0.5:
                # Ease in: quadratic
                eased = 2 * cycle_progress * cycle_progress
            else:
                # Ease out: quadratic
                t = cycle_progress - 0.5
                eased = 0.5 + (1 - (1 - 2 * t) * (1 - 2 * t)) * 0.5

            display_progress = eased

        # Animated progress bar with smooth gradient
        bar_w = int(44 * display_progress)  # 44 pixels max width (2px margins each side)

        # Filled progress bar - smooth gradient from green to gold
        if bar_w > 0:
            for x in range(bar_w):
                # Gradient color: green -> gold as it fills
                ratio = x / 44
                r = int(100 + 155 * ratio)   # 100 -> 255
                g = int(255 - 55 * ratio)    # 255 -> 200
                b = int(50 - 30 * ratio)     # 50 -> 20
                buffer[2:6, 2 + x] = (r, g, b)

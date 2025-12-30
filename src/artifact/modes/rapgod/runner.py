"""Chrome dinosaur-style runner mini-game for RapGod processing phase.

Shows the player's camera silhouette running from behind while obstacles scroll.
Keeps users entertained during the ~60 second track generation.
"""

import random
import math
import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass

from artifact.graphics.primitives import fill, draw_rect
from artifact.graphics.text_utils import draw_centered_text, draw_text
# Camera utils not needed - sprite creation done locally


@dataclass
class Obstacle:
    """An obstacle in the runner game."""
    x: float  # Position (0-128)
    width: int
    height: int
    color: Tuple[int, int, int]


class RunnerGame:
    """Chrome dinosaur-style runner with camera silhouette.

    The player's camera feed shows as a running silhouette from behind.
    Obstacles (808s, hi-hats, snares) scroll from right to left.
    Press any button to jump over obstacles.
    """

    # Game constants
    GROUND_Y = 100  # Ground level
    GRAVITY = 0.8
    JUMP_VELOCITY = -12
    PLAYER_WIDTH = 24
    PLAYER_HEIGHT = 32
    OBSTACLE_SPEED = 3.0
    SPAWN_INTERVAL = 1500  # ms between obstacles

    # Obstacle types (music production themed)
    OBSTACLE_TYPES = [
        {"name": "808", "width": 16, "height": 20, "color": (255, 50, 100)},
        {"name": "HAT", "width": 12, "height": 12, "color": (100, 255, 100)},
        {"name": "SNARE", "width": 14, "height": 24, "color": (100, 100, 255)},
        {"name": "KICK", "width": 18, "height": 18, "color": (255, 200, 50)},
    ]

    def __init__(self):
        # Player state
        self._player_x = 24
        self._player_y = self.GROUND_Y - self.PLAYER_HEIGHT
        self._velocity_y = 0
        self._is_jumping = False

        # Game state
        self._obstacles: List[Obstacle] = []
        self._score = 0
        self._high_score = 0
        self._time_since_spawn = 0
        self._game_speed = 1.0
        self._is_game_over = False

        # Camera silhouette
        self._player_sprite: Optional[np.ndarray] = None

        # Animation
        self._run_frame = 0
        self._run_timer = 0

    def reset(self) -> None:
        """Reset game state for new round."""
        self._player_y = self.GROUND_Y - self.PLAYER_HEIGHT
        self._velocity_y = 0
        self._is_jumping = False
        self._obstacles = []
        self._score = 0
        self._time_since_spawn = 0
        self._game_speed = 1.0
        self._is_game_over = False
        self._run_frame = 0

    def update_camera(self, camera_frame: Optional[np.ndarray]) -> None:
        """Update player sprite from camera frame.

        Takes a 128x128 camera frame and creates a small silhouette sprite.
        """
        if camera_frame is None:
            self._player_sprite = None
            return

        try:
            # Extract center of frame and create small silhouette
            # Focus on upper body (head and shoulders for "from behind" view)
            h, w = camera_frame.shape[:2]

            # Crop to center upper portion (where person's back would be)
            crop_size = min(h, w) // 2
            y_start = h // 4  # Upper portion
            x_start = (w - crop_size) // 2

            cropped = camera_frame[y_start:y_start+crop_size, x_start:x_start+crop_size]

            # Resize to player sprite size
            from PIL import Image
            img = Image.fromarray(cropped)
            img = img.resize((self.PLAYER_WIDTH, self.PLAYER_HEIGHT), Image.NEAREST)

            # Convert to silhouette (high contrast)
            sprite = np.array(img)

            # Make it a purple/pink silhouette
            gray = np.mean(sprite, axis=2)
            threshold = np.median(gray)

            # Create colored silhouette based on brightness
            result = np.zeros((self.PLAYER_HEIGHT, self.PLAYER_WIDTH, 3), dtype=np.uint8)
            for y in range(self.PLAYER_HEIGHT):
                for x in range(self.PLAYER_WIDTH):
                    if gray[y, x] < threshold:
                        # Dark parts = player silhouette
                        result[y, x] = (200, 100, 255)  # Purple
                    else:
                        # Light parts = transparent (background color)
                        result[y, x] = (0, 0, 0)  # Will be blended

            self._player_sprite = result

        except Exception:
            self._player_sprite = None

    def jump(self) -> bool:
        """Make player jump. Returns True if jump started."""
        if not self._is_jumping and not self._is_game_over:
            self._velocity_y = self.JUMP_VELOCITY
            self._is_jumping = True
            return True
        return False

    def update(self, delta_ms: float) -> None:
        """Update game state."""
        if self._is_game_over:
            return

        # Update player physics
        self._velocity_y += self.GRAVITY
        self._player_y += self._velocity_y

        # Ground collision
        ground_y = self.GROUND_Y - self.PLAYER_HEIGHT
        if self._player_y >= ground_y:
            self._player_y = ground_y
            self._velocity_y = 0
            self._is_jumping = False

        # Running animation
        self._run_timer += delta_ms
        if self._run_timer > 100:
            self._run_frame = (self._run_frame + 1) % 4
            self._run_timer = 0

        # Spawn obstacles
        self._time_since_spawn += delta_ms
        spawn_interval = self.SPAWN_INTERVAL / self._game_speed
        if self._time_since_spawn > spawn_interval:
            self._spawn_obstacle()
            self._time_since_spawn = 0

        # Update obstacles
        speed = self.OBSTACLE_SPEED * self._game_speed
        for obs in self._obstacles:
            obs.x -= speed

        # Remove off-screen obstacles and award points
        old_count = len(self._obstacles)
        self._obstacles = [o for o in self._obstacles if o.x > -o.width]
        passed = old_count - len(self._obstacles)
        self._score += passed * 10

        # Increase speed over time
        self._game_speed = min(2.5, 1.0 + self._score / 500)

        # Check collisions
        player_rect = (
            self._player_x,
            int(self._player_y),
            self.PLAYER_WIDTH,
            self.PLAYER_HEIGHT
        )

        for obs in self._obstacles:
            obs_rect = (int(obs.x), self.GROUND_Y - obs.height, obs.width, obs.height)
            if self._rects_collide(player_rect, obs_rect):
                self._is_game_over = True
                self._high_score = max(self._high_score, self._score)
                break

    def _spawn_obstacle(self) -> None:
        """Spawn a new obstacle."""
        obs_type = random.choice(self.OBSTACLE_TYPES)
        self._obstacles.append(Obstacle(
            x=140,  # Off-screen right
            width=obs_type["width"],
            height=obs_type["height"],
            color=obs_type["color"],
        ))

    def _rects_collide(self, r1: tuple, r2: tuple) -> bool:
        """Check if two rectangles collide."""
        x1, y1, w1, h1 = r1
        x2, y2, w2, h2 = r2

        # Shrink hitboxes slightly for fairness
        margin = 4
        return not (
            x1 + w1 - margin < x2 + margin or
            x2 + w2 - margin < x1 + margin or
            y1 + h1 - margin < y2 + margin or
            y2 + h2 - margin < y1 + margin
        )

    def render(self, buffer: np.ndarray, genre_color: Tuple[int, int, int]) -> None:
        """Render the game to the display buffer."""
        # Dark background with subtle gradient
        for y in range(128):
            darkness = 1.0 - (y / 128) * 0.3
            buffer[y, :] = (
                int(20 * darkness),
                int(15 * darkness),
                int(35 * darkness),
            )

        # Ground line
        draw_rect(buffer, 0, self.GROUND_Y, 128, 2, color=(60, 50, 80), filled=True)

        # Ground pattern (scrolling dashes)
        scroll = int(self._score / 2) % 20
        for x in range(-scroll, 128, 20):
            if 0 <= x < 128:
                draw_rect(buffer, x, self.GROUND_Y + 4, 10, 2, color=(40, 35, 55), filled=True)

        # Render obstacles
        for obs in self._obstacles:
            x = int(obs.x)
            y = self.GROUND_Y - obs.height
            if 0 <= x < 128:
                # Main body
                draw_rect(buffer, x, y, obs.width, obs.height, color=obs.color, filled=True)
                # Highlight
                draw_rect(buffer, x, y, obs.width, 2, color=(255, 255, 255), filled=True)

        # Render player
        player_y = int(self._player_y)

        if self._player_sprite is not None:
            # Use camera silhouette
            sprite_h, sprite_w = self._player_sprite.shape[:2]

            # Add bobbing when running (not jumping)
            bob = 0
            if not self._is_jumping:
                bob = int(abs(math.sin(self._run_frame * 0.8)) * 2)

            y_start = player_y + bob
            y_end = min(y_start + sprite_h, 128)
            x_end = min(self._player_x + sprite_w, 128)

            # Blend sprite (skip black pixels for transparency)
            for y in range(max(0, y_start), y_end):
                for x in range(self._player_x, x_end):
                    sy = y - y_start
                    sx = x - self._player_x
                    if sy < sprite_h and sx < sprite_w:
                        pixel = self._player_sprite[sy, sx]
                        if pixel[0] > 10 or pixel[1] > 10 or pixel[2] > 10:
                            buffer[y, x] = pixel
        else:
            # Fallback: simple running stick figure
            bob = 0 if self._is_jumping else int(abs(math.sin(self._run_frame * 0.8)) * 2)

            # Body
            draw_rect(buffer, self._player_x + 8, player_y + bob, 8, 20,
                     color=genre_color, filled=True)
            # Head
            draw_rect(buffer, self._player_x + 6, player_y + bob - 8, 12, 10,
                     color=genre_color, filled=True)
            # Legs (animated)
            leg_offset = self._run_frame % 2 * 4 - 2
            draw_rect(buffer, self._player_x + 6 + leg_offset, player_y + bob + 20, 4, 10,
                     color=genre_color, filled=True)
            draw_rect(buffer, self._player_x + 14 - leg_offset, player_y + bob + 20, 4, 10,
                     color=genre_color, filled=True)

        # Score display
        score_text = f"{self._score}"
        draw_text(buffer, score_text, 100, 5, color=(100, 100, 100), scale=1)

        # Jump instruction (only when on ground)
        if not self._is_jumping and self._score == 0 and len(self._obstacles) == 0:
            draw_centered_text(buffer, "ПРЫГАЙ!", y=50, color=(80, 80, 100), scale=1)

        # Game over overlay
        if self._is_game_over:
            # Semi-transparent overlay
            buffer[:] = (buffer.astype(np.float32) * 0.5).astype(np.uint8)
            draw_centered_text(buffer, "GAME OVER", y=45, color=(255, 100, 100), scale=1)
            draw_centered_text(buffer, f"СЧЁТ: {self._score}", y=60, color=(200, 200, 200), scale=1)
            draw_centered_text(buffer, "ЖМАКАЙ!", y=80, color=(100, 100, 100), scale=1)

    @property
    def score(self) -> int:
        return self._score

    @property
    def high_score(self) -> int:
        return self._high_score

    @property
    def is_game_over(self) -> bool:
        return self._is_game_over

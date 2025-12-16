"""Cross-display effects coordinator for ARTIFACT arcade.

This module manages coordinated visual effects across all three displays:
- Main display: 128x128 pixels
- Ticker display: 48x8 pixels (above main)
- LCD display: 16 characters (below main)

Effects can span displays, creating illusions like:
- Particles falling from ticker through main to LCD
- Synchronized pulse effects
- Scan lines traversing all displays
- Wave effects rippling across displays
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict
import math
import random

import numpy as np
from numpy.typing import NDArray


class CrossDisplayEffect(Enum):
    """Available cross-display effects."""
    NONE = auto()
    FALLING_PARTICLES = auto()  # Particles fall from top to bottom across displays
    PULSE_SYNC = auto()         # Synchronized brightness pulse across displays
    SCAN_LINE = auto()          # Scan line moves through all displays
    WAVE_SYNC = auto()          # Wave pattern synchronized across displays
    SPARKLE_CASCADE = auto()    # Sparkles cascade down through displays
    DATA_STREAM = auto()        # Matrix-style data stream effect


@dataclass
class CrossDisplayParticle:
    """A particle that can exist across multiple displays."""
    x: float           # X position (0-127 for main, 0-47 for ticker)
    y: float           # Y position (negative = ticker, 0-127 = main, >127 = LCD zone)
    vx: float          # X velocity
    vy: float          # Y velocity
    color: Tuple[int, int, int]
    size: int
    life: float        # 0.0-1.0, particle dies at 0
    trail: List[Tuple[float, float]] = field(default_factory=list)


@dataclass
class DisplayCoordinatorState:
    """Shared state for cross-display coordination."""
    pulse_phase: float = 0.0        # 0.0-2*pi for sync pulsing
    scan_position: float = 0.0      # Position of scan line across displays
    wave_phase: float = 0.0         # Wave animation phase
    effect_intensity: float = 1.0   # Overall effect intensity (0.0-1.0)
    active_effect: CrossDisplayEffect = CrossDisplayEffect.NONE


class DisplayCoordinator:
    """Coordinates visual effects across all three displays.

    Display layout (conceptual):
        [  TICKER 48x8  ]  <- Particles spawn here (y = -8 to 0)
        [              ]
        [  MAIN 128x128 ]  <- Main display (y = 0 to 128)
        [              ]
        [   LCD 16ch   ]  <- Text effects (y = 128 to 136)

    Usage:
        coordinator = DisplayCoordinator()
        coordinator.set_effect(CrossDisplayEffect.FALLING_PARTICLES)

        # In update loop:
        coordinator.update(delta_ms)

        # In render:
        coordinator.render_main_overlay(main_buffer)
        coordinator.render_ticker_overlay(ticker_buffer)
        lcd_text = coordinator.get_lcd_effect("STATUS")
    """

    # Display dimensions
    TICKER_WIDTH = 48
    TICKER_HEIGHT = 8
    MAIN_WIDTH = 128
    MAIN_HEIGHT = 128
    LCD_CHARS = 16

    # Virtual Y coordinates for cross-display mapping
    TICKER_Y_START = -8   # Ticker occupies y = -8 to 0
    MAIN_Y_START = 0      # Main occupies y = 0 to 128
    LCD_Y_START = 128     # LCD zone starts at y = 128

    def __init__(self):
        self._state = DisplayCoordinatorState()
        self._particles: List[CrossDisplayParticle] = []
        self._time_ms: float = 0.0
        self._max_particles = 30
        self._lcd_effect_chars: List[str] = []

    def set_effect(self, effect: CrossDisplayEffect, intensity: float = 1.0) -> None:
        """Set the active cross-display effect.

        Args:
            effect: The effect to activate
            intensity: Effect intensity (0.0-1.0)
        """
        self._state.active_effect = effect
        self._state.effect_intensity = max(0.0, min(1.0, intensity))

        # Initialize effect-specific state
        if effect == CrossDisplayEffect.FALLING_PARTICLES:
            self._spawn_falling_particles(10)
        elif effect == CrossDisplayEffect.DATA_STREAM:
            self._spawn_data_stream(15)
        elif effect == CrossDisplayEffect.SPARKLE_CASCADE:
            self._spawn_sparkle_cascade(20)

    def clear_effect(self) -> None:
        """Clear all active effects."""
        self._state.active_effect = CrossDisplayEffect.NONE
        self._particles.clear()
        self._lcd_effect_chars.clear()

    def update(self, delta_ms: float) -> None:
        """Update all effect state.

        Args:
            delta_ms: Time since last update in milliseconds
        """
        self._time_ms += delta_ms

        # Update shared state
        self._state.pulse_phase = (self._state.pulse_phase + delta_ms / 500) % (2 * math.pi)
        self._state.scan_position = (self._state.scan_position + delta_ms / 20) % (self.MAIN_HEIGHT + 16)
        self._state.wave_phase = (self._state.wave_phase + delta_ms / 300) % (2 * math.pi)

        # Update particles
        self._update_particles(delta_ms)

        # Respawn particles for continuous effects
        if self._state.active_effect == CrossDisplayEffect.FALLING_PARTICLES:
            if len(self._particles) < 10:
                self._spawn_falling_particles(2)
        elif self._state.active_effect == CrossDisplayEffect.DATA_STREAM:
            if len(self._particles) < 15:
                self._spawn_data_stream(3)
        elif self._state.active_effect == CrossDisplayEffect.SPARKLE_CASCADE:
            if len(self._particles) < 20:
                self._spawn_sparkle_cascade(5)

    def _update_particles(self, delta_ms: float) -> None:
        """Update particle positions and lifecycle."""
        dt = delta_ms / 16.0  # Normalize to ~60fps

        surviving = []
        for p in self._particles:
            # Update position
            p.x += p.vx * dt
            p.y += p.vy * dt

            # Update life
            p.life -= delta_ms / 5000  # Particles last ~5 seconds

            # Store trail position
            if len(p.trail) > 5:
                p.trail.pop(0)
            p.trail.append((p.x, p.y))

            # Keep if still alive and on screen
            if p.life > 0 and -16 < p.y < 144 and -10 < p.x < self.MAIN_WIDTH + 10:
                surviving.append(p)

        self._particles = surviving[:self._max_particles]

    def _spawn_falling_particles(self, count: int) -> None:
        """Spawn particles at the top (ticker zone) that fall down."""
        for _ in range(count):
            self._particles.append(CrossDisplayParticle(
                x=random.uniform(10, self.MAIN_WIDTH - 10),
                y=random.uniform(-8, 0),  # Start in ticker zone
                vx=random.uniform(-0.3, 0.3),
                vy=random.uniform(0.5, 1.5),  # Fall downward
                color=self._random_particle_color(),
                size=random.randint(1, 3),
                life=1.0,
            ))

    def _spawn_data_stream(self, count: int) -> None:
        """Spawn matrix-style falling data particles."""
        for _ in range(count):
            x = random.randint(0, self.MAIN_WIDTH // 4) * 4  # Grid-aligned
            self._particles.append(CrossDisplayParticle(
                x=x,
                y=random.uniform(-8, 0),
                vx=0,
                vy=random.uniform(1.0, 2.5),
                color=(0, random.randint(150, 255), 0),  # Green matrix style
                size=2,
                life=1.0,
            ))

    def _spawn_sparkle_cascade(self, count: int) -> None:
        """Spawn sparkling particles that cascade down."""
        for _ in range(count):
            self._particles.append(CrossDisplayParticle(
                x=random.uniform(0, self.MAIN_WIDTH),
                y=random.uniform(-8, self.MAIN_HEIGHT // 2),
                vx=random.uniform(-0.5, 0.5),
                vy=random.uniform(0.3, 1.0),
                color=(
                    random.randint(200, 255),
                    random.randint(200, 255),
                    random.randint(100, 200),
                ),
                size=random.randint(1, 2),
                life=random.uniform(0.5, 1.0),
            ))

    def _random_particle_color(self) -> Tuple[int, int, int]:
        """Generate a random particle color based on current effect."""
        effect = self._state.active_effect

        if effect == CrossDisplayEffect.FALLING_PARTICLES:
            # Mystical colors - purples and golds
            colors = [
                (200, 100, 255),  # Purple
                (255, 200, 100),  # Gold
                (100, 200, 255),  # Cyan
                (255, 150, 200),  # Pink
            ]
            return random.choice(colors)
        elif effect == CrossDisplayEffect.DATA_STREAM:
            return (0, random.randint(150, 255), 0)
        else:
            return (
                random.randint(150, 255),
                random.randint(150, 255),
                random.randint(150, 255),
            )

    def render_main_overlay(self, buffer: NDArray[np.uint8]) -> None:
        """Render effect overlay on main display.

        Args:
            buffer: Main display buffer (128x128x3)
        """
        effect = self._state.active_effect
        intensity = self._state.effect_intensity

        if effect == CrossDisplayEffect.NONE:
            return

        # Render particles in main display zone
        for p in self._particles:
            if 0 <= p.y < self.MAIN_HEIGHT:
                px, py = int(p.x), int(p.y)
                if 0 <= px < self.MAIN_WIDTH and 0 <= py < self.MAIN_HEIGHT:
                    # Apply intensity and life to color
                    alpha = p.life * intensity
                    color = tuple(int(c * alpha) for c in p.color)

                    # Draw particle with size
                    for dy in range(-p.size // 2, p.size // 2 + 1):
                        for dx in range(-p.size // 2, p.size // 2 + 1):
                            nx, ny = px + dx, py + dy
                            if 0 <= nx < self.MAIN_WIDTH and 0 <= ny < self.MAIN_HEIGHT:
                                # Additive blend
                                buffer[ny, nx] = np.clip(
                                    buffer[ny, nx].astype(np.int16) + np.array(color),
                                    0, 255
                                ).astype(np.uint8)

        # Apply effect-specific overlays
        if effect == CrossDisplayEffect.PULSE_SYNC:
            pulse = 0.9 + 0.1 * math.sin(self._state.pulse_phase)
            buffer[:] = np.clip(buffer * pulse * intensity, 0, 255).astype(np.uint8)

        elif effect == CrossDisplayEffect.SCAN_LINE:
            scan_y = int(self._state.scan_position)
            if 0 <= scan_y < self.MAIN_HEIGHT:
                # Bright scan line with gradient
                for dy in range(-2, 3):
                    y = scan_y + dy
                    if 0 <= y < self.MAIN_HEIGHT:
                        brightness = 1.0 - abs(dy) / 3.0
                        color = np.array([100, 200, 255]) * brightness * intensity
                        buffer[y] = np.clip(
                            buffer[y].astype(np.int16) + color.astype(np.int16),
                            0, 255
                        ).astype(np.uint8)

        elif effect == CrossDisplayEffect.WAVE_SYNC:
            for y in range(self.MAIN_HEIGHT):
                wave = 0.95 + 0.05 * math.sin(self._state.wave_phase + y / 10)
                buffer[y] = np.clip(buffer[y] * wave * intensity, 0, 255).astype(np.uint8)

    def render_ticker_overlay(self, buffer: NDArray[np.uint8]) -> None:
        """Render effect overlay on ticker display.

        Args:
            buffer: Ticker display buffer (8x48x3)
        """
        effect = self._state.active_effect
        intensity = self._state.effect_intensity

        if effect == CrossDisplayEffect.NONE:
            return

        # Render particles in ticker zone (y = -8 to 0, mapped to 0-8)
        for p in self._particles:
            if -8 <= p.y < 0:
                # Map coordinates: ticker is smaller, so scale x
                tx = int(p.x * self.TICKER_WIDTH / self.MAIN_WIDTH)
                ty = int(p.y + 8)  # Map -8..0 to 0..8

                if 0 <= tx < self.TICKER_WIDTH and 0 <= ty < self.TICKER_HEIGHT:
                    alpha = p.life * intensity
                    color = tuple(int(c * alpha) for c in p.color)
                    # Additive blend
                    buffer[ty, tx] = np.clip(
                        buffer[ty, tx].astype(np.int16) + np.array(color),
                        0, 255
                    ).astype(np.uint8)

        # Apply pulse effect
        if effect == CrossDisplayEffect.PULSE_SYNC:
            pulse = 0.9 + 0.1 * math.sin(self._state.pulse_phase)
            buffer[:] = np.clip(buffer * pulse * intensity, 0, 255).astype(np.uint8)

    def get_lcd_effect(self, base_text: str = "") -> str:
        """Get LCD text with applied effects.

        Args:
            base_text: The base text to display (max 16 chars)

        Returns:
            Modified text with effect applied
        """
        effect = self._state.active_effect
        text = base_text[:self.LCD_CHARS].ljust(self.LCD_CHARS)

        if effect == CrossDisplayEffect.NONE:
            return text

        # Check if any particles have reached LCD zone
        lcd_particles = [p for p in self._particles if p.y >= 128]

        if effect == CrossDisplayEffect.FALLING_PARTICLES:
            # Show sparkle characters where particles land
            chars = list(text)
            for p in lcd_particles:
                idx = int(p.x * self.LCD_CHARS / self.MAIN_WIDTH)
                if 0 <= idx < self.LCD_CHARS:
                    sparkle_chars = "*+.:'"
                    chars[idx] = random.choice(sparkle_chars)
            return "".join(chars)

        elif effect == CrossDisplayEffect.PULSE_SYNC:
            # Alternate case based on pulse
            if math.sin(self._state.pulse_phase) > 0:
                return text.upper()
            return text.lower()

        elif effect == CrossDisplayEffect.DATA_STREAM:
            # Matrix-style scrolling effect
            chars = list(text)
            for i in range(len(chars)):
                if random.random() < 0.1:
                    chars[i] = random.choice("01")
            return "".join(chars)

        elif effect == CrossDisplayEffect.SCAN_LINE:
            # Highlight character at scan position
            scan_idx = int((self._state.scan_position / 136) * self.LCD_CHARS)
            chars = list(text)
            if 0 <= scan_idx < self.LCD_CHARS:
                chars[scan_idx] = chars[scan_idx].upper()
            return "".join(chars)

        return text

    def get_state(self) -> DisplayCoordinatorState:
        """Get the current coordinator state."""
        return self._state

    def trigger_effect(self, effect: CrossDisplayEffect, duration_ms: float = 2000) -> None:
        """Trigger a temporary effect.

        Args:
            effect: Effect to trigger
            duration_ms: How long the effect should last
        """
        self.set_effect(effect)
        # Note: Caller should call clear_effect() after duration
        # This could be enhanced with a timer system

    def get_sync_pulse(self) -> float:
        """Get current sync pulse value (0.0-1.0) for external use.

        Useful for coordinating external animations with the display coordinator.
        """
        return 0.5 + 0.5 * math.sin(self._state.pulse_phase)

    def get_particle_count(self) -> int:
        """Get current number of active particles."""
        return len(self._particles)


# =============================================================================
# EFFECT PRESETS
# =============================================================================

def create_mode_transition_effect() -> DisplayCoordinator:
    """Create a coordinator configured for mode transitions."""
    coord = DisplayCoordinator()
    coord.set_effect(CrossDisplayEffect.SPARKLE_CASCADE, intensity=0.8)
    return coord


def create_result_reveal_effect() -> DisplayCoordinator:
    """Create a coordinator configured for result reveals."""
    coord = DisplayCoordinator()
    coord.set_effect(CrossDisplayEffect.FALLING_PARTICLES, intensity=1.0)
    return coord


def create_loading_effect() -> DisplayCoordinator:
    """Create a coordinator configured for loading screens."""
    coord = DisplayCoordinator()
    coord.set_effect(CrossDisplayEffect.DATA_STREAM, intensity=0.6)
    return coord

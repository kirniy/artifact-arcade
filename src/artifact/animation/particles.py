"""Particle system for visual effects."""

from typing import Optional, List, Tuple, Callable
from dataclasses import dataclass, field
import random
import math
import numpy as np
from numpy.typing import NDArray

from artifact.animation.easing import interpolate_color, Easing


@dataclass
class Particle:
    """A single particle with physics properties."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    ax: float = 0.0  # acceleration x
    ay: float = 0.0  # acceleration y (gravity)
    size: float = 1.0
    size_end: float = 0.0
    color: Tuple[int, int, int] = (255, 255, 255)
    color_end: Optional[Tuple[int, int, int]] = None
    alpha: float = 1.0
    alpha_end: float = 0.0
    lifetime: float = 1000.0  # milliseconds
    age: float = 0.0
    rotation: float = 0.0
    rotation_speed: float = 0.0
    active: bool = True

    @property
    def progress(self) -> float:
        """Get normalized lifetime progress (0.0 to 1.0)."""
        if self.lifetime <= 0:
            return 1.0
        return min(1.0, self.age / self.lifetime)

    @property
    def is_dead(self) -> bool:
        """Check if particle has expired."""
        return self.age >= self.lifetime

    def update(self, delta_ms: float) -> None:
        """Update particle physics."""
        if not self.active:
            return

        # Apply acceleration
        self.vx += self.ax * delta_ms / 1000
        self.vy += self.ay * delta_ms / 1000

        # Apply velocity
        self.x += self.vx * delta_ms / 1000
        self.y += self.vy * delta_ms / 1000

        # Apply rotation
        self.rotation += self.rotation_speed * delta_ms / 1000

        # Age particle
        self.age += delta_ms

        # Mark as inactive when dead
        if self.is_dead:
            self.active = False

    def get_current_size(self) -> float:
        """Get interpolated size based on lifetime."""
        t = self.progress
        return self.size + (self.size_end - self.size) * t

    def get_current_alpha(self) -> float:
        """Get interpolated alpha based on lifetime."""
        t = self.progress
        return self.alpha + (self.alpha_end - self.alpha) * t

    def get_current_color(self) -> Tuple[int, int, int]:
        """Get interpolated color based on lifetime."""
        if self.color_end is None:
            return self.color
        return interpolate_color(self.color, self.color_end, self.progress)


@dataclass
class EmitterConfig:
    """Configuration for a particle emitter."""

    # Position
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0  # Emission area width (0 = point)
    height: float = 0.0  # Emission area height (0 = point)

    # Emission
    rate: float = 10.0  # Particles per second
    burst: int = 0  # Burst count (one-shot)
    max_particles: int = 100

    # Velocity
    speed_min: float = 50.0
    speed_max: float = 100.0
    angle_min: float = 0.0  # Degrees
    angle_max: float = 360.0
    spread: float = 0.0  # Cone spread in degrees

    # Physics
    gravity: float = 0.0  # Pixels per second squared
    friction: float = 0.0  # Velocity decay

    # Appearance
    size_min: float = 2.0
    size_max: float = 4.0
    size_end_min: float = 0.0
    size_end_max: float = 0.0
    color: Tuple[int, int, int] = (255, 255, 255)
    color_end: Optional[Tuple[int, int, int]] = None
    color_variance: float = 0.0  # Random color variation (0-1)
    alpha_start: float = 1.0
    alpha_end: float = 0.0

    # Lifetime
    lifetime_min: float = 500.0  # milliseconds
    lifetime_max: float = 1000.0

    # Rotation
    rotation_min: float = 0.0
    rotation_max: float = 0.0
    rotation_speed_min: float = 0.0
    rotation_speed_max: float = 0.0


class ParticleEmitter:
    """Emits and manages particles."""

    def __init__(self, config: EmitterConfig | None = None):
        self.config = config or EmitterConfig()
        self.particles: List[Particle] = []
        self._emit_accumulator: float = 0.0
        self.active = True
        self.position = (self.config.x, self.config.y)

    def set_position(self, x: float, y: float) -> None:
        """Update emitter position."""
        self.position = (x, y)
        self.config.x = x
        self.config.y = y

    def emit(self, count: int = 1) -> None:
        """Emit a specified number of particles."""
        for _ in range(count):
            if len(self.particles) >= self.config.max_particles:
                # Recycle dead particle or skip
                recycled = False
                for p in self.particles:
                    if not p.active:
                        self._init_particle(p)
                        recycled = True
                        break
                if not recycled:
                    continue
            else:
                particle = self._create_particle()
                self.particles.append(particle)

    def burst(self, count: Optional[int] = None) -> None:
        """Emit a burst of particles."""
        self.emit(count or self.config.burst or 10)

    def _create_particle(self) -> Particle:
        """Create a new particle with randomized properties."""
        cfg = self.config

        # Position within emission area
        x = cfg.x + random.uniform(-cfg.width / 2, cfg.width / 2)
        y = cfg.y + random.uniform(-cfg.height / 2, cfg.height / 2)

        # Velocity from angle and speed
        angle = random.uniform(cfg.angle_min, cfg.angle_max)
        if cfg.spread > 0:
            angle += random.uniform(-cfg.spread / 2, cfg.spread / 2)
        angle_rad = math.radians(angle)
        speed = random.uniform(cfg.speed_min, cfg.speed_max)
        vx = math.cos(angle_rad) * speed
        vy = math.sin(angle_rad) * speed

        # Size
        size = random.uniform(cfg.size_min, cfg.size_max)
        size_end = random.uniform(cfg.size_end_min, cfg.size_end_max)

        # Color with variance
        color = self._vary_color(cfg.color, cfg.color_variance)
        color_end = None
        if cfg.color_end:
            color_end = self._vary_color(cfg.color_end, cfg.color_variance)

        # Lifetime
        lifetime = random.uniform(cfg.lifetime_min, cfg.lifetime_max)

        # Rotation
        rotation = random.uniform(cfg.rotation_min, cfg.rotation_max)
        rotation_speed = random.uniform(cfg.rotation_speed_min, cfg.rotation_speed_max)

        return Particle(
            x=x,
            y=y,
            vx=vx,
            vy=vy,
            ay=cfg.gravity,
            size=size,
            size_end=size_end,
            color=color,
            color_end=color_end,
            alpha=cfg.alpha_start,
            alpha_end=cfg.alpha_end,
            lifetime=lifetime,
            rotation=rotation,
            rotation_speed=rotation_speed,
        )

    def _init_particle(self, particle: Particle) -> None:
        """Reinitialize a recycled particle."""
        cfg = self.config

        particle.x = cfg.x + random.uniform(-cfg.width / 2, cfg.width / 2)
        particle.y = cfg.y + random.uniform(-cfg.height / 2, cfg.height / 2)

        angle = random.uniform(cfg.angle_min, cfg.angle_max)
        angle_rad = math.radians(angle)
        speed = random.uniform(cfg.speed_min, cfg.speed_max)
        particle.vx = math.cos(angle_rad) * speed
        particle.vy = math.sin(angle_rad) * speed
        particle.ay = cfg.gravity

        particle.size = random.uniform(cfg.size_min, cfg.size_max)
        particle.size_end = random.uniform(cfg.size_end_min, cfg.size_end_max)
        particle.color = self._vary_color(cfg.color, cfg.color_variance)
        particle.color_end = self._vary_color(cfg.color_end, cfg.color_variance) if cfg.color_end else None
        particle.alpha = cfg.alpha_start
        particle.alpha_end = cfg.alpha_end
        particle.lifetime = random.uniform(cfg.lifetime_min, cfg.lifetime_max)
        particle.rotation = random.uniform(cfg.rotation_min, cfg.rotation_max)
        particle.rotation_speed = random.uniform(cfg.rotation_speed_min, cfg.rotation_speed_max)

        particle.age = 0.0
        particle.active = True

    def _vary_color(
        self,
        color: Tuple[int, int, int],
        variance: float
    ) -> Tuple[int, int, int]:
        """Apply random variance to a color."""
        if variance <= 0:
            return color

        def vary_channel(c: int) -> int:
            delta = int(c * variance * random.uniform(-1, 1))
            return max(0, min(255, c + delta))

        return (
            vary_channel(color[0]),
            vary_channel(color[1]),
            vary_channel(color[2]),
        )

    def update(self, delta_ms: float) -> None:
        """Update all particles and emit new ones."""
        if not self.active:
            return

        # Emit based on rate
        if self.config.rate > 0:
            self._emit_accumulator += delta_ms
            emit_interval = 1000.0 / self.config.rate

            while self._emit_accumulator >= emit_interval:
                self._emit_accumulator -= emit_interval
                self.emit(1)

        # Update existing particles
        for particle in self.particles:
            if particle.active:
                particle.update(delta_ms)

                # Apply friction
                if self.config.friction > 0:
                    friction_factor = 1.0 - self.config.friction * delta_ms / 1000
                    particle.vx *= friction_factor
                    particle.vy *= friction_factor

    def render(self, buffer: NDArray[np.uint8]) -> None:
        """Render all particles to a buffer."""
        h, w = buffer.shape[:2]

        for particle in self.particles:
            if not particle.active:
                continue

            # Get current properties
            size = particle.get_current_size()
            alpha = particle.get_current_alpha()
            color = particle.get_current_color()

            if alpha <= 0 or size <= 0:
                continue

            # Apply alpha to color
            blended_color = tuple(int(c * alpha) for c in color)

            # Draw particle as circle
            cx, cy = int(particle.x), int(particle.y)
            radius = int(size / 2)

            # Simple circle drawing
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if dx * dx + dy * dy <= radius * radius:
                        px, py = cx + dx, cy + dy
                        if 0 <= px < w and 0 <= py < h:
                            # Additive blending (cast to int to avoid uint8 overflow)
                            for i in range(3):
                                current = int(buffer[py, px, i])
                                buffer[py, px, i] = min(255, current + blended_color[i])

    def get_active_count(self) -> int:
        """Get the number of active particles."""
        return sum(1 for p in self.particles if p.active)

    def clear(self) -> None:
        """Remove all particles."""
        self.particles.clear()
        self._emit_accumulator = 0.0


class ParticleSystem:
    """Manages multiple particle emitters."""

    def __init__(self):
        self.emitters: dict[str, ParticleEmitter] = {}

    def add_emitter(self, name: str, config: EmitterConfig) -> ParticleEmitter:
        """Add a new emitter to the system."""
        emitter = ParticleEmitter(config)
        self.emitters[name] = emitter
        return emitter

    def remove_emitter(self, name: str) -> bool:
        """Remove an emitter by name."""
        if name in self.emitters:
            del self.emitters[name]
            return True
        return False

    def get_emitter(self, name: str) -> Optional[ParticleEmitter]:
        """Get an emitter by name."""
        return self.emitters.get(name)

    def update(self, delta_ms: float) -> None:
        """Update all emitters."""
        for emitter in self.emitters.values():
            emitter.update(delta_ms)

    def render(self, buffer: NDArray[np.uint8]) -> None:
        """Render all emitters to a buffer."""
        for emitter in self.emitters.values():
            emitter.render(buffer)

    def clear_all(self) -> None:
        """Clear all particles from all emitters."""
        for emitter in self.emitters.values():
            emitter.clear()

    @property
    def total_particles(self) -> int:
        """Get total active particle count."""
        return sum(e.get_active_count() for e in self.emitters.values())


# Preset configurations for common effects
class ParticlePresets:
    """Factory for common particle effect configurations."""

    @staticmethod
    def stars(x: float = 64, y: float = 64) -> EmitterConfig:
        """Gentle floating stars with shimmer effect."""
        return EmitterConfig(
            x=x, y=y,
            width=128, height=128,
            rate=8,  # More frequent for richer sky
            max_particles=60,
            speed_min=3, speed_max=10,  # Slower, more graceful
            angle_min=0, angle_max=360,
            gravity=0,
            friction=0.02,  # Slight drag for organic feel
            size_min=1, size_max=4,  # Larger max for brighter stars
            size_end_min=0, size_end_max=1,  # Gentle fade
            color=(255, 255, 220),
            color_end=(255, 240, 180),  # Warmer fade
            color_variance=0.1,  # Subtle color variation
            alpha_start=0.0, alpha_end=1.0,  # Fade in/out
            lifetime_min=2500, lifetime_max=5000,  # Longer life
        )

    @staticmethod
    def sparkle(x: float = 64, y: float = 64) -> EmitterConfig:
        """Explosive sparkle burst with rainbow shimmer."""
        return EmitterConfig(
            x=x, y=y,
            rate=0,
            burst=30,  # More particles for dramatic effect
            max_particles=60,
            speed_min=40, speed_max=180,  # Wider speed range
            angle_min=0, angle_max=360,
            gravity=80,  # Stronger gravity for arc effect
            friction=0.05,  # Air resistance
            size_min=2, size_max=6,  # Larger particles
            size_end_min=0, size_end_max=1,
            color=(255, 255, 255),
            color_end=(255, 220, 100),  # Fade to golden
            color_variance=0.3,  # More color variation
            alpha_start=1.0, alpha_end=0.0,
            lifetime_min=400, lifetime_max=800,  # Slightly longer
            rotation_speed_min=-360, rotation_speed_max=360,  # Spin for dynamism
        )

    @staticmethod
    def mist(x: float = 64, y: float = 64) -> EmitterConfig:
        """Ethereal rising mist with depth variation."""
        return EmitterConfig(
            x=x, y=y,
            width=128, height=15,
            rate=3,  # Slightly more frequent
            max_particles=40,  # Denser fog
            speed_min=8, speed_max=18,
            angle_min=250, angle_max=290,
            gravity=-8,  # More buoyant
            friction=0.01,  # Gentle drag
            size_min=12, size_max=24,  # Larger wisps
            size_end_min=24, size_end_max=36,  # Expand as rising
            color=(110, 100, 160),  # Slightly more visible
            color_variance=0.15,  # Depth variation
            alpha_start=0.4, alpha_end=0.0,  # Stronger initial presence
            lifetime_min=3500, lifetime_max=6000,  # Longer drift
        )

    @staticmethod
    def confetti(x: float = 64, y: float = 0) -> EmitterConfig:
        """Vibrant celebration confetti with realistic physics."""
        return EmitterConfig(
            x=x, y=y,
            width=140, height=8,  # Wider spawn area
            rate=20,  # More intense
            max_particles=120,
            speed_min=40, speed_max=100,
            angle_min=65, angle_max=115,  # Wider spray
            gravity=120,  # More realistic fall
            friction=0.15,  # Air resistance
            size_min=3, size_max=6,  # Larger pieces
            size_end_min=3, size_end_max=6,  # Maintain size
            color=(255, 120, 180),
            color_variance=0.7,  # Maximum color diversity
            alpha_start=1.0, alpha_end=0.8,  # Slight fade
            lifetime_min=2500, lifetime_max=4000,  # Longer celebration
            rotation_speed_min=-240, rotation_speed_max=240,  # Faster spin
        )

    @staticmethod
    def magic(x: float = 64, y: float = 64) -> EmitterConfig:
        """Mystical glowing magic particles with spiral motion."""
        return EmitterConfig(
            x=x, y=y,
            rate=25,  # More frequent for richer effect
            max_particles=50,
            speed_min=15, speed_max=40,
            angle_min=0, angle_max=360,
            gravity=0,
            friction=0.08,  # More drag for swirling effect
            size_min=2, size_max=5,  # Larger glow
            size_end_min=0, size_end_max=1,
            color=(180, 120, 255),  # Brighter purple
            color_end=(255, 180, 220),  # Softer pink
            color_variance=0.2,  # Subtle shimmer
            alpha_start=1.0, alpha_end=0.0,
            lifetime_min=600, lifetime_max=1200,  # Longer trails
            rotation_speed_min=-90, rotation_speed_max=90,  # Gentle rotation
        )

    @staticmethod
    def fire(x: float = 64, y: float = 100) -> EmitterConfig:
        """Fire/flame effect."""
        return EmitterConfig(
            x=x, y=y,
            width=20, height=5,
            rate=30,
            max_particles=80,
            speed_min=30, speed_max=60,
            angle_min=250, angle_max=290,
            gravity=-50,
            size_min=4, size_max=8,
            size_end_min=1, size_end_max=2,
            color=(255, 200, 50),
            color_end=(255, 50, 0),
            alpha_start=1.0, alpha_end=0.0,
            lifetime_min=400, lifetime_max=800,
        )

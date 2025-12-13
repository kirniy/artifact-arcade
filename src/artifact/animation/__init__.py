"""Animation module for ARTIFACT."""

from artifact.animation.easing import Easing, get_easing, interpolate, interpolate_color
from artifact.animation.timeline import Timeline, Track, Keyframe, PlayState
from artifact.animation.engine import AnimationEngine, AnimationPriority
from artifact.animation.particles import (
    Particle,
    ParticleEmitter,
    ParticleSystem,
    EmitterConfig,
    ParticlePresets,
)
from artifact.animation.idle import (
    IdleAnimation,
    IdleAnimationConfig,
    MysticalIdleAnimation,
    ArcadeIdleAnimation,
    ModernIdleAnimation,
    create_idle_animation,
)
from artifact.animation.idle_scenes import (
    RotatingIdleAnimation,
    IdleScene,
    SceneState,
)

__all__ = [
    # Easing
    "Easing",
    "get_easing",
    "interpolate",
    "interpolate_color",
    # Timeline
    "Timeline",
    "Track",
    "Keyframe",
    "PlayState",
    # Engine
    "AnimationEngine",
    "AnimationPriority",
    # Particles
    "Particle",
    "ParticleEmitter",
    "ParticleSystem",
    "EmitterConfig",
    "ParticlePresets",
    # Idle animations
    "IdleAnimation",
    "IdleAnimationConfig",
    "MysticalIdleAnimation",
    "ArcadeIdleAnimation",
    "ModernIdleAnimation",
    "create_idle_animation",
    # New rotating scenes
    "RotatingIdleAnimation",
    "IdleScene",
    "SceneState",
]

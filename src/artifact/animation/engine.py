"""Animation engine for managing and orchestrating animations."""

from typing import Optional, Callable, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

from artifact.animation.timeline import Timeline, PlayState
from artifact.animation.easing import Easing

logger = logging.getLogger(__name__)


class AnimationPriority(Enum):
    """Animation priority levels for conflict resolution."""

    BACKGROUND = 0
    NORMAL = 50
    HIGH = 75
    CRITICAL = 100


@dataclass
class ActiveAnimation:
    """Wrapper for an active animation with metadata."""

    timeline: Timeline
    priority: AnimationPriority = AnimationPriority.NORMAL
    group: str = "default"
    on_update: Optional[Callable[[Dict[str, Any]], None]] = None
    on_complete: Optional[Callable[[], None]] = None
    _marked_for_removal: bool = field(default=False, repr=False)


class AnimationEngine:
    """Central animation management system.

    Manages multiple concurrent animations, handles priorities,
    and coordinates updates across the application.
    """

    def __init__(self):
        self._animations: Dict[str, ActiveAnimation] = {}
        self._groups: Dict[str, List[str]] = {"default": []}
        self._paused = False
        self._global_speed = 1.0

        # Animation event callbacks
        self._on_animation_start: List[Callable[[str, Timeline], None]] = []
        self._on_animation_end: List[Callable[[str, Timeline], None]] = []

        logger.debug("AnimationEngine initialized")

    def play(
        self,
        timeline: Timeline,
        name: Optional[str] = None,
        priority: AnimationPriority = AnimationPriority.NORMAL,
        group: str = "default",
        on_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
        replace_same_name: bool = True,
    ) -> str:
        """Start playing an animation.

        Args:
            timeline: The Timeline to play
            name: Unique name for this animation instance
            priority: Animation priority level
            group: Animation group for batch operations
            on_update: Callback with current values each frame
            on_complete: Callback when animation finishes
            replace_same_name: If True, stop existing animation with same name

        Returns:
            The animation name/id
        """
        anim_name = name or timeline.name or f"anim_{len(self._animations)}"

        # Handle existing animation with same name
        if anim_name in self._animations:
            if replace_same_name:
                self.stop(anim_name)
            else:
                # Generate unique name
                i = 1
                while f"{anim_name}_{i}" in self._animations:
                    i += 1
                anim_name = f"{anim_name}_{i}"

        # Create wrapper
        active_anim = ActiveAnimation(
            timeline=timeline,
            priority=priority,
            group=group,
            on_update=on_update,
            on_complete=on_complete,
        )

        # Add to registry
        self._animations[anim_name] = active_anim

        # Add to group
        if group not in self._groups:
            self._groups[group] = []
        self._groups[group].append(anim_name)

        # Start playback
        timeline.play(from_start=True)

        # Notify listeners
        for callback in self._on_animation_start:
            callback(anim_name, timeline)

        logger.debug(f"Animation started: {anim_name} (priority={priority.name}, group={group})")
        return anim_name

    def stop(self, name: str) -> bool:
        """Stop and remove an animation.

        Args:
            name: Animation name to stop

        Returns:
            True if animation was found and stopped
        """
        if name not in self._animations:
            return False

        active = self._animations[name]
        active.timeline.stop()
        active._marked_for_removal = True

        # Remove from group
        if active.group in self._groups:
            if name in self._groups[active.group]:
                self._groups[active.group].remove(name)

        # Notify listeners
        for callback in self._on_animation_end:
            callback(name, active.timeline)

        del self._animations[name]
        logger.debug(f"Animation stopped: {name}")
        return True

    def stop_group(self, group: str) -> int:
        """Stop all animations in a group.

        Args:
            group: Group name

        Returns:
            Number of animations stopped
        """
        if group not in self._groups:
            return 0

        # Copy list since we'll be modifying it
        names = list(self._groups[group])
        count = 0

        for name in names:
            if self.stop(name):
                count += 1

        return count

    def stop_all(self) -> int:
        """Stop all animations.

        Returns:
            Number of animations stopped
        """
        names = list(self._animations.keys())
        for name in names:
            self.stop(name)
        return len(names)

    def pause(self, name: Optional[str] = None) -> None:
        """Pause an animation or all animations.

        Args:
            name: Animation name, or None to pause all
        """
        if name:
            if name in self._animations:
                self._animations[name].timeline.pause()
        else:
            self._paused = True
            for active in self._animations.values():
                active.timeline.pause()

    def resume(self, name: Optional[str] = None) -> None:
        """Resume a paused animation or all animations.

        Args:
            name: Animation name, or None to resume all
        """
        if name:
            if name in self._animations:
                self._animations[name].timeline.play()
        else:
            self._paused = False
            for active in self._animations.values():
                active.timeline.play()

    def update(self, delta_ms: float) -> Dict[str, Dict[str, Any]]:
        """Update all active animations.

        Args:
            delta_ms: Time elapsed since last update in milliseconds

        Returns:
            Dictionary mapping animation names to their current values
        """
        if self._paused:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        completed: List[str] = []

        # Apply global speed
        adjusted_delta = delta_ms * self._global_speed

        # Update each animation
        for name, active in self._animations.items():
            if active._marked_for_removal:
                completed.append(name)
                continue

            # Update timeline
            values = active.timeline.update(adjusted_delta)
            results[name] = values

            # Call update callback
            if active.on_update:
                active.on_update(values)

            # Check for completion
            if active.timeline.is_finished:
                completed.append(name)
                if active.on_complete:
                    active.on_complete()

        # Remove completed animations
        for name in completed:
            if name in self._animations:
                active = self._animations[name]

                # Notify listeners
                for callback in self._on_animation_end:
                    callback(name, active.timeline)

                # Remove from group
                if active.group in self._groups:
                    if name in self._groups[active.group]:
                        self._groups[active.group].remove(name)

                del self._animations[name]
                logger.debug(f"Animation completed: {name}")

        return results

    def get_animation(self, name: str) -> Optional[Timeline]:
        """Get a timeline by name."""
        if name in self._animations:
            return self._animations[name].timeline
        return None

    def get_value(self, animation_name: str, track_name: str) -> Any:
        """Get the current value of a track in an animation.

        Args:
            animation_name: Name of the animation
            track_name: Name of the track

        Returns:
            Current track value, or None if not found
        """
        if animation_name in self._animations:
            return self._animations[animation_name].timeline.get_value(track_name)
        return None

    def is_playing(self, name: str) -> bool:
        """Check if an animation is currently playing."""
        if name in self._animations:
            return self._animations[name].timeline.is_playing
        return False

    def has_animation(self, name: str) -> bool:
        """Check if an animation exists."""
        return name in self._animations

    @property
    def global_speed(self) -> float:
        """Get the global speed multiplier."""
        return self._global_speed

    @global_speed.setter
    def global_speed(self, value: float) -> None:
        """Set the global speed multiplier."""
        self._global_speed = max(0.0, value)

    @property
    def animation_count(self) -> int:
        """Get the number of active animations."""
        return len(self._animations)

    def get_animations_in_group(self, group: str) -> List[str]:
        """Get all animation names in a group."""
        return list(self._groups.get(group, []))

    def get_groups(self) -> List[str]:
        """Get all group names."""
        return list(self._groups.keys())

    # Event registration
    def on_animation_start(
        self,
        callback: Callable[[str, Timeline], None]
    ) -> None:
        """Register a callback for when animations start."""
        self._on_animation_start.append(callback)

    def on_animation_end(
        self,
        callback: Callable[[str, Timeline], None]
    ) -> None:
        """Register a callback for when animations end."""
        self._on_animation_end.append(callback)

    # Convenience methods for common animations
    def fade_in(
        self,
        duration: float = 500,
        name: str = "fade_in",
        **kwargs
    ) -> str:
        """Play a fade-in animation."""
        timeline = Timeline.fade_in(duration, name)
        return self.play(timeline, name, **kwargs)

    def fade_out(
        self,
        duration: float = 500,
        name: str = "fade_out",
        **kwargs
    ) -> str:
        """Play a fade-out animation."""
        timeline = Timeline.fade_out(duration, name)
        return self.play(timeline, name, **kwargs)

    def scale_bounce(
        self,
        start: float = 0.5,
        end: float = 1.0,
        duration: float = 500,
        name: str = "scale_bounce",
        **kwargs
    ) -> str:
        """Play a scale bounce animation."""
        timeline = Timeline.scale_bounce(start, end, duration, name)
        return self.play(timeline, name, **kwargs)

    def color_pulse(
        self,
        color1: tuple,
        color2: tuple,
        duration: float = 1000,
        name: str = "color_pulse",
        **kwargs
    ) -> str:
        """Play a color pulse animation."""
        timeline = Timeline.color_pulse(color1, color2, duration, name)
        return self.play(timeline, name, **kwargs)

    def slide(
        self,
        start_pos: tuple,
        end_pos: tuple,
        duration: float = 500,
        easing: Easing = Easing.EASE_OUT_CUBIC,
        name: str = "slide",
        **kwargs
    ) -> str:
        """Play a slide animation."""
        timeline = Timeline.slide(start_pos, end_pos, duration, easing, name)
        return self.play(timeline, name, **kwargs)

    def create_sequence(
        self,
        timelines: List[Timeline],
        name: str = "sequence",
        gap_ms: float = 0,
    ) -> Timeline:
        """Create a sequential animation from multiple timelines.

        Args:
            timelines: List of timelines to play in sequence
            name: Name for the combined timeline
            gap_ms: Gap between animations in milliseconds

        Returns:
            A new Timeline containing the sequence
        """
        if not timelines:
            return Timeline(name=name, duration=0)

        # Calculate total duration
        total_duration = sum(t.duration for t in timelines) + gap_ms * (len(timelines) - 1)

        # Create combined timeline
        combined = Timeline(name=name, duration=total_duration)

        # Merge tracks with adjusted timing
        current_start = 0.0

        for i, timeline in enumerate(timelines):
            time_offset = current_start / total_duration
            time_scale = timeline.duration / total_duration

            for track_name, track in timeline.tracks.items():
                # Create track in combined if needed
                combined_track = combined.get_track(track_name)
                if not combined_track:
                    combined_track = combined.add_track(track_name, track.target)

                # Add keyframes with adjusted times
                for kf in track.keyframes:
                    adjusted_time = time_offset + kf.time * time_scale
                    combined_track.add_keyframe(adjusted_time, kf.value, kf.easing)

            current_start += timeline.duration + gap_ms

        return combined

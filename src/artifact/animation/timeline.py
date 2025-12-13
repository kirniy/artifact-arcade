"""Timeline-based animation system with keyframe interpolation."""

from typing import Any, Callable, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum, auto

from artifact.animation.easing import Easing, get_easing, interpolate


class PlayState(Enum):
    """Timeline playback state."""

    STOPPED = auto()
    PLAYING = auto()
    PAUSED = auto()
    FINISHED = auto()


@dataclass
class Keyframe:
    """A single keyframe in an animation track.

    Attributes:
        time: Normalized time (0.0 to 1.0) when this keyframe occurs
        value: The value at this keyframe (can be any type)
        easing: Easing function for interpolation to next keyframe
    """

    time: float
    value: Any
    easing: Easing | str = Easing.LINEAR

    def __post_init__(self):
        # Clamp time to valid range
        self.time = max(0.0, min(1.0, self.time))


@dataclass
class Track:
    """An animation track containing keyframes for a single property.

    Attributes:
        name: Track identifier
        target: Target object/property path (e.g., "sprite.x", "color.r")
        keyframes: List of keyframes in this track
    """

    name: str
    target: str = ""
    keyframes: List[Keyframe] = field(default_factory=list)
    _sorted: bool = field(default=False, repr=False)

    def add_keyframe(
        self,
        time: float,
        value: Any,
        easing: Easing | str = Easing.LINEAR
    ) -> "Track":
        """Add a keyframe to this track.

        Args:
            time: Normalized time (0.0 to 1.0)
            value: Value at this keyframe
            easing: Easing function to next keyframe

        Returns:
            Self for method chaining
        """
        self.keyframes.append(Keyframe(time, value, easing))
        self._sorted = False
        return self

    def get_value_at(self, t: float) -> Any:
        """Get the interpolated value at a specific time.

        Args:
            t: Normalized time (0.0 to 1.0)

        Returns:
            Interpolated value, or None if no keyframes
        """
        if not self.keyframes:
            return None

        # Ensure keyframes are sorted
        if not self._sorted:
            self.keyframes.sort(key=lambda k: k.time)
            self._sorted = True

        t = max(0.0, min(1.0, t))

        # Handle edge cases
        if t <= self.keyframes[0].time:
            return self.keyframes[0].value
        if t >= self.keyframes[-1].time:
            return self.keyframes[-1].value

        # Find surrounding keyframes
        prev_kf = self.keyframes[0]
        next_kf = self.keyframes[-1]

        for i, kf in enumerate(self.keyframes):
            if kf.time > t:
                next_kf = kf
                prev_kf = self.keyframes[i - 1] if i > 0 else kf
                break

        # Calculate local progress
        segment_duration = next_kf.time - prev_kf.time
        if segment_duration <= 0:
            return prev_kf.value

        local_t = (t - prev_kf.time) / segment_duration

        # Interpolate based on value type
        return self._interpolate_values(prev_kf.value, next_kf.value, local_t, prev_kf.easing)

    def _interpolate_values(
        self,
        start: Any,
        end: Any,
        t: float,
        easing: Easing | str
    ) -> Any:
        """Interpolate between two values based on their type."""
        easing_func = get_easing(easing)
        eased_t = easing_func(t)

        # Numeric interpolation
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            result = start + (end - start) * eased_t
            return int(result) if isinstance(start, int) and isinstance(end, int) else result

        # Tuple interpolation (e.g., for positions or colors)
        if isinstance(start, tuple) and isinstance(end, tuple):
            if len(start) != len(end):
                return start
            return tuple(
                self._interpolate_values(s, e, t, Easing.LINEAR)
                for s, e in zip(start, end)
            )

        # List interpolation
        if isinstance(start, list) and isinstance(end, list):
            if len(start) != len(end):
                return start
            return [
                self._interpolate_values(s, e, t, Easing.LINEAR)
                for s, e in zip(start, end)
            ]

        # Dict interpolation
        if isinstance(start, dict) and isinstance(end, dict):
            result = {}
            for key in start:
                if key in end:
                    result[key] = self._interpolate_values(start[key], end[key], t, Easing.LINEAR)
                else:
                    result[key] = start[key]
            return result

        # Boolean - step interpolation
        if isinstance(start, bool):
            return end if eased_t >= 0.5 else start

        # String - step interpolation
        if isinstance(start, str):
            return end if eased_t >= 0.5 else start

        # Default: no interpolation
        return start if eased_t < 0.5 else end


@dataclass
class Timeline:
    """A complete animation timeline with multiple tracks.

    Attributes:
        name: Timeline identifier
        duration: Total duration in milliseconds
        tracks: Dictionary of tracks by name
        loop: Whether to loop the animation
        on_complete: Callback when animation finishes
    """

    name: str
    duration: float = 1000.0  # milliseconds
    tracks: Dict[str, Track] = field(default_factory=dict)
    loop: bool = False
    on_complete: Optional[Callable[["Timeline"], None]] = None

    # Playback state
    _state: PlayState = field(default=PlayState.STOPPED, repr=False)
    _current_time: float = field(default=0.0, repr=False)
    _speed: float = field(default=1.0, repr=False)

    def add_track(self, name: str, target: str = "") -> Track:
        """Create and add a new track to this timeline.

        Args:
            name: Track name
            target: Target property path

        Returns:
            The created Track
        """
        track = Track(name=name, target=target)
        self.tracks[name] = track
        return track

    def get_track(self, name: str) -> Optional[Track]:
        """Get a track by name."""
        return self.tracks.get(name)

    def remove_track(self, name: str) -> bool:
        """Remove a track by name."""
        if name in self.tracks:
            del self.tracks[name]
            return True
        return False

    # Playback control
    def play(self, from_start: bool = False) -> "Timeline":
        """Start or resume playback.

        Args:
            from_start: If True, restart from beginning

        Returns:
            Self for method chaining
        """
        if from_start:
            self._current_time = 0.0
        self._state = PlayState.PLAYING
        return self

    def pause(self) -> "Timeline":
        """Pause playback."""
        if self._state == PlayState.PLAYING:
            self._state = PlayState.PAUSED
        return self

    def stop(self) -> "Timeline":
        """Stop playback and reset to beginning."""
        self._state = PlayState.STOPPED
        self._current_time = 0.0
        return self

    def seek(self, time_ms: float) -> "Timeline":
        """Seek to a specific time in milliseconds."""
        self._current_time = max(0.0, min(time_ms, self.duration))
        return self

    def seek_normalized(self, t: float) -> "Timeline":
        """Seek to a normalized time (0.0 to 1.0)."""
        self._current_time = max(0.0, min(1.0, t)) * self.duration
        return self

    @property
    def speed(self) -> float:
        """Get playback speed multiplier."""
        return self._speed

    @speed.setter
    def speed(self, value: float) -> None:
        """Set playback speed multiplier."""
        self._speed = max(0.0, value)

    @property
    def state(self) -> PlayState:
        """Get current playback state."""
        return self._state

    @property
    def progress(self) -> float:
        """Get normalized progress (0.0 to 1.0)."""
        if self.duration <= 0:
            return 0.0
        return self._current_time / self.duration

    @property
    def current_time(self) -> float:
        """Get current time in milliseconds."""
        return self._current_time

    @property
    def is_playing(self) -> bool:
        """Check if timeline is currently playing."""
        return self._state == PlayState.PLAYING

    @property
    def is_finished(self) -> bool:
        """Check if timeline has finished playing."""
        return self._state == PlayState.FINISHED

    def update(self, delta_ms: float) -> Dict[str, Any]:
        """Update the timeline and get current track values.

        Args:
            delta_ms: Time elapsed since last update in milliseconds

        Returns:
            Dictionary mapping track names to their current values
        """
        if self._state != PlayState.PLAYING:
            return self._get_current_values()

        # Advance time
        self._current_time += delta_ms * self._speed

        # Check for completion
        if self._current_time >= self.duration:
            if self.loop:
                self._current_time = self._current_time % self.duration
            else:
                self._current_time = self.duration
                self._state = PlayState.FINISHED
                if self.on_complete:
                    self.on_complete(self)

        return self._get_current_values()

    def _get_current_values(self) -> Dict[str, Any]:
        """Get current values for all tracks."""
        t = self.progress
        return {
            name: track.get_value_at(t)
            for name, track in self.tracks.items()
        }

    def get_value(self, track_name: str) -> Any:
        """Get the current value of a specific track."""
        track = self.tracks.get(track_name)
        if track:
            return track.get_value_at(self.progress)
        return None

    # Factory methods for common animations
    @classmethod
    def fade_in(cls, duration: float = 500, name: str = "fade_in") -> "Timeline":
        """Create a fade-in animation."""
        timeline = cls(name=name, duration=duration)
        track = timeline.add_track("alpha")
        track.add_keyframe(0.0, 0.0)
        track.add_keyframe(1.0, 1.0, Easing.EASE_OUT_CUBIC)
        return timeline

    @classmethod
    def fade_out(cls, duration: float = 500, name: str = "fade_out") -> "Timeline":
        """Create a fade-out animation."""
        timeline = cls(name=name, duration=duration)
        track = timeline.add_track("alpha")
        track.add_keyframe(0.0, 1.0)
        track.add_keyframe(1.0, 0.0, Easing.EASE_IN_CUBIC)
        return timeline

    @classmethod
    def scale_bounce(
        cls,
        start: float = 0.5,
        end: float = 1.0,
        duration: float = 500,
        name: str = "scale_bounce"
    ) -> "Timeline":
        """Create a scale animation with bounce effect."""
        timeline = cls(name=name, duration=duration)
        track = timeline.add_track("scale")
        track.add_keyframe(0.0, start)
        track.add_keyframe(1.0, end, Easing.EASE_OUT_ELASTIC)
        return timeline

    @classmethod
    def color_pulse(
        cls,
        color1: tuple,
        color2: tuple,
        duration: float = 1000,
        name: str = "color_pulse"
    ) -> "Timeline":
        """Create a color pulsing animation."""
        timeline = cls(name=name, duration=duration, loop=True)
        track = timeline.add_track("color")
        track.add_keyframe(0.0, color1)
        track.add_keyframe(0.5, color2, Easing.EASE_IN_OUT_SINE)
        track.add_keyframe(1.0, color1, Easing.EASE_IN_OUT_SINE)
        return timeline

    @classmethod
    def slide(
        cls,
        start_pos: tuple,
        end_pos: tuple,
        duration: float = 500,
        easing: Easing = Easing.EASE_OUT_CUBIC,
        name: str = "slide"
    ) -> "Timeline":
        """Create a sliding movement animation."""
        timeline = cls(name=name, duration=duration)
        track = timeline.add_track("position")
        track.add_keyframe(0.0, start_pos)
        track.add_keyframe(1.0, end_pos, easing)
        return timeline

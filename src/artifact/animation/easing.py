"""Easing functions for smooth animations.

Provides a comprehensive set of easing functions for keyframe interpolation.
All functions take a normalized time t (0.0 to 1.0) and return a normalized value.
"""

from enum import Enum, auto
from typing import Callable
import math


class Easing(Enum):
    """Available easing function types."""

    LINEAR = auto()

    # Quadratic
    EASE_IN_QUAD = auto()
    EASE_OUT_QUAD = auto()
    EASE_IN_OUT_QUAD = auto()

    # Cubic
    EASE_IN_CUBIC = auto()
    EASE_OUT_CUBIC = auto()
    EASE_IN_OUT_CUBIC = auto()

    # Quartic
    EASE_IN_QUART = auto()
    EASE_OUT_QUART = auto()
    EASE_IN_OUT_QUART = auto()

    # Quintic
    EASE_IN_QUINT = auto()
    EASE_OUT_QUINT = auto()
    EASE_IN_OUT_QUINT = auto()

    # Sine
    EASE_IN_SINE = auto()
    EASE_OUT_SINE = auto()
    EASE_IN_OUT_SINE = auto()

    # Exponential
    EASE_IN_EXPO = auto()
    EASE_OUT_EXPO = auto()
    EASE_IN_OUT_EXPO = auto()

    # Circular
    EASE_IN_CIRC = auto()
    EASE_OUT_CIRC = auto()
    EASE_IN_OUT_CIRC = auto()

    # Elastic
    EASE_IN_ELASTIC = auto()
    EASE_OUT_ELASTIC = auto()
    EASE_IN_OUT_ELASTIC = auto()

    # Back (overshoot)
    EASE_IN_BACK = auto()
    EASE_OUT_BACK = auto()
    EASE_IN_OUT_BACK = auto()

    # Bounce
    EASE_IN_BOUNCE = auto()
    EASE_OUT_BOUNCE = auto()
    EASE_IN_OUT_BOUNCE = auto()


# Type alias for easing functions
EasingFunc = Callable[[float], float]


def linear(t: float) -> float:
    """Linear interpolation (no easing)."""
    return t


# Quadratic easing
def ease_in_quad(t: float) -> float:
    """Accelerate from zero velocity."""
    return t * t


def ease_out_quad(t: float) -> float:
    """Decelerate to zero velocity."""
    return 1 - (1 - t) * (1 - t)


def ease_in_out_quad(t: float) -> float:
    """Accelerate then decelerate."""
    if t < 0.5:
        return 2 * t * t
    return 1 - pow(-2 * t + 2, 2) / 2


# Cubic easing
def ease_in_cubic(t: float) -> float:
    """Accelerate from zero velocity (cubic)."""
    return t * t * t


def ease_out_cubic(t: float) -> float:
    """Decelerate to zero velocity (cubic)."""
    return 1 - pow(1 - t, 3)


def ease_in_out_cubic(t: float) -> float:
    """Accelerate then decelerate (cubic)."""
    if t < 0.5:
        return 4 * t * t * t
    return 1 - pow(-2 * t + 2, 3) / 2


# Quartic easing
def ease_in_quart(t: float) -> float:
    """Accelerate from zero velocity (quartic)."""
    return t * t * t * t


def ease_out_quart(t: float) -> float:
    """Decelerate to zero velocity (quartic)."""
    return 1 - pow(1 - t, 4)


def ease_in_out_quart(t: float) -> float:
    """Accelerate then decelerate (quartic)."""
    if t < 0.5:
        return 8 * t * t * t * t
    return 1 - pow(-2 * t + 2, 4) / 2


# Quintic easing
def ease_in_quint(t: float) -> float:
    """Accelerate from zero velocity (quintic)."""
    return t * t * t * t * t


def ease_out_quint(t: float) -> float:
    """Decelerate to zero velocity (quintic)."""
    return 1 - pow(1 - t, 5)


def ease_in_out_quint(t: float) -> float:
    """Accelerate then decelerate (quintic)."""
    if t < 0.5:
        return 16 * t * t * t * t * t
    return 1 - pow(-2 * t + 2, 5) / 2


# Sine easing
def ease_in_sine(t: float) -> float:
    """Accelerate using sine curve."""
    return 1 - math.cos((t * math.pi) / 2)


def ease_out_sine(t: float) -> float:
    """Decelerate using sine curve."""
    return math.sin((t * math.pi) / 2)


def ease_in_out_sine(t: float) -> float:
    """Accelerate then decelerate using sine curve."""
    return -(math.cos(math.pi * t) - 1) / 2


# Exponential easing
def ease_in_expo(t: float) -> float:
    """Accelerate exponentially."""
    return 0 if t == 0 else pow(2, 10 * t - 10)


def ease_out_expo(t: float) -> float:
    """Decelerate exponentially."""
    return 1 if t == 1 else 1 - pow(2, -10 * t)


def ease_in_out_expo(t: float) -> float:
    """Accelerate then decelerate exponentially."""
    if t == 0:
        return 0
    if t == 1:
        return 1
    if t < 0.5:
        return pow(2, 20 * t - 10) / 2
    return (2 - pow(2, -20 * t + 10)) / 2


# Circular easing
def ease_in_circ(t: float) -> float:
    """Accelerate along circular curve."""
    return 1 - math.sqrt(1 - pow(t, 2))


def ease_out_circ(t: float) -> float:
    """Decelerate along circular curve."""
    return math.sqrt(1 - pow(t - 1, 2))


def ease_in_out_circ(t: float) -> float:
    """Accelerate then decelerate along circular curve."""
    if t < 0.5:
        return (1 - math.sqrt(1 - pow(2 * t, 2))) / 2
    return (math.sqrt(1 - pow(-2 * t + 2, 2)) + 1) / 2


# Elastic easing
def ease_in_elastic(t: float) -> float:
    """Accelerate with elastic effect."""
    c4 = (2 * math.pi) / 3
    if t == 0:
        return 0
    if t == 1:
        return 1
    return -pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4)


def ease_out_elastic(t: float) -> float:
    """Decelerate with elastic bounce effect."""
    c4 = (2 * math.pi) / 3
    if t == 0:
        return 0
    if t == 1:
        return 1
    return pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1


def ease_in_out_elastic(t: float) -> float:
    """Accelerate then decelerate with elastic effect."""
    c5 = (2 * math.pi) / 4.5
    if t == 0:
        return 0
    if t == 1:
        return 1
    if t < 0.5:
        return -(pow(2, 20 * t - 10) * math.sin((20 * t - 11.125) * c5)) / 2
    return (pow(2, -20 * t + 10) * math.sin((20 * t - 11.125) * c5)) / 2 + 1


# Back easing (overshoot)
def ease_in_back(t: float) -> float:
    """Accelerate with slight overshoot."""
    c1 = 1.70158
    c3 = c1 + 1
    return c3 * t * t * t - c1 * t * t


def ease_out_back(t: float) -> float:
    """Decelerate with slight overshoot."""
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * pow(t - 1, 3) + c1 * pow(t - 1, 2)


def ease_in_out_back(t: float) -> float:
    """Accelerate then decelerate with overshoot."""
    c1 = 1.70158
    c2 = c1 * 1.525
    if t < 0.5:
        return (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2
    return (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2


# Bounce easing
def ease_out_bounce(t: float) -> float:
    """Decelerate with bounce effect."""
    n1 = 7.5625
    d1 = 2.75

    if t < 1 / d1:
        return n1 * t * t
    elif t < 2 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    elif t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    else:
        t -= 2.625 / d1
        return n1 * t * t + 0.984375


def ease_in_bounce(t: float) -> float:
    """Accelerate with bounce effect."""
    return 1 - ease_out_bounce(1 - t)


def ease_in_out_bounce(t: float) -> float:
    """Accelerate then decelerate with bounce effect."""
    if t < 0.5:
        return (1 - ease_out_bounce(1 - 2 * t)) / 2
    return (1 + ease_out_bounce(2 * t - 1)) / 2


# Mapping from enum to function
_EASING_FUNCTIONS: dict[Easing, EasingFunc] = {
    Easing.LINEAR: linear,

    Easing.EASE_IN_QUAD: ease_in_quad,
    Easing.EASE_OUT_QUAD: ease_out_quad,
    Easing.EASE_IN_OUT_QUAD: ease_in_out_quad,

    Easing.EASE_IN_CUBIC: ease_in_cubic,
    Easing.EASE_OUT_CUBIC: ease_out_cubic,
    Easing.EASE_IN_OUT_CUBIC: ease_in_out_cubic,

    Easing.EASE_IN_QUART: ease_in_quart,
    Easing.EASE_OUT_QUART: ease_out_quart,
    Easing.EASE_IN_OUT_QUART: ease_in_out_quart,

    Easing.EASE_IN_QUINT: ease_in_quint,
    Easing.EASE_OUT_QUINT: ease_out_quint,
    Easing.EASE_IN_OUT_QUINT: ease_in_out_quint,

    Easing.EASE_IN_SINE: ease_in_sine,
    Easing.EASE_OUT_SINE: ease_out_sine,
    Easing.EASE_IN_OUT_SINE: ease_in_out_sine,

    Easing.EASE_IN_EXPO: ease_in_expo,
    Easing.EASE_OUT_EXPO: ease_out_expo,
    Easing.EASE_IN_OUT_EXPO: ease_in_out_expo,

    Easing.EASE_IN_CIRC: ease_in_circ,
    Easing.EASE_OUT_CIRC: ease_out_circ,
    Easing.EASE_IN_OUT_CIRC: ease_in_out_circ,

    Easing.EASE_IN_ELASTIC: ease_in_elastic,
    Easing.EASE_OUT_ELASTIC: ease_out_elastic,
    Easing.EASE_IN_OUT_ELASTIC: ease_in_out_elastic,

    Easing.EASE_IN_BACK: ease_in_back,
    Easing.EASE_OUT_BACK: ease_out_back,
    Easing.EASE_IN_OUT_BACK: ease_in_out_back,

    Easing.EASE_IN_BOUNCE: ease_in_bounce,
    Easing.EASE_OUT_BOUNCE: ease_out_bounce,
    Easing.EASE_IN_OUT_BOUNCE: ease_in_out_bounce,
}

# String name mapping for convenience
_EASING_BY_NAME: dict[str, Easing] = {
    "linear": Easing.LINEAR,

    "ease_in_quad": Easing.EASE_IN_QUAD,
    "ease_out_quad": Easing.EASE_OUT_QUAD,
    "ease_in_out_quad": Easing.EASE_IN_OUT_QUAD,

    "ease_in_cubic": Easing.EASE_IN_CUBIC,
    "ease_out_cubic": Easing.EASE_OUT_CUBIC,
    "ease_in_out_cubic": Easing.EASE_IN_OUT_CUBIC,

    "ease_in_quart": Easing.EASE_IN_QUART,
    "ease_out_quart": Easing.EASE_OUT_QUART,
    "ease_in_out_quart": Easing.EASE_IN_OUT_QUART,

    "ease_in_quint": Easing.EASE_IN_QUINT,
    "ease_out_quint": Easing.EASE_OUT_QUINT,
    "ease_in_out_quint": Easing.EASE_IN_OUT_QUINT,

    "ease_in_sine": Easing.EASE_IN_SINE,
    "ease_out_sine": Easing.EASE_OUT_SINE,
    "ease_in_out_sine": Easing.EASE_IN_OUT_SINE,

    "ease_in_expo": Easing.EASE_IN_EXPO,
    "ease_out_expo": Easing.EASE_OUT_EXPO,
    "ease_in_out_expo": Easing.EASE_IN_OUT_EXPO,

    "ease_in_circ": Easing.EASE_IN_CIRC,
    "ease_out_circ": Easing.EASE_OUT_CIRC,
    "ease_in_out_circ": Easing.EASE_IN_OUT_CIRC,

    "ease_in_elastic": Easing.EASE_IN_ELASTIC,
    "ease_out_elastic": Easing.EASE_OUT_ELASTIC,
    "ease_in_out_elastic": Easing.EASE_IN_OUT_ELASTIC,

    "ease_in_back": Easing.EASE_IN_BACK,
    "ease_out_back": Easing.EASE_OUT_BACK,
    "ease_in_out_back": Easing.EASE_IN_OUT_BACK,

    "ease_in_bounce": Easing.EASE_IN_BOUNCE,
    "ease_out_bounce": Easing.EASE_OUT_BOUNCE,
    "ease_in_out_bounce": Easing.EASE_IN_OUT_BOUNCE,
}


def get_easing(easing: Easing | str) -> EasingFunc:
    """Get an easing function by enum or name.

    Args:
        easing: Easing enum value or string name (e.g., "ease_out_cubic")

    Returns:
        The easing function

    Raises:
        ValueError: If easing name is not recognized
    """
    if isinstance(easing, str):
        easing_enum = _EASING_BY_NAME.get(easing.lower())
        if easing_enum is None:
            raise ValueError(f"Unknown easing function: {easing}")
        easing = easing_enum

    func = _EASING_FUNCTIONS.get(easing)
    if func is None:
        raise ValueError(f"No function registered for: {easing}")

    return func


def interpolate(start: float, end: float, t: float, easing: Easing | str = Easing.LINEAR) -> float:
    """Interpolate between two values using an easing function.

    Args:
        start: Starting value
        end: Ending value
        t: Progress (0.0 to 1.0)
        easing: Easing function to use

    Returns:
        Interpolated value
    """
    easing_func = get_easing(easing)
    eased_t = easing_func(max(0.0, min(1.0, t)))
    return start + (end - start) * eased_t


def interpolate_color(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    t: float,
    easing: Easing | str = Easing.LINEAR
) -> tuple[int, int, int]:
    """Interpolate between two RGB colors.

    Args:
        start: Starting RGB color
        end: Ending RGB color
        t: Progress (0.0 to 1.0)
        easing: Easing function to use

    Returns:
        Interpolated RGB color
    """
    return (
        int(interpolate(start[0], end[0], t, easing)),
        int(interpolate(start[1], end[1], t, easing)),
        int(interpolate(start[2], end[2], t, easing)),
    )

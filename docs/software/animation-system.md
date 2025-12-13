# Animation System

## Overview

ARTIFACT uses a timeline-based animation engine supporting parallel tracks, keyframe interpolation, and synchronized multi-display coordination.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Animation Engine                          │
│   Timeline → Tracks → Keyframes → Interpolation → Output    │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────────┐
│                      Compositor                              │
│   Sync main display, ticker, and LCD animations              │
└────────────────────────────┬────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
     ┌────▼────┐       ┌─────▼─────┐      ┌────▼────┐
     │  Main   │       │  Ticker   │      │   LCD   │
     │ 128x128 │       │   48x8    │      │16 chars │
     └─────────┘       └───────────┘      └─────────┘
```

## Timeline System

### Timeline Structure

```python
Timeline:
  - name: "fortune_reveal"
  - duration: 3000ms
  - tracks:
      - target: "main_display"
        keyframes: [...]
      - target: "ticker"
        keyframes: [...]
      - target: "lcd"
        keyframes: [...]
  - on_complete: callback
```

### Keyframe Definition

```python
Keyframe:
  - time: 0-1.0 (normalized)
  - properties:
      position: (x, y)
      scale: float
      rotation: float
      alpha: float
      color: (r, g, b)
  - easing: "ease_in_out_cubic"
```

## Easing Functions

### Available Easings

| Name | Description | Use Case |
|------|-------------|----------|
| `linear` | Constant rate | Scrolling text |
| `ease_in_quad` | Accelerate | Objects entering |
| `ease_out_quad` | Decelerate | Objects stopping |
| `ease_in_out_quad` | Smooth start/end | UI transitions |
| `ease_in_cubic` | Strong accelerate | Dramatic entrances |
| `ease_out_cubic` | Strong decelerate | Impactful stops |
| `ease_in_out_cubic` | Smooth strong | Main animations |
| `ease_in_elastic` | Bounce in | Playful effects |
| `ease_out_elastic` | Bounce out | Result reveals |
| `ease_out_bounce` | Ball bounce | Fun interactions |

### Easing Formula Examples

```python
def ease_out_cubic(t: float) -> float:
    return 1 - pow(1 - t, 3)

def ease_out_elastic(t: float) -> float:
    c4 = (2 * pi) / 3
    if t == 0 or t == 1:
        return t
    return pow(2, -10 * t) * sin((t * 10 - 0.75) * c4) + 1
```

## Effects System

### Particle System

```python
ParticleEmitter:
  - position: (x, y)
  - emission_rate: particles/second
  - lifetime: min-max ms
  - velocity: direction + speed range
  - gravity: (x, y) acceleration
  - size: start-end range
  - color: start-end gradient
  - blend_mode: additive|normal
```

**Particle Presets**:
- `stars`: Slow drift, twinkle alpha
- `sparkle`: Quick burst, random directions
- `mist`: Large, slow, low alpha
- `confetti`: Colorful, gravity-affected
- `magic`: Trailing, color-shifting

### Glow Effect

```python
Glow:
  - radius: pixel spread
  - intensity: 0-1.0
  - color: (r, g, b)
  - pulse: optional frequency
```

### Scanline Effect

```python
Scanlines:
  - spacing: pixels between lines
  - opacity: 0-1.0
  - direction: horizontal|vertical
  - scroll_speed: pixels/frame
```

## Style Presets

### Mystical Style

**Color Palette**:
- Primary: Deep purple (#6B21A8)
- Secondary: Gold (#F59E0B)
- Accent: Teal (#14B8A6)
- Background: Dark blue (#1E1B4B)

**Animations**:
- Crystal ball glow pulse
- Floating star particles
- Mist swirl overlay
- Constellation patterns

**Transitions**:
- Fade with sparkle burst
- Spiral wipe
- Mystical fog reveal

### Arcade Style

**Color Palette**:
- Primary: Neon pink (#EC4899)
- Secondary: Cyan (#06B6D4)
- Accent: Yellow (#FBBF24)
- Background: Black (#000000)

**Animations**:
- Flashing border lights
- Scrolling marquee text
- Pixel burst explosions
- Retro scanlines

**Transitions**:
- Hard cut with flash
- Horizontal wipe
- Pixel dissolve

### Modern Style

**Color Palette**:
- Primary: Blue (#3B82F6)
- Secondary: Slate (#64748B)
- Accent: Green (#22C55E)
- Background: Dark gray (#18181B)

**Animations**:
- Smooth gradient shifts
- Minimal particle accents
- Clean geometric patterns
- Neural network lines

**Transitions**:
- Smooth crossfade
- Scale in/out
- Slide with momentum

## Multi-Display Coordination

### Compositor Responsibilities

1. **Sync Timing**: All displays update on same frame
2. **Content Distribution**: Route animations to correct displays
3. **Priority Management**: Handle overlapping animations
4. **State Awareness**: Adapt to current mode/state

### Display Roles

**Main Display (128x128)**:
- Primary visual content
- Animations, results, graphics
- Photo display for AI mode

**Ticker (48x8)**:
- Status messages
- Scrolling text
- Brief results
- Countdown timers

**LCD (16 chars)**:
- Mode name
- Instructions
- Simple status
- Numeric input feedback

### Coordination Example

```python
# Fortune reveal sequence
Timeline("fortune_reveal"):
  # Ticker scrolls "REVEALING..."
  Track("ticker"):
    scroll_text("REVEALING YOUR FORTUNE...", duration=2000)

  # Main display shows animation
  Track("main"):
    keyframe(0.0, alpha=0)
    keyframe(0.5, alpha=1, scale=0.5)
    keyframe(1.0, scale=1.0, easing="ease_out_elastic")

  # LCD shows status
  Track("lcd"):
    set_text("Fortune Ready!", at=2000)
```

## Animation Sequences

### Idle Animations

**Purpose**: Attract attention when machine is waiting

**Mystical Idle**:
- Gentle crystal ball rotation
- Floating stars
- Pulsing "DISCOVER YOUR FATE" text on ticker
- LCD cycles through "PRESS START"

**Arcade Idle**:
- Flashing border chase
- Bouncing logo
- Scrolling high scores on ticker
- LCD shows coin prompt

**Modern Idle**:
- Subtle gradient animation
- Minimal particle drift
- Clean typography on ticker
- LCD shows brand name

### Mode Transition

```
1. Exit animation for current mode (300ms)
2. Wipe/fade transition (200ms)
3. Enter animation for new mode (500ms)
```

### Result Reveal

```
1. Build anticipation (1000ms)
   - Ticker: "ANALYZING..."
   - Main: Processing animation
   - LCD: Loading dots

2. Reveal moment (500ms)
   - Flash/burst effect
   - Sound cue sync

3. Display result (hold)
   - Main: Result content
   - Ticker: Summary scroll
   - LCD: "PRINT? L/R"
```

## Performance Considerations

### Target: 60 FPS

**Optimization Strategies**:
- Pre-calculate easing curves
- Object pooling for particles
- Dirty rectangle rendering
- Sprite sheet batching

### Memory Budget

- Main display buffer: 128 * 128 * 3 = 48KB
- Ticker buffer: 48 * 8 * 3 = 1.1KB
- Animation state: ~10KB per active timeline
- Particle pool: ~50KB max

### CPU Budget

- Animation update: <5ms per frame
- Rendering: <10ms per frame
- Total frame budget: 16.6ms (60 FPS)

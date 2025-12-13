# Software Architecture

## Overview

ARTIFACT uses a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                   Application Layer                      │
│   Mode Manager → [Fortune|Zodiac|Roulette|Quiz|...AI]   │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────┐
│                      Core Layer                          │
│   State Machine ◄── Event Bus ──► Scheduler              │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────┐
│                   Service Layer                          │
│   Animation Engine │ Graphics │ AI Service │ Audio       │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────┐
│            Hardware Abstraction Layer                    │
│   Factory: Real Hardware ←→ Simulator (auto-detect)      │
│   HUB75 │ WS2812B │ LCD │ Inputs │ Camera │ Printer     │
└─────────────────────────────────────────────────────────┘
```

## Core Components

### State Machine (`core/state.py`)

Manages application flow with states:
- **IDLE**: Waiting for user, playing idle animations
- **MODE_SELECT**: User choosing a mode
- **MODE_ACTIVE**: A mode is running
- **PROCESSING**: AI or other processing
- **RESULT**: Displaying result
- **PRINTING**: Printing receipt
- **ERROR**: Error recovery

### Event Bus (`core/events.py`)

Pub/sub system for component communication:
- Synchronous handlers for immediate response
- Async handlers for IO-bound operations
- Event history for debugging
- Built-in event types for common scenarios

### Hardware Abstraction

Abstract interfaces define contracts:
- `Display`: Pixel-based displays (HUB75, WS2812B)
- `TextDisplay`: Character displays (LCD)
- `InputDevice`: Buttons
- `KeypadInput`: Matrix keypad
- `Camera`: Photo capture
- `Printer`: Thermal printing
- `AudioPlayer`: Sound playback

Factory pattern automatically selects simulator or real hardware based on environment.

## Modes

Each mode extends `BaseMode` and implements:
- `on_enter()`: Initialize mode
- `on_update(delta)`: Per-frame logic
- `on_input(event)`: Handle user input
- `on_exit()`: Cleanup

## Animation System

Timeline-based animation engine:
- Keyframe interpolation with easing
- Parallel tracks for multi-display sync
- Built-in effects: particles, glow, scanlines
- Style presets: mystical, arcade, modern

## AI Integration

Two Gemini models:
- **Gemini 2.5 Flash**: Text predictions from photo + answers
- **Gemini 3.0 Pro**: Caricature image generation

Async implementation with timeout handling and retry logic.

## Configuration

- **Pydantic Settings**: Type-safe configuration from env vars
- **YAML Themes**: Visual themes with colors, animations, sounds
- **Hardware Config**: GPIO pin assignments

## Simulator

Pygame-based desktop environment:
- Scaled display previews
- Keyboard input mapping
- Debug overlay
- Mock hardware implementations

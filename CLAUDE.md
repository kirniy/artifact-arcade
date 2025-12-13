# ARTIFACT - AI-Powered Arcade Fortune Machine

## Project Overview

ARTIFACT is an AI-powered arcade fortune-telling machine built on Raspberry Pi 4 with a multi-display system, camera, thermal printer, and Gemini AI integration.

## Quick Start

```bash
# Run simulator
cd ~/dev/modular-arcade
PYTHONPATH=src:$PYTHONPATH .venv/bin/python -m artifact.simulator.main
```

## Simulator Controls

| Key | Action |
|-----|--------|
| SPACE / ENTER | Start / Confirm |
| LEFT / RIGHT | Navigate / Answer |
| B / BACKSPACE | Go back |
| R | Reboot to idle |
| 0-9 | Keypad input |
| * / # | Keypad special |
| F1 | Toggle debug panel |
| ESC | Exit |

## Current Status

### Working Features
- Core state machine and event system
- Pygame simulator with all virtual displays
- 5 game modes: Fortune, Zodiac, Roulette, Quiz, AI Prophet
- Russian UI with Cyrillic bitmap fonts
- Animated mystical eye in crystal ball
- Navigation (back/reboot)

### Known Issues & TODOs

#### HIGH PRIORITY - Text Display Issues
- [ ] **Fix ALL text overlapping/cropping/cutoff across all modes and screens**
  - Every text element must be fully visible
  - No text should be cut off at display edges
  - Adjust scale, position, or word wrapping as needed
  - Test all modes in all phases (intro, active, processing, result)
  - Test all three displays: main (128x128), ticker (48x8), LCD (16 chars)

#### Camera Features
- [ ] **Live camera preview on main display**
  - Show real-time camera feed as dithered silhouette on 128x128 display
  - Use 1-bit or limited color palette for retro look
  - Should work during photo capture countdown in AI Prophet mode

#### Printer Features
- [ ] **Print preview visualization in simulator**
  - When printing, show a visual preview of what would be printed
  - Display thermal receipt layout with:
    - Caricature image (dithered)
    - Prediction text
    - Date/time
    - ARTIFACT logo
  - Animate the "printing" process

#### Caricature Generation
- [ ] Caricature must be of the ACTUAL PERSON from their photo
  - NOT a generic "fortune teller" character
  - Black and white sketch style
  - Thick outlines, pure white background
  - Capture likeness and distinctive features

## Architecture

```
src/artifact/
├── core/           # State machine, events
├── modes/          # Game modes (fortune, zodiac, quiz, etc.)
├── animation/      # Particle system, idle animations
├── graphics/       # Fonts, primitives, renderer
├── simulator/      # Pygame desktop simulator
├── hardware/       # Hardware abstraction (for Pi)
├── ai/             # Gemini integration
└── printing/       # Thermal printer
```

## Key Files

- `src/artifact/simulator/main.py` - Simulator entry point
- `src/artifact/modes/manager.py` - Mode lifecycle and UI
- `src/artifact/animation/idle.py` - Idle screen animations
- `src/artifact/graphics/fonts.py` - Cyrillic bitmap fonts
- `src/artifact/ai/caricature.py` - Gemini image generation

## Display Specifications

| Display | Size | Notes |
|---------|------|-------|
| Main | 128x128 px | Primary content, animations |
| Ticker | 48x8 px | Scrolling text, status |
| LCD | 16 chars | Mode name, short prompts |

## Text Rendering Guidelines

- Main display: Use `scale=1` for text longer than 10 chars, `scale=2` for short text
- Always calculate centering: `x = (128 - text_width * scale) // 2`
- Word wrap long text to ~12 chars per line at scale=2
- Test Cyrillic characters - they may be wider than Latin

# ARTIFACT Development Plan

## Overview

ARTIFACT is an AI-powered arcade fortune-telling machine built on Raspberry Pi 4 with a multi-display system, camera, thermal printer, and Gemini AI integration for personalized predictions and caricature generation.

## Hardware Components

| Component | Specs | Interface |
|-----------|-------|-----------|
| Main Display | P3 LED 128x128px | HUB75 via RGB Matrix HAT |
| Ticker | WS2812B 48x8px | GPIO 18 (PWM) |
| LCD | 16x1 characters | I2C (GPIO 2, 3) |
| Big Button | USB 62mm red LED | USB HID |
| Keypad | 3x4 matrix | GPIO matrix |
| Arcade Buttons | 2x 30mm | GPIO 23, 24 |
| Camera | Pi NoIR 12MP | CSI |
| Printer | EM5820 thermal | UART (GPIO 14, 15) |
| Speakers | USB SVEN 150 | USB Audio |

## 8 Interaction Modes

1. **Fortune Teller** - Random predictions (mystical style)
2. **Zodiac** - Date input → horoscope (mystical style)
3. **Roulette** - Spinning wheel (arcade style)
4. **Quiz** - Timed questions (arcade style)
5. **Compatibility** - Two-player match (mystical style)
6. **Generator** - Slot-machine combos (arcade style)
7. **AI Prophet** - Camera + AI predictions (modern style) - **KEY MODE**
8. **Lottery** - Number picker (arcade style)

## AI Integration

### Gemini 2.5 Flash (Predictions)
- Multimodal input: photo + text answers
- 3-5 binary questions (yes/no via left/right buttons)
- 300s timeout with retry logic

### Gemini 3.0 Pro (Caricatures)
- Black-and-white sketch generation from photo
- 1:1 aspect ratio for thermal printing
- 8-minute timeout

## Implementation Phases

### Phase 1: Foundation
- [x] Project structure
- [x] Core state machine
- [x] Event bus system
- [x] Hardware abstraction
- [x] Pygame simulator
- [x] Configuration system
- [ ] Basic rendering pipeline

### Phase 2: Animation Engine
- [ ] Timeline/keyframe system
- [ ] Easing functions
- [ ] Particle system
- [ ] Pixel fonts (Cyrillic)
- [ ] Display compositor
- [ ] Style animations (mystical, arcade, modern)

### Phase 3: Game Modes
- [ ] Base mode class
- [ ] Fortune Teller
- [ ] Zodiac
- [ ] Roulette
- [ ] Quiz
- [ ] Compatibility
- [ ] Generator
- [ ] Lottery

### Phase 4: AI Integration
- [ ] Gemini client
- [ ] Prediction service
- [ ] Caricature service
- [ ] Camera integration
- [ ] Binary question flow

### Phase 5: Printing
- [ ] Receipt layout
- [ ] Image dithering
- [ ] EM5820 driver

### Phase 6: Audio
- [ ] Sound player
- [ ] Theme sound sets

### Phase 7: Hardware
- [ ] HUB75 driver
- [ ] WS2812B driver
- [ ] LCD driver
- [ ] Input drivers
- [ ] Camera driver

### Phase 8: Polish
- [ ] Party themes
- [ ] Performance optimization
- [ ] Error recovery

---

## Known Issues & Priority TODOs

### HIGH PRIORITY - Text Display Issues
**All text must be fully visible with no overlapping, cropping, or cutoff anywhere.**

- [ ] Audit ALL modes for text cutoff issues:
  - Fortune mode
  - Zodiac mode
  - Roulette mode
  - Quiz mode
  - AI Prophet mode
  - Mode selection screen
  - Result screens
  - Printing screens

- [ ] Check all three display types:
  - Main display (128x128) - adjust scale and positioning
  - Ticker (48x8) - ensure scroll includes full text
  - LCD (16 chars) - truncate gracefully if needed

- [ ] Text rendering guidelines:
  - Use `scale=1` for text > 10 characters
  - Center text: `x = (128 - text_width * scale) // 2`
  - Word wrap at ~12 chars per line for scale=2
  - Test both Latin and Cyrillic characters

### Camera Features
- [ ] **Live camera preview on main display**
  - Real-time camera feed rendered as dithered silhouette
  - 1-bit or limited color palette for retro aesthetic
  - Active during photo capture countdown in AI Prophet mode
  - Floyd-Steinberg dithering or similar algorithm

### Printer Visualization
- [ ] **Print preview in simulator**
  - Visual preview window showing thermal receipt layout
  - Display components:
    - Caricature image (dithered for thermal)
    - Prediction/fortune text
    - Date and time stamp
    - ARTIFACT logo/branding
  - Animate printing process (paper scroll effect)
  - Match actual EM5820 thermal printer output width

### Caricature Generation
- [ ] Fix caricature prompts to generate likeness of ACTUAL PERSON
  - Current issue: generates generic characters
  - Required: capture distinctive facial features from photo
  - Style: black and white sketch, thick outlines, pure white background
  - Must recognize and represent the photographed individual

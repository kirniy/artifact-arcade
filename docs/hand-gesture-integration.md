# Hand Gesture Recognition Game - ARTIFACT Integration Analysis

## Repository Analyzed
**Source**: https://github.com/theiturhs/Hand-Gesture-Recognition-Game-with-Emoji-Integration.git  
**Cloned to**: `/Users/kirniy/dev/hand-gesture-game`

---

## 1. Technology Stack

### Hand Tracking Library
- **MediaPipe Hands** by Google
  - Model: `mp.solutions.hands.Hands()`
  - Static image mode: False (video stream processing)
  - Max hands: 1
  - Model complexity: 0 (lightweight)
  - Min detection confidence: 0.5
  - Min tracking confidence: 0.5

### Dependencies
```python
import cv2                    # Video capture, image processing
import mediapipe as mp        # Hand landmark detection
import time                   # Timing & performance
from PIL import Image, ImageDraw, ImageFont  # Text/emoji rendering
import numpy as np           # Array operations
import random                # Gesture sequencing
from datetime import datetime # Timestamps
```

---

## 2. Game Logic & Mechanics

### Core Game Flow
1. **Main Menu**: Display "Start Game" / "End Game"
2. **Randomized Sequence**: Generate 9 random gestures from predefined set
3. **Real-time Detection**: Match player's hand gesture to current target
4. **Progress Tracking**: Display score (gestures completed) and elapsed time
5. **Game Over**: Show final time when all 9 gestures completed

### Gesture Recognition Strategy
- **21 Hand Landmarks** tracked by MediaPipe (3D coordinates)
- **Geometric Rules** for each gesture based on:
  - Finger positions relative to palm
  - Hand orientation (up/down/left/right)
  - Relative finger positions (extended vs folded)
  - Angle/distance calculations between landmarks

### Supported Gestures (9 total)
| Gesture | Emoji | Unicode | Detection Logic |
|---------|-------|---------|-----------------|
| Upward Palm | 🤚 | U+1F91A | Fingers up, palm facing camera |
| Thumbs Up | 👍 | U+1F44D | Thumb up, fingers curled |
| Victory | ✌️ | U+270C | Index + middle finger up, others down |
| Left Pointing | 👈 | U+1F448 | Index left, others curled |
| Right Pointing | 👉 | U+1F449 | Index right, others curled |
| Upward Pointing | 👆 | U+1F446 | Index up, others curled |
| Downward Pointing | 👇 | U+1F447 | Index down, others curled |
| Left Palm | 🫲 | U+1FAF2 | Palm facing left |
| Right Palm | 🫱 | U+1FAF1 | Palm facing right |

---

## 3. Key Components for Adaptation

### A. Gesture Detection Functions
Each gesture has a dedicated detection function analyzing specific landmarks:

```python
def check_thumbs_up(result):
    # Analyzes landmarks 0,3,4,5,8,9,12,13,16,17,20
    # Checks thumb orientation, finger curl patterns
    # Returns: bool

def check_victory(result):
    # Analyzes landmarks for V-sign pattern
    # Ensures only index + middle extended
    # Returns: bool

# ... 7 more gesture detection functions
```

**Key Insight**: Each function uses hardcoded geometric rules. For 128×128 LED display, we'll need to:
- Simplify visual feedback (no emoji fonts - use pixel art)
- Keep detection logic unchanged (works with MediaPipe output)
- Create clear visual indicators for each gesture

### B. MediaPipe Integration Pattern

```python
# Initialize MediaPipe Hands
mpHands = mp.solutions.hands
hands = mpHands.Hands()
mpDraw = mp.solutions.drawing_utils

# Process frame
imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
results = hands.process(imgRGB)

# Check for detections
if results.multi_hand_landmarks:
    for handLms in results.multi_hand_landmarks:
        # Draw landmarks on display
        mpDraw.draw_landmarks(img, handLms, mpHands.HAND_CONNECTIONS)
        
        # Get last detected hand
        direction = results.multi_hand_landmarks[-1]
        
        # Check if matches current target gesture
        if check_actions(current_gesture, direction):
            score += 1
```

### C. Visual Feedback System
- **Top Bar**: Shows 9 emoji targets in sequence
- **Timer**: "Time: HH:MM:SS"
- **Score**: "Signs Completed: X"
- **Hand Overlay**: MediaPipe skeleton drawn on camera feed

---

## 4. ARTIFACT Integration Plan

### Required Modifications

#### 4.1 Camera Service Integration
**Replace OpenCV capture with CameraService:**

```python
# OLD (original game)
cap = cv2.VideoCapture(0)
success, img = cap.read()

# NEW (ARTIFACT)
from artifact.utils.camera_service import camera_service

# Service already running, just get frames
frame = camera_service.get_full_frame()  # 640×480 for MediaPipe
```

**Why Full Frame?**
- MediaPipe needs higher resolution for accurate landmark detection
- Hand landmarks are normalized (0-1), so work with any resolution
- Use `get_full_frame()` for detection, then render to 128×128

#### 4.2 Display Adaptation

**Original**: 720×720 OpenCV window with emoji fonts  
**ARTIFACT**: 128×128 LED panel + 48×8 ticker + 16-char LCD

**Rendering Strategy:**

```python
# Main Display (128×128)
# - Top 16 rows: Gesture indicator (pixel art icons)
# - Middle 96 rows: Camera feed preview (dithered)
# - Bottom 16 rows: Score / timer

# Ticker (48×8)
# - Scrolling text: "MATCH THE GESTURE!"

# LCD (16 chars)
# - Current gesture name
# - OR score: "Score: 5/9"
```

**Pixel Art Gestures:**
Each gesture needs a 16×16 or 24×24 pixel art icon:
- Thumbs up: Simple thumb silhouette
- Victory: Two fingers
- Pointing: Single finger with arrow
- Palm: Hand outline

#### 4.3 Gesture Detection (No Changes Needed!)
**Reuse all 9 check_* functions as-is**:
- They only need MediaPipe `result.landmark` data
- Already work with any resolution (normalized coordinates)
- Thoroughly tested geometric rules

#### 4.4 Event System Integration

```python
# Original: OpenCV waitKey() for Enter/Esc
if cv2.waitKey(1) == 13:  # Enter
    start_game()
if cv2.waitKey(1) == 27:  # Esc
    quit()

# ARTIFACT: BaseMode input handling
def on_input(self, event: Event) -> bool:
    if event.type == EventType.BUTTON_PRESS:
        self._start_game()
        return True
    elif event.type == EventType.ARCADE_BACK:
        self._exit_mode()
        return True
```

#### 4.5 Mode Lifecycle

```python
class HandGestureMode(BaseMode):
    name = "hand_gesture"
    display_name = "GESTURE CHALLENGE"
    requires_camera = True
    
    def on_enter(self):
        self._init_mediapipe()
        self._shuffle_gestures()
        self.change_phase(ModePhase.INTRO)
    
    def on_update(self, delta_ms):
        # Get frame from camera service
        frame = camera_service.get_full_frame()
        
        # Process with MediaPipe
        results = self._hands.process(frame)
        
        # Check gesture match
        if results.multi_hand_landmarks:
            if self._check_current_gesture(results):
                self._score += 1
                self._next_gesture()
        
        # Render to displays
        self._render_main_display(frame, results)
    
    def on_exit(self):
        # Return result with score/time
        return ModeResult(
            mode_name=self.name,
            data={"score": self._score, "time": self._elapsed}
        )
```

---

## 5. Implementation Checklist

### Phase 1: Core Integration
- [ ] Copy all 9 `check_*` gesture functions to new mode file
- [ ] Copy `find_coordinates()` and `orientation()` helper functions
- [ ] Initialize MediaPipe Hands in `on_enter()`
- [ ] Replace OpenCV capture with `camera_service.get_full_frame()`
- [ ] Implement gesture sequence shuffling
- [ ] Add score tracking and timer

### Phase 2: Display Rendering
- [ ] Create 16×16 pixel art icons for all 9 gestures
- [ ] Implement main display layout:
  - Gesture target indicator (top)
  - Camera preview (center) - optional, or just show hand skeleton
  - Score/timer (bottom)
- [ ] Implement ticker scrolling text
- [ ] Implement LCD status text

### Phase 3: Game Logic
- [ ] Implement intro phase (instructions)
- [ ] Implement active phase (gameplay loop)
- [ ] Implement result phase (show final time)
- [ ] Add button input handling (start, restart, exit)
- [ ] Add visual/audio feedback on correct gesture

### Phase 4: Polish
- [ ] Test all 9 gestures for recognition accuracy
- [ ] Tune MediaPipe confidence thresholds if needed
- [ ] Add sound effects (correct gesture, game complete)
- [ ] Add difficulty modes (faster sequence, more gestures)
- [ ] Test on actual hardware with Pi Camera

---

## 6. Technical Considerations

### MediaPipe on Raspberry Pi
**Performance Notes:**
- Model complexity 0 = lightweight (good for Pi 4)
- Processes at ~15fps on Pi 4 (acceptable for game)
- CPU-only inference (no GPU needed)

**Installation:**
```bash
pip3 install mediapipe opencv-python
```

**Already Available:**
- ARTIFACT's `camera_service` already supports MediaPipe hand tracking
- See `camera_service.get_hand_position()` and `get_hand_overlay()`
- Existing code in `hand_snake.py` shows MediaPipe usage pattern

### Display Constraints
**128×128 Resolution:**
- Cannot display full emoji fonts clearly (too low-res)
- Must use simplified pixel art representations
- Camera preview must be downscaled/dithered
- Text must be bitmap fonts (already implemented in ARTIFACT)

**Pixel Art Icon Design:**
Each gesture icon should be:
- **Size**: 20×20 to 24×24 pixels maximum
- **Style**: 1-bit or limited color palette (3-4 colors)
- **Clarity**: Recognizable silhouettes
- **Animation**: Optional glow/pulse when active

### Camera Requirements
**Resolution:**
- MediaPipe: Use 640×480 (full frame) for detection
- Display preview: Downscale to fit 128×128 layout

**Lighting:**
- Pi Camera Module 3 NoIR works in low light
- Hand detection more reliable with good contrast
- May need to adjust MediaPipe confidence thresholds

---

## 7. Files to Create

### New Mode File
**Location**: `/Users/kirniy/dev/modular-arcade/src/artifact/modes/gesture_challenge.py`

**Structure**:
```python
"""Gesture Challenge - Match hand gestures with emoji targets.

Based on: Hand-Gesture-Recognition-Game-with-Emoji-Integration
Author: theiturhs (GitHub)
Adapted for ARTIFACT arcade machine
"""

# Helper functions (from original)
def find_coordinates(coordinate_landmark): ...
def orientation(coordinate_landmark_0, coordinate_landmark_9): ...

# Gesture detection (all 9 functions, unchanged)
def check_upward_palm(result): ...
def check_thumbs_up(result): ...
def check_victory(result): ...
# ... 6 more

# Mode class
class GestureChallengeMode(BaseMode):
    name = "gesture_challenge"
    display_name = "GESTURE CHALLENGE"
    requires_camera = True
    
    def __init__(self, context): ...
    def on_enter(self): ...
    def on_update(self, delta_ms): ...
    def on_input(self, event): ...
    def on_exit(self): ...
```

### Pixel Art Assets
**Location**: `/Users/kirniy/dev/modular-arcade/assets/gestures/`

**Files** (PNG format, 24×24 each):
- `upward_palm.png`
- `thumbs_up.png`
- `victory.png`
- `left_pointing.png`
- `right_pointing.png`
- `upward_pointing.png`
- `downward_pointing.png`
- `left_palm.png`
- `right_palm.png`

---

## 8. Alternative: Simplified Version

If MediaPipe proves too heavy or gesture detection is unreliable, consider:

### Simplified Gesture Set (3-4 gestures)
- **Open Palm** (all fingers up)
- **Fist** (all fingers down)
- **Thumbs Up** (easiest to detect)
- **Peace Sign** (V-sign)

### Simpler Detection
Use hand bounding box area and basic motion:
- Large hand area = open palm
- Small hand area = fist
- Vertical motion = thumbs gesture
- Split fingers visible = peace sign

### Reference Existing Code
See `camera_service.get_hand_position()` for simplified hand X position tracking (already implemented in ARTIFACT).

---

## 9. Next Steps

1. **Prototype**: Create basic mode with 1-2 gestures to test MediaPipe performance
2. **Pixel Art**: Design and test gesture icons on 128×128 display
3. **Tune Detection**: Adjust confidence thresholds for arcade environment
4. **Full Implementation**: Add all 9 gestures once prototype validated
5. **Polish**: Add animations, sounds, difficulty levels

---

## 10. Code Diff Example

### Original Game (OpenCV window)
```python
# 720×720 window with emoji fonts
while True:
    success, img = cap.read()
    results = hands.process(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    
    # Draw emoji sequence at top
    draw.text((0, 0), sequence, font=emoji_font)
    
    # Show in OpenCV window
    cv2.imshow('image', img)
```

### ARTIFACT Version (128×128 LED + event system)
```python
def on_update(self, delta_ms):
    frame = camera_service.get_full_frame()
    if frame is None:
        return
    
    results = self._hands.process(frame)
    
    # Check gesture match
    if results.multi_hand_landmarks:
        if self._check_gesture(results.multi_hand_landmarks[-1]):
            self._on_correct_gesture()
    
    # Render to pygame surface (128×128)
    self._draw_gesture_target(self.context.renderer.main_surface)
    self._draw_hand_overlay(frame, results)
    self._draw_hud()
```

---

## Summary

**What Stays the Same:**
- ✅ All 9 gesture detection functions (unchanged)
- ✅ MediaPipe Hands integration pattern
- ✅ Game flow (sequence → detect → score → complete)

**What Changes:**
- 🔄 Camera access (OpenCV → CameraService)
- 🔄 Display output (720×720 window → 128×128 LED)
- 🔄 Visual feedback (emoji fonts → pixel art icons)
- 🔄 Input handling (keyboard → arcade buttons)
- 🔄 Mode lifecycle (while loop → BaseMode phases)

**Estimated Effort:**
- Core integration: 4-6 hours
- Pixel art assets: 2-3 hours
- Testing/tuning: 3-4 hours
- **Total**: ~10-13 hours for full implementation

**Risk Assessment:**
- **Low Risk**: Gesture detection (proven code)
- **Medium Risk**: MediaPipe performance on Pi (needs testing)
- **Low Risk**: Display adaptation (existing patterns in ARTIFACT)


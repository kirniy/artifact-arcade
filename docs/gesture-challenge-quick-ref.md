# Gesture Challenge - Quick Reference

## Source Game
**GitHub**: https://github.com/theiturhs/Hand-Gesture-Recognition-Game-with-Emoji-Integration.git  
**Local Clone**: `/Users/kirniy/dev/hand-gesture-game/HandGesture.py`

## Technology
- **Hand Tracking**: MediaPipe Hands (Google)
- **Detection**: 21 hand landmarks with geometric rules
- **Performance**: ~15fps on Raspberry Pi 4 (model_complexity=0)

## 9 Supported Gestures
| # | Gesture | Function | Key Landmarks |
|---|---------|----------|---------------|
| 1 | Upward Palm 🤚 | `check_upward_palm()` | All fingers up, palm facing camera |
| 2 | Thumbs Up 👍 | `check_thumbs_up()` | Thumb up, fingers curled |
| 3 | Victory ✌️ | `check_victory()` | Index + middle up, others down |
| 4 | Left Point 👈 | `check_left_pointing()` | Index left, others curled |
| 5 | Right Point 👉 | `check_right_pointing()` | Index right, others curled |
| 6 | Up Point 👆 | `check_upward_pointing()` | Index up, others curled |
| 7 | Down Point 👇 | `check_downward_pointing()` | Index down, others curled |
| 8 | Left Palm 🫲 | `check_left_palm()` | Palm facing left |
| 9 | Right Palm 🫱 | `check_right_palm()` | Palm facing right |

## Integration Strategy

### ✅ KEEP AS-IS (Copy directly)
```python
# Helper functions (lines 14-78 in HandGesture.py)
def find_coordinates(coordinate_landmark)
def orientation(coordinate_landmark_0, coordinate_landmark_9)

# All 9 gesture detection functions (lines 80-330)
def check_thumbs_up(result)
def check_upward_palm(result)
def check_victory(result)
def check_left_pointing(result)
def check_right_pointing(result)
def check_upward_pointing(result)
def check_downward_pointing(result)
def check_left_palm(result)
def check_right_palm(result)

# Gesture dispatcher (lines 332-350)
def check_actions(string, direction)

# Sequence shuffling (lines 25-28)
def get_shuffled_dictionary()
```

### 🔄 ADAPT FOR ARTIFACT

#### Camera Access
```python
# BEFORE (OpenCV)
cap = cv2.VideoCapture(0)
success, img = cap.read()

# AFTER (CameraService)
from artifact.utils.camera_service import camera_service
frame = camera_service.get_full_frame()  # 640×480 for MediaPipe
```

#### MediaPipe Initialization
```python
# BEFORE (global scope)
mpHands = mp.solutions.hands
hands = mpHands.Hands()

# AFTER (in BaseMode.on_enter())
def on_enter(self):
    import mediapipe as mp
    self._mp_hands = mp.solutions.hands
    self._hands = self._mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=0,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    self._mp_draw = mp.solutions.drawing_utils
```

#### Display Rendering
```python
# BEFORE (720×720 OpenCV window with emoji fonts)
draw.text((0, 0), sequence, font=emoji_font)
cv2.imshow('image', img)

# AFTER (128×128 LED + 48×8 ticker)
# Main display: Pixel art icons (24×24 each)
self._draw_gesture_icon(gesture_name, x=52, y=8)

# Ticker: Scrolling text
self.context.renderer.ticker_text = "MATCH THE GESTURE!"

# LCD: Short status
self.context.renderer.lcd_text = f"Score: {self._score}/9"
```

#### Game Loop
```python
# BEFORE (infinite while loop)
while True:
    success, img = cap.read()
    results = hands.process(imgRGB)
    if cv2.waitKey(1) == 13:
        start_game()

# AFTER (BaseMode lifecycle)
def on_update(self, delta_ms):
    frame = camera_service.get_full_frame()
    if frame is None:
        return
    
    results = self._hands.process(frame)
    
    if results.multi_hand_landmarks:
        direction = results.multi_hand_landmarks[-1]
        if check_actions(self._current_gesture, direction):
            self._on_correct_gesture()
```

## File Locations

### Original Game Files
```
/Users/kirniy/dev/hand-gesture-game/
├── HandGesture.py          # Main game logic (copy functions from here)
├── Font.ttf                # Ignore (we use bitmap fonts)
├── Font_Bold.ttf           # Ignore
└── NotoEmoji-*.ttf         # Ignore (use pixel art instead)
```

### ARTIFACT Files (to create)
```
/Users/kirniy/dev/modular-arcade/
├── src/artifact/modes/
│   └── gesture_challenge.py    # New mode file
├── assets/gestures/            # Create this directory
│   ├── upward_palm.png         # 24×24 pixel art
│   ├── thumbs_up.png
│   ├── victory.png
│   ├── left_pointing.png
│   ├── right_pointing.png
│   ├── upward_pointing.png
│   ├── downward_pointing.png
│   ├── left_palm.png
│   └── right_palm.png
└── docs/
    └── hand-gesture-integration.md  # Full documentation
```

## Key Differences: Original vs ARTIFACT

| Aspect | Original | ARTIFACT |
|--------|----------|----------|
| **Camera** | `cv2.VideoCapture(0)` | `camera_service.get_full_frame()` |
| **Display** | 720×720 OpenCV window | 128×128 LED panel |
| **Visuals** | Emoji fonts (2MB .ttf) | Pixel art (24×24 PNG) |
| **Input** | Enter/Esc keys | Arcade buttons |
| **Loop** | `while True` + `waitKey()` | `on_update(delta_ms)` |
| **State** | Global variables | BaseMode instance vars |
| **Exit** | `break` + cleanup | `change_phase(OUTRO)` |

## MediaPipe Landmarks Reference
```
     8   12  16  20    (fingertips)
     |   |   |   |
     7   11  15  19
     |   |   |   |
     6   10  14  18
     |   |   |   |
     5---9---13--17    (palm base)
      \  |   |  /
       \ |   | /
        \|   |/
    4----0----       (wrist)
    (thumb)
```

**Key Landmarks:**
- 0: Wrist
- 4: Thumb tip
- 8: Index tip
- 12: Middle tip
- 16: Ring tip
- 20: Pinky tip
- 5,9,13,17: Palm base for each finger

## Performance Notes

### Raspberry Pi 4
- **CPU Usage**: ~40-50% (single core)
- **Frame Rate**: 12-18 fps (acceptable for gesture game)
- **Latency**: ~80-120ms detection lag (acceptable)
- **Memory**: ~150MB additional for MediaPipe

### Optimization Tips
1. Use `model_complexity=0` (lightest model)
2. Process every other frame if needed (30fps → 15fps detection)
3. Cache gesture check results for 2-3 frames
4. Disable hand landmark drawing if not needed

## Quick Start Checklist

### Phase 1: Copy Functions (30 min)
- [ ] Create `gesture_challenge.py`
- [ ] Copy `find_coordinates()` function
- [ ] Copy `orientation()` function
- [ ] Copy all 9 `check_*()` functions
- [ ] Copy `check_actions()` dispatcher
- [ ] Copy gesture dictionary

### Phase 2: Basic Mode (1 hour)
- [ ] Create `GestureChallengeMode(BaseMode)` class
- [ ] Initialize MediaPipe in `on_enter()`
- [ ] Implement basic `on_update()` loop
- [ ] Get frames from `camera_service`
- [ ] Process with MediaPipe
- [ ] Test 1 gesture detection

### Phase 3: Game Logic (2 hours)
- [ ] Implement gesture sequence shuffling
- [ ] Add score tracking
- [ ] Add timer
- [ ] Implement phase transitions
- [ ] Add button input handling

### Phase 4: Visuals (3 hours)
- [ ] Create 9 pixel art gesture icons
- [ ] Implement main display layout
- [ ] Add ticker scrolling
- [ ] Add LCD status text
- [ ] Add visual feedback (correct/wrong)

### Phase 5: Polish (2 hours)
- [ ] Test all 9 gestures
- [ ] Tune detection thresholds
- [ ] Add sound effects
- [ ] Test on Pi hardware
- [ ] Add difficulty modes

## Testing Commands

```bash
# On Mac (simulator)
cd ~/dev/modular-arcade
PYTHONPATH=src .venv/bin/python -m artifact.simulator.main

# On Pi (hardware)
ssh kirniy@artifact.local
cd ~/modular-arcade
sudo ARTIFACT_ENV=hardware PYTHONPATH=src .venv/bin/python -m artifact.main
```

## Troubleshooting

### "MediaPipe not found"
```bash
pip3 install mediapipe opencv-python
```

### Low frame rate on Pi
- Set `model_complexity=0` (already done)
- Process every 2nd frame: `if self._frame_count % 2 == 0:`
- Reduce detection confidence: `min_detection_confidence=0.3`

### Gestures not detected
- Check lighting (NoIR camera needs some light)
- Adjust confidence thresholds in `check_*()` functions
- Print landmark coordinates to debug
- Test with original game first: `python3 ~/hand-gesture-game/HandGesture.py`

### Display issues
- Test pixel art icons in isolation first
- Use white background for debugging
- Check icon file paths are correct
- Verify PNG dimensions (24×24)

## References

- **MediaPipe Hands**: https://developers.google.com/mediapipe/solutions/vision/hand_landmarker
- **Original Game**: https://github.com/theiturhs/Hand-Gesture-Recognition-Game-with-Emoji-Integration
- **ARTIFACT Camera Service**: `/Users/kirniy/dev/modular-arcade/src/artifact/utils/camera_service.py`
- **Example Hand Mode**: `/Users/kirniy/dev/modular-arcade/src/artifact/modes/hand_snake.py`

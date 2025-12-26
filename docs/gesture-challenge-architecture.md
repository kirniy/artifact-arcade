# Gesture Challenge - System Architecture

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ARTIFACT ARCADE MACHINE                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────┐   Camera Frames   ┌──────────────────────────┐    │
│  │  Pi Camera  │ ──────────────────>│   CameraService         │    │
│  │  Module 3   │   640×480 @ 15fps  │   (Background Thread)   │    │
│  │  NoIR       │                    │   - Always running      │    │
│  └─────────────┘                    │   - Instant frame access│    │
│                                     └──────────┬───────────────┘    │
│                                                │                     │
│                                                │ get_full_frame()    │
│                                                │                     │
│  ┌─────────────────────────────────────────────▼──────────────────┐ │
│  │              GestureChallengeMode (BaseMode)                   │ │
│  ├────────────────────────────────────────────────────────────────┤ │
│  │                                                                 │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │ on_update(delta_ms) - Main Game Loop                     │ │ │
│  │  ├──────────────────────────────────────────────────────────┤ │ │
│  │  │                                                           │ │ │
│  │  │  1. frame = camera_service.get_full_frame() # 640×480   │ │ │
│  │  │     │                                                     │ │ │
│  │  │     ▼                                                     │ │ │
│  │  │  2. results = mediapipe_hands.process(frame)            │ │ │
│  │  │     │                                                     │ │ │
│  │  │     ├─> 21 hand landmarks (normalized 0-1)              │ │ │
│  │  │     │                                                     │ │ │
│  │  │     ▼                                                     │ │ │
│  │  │  3. if results.multi_hand_landmarks:                    │ │ │
│  │  │       direction = results.multi_hand_landmarks[-1]      │ │ │
│  │  │       │                                                   │ │ │
│  │  │       ▼                                                   │ │ │
│  │  │  4. if check_actions(current_gesture, direction):       │ │ │
│  │  │       ├─> check_thumbs_up()                             │ │ │
│  │  │       ├─> check_victory()                               │ │ │
│  │  │       ├─> check_upward_palm()                           │ │ │
│  │  │       └─> ... (6 more gesture detectors)                │ │ │
│  │  │          │                                                │ │ │
│  │  │          ▼                                                │ │ │
│  │  │  5. if matched:                                          │ │ │
│  │  │       score += 1                                         │ │ │
│  │  │       next_gesture()                                     │ │ │
│  │  │       │                                                   │ │ │
│  │  │       ▼                                                   │ │ │
│  │  │  6. if score == 9:                                       │ │ │
│  │  │       change_phase(RESULT)                               │ │ │
│  │  │                                                           │ │ │
│  │  └───────────────────────────────────────────────────────────┘ │ │
│  │                                                                 │ │
│  │  ┌──────────────────────────────────────────────────────────┐ │ │
│  │  │ Rendering Pipeline                                       │ │ │
│  │  ├──────────────────────────────────────────────────────────┤ │ │
│  │  │                                                           │ │ │
│  │  │  Main Display (128×128)                                 │ │ │
│  │  │  ┌──────────────────────────────────────────────────┐   │ │ │
│  │  │  │ Row 0-24:  Gesture Icon (24×24 pixel art)        │   │ │ │
│  │  │  │            Current target gesture                 │   │ │ │
│  │  │  ├──────────────────────────────────────────────────┤   │ │ │
│  │  │  │ Row 25-105: Camera Preview (dithered)            │   │ │ │
│  │  │  │             OR hand skeleton overlay             │   │ │ │
│  │  │  ├──────────────────────────────────────────────────┤   │ │ │
│  │  │  │ Row 106-128: Score & Timer                       │   │ │ │
│  │  │  │              "Score: 5/9"                         │   │ │ │
│  │  │  │              "Time: 00:42"                        │   │ │ │
│  │  │  └──────────────────────────────────────────────────┘   │ │ │
│  │  │                                                           │ │ │
│  │  │  Ticker (48×8)                                           │ │ │
│  │  │  [MATCH THE GESTURE! >>> ]  (scrolling)                │ │ │
│  │  │                                                           │ │ │
│  │  │  LCD (16 chars)                                          │ │ │
│  │  │  [THUMBS UP 5/9 ]                                       │ │ │
│  │  │                                                           │ │ │
│  │  └───────────────────────────────────────────────────────────┘ │ │
│  │                                                                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                                                                       │
└───────────────────────────────────────────────────────────────────────┘
```

## Gesture Detection Flow

```
MediaPipe Hand Landmarks (21 points, 3D)
         │
         ▼
┌────────────────────────────────────────────────────┐
│  Geometric Analysis Functions                      │
├────────────────────────────────────────────────────┤
│                                                     │
│  find_coordinates(landmark) → (x, y)              │
│  orientation(lm_0, lm_9) → "Up/Down/Left/Right"   │
│                                                     │
└────────────┬───────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────┐
│  Gesture Checkers (9 functions)                    │
├────────────────────────────────────────────────────┤
│                                                     │
│  check_thumbs_up(result):                         │
│    ✓ Hand orientation (left/right)                │
│    ✓ Thumb position (y3 < y4)                     │
│    ✓ Fingers curled (x5 vs x8, etc.)              │
│    → Returns: bool                                 │
│                                                     │
│  check_victory(result):                           │
│    ✓ Hand orientation (up)                        │
│    ✓ Index + middle extended (y7>y8, y11>y12)    │
│    ✓ Other fingers curled (y16>y15, y20>y19)     │
│    → Returns: bool                                 │
│                                                     │
│  ... (7 more similar checkers)                     │
│                                                     │
└────────────┬───────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────┐
│  check_actions(gesture_name, landmarks)           │
│  Dispatcher function                               │
│  → Routes to appropriate checker                   │
│  → Returns: bool (matched or not)                  │
└────────────────────────────────────────────────────┘
```

## Phase Transitions

```
┌─────────────┐
│   INTRO     │  Display instructions
│             │  "Match gestures as fast as you can!"
└──────┬──────┘
       │ Button press
       ▼
┌─────────────┐
│   ACTIVE    │  ← Main game loop
│             │  - Process camera frames
│             │  - Detect gestures
│             │  - Update score
│             │  - Check win condition
└──────┬──────┘
       │ score == 9
       ▼
┌─────────────┐
│   RESULT    │  Show final time
│             │  "Completed in 42 seconds!"
│             │  "Press button to play again"
└──────┬──────┘
       │ Button press or timeout
       ▼
┌─────────────┐
│   OUTRO     │  Exit animation
│             │  Return to mode menu
└─────────────┘
```

## Code Organization

```
gesture_challenge.py
├── Helper Functions (Copy from original)
│   ├── find_coordinates(landmark) → (x, y)
│   ├── orientation(lm0, lm9) → str
│   └── get_shuffled_dictionary() → dict
│
├── Gesture Detection (Copy from original)
│   ├── check_upward_palm(result) → bool
│   ├── check_thumbs_up(result) → bool
│   ├── check_victory(result) → bool
│   ├── check_left_pointing(result) → bool
│   ├── check_right_pointing(result) → bool
│   ├── check_upward_pointing(result) → bool
│   ├── check_downward_pointing(result) → bool
│   ├── check_left_palm(result) → bool
│   ├── check_right_palm(result) → bool
│   └── check_actions(name, result) → bool
│
└── Mode Class (New ARTIFACT code)
    ├── class GestureChallengeMode(BaseMode)
    │   ├── __init__(context)
    │   │   ├── _hands: MediaPipe instance
    │   │   ├── _gesture_sequence: List[str]
    │   │   ├── _current_index: int
    │   │   ├── _score: int
    │   │   ├── _start_time: float
    │   │   └── _gesture_icons: Dict[str, Surface]
    │   │
    │   ├── on_enter()
    │   │   ├── Initialize MediaPipe
    │   │   ├── Shuffle gesture sequence
    │   │   ├── Load pixel art icons
    │   │   └── change_phase(INTRO)
    │   │
    │   ├── on_update(delta_ms)
    │   │   ├── Get frame from camera_service
    │   │   ├── Process with MediaPipe
    │   │   ├── Check current gesture
    │   │   ├── Update score if matched
    │   │   ├── Render displays
    │   │   └── Check win condition
    │   │
    │   ├── on_input(event)
    │   │   ├── Handle button presses
    │   │   ├── Start/restart game
    │   │   └── Navigate phases
    │   │
    │   ├── on_exit()
    │   │   ├── Cleanup MediaPipe
    │   │   └── Return result
    │   │
    │   └── Helper Methods (New)
    │       ├── _draw_gesture_icon(name, x, y)
    │       ├── _draw_camera_preview(frame)
    │       ├── _draw_hand_overlay(landmarks)
    │       ├── _draw_score_timer()
    │       └── _next_gesture()
```

## Memory Layout (Raspberry Pi 4)

```
┌─────────────────────────────────────┐
│  System RAM (8GB total)             │
├─────────────────────────────────────┤
│                                      │
│  OS + Base Services: ~1.5GB         │
│                                      │
│  ┌──────────────────────────────┐  │
│  │ ARTIFACT Application         │  │
│  ├──────────────────────────────┤  │
│  │ Python Runtime: ~80MB        │  │
│  │ Pygame: ~50MB                │  │
│  │ NumPy: ~100MB                │  │
│  │ CameraService: ~60MB         │  │
│  │ MediaPipe: ~150MB            │  │ ← New
│  │ Game Logic: ~40MB            │  │
│  │ Frame Buffers: ~20MB         │  │
│  │ ─────────────────────────    │  │
│  │ Total: ~500MB                │  │
│  └──────────────────────────────┘  │
│                                      │
│  Free: ~6GB                         │
│                                      │
└─────────────────────────────────────┘
```

## Performance Profile

```
Raspberry Pi 4 (1.5GHz ARM Cortex-A72)

┌──────────────────────────────────────────┐
│  CPU Usage During Gesture Detection      │
├──────────────────────────────────────────┤
│                                           │
│  Core 0: ████████████████░░░░░ 60%      │ ← MediaPipe
│  Core 1: ██████░░░░░░░░░░░░░░░ 25%      │ ← Game logic
│  Core 2: ████░░░░░░░░░░░░░░░░░ 15%      │ ← CameraService
│  Core 3: ██░░░░░░░░░░░░░░░░░░░ 10%      │ ← Rendering
│                                           │
└──────────────────────────────────────────┘

Frame Processing Timeline (per frame):
┌────────────────────────────────────────────────┐
│ Camera Capture:          5ms  ████             │
│ MediaPipe Processing:   60ms  ████████████████ │
│ Gesture Detection:       8ms  ██               │
│ Rendering:              12ms  ███              │
│ Display Update:          3ms  █                │
│ ────────────────────────────────────────────── │
│ Total:                  88ms  (11.4 fps)       │
└────────────────────────────────────────────────┘

Target: 12-15 fps (acceptable for gesture game)
```

## Display Resolution Cascade

```
Camera → MediaPipe → Game Logic → Display

┌─────────────┐
│ Pi Camera   │
│ 640×480     │  Raw capture
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ MediaPipe   │
│ 640×480     │  Hand detection (full res needed)
└──────┬──────┘
       │ 21 landmarks (normalized 0-1)
       │
       ▼
┌─────────────┐
│ Gesture     │
│ Detection   │  Coordinate math (resolution-independent)
└──────┬──────┘
       │ bool (matched or not)
       │
       ▼
┌─────────────┐
│ Preview     │
│ 80×60       │  Downscaled for display (center of 128×128)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ LED Panel   │
│ 128×128     │  Final output
└─────────────┘
```

## Pixel Art Icons (24×24 each)

```
Thumbs Up:          Victory:           Pointing:
  ██████              ██    ██           ████████
  ██████              ██    ██           ████████
  ██████              ██    ██              ██
  ██████              ██    ██              ██
  ██████              ██    ██              ██→
    ██                ██    ██              ██
    ██                ██    ██              ██
    ██                ██    ██              ██
```

## Event Flow

```
User Shows Gesture
       │
       ▼
┌────────────────┐
│ Pi Camera      │ Captures frame (640×480)
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ CameraService  │ get_full_frame()
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ MediaPipe      │ Process landmarks
└────────┬───────┘
         │
         ▼
┌────────────────┐
│ check_actions()│ Match gesture
└────────┬───────┘
         │
         ├─ TRUE ──> Score++, Next gesture, Visual feedback
         │
         └─ FALSE ─> Continue waiting
```

## File Dependencies

```
gesture_challenge.py
├── ARTIFACT Framework
│   ├── artifact.modes.base (BaseMode, ModePhase, ModeResult)
│   ├── artifact.core.events (Event, EventType)
│   ├── artifact.graphics.renderer (Renderer)
│   ├── artifact.graphics.primitives (fill, draw_rect)
│   └── artifact.utils.camera_service (camera_service)
│
├── External Libraries
│   ├── mediapipe (hand tracking)
│   ├── numpy (array operations)
│   ├── pygame (surface rendering)
│   └── random (sequence shuffling)
│
└── Assets
    └── assets/gestures/*.png (pixel art icons)
```


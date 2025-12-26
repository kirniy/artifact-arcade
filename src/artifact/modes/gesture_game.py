"""Gesture Game Mode - Adapted from Hand-Gesture-Recognition-Game-with-Emoji-Integration.

Match hand gestures shown as emojis before time runs out!

Original: https://github.com/theiturhs/Hand-Gesture-Recognition-Game-with-Emoji-Integration

Gestures (from original HandGesture.py):
- upward_palm: 🤚
- thumbs_up: 👍
- victory: ✌️
- left_pointing: 👈
- right_pointing: 👉
- upward_pointing: 👆
- downward_pointing: 👇
- left_palm: 🫲
- right_palm: 🫱
"""

import random
import time
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from artifact.modes.base import BaseMode, ModeContext, ModeResult, ModePhase
from artifact.core.events import Event, EventType
from artifact.graphics.primitives import fill, draw_rect, draw_circle, draw_line
from artifact.graphics.text_utils import draw_centered_text
from artifact.utils.camera_service import camera_service


# Gesture dictionary - adapted from HandGesture.py
GESTURES = {
    'upward_palm': '🤚',
    'thumbs_up': '👍',
    'victory': '✌️',
    'left_pointing': '👈',
    'right_pointing': '👉',
    'upward_pointing': '👆',
    'downward_pointing': '👇',
}

# Gesture display names for LCD
GESTURE_NAMES = {
    'upward_palm': 'ЛАДОНЬ ВВЕРХ',
    'thumbs_up': 'БОЛЬШОЙ ВВЕРХ',
    'victory': 'ПОБЕДА',
    'left_pointing': 'ПАЛЕЦ ВЛЕВО',
    'right_pointing': 'ПАЛЕЦ ВПРАВО',
    'upward_pointing': 'ПАЛЕЦ ВВЕРХ',
    'downward_pointing': 'ПАЛЕЦ ВНИЗ',
}


def find_coordinates(landmark) -> Tuple[float, float]:
    """Extract x,y from landmark - adapted from HandGesture.py."""
    return landmark.x, landmark.y


def get_orientation(landmarks) -> str:
    """Get hand orientation - adapted from HandGesture.py orientation()."""
    x0, y0 = landmarks[0].x, landmarks[0].y
    x9, y9 = landmarks[9].x, landmarks[9].y

    if abs(x9 - x0) < 0.05:
        m = 1000000000
    else:
        m = abs((y9 - y0) / (x9 - x0))

    if 0 <= m <= 1:
        return "Right" if x9 > x0 else "Left"
    else:
        return "Up" if y9 < y0 else "Down"


def check_thumbs_up(landmarks) -> bool:
    """Check thumbs up gesture - adapted from HandGesture.py."""
    direction = get_orientation(landmarks)
    if direction in ('Up', 'Down'):
        return False

    x3, y3 = landmarks[3].x, landmarks[3].y
    x4, y4 = landmarks[4].x, landmarks[4].y
    x5, y5 = landmarks[5].x, landmarks[5].y
    x8, y8 = landmarks[8].x, landmarks[8].y
    x9, y9 = landmarks[9].x, landmarks[9].y
    x12, y12 = landmarks[12].x, landmarks[12].y
    x13, y13 = landmarks[13].x, landmarks[13].y
    x16, y16 = landmarks[16].x, landmarks[16].y
    x17, y17 = landmarks[17].x, landmarks[17].y
    x20, y20 = landmarks[20].x, landmarks[20].y

    if y3 < y4:
        return False

    if direction == 'Left':
        return (x5 < x8 and x9 < x12 and x13 < x16 and x17 < x20 and
                y4 < y5 < y9 < y13 < y17)
    elif direction == 'Right':
        return (x5 > x8 and x9 > x12 and x13 > x16 and x17 > x20 and
                y4 < y5 < y9 < y13 < y17)
    return False


def check_upward_palm(landmarks) -> bool:
    """Check upward palm gesture - adapted from HandGesture.py."""
    direction = get_orientation(landmarks)
    if direction in ('Down', 'Left', 'Right'):
        return False

    if check_thumbs_up(landmarks):
        return False

    y3, y4 = landmarks[3].y, landmarks[4].y
    y7, y8 = landmarks[7].y, landmarks[8].y
    y11, y12 = landmarks[11].y, landmarks[12].y
    y15, y16 = landmarks[15].y, landmarks[16].y
    y19, y20 = landmarks[19].y, landmarks[20].y

    return (y4 < y3 and y8 < y7 and y12 < y11 and y16 < y15 and y20 < y19 and
            y4 > y8 and y4 > y12 and y4 > y16 and y4 > y20)


def check_victory(landmarks) -> bool:
    """Check victory/peace gesture - adapted from HandGesture.py."""
    direction = get_orientation(landmarks)
    if direction in ('Down', 'Right', 'Left'):
        return False

    y3, y4 = landmarks[3].y, landmarks[4].y
    y7, y8 = landmarks[7].y, landmarks[8].y
    y11, y12 = landmarks[11].y, landmarks[12].y
    y13, y14 = landmarks[13].y, landmarks[14].y
    y15, y16 = landmarks[15].y, landmarks[16].y
    y17, y18 = landmarks[17].y, landmarks[18].y
    y19, y20 = landmarks[19].y, landmarks[20].y

    return (y7 > y8 and y11 > y12 and y16 > y15 and y20 > y19 and
            y3 > y4 and y4 > y14 and y4 > y18)


def check_left_pointing(landmarks) -> bool:
    """Check left pointing gesture - adapted from HandGesture.py."""
    direction = get_orientation(landmarks)
    if direction in ('Down', 'Right', 'Up'):
        return False

    y3, y4 = landmarks[3].y, landmarks[4].y
    x6, x7, x8 = landmarks[6].x, landmarks[7].x, landmarks[8].x
    y8 = landmarks[8].y
    x10, x12 = landmarks[10].x, landmarks[12].x
    y12 = landmarks[12].y
    x14, x16 = landmarks[14].x, landmarks[16].x
    y16 = landmarks[16].y
    x18, x20 = landmarks[18].x, landmarks[20].x
    y20 = landmarks[20].y

    return (y3 > y4 and y4 < y8 < y12 < y16 < y20 and
            x6 > x7 > x8 and x12 > x10 and x16 > x14 and x20 > x18)


def check_right_pointing(landmarks) -> bool:
    """Check right pointing gesture - adapted from HandGesture.py."""
    direction = get_orientation(landmarks)
    if direction in ('Down', 'Left', 'Up'):
        return False

    y3, y4 = landmarks[3].y, landmarks[4].y
    x6, x7, x8 = landmarks[6].x, landmarks[7].x, landmarks[8].x
    y8 = landmarks[8].y
    x10, x12 = landmarks[10].x, landmarks[12].x
    y12 = landmarks[12].y
    x14, x16 = landmarks[14].x, landmarks[16].x
    y16 = landmarks[16].y
    x18, x20 = landmarks[18].x, landmarks[20].x
    y20 = landmarks[20].y

    return (y3 > y4 and y4 < y8 < y12 < y16 < y20 and
            x6 < x7 < x8 and x12 < x10 and x16 < x14 and x20 < x18)


def check_upward_pointing(landmarks) -> bool:
    """Check upward pointing gesture - adapted from HandGesture.py."""
    direction = get_orientation(landmarks)
    if direction in ('Down', 'Left', 'Right'):
        return False

    y3, y4 = landmarks[3].y, landmarks[4].y
    x7, y7, y8 = landmarks[7].x, landmarks[7].y, landmarks[8].y
    x9, y9 = landmarks[9].x, landmarks[9].y
    y12 = landmarks[12].y
    x13, y13 = landmarks[13].x, landmarks[13].y
    y16 = landmarks[16].y
    x17, y17 = landmarks[17].x, landmarks[17].y
    y20 = landmarks[20].y

    return (y3 > y4 and y7 > y8 and y12 > y9 and y16 > y13 and y20 > y17 and
            ((x7 > x9 > x13 > x17) or (x7 < x9 < x13 < x17)))


def check_downward_pointing(landmarks) -> bool:
    """Check downward pointing gesture - adapted from HandGesture.py."""
    direction = get_orientation(landmarks)
    if direction in ('Up', 'Left', 'Right'):
        return False

    y3, y4 = landmarks[3].y, landmarks[4].y
    x7, y7, y8 = landmarks[7].x, landmarks[7].y, landmarks[8].y
    x9 = landmarks[9].x
    y10, y12 = landmarks[10].y, landmarks[12].y
    x13 = landmarks[13].x
    y14, y16 = landmarks[14].y, landmarks[16].y
    x17 = landmarks[17].x
    y18, y20 = landmarks[18].y, landmarks[20].y

    return (y3 < y4 and y7 < y8 and y12 < y10 and y16 < y14 and y20 < y18 and
            ((x7 > x9 > x13 > x17) or (x7 < x9 < x13 < x17)))


# Gesture checker mapping
GESTURE_CHECKERS = {
    'upward_palm': check_upward_palm,
    'thumbs_up': check_thumbs_up,
    'victory': check_victory,
    'left_pointing': check_left_pointing,
    'right_pointing': check_right_pointing,
    'upward_pointing': check_upward_pointing,
    'downward_pointing': check_downward_pointing,
}


@dataclass
class GestureGameState:
    """State for gesture game session."""
    gesture_sequence: List[str] = None
    current_index: int = 0
    score: int = 0
    total_gestures: int = 7
    start_time: float = 0.0
    game_over: bool = False
    time_limit: float = 60.0  # seconds
    last_detected: Optional[str] = None
    detection_hold: float = 0.0
    detection_confirm: float = 0.5  # Must hold gesture for 0.5s

    def __post_init__(self):
        if self.gesture_sequence is None:
            self.gesture_sequence = []


class GestureGameMode(BaseMode):
    """Gesture matching game - show gestures matching emojis.

    Adapted from Hand-Gesture-Recognition-Game-with-Emoji-Integration.
    Uses MediaPipe via camera_service for hand tracking.
    """

    name = "gesture_game"
    display_name = "ЖЕСТЫ"
    description = "Покажи жест как на экране"
    icon = "hand"
    style = "arcade"
    requires_camera = True
    estimated_duration = 60

    def __init__(self, context: ModeContext):
        super().__init__(context)
        self._state = GestureGameState()
        self._mp_hands = None
        self._mp_initialized = False

    def _init_mediapipe(self) -> bool:
        """Initialize MediaPipe hands - lazy load."""
        if self._mp_initialized:
            return self._mp_hands is not None

        try:
            import mediapipe as mp
            self._mp_hands = mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                model_complexity=0,
                min_detection_confidence=0.6,
                min_tracking_confidence=0.5,
            )
            self._mp_initialized = True
            return True
        except ImportError:
            self._mp_initialized = True
            return False

    def on_enter(self) -> None:
        """Initialize game - adapted from HandGesture.py main loop."""
        # Initialize MediaPipe
        self._init_mediapipe()

        # Create shuffled gesture sequence - from get_shuffled_dictionary()
        gestures = list(GESTURES.keys())
        random.shuffle(gestures)
        self._state = GestureGameState(
            gesture_sequence=gestures,
            start_time=time.time(),
        )
        self.change_phase(ModePhase.ACTIVE)

    def on_exit(self) -> None:
        """Cleanup."""
        pass

    def on_input(self, event: Event) -> bool:
        """Handle input."""
        if event.type == EventType.BUTTON_PRESS:
            if self._state.game_over:
                self._complete_game()
                return True
        return False

    def on_update(self, delta_ms: float) -> None:
        """Per-frame update - gesture detection."""
        if self.phase != ModePhase.ACTIVE or self._state.game_over:
            return

        # Check time limit
        elapsed = time.time() - self._state.start_time
        if elapsed >= self._state.time_limit:
            self._state.game_over = True
            return

        # Detect gestures - adapted from HandGesture.py main loop
        self._detect_gesture(delta_ms)

    def _detect_gesture(self, delta_ms: float) -> None:
        """Detect hand gesture using MediaPipe."""
        if not self._mp_hands:
            return

        # Get camera frame
        frame = camera_service.get_full_frame(max_age=0.1)
        if frame is None:
            frame = camera_service.get_frame(timeout=0)
            if frame is None:
                return

        try:
            # Process with MediaPipe - from HandGesture.py
            results = self._mp_hands.process(frame)

            if not results.multi_hand_landmarks:
                self._state.last_detected = None
                self._state.detection_hold = 0.0
                return

            # Get landmarks - from HandGesture.py
            landmarks = results.multi_hand_landmarks[0].landmark

            # Check current target gesture
            current_gesture = self._state.gesture_sequence[self._state.current_index]
            checker = GESTURE_CHECKERS.get(current_gesture)

            if checker and checker(landmarks):
                # Correct gesture detected
                if self._state.last_detected == current_gesture:
                    self._state.detection_hold += delta_ms / 1000.0
                    if self._state.detection_hold >= self._state.detection_confirm:
                        self._gesture_matched()
                else:
                    self._state.last_detected = current_gesture
                    self._state.detection_hold = 0.0
            else:
                self._state.last_detected = None
                self._state.detection_hold = 0.0

        except Exception:
            pass

    def _gesture_matched(self) -> None:
        """Handle successful gesture match - from HandGesture.py score update."""
        self._state.score += 1
        self._state.current_index += 1
        self._state.last_detected = None
        self._state.detection_hold = 0.0

        # Check if all gestures completed
        if self._state.current_index >= len(self._state.gesture_sequence):
            self._state.game_over = True

    def _complete_game(self) -> None:
        """Complete the game session."""
        elapsed = time.time() - self._state.start_time
        result = ModeResult(
            mode_name=self.name,
            success=self._state.score == len(self._state.gesture_sequence),
            data={
                "score": self._state.score,
                "total": len(self._state.gesture_sequence),
                "time": round(elapsed, 1),
            },
            display_text=f"СЧЕТ: {self._state.score}/{len(self._state.gesture_sequence)}",
            ticker_text="ЖЕСТЫ",
        )
        self.complete(result)

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        """Render main display."""
        # Camera background
        frame = camera_service.get_frame(timeout=0)
        if frame is not None and frame.shape[:2] == (128, 128):
            # Dim background
            dimmed = (frame.astype(np.float32) * 0.6).astype(np.uint8)
            np.copyto(buffer, dimmed)
        else:
            fill(buffer, (15, 10, 25))

        if self._state.game_over:
            self._render_game_over(buffer)
        else:
            self._render_active_game(buffer)

    def _render_active_game(self, buffer: NDArray[np.uint8]) -> None:
        """Render active game state."""
        # HUD - Score and time
        elapsed = time.time() - self._state.start_time
        remaining = max(0, self._state.time_limit - elapsed)

        # Score display
        score_text = f"СЧЕТ {self._state.score}/{len(self._state.gesture_sequence)}"
        draw_centered_text(buffer, score_text, 2, (200, 200, 200), scale=1)

        # Timer
        time_text = f"ВРЕМЯ {int(remaining)}"
        draw_centered_text(buffer, time_text, 12, (255, 200, 100), scale=1)

        # Current gesture to match
        if self._state.current_index < len(self._state.gesture_sequence):
            current_gesture = self._state.gesture_sequence[self._state.current_index]
            self._draw_gesture_icon(buffer, current_gesture, 64, 60)

            # Progress indicator - adapted from HandGesture.py emoji sequence
            progress = self._state.detection_hold / self._state.detection_confirm
            if progress > 0:
                # Show detection progress bar
                bar_width = int(80 * min(1.0, progress))
                draw_rect(buffer, 24, 90, bar_width, 6, (100, 255, 100), filled=True)
                draw_rect(buffer, 24, 90, 80, 6, (100, 100, 100), filled=False)

        # Gesture progress indicator (dots at bottom)
        self._render_progress_dots(buffer)

    def _draw_gesture_icon(self, buffer: NDArray[np.uint8], gesture: str, cx: int, cy: int) -> None:
        color = (255, 255, 255)
        shadow = (0, 0, 0)
        size = 36
        self._draw_gesture_shape(buffer, gesture, cx + 2, cy + 2, size, shadow)
        self._draw_gesture_shape(buffer, gesture, cx, cy, size, color)

    def _draw_gesture_shape(
        self,
        buffer: NDArray[np.uint8],
        gesture: str,
        cx: int,
        cy: int,
        size: int,
        color: tuple,
    ) -> None:
        arrow_map = {
            "left_pointing": "left",
            "right_pointing": "right",
            "upward_pointing": "up",
            "downward_pointing": "down",
        }

        direction = arrow_map.get(gesture)
        if direction:
            self._draw_arrow_icon(buffer, cx, cy, direction, size, color)
        elif gesture == "victory":
            self._draw_victory_icon(buffer, cx, cy, size, color)
        elif gesture == "thumbs_up":
            self._draw_thumbs_up_icon(buffer, cx, cy, size, color)
        elif gesture == "upward_palm":
            self._draw_palm_icon(buffer, cx, cy, size, color)
        else:
            draw_circle(buffer, cx, cy, max(8, size // 4), color, filled=False)

    def _draw_arrow_icon(
        self,
        buffer: NDArray[np.uint8],
        cx: int,
        cy: int,
        direction: str,
        size: int,
        color: tuple,
    ) -> None:
        half = size // 2
        head = max(6, size // 3)
        thickness = 3

        if direction == "left":
            draw_line(buffer, cx + half, cy, cx - half, cy, color, thickness=thickness)
            draw_line(buffer, cx - half, cy, cx - half + head, cy - head, color, thickness=thickness)
            draw_line(buffer, cx - half, cy, cx - half + head, cy + head, color, thickness=thickness)
        elif direction == "right":
            draw_line(buffer, cx - half, cy, cx + half, cy, color, thickness=thickness)
            draw_line(buffer, cx + half, cy, cx + half - head, cy - head, color, thickness=thickness)
            draw_line(buffer, cx + half, cy, cx + half - head, cy + head, color, thickness=thickness)
        elif direction == "up":
            draw_line(buffer, cx, cy + half, cx, cy - half, color, thickness=thickness)
            draw_line(buffer, cx, cy - half, cx - head, cy - half + head, color, thickness=thickness)
            draw_line(buffer, cx, cy - half, cx + head, cy - half + head, color, thickness=thickness)
        elif direction == "down":
            draw_line(buffer, cx, cy - half, cx, cy + half, color, thickness=thickness)
            draw_line(buffer, cx, cy + half, cx - head, cy + half - head, color, thickness=thickness)
            draw_line(buffer, cx, cy + half, cx + head, cy + half - head, color, thickness=thickness)

    def _draw_victory_icon(
        self,
        buffer: NDArray[np.uint8],
        cx: int,
        cy: int,
        size: int,
        color: tuple,
    ) -> None:
        half = size // 2
        thickness = 3
        draw_line(buffer, cx - half, cy - half, cx, cy + half, color, thickness=thickness)
        draw_line(buffer, cx + half, cy - half, cx, cy + half, color, thickness=thickness)

    def _draw_thumbs_up_icon(
        self,
        buffer: NDArray[np.uint8],
        cx: int,
        cy: int,
        size: int,
        color: tuple,
    ) -> None:
        palm_w = max(16, size // 2)
        palm_h = max(14, size // 2)
        palm_x = cx - palm_w // 2
        palm_y = cy - palm_h // 2 + 8
        draw_rect(buffer, palm_x, palm_y, palm_w, palm_h, color, filled=True)

        thumb_w = max(6, palm_w // 3)
        thumb_h = palm_h + 4
        thumb_x = palm_x + palm_w - thumb_w
        thumb_y = palm_y - thumb_h + 4
        draw_rect(buffer, thumb_x, thumb_y, thumb_w, thumb_h, color, filled=True)

    def _draw_palm_icon(
        self,
        buffer: NDArray[np.uint8],
        cx: int,
        cy: int,
        size: int,
        color: tuple,
    ) -> None:
        palm_w = size
        palm_h = max(14, size // 2)
        palm_x = cx - palm_w // 2
        palm_y = cy - palm_h // 2 + 6
        draw_rect(buffer, palm_x, palm_y, palm_w, palm_h, color, filled=True)

        finger_w = max(3, palm_w // 6)
        spacing = max(2, finger_w - 1)
        total_w = finger_w * 5 + spacing * 4
        finger_h = max(10, palm_h)
        finger_y = palm_y - finger_h + 2
        start_x = cx - total_w // 2
        for i in range(5):
            fx = start_x + i * (finger_w + spacing)
            draw_rect(buffer, fx, finger_y, finger_w, finger_h, color, filled=True)

    def _render_progress_dots(self, buffer: NDArray[np.uint8]) -> None:
        """Render progress dots at bottom."""
        total = len(self._state.gesture_sequence)
        dot_spacing = min(12, 100 // max(1, total))
        start_x = 64 - (total * dot_spacing) // 2

        for i in range(total):
            x = start_x + i * dot_spacing
            y = 118
            if i < self._state.current_index:
                # Completed - green
                color = (100, 255, 100)
            elif i == self._state.current_index:
                # Current - yellow
                color = (255, 255, 0)
            else:
                # Pending - gray
                color = (80, 80, 80)

            draw_circle(buffer, x, y, 3, color, filled=True)

    def _render_game_over(self, buffer: NDArray[np.uint8]) -> None:
        """Render game over screen - adapted from HandGesture.py score display."""
        fill(buffer, (10, 10, 20))

        # Title
        draw_centered_text(buffer, "КОНЕЦ", 20, (255, 100, 100), scale=2)

        # Score
        score_text = f"СЧЕТ: {self._state.score}/{len(self._state.gesture_sequence)}"
        draw_centered_text(buffer, score_text, 55, (200, 200, 200), scale=1)

        # Time
        elapsed = time.time() - self._state.start_time
        time_text = f"ВРЕМЯ: {int(elapsed)}"
        draw_centered_text(buffer, time_text, 70, (150, 150, 150), scale=1)

        # Win/lose message
        if self._state.score == len(self._state.gesture_sequence):
            draw_centered_text(buffer, "ОТЛИЧНО!", 90, (100, 255, 100), scale=1)
        else:
            draw_centered_text(buffer, "ЕЩЕ РАЗ", 90, (255, 150, 100), scale=1)

        draw_centered_text(buffer, "НАЖМИ", 110, (150, 150, 150), scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        """Render ticker display."""
        fill(buffer, (0, 0, 0))

        if self._state.game_over:
            text = f"СЧ {self._state.score}"
        else:
            elapsed = time.time() - self._state.start_time
            remaining = max(0, self._state.time_limit - elapsed)
            text = f" {int(remaining):02d}С"

        draw_centered_text(buffer, text, 1, (255, 200, 100), scale=1)

    def get_lcd_text(self) -> str:
        """Get LCD display text."""
        if self._state.game_over:
            return f"СЧЕТ: {self._state.score:02d}   "[:16]
        elif self._state.current_index < len(self._state.gesture_sequence):
            gesture = self._state.gesture_sequence[self._state.current_index]
            name = GESTURE_NAMES.get(gesture, gesture[:10])
            return name.center(16)[:16]
        return "    ЖЕСТЫ    "[:16]

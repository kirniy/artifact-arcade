"""Hidden SPIDERVERSE photo quest, toggled by a deliberate KP7 hold."""

from __future__ import annotations

import logging
import math
import uuid
from enum import Enum, auto
import numpy as np
from numpy.typing import NDArray

from artifact.core.events import Event, EventType
from artifact.graphics.primitives import draw_circle, draw_line, draw_rect, fill
from artifact.graphics.text_utils import draw_centered_text, render_idle_style_ticker_text
from artifact.modes.base import ModeContext, ModePhase
from artifact.modes.photobooth import PhotoboothMode, PhotoboothState
logger = logging.getLogger(__name__)

INK = (8, 12, 25)
RED = (235, 28, 48)
CREAM = (245, 235, 213)
BLUE = (32, 72, 150)
TICKER_GREEN = (0, 255, 48)
QUEST_START_URL = "https://t.me/vnvncbattlebot?start=spiderquest"


class QuestScreen(Enum):
    READY = auto()
    PHOTO = auto()


class SpiderverseQuestMode(PhotoboothMode):
    """Run the existing themed photo flow and print the static quest entry QR."""

    name = "spiderverse_quest"
    display_name = "ПАУЧЬЕ\nЧУТЬЁ"
    description = "КВЕСТ · КОКТЕЙЛЬ + ШОТ"
    theme_id_override = "spiderverse"
    ai_style_key_override = "spiderverse"

    def __init__(self, context: ModeContext) -> None:
        self._quest_screen = QuestScreen.READY
        self._quest_print_id = ""
        self._quest_receipt_queued = False
        super().__init__(context)
        self._camera_selector_enabled = False

    @property
    def is_safe_to_exit(self) -> bool:
        return self._quest_screen == QuestScreen.READY or (
            self._quest_screen == QuestScreen.PHOTO and self._state.show_result
        )

    def on_enter(self) -> None:
        super().on_enter()
        self._reset_to_quest_ready()

    def on_exit(self) -> None:
        super().on_exit()

    def on_input(self, event: Event) -> bool:
        if event.type in {EventType.PRINT_COMPLETE, EventType.PRINT_ERROR}:
            event_mode = str(event.data.get("type") or event.data.get("mode") or "")
            if event_mode != "photobooth" or not self._quest_receipt_queued:
                return False
            self._quest_receipt_queued = False
            if event.type == EventType.PRINT_ERROR:
                logger.error("SPIDERVERSE quest photo receipt failed; companion receipt suppressed")
                return True
            self._emit_quest_receipt()
            return True
        if self._quest_screen == QuestScreen.READY:
            if event.type == EventType.BUTTON_PRESS:
                self._start_quest_photo()
                return True
            return event.type == EventType.KEYPAD_INPUT
        return super().on_input(event)

    def on_update(self, delta_ms: float) -> None:
        if self._quest_screen == QuestScreen.PHOTO:
            super().on_update(delta_ms)

    def _start_quest_photo(self) -> None:
        """Start immediately; Telegram enforces eligibility after QR scan."""
        self._quest_screen = QuestScreen.PHOTO
        self._quest_print_id = uuid.uuid4().hex
        self._quest_receipt_queued = False
        self._working = True
        self._state.awaiting_camera_selection = False
        self._start_countdown()
        logger.info("SPIDERVERSE quest photo started")

    def _start_printing_now(self) -> None:
        was_printing = self._state.is_printing
        super()._start_printing_now()
        if was_printing or self._quest_receipt_queued or not self._state.is_printing:
            return
        self._quest_receipt_queued = True

    def _emit_quest_receipt(self) -> None:
        self.context.event_bus.emit(
            Event(
                EventType.PRINT_START,
                data={
                    "type": "spiderverse_quest",
                    "quest_start_url": QUEST_START_URL,
                    "print_job_key": f"quest:{self._quest_print_id}",
                },
                source="spiderverse_quest",
            )
        )

    def _complete_session(self) -> None:
        """Stay in the hidden profile and prepare a fresh run."""
        self._reset_to_quest_ready()

    def _reset_to_quest_ready(self) -> None:
        self._state = PhotoboothState()
        self._state.awaiting_camera_selection = False
        self._working = False
        self._quest_screen = QuestScreen.READY
        self._quest_print_id = ""
        self._quest_receipt_queued = False
        self.change_phase(ModePhase.ACTIVE)

    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        if self._quest_screen == QuestScreen.PHOTO:
            super().render_main(buffer)
            return
        self._render_quest_attract(buffer)

    def _render_quest_attract(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, INK)
        t = self._time_in_mode / 1000.0

        # Breathing suit panels and animated perspective web.
        pulse = int(18 + 12 * (0.5 + 0.5 * math.sin(t * 2.2)))
        draw_rect(buffer, 2, 2, 124, 124, RED, filled=False, thickness=2)
        draw_rect(buffer, 5, 5, 118, 118, (pulse, 25, 55), filled=False, thickness=1)
        cx, cy = 64, 31
        for radius in (10, 18, 27, 36):
            shade = (100 + radius * 2, 18, 38)
            draw_circle(buffer, cx, cy, radius, shade, filled=False)
        phase = t * 0.45
        for index in range(10):
            angle = phase + index * math.tau / 10
            x = int(cx + math.cos(angle) * 48)
            y = int(cy + math.sin(angle) * 40)
            draw_line(buffer, cx, cy, x, y, RED, thickness=1)

        # Original angular mask/suit emblem.
        bob = int(2 * math.sin(t * 2.8))
        for y in range(14 + bob, 39 + bob):
            inset = abs(27 + bob - y) // 2
            draw_line(buffer, 42 + inset, y, 59, y, CREAM, thickness=1)
            draw_line(buffer, 69, y, 86 - inset, y, CREAM, thickness=1)
        draw_line(buffer, 47, 47 + bob, 64, 56 + bob, BLUE, thickness=2)
        draw_line(buffer, 81, 47 + bob, 64, 56 + bob, BLUE, thickness=2)

        # The typography owns a quiet field; no animated line may reduce legibility.
        draw_rect(buffer, 8, 62, 112, 62, INK, filled=True)
        draw_rect(buffer, 8, 62, 112, 62, RED, filled=False, thickness=1)

        draw_centered_text(buffer, "ПАУЧЬЕ", 66, CREAM, scale=2)
        draw_centered_text(buffer, "ЧУТЬЁ", 83, CREAM, scale=2)
        draw_centered_text(buffer, "КВЕСТ", 103, RED, scale=1)
        draw_centered_text(buffer, "КОКТЕЙЛЬ + ШОТ", 115, CREAM, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        if self._quest_screen == QuestScreen.PHOTO:
            super().render_ticker(buffer)
            return
        fill(buffer, (0, 0, 0))
        text = "ПАУЧЬЕ ЧУТЬЁ"
        render_idle_style_ticker_text(buffer, text, TICKER_GREEN, self._time_in_mode, safe_left=8)

    def get_lcd_text(self) -> str:
        if self._quest_screen == QuestScreen.PHOTO:
            return super().get_lcd_text()
        return " ПАУЧЬЕ ЧУТЬЁ   "[:16]

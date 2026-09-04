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
from artifact.graphics.text_utils import draw_centered_text, render_idle_style_ticker_text, measure_text
from artifact.modes.base import ModeContext, ModePhase
from artifact.modes.photobooth import PhotoboothMode, PhotoboothState
logger = logging.getLogger(__name__)

INK = (8, 12, 25)
RED = (235, 28, 48)
CREAM = (245, 235, 213)
BLUE = (32, 72, 150)
TICKER_GREEN = (0, 255, 48)
QUEST_START_URL = "https://t.me/vnvncbattlebot?start=spiderquest"
QUEST_STORY = (
    ("ПОМОЖЕШЬ", "ПИТЕРУ", "ПАРКЕРУ?"),
    ("СДЕЛАЙ", "ФОТО", "В БУДКЕ"),
    ("ЗАБЕРИ", "ЧЕК", "С ФОТО"),
    ("СКАНИРУЙ", "QR С ЧЕКА", "В TELEGRAM"),
    ("ПРОЙДИ", "5 ФОТО", "ЗАДАНИЙ"),
    ("КОКТЕЙЛЬ", "+ ШОТ", "ЗА КВЕСТ"),
)
QUEST_SCENE_MS = 4200


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
        return not self._quest_receipt_queued and (
            self._quest_screen == QuestScreen.READY or (
            self._quest_screen == QuestScreen.PHOTO and self._state.show_result
            )
        )

    def on_enter(self) -> None:
        super().on_enter()
        self._reset_to_quest_ready()

    def on_exit(self) -> None:
        super().on_exit()

    def on_input(self, event: Event) -> bool:
        if event.type in {EventType.PRINT_COMPLETE, EventType.PRINT_ERROR}:
            event_mode = str(event.data.get("type") or event.data.get("mode") or "")
            issue_id = str(event.data.get("issue_id") or "")
            if (
                event_mode != "photobooth"
                or not self._quest_receipt_queued
                or issue_id != self._quest_print_id
            ):
                return False
            self._quest_receipt_queued = False
            if event.type == EventType.PRINT_ERROR:
                logger.error("SPIDERVERSE combined photo/quest receipt failed")
                return True
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
        if self._state.is_printing or self._quest_receipt_queued:
            return
        image_for_print = (
            self._state.ai_label_bytes
            or self._state.ai_display_bytes
            or self._state.photo_bytes
        )
        if not image_for_print:
            logger.warning("SPIDERVERSE quest has no image available for printing")
            return
        self._state.is_printing = True
        self._quest_receipt_queued = True
        self.context.event_bus.emit(
            Event(
                EventType.PRINT_START,
                data={
                    "type": "photobooth",
                    "caricature": image_for_print,
                    "photo": self._state.photo_bytes,
                    "qr_url": self._state.qr_url,
                    "short_url": self._state.qr_url,
                    "qr_image": self._state.qr_image,
                    "issue_id": self._quest_print_id,
                    "quest_start_url": QUEST_START_URL,
                    # Unlike the public photo mode, this combined receipt
                    # must receive an explicit error if no printer is present.
                    "print_required": True,
                },
                source="spiderverse_quest",
            )
        )

    def _complete_session(self) -> None:
        """Stay in the hidden profile and prepare a fresh run."""
        if self._quest_receipt_queued:
            # Do not discard the combined receipt while the physical
            # print is still in flight. PRINT_COMPLETE/PRINT_ERROR releases it.
            self._state.countdown_timer = 1.0
            return
        self._reset_to_quest_ready()

    def _do_flash_and_capture(self) -> None:
        super()._do_flash_and_capture()
        if not self._state.photo_bytes and not self._working:
            logger.error("SPIDERVERSE quest capture failed; returning to attract screen")
            self._reset_to_quest_ready()

    def _reset_to_quest_ready(self) -> None:
        self._quest_ready_started_ms = self._time_in_mode
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
        """Interruptible comic onboarding; button starts immediately in every scene."""
        story_ms = self._time_in_mode - getattr(self, "_quest_ready_started_ms", 0)
        scene = int(story_ms // QUEST_SCENE_MS) % len(QUEST_STORY)
        local_ms = story_ms % QUEST_SCENE_MS
        # Fast ease-out entry; most of the scene is motionless readable copy.
        progress = min(1.0, local_ms / 240.0)
        offset = round(5 * (1 - progress) ** 3)
        fill(buffer, INK)
        draw_rect(buffer, 2, 2, 124, 124, RED, filled=False, thickness=2)
        if scene == 0:
            mask = np.zeros_like(buffer)
            self._render_quest_mask(mask)
            buffer[6:42, 8:120] = mask[7:79:2, 8:120]
        else:
            # Small animated illustrations explain the physical sequence.
            bob = round(math.sin(self._time_in_mode / 600) * 1.5)
            y = 10 + bob
            if scene == 1:
                draw_rect(buffer, 41, y + 6, 46, 26, RED, filled=True)
                draw_rect(buffer, 48, y + 1, 16, 7, RED, filled=True)
                draw_circle(buffer, 64, y + 19, 10, CREAM, filled=True)
                draw_circle(buffer, 64, y + 19, 6, INK, filled=True)
            elif scene in (2, 3, 4):
                draw_rect(buffer, 49, y, 30, 33, CREAM, filled=True)
                for line in range(3):
                    draw_line(buffer, 54, y + 6 + line * 6, 73, y + 6 + line * 6, INK, thickness=2)
                draw_line(buffer, 59, y + 27, 64, y + 30, RED, thickness=2)
                draw_line(buffer, 64, y + 30, 72, y + 22, RED, thickness=2)
            else:
                draw_line(buffer, 43, y + 4, 67, y + 4, CREAM, thickness=2)
                draw_line(buffer, 43, y + 4, 55, y + 20, RED, thickness=2)
                draw_line(buffer, 67, y + 4, 55, y + 20, RED, thickness=2)
                draw_line(buffer, 55, y + 20, 55, y + 31, CREAM, thickness=2)
                draw_line(buffer, 48, y + 31, 62, y + 31, CREAM, thickness=2)
                draw_rect(buffer, 75, y + 16, 12, 15, CREAM, filled=False, thickness=2)
        for index, line in enumerate(QUEST_STORY[scene]):
            scale = 2 if measure_text(line, scale=2)[0] <= 112 else 1
            draw_centered_text(buffer, line, 49 + index * 19 + offset, CREAM if index != 1 else RED, scale=scale)
        for index in range(len(QUEST_STORY)):
            draw_rect(buffer, 25 + index * 13, 108, 9, 2, RED if index == scene else BLUE, filled=True)
        draw_centered_text(buffer, "НАЖМИ КНОПКУ", 116, CREAM, scale=1)

    def _render_quest_mask(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, INK)
        t = self._time_in_mode / 1000.0

        # A large breathing red mask owns the frame; the web moves behind it.
        pulse = int(34 + 22 * (0.5 + 0.5 * math.sin(t * 2.2)))
        draw_rect(buffer, 2, 2, 124, 124, RED, filled=False, thickness=2)
        draw_rect(buffer, 7, 7, 114, 70, (145 + pulse, 12, 35), filled=True)
        cx, cy = 64, 38
        for radius in (12, 23, 35, 47):
            shade = (55 + radius * 2, 8, 27)
            draw_circle(buffer, cx, cy, radius, shade, filled=False)
        phase = t * 0.45
        for index in range(12):
            angle = phase + index * math.tau / 12
            x = int(cx + math.cos(angle) * 58)
            y = int(cy + math.sin(angle) * 38)
            draw_line(buffer, cx, cy, x, y, (104, 9, 29), thickness=1)

        # Swept temple lenses, heavy ink rims and asymmetrical expression.
        bob = int(2 * math.sin(t * 2.1))
        blink_phase = t % 4.8
        openness = 2 if blink_phase < 0.13 or 0.22 < blink_phase < 0.34 else 10
        left_open = max(2, openness + int(2 * math.sin(t * 1.15)))
        right_open = max(2, openness - int(2 * math.sin(t * 1.15)))
        eye_mid_y = 39 + bob
        for is_left, eye_open in ((True, left_open), (False, right_open)):
            half = max(1, eye_open)
            for offset in range(-half - 2, half + 3):
                taper = int(abs(offset) * 0.8)
                if is_left:
                    x0, x1 = 13 + taper, 55 - taper // 3
                else:
                    x0, x1 = 73 + taper // 3, 115 - taper
                draw_line(buffer, x0, eye_mid_y + offset, x1, eye_mid_y + offset, INK, thickness=1)
            for offset in range(-half, half + 1):
                taper = int(abs(offset) * 0.9)
                if is_left:
                    x0, x1 = 16 + taper, 52 - taper // 3
                else:
                    x0, x1 = 76 + taper // 3, 112 - taper
                draw_line(buffer, x0, eye_mid_y + offset, x1, eye_mid_y + offset, CREAM, thickness=1)
        draw_line(buffer, 18, 24 + bob, 55, 31 + bob, INK, thickness=3)
        draw_line(buffer, 73, 31 + bob, 110, 24 + bob, INK, thickness=3)

        # Comic sparks orbit outside the quiet type panel.
        for index in range(8):
            spark_t = t * (0.8 + index * 0.035) + index * 1.7
            sx = int(64 + math.cos(spark_t) * (43 + index % 3 * 3))
            sy = int(32 + math.sin(spark_t * 1.31) * 25)
            draw_circle(buffer, sx, sy, 1, CREAM if index % 2 else RED, filled=True)

        # The typography owns a quiet field; no animated line may reduce legibility.
        draw_rect(buffer, 8, 80, 112, 44, INK, filled=True)
        draw_rect(buffer, 8, 80, 112, 44, RED, filled=False, thickness=1)

        draw_centered_text(buffer, "ПАУЧЬЕ ЧУТЬЁ", 84, CREAM, scale=1)
        draw_centered_text(buffer, "КОКТЕЙЛЬ + ШОТ", 97, RED, scale=1)
        draw_centered_text(buffer, "НАЖМИ КНОПКУ", 111, CREAM, scale=1)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        if self._quest_screen == QuestScreen.PHOTO:
            super().render_ticker(buffer)
            return
        fill(buffer, (0, 0, 0))
        text = "КОКТЕЙЛЬ + ШОТ" if int(self._time_in_mode / 1800) % 2 else "5 ФОТО-ЗАДАНИЙ"
        render_idle_style_ticker_text(buffer, text, TICKER_GREEN, self._time_in_mode, safe_left=8)

    def get_lcd_text(self) -> str:
        if self._quest_screen == QuestScreen.PHOTO:
            return super().get_lcd_text()
        return " НАЖМИ КНОПКУ   "[:16]

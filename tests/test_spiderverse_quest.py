from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from artifact.animation.engine import AnimationEngine
from artifact.core.events import Event, EventBus, EventType
from artifact.core.state import StateMachine
from artifact.graphics.renderer import Renderer
from artifact.modes.base import ModeContext, ModePhase
from artifact.modes.manager import ManagerState, ModeManager
from artifact.modes.spiderverse_quest import (
    QUEST_START_URL,
    QuestScreen,
    SpiderverseQuestMode,
)
from artifact.printing.spiderverse_quest_roll import (
    SPIDERVERSE_QUEST_MODE_NAME,
    SpiderverseQuestRollReceiptGenerator,
)


class _SilentAudio:
    def __getattr__(self, name):
        if name == "is_idle_music_active":
            return lambda: True
        return lambda *args, **kwargs: None


def _context(bus: EventBus | None = None) -> ModeContext:
    return ModeContext(
        state_machine=StateMachine(),
        event_bus=bus or EventBus(),
        renderer=Renderer(),
        animation_engine=AnimationEngine(),
    )


def test_kp7_hold_toggles_quest_without_changing_kp9_wheel(monkeypatch) -> None:
    import artifact.modes.manager as manager_module

    monkeypatch.setattr(manager_module, "get_audio_engine", lambda: _SilentAudio())
    bus = EventBus()
    manager = ModeManager(
        StateMachine(),
        bus,
        Renderer(),
        AnimationEngine(),
        enable_prize_drum=True,
        enable_spiderverse_quest=True,
    )

    bus.emit(Event(EventType.KEYPAD_PRESS, {"key": "7"}, source="test"))
    manager.update(1999.0)
    assert not manager._spiderverse_quest_active
    manager.update(1.0)
    assert manager._spiderverse_quest_active
    assert isinstance(manager._current_mode, SpiderverseQuestMode)
    assert not manager._prize_drum_active

    bus.emit(Event(EventType.KEYPAD_RELEASE, {"key": "7"}, source="test"))
    bus.emit(Event(EventType.KEYPAD_PRESS, {"key": "7"}, source="test"))
    manager.update(2000.0)
    assert not manager._spiderverse_quest_active
    assert manager.state in {ManagerState.IDLE, ManagerState.MODE_SELECT}


def test_short_kp7_is_forwarded_as_seven(monkeypatch) -> None:
    import artifact.modes.manager as manager_module

    monkeypatch.setattr(manager_module, "get_audio_engine", lambda: _SilentAudio())
    bus = EventBus()
    manager = ModeManager(
        StateMachine(), bus, Renderer(), AnimationEngine(),
        enable_prize_drum=False, enable_spiderverse_quest=True,
    )
    bus.emit(Event(EventType.KEYPAD_PRESS, {"key": "7"}, source="test"))
    manager.update(100.0)
    bus.emit(Event(EventType.KEYPAD_RELEASE, {"key": "7"}, source="test"))
    assert [event.data["key"] for event in bus.get_history(EventType.KEYPAD_INPUT)] == ["7"]


def test_hardware_kp7_emits_edges_only() -> None:
    pygame = pytest.importorskip("pygame")
    from artifact.hardware.runner import HardwareRunner

    bus = EventBus()
    runner = HardwareRunner(event_bus=bus)
    event = SimpleNamespace(key=pygame.K_KP7)
    runner._handle_keydown(event)
    runner._handle_keydown(event)
    runner._handle_keyup(event)
    assert [item.type for item in bus.get_history(limit=10)] == [
        EventType.KEYPAD_PRESS,
        EventType.KEYPAD_RELEASE,
    ]


def test_quest_press_starts_spiderverse_photo_immediately_without_network() -> None:
    mode = SpiderverseQuestMode(_context())
    mode.enter()
    assert mode._theme.id == "spiderverse"
    assert mode._quest_screen == QuestScreen.READY
    assert mode.handle_input(Event(EventType.BUTTON_PRESS, source="test"))
    assert mode._quest_screen == QuestScreen.PHOTO
    assert mode.phase == ModePhase.PROCESSING
    assert mode._state.countdown == 3


def test_quest_ready_frame_ticker_and_lcd_are_not_blank() -> None:
    mode = SpiderverseQuestMode(_context())
    mode.enter()
    main = np.zeros((128, 128, 3), dtype=np.uint8)
    ticker = np.zeros((8, 48, 3), dtype=np.uint8)
    mode.render_main(main)
    mode.render_ticker(ticker)
    assert np.count_nonzero(main) > 500
    assert np.count_nonzero(ticker) > 8
    assert "ПАУЧЬЕ" in mode.get_lcd_text()


def test_successful_photo_print_is_followed_by_static_quest_receipt(monkeypatch) -> None:
    import artifact.modes.photobooth as photobooth_module

    monkeypatch.setattr(photobooth_module, "PRINTING_ENABLED", True)
    bus = EventBus()
    mode = SpiderverseQuestMode(_context(bus))
    mode.enter()
    mode._start_quest_photo()
    mode._state.ai_label_bytes = BytesIO()
    sample = Image.new("RGB", (64, 96), "white")
    sample.save(mode._state.ai_label_bytes, format="PNG")
    mode._state.ai_label_bytes = mode._state.ai_label_bytes.getvalue()
    mode._start_printing_now()

    jobs = bus.get_history(EventType.PRINT_START)
    assert [job.data["type"] for job in jobs] == ["photobooth"]
    assert jobs[0].data["print_required"] is True
    mode._complete_session()
    assert mode._quest_screen == QuestScreen.PHOTO
    assert not mode.is_safe_to_exit
    assert mode.handle_input(Event(EventType.PRINT_COMPLETE, {"type": "photobooth"}, source="test"))
    jobs = bus.get_history(EventType.PRINT_START)
    assert [job.data["type"] for job in jobs] == ["photobooth", SPIDERVERSE_QUEST_MODE_NAME]
    assert jobs[1].data["quest_start_url"] == QUEST_START_URL
    assert "quest_session_id" not in jobs[1].data


def test_failed_or_missing_photo_print_never_queues_quest_receipt(monkeypatch) -> None:
    import artifact.modes.photobooth as photobooth_module

    monkeypatch.setattr(photobooth_module, "PRINTING_ENABLED", True)
    bus = EventBus()
    mode = SpiderverseQuestMode(_context(bus))
    mode.enter()
    mode._start_quest_photo()
    mode._start_printing_now()
    assert bus.get_history(EventType.PRINT_START) == []

    mode._state.photo_bytes = b"photo"
    mode._start_printing_now()
    assert [job.data["type"] for job in bus.get_history(EventType.PRINT_START)] == ["photobooth"]
    assert mode.handle_input(Event(EventType.PRINT_ERROR, {"type": "photobooth"}, source="test"))
    assert [job.data["type"] for job in bus.get_history(EventType.PRINT_START)] == ["photobooth"]


def test_capture_failure_returns_to_attract_screen(monkeypatch) -> None:
    import artifact.modes.photobooth as photobooth_module

    mode = SpiderverseQuestMode(_context())
    mode.enter()
    mode._start_quest_photo()
    monkeypatch.setattr(photobooth_module.camera_service, "capture_jpeg", lambda quality=90: None)
    mode._do_flash_and_capture()
    assert mode._quest_screen == QuestScreen.READY
    assert mode.is_safe_to_exit


def test_quest_receipt_uses_one_large_static_scannable_qr() -> None:
    cv2 = pytest.importorskip("cv2")
    generator = SpiderverseQuestRollReceiptGenerator()
    receipt = generator.generate_receipt(
        SPIDERVERSE_QUEST_MODE_NAME,
        {"quest_start_url": QUEST_START_URL},
    )
    image = Image.open(BytesIO(receipt.preview_image)).convert("RGB")
    assert image.width == 576
    assert image.height < 1200
    assert image.getpixel((0, image.height - 1)) == (255, 255, 255)
    x0, y0, x1, y1 = receipt.qr_region
    assert x1 - x0 >= 300
    decoded, _points, _straight = cv2.QRCodeDetector().detectAndDecode(
        np.array(image.crop((x0, y0, x1, y1)))
    )
    assert decoded == QUEST_START_URL

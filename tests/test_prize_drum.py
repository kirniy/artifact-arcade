import asyncio
import hashlib
import hmac
import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from artifact.animation.engine import AnimationEngine
from artifact.core.events import Event, EventBus, EventType, HoldKeyDetector
from artifact.core.state import StateMachine
from artifact.graphics.fonts import PixelFont, draw_text_bitmap, load_font
from artifact.graphics.renderer import Renderer
from artifact.modes.base import BaseMode, ModeContext
from artifact.modes.manager import ManagerState, ModeManager
from artifact.modes.prize_drum import (
    AUTH_QR_MAX_SIZE,
    BLACK,
    FADED_PAPER,
    LCD_PRIZE_HEADLINES,
    OFF_WHITE,
    PRESENTATION_ONLY_PRIZE_IDS,
    PRIZE_DRUM_AUDIT_PREFIX,
    PrizeDrumFlow,
    PrizeDrumMode,
    PrizeDrumScreen,
    RED,
    ReelMotion,
    SECTOR_STEP,
    SIDE_DISPLAY_STATUS,
    SHOWCASE_HOLD_MS,
    SHOWCASE_SECTORS,
    SHOWCASE_TRAVEL_MS,
    SPIN_CATALOG_PASSES,
    SPIN_DURATION_MS,
    TICKET_HEADLINES,
    TICKET_DISCOUNT_PRIZE_ID,
    TICKER_GREEN,
    TICKER_PRIZE_HEADLINES,
    WHITE,
    VISUAL_DUPLICATES_PER_PRIZE,
    build_visual_reel,
    find_false_hit_indices,
    find_reel_stop_index,
    make_qr_array,
)
from artifact.services.vnvnc_kiosk import (
    KioskAward,
    KioskAuth,
    KioskClientError,
    KioskConfigurationError,
    KioskCoupon,
    KioskPrize,
    KioskSession,
    KioskSpinResult,
    KioskUser,
    LocalKioskStub,
    SpinAllowance,
    VNVNCKioskClient,
    parse_spin_response,
)


class _SilentAudio:
    def __getattr__(self, name):
        if name == "is_idle_music_active":
            return lambda: True
        return lambda *args, **kwargs: None


def _context() -> ModeContext:
    return ModeContext(
        state_machine=StateMachine(),
        event_bus=EventBus(),
        renderer=Renderer(),
        animation_engine=AnimationEngine(),
    )


async def _settle(mode: PrizeDrumMode, *, frames: int = 12, delta_ms: float = 0.0) -> None:
    for _ in range(frames):
        await asyncio.sleep(0)
        mode.update(delta_ms)


def test_simulator_facing_mode_description_uses_current_public_brand() -> None:
    assert PrizeDrumMode.description == "Призовой барабан ФОТОБУДКИ ВИНОВНИЦЫ"
    assert "VNVNC PHOTOBOOTH" not in PrizeDrumMode.description


def test_hold_detector_fires_at_exactly_two_seconds_and_requires_release() -> None:
    detector = HoldKeyDetector("9", threshold_ms=2000.0)

    assert detector.press("9")
    assert not detector.press("9")  # SDL repeat is ignored.
    assert not detector.update(1999.999)
    assert detector.update(0.001)
    assert not detector.update(5000)
    assert detector.elapsed_ms == 2000.0

    assert detector.release("9")
    assert detector.press("9")
    assert detector.update(2000.0)


def test_hardware_kp9_edges_never_emit_keypad_digit() -> None:
    pygame = pytest.importorskip("pygame")
    from artifact.hardware.runner import HardwareRunner

    bus = EventBus()
    runner = HardwareRunner(event_bus=bus)
    event = SimpleNamespace(key=pygame.K_KP9)

    runner._handle_keydown(event)
    runner._handle_keydown(event)
    runner._handle_keyup(event)

    history = bus.get_history(limit=10)
    assert [item.type for item in history] == [EventType.KEYPAD_PRESS, EventType.KEYPAD_RELEASE]
    assert not any(item.type == EventType.KEYPAD_INPUT for item in history)


def test_simulator_nine_edges_never_emit_keypad_digit() -> None:
    pygame = pytest.importorskip("pygame")
    from artifact.simulator.window import SimulatorWindow

    bus = EventBus()
    window = SimulatorWindow(event_bus=bus)
    event = SimpleNamespace(key=pygame.K_9)

    window._handle_keydown(event)
    window._handle_keydown(event)
    window._handle_keyup(event)

    history = bus.get_history(limit=10)
    assert [item.type for item in history] == [EventType.KEYPAD_PRESS, EventType.KEYPAD_RELEASE]
    assert not any(item.type == EventType.KEYPAD_INPUT for item in history)


@pytest.mark.parametrize("enabled", [False, True])
def test_manager_forwards_one_short_nine_even_when_feature_disabled(monkeypatch, enabled) -> None:
    import artifact.modes.manager as manager_module

    monkeypatch.setattr(manager_module, "get_audio_engine", lambda: _SilentAudio())
    bus = EventBus()
    manager = ModeManager(
        StateMachine(),
        bus,
        Renderer(),
        AnimationEngine(),
        enable_prize_drum=enabled,
        prize_drum_client=LocalKioskStub(),
    )

    bus.emit(Event(EventType.KEYPAD_PRESS, {"key": "9"}, source="keypad"))
    manager.update(1999.0)
    bus.emit(Event(EventType.KEYPAD_RELEASE, {"key": "9"}, source="keypad"))

    digits = bus.get_history(EventType.KEYPAD_INPUT)
    assert [event.data["key"] for event in digits] == ["9"]
    assert not manager._prize_drum_active


@pytest.mark.asyncio
async def test_manager_hidden_mode_toggles_only_after_release_and_second_hold(monkeypatch) -> None:
    import artifact.modes.manager as manager_module

    monkeypatch.setattr(manager_module, "get_audio_engine", lambda: _SilentAudio())
    bus = EventBus()
    manager = ModeManager(
        StateMachine(),
        bus,
        Renderer(),
        AnimationEngine(),
        enable_prize_drum=True,
        prize_drum_client=LocalKioskStub(auto_auth_after_polls=None),
    )

    bus.emit(Event(EventType.KEYPAD_PRESS, {"key": "9"}, source="test"))
    manager.update(1999.0)
    assert not manager._prize_drum_active
    manager.update(1.0)
    assert manager._prize_drum_active
    assert manager.state == ManagerState.MODE_ACTIVE
    assert not bus.get_history(EventType.KEYPAD_INPUT)

    # Holding remains latched and cannot toggle again until a real KEYUP.
    manager.update(3000.0)
    assert manager._prize_drum_active
    bus.emit(Event(EventType.KEYPAD_RELEASE, {"key": "9"}, source="test"))
    bus.emit(Event(EventType.KEYPAD_PRESS, {"key": "9"}, source="test"))
    manager.update(2000.0)
    assert not manager._prize_drum_active


@pytest.mark.asyncio
async def test_hidden_mode_transition_keeps_main_lit_and_restores_selector_camera(
    monkeypatch,
) -> None:
    """Guard the cabinet regression where a hidden-mode transition left HDMI black."""
    import artifact.modes.manager as manager_module

    monkeypatch.setattr(manager_module, "get_audio_engine", lambda: _SilentAudio())
    bus = EventBus()
    manager = ModeManager(
        StateMachine(),
        bus,
        Renderer(),
        AnimationEngine(),
        enable_prize_drum=True,
        prize_drum_client=LocalKioskStub(auto_auth_after_polls=None),
    )
    manager.register_mode(_EventProbeMode)
    camera_edges: list[str] = []
    monkeypatch.setattr(manager, "_open_selector_camera", lambda: camera_edges.append("open"))
    monkeypatch.setattr(manager, "_close_selector_camera", lambda: camera_edges.append("close"))

    manager._change_state(ManagerState.MODE_SELECT)
    manager._selector_frame = np.full((128, 128, 3), 96, dtype=np.uint8)
    public_frame = np.zeros((128, 128, 3), dtype=np.uint8)
    manager.render_main(public_frame)
    assert public_frame.any()

    manager._enter_prize_drum()
    hidden_frame = np.zeros_like(public_frame)
    manager.render_main(hidden_frame)
    assert hidden_frame.any()
    assert camera_edges[-1] == "close"

    manager._exit_prize_drum()
    restored_frame = np.zeros_like(public_frame)
    manager.render_main(restored_frame)
    assert restored_frame.any()
    assert manager.state == ManagerState.MODE_SELECT
    assert camera_edges[-1] == "open"


@pytest.mark.asyncio
async def test_manager_defers_hidden_exit_until_reel_is_safe(monkeypatch) -> None:
    import artifact.modes.manager as manager_module

    monkeypatch.setattr(manager_module, "get_audio_engine", lambda: _SilentAudio())
    bus = EventBus()
    manager = ModeManager(
        StateMachine(),
        bus,
        Renderer(),
        AnimationEngine(),
        enable_prize_drum=True,
        prize_drum_client=LocalKioskStub(),
    )
    manager._enter_prize_drum()
    mode = manager._current_mode
    assert isinstance(mode, PrizeDrumMode)
    mode.screen = PrizeDrumScreen.SPINNING

    manager._on_prize_drum_toggle(Event(EventType.PRIZE_DRUM_TOGGLE))
    assert manager._pending_prize_drum_exit
    assert manager._prize_drum_active

    mode.screen = PrizeDrumScreen.RESULT
    manager.update(0.0)
    assert not manager._prize_drum_active


@pytest.mark.parametrize(
    ("flow", "boosts", "expected"),
    [
        (PrizeDrumFlow.GUEST, 2, 1),
        (PrizeDrumFlow.AUTH, 0, 1),
        (PrizeDrumFlow.AUTH, 1, 2),
        (PrizeDrumFlow.AUTH, 2, 3),
    ],
)
@pytest.mark.asyncio
async def test_allowance_flows_are_one_one_two_three(flow, boosts, expected) -> None:
    stub = LocalKioskStub(active_boosts=boosts, auto_auth_after_polls=1)
    mode = PrizeDrumMode(_context(), client=stub)
    mode.preferred_flow = flow
    mode.enter()
    await _settle(mode)
    if flow == PrizeDrumFlow.AUTH:
        mode.update(900.0)
        await _settle(mode)

    assert mode.screen == PrizeDrumScreen.READY
    assert mode._session is not None
    assert mode._session.allowance.total == expected
    assert mode._session.allowance.left == expected


@pytest.mark.asyncio
async def test_kp4_kp6_mirror_pair_selects_flow_once_and_persists() -> None:
    stub = LocalKioskStub(auto_auth_after_polls=None)
    mode = PrizeDrumMode(_context(), client=stub)
    mode.enter()
    await _settle(mode)
    assert mode.preferred_flow == PrizeDrumFlow.AUTH

    mode.handle_input(Event(EventType.ARCADE_RIGHT, source="numpad"))
    finish_task = mode._task
    mode.handle_input(Event(EventType.KEYPAD_INPUT, {"key": "6"}, source="keypad"))
    assert mode._task is finish_task
    assert mode.preferred_flow == PrizeDrumFlow.GUEST
    await _settle(mode)
    await _settle(mode)
    assert mode._session is not None
    assert mode._session.auth_mode == "guest"
    assert mode.preferred_flow == PrizeDrumFlow.GUEST


@pytest.mark.asyncio
async def test_kp4_forces_fresh_login_qr_from_authenticated_ready_session() -> None:
    """KP4 means "show login QR", even when the old session was Telegram."""
    stub = LocalKioskStub(auto_auth_after_polls=1)
    mode = PrizeDrumMode(_context(), client=stub)
    mode.enter()
    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.AUTH_QR
    mode.update(900.0)
    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.READY
    assert mode._session is not None and mode._session.authenticated
    old_session_id = mode._session.id

    mode.handle_input(Event(EventType.ARCADE_LEFT, source="numpad"))
    mode.handle_input(Event(EventType.KEYPAD_INPUT, {"key": "4"}, source="keypad"))
    assert mode.screen == PrizeDrumScreen.CONNECTING
    assert mode.preferred_flow == PrizeDrumFlow.AUTH
    await _settle(mode, frames=36)

    assert mode.screen == PrizeDrumScreen.AUTH_QR
    assert mode._auth_qr is not None
    assert mode._auth_qr.shape[0] >= 120
    assert mode._session is not None
    assert mode._session.id != old_session_id
    assert mode._session.auth_mode == "telegram"
    assert not mode._session.authenticated


@pytest.mark.asyncio
async def test_manager_forwards_numlock_off_kp8_and_mirror_pair_reprints_once(
    monkeypatch,
) -> None:
    """KP8 is ARCADE_UP without Num Lock and two events with Num Lock on."""
    import artifact.modes.manager as manager_module

    monkeypatch.setattr(manager_module, "get_audio_engine", lambda: _SilentAudio())
    bus = EventBus()
    manager = ModeManager(
        StateMachine(),
        bus,
        Renderer(),
        AnimationEngine(),
        enable_prize_drum=True,
        prize_drum_client=LocalKioskStub(),
    )
    manager._enter_prize_drum()
    mode = manager._current_mode
    assert isinstance(mode, PrizeDrumMode)
    mode.screen = PrizeDrumScreen.RESULT
    mode._last_print_data = {
        "type": "prize_drum",
        "mode": "prize_drum",
        "issue_id": "immutable-reprint-issue",
        "coupon_code": "VNVNC-KSK-REPRINT",
    }

    # Num Lock off: Linux exposes physical KP8 only as the Up event.
    bus.emit(Event(EventType.ARCADE_UP, source="numpad"))
    prints = bus.get_history(EventType.PRINT_START)
    assert len(prints) == 1
    assert prints[0].data["manual_reprint"] is True

    # Num Lock on mirrors ARCADE_UP + digit 8. The pending physical job is a
    # synchronous latch, so the pair can never enqueue a duplicate copy.
    bus.emit(Event(EventType.ARCADE_UP, source="numpad"))
    bus.emit(Event(EventType.KEYPAD_INPUT, {"key": "8"}, source="keypad"))
    assert len(bus.get_history(EventType.PRINT_START)) == 1


@pytest.mark.asyncio
async def test_spin_countdown_flashes_confetti_and_counts_3_2_1_before_motion() -> None:
    stub = LocalKioskStub(auto_auth_after_polls=None)
    context = _context()
    mode = PrizeDrumMode(context, client=stub)
    mode.preferred_flow = PrizeDrumFlow.GUEST
    mode.enter()
    await _settle(mode)
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode)

    assert mode.screen == PrizeDrumScreen.SPINNING
    assert mode._countdown_active
    assert mode._countdown_value() == 3
    assert mode._reel_position == 0.0
    assert mode._ticker_text() == "3"
    assert mode.get_lcd_text().strip() == "3"

    frame = np.zeros((128, 128, 3), dtype=np.uint8)
    mode.render_main(frame)
    assert np.count_nonzero(frame) > 12_000
    assert np.any(np.all(frame == np.asarray(RED), axis=2))
    assert np.any(np.all(frame == np.asarray(WHITE), axis=2))

    mode.update(900.0)
    assert mode._countdown_value() == 2
    assert mode._reel_position == 0.0
    mode.update(900.0)
    assert mode._countdown_value() == 1
    assert mode._reel_position == 0.0
    mode.update(900.0)
    assert not mode._countdown_active
    assert mode._reel_position == 0.0

    sounds = [event.data["sound"] for event in context.event_bus.get_history(EventType.SOUND_PLAY)]
    assert sounds[:3] == ["countdown_tick", "countdown_tick", "countdown_tick"]
    assert sounds[-2:] == ["countdown_go", "reel_start"]


@pytest.mark.asyncio
async def test_offline_issue_never_starts_reel_or_prints() -> None:
    stub = LocalKioskStub(online=False)
    context = _context()
    mode = PrizeDrumMode(context, client=stub)
    mode.preferred_flow = PrizeDrumFlow.GUEST
    mode.enter()
    await _settle(mode)

    assert mode.screen == PrizeDrumScreen.OFFLINE
    assert mode._motion is None
    assert not context.event_bus.get_history(EventType.PRINT_START)


@pytest.mark.asyncio
async def test_ambiguous_spin_retry_reuses_request_and_prints_committed_award_once() -> None:
    class CommitThenTimeoutClient(LocalKioskStub):
        def __init__(self) -> None:
            super().__init__(auto_auth_after_polls=None)
            self.create_calls = 0
            self.spin_request_ids: list[str] = []
            self._lost_first_response = False

        async def create_session(self, *, request_id: str, auth_mode: str) -> KioskSession:
            self.create_calls += 1
            return await super().create_session(request_id=request_id, auth_mode=auth_mode)

        async def spin(self, session_id: str, *, request_id: str) -> KioskSpinResult:
            self.spin_request_ids.append(request_id)
            result = await super().spin(session_id, request_id=request_id)
            if not self._lost_first_response:
                self._lost_first_response = True
                raise KioskClientError("NETWORK_ERROR", "RESPONSE LOST", retryable=True)
            return result

    client = CommitThenTimeoutClient()
    context = _context()
    mode = PrizeDrumMode(context, client=client)
    mode.preferred_flow = PrizeDrumFlow.GUEST
    mode.set_motion_debug(reduced=True)
    mode.enter()
    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.READY

    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    request_id = mode._pending_spin_request_id
    session_id = mode._pending_spin_session_id
    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.OFFLINE
    assert request_id and mode._pending_spin_request_id == request_id
    assert mode._pending_spin_session_id == session_id
    assert not mode.is_safe_to_exit

    # Neither a flow key nor a direct session reset may abandon the uncertain award.
    mode.handle_input(Event(EventType.KEYPAD_INPUT, {"key": "4"}, source="keypad"))
    mode._start_new_session()
    assert mode.preferred_flow == PrizeDrumFlow.GUEST
    assert client.create_calls == 1
    assert mode._pending_spin_request_id == request_id

    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.SPINNING
    assert mode._pending_spin_request_id is None
    assert client.spin_request_ids == [request_id, request_id]
    assert client._award_index == 1
    assert client.create_calls == 1

    mode.update(260.0)
    mode.update(220.0)
    assert mode.screen == PrizeDrumScreen.RESULT
    prints = context.event_bus.get_history(EventType.PRINT_START)
    assert len(prints) == 1
    assert prints[0].data["issue_id"] == "stub-issue-0001"


@pytest.mark.asyncio
async def test_nonretryable_spin_error_releases_session_boundary() -> None:
    class RejectedSpinClient(LocalKioskStub):
        async def spin(self, session_id: str, *, request_id: str) -> KioskSpinResult:
            raise KioskClientError("NO_SPINS_LEFT", "СПИНЫ ЗАКОНЧИЛИСЬ", retryable=False)

    mode = PrizeDrumMode(_context(), client=RejectedSpinClient())
    mode.preferred_flow = PrizeDrumFlow.GUEST
    mode.enter()
    await _settle(mode)
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode)

    assert mode.screen == PrizeDrumScreen.OFFLINE
    assert mode._pending_spin_request_id is None
    assert mode.is_safe_to_exit
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode, frames=24)
    assert mode.screen == PrizeDrumScreen.READY


@pytest.mark.asyncio
async def test_exit_cleanup_failure_is_consumed_and_logged(caplog) -> None:
    class FailingFinishClient(LocalKioskStub):
        async def finish_session(self, session_id: str) -> None:
            raise RuntimeError("finish failed")

    mode = PrizeDrumMode(_context(), client=FailingFinishClient())
    mode._session = KioskSession(
        id="cleanup-session",
        status="READY",
        auth_mode="guest",
        club_night=None,
        authenticated=False,
        user=None,
        allowance=SpinAllowance(),
    )
    mode.on_exit()
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert not mode._cleanup_tasks
    assert "Prize-drum exit cleanup failed" in caplog.text


@pytest.mark.asyncio
async def test_committed_award_drives_motion_print_and_clears_final_identity() -> None:
    stub = LocalKioskStub(active_boosts=0, auto_auth_after_polls=1)
    context = _context()
    mode = PrizeDrumMode(context, client=stub)
    mode.preferred_flow = PrizeDrumFlow.AUTH
    mode.set_motion_debug(reduced=True)
    mode.enter()
    await _settle(mode)
    mode.update(900.0)
    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.READY
    assert mode.authenticated_user is not None

    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    # The request is pending and the reel is completely stationary.
    assert mode.screen == PrizeDrumScreen.ISSUING
    assert mode._motion is None
    assert not context.event_bus.get_history(EventType.PRINT_START)

    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.SPINNING
    sounds = [event.data["sound"] for event in context.event_bus.get_history(EventType.SOUND_PLAY)]
    assert "reel_start" in sounds
    mode.update(260.0)
    assert mode.screen == PrizeDrumScreen.REVEAL
    mode.update(220.0)
    assert mode.screen == PrizeDrumScreen.RESULT

    print_events = context.event_bus.get_history(EventType.PRINT_START)
    assert len(print_events) == 1
    payload = print_events[0].data
    assert payload["type"] == payload["mode"] == "prize_drum"
    assert payload["issue_id"]
    assert payload["prize_title"]
    assert payload["coupon_code"] == payload["redeem_qr_payload"]
    assert payload["expires_at"]
    assert payload["club_night"] == "SIMULATOR"
    assert mode._session is None
    assert mode._auth is None
    assert mode._auth_qr is None
    assert mode.preferred_flow == PrizeDrumFlow.AUTH
    assert mode.authenticated_user is None
    assert mode._pending_finish_session_id is not None
    assert not mode.is_safe_to_exit

    await _settle(mode)
    assert mode._pending_finish_session_id is None

    sounds = [event.data["sound"] for event in context.event_bus.get_history(EventType.SOUND_PLAY)]
    assert "reel_win" in sounds


@pytest.mark.asyncio
async def test_runtime_emits_secret_safe_correlated_physical_soak_rows(caplog) -> None:
    caplog.set_level(logging.INFO, logger="artifact.modes.prize_drum")
    context = _context()
    mode = PrizeDrumMode(context, client=LocalKioskStub(auto_auth_after_polls=None))
    mode.preferred_flow = PrizeDrumFlow.GUEST
    mode.set_motion_debug(reduced=True)
    mode.enter()
    await _settle(mode)
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode)
    mode.update(260.0)
    mode.update(220.0)

    print_event = context.event_bus.get_history(EventType.PRINT_START)[0]
    issue_id = str(print_event.data["issue_id"])
    mode.handle_input(
        Event(
            EventType.PRINT_COMPLETE,
            {"type": "prize_drum", "issue_id": issue_id},
            source="printer",
        )
    )

    rows = [
        json.loads(record.getMessage().split(PRIZE_DRUM_AUDIT_PREFIX, 1)[1])
        for record in caplog.records
        if PRIZE_DRUM_AUDIT_PREFIX in record.getMessage()
    ]
    assert rows[0]["event"] == "session_created"
    assert rows[0]["session_auth_mode"] == "guest"
    award_rows = [row for row in rows if "issue_id" in row]
    assert [row["event"] for row in award_rows] == [
        "award_committed",
        "reel_landed",
        "print_complete",
    ]
    assert {row["issue_id"] for row in award_rows} == {issue_id}
    assert award_rows[1]["landed_prize_id"] == award_rows[0]["prize_id"]
    assert len(award_rows[0]["coupon_audit_id"]) == 16
    assert print_event.data["coupon_code"] not in caplog.text


@pytest.mark.asyncio
async def test_failed_final_logout_is_retried_before_next_guest_and_keeps_prize_qr() -> None:
    class FailOnceFinishClient(LocalKioskStub):
        def __init__(self) -> None:
            super().__init__(active_boosts=0, auto_auth_after_polls=1)
            self.finish_calls: list[str] = []
            self.create_calls = 0

        async def create_session(self, *, request_id: str, auth_mode: str) -> KioskSession:
            self.create_calls += 1
            return await super().create_session(request_id=request_id, auth_mode=auth_mode)

        async def finish_session(self, session_id: str) -> None:
            self.finish_calls.append(session_id)
            if len(self.finish_calls) == 1:
                raise KioskClientError("TEMPORARY", "retry", retryable=True)
            await super().finish_session(session_id)

    client = FailOnceFinishClient()
    context = _context()
    mode = PrizeDrumMode(context, client=client)
    mode.preferred_flow = PrizeDrumFlow.AUTH
    mode.set_motion_debug(reduced=True)
    mode.enter()
    await _settle(mode)
    mode.update(900.0)
    await _settle(mode)
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode)
    mode.update(260.0)
    mode.update(220.0)
    qr_before = mode._redeem_qr.copy()
    issue_id = mode._pending_print_issue_id

    await _settle(mode)
    assert mode.screen == PrizeDrumScreen.RESULT
    assert mode._pending_finish_session_id == client.finish_calls[0]
    assert mode._session is None
    assert mode.authenticated_user is None
    assert np.array_equal(mode._redeem_qr, qr_before)
    assert not mode.is_safe_to_exit
    assert client.create_calls == 1

    mode.handle_input(
        Event(
            EventType.PRINT_COMPLETE,
            {"type": "prize_drum", "issue_id": issue_id},
            source="printer",
        )
    )
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode, frames=24)

    assert len(client.finish_calls) == 2
    assert client.finish_calls[0] == client.finish_calls[1]
    assert mode._pending_finish_session_id is None
    assert client.create_calls == 2
    assert mode.preferred_flow == PrizeDrumFlow.AUTH
    assert mode.authenticated_user is None


@pytest.mark.asyncio
async def test_print_failure_keeps_redeem_qr_visible_and_kp8_reprints_same_issue() -> None:
    stub = LocalKioskStub(auto_auth_after_polls=1)
    context = _context()
    mode = PrizeDrumMode(context, client=stub)
    mode.preferred_flow = PrizeDrumFlow.GUEST
    mode.set_motion_debug(reduced=True)
    mode.enter()
    await _settle(mode)
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    await _settle(mode)
    mode.update(260.0)
    mode.update(220.0)
    assert mode.screen == PrizeDrumScreen.RESULT
    qr_before = mode._redeem_qr.copy()
    issue_id = mode._pending_print_issue_id
    assert issue_id

    # Unrelated completion/error signals cannot unlock this award.
    mode.handle_input(
        Event(
            EventType.PRINT_ERROR,
            {"type": "prize_drum", "issue_id": "some-other-award", "error": "paper"},
            source="printer",
        )
    )
    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))
    assert mode._pending_print_issue_id == issue_id
    assert len(context.event_bus.get_history(EventType.PRINT_START)) == 1

    # KP8 cannot duplicate a job that is still physically pending.
    mode.handle_input(Event(EventType.KEYPAD_INPUT, {"key": "8"}, source="keypad"))
    assert mode._pending_print_issue_id == issue_id
    assert len(context.event_bus.get_history(EventType.PRINT_START)) == 1

    mode.handle_input(
        Event(
            EventType.PRINT_ERROR,
            {"type": "prize_drum", "issue_id": issue_id, "error": "paper"},
            source="printer",
        )
    )
    assert mode.screen == PrizeDrumScreen.RESULT
    assert mode._motion is not None and mode._motion.complete
    assert np.array_equal(mode._redeem_qr, qr_before)
    assert mode._ticker_text() == "КОКТЕЙЛЬ"
    assert mode.get_lcd_text().strip() == "КОКТЕЙЛЬ"
    buffer = np.zeros((128, 128, 3), dtype=np.uint8)
    mode.render_main(buffer)
    assert buffer.any()

    # KP8 prints another physical copy of the exact same immutable issue.  A
    # fresh print key deliberately bypasses the physical-job dedupe ledger;
    # the prize/coupon itself is unchanged and no backend spin is performed.
    mode.handle_input(Event(EventType.KEYPAD_INPUT, {"key": "8"}, source="keypad"))
    retry_events = context.event_bus.get_history(EventType.PRINT_START)
    assert len(retry_events) == 2
    assert retry_events[-1].data["issue_id"] == issue_id
    assert retry_events[-1].data["coupon_code"] == retry_events[0].data["coupon_code"]
    assert retry_events[-1].data["manual_reprint"] is True
    assert retry_events[-1].data["reprint_number"] == 1
    assert retry_events[-1].data["print_job_key"] == f"{issue_id}:manual-reprint:1"
    assert mode._pending_print_issue_id == issue_id
    assert np.array_equal(mode._redeem_qr, qr_before)
    mode.handle_input(
        Event(
            EventType.PRINT_COMPLETE,
            {"type": "prize_drum", "issue_id": issue_id},
            source="printer",
        )
    )
    assert mode._pending_print_issue_id is None
    assert not mode._print_failed


def test_big_button_advances_after_print_failure_and_never_reprints() -> None:
    context = _context()
    mode = PrizeDrumMode(context, client=LocalKioskStub())
    mode._active = True
    mode.screen = PrizeDrumScreen.RESULT
    mode._print_failed = True
    mode._last_print_data = {
        "type": "prize_drum",
        "mode": "prize_drum",
        "issue_id": "immutable-issue",
        "coupon_code": "VNVNC-KSK-TEST",
    }
    mode._session = KioskSession(
        id="next-spin-session",
        status="READY",
        auth_mode="telegram",
        club_night="2026-08-28",
        authenticated=True,
        user=KioskUser(42, "ГОСТЬ"),
        allowance=SpinAllowance(base=1, total=2, used=1, left=1),
    )

    mode.handle_input(Event(EventType.BUTTON_PRESS, source="center"))

    assert mode.screen == PrizeDrumScreen.READY
    assert mode._award is None
    assert not context.event_bus.get_history(EventType.PRINT_START)


@pytest.mark.asyncio
async def test_exhausted_authenticated_identity_is_logged_out_with_clear_state() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode._active = True
    mode.preferred_flow = PrizeDrumFlow.AUTH
    exhausted = KioskSession(
        id="already-played",
        status="READY",
        auth_mode="telegram",
        club_night="2026-08-26",
        authenticated=True,
        user=KioskUser(42, "ГОСТЬ"),
        allowance=SpinAllowance(base=1, total=1, used=1, left=0),
    )

    mode._accept_session(exhausted)
    assert mode.screen == PrizeDrumScreen.NO_SPINS
    assert mode._session is None
    assert mode.authenticated_user is None
    assert mode._auth is None
    assert mode._auth_qr is None
    assert mode.preferred_flow == PrizeDrumFlow.AUTH
    assert mode._ticker_text() == "СПАСИБО"
    assert mode.get_lcd_text().strip() == "СПАСИБО"
    await _settle(mode)


@pytest.mark.parametrize("deltas", [[16.0], [33.333], [7.0, 41.0, 19.0], [1000.0]])
def test_reel_lands_exactly_on_server_selected_sector_for_varied_frame_delta(deltas) -> None:
    motion = ReelMotion(target_index=4, catalog_size=6)
    index = 0
    while not motion.complete:
        motion.advance(deltas[index % len(deltas)])
        index += 1
    assert motion.position == motion.target_position
    assert round(motion.position / motion.sector_step) % motion.catalog_size == 4


def test_reel_motion_is_long_and_has_two_distinct_false_near_hit_locks() -> None:
    motion = ReelMotion(target_index=4, catalog_size=6)
    assert motion.duration_ms == SPIN_DURATION_MS == 10800.0
    assert motion.catalog_passes == SPIN_CATALOG_PASSES == 11

    def sector_at(progress: float) -> float:
        return motion._position_at(progress) / motion.sector_step

    first_approach = sector_at(0.565)
    first_lock = sector_at(0.645)
    first_rekick = sector_at(0.710)
    second_approach = sector_at(0.765)
    second_lock = sector_at(0.840)
    second_rekick = sector_at(0.895)
    target = motion.target_position / motion.sector_step

    # Each brake beat stays within a fraction of one sector long enough to
    # read as a false stop, then receives a clear forward re-kick.
    assert abs(first_lock - first_approach) < 0.25
    assert first_rekick - first_lock > 2.0
    assert abs(second_lock - second_approach) < 0.25
    assert second_rekick - second_lock > 4.0

    false_one = round(first_lock) % motion.catalog_size
    false_two = round(second_lock) % motion.catalog_size
    winner = round(target) % motion.catalog_size
    assert len({false_one, false_two, winner}) == 3

    motion.elapsed_ms = motion.duration_ms * 0.625
    assert motion.near_hit_stage == 1
    assert motion.near_hit_strength > 0.9
    motion.elapsed_ms = motion.duration_ms * 0.810
    assert motion.near_hit_stage == 2
    assert motion.near_hit_strength > 0.9


def test_reel_opens_with_a_slow_random_excerpt_before_acceleration() -> None:
    motion = ReelMotion(target_index=4, catalog_size=6)
    hold_progress = SHOWCASE_HOLD_MS / SPIN_DURATION_MS
    excerpt_progress = (SHOWCASE_HOLD_MS + SHOWCASE_TRAVEL_MS) / SPIN_DURATION_MS

    assert motion._position_at(hold_progress) == 0.0
    assert motion._position_at(excerpt_progress) / SECTOR_STEP == pytest.approx(SHOWCASE_SECTORS)
    assert SHOWCASE_SECTORS > motion.catalog_size
    assert SHOWCASE_TRAVEL_MS / SHOWCASE_SECTORS >= 400.0


def test_visual_reel_is_long_randomized_repeated_and_circularly_non_adjacent() -> None:
    catalog = PrizeDrumMode.CATALOG
    first = build_visual_reel(catalog, seed="award-a", first_prize_id="COCKTL")
    replay = build_visual_reel(catalog, seed="award-a", first_prize_id="COCKTL")
    second = build_visual_reel(catalog, seed="award-b", first_prize_id="COCKTL")

    expected_count = VISUAL_DUPLICATES_PER_PRIZE
    assert len(first) == len(catalog) * expected_count
    assert first == replay
    assert [item[0] for item in first] != [item[0] for item in second]
    assert first[0][0] == second[0][0] == "COCKTL"
    for prize_id, _label in catalog:
        assert sum(item[0] == prize_id for item in first) == expected_count
    assert all(first[index][0] != first[(index + 1) % len(first)][0] for index in range(len(first)))
    # The slow opening comes from the long randomized tape, independently of
    # how many presentation prizes happen to be live this week.
    excerpt = [item[0] for item in first[:SHOWCASE_SECTORS]]
    assert len(excerpt) == SHOWCASE_SECTORS
    assert set(excerpt) <= {prize_id for prize_id, _label in catalog}


@pytest.mark.parametrize("catalog", [[], [("ONLY", "ЕДИНСТВЕННЫЙ")]])
def test_visual_reel_fails_closed_without_two_distinct_prizes(catalog) -> None:
    with pytest.raises(ValueError, match="at least two distinct prizes"):
        build_visual_reel(catalog, seed="invalid-catalog")


@pytest.mark.parametrize("winner_id", [prize_id for prize_id, _label in PrizeDrumMode.CATALOG])
def test_randomized_reel_false_hits_are_distinct_and_terminal_prize_is_exact(winner_id) -> None:
    reel = build_visual_reel(
        PrizeDrumMode.CATALOG,
        seed=f"server-award-{winner_id}",
        first_prize_id="COCKTL",
    )
    minimum = SHOWCASE_SECTORS + SPIN_CATALOG_PASSES * len(PrizeDrumMode.CATALOG)
    stop = find_reel_stop_index(reel, winner_id, minimum_index=minimum)
    false_one, false_two = find_false_hit_indices(
        reel,
        winner_index=stop,
        winner_prize_id=winner_id,
        catalog_size=len(PrizeDrumMode.CATALOG),
    )
    assert stop >= minimum
    assert reel[stop % len(reel)][0] == winner_id
    assert false_one < false_two < stop
    assert (
        len(
            {
                reel[false_one % len(reel)][0],
                reel[false_two % len(reel)][0],
                winner_id,
            }
        )
        == 3
    )

    motion = ReelMotion(
        target_index=0,
        catalog_size=len(PrizeDrumMode.CATALOG),
        target_virtual_index_override=stop,
        false_hit_virtual_indices=(false_one, false_two),
    )
    motion.advance(SPIN_DURATION_MS)
    assert round(motion.position / SECTOR_STEP) == stop
    assert reel[round(motion.position / SECTOR_STEP) % len(reel)][0] == winner_id


def test_reduced_motion_has_no_spatial_travel_and_exact_landing() -> None:
    motion = ReelMotion(
        target_index=2,
        catalog_size=6,
        duration_ms=260.0,
        reduced_motion=True,
    )
    assert motion.position == motion.target_position
    motion.advance(260.0)
    assert motion.complete
    assert motion.position == motion.target_position


def test_reel_uses_one_crisp_center_ticket_with_neighbor_slivers() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    frame = np.zeros((128, 128, 3), dtype=np.uint8)

    mode._render_reel(frame, 0.0)

    center_red = np.all(frame[31:98, 22:114] == np.asarray(RED), axis=2)
    upper_paper = np.all(frame[16:24, 16:112] == np.asarray(FADED_PAPER), axis=2)
    lower_paper = np.all(frame[104:112, 16:112] == np.asarray(FADED_PAPER), axis=2)
    assert center_red.sum() > 1800
    assert upper_paper.sum() > 250
    assert lower_paper.sum() > 250

    selected = mode._get_sector("COCKTL", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ", selected=True)
    neighbor = mode._get_sector("DEP1K", "ДЕПОЗИТ 1 000 Р", selected=False)
    assert selected.shape[1] > neighbor.shape[1]
    assert np.all(selected[3, 3] == np.asarray(RED))
    assert np.all(neighbor[3, 3] == np.asarray(FADED_PAPER))


def test_reel_selector_is_a_left_chevron_pointing_right() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    frame = np.full((128, 128, 3), np.asarray(BLACK), dtype=np.uint8)

    mode._draw_left_chevron(frame)

    assert np.all(frame[52, 3] == np.asarray(WHITE))
    assert np.all(frame[64, 12] == np.asarray(WHITE))
    assert np.all(frame[76, 3] == np.asarray(WHITE))
    white = np.all(frame == np.asarray(WHITE), axis=2)
    assert white[:, :20].any()
    assert not white[:, 20:].any()


def test_ready_screen_is_only_the_unobstructed_reel() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode.preferred_flow = PrizeDrumFlow.AUTH
    mode.screen = PrizeDrumScreen.READY
    mode._session = SimpleNamespace(
        allowance=SimpleNamespace(left=1, active_boosts=0),
    )
    reel = np.zeros((128, 128, 3), dtype=np.uint8)
    ready = np.zeros_like(reel)

    mode._render_reel(reel, 0.0)
    mode.render_main(ready)

    assert np.array_equal(ready, reel)
    assert mode._ticker_text() == "КОКТЕЙЛЬ"
    assert mode.get_lcd_text().strip() == "КОКТЕЙЛЬ"


def test_every_prize_drum_side_display_state_is_guest_facing_and_safe() -> None:
    font = load_font("cyrillic")
    compact_font = PixelFont(
        name="test_compact",
        char_height=font.char_height,
        char_width=font.char_width,
        spacing=0,
        glyphs=font.glyphs,
    )
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode._award = KioskAward(
        "ticker-award",
        KioskPrize("COCKTL", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ"),
        KioskCoupon("VNVNC-TICKER", None, "VNVNC-TICKER"),
    )
    expected_status = {
        PrizeDrumScreen.CONNECTING: "ПОДОЖДИ",
        PrizeDrumScreen.AUTH_QR: "СКАНИРУЙ QR",
        PrizeDrumScreen.NO_SPINS: "СПАСИБО",
        PrizeDrumScreen.OFFLINE: "НЕТ СВЯЗИ",
    }
    assert SIDE_DISPLAY_STATUS == expected_status
    for screen in PrizeDrumScreen:
        mode.screen = screen
        mode._session = SimpleNamespace(allowance=SimpleNamespace(left=3))
        text = mode._ticker_text()
        lcd = mode.get_lcd_text().strip()
        if screen in expected_status:
            assert text == expected_status[screen]
            assert lcd == expected_status[screen]
        else:
            assert text == "КОКТЕЙЛЬ"
            assert lcd == "КОКТЕЙЛЬ"
        assert not any(token in f"{text} {lcd}" for token in ("[", "]", ">", "<", "4", "6", "TG"))

        first = np.zeros((8, 48, 3), dtype=np.uint8)
        later = np.zeros_like(first)
        mode._time_in_mode = 0.0
        mode.render_ticker(first)
        mode._time_in_mode = 1900.0
        mode.render_ticker(later)
        lit = np.any(first != np.asarray(BLACK), axis=2)
        later_lit = np.any(later != np.asarray(BLACK), axis=2)
        assert lit.any(), screen
        assert later_lit.any(), screen
        assert np.flatnonzero(lit.any(axis=0)).min() >= 8, screen
        assert np.all(first[lit] == np.asarray(TICKER_GREEN)), screen
        assert np.all(later[later_lit] == np.asarray(TICKER_GREEN)), screen
        text_width = compact_font.measure_text(text)[0]
        if text_width > 40:
            assert not np.array_equal(first, later), screen
        else:
            assert np.array_equal(first, later), screen


@pytest.mark.parametrize("screen", [PrizeDrumScreen.AUTH_QR, PrizeDrumScreen.OFFLINE])
def test_long_status_ticker_pans_between_complete_safe_endpoints(screen) -> None:
    font = load_font("cyrillic")
    compact_font = PixelFont(
        name="test_compact_status",
        char_height=font.char_height,
        char_width=font.char_width,
        spacing=0,
        glyphs=font.glyphs,
    )
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode.screen = screen
    text = SIDE_DISPLAY_STATUS[screen]
    text_width = compact_font.measure_text(text)[0]
    assert text_width > 40

    reference = np.full((8, text_width, 3), np.asarray(BLACK), dtype=np.uint8)
    draw_text_bitmap(reference, text, 0, 0, TICKER_GREEN, compact_font, scale=1)
    first = np.zeros((8, 48, 3), dtype=np.uint8)
    last = np.zeros_like(first)
    mode._time_in_mode = 0.0
    mode.render_ticker(first)
    overflow = text_width - 40
    mode._time_in_mode = 800.0 + max(550.0, overflow * 110.0)
    mode.render_ticker(last)

    assert np.all(first[:, :8] == np.asarray(BLACK))
    assert np.all(last[:, :8] == np.asarray(BLACK))
    assert np.array_equal(first[:, 8:], reference[:, :40])
    assert np.array_equal(last[:, 8:], reference[:, -40:])


def test_side_displays_follow_every_visible_reel_sector_without_service_copy() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode.screen = PrizeDrumScreen.SPINNING
    banned = ("TG", "БУСТ", "VNVNC", "4", "6")

    for prize_id, _label in mode.CATALOG:
        index = next(
            index
            for index, (candidate_id, _candidate_label) in enumerate(mode._reel_items)
            if candidate_id == prize_id
        )
        mode._reel_position = float(index * SECTOR_STEP)
        ticker = mode._ticker_text()
        lcd = mode.get_lcd_text().strip()
        assert ticker == TICKER_PRIZE_HEADLINES[prize_id]
        assert lcd == LCD_PRIZE_HEADLINES[prize_id]
        assert not any(token in f"{ticker} {lcd}" for token in banned)

        frame = np.zeros((8, 48, 3), dtype=np.uint8)
        mode.render_ticker(frame)
        lit = np.any(frame != np.asarray(BLACK), axis=2)
        assert lit.any()
        assert np.flatnonzero(lit.any(axis=0)).min() >= 8


@pytest.mark.parametrize("active_boosts", [0, 1, 2, 8])
def test_ready_screen_never_exposes_auth_boost_or_key_hints(active_boosts) -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode.preferred_flow = PrizeDrumFlow.AUTH
    mode.screen = PrizeDrumScreen.READY
    mode._session = SimpleNamespace(
        allowance=SimpleNamespace(left=1 + min(active_boosts, 2), active_boosts=active_boosts)
    )

    reel = np.zeros((128, 128, 3), dtype=np.uint8)
    frame = np.zeros_like(reel)
    mode._render_reel(reel, mode._reel_position)
    mode.render_main(frame)
    assert np.array_equal(frame, reel)
    assert mode._ticker_text() == "КОКТЕЙЛЬ"
    assert mode.get_lcd_text().strip() == "КОКТЕЙЛЬ"


def test_all_ticket_headlines_are_deliberate_large_and_service_copy_free() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    assert set(TICKET_HEADLINES) == {prize_id for prize_id, _label in mode.CATALOG}
    banned = {"VNVNC", "TG", "БУСТ", "4", "6", "BAR", "SHOT", "TIX"}
    for prize_id, label in mode.CATALOG:
        lines = TICKET_HEADLINES[prize_id]
        assert 1 <= len(lines) <= 2
        assert max(scale for _text, scale in lines) >= 2
        assert not any(token in " ".join(text for text, _scale in lines) for token in banned)
        selected = mode._get_sector(prize_id, label, selected=True)
        foreground = np.all(selected == np.asarray(WHITE), axis=2)
        assert foreground.sum() > 150, prize_id


def test_revised_catalog_keeps_deposits_visual_only_and_distinguishes_shot_prizes() -> None:
    catalog = dict(PrizeDrumMode.CATALOG)
    selectable = {prize.id: prize.label for prize in LocalKioskStub.PRIZES}

    assert PRESENTATION_ONLY_PRIZE_IDS == {"DEP1K", "DEP2K"}
    assert PRESENTATION_ONLY_PRIZE_IDS <= set(catalog)
    assert PRESENTATION_ONLY_PRIZE_IDS.isdisjoint(selectable)
    assert catalog["SHOT1FREE"] == "БЕСПЛАТНЫЙ ШОТ"
    assert catalog["SHOTFR"] == "СЕТ ШОТОВ"
    assert selectable["SHOT1FREE"] == "БЕСПЛАТНЫЙ ШОТ"
    assert selectable["SHOTFR"] == "СЕТ ШОТОВ"
    assert TICKET_HEADLINES["SHOT1FREE"] != TICKET_HEADLINES["SHOTFR"]
    assert LCD_PRIZE_HEADLINES["SHOT1FREE"] == "БЕСПЛАТНЫЙ ШОТ"
    assert LCD_PRIZE_HEADLINES["SHOTFR"] == "СЕТ ШОТОВ"
    assert TICKET_DISCOUNT_PRIZE_ID == "TIX50"
    assert catalog["TIX50"] == "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ"
    assert selectable["TIX50"] == catalog["TIX50"]
    assert LCD_PRIZE_HEADLINES["TIX50"] == "СКИДКА 50%"
    assert TICKER_PRIZE_HEADLINES["TIX50"] == "-50%"


@pytest.mark.asyncio
async def test_local_stub_emits_production_shaped_tix50_text_code_metadata() -> None:
    stub = LocalKioskStub()
    tix50_index = next(
        index for index, prize in enumerate(stub.PRIZES) if prize.id == TICKET_DISCOUNT_PRIZE_ID
    )
    stub._award_index = tix50_index
    session = await stub.create_session(request_id="stub-tix50-session", auth_mode="guest")

    result = await stub.spin(session.id, request_id="stub-tix50-spin")

    coupon = result.award.coupon
    assert result.award.prize.id == "TIX50"
    assert coupon.code == f"260826-{tix50_index + 1:010d}-50"
    assert coupon.text_promo_code == coupon.code
    assert coupon.redemption_method == "text_code"
    assert coupon.show_prize_qr is False
    assert coupon.redeemable_via_staff is False
    assert coupon.redeem_qr_payload == coupon.code


def test_tix50_uses_text_code_ticket_result_without_creating_redeem_qr(monkeypatch) -> None:
    import artifact.modes.prize_drum as prize_drum_module

    context = _context()
    mode = PrizeDrumMode(context, client=LocalKioskStub())
    session = KioskSession(
        id="tix50-session",
        status="READY",
        auth_mode="guest",
        club_night="2026-08-28",
        authenticated=False,
        user=None,
        allowance=SpinAllowance(base=1, total=1, used=1, left=0),
    )
    code = "260826-1234567890-50"
    award = KioskAward(
        "tix50-award",
        KioskPrize(
            "TIX50",
            "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ",
            "Введи код в TicketsCloud при покупке.",
        ),
        KioskCoupon(code, "2026-09-05T07:00:00+03:00", code),
    )

    def fail_if_qr_is_requested(*_args, **_kwargs):
        pytest.fail("TIX50 must not create a redemption QR")

    monkeypatch.setattr(prize_drum_module, "make_qr_array", fail_if_qr_is_requested)
    mode._redeem_qr = np.full((76, 76, 3), (0, 255, 0), dtype=np.uint8)
    mode._accept_spin(KioskSpinResult(award, session))

    assert mode._redeem_qr is None
    assert mode.screen == PrizeDrumScreen.SPINNING
    mode.screen = PrizeDrumScreen.RESULT
    frame = np.zeros((128, 128, 3), dtype=np.uint8)
    mode.render_main(frame)

    red = np.all(frame == np.asarray(RED), axis=2)
    white = np.all(frame == np.asarray(WHITE), axis=2)
    green = np.all(frame == np.asarray((0, 255, 0)), axis=2)
    assert red.sum() > 5_000
    assert white[20:60].sum() > 250  # prominent -50% offer
    assert red[89:113, 14:114].sum() > 25  # readable text code in white stub
    assert not green.any()  # even a stale QR buffer cannot leak into this result
    assert mode._ticker_text() == "-50%"
    assert mode.get_lcd_text().strip() == "СКИДКА 50%"

    alternate = KioskAward(
        "tix50-award-2",
        award.prize,
        KioskCoupon("260826-9999999999-50", award.coupon.expires_at, "unused-qr"),
    )
    mode._award = alternate
    alternate_frame = np.zeros_like(frame)
    mode.render_main(alternate_frame)
    assert np.array_equal(frame[:89], alternate_frame[:89])
    assert not np.array_equal(frame[89:113], alternate_frame[89:113])

    mode._award = award
    mode._emit_print_once(award)
    print_data = context.event_bus.get_history(EventType.PRINT_START)[0].data
    assert print_data["coupon_code"] == code
    assert print_data["redeem_qr_payload"] == code


def test_neighbor_slivers_show_the_adjacent_prize_names() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    frame = np.zeros((128, 128, 3), dtype=np.uint8)
    mode._render_reel(frame, 0.0)
    upper_text = np.all(frame[7:24] == np.asarray((118, 18, 30)), axis=2)
    lower_text = np.all(frame[104:121] == np.asarray((118, 18, 30)), axis=2)
    assert upper_text.sum() > 20
    assert lower_text.sum() > 20


def test_allowance_parser_caps_bonus_at_two_and_total_at_three() -> None:
    allowance = SpinAllowance.from_mapping(
        {"base": 1, "bonus": 20, "total": 21, "used": 1, "left": 20, "active_boosts": 20}
    )
    assert allowance.base == 1
    assert allowance.bonus == 2
    assert allowance.total == 3
    assert allowance.used == 1
    assert allowance.left == 2


def test_flat_backend_spin_contract_parses_without_client_side_prize_choice() -> None:
    payload = {
        "success": True,
        "idempotent": False,
        "award": {
            "issue_id": "issue-1",
            "prize_id": "DEP1K",
            "prize_title": "ДЕПОЗИТ 1 000 ₽",
            "prize_label": "ДЕПОЗИТ 1 000 ₽",
            "prize_description": "До конца клубной ночи",
            "coupon_code": "VNVNC-ABCD-EFGH-JKLM",
            "redeem_qr_payload": "VNVNC-ABCD-EFGH-JKLM",
            "issued_at": "2026-08-26T23:00:00+03:00",
            "expires_at": "2026-08-27T07:00:00+03:00",
            "validity_slots": [],
            "source_credit": "BASE",
        },
        "session": {
            "id": "session-1",
            "status": "READY",
            "auth_mode": "guest",
            "authenticated": False,
            "allowance": {"base": 1, "bonus": 0, "total": 1, "used": 1, "left": 0},
        },
    }
    result = parse_spin_response(payload)
    assert result.award.id == "issue-1"
    assert result.award.prize.id == "DEP1K"
    assert result.award.prize.label == "ДЕПОЗИТ 1 000 ₽"
    assert result.award.coupon.code == "VNVNC-ABCD-EFGH-JKLM"
    assert result.session.allowance.left == 0


def test_tix50_parser_accepts_only_hardened_text_code_contract() -> None:
    code = "260826-1234567890-50"
    payload = {
        "success": True,
        "award": {
            "issue_id": "issue-tix50",
            "prize_id": "TIX50",
            "prize_label": "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ",
            "coupon_code": code,
            "redeem_qr_payload": None,
            "redemption_method": "text_code",
            "show_prize_qr": False,
            "redeemable_via_staff": False,
            "text_promo_code": code,
        },
        "session": {
            "id": "session-tix50",
            "status": "READY",
            "auth_mode": "guest",
            "authenticated": False,
            "allowance": {"base": 1, "total": 1, "used": 1, "left": 0},
        },
    }

    result = parse_spin_response(payload)

    assert result.award.prize.id == "TIX50"
    assert result.award.coupon.code == code
    assert result.award.coupon.text_promo_code == code
    assert result.award.coupon.redemption_method == "text_code"
    assert result.award.coupon.show_prize_qr is False
    assert result.award.coupon.redeemable_via_staff is False
    # Compatibility-only payload for print_data; PrizeDrumMode never QR-renders it.
    assert result.award.coupon.redeem_qr_payload == code


@pytest.mark.parametrize(
    "override",
    [
        {"text_promo_code": "260826-9999999999-50"},
        {"text_promo_code": None},
        {"redemption_method": "qr"},
        {"redemption_method": None},
        {"show_prize_qr": True},
        {"show_prize_qr": None},
        {"redeemable_via_staff": True},
        {"redeemable_via_staff": None},
        {"redeem_qr_payload": "260826-1234567890-50"},
    ],
)
def test_tix50_parser_rejects_any_qr_or_mutated_text_code_contract(override) -> None:
    code = "260826-1234567890-50"
    award = {
        "issue_id": "issue-tix50",
        "prize_id": "TIX50",
        "prize_label": "СКИДКА 50% НА БИЛЕТ",
        "coupon_code": code,
        "redeem_qr_payload": None,
        "redemption_method": "text_code",
        "show_prize_qr": False,
        "redeemable_via_staff": False,
        "text_promo_code": code,
    }
    award.update(override)
    payload = {
        "award": award,
        "session": {
            "id": "session-tix50",
            "status": "READY",
            "auth_mode": "guest",
            "authenticated": False,
            "allowance": {"base": 1, "total": 1, "used": 1, "left": 0},
        },
    }

    with pytest.raises(KioskClientError) as exc_info:
        parse_spin_response(payload)
    assert exc_info.value.code == "BAD_RESPONSE"


@pytest.mark.parametrize(
    ("coupon_code", "redeem_payload"),
    [
        ("VNVNC-ABCD", "vnvnc-abcd"),
        ("vnvnc-abcd", "vnvnc-abcd"),
        ("VNVNC-ABCD", "VNVNC-SOMETHING-ELSE"),
        ("VNVNC-ABCD", None),
    ],
)
def test_spin_parser_rejects_mutated_or_mismatched_redeem_payload(
    coupon_code,
    redeem_payload,
) -> None:
    payload = {
        "success": True,
        "award": {
            "issue_id": "issue-1",
            "prize_id": "COCKTL",
            "prize_label": "КОКТЕЙЛЬ",
            "coupon_code": coupon_code,
            "redeem_qr_payload": redeem_payload,
        },
        "session": {
            "id": "session-1",
            "status": "READY",
            "auth_mode": "guest",
            "authenticated": False,
            "allowance": {"base": 1, "total": 1, "used": 1, "left": 0},
        },
    }
    with pytest.raises(KioskClientError) as exc_info:
        parse_spin_response(payload)
    assert exc_info.value.code == "BAD_RESPONSE"


def test_rendered_auth_and_redeem_qrs_decode_to_exact_payloads() -> None:
    cv2 = pytest.importorskip("cv2")
    qrcode = pytest.importorskip("qrcode")
    from artifact.modes.prize_drum import make_qr_array

    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    provider_url = (
        "https://oauth.telegram.org/auth?client_id=123456789&redirect_uri="
        "https%3A%2F%2Fapi.vnvnc.ru%2Fapi%2Fartifact-kiosk%2Ftelegram%2Fcallback"
        "&response_type=code&scope=openid+profile+telegram%3Abot_access&state="
        "artifact_01K4Z8E6PKDNQFW11ZT6ABCTQV_session_01K4Z8DJ7RX5DZ7VXTY62T2K8C"
        "&code_challenge=Q0N-kZyC1UBfpYluydZvXAQetpl_cXa-GwbCOh7MtRU"
        "&code_challenge_method=S256&nonce=01K4Z8F29495KYDC7JD31K5W1P"
    )
    auth_url = "https://api.vnvnc.ru/k/AbCdEfGhIjKlMnOpQrStUv"
    assert len(auth_url) < 64
    assert (
        make_qr_array(
            provider_url,
            max_size=AUTH_QR_MAX_SIZE,
            telegram_brand=True,
            min_module_scale=3,
            error_correction="Q",
        )
        is None
    )
    mode._accept_auth(KioskAuth("pairing-id", auth_url))
    assert mode._auth_qr is not None

    reference = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=1,
        border=4,
    )
    reference.add_data(auth_url)
    reference.make(fit=True)
    qr_modules_with_quiet_zone = reference.modules_count + 8
    assert mode._auth_qr.shape == (123, 123, 3)
    assert mode._auth_qr.shape[0] % qr_modules_with_quiet_zone == 0
    physical_module_scale = mode._auth_qr.shape[0] // qr_modules_with_quiet_zone
    assert physical_module_scale == 3
    assert mode._auth_qr.shape[1:] == (mode._auth_qr.shape[0], 3)
    telegram_blue = np.all(mode._auth_qr == np.asarray((39, 159, 217)), axis=2)
    blue_columns = np.flatnonzero(telegram_blue.any(axis=0))
    assert blue_columns.size
    assert blue_columns[-1] - blue_columns[0] + 1 <= mode._auth_qr.shape[0] * 0.15
    quiet_zone = 4 * physical_module_scale
    assert np.all(mode._auth_qr[:quiet_zone] == 255)
    assert np.all(mode._auth_qr[-quiet_zone:] == 255)
    assert np.all(mode._auth_qr[:, :quiet_zone] == 255)
    assert np.all(mode._auth_qr[:, -quiet_zone:] == 255)
    assert mode._ticker_text() == "СКАНИРУЙ QR"
    auth_lcd = mode.get_lcd_text()
    assert len(auth_lcd) == 16
    assert auth_lcd.strip() == "СКАНИРУЙ QR"
    auth_ticker = np.zeros((8, 48, 3), dtype=np.uint8)
    mode.render_ticker(auth_ticker)
    auth_ticker_lit = np.any(auth_ticker != np.asarray(BLACK), axis=2)
    assert auth_ticker_lit.any()
    assert np.flatnonzero(auth_ticker_lit.any(axis=0)).min() >= 8
    auth_frame = np.zeros((128, 128, 3), dtype=np.uint8)
    mode.render_main(auth_frame)

    coupon = "VNVNC-K-TEST-ABCD"
    mode._redeem_qr = make_qr_array(coupon, max_size=76, telegram_brand=False)
    mode._award = KioskAward(
        "issue-qr",
        KioskPrize("COCKTL", "КОКТЕЙЛЬ"),
        KioskCoupon(coupon, None, coupon),
    )
    mode.screen = PrizeDrumScreen.RESULT
    redeem_frame = np.zeros((128, 128, 3), dtype=np.uint8)
    mode.render_main(redeem_frame)

    detector = cv2.QRCodeDetector()
    decoded = []
    for frame in (auth_frame, redeem_frame):
        # Nearest-neighbour enlargement models the physical 3 mm LED pixels.
        physical = np.repeat(np.repeat(frame, 8, axis=0), 8, axis=1)
        value, points, _ = detector.detectAndDecode(physical)
        assert points is not None
        decoded.append(value)
    assert decoded == [auth_url, coupon]


def test_canary_award_is_visibly_marked_on_displays_and_print_contract() -> None:
    context = _context()
    mode = PrizeDrumMode(context, client=LocalKioskStub())
    code = "TEST-VNVNC-000001"
    mode._award = KioskAward(
        "canary-issue",
        KioskPrize("COCKTL", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ", "ТЕСТОВЫЙ ЧЕК"),
        KioskCoupon(code, "2026-08-27T07:00:00+03:00", code),
        source_credit="CANARY",
        issued_at="2026-08-26T23:15:00+03:00",
        test_mode=True,
    )
    mode._redeem_qr = make_qr_array(code, max_size=76, telegram_brand=False)
    mode.screen = PrizeDrumScreen.RESULT
    frame = np.zeros((128, 128, 3), dtype=np.uint8)
    mode.render_main(frame)

    assert frame.any()
    assert mode._ticker_text() == "КОКТЕЙЛЬ"
    assert mode.get_lcd_text().strip() == "КОКТЕЙЛЬ"
    mode._emit_print_once(mode._award)
    print_event = context.event_bus.get_history(EventType.PRINT_START)[0]
    assert print_event.data["test_mode"] is True
    assert print_event.data["coupon_code"] == code


def test_reveal_burst_is_deterministic_bounded_and_reduced_motion_is_restrained() -> None:
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode._motion = ReelMotion(
        target_index=2,
        catalog_size=6,
        elapsed_ms=SPIN_DURATION_MS,
    )
    mode.screen = PrizeDrumScreen.REVEAL
    normal_frames = []
    for elapsed in (0.0, 90.0, 270.0, 550.0):
        mode._reveal_elapsed_ms = elapsed
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        mode.render_main(frame)
        assert frame.shape == (128, 128, 3)
        assert frame.any()
        normal_frames.append(frame)
    assert not np.array_equal(normal_frames[0], normal_frames[-1])

    mode._reduced_motion = True
    first = np.zeros((128, 128, 3), dtype=np.uint8)
    second = np.zeros_like(first)
    mode._reveal_elapsed_ms = 100.0
    mode.render_main(first)
    mode.render_main(second)
    assert np.array_equal(first, second)


def test_semantic_prize_drum_sounds_route_on_hardware_and_simulator() -> None:
    pytest.importorskip("pygame")
    from artifact.main import _route_prize_drum_sound as route_hardware
    from artifact.simulator.main import _route_prize_drum_sound as route_simulator

    expected_hardware = ["roulette_spin", "wheel_tick", "jackpot", "score_up"]
    hardware_calls = []
    for semantic in ("reel_start", "reel_tick", "reel_win", "bonus_ready"):
        assert route_hardware(
            Event(EventType.SOUND_PLAY, {"sound": semantic}),
            hardware_calls.append,
        )
    assert hardware_calls == expected_hardware

    class FakeAudio:
        def __init__(self):
            self.calls = []

        def __getattr__(self, name):
            return lambda: self.calls.append(name)

    audio = FakeAudio()
    for semantic in ("reel_start", "reel_tick", "reel_win", "bonus_ready"):
        assert route_simulator(audio, Event(EventType.SOUND_PLAY, {"sound": semantic}))
    assert audio.calls == [
        "play_roulette_spin",
        "play_wheel_tick",
        "play_jackpot",
        "play_score_up",
    ]


def test_production_signature_matches_backend_canonical_contract(monkeypatch) -> None:
    import artifact.services.vnvnc_kiosk as kiosk_module

    client = VNVNCKioskClient(
        base_url="https://api.vnvnc.ru",
        device_id="artifact-test",
        device_secret="top-secret",
    )
    monkeypatch.setattr(kiosk_module.time, "time", lambda: 1_700_000_000)
    monkeypatch.setattr(kiosk_module.uuid, "uuid4", lambda: SimpleNamespace(hex="nonce-1"))
    body = b'{"request_id":"r1"}'
    headers = client._signed_headers("POST", "/api/artifact-kiosk/session", body)
    canonical = "\n".join(
        (
            "POST",
            "/api/artifact-kiosk/session",
            "1700000000",
            "nonce-1",
            hashlib.sha256(body).hexdigest(),
        )
    ).encode()
    expected = hmac.new(b"top-secret", canonical, hashlib.sha256).hexdigest()
    assert headers["X-Artifact-Signature"] == expected


def test_production_client_accepts_tailscale_only_http_transport() -> None:
    client = VNVNCKioskClient(
        base_url="http://100.114.78.88:8085",
        device_id="artifact-test",
        device_secret="top-secret",
    )
    assert client.base_url == "http://100.114.78.88:8085"


@pytest.mark.parametrize(
    "base_url",
    (
        "http://api.vnvnc.ru",
        "http://82.38.148.239:8085",
        "http://192.168.2.1:8085",
    ),
)
def test_production_client_rejects_non_tailscale_http_transport(base_url: str) -> None:
    with pytest.raises(KioskConfigurationError):
        VNVNCKioskClient(
            base_url=base_url,
            device_id="artifact-test",
            device_secret="top-secret",
        )


def test_production_client_ignores_ambient_http_proxy(monkeypatch) -> None:
    import aiohttp

    captured = {}

    class FakeResponse:
        status = 200

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def json(self, *, content_type=None):
            return {"success": True}

    class FakeSession:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setenv("https_proxy", "http://legacy-proxy.invalid:40000")
    monkeypatch.setattr(aiohttp, "ClientSession", FakeSession)
    client = VNVNCKioskClient(
        base_url="https://api.vnvnc.ru",
        device_id="artifact-test",
        device_secret="top-secret",
    )

    result = asyncio.run(client._request("GET", "/health"))

    assert result == {"success": True}
    assert captured["trust_env"] is False
    assert captured["url"] == "https://api.vnvnc.ru/health"


class _EventProbeMode(BaseMode):
    def on_enter(self):
        pass

    def on_update(self, delta_ms):
        pass

    def on_input(self, event):
        return False

    def on_exit(self):
        pass


def test_base_mode_emit_event_uses_event_type_field() -> None:
    context = _context()
    seen = []
    context.event_bus.subscribe(EventType.SOUND_PLAY, lambda event: seen.append(event))
    mode = _EventProbeMode(context)
    mode.emit_event(EventType.SOUND_PLAY, {"sound": "tick"})
    assert seen[0].type == EventType.SOUND_PLAY
    assert seen[0].data == {"sound": "tick"}

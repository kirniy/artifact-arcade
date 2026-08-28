"""Hidden ФОТОБУДКА ВИНОВНИЦЫ physical prize-drum mode.

The backend commits an award before any reel motion starts.  The local reel is
only a deterministic presentation of that immutable result.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import random
import uuid
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Coroutine

import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageOps

from artifact.core.events import Event, EventType
from artifact.graphics.fonts import PixelFont, draw_text_bitmap, load_font
from artifact.graphics.primitives import draw_circle, draw_line, draw_rect, fill
from artifact.graphics.text_utils import (
    draw_centered_text,
    draw_wrapped_text,
    render_idle_style_ticker_text,
)
from artifact.modes.base import BaseMode, ModeContext
from artifact.services.vnvnc_kiosk import (
    KioskAuth,
    KioskAward,
    KioskClient,
    KioskClientError,
    KioskConfigurationError,
    KioskSession,
    KioskSpinResult,
    create_kiosk_client,
)

logger = logging.getLogger(__name__)
PRIZE_DRUM_AUDIT_PREFIX = "PRIZE_DRUM_AUDIT "


def _audit_prize_drum_event(event: str, **fields: Any) -> None:
    """Emit one secret-safe machine-readable physical-canary evidence row."""
    payload = {"event": str(event), **fields}
    logger.info(
        "%s%s",
        PRIZE_DRUM_AUDIT_PREFIX,
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
    )


RED = (204, 0, 24)
DEEP_RED = (91, 0, 15)
WHITE = (255, 255, 255)
OFF_WHITE = (248, 245, 239)
FADED_PAPER = (235, 226, 222)
PAPER_GRID = (224, 196, 199)
BLACK = (12, 9, 10)
MUTED_RED = (118, 18, 30)
TICKER_GREEN = (0, 255, 48)
AUTH_QR_MAX_SIZE = 128
COUNTDOWN_STEP_MS = 900.0
COUNTDOWN_TOTAL_MS = COUNTDOWN_STEP_MS * 3.0
SPIN_DURATION_MS = 14400.0
SPIN_CATALOG_PASSES = 11
SHOWCASE_HOLD_MS = 300.0
SHOWCASE_TRAVEL_MS = 4800.0
SHOWCASE_SECTORS = 8
VISUAL_DUPLICATES_PER_PRIZE = 3
PRESENTATION_ONLY_PRIZE_IDS = frozenset({"DEP1K", "DEP2K"})
TICKET_DISCOUNT_PRIZE_ID = "TIX50"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLASSIC_LOGO_PATH = (
    PROJECT_ROOT / "assets" / "logos" / "vnvnc-logo-classic-border-letters-black.png"
)

SECTOR_HEIGHT = 68
SECTOR_STEP = 72
SECTOR_WIDTH = 116
NEIGHBOR_SECTOR_HEIGHT = 64
NEIGHBOR_SECTOR_WIDTH = 106
REEL_CENTER_Y = 64
REEL_VIEW_TOP = 4
REEL_VIEW_BOTTOM = 124

# The reel is glanced at from several metres away, so each ticket has one job:
# name the prize. These deliberate display headlines preserve the backend's
# full canonical labels while cutting words instead of shrinking the type.
TICKET_HEADLINES: dict[str, tuple[tuple[str, int], ...]] = {
    "COCKTL": (("КОКТЕЙЛЬ", 2),),
    "DEP1K": (("ДЕПОЗИТ", 2), ("1 000 Р", 2)),
    "DEP2K": (("ДЕПОЗИТ", 2), ("2 000 Р", 2)),
    "MERCHFREE": (("МЕРЧ", 3),),
    "SHOT1FREE": (("БЕСПЛАТНЫЙ", 1), ("ШОТ", 3)),
    "SHOTFR": (("СЕТ", 3), ("ШОТОВ", 3)),
    "TIX1FREE": (("БИЛЕТ", 3), ("НА ОДНОГО", 2)),
    "TIX50": (("СКИДКА", 2), ("-50%", 3)),
}

LCD_PRIZE_HEADLINES: dict[str, str] = {
    "COCKTL": "КОКТЕЙЛЬ",
    "DEP1K": "ДЕПОЗИТ 1 000",
    "DEP2K": "ДЕПОЗИТ 2 000",
    "MERCHFREE": "МЕРЧ",
    "SHOT1FREE": "БЕСПЛАТНЫЙ ШОТ",
    "SHOTFR": "СЕТ ШОТОВ",
    "TIX1FREE": "БИЛЕТ НА ОДНОГО",
    "TIX50": "СКИДКА 50%",
}

TICKER_PRIZE_HEADLINES: dict[str, str] = {
    "COCKTL": "КОКТЕЙЛЬ",
    "DEP1K": "1 000 Р",
    "DEP2K": "2 000 Р",
    "MERCHFREE": "МЕРЧ",
    "SHOT1FREE": "ШОТ",
    "SHOTFR": "ШОТЫ",
    "TIX1FREE": "БИЛЕТ",
    "TIX50": "-50%",
}

class PrizeDrumScreen(Enum):
    CONNECTING = auto()
    AUTH_QR = auto()
    READY = auto()
    ISSUING = auto()
    SPINNING = auto()
    REVEAL = auto()
    RESULT = auto()
    NO_SPINS = auto()
    OFFLINE = auto()


SIDE_DISPLAY_STATUS: dict[PrizeDrumScreen, str] = {
    PrizeDrumScreen.CONNECTING: "ПОДОЖДИ",
    PrizeDrumScreen.AUTH_QR: "СКАНИРУЙ QR",
    PrizeDrumScreen.READY: "КОЛЕСО ФОРТУНЫ",
    PrizeDrumScreen.ISSUING: "ПОДОЖДИ",
    PrizeDrumScreen.NO_SPINS: "СПАСИБО",
    PrizeDrumScreen.OFFLINE: "НЕТ СВЯЗИ",
}


def _load_classic_logo(size: int = 46) -> NDArray[np.uint8] | None:
    """Load the canonical Classic mark once at native LED-friendly size."""
    try:
        with Image.open(CLASSIC_LOGO_PATH) as source:
            fitted = ImageOps.fit(
                source.convert("RGB"),
                (size, size),
                method=Image.Resampling.LANCZOS,
                centering=(0.5, 0.5),
            )
            return np.array(fitted, dtype=np.uint8)
    except Exception:
        logger.exception("Prize-drum Classic logo failed to load: %s", CLASSIC_LOGO_PATH)
        return None


class PrizeDrumFlow(Enum):
    AUTH = "telegram"
    GUEST = "guest"


PrizeSector = tuple[str, str]


def build_visual_reel(
    catalog: list[PrizeSector] | tuple[PrizeSector, ...],
    *,
    seed: str,
    duplicate_count: int = VISUAL_DUPLICATES_PER_PRIZE,
    first_prize_id: str | None = None,
) -> list[PrizeSector]:
    """Build the long VPISKA-style presentation tape for one spin.

    The tape is deliberately unrelated to backend probability: every public
    prize receives the same number of visual duplicates. The one circular
    multiset is freshly randomized, equal prizes can never touch (including
    the loop seam), and a stable award-derived seed makes an idempotent HTTP
    retry replay the exact same animation.
    """
    if duplicate_count < 1:
        raise ValueError("visual reel duplicate_count must be positive")

    unique: list[PrizeSector] = []
    seen_ids: set[str] = set()
    for prize_id, label in catalog:
        normalized_id = str(prize_id)
        if not normalized_id or normalized_id in seen_ids:
            continue
        unique.append((normalized_id, str(label)))
        seen_ids.add(normalized_id)
    if len(unique) < 2:
        raise ValueError("visual reel requires at least two distinct prizes")

    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:16], "big"))
    label_by_id = dict(unique)
    for _attempt in range(32):
        counts = {prize_id: duplicate_count for prize_id, _label in unique}
        reel_ids = _build_random_non_adjacent_block(
            counts,
            rng=rng,
            previous_id=None,
            forbidden_final_id=None,
        )
        if reel_ids[-1] != reel_ids[0]:
            break
    else:
        raise RuntimeError("could not close visual reel without an equal seam")
    reel = [(prize_id, label_by_id[prize_id]) for prize_id in reel_ids]

    if first_prize_id and first_prize_id in seen_ids:
        candidates = [index for index, item in enumerate(reel) if item[0] == first_prize_id]
        rotate_at = rng.choice(candidates)
        reel = reel[rotate_at:] + reel[:rotate_at]

    if any(reel[index][0] == reel[(index + 1) % len(reel)][0] for index in range(len(reel))):
        raise RuntimeError("visual reel adjacency invariant failed")
    return reel


def _build_random_non_adjacent_block(
    counts: dict[str, int],
    *,
    rng: random.Random,
    previous_id: str | None,
    forbidden_final_id: str | None,
) -> list[str]:
    """Randomized backtracking for one small repeated-prize block."""
    total = sum(counts.values())

    def search(last_id: str | None, remaining: int) -> list[str] | None:
        if remaining == 0:
            return [] if last_id != forbidden_final_id else None

        candidates = [
            prize_id for prize_id, count in counts.items() if count > 0 and prize_id != last_id
        ]
        rng.shuffle(candidates)
        # Consuming frequent IDs first prevents a duplicate being stranded at
        # the end, while the shuffle keeps equal-count choices unpredictable.
        candidates.sort(key=lambda prize_id: counts[prize_id], reverse=True)
        for prize_id in candidates:
            counts[prize_id] -= 1
            next_remaining = remaining - 1
            max_left = max(counts.values(), default=0)
            can_interleave = max_left <= (next_remaining + 1) // 2
            # The next slot cannot repeat prize_id, so its own remaining copies
            # have one fewer legal parity position than all other IDs.
            own_fits = counts[prize_id] <= next_remaining // 2
            if can_interleave and own_fits:
                suffix = search(prize_id, next_remaining)
                if suffix is not None:
                    return [prize_id, *suffix]
            counts[prize_id] += 1
        return None

    result = search(previous_id, total)
    if result is None:
        raise RuntimeError("could not construct non-adjacent visual reel block")
    return result


def find_reel_stop_index(
    reel: list[PrizeSector],
    prize_id: str,
    *,
    minimum_index: int,
) -> int:
    """Find a late exact occurrence with enough neighboring tape to render."""
    # The physical drum is circular. Search one complete future revolution in
    # virtual coordinates instead of materializing dozens of duplicate laps.
    start = max(2, minimum_index)
    for index in range(start, start + len(reel)):
        if reel[index % len(reel)][0] == prize_id:
            return index
    raise ValueError(f"prize {prize_id!r} is absent from the visual reel")


def find_false_hit_indices(
    reel: list[PrizeSector],
    *,
    winner_index: int,
    winner_prize_id: str,
    catalog_size: int,
) -> tuple[int, int]:
    """Choose two readable, distinct non-winning stops before the winner."""
    selected: list[int] = []
    excluded_ids = {winner_prize_id}
    desired = (
        winner_index - (2 * catalog_size + 2),
        winner_index - (catalog_size + 1),
    )
    lower_bound = SHOWCASE_SECTORS + 2
    for desired_index in desired:
        candidates: list[int] = []
        for radius in range(max(3, catalog_size * 2)):
            candidates.extend((desired_index - radius, desired_index + radius))
        match = next(
            (
                index
                for index in candidates
                if lower_bound <= index < winner_index
                and (not selected or index >= selected[-1] + 2)
                and reel[index % len(reel)][0] not in excluded_ids
            ),
            None,
        )
        if match is None:
            raise RuntimeError("visual reel has no safe false-hit sector")
        selected.append(match)
        excluded_ids.add(reel[match % len(reel)][0])
    return selected[0], selected[1]


@dataclass
class ReelMotion:
    """Deterministic slot-machine timeline with two false near-hit locks.

    The backend has already committed the award when this starts.  The local
    motion can therefore build anticipation without ever changing the result:
    a fast launch, two convincing brake/re-kick beats on other prizes, and a
    final mechanical overshoot that resolves to the exact server sector.
    """

    target_index: int
    catalog_size: int
    duration_ms: float = SPIN_DURATION_MS
    sector_step: int = SECTOR_STEP
    catalog_passes: int = SPIN_CATALOG_PASSES
    target_virtual_index_override: int | None = None
    false_hit_virtual_indices: tuple[int, int] | None = None
    reduced_motion: bool = False
    elapsed_ms: float = 0.0

    @property
    def target_virtual_index(self) -> int:
        if self.target_virtual_index_override is not None:
            return self.target_virtual_index_override
        return self.catalog_passes * self.catalog_size + self.target_index

    @property
    def target_position(self) -> float:
        return float(self.target_virtual_index * self.sector_step)

    @property
    def complete(self) -> bool:
        return self.elapsed_ms >= self.duration_ms

    @property
    def progress(self) -> float:
        return max(0.0, min(1.0, self.elapsed_ms / max(1.0, self.duration_ms)))

    @property
    def showcase_active(self) -> bool:
        """The opening beat presents a slow random excerpt of the loop."""
        return self.elapsed_ms < min(
            self.duration_ms,
            SHOWCASE_HOLD_MS + SHOWCASE_TRAVEL_MS,
        )

    @property
    def near_hit_stage(self) -> int:
        """Return the currently visible false-lock beat, or zero."""
        t = self.progress
        if 0.565 <= t < 0.655:
            return 1
        if 0.765 <= t < 0.850:
            return 2
        return 0

    @property
    def near_hit_strength(self) -> float:
        """A bounded visual pulse for the selector during each false lock."""
        t = self.progress
        pulses = ((0.625, 0.055), (0.810, 0.050))
        return max(
            (max(0.0, 1.0 - abs(t - center) / radius) for center, radius in pulses),
            default=0.0,
        )

    def advance(self, delta_ms: float) -> float:
        self.elapsed_ms = min(self.duration_ms, self.elapsed_ms + max(0.0, float(delta_ms)))
        return self.position

    @property
    def position(self) -> float:
        if self.complete:
            return self.target_position
        if self.reduced_motion:
            # Reduced motion preserves the result/reveal timing without spatial travel.
            return self.target_position

        return self._position_at(self.progress)

    def _position_at(self, t: float) -> float:
        """Evaluate absolute motion; frame rate can never alter the landing."""
        target_sector = float(self.target_virtual_index)
        # The first false lock lands two catalog positions before the winner;
        # the second lands one position before it on the following lap.  They
        # are different sectors and neither can accidentally reveal the award.
        if self.false_hit_virtual_indices is not None:
            near_one, near_two = map(float, self.false_hit_virtual_indices)
        else:
            near_one = max(1.0, target_sector - (2 * self.catalog_size + 2))
            near_two = max(near_one + 2.0, target_sector - (self.catalog_size + 1))
        near_two = min(near_two, target_sector - 1.0)
        relaunch_one = min(near_two - 0.8, near_one + 2.3)
        final_approach = max(near_two + 1.0, target_sector - 2.15)
        showcase_hold = min(0.05, SHOWCASE_HOLD_MS / max(1.0, self.duration_ms))
        showcase_end = min(
            0.45,
            (SHOWCASE_HOLD_MS + SHOWCASE_TRAVEL_MS) / max(1.0, self.duration_ms),
        )
        showcase_sector = min(float(SHOWCASE_SECTORS), near_one - 1.0)

        # Each tuple is (time, sector position, easing into the next tuple).
        # The opening pause + linear excerpt is explanatory without pretending
        # to enumerate a finite catalog. A custom blended curve then preserves
        # velocity while accelerating into the loop. Recoil uses strong
        # ease-in-out curves.
        anchors = (
            (0.000, 0.0, _linear),
            (showcase_hold, 0.0, _linear),
            (showcase_end, showcase_sector, _ease_showcase_to_spin),
            (0.565, near_one - 0.18, _ease_out_quint),
            (0.605, near_one + 0.10, _ease_in_out_quint),
            (0.645, near_one, _ease_out_quint),
            (0.710, relaunch_one, _ease_in_out_quint),
            (0.765, near_two - 0.16, _ease_out_quint),
            (0.800, near_two + 0.10, _ease_in_out_quint),
            (0.840, near_two, _ease_out_quint),
            (0.895, final_approach, _ease_in_out_quint),
            (0.965, target_sector + 0.14, _ease_in_out_quint),
            (1.000, target_sector, _ease_out_cubic),
        )
        t = max(0.0, min(1.0, t))
        for index in range(len(anchors) - 1):
            start_t, start_sector, easing = anchors[index]
            end_t, end_sector, _ = anchors[index + 1]
            if t <= end_t:
                local = (t - start_t) / max(1e-9, end_t - start_t)
                eased = easing(max(0.0, min(1.0, local)))
                sector = start_sector + (end_sector - start_sector) * eased
                return sector * self.sector_step
        return self.target_position


def _ease_in_out_quint(value: float) -> float:
    value = max(0.0, min(1.0, value))
    if value < 0.5:
        return 16.0 * value**5
    return 1.0 - ((-2.0 * value + 2.0) ** 5) / 2.0


def _ease_out_quint(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 5


def _ease_out_cubic(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 1.0 - (1.0 - value) ** 3


def _linear(value: float) -> float:
    return max(0.0, min(1.0, value))


def _ease_showcase_to_spin(value: float) -> float:
    """Accelerate without a velocity discontinuity after the linear lap."""
    value = max(0.0, min(1.0, value))
    return 0.11 * value + 0.89 * _ease_in_out_quint(value)


class PrizeDrumMode(BaseMode):
    """Exclusive hidden slot-machine mode, controlled by KP9 in ModeManager."""

    name = "prize_drum"
    display_name = "ПРИЗОВОЙ БАРАБАН"
    description = "Призовой барабан ФОТОБУДКИ ВИНОВНИЦЫ"
    icon = "▣"
    style = "vnvnc"
    requires_camera = False
    requires_ai = False

    CATALOG: tuple[tuple[str, str], ...] = (
        ("COCKTL", "БЕСПЛАТНЫЙ КОКТЕЙЛЬ"),
        ("DEP1K", "ДЕПОЗИТ 1 000 Р"),
        ("DEP2K", "ДЕПОЗИТ 2 000 Р"),
        ("MERCHFREE", "БЕСПЛАТНЫЙ МЕРЧ"),
        ("SHOT1FREE", "БЕСПЛАТНЫЙ ШОТ"),
        ("SHOTFR", "СЕТ ШОТОВ"),
        ("TIX1FREE", "БИЛЕТ НА ОДНОГО"),
        ("TIX50", "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ"),
    )

    def __init__(self, context: ModeContext, *, client: KioskClient | None = None) -> None:
        super().__init__(context)
        self.client = client
        self.screen = PrizeDrumScreen.CONNECTING
        self.preferred_flow = PrizeDrumFlow.AUTH
        self._session: KioskSession | None = None
        self._auth: KioskAuth | None = None
        self._award: KioskAward | None = None
        self._task: asyncio.Task[Any] | None = None
        self._task_kind: str | None = None
        self._cleanup_tasks: set[asyncio.Task[Any]] = set()
        self._poll_elapsed_ms = 0.0
        self._error_code = ""
        self._error_message = ""
        self._restart_after_finish = False
        self._pending_finish_session_id: str | None = None
        self._print_emitted_for: set[str] = set()
        self._pending_print_issue_id: str | None = None
        self._last_print_data: dict[str, Any] | None = None
        self._print_failed = False
        self._manual_reprint_count = 0
        self._identity_cleared = True
        self._pending_spin_request_id: str | None = None
        self._pending_spin_session_id: str | None = None

        motion_scale = max(0.1, float(os.getenv("ARTIFACT_DRUM_MOTION_SCALE", "1") or 1))
        self._motion_duration_ms = SPIN_DURATION_MS * motion_scale
        self._reduced_motion = os.getenv("ARTIFACT_REDUCED_MOTION", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if self._reduced_motion:
            self._motion_duration_ms = 260.0
        self._motion: ReelMotion | None = None
        self._reel_position = 0.0
        self._last_tick_index = 0
        self._tick_count = 0
        self._pointer_kick_ms = 0.0
        self._reveal_elapsed_ms = 0.0
        self._countdown_elapsed_ms = 0.0
        self._countdown_active = False
        self._countdown_last_value = 0
        self._nav_action: tuple[PrizeDrumFlow, float] | None = None

        self._catalog = list(self.CATALOG)
        self._reel_items = build_visual_reel(
            self._catalog,
            seed="vnvnc-photobooth-ready-v1",
            first_prize_id=self._catalog[0][0],
        )
        self._sector_cache: dict[tuple[str, str, bool], NDArray[np.uint8]] = {}
        self._auth_qr: NDArray[np.uint8] | None = None
        self._redeem_qr: NDArray[np.uint8] | None = None
        self._classic_logo = _load_classic_logo()

    @property
    def is_safe_to_exit(self) -> bool:
        return (
            self.screen
            not in {
                PrizeDrumScreen.ISSUING,
                PrizeDrumScreen.SPINNING,
                PrizeDrumScreen.REVEAL,
            }
            and self._task_kind not in {"spin", "finish"}
            and (
                self._pending_print_issue_id is None
                and self._pending_spin_request_id is None
                and self._pending_finish_session_id is None
            )
        )

    @property
    def spins_left(self) -> int:
        return self._session.allowance.left if self._session else 0

    @property
    def authenticated_user(self):
        return self._session.user if self._session else None

    def set_motion_debug(self, *, slow_factor: float = 1.0, reduced: bool = False) -> None:
        """Simulator QA hook for slow-motion and frame-by-frame inspection."""
        self._reduced_motion = bool(reduced)
        self._motion_duration_ms = 260.0 if reduced else SPIN_DURATION_MS * max(0.1, slow_factor)

    def on_enter(self) -> None:
        self.screen = PrizeDrumScreen.CONNECTING
        if self.client is None:
            try:
                self.client = create_kiosk_client()
            except KioskConfigurationError as exc:
                self._show_error(exc)
                return
        self._start_new_session()

    def on_exit(self) -> None:
        session_id = self._pending_finish_session_id or (
            self._session.id if self._session else None
        )
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self._task_kind = None
        self._pending_finish_session_id = None
        self._clear_identity()
        if session_id and self.client:
            try:
                loop = asyncio.get_running_loop()
                cleanup = loop.create_task(self.client.finish_session(session_id))
                self._cleanup_tasks.add(cleanup)
                cleanup.add_done_callback(self._consume_cleanup_task)
            except RuntimeError:
                pass

    def _consume_cleanup_task(self, task: asyncio.Task[Any]) -> None:
        """Consume exit-cleanup failures so asyncio never loses them silently."""
        self._cleanup_tasks.discard(task)
        try:
            task.result()
        except asyncio.CancelledError:
            logger.warning("Prize-drum exit cleanup was cancelled")
        except Exception:
            logger.warning("Prize-drum exit cleanup failed", exc_info=True)

    def on_update(self, delta_ms: float) -> None:
        self._drain_task()
        self._pointer_kick_ms = max(0.0, self._pointer_kick_ms - delta_ms)

        if self.screen == PrizeDrumScreen.AUTH_QR and self._task is None and self._session:
            self._poll_elapsed_ms += delta_ms
            if self._poll_elapsed_ms >= 900.0:
                self._poll_elapsed_ms = 0.0
                self._spawn("poll", self.client.get_session(self._session.id))

        elif self.screen in {PrizeDrumScreen.ISSUING, PrizeDrumScreen.SPINNING} and self._countdown_active:
            # Countdown starts at the physical button edge. Reel motion still
            # waits for the immutable server award, preserving authoritative
            # prize selection even when the network is briefly slow.
            self._advance_spin_countdown(delta_ms)

        elif self.screen == PrizeDrumScreen.SPINNING and self._motion:
            previous_index = math.floor(self._reel_position / SECTOR_STEP)
            self._reel_position = self._motion.advance(delta_ms)
            current_index = math.floor(self._reel_position / SECTOR_STEP)
            if current_index != previous_index:
                self._emit_reel_ticks(previous_index, current_index)
            if self._motion.complete:
                self._reel_position = self._motion.target_position
                landed_prize_id = self._reel_item_at(
                    int(round(self._reel_position / SECTOR_STEP))
                )[0]
                _audit_prize_drum_event(
                    "reel_landed",
                    issue_id=self._award.id if self._award else "",
                    prize_id=self._award.prize.id if self._award else "",
                    landed_prize_id=landed_prize_id,
                    test_mode=bool(self._award and self._award.test_mode),
                    ticks=self._tick_count,
                )
                self.screen = PrizeDrumScreen.REVEAL
                self._reveal_elapsed_ms = 0.0

        elif self.screen == PrizeDrumScreen.REVEAL:
            self._reveal_elapsed_ms += delta_ms
            if self._reveal_elapsed_ms >= (220.0 if self._reduced_motion else 560.0):
                self._finish_reveal()

    def on_input(self, event: Event) -> bool:
        if event.type in {EventType.PRINT_ERROR, EventType.PRINT_COMPLETE}:
            issue_id = str(event.data.get("issue_id") or "")
            event_mode = str(event.data.get("type") or event.data.get("mode") or "")
            if (
                event_mode != self.name
                or not self._pending_print_issue_id
                or issue_id != self._pending_print_issue_id
            ):
                return False
            self._pending_print_issue_id = None
            self._print_failed = event.type == EventType.PRINT_ERROR
            _audit_prize_drum_event(
                "print_error" if self._print_failed else "print_complete",
                issue_id=issue_id,
                prize_id=self._award.prize.id if self._award else "",
                test_mode=bool(self._award and self._award.test_mode),
            )
            return True

        if (
            event.type == EventType.ARCADE_UP
            or (
                event.type == EventType.KEYPAD_INPUT
                and str(event.data.get("key", "")) == "8"
            )
        ):
            # KP8 is the staff-only physical reprint action.  It deliberately
            # reuses the immutable award/coupon while assigning a fresh print
            # job key, so PrintManager prints another physical copy without
            # issuing a second prize.  The big red button remains progression.
            if self.screen == PrizeDrumScreen.RESULT:
                self._request_manual_reprint()
            return True

        flow = self._flow_for_event(event)
        if flow is not None:
            if (
                self._pending_spin_request_id is not None
                or self.screen
                in {
                    PrizeDrumScreen.ISSUING,
                    PrizeDrumScreen.SPINNING,
                    PrizeDrumScreen.REVEAL,
                }
                or (
                    self.screen == PrizeDrumScreen.RESULT
                    and (self._pending_print_issue_id is not None or self._print_failed)
                )
            ):
                return True
            self._select_flow(
                flow,
                input_source=event.source,
                input_event=event.type.name if isinstance(event.type, EventType) else str(event.type),
            )
            return True

        if event.type != EventType.BUTTON_PRESS:
            return False
        if self.screen == PrizeDrumScreen.OFFLINE:
            if self._pending_finish_session_id is not None:
                self._retry_pending_finish()
            elif self._pending_spin_request_id is not None:
                self._retry_pending_spin()
            else:
                self._start_new_session()
            return True
        if self.screen == PrizeDrumScreen.NO_SPINS:
            if self._task_kind == "finish":
                self._restart_after_finish = True
            else:
                self._start_new_session()
            return True
        if self.screen == PrizeDrumScreen.AUTH_QR:
            # Immediate status check; the reel remains still.
            if self._task is None and self._session:
                self._spawn("poll", self.client.get_session(self._session.id))
            return True
        if self.screen == PrizeDrumScreen.READY:
            self._request_spin()
            return True
        if self.screen == PrizeDrumScreen.RESULT:
            if self._pending_print_issue_id is not None:
                return True
            if self._session and self._session.allowance.left > 0:
                self._award = None
                self._redeem_qr = None
                self.screen = PrizeDrumScreen.READY
            elif self._task_kind == "finish":
                self._restart_after_finish = True
            else:
                self._start_new_session()
            return True
        return True

    def _flow_for_event(self, event: Event) -> PrizeDrumFlow | None:
        # Both detached GPIO direction switches and the USB numpad's mirrored
        # arrow events have produced phantom flow changes on the real cabinet.
        # Flow selection is therefore *digit-only*: KP4/KP6 with Num Lock on.
        # Every ARCADE_LEFT/RIGHT event is ignored regardless of source.
        if event.type in {EventType.ARCADE_LEFT, EventType.ARCADE_RIGHT}:
            return None
        flow: PrizeDrumFlow | None = None
        if event.type == EventType.KEYPAD_INPUT:
            key = str(event.data.get("key", ""))
            if key == "4":
                flow = PrizeDrumFlow.AUTH
            elif key == "6":
                flow = PrizeDrumFlow.GUEST
        if flow is None:
            return None

        return flow

    def _select_flow(
        self,
        flow: PrizeDrumFlow,
        *,
        input_source: str = "system",
        input_event: str = "",
    ) -> None:
        if self._pending_spin_request_id is not None:
            return
        current_screen = self.screen.name
        current_preference = self.preferred_flow.value
        session_auth_mode = self._session.auth_mode if self._session else ""
        session_authenticated = bool(self._session and self._session.authenticated)
        _audit_prize_drum_event(
            "flow_selected",
            requested_flow=flow.value,
            current_screen=current_screen,
            current_preference=current_preference,
            session_auth_mode=session_auth_mode,
            session_authenticated=session_authenticated,
            input_source=input_source,
            input_event=input_event,
        )
        same_session_flow = (
            self.preferred_flow == flow
            and self._session is not None
            and self._session.auth_mode == flow.value
        )
        if same_session_flow:
            if flow == PrizeDrumFlow.GUEST:
                return
            if self.screen in {PrizeDrumScreen.CONNECTING, PrizeDrumScreen.AUTH_QR}:
                return
            # KP4 is an explicit request for a fresh login QR, not merely a
            # preference toggle.  An authenticated Telegram session used to
            # satisfy this early-return and leave the guest looking at the
            # reel, which made the QR appear "broken".
        self.preferred_flow = flow
        if self._task_kind == "finish":
            self._restart_after_finish = True
            return
        self._start_new_session()

    def _start_new_session(self) -> None:
        if not self.client:
            return
        if self._pending_finish_session_id is not None:
            # Never put a new guest behind an identity whose server-side
            # session has not been confirmed closed.  Retry the same cleanup.
            self._restart_after_finish = True
            self._retry_pending_finish()
            return
        if self._pending_spin_request_id is not None:
            logger.warning(
                "Refusing to replace prize-drum session %s while spin request %s is unresolved",
                self._pending_spin_session_id,
                self._pending_spin_request_id,
            )
            return
        previous_session_id = self._session.id if self._session else None
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self._task_kind = None
        self._session = None
        self._auth = None
        self._award = None
        self._auth_qr = None
        self._redeem_qr = None
        self._pending_print_issue_id = None
        self._last_print_data = None
        self._print_failed = False
        self._manual_reprint_count = 0
        self._clear_identity()
        self._error_code = ""
        self._error_message = ""
        self.screen = PrizeDrumScreen.CONNECTING
        if previous_session_id:
            # Flow switches must revoke the old pairing before a new guest can
            # appear.  Only the AUTH/GUEST preference survives this boundary.
            self._begin_finish(previous_session_id, restart=True)
            return
        self._spawn(
            "create",
            self.client.create_session(
                request_id=str(uuid.uuid4()),
                auth_mode=self.preferred_flow.value,
            ),
        )

    def _request_spin(self) -> None:
        if not self.client or not self._session or self._session.allowance.left <= 0:
            return
        if self._pending_spin_request_id is None:
            self._pending_spin_request_id = str(uuid.uuid4())
            self._pending_spin_session_id = self._session.id
        self._countdown_elapsed_ms = 0.0
        self._countdown_active = not self._reduced_motion
        self._countdown_last_value = 3 if self._countdown_active else 0
        if self._countdown_active:
            self._emit_countdown_sound("countdown_tick", value=3)
        self.screen = PrizeDrumScreen.ISSUING
        self._spawn_pending_spin()

    def _retry_pending_spin(self) -> None:
        if (
            not self.client
            or not self._pending_spin_request_id
            or not self._pending_spin_session_id
        ):
            return
        if not self._session or self._session.id != self._pending_spin_session_id:
            self._clear_pending_spin()
            self._show_error(
                KioskClientError(
                    "SESSION_LOST",
                    "СЕССИЯ ПОТЕРЯНА - НАЧНИ ЗАНОВО",
                    retryable=False,
                )
            )
            return
        self.screen = PrizeDrumScreen.ISSUING
        self._spawn_pending_spin()

    def _spawn_pending_spin(self) -> None:
        if (
            not self.client
            or not self._pending_spin_request_id
            or not self._pending_spin_session_id
        ):
            return
        self._spawn(
            "spin",
            self.client.spin(
                self._pending_spin_session_id,
                request_id=self._pending_spin_request_id,
            ),
        )

    def _clear_pending_spin(self) -> None:
        self._pending_spin_request_id = None
        self._pending_spin_session_id = None

    def _begin_finish(self, session_id: str, *, restart: bool = False) -> None:
        """Track server cleanup until it is acknowledged; never abandon it."""
        if not self.client:
            return
        self._pending_finish_session_id = session_id
        self._restart_after_finish = self._restart_after_finish or restart
        self._retry_pending_finish()

    def _retry_pending_finish(self) -> None:
        if not self.client or not self._pending_finish_session_id or self._task is not None:
            return
        self._spawn(
            "finish",
            self.client.finish_session(self._pending_finish_session_id),
        )

    def _handle_finish_failure(self, error_code: str) -> None:
        logger.warning("Prize-drum session finish failed: %s", error_code)
        self._error_code = "SESSION_FINISH_FAILED"
        self._error_message = "СЕССИЯ НЕ ЗАКРЫТА - ЖМИ ПОВТОР"
        # Preserve an already-issued QR/result while cleanup is retried.  At a
        # session boundary there is no prize to preserve, so show retry state.
        if self.screen != PrizeDrumScreen.RESULT:
            self.screen = PrizeDrumScreen.OFFLINE

    def _spawn(self, kind: str, coroutine: Coroutine[Any, Any, Any]) -> None:
        if self._task is not None:
            coroutine.close()
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coroutine.close()
            self._show_error(KioskClientError("NO_EVENT_LOOP", "СВЯЗИ НЕТ - ПРИЗ НЕ РАЗЫГРАН"))
            return
        self._task_kind = kind
        self._task = loop.create_task(coroutine)

    def _drain_task(self) -> None:
        if not self._task or not self._task.done():
            return
        task = self._task
        kind = self._task_kind
        self._task = None
        self._task_kind = None
        try:
            result = task.result()
        except asyncio.CancelledError:
            return
        except KioskClientError as exc:
            if kind == "poll" and exc.code == "AUTH_PENDING":
                return
            if kind == "poll" and (exc.retryable or exc.code == "NETWORK_ERROR"):
                # A single damaged office-network packet must not destroy a
                # valid five-minute QR. Keep the pairing visible and retry.
                self._poll_elapsed_ms = -1200.0
                _audit_prize_drum_event(
                    "poll_retry",
                    code=exc.code,
                    preferred_flow=self.preferred_flow.value,
                )
                return
            if kind == "finish":
                self._handle_finish_failure(exc.code)
                return
            if kind == "spin":
                if not exc.retryable:
                    self._clear_pending_spin()
                self._show_error(exc)
                return
            self._show_error(exc)
            return
        except Exception as exc:
            if kind == "finish":
                self._handle_finish_failure(type(exc).__name__)
                return
            logger.exception("Unexpected prize-drum service failure")
            self._show_error(KioskClientError("CLIENT_ERROR", "СВЯЗИ НЕТ - ПОВТОРИ ЗАПРОС"))
            return

        if kind == "create":
            self._accept_created_session(result)
        elif kind == "auth":
            self._accept_auth(result)
        elif kind == "poll":
            self._accept_session(result)
        elif kind == "spin":
            self._accept_spin(result)
        elif kind == "finish":
            self._pending_finish_session_id = None
            self._error_code = ""
            self._error_message = ""
            if self._restart_after_finish:
                self._restart_after_finish = False
                self._start_new_session()

    def _accept_created_session(self, session: KioskSession) -> None:
        self._session = session
        self._identity_cleared = not session.authenticated
        _audit_prize_drum_event(
            "session_created",
            session_auth_mode=session.auth_mode,
            session_authenticated=bool(session.authenticated),
            session_status=session.status,
            preferred_flow=self.preferred_flow.value,
            spins_left=session.allowance.left,
        )
        if self.preferred_flow == PrizeDrumFlow.GUEST:
            if session.allowance.left <= 0:
                self._show_no_spins(session)
            else:
                self.screen = PrizeDrumScreen.READY
        elif session.authenticated:
            self._accept_session(session)
        else:
            self._spawn("auth", self.client.start_auth(session.id))

    def _accept_auth(self, auth: KioskAuth) -> None:
        if not auth.auth_url:
            self._show_error(KioskClientError("BAD_AUTH_URL", "TELEGRAM QR НЕ ГОТОВ"))
            return
        qr = make_qr_array(
            auth.auth_url,
            max_size=AUTH_QR_MAX_SIZE,
            telegram_brand=True,
            min_module_scale=3,
            error_correction="Q",
        )
        if qr is None:
            self._show_error(KioskClientError("QR_TOO_DENSE", "TELEGRAM QR СЛИШКОМ ДЛИННЫЙ"))
            return
        self._auth = auth
        self._auth_qr = qr
        self.screen = PrizeDrumScreen.AUTH_QR
        self._poll_elapsed_ms = 0.0
        _audit_prize_drum_event(
            "auth_qr_ready",
            auth_url_length=len(auth.auth_url),
            qr_height=int(qr.shape[0]),
            qr_width=int(qr.shape[1]),
            preferred_flow=self.preferred_flow.value,
        )

    def _accept_session(self, session: KioskSession) -> None:
        self._session = session
        if session.authenticated:
            self._identity_cleared = False
            if session.allowance.left <= 0:
                self._show_no_spins(session)
            else:
                self.screen = PrizeDrumScreen.READY
        else:
            self.screen = PrizeDrumScreen.AUTH_QR

    def _show_no_spins(self, session: KioskSession) -> None:
        """Log out an exhausted identity while preserving AUTH/GUEST preference."""
        session_id = session.id
        self._clear_identity()
        self._session = None
        self.screen = PrizeDrumScreen.NO_SPINS
        if self.client:
            self._begin_finish(session_id)

    def _accept_spin(self, result: KioskSpinResult) -> None:
        # This is the only point at which motion may start: award.id, coupon, and
        # expiry already exist on the backend.
        if (
            self._pending_spin_session_id is not None
            and result.session.id != self._pending_spin_session_id
        ):
            self._show_error(
                KioskClientError(
                    "BAD_RESPONSE",
                    "СЕРВЕР ВЕРНУЛ ЧУЖУЮ СЕССИЮ",
                )
            )
            return
        self._clear_pending_spin()
        self._session = result.session
        self._award = result.award
        coupon_audit_id = (
            result.award.coupon.code
            if result.award.test_mode
            else hashlib.sha256(result.award.coupon.code.encode("utf-8")).hexdigest()[:16]
        )
        _audit_prize_drum_event(
            "award_committed",
            issue_id=result.award.id,
            prize_id=result.award.prize.id,
            coupon_audit_id=coupon_audit_id,
            idempotent=bool(result.idempotent),
            test_mode=bool(result.award.test_mode),
        )
        if result.award.prize.id == TICKET_DISCOUNT_PRIZE_ID:
            # TicketsCloud consumes this award as a text promo code. A QR on
            # the result screen would imply the wrong staff-redemption flow.
            self._redeem_qr = None
        else:
            self._redeem_qr = make_qr_array(
                result.award.coupon.redeem_qr_payload,
                max_size=76,
                telegram_brand=False,
            )
        current_prize_id = self._reel_item_at(int(round(self._reel_position / SECTOR_STEP)))[0]
        target_index = self._ensure_catalog_prize(result.award)
        self._reel_items = build_visual_reel(
            self._catalog,
            seed=f"{result.award.id}:{result.award.coupon.code}",
            first_prize_id=current_prize_id,
        )
        minimum_stop = SHOWCASE_SECTORS + SPIN_CATALOG_PASSES * len(self._catalog)
        stop_index = find_reel_stop_index(
            self._reel_items,
            result.award.prize.id,
            minimum_index=minimum_stop,
        )
        false_hits = find_false_hit_indices(
            self._reel_items,
            winner_index=stop_index,
            winner_prize_id=result.award.prize.id,
            catalog_size=len(self._catalog),
        )
        self._motion = ReelMotion(
            target_index=target_index,
            catalog_size=len(self._catalog),
            duration_ms=self._motion_duration_ms,
            target_virtual_index_override=stop_index,
            false_hit_virtual_indices=false_hits,
            reduced_motion=self._reduced_motion,
        )
        self._reel_position = 0.0
        self._last_tick_index = 0
        self._tick_count = 0
        self._pointer_kick_ms = 150.0
        # A normal spin has already begun its 3-2-1 at the physical button
        # edge. If the server needed longer than the countdown, launch now;
        # otherwise the existing countdown completes before motion begins.
        if not self._countdown_active:
            self._emit_countdown_sound("reel_start")
        self.screen = PrizeDrumScreen.SPINNING

    def _advance_spin_countdown(self, delta_ms: float) -> None:
        """Run one deterministic 3-2-1 celebration before reel motion."""
        self._countdown_elapsed_ms = min(
            COUNTDOWN_TOTAL_MS,
            self._countdown_elapsed_ms + max(0.0, delta_ms),
        )
        value = self._countdown_value()
        if value != self._countdown_last_value and value > 0:
            self._countdown_last_value = value
            self._emit_countdown_sound("countdown_tick", value=value)
        if self._countdown_elapsed_ms >= COUNTDOWN_TOTAL_MS:
            self._countdown_active = False
            self._countdown_last_value = 0
            self._emit_countdown_sound("countdown_go")
            if self._motion is not None:
                self._emit_countdown_sound("reel_start")

    def _emit_countdown_sound(self, sound: str, **data: Any) -> None:
        self.context.event_bus.emit(
            Event(
                EventType.SOUND_PLAY,
                data={"sound": sound, **data},
                source="mode_prize_drum",
            )
        )

    def _countdown_value(self) -> int:
        if not self._countdown_active:
            return 0
        return max(1, 3 - int(self._countdown_elapsed_ms // COUNTDOWN_STEP_MS))

    def _emit_reel_ticks(self, previous: int, current: int) -> None:
        crossed = max(1, min(4, abs(current - previous)))
        self._tick_count += crossed
        self._last_tick_index = current
        self._pointer_kick_ms = 75.0
        self.context.event_bus.emit(
            Event(
                EventType.SOUND_PLAY,
                data={"sound": "reel_tick", "count": crossed},
                source="mode_prize_drum",
            )
        )

    def _finish_reveal(self) -> None:
        if not self._award:
            self._show_error(KioskClientError("MISSING_AWARD", "ПРИЗ НЕ НАЙДЕН"))
            return
        self.screen = PrizeDrumScreen.RESULT
        self.context.event_bus.emit(
            Event(
                EventType.SOUND_PLAY,
                data={"sound": "reel_win", "notes": 5},
                source="mode_prize_drum",
            )
        )
        self._emit_print_once(self._award)
        if self._session and self._session.allowance.left > 0:
            self.context.event_bus.emit(
                Event(
                    EventType.SOUND_PLAY,
                    data={"sound": "bonus_ready", "spins_left": self._session.allowance.left},
                    source="mode_prize_drum",
                )
            )
        if self._session and self._session.allowance.left <= 0:
            session_id = self._session.id
            self._clear_identity()
            # Keep the immutable award/QR visible, but remove all guest identity.
            self._session = None
            self._begin_finish(session_id)

    def _emit_print_once(self, award: KioskAward) -> None:
        if award.id in self._print_emitted_for:
            return
        self._print_emitted_for.add(award.id)
        print_data = {
            "type": "prize_drum",
            "mode": "prize_drum",
            "issue_id": award.id,
            "prize_id": award.prize.id,
            "prize_title": award.prize.label,
            "prize_label": award.prize.label,
            "prize_description": award.prize.description,
            "terms": award.prize.description,
            "coupon_code": award.coupon.code,
            "redeem_qr_payload": award.coupon.redeem_qr_payload,
            "issued_at": award.issued_at,
            "expires_at": award.coupon.expires_at,
            "club_night": self._session.club_night if self._session else None,
            "validity_slots": list(award.coupon.validity_slots),
            "test_mode": award.test_mode,
        }
        self._last_print_data = print_data
        self._emit_print(print_data)

    def _emit_print(self, print_data: dict[str, Any]) -> None:
        self._pending_print_issue_id = str(print_data["issue_id"])
        self._print_failed = False
        self.context.event_bus.emit(
            Event(
                EventType.PRINT_START,
                data=print_data,
                source="mode_prize_drum",
            )
        )

    def _request_manual_reprint(self) -> None:
        """Print another copy of the current immutable award via staff KP8."""
        if not self._last_print_data or self._pending_print_issue_id is not None:
            return
        self._manual_reprint_count += 1
        print_data = dict(self._last_print_data)
        issue_id = str(print_data["issue_id"])
        print_data.update(
            {
                "manual_reprint": True,
                "reprint_number": self._manual_reprint_count,
                "print_job_key": (
                    f"{issue_id}:manual-reprint:{self._manual_reprint_count}"
                ),
            }
        )
        _audit_prize_drum_event(
            "manual_reprint_requested",
            issue_id=issue_id,
            prize_id=self._award.prize.id if self._award else "",
            reprint_number=self._manual_reprint_count,
            test_mode=bool(self._award and self._award.test_mode),
        )
        self._emit_print(print_data)

    def _clear_identity(self) -> None:
        self._identity_cleared = True
        self._auth = None
        self._auth_qr = None

    def _show_error(self, exc: KioskClientError) -> None:
        _audit_prize_drum_event(
            "client_error",
            code=exc.code,
            task_kind=self._task_kind or "",
            screen=self.screen.name,
            preferred_flow=self.preferred_flow.value,
        )
        self._error_code = exc.code
        self._error_message = exc.message
        self.screen = PrizeDrumScreen.OFFLINE
        self._countdown_active = False
        self._countdown_elapsed_ms = 0.0
        self._countdown_last_value = 0
        self._motion = None
        self._reel_position = 0.0

    def _ensure_catalog_prize(self, award: KioskAward) -> int:
        for index, (prize_id, _) in enumerate(self._catalog):
            if prize_id == award.prize.id:
                self._catalog[index] = (prize_id, award.prize.label)
                return index
        self._catalog.append((award.prize.id, award.prize.label))
        return len(self._catalog) - 1

    def _reel_item_at(self, virtual_index: int) -> PrizeSector:
        if not self._reel_items:
            raise RuntimeError("visual reel is empty")
        return self._reel_items[virtual_index % len(self._reel_items)]

    # ------------------------------------------------------------------ render
    def render_main(self, buffer: NDArray[np.uint8]) -> None:
        if self.screen == PrizeDrumScreen.CONNECTING:
            self._render_connecting(buffer)
        elif self.screen == PrizeDrumScreen.AUTH_QR:
            self._render_auth(buffer)
        elif self.screen == PrizeDrumScreen.READY:
            self._render_ready(buffer)
        elif self.screen == PrizeDrumScreen.ISSUING:
            if self._countdown_active:
                self._render_spin_countdown(buffer)
            else:
                self._render_connecting(buffer)
        elif self.screen == PrizeDrumScreen.SPINNING:
            if self._countdown_active:
                self._render_spin_countdown(buffer)
            else:
                self._render_reel(buffer, self._reel_position)
                self._render_spin_sparks(buffer)
        elif self.screen == PrizeDrumScreen.REVEAL:
            self._render_reveal(buffer)
        elif self.screen == PrizeDrumScreen.RESULT:
            self._render_result(buffer)
        elif self.screen == PrizeDrumScreen.NO_SPINS:
            self._render_no_spins(buffer)
        else:
            self._render_offline(buffer)

    def render_ticker(self, buffer: NDArray[np.uint8]) -> None:
        buffer[:] = BLACK
        text = self._ticker_text()
        self._render_safe_ticker_text(buffer, text)

    def get_lcd_text(self) -> str:
        prize = self._side_display_prize()
        if prize:
            prize_id, label = prize
            text = LCD_PRIZE_HEADLINES.get(prize_id, _short_prize_label(label))
            return text.center(16)[:16]
        return self._status_text().center(16)[:16]

    def _ticker_text(self) -> str:
        prize = self._side_display_prize()
        if prize:
            prize_id, label = prize
            return TICKER_PRIZE_HEADLINES.get(prize_id, _short_prize_label(label))
        return self._status_text()

    def _status_text(self) -> str:
        countdown = self._countdown_value()
        if countdown:
            return str(countdown)
        return SIDE_DISPLAY_STATUS.get(self.screen, "ПОДОЖДИ")

    def _render_safe_ticker_text(
        self,
        buffer: NDArray[np.uint8],
        text: str,
        *,
        safe_left: int = 8,
    ) -> None:
        """Show real guest copy without ever touching the bad left segment.

        The cabinet has only 40 readable columns after its calibrated 8-column
        seam. Short copy stays perfectly static. Longer exact phrases pan
        gently between readable endpoints, with a hold at each end, so the
        wording is never abbreviated and no technical activity glyphs leak
        back into the guest experience.
        """
        safe_left = max(0, min(buffer.shape[1] - 1, safe_left))
        available_width = buffer.shape[1] - safe_left
        full_font = load_font("cyrillic")
        compact_font = PixelFont(
            name=f"{full_font.name}_prize_drum_safe",
            char_height=full_font.char_height,
            char_width=full_font.char_width,
            spacing=0,
            glyphs=full_font.glyphs,
        )
        compact_width, _ = compact_font.measure_text(text)
        if compact_width <= available_width:
            render_idle_style_ticker_text(
                buffer,
                text,
                TICKER_GREEN,
                self._time_in_mode,
                compact_static=True,
                safe_left=safe_left,
            )
            return

        overflow = compact_width - available_width
        hold_ms = 800.0
        travel_ms = max(550.0, overflow * 110.0)
        cycle_ms = 2.0 * (hold_ms + travel_ms)
        phase = self._time_in_mode % cycle_ms
        if phase < hold_ms:
            offset = 0
        elif phase < hold_ms + travel_ms:
            offset = round(overflow * (phase - hold_ms) / travel_ms)
        elif phase < 2.0 * hold_ms + travel_ms:
            offset = overflow
        else:
            offset = round(
                overflow
                * (1.0 - (phase - (2.0 * hold_ms + travel_ms)) / travel_ms)
            )
        draw_text_bitmap(
            buffer[:, safe_left:],
            text,
            -offset,
            0,
            TICKER_GREEN,
            compact_font,
            scale=1,
        )

    def _lcd_prize_headline(self) -> str:
        prize = self._side_display_prize()
        if not prize:
            return ""
        prize_id, label = prize
        return LCD_PRIZE_HEADLINES.get(prize_id, _short_prize_label(label))

    def _side_display_prize(self) -> tuple[str, str] | None:
        if self.screen in {PrizeDrumScreen.REVEAL, PrizeDrumScreen.RESULT} and self._award:
            return self._award.prize.id, self._award.prize.label
        if self.screen == PrizeDrumScreen.SPINNING and self._reel_items:
            if self._countdown_active:
                return None
            index = int(round(self._reel_position / SECTOR_STEP))
            return self._reel_item_at(index)
        return None

    def _render_connecting(self, buffer: NDArray[np.uint8]) -> None:
        """A text-free mechanical loader keeps startup quiet and unbranded."""
        fill(buffer, OFF_WHITE)
        draw_rect(buffer, 2, 2, 124, 124, RED, filled=False, thickness=3)
        phase = int(self._time_in_mode / 180.0) % 8
        points = (
            (64, 37),
            (82, 44),
            (90, 64),
            (82, 84),
            (64, 91),
            (46, 84),
            (38, 64),
            (46, 44),
        )
        for index, (x, y) in enumerate(points):
            color = RED if index == phase else MUTED_RED
            size = 3 if index == phase else 2
            draw_circle(buffer, x, y, size, color)

    def _render_auth(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, OFF_WHITE)
        if self._auth_qr is not None:
            _blit_centered(
                buffer,
                self._auth_qr,
                y=(buffer.shape[0] - self._auth_qr.shape[0]) // 2,
            )

    def _render_ready(self, buffer: NDArray[np.uint8]) -> None:
        """Large idle title over a slow, text-free looping ticket drum."""
        fill(buffer, BLACK)
        draw_rect(buffer, 2, 2, 124, 124, RED, filled=False, thickness=3)
        draw_rect(buffer, 6, 6, 116, 116, OFF_WHITE, filled=True)

        # Blank sectors move continuously behind the title. Their notches and
        # perforation communicate a physical drum without suggesting a prize.
        idle_offset = int((self._time_in_mode * 0.018) % 52.0)
        for sector_index in range(-2, 4):
            center_y = 9 + sector_index * 52 + idle_offset
            top = center_y - 22
            sector_color = RED if sector_index % 2 == 0 else OFF_WHITE
            ink = WHITE if sector_color == RED else DEEP_RED
            draw_rect(buffer, 9, top, 110, 44, sector_color, filled=True)
            draw_rect(buffer, 9, top, 110, 44, ink, filled=False, thickness=2)
            draw_circle(buffer, 9, center_y, 5, BLACK)
            draw_circle(buffer, 118, center_y, 5, BLACK)
            for x in range(19, 113, 12):
                draw_rect(buffer, x, top + 6, 6, 2, ink)
                draw_rect(buffer, x, top + 36, 6, 2, ink)

        # Opaque title plate leaves the moving sector above and below visible.
        draw_rect(buffer, 8, 34, 112, 58, BLACK, filled=True)
        draw_rect(buffer, 8, 34, 112, 58, RED, filled=False, thickness=2)
        draw_centered_text(buffer, "КОЛЕСО", 43, WHITE, scale=3)
        draw_centered_text(buffer, "ФОРТУНЫ", 69, WHITE, scale=2)

    def _render_spin_countdown(self, buffer: NDArray[np.uint8]) -> None:
        """Full-screen red/white flash, huge numeral, and falling confetti."""
        value = self._countdown_value()
        step_elapsed = self._countdown_elapsed_ms % COUNTDOWN_STEP_MS
        flash = step_elapsed < 105.0
        background = WHITE if flash else (RED if value % 2 else OFF_WHITE)
        foreground = RED if flash or value % 2 == 0 else WHITE
        fill(buffer, background)

        # Deterministic particles keep the frame stable at 60fps and avoid
        # allocating/randomizing in the render loop. They travel behind the
        # numeral so the one essential piece of information remains dominant.
        progress = self._countdown_elapsed_ms / COUNTDOWN_TOTAL_MS
        for index in range(26):
            seed_x = (index * 37 + 11) % 124
            speed = 1.35 + (index % 5) * 0.22
            y = int(((progress * speed * 178.0) + index * 19) % 154) - 13
            x = 2 + seed_x
            color = WHITE if background == RED else RED
            if index % 3 == 0:
                draw_rect(buffer, x, y, 2, 5, color)
            elif index % 3 == 1:
                draw_rect(buffer, x, y, 4, 2, color)
            else:
                draw_circle(buffer, x, y, 2, color)

        # A short overshoot settles immediately after each flash: strong
        # feedback without making a frequently repeated sequence feel gummy.
        scale = 11 if step_elapsed < 165.0 else 10
        font = load_font("cyrillic")
        base_width, base_height = font.measure_text(str(value))
        glyph_width, glyph_height = base_width * scale, base_height * scale
        x = (buffer.shape[1] - glyph_width) // 2
        y = max(4, (128 - glyph_height) // 2)
        for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
            draw_text_bitmap(buffer, str(value), x + dx, y + dy, BLACK, font, scale=scale)
        draw_text_bitmap(buffer, str(value), x, y, foreground, font, scale=scale)
        draw_rect(buffer, 2, 2, 124, 124, foreground, filled=False, thickness=3)

    def _render_reel(self, buffer: NDArray[np.uint8], position: float) -> None:
        fill(buffer, BLACK)
        draw_rect(buffer, 1, REEL_VIEW_TOP, 126, REEL_VIEW_BOTTOM - REEL_VIEW_TOP, OFF_WHITE)
        for grid_x in range(7, 126, 12):
            draw_line(buffer, grid_x, REEL_VIEW_TOP + 2, grid_x, REEL_VIEW_BOTTOM - 2, PAPER_GRID)
        for grid_y in range(REEL_VIEW_TOP + 7, REEL_VIEW_BOTTOM - 1, 12):
            draw_line(buffer, 3, grid_y, 124, grid_y, PAPER_GRID)
        center_index = int(round(position / SECTOR_STEP))
        for virtual_index in range(center_index - 2, center_index + 3):
            prize_id, label = self._reel_item_at(virtual_index)
            center_y = int(round(REEL_CENTER_Y + virtual_index * SECTOR_STEP - position))
            selected = virtual_index == center_index
            card = self._get_sector(prize_id, label, selected=selected)
            top = center_y - card.shape[0] // 2
            card_x = (buffer.shape[1] - card.shape[1]) // 2
            _blit_clipped(buffer, card, card_x, top, REEL_VIEW_TOP, REEL_VIEW_BOTTOM)

        draw_rect(
            buffer,
            1,
            REEL_VIEW_TOP,
            126,
            REEL_VIEW_BOTTOM - REEL_VIEW_TOP,
            BLACK,
            filled=False,
            thickness=2,
        )
        draw_rect(
            buffer,
            3,
            REEL_VIEW_TOP + 2,
            122,
            REEL_VIEW_BOTTOM - REEL_VIEW_TOP - 4,
            RED,
            filled=False,
        )
        self._draw_left_chevron(buffer)

    def _render_spin_sparks(self, buffer: NDArray[np.uint8]) -> None:
        """Fast deterministic edge sparks reinforce motion without hiding prizes."""
        if self._reduced_motion or self._motion is None:
            return
        elapsed = self._motion.elapsed_ms
        for index in range(22):
            lifetime = 420.0 + (index % 5) * 75.0
            phase = ((elapsed + index * 97.0) % lifetime) / lifetime
            direction = -1 if index % 2 else 1
            y_origin = 8 + ((index * 31) % 111)
            y = int(round(y_origin + direction * phase * (10 + index % 7)))
            left = index % 4 < 2
            x = int(round((5 + phase * 12) if left else (122 - phase * 12)))
            color = WHITE if index % 3 else RED
            length = 2 + (index % 4)
            if 4 <= y <= 123:
                draw_line(
                    buffer,
                    x,
                    y,
                    x + (length if left else -length),
                    y - direction * length,
                    color,
                    thickness=1,
                )

        # The selector gets a short starburst on every mechanical tick and
        # stronger false-near-hit locks. It is a payoff cue, never decoration
        # over the prize name itself.
        strength = max(
            self._motion.near_hit_strength,
            min(1.0, self._pointer_kick_ms / 75.0),
        )
        if strength > 0.05:
            reach = 5 + int(round(8 * strength))
            for dx, dy in ((1, 0), (1, 1), (1, -1)):
                draw_line(buffer, 15, 64, 15 + dx * reach, 64 + dy * reach, WHITE)

    def _render_reveal(self, buffer: NDArray[np.uint8]) -> None:
        if self._motion:
            shake = 0.0
            if not self._reduced_motion and self._reveal_elapsed_ms < 260.0:
                impacts = (0.0, -3.0, 2.0, -1.0, 1.0, 0.0)
                impact_index = min(len(impacts) - 1, int(self._reveal_elapsed_ms / 45.0))
                shake = impacts[impact_index]
            self._render_reel(buffer, self._motion.target_position + shake)
        flash_phase = int(self._reveal_elapsed_ms / 90.0) % 2
        color = WHITE if flash_phase == 0 else RED
        draw_rect(buffer, 2, 2, 124, 124, color, filled=False, thickness=4)
        self._render_win_burst(buffer)

    def _render_win_burst(self, buffer: NDArray[np.uint8]) -> None:
        """Deterministic, bounded payoff particles; no frame-state randomness."""
        if self._reduced_motion:
            for x, y in ((7, 29), (119, 29), (7, 99), (119, 99)):
                draw_rect(buffer, x, y, 2, 2, WHITE)
            return
        progress = max(0.0, min(1.0, self._reveal_elapsed_ms / 560.0))
        eased = 1.0 - (1.0 - progress) ** 3
        for index in range(14):
            angle = (math.tau * index / 14.0) + 0.17
            radius = 13.0 + 48.0 * eased
            x = int(round(64 + math.cos(angle) * radius))
            y = int(round(65 + math.sin(angle) * radius * 0.78))
            particle_color = WHITE if index % 2 == 0 else RED
            if 3 <= x <= 123 and 25 <= y <= 119:
                if index % 3 == 0:
                    draw_circle(buffer, x, y, 2, particle_color)
                else:
                    draw_rect(buffer, x - 1, y - 1, 3, 3, particle_color)

    def _render_result(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, OFF_WHITE)
        draw_rect(buffer, 1, 1, 126, 126, RED, filled=False, thickness=3)
        draw_rect(buffer, 5, 5, 118, 118, BLACK, filled=False, thickness=1)
        if self._classic_logo is not None:
            _blit_centered(buffer, self._classic_logo, y=5)
        else:
            draw_rect(buffer, 41, 5, 46, 46, RED, filled=False, thickness=2)
            draw_centered_text(buffer[7:49], "VNVNC", 16, BLACK, scale=1)
        draw_centered_text(buffer, "ВЫ ВЫИГРАЛИ:", 54, BLACK, scale=1)
        draw_rect(buffer, 6, 68, 116, 54, RED, filled=True)
        draw_circle(buffer, 6, 95, 5, OFF_WHITE)
        draw_circle(buffer, 121, 95, 5, OFF_WHITE)
        if self._award:
            title = buffer[70:120, 9:119]
            _draw_prize_headline(
                title,
                self._award.prize.id,
                self._award.prize.label,
                WHITE,
                max_scale=3,
            )
        self._render_result_status_badge(buffer)

    def _render_result_status_badge(self, buffer: NDArray[np.uint8]) -> None:
        if self._award and self._award.test_mode:
            draw_rect(buffer, 4, 4, 28, 9, BLACK, filled=True)
            draw_centered_text(buffer[4:13, 4:32], "ТЕСТ", 1, WHITE, scale=1)
        elif self._print_failed:
            draw_circle(buffer, 116, 11, 7, RED)
            draw_centered_text(buffer[5:17, 110:123], "!", 2, WHITE, scale=1)

    def _render_ticket_discount_result(self, buffer: NDArray[np.uint8]) -> None:
        """Render the TIX50 TicketsCloud text-code contract as one bold ticket."""
        fill(buffer, OFF_WHITE)
        draw_rect(buffer, 1, 1, 126, 126, RED, filled=False, thickness=2)
        draw_rect(buffer, 6, 6, 116, 116, RED, filled=True)
        draw_rect(buffer, 7, 7, 114, 114, WHITE, filled=False, thickness=2)

        # Large red/white VPISKA ticket hierarchy: offer first, redemption code
        # second. Side notches and perforation make it read as a physical stub.
        draw_centered_text(buffer, "СКИДКА", 11, WHITE, scale=2)
        draw_centered_text(buffer, "-50%", 29, WHITE, scale=4)
        draw_centered_text(buffer, "НА ЛЮБОЙ БИЛЕТ", 59, WHITE, scale=1)
        draw_circle(buffer, 6, 70, 5, OFF_WHITE)
        draw_circle(buffer, 121, 70, 5, OFF_WHITE)
        for x in range(14, 116, 8):
            draw_rect(buffer, x, 69, 4, 2, WHITE)

        draw_rect(buffer, 11, 77, 106, 39, WHITE, filled=True)
        draw_rect(buffer, 11, 77, 106, 39, DEEP_RED, filled=False, thickness=2)
        draw_centered_text(buffer, "ПРОМОКОД", 80, RED, scale=1)
        code = self._award.coupon.code if self._award else ""
        _draw_ticket_discount_code(buffer[89:113, 14:114], code, RED)

    def _render_no_spins(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, OFF_WHITE)
        draw_rect(buffer, 2, 2, 124, 124, RED, filled=False, thickness=3)
        draw_circle(buffer, 64, 64, 31, RED, filled=False)
        draw_circle(buffer, 64, 64, 28, RED, filled=False)
        draw_centered_text(buffer, "0", 43, RED, scale=6)

    def _render_offline(self, buffer: NDArray[np.uint8]) -> None:
        fill(buffer, BLACK)
        draw_rect(buffer, 2, 2, 124, 124, RED, filled=False, thickness=3)
        draw_circle(buffer, 64, 35, 17, RED, filled=False)
        draw_line(buffer, 64, 24, 64, 39, RED, thickness=3)
        draw_rect(buffer, 62, 45, 5, 5, RED)
        draw_centered_text(buffer, "СВЯЗИ НЕТ", 61, WHITE, scale=1)
        draw_wrapped_text(
            buffer,
            "ПРИЗ НЕ РАЗЫГРАН",
            77,
            RED,
            scale=1,
            max_lines=2,
            max_width=118,
        )

    def _draw_left_chevron(self, buffer: NDArray[np.uint8]) -> None:
        """Draw the VPISKA-style selector on the left, pointing into the winner."""
        near_lock = 0
        if self.screen == PrizeDrumScreen.SPINNING and self._motion and not self._reduced_motion:
            near_lock = int(round(4.0 * self._motion.near_hit_strength))
        kick = (2 if self._pointer_kick_ms > 0 else 0) + near_lock
        x0 = 3 + kick
        tip_x = 12 + kick
        # A dark under-stroke keeps the selector readable over either ticket color.
        draw_line(buffer, x0 + 1, REEL_CENTER_Y - 12, tip_x + 1, REEL_CENTER_Y, BLACK, thickness=5)
        draw_line(buffer, tip_x + 1, REEL_CENTER_Y, x0 + 1, REEL_CENTER_Y + 12, BLACK, thickness=5)
        draw_line(buffer, x0, REEL_CENTER_Y - 12, tip_x, REEL_CENTER_Y, WHITE, thickness=3)
        draw_line(buffer, tip_x, REEL_CENTER_Y, x0, REEL_CENTER_Y + 12, WHITE, thickness=3)

    def _get_sector(
        self,
        prize_id: str,
        label: str,
        *,
        selected: bool,
    ) -> NDArray[np.uint8]:
        normalized_label = _normalize_label(label)
        key = (prize_id, normalized_label, selected)
        cached = self._sector_cache.get(key)
        if cached is not None:
            return cached
        width = SECTOR_WIDTH if selected else NEIGHBOR_SECTOR_WIDTH
        height = SECTOR_HEIGHT if selected else NEIGHBOR_SECTOR_HEIGHT
        card = np.zeros((height, width, 3), dtype=np.uint8)
        bg, fg = (RED, WHITE) if selected else (FADED_PAPER, MUTED_RED)
        fill(card, bg)
        draw_rect(card, 0, 0, width, height, fg, filled=False, thickness=2)

        # Ticket silhouette is enough to carry the VPISKA reel language. All
        # service copy, stubs and barcodes are deliberately omitted so the
        # prize headline owns the full field.
        draw_circle(card, 0, height // 2, 4, OFF_WHITE)
        draw_circle(card, width - 1, height // 2, 4, OFF_WHITE)
        if selected:
            _draw_prize_headline(
                card,
                prize_id,
                normalized_label,
                fg,
                max_scale=3,
            )
        else:
            _draw_neighbor_headlines(card, prize_id, normalized_label, fg)
        self._sector_cache[key] = card
        return card


def _draw_prize_headline(
    buffer: NDArray[np.uint8],
    prize_id: str,
    label: str,
    color: tuple[int, int, int],
    *,
    max_scale: int = 3,
) -> None:
    """Render one balanced, billboard-scale prize headline and nothing else."""
    font = load_font("cyrillic")
    requested = TICKET_HEADLINES.get(
        prize_id,
        ((_short_prize_label(label), min(2, max_scale)),),
    )
    max_width = max(1, buffer.shape[1] - 8)
    lines: list[tuple[str, int, int]] = []
    for text, requested_scale in requested:
        scale = min(requested_scale, max_scale)
        measured_width, _ = font.measure_text(text)
        while scale > 1 and measured_width * scale > max_width:
            scale -= 1
        lines.append((text, scale, font.char_height * scale))

    gap = 5 if len(lines) > 1 else 0
    total_height = sum(line_height for _text, _scale, line_height in lines)
    total_height += gap * max(0, len(lines) - 1)
    y = max(3, (buffer.shape[0] - total_height) // 2)
    for text, scale, line_height in lines:
        draw_centered_text(buffer, text, y, color, scale=scale, font=font)
        y += line_height + gap


def _draw_neighbor_headlines(
    buffer: NDArray[np.uint8],
    prize_id: str,
    label: str,
    color: tuple[int, int, int],
) -> None:
    """Repeat only the adjacent prize name at the two visible reel edges."""
    text = LCD_PRIZE_HEADLINES.get(prize_id, _short_prize_label(label))
    font = load_font("cyrillic")
    max_width = buffer.shape[1] - 10
    if font.measure_text(text)[0] > max_width:
        text = TICKER_PRIZE_HEADLINES.get(prize_id, _short_prize_label(label))
    draw_centered_text(buffer, text, 4, color, scale=1, font=font)
    draw_centered_text(
        buffer,
        text,
        buffer.shape[0] - font.char_height - 4,
        color,
        scale=1,
        font=font,
    )


def _draw_ticket_discount_code(
    buffer: NDArray[np.uint8],
    code: str,
    color: tuple[int, int, int],
) -> None:
    """Fit the complete TicketsCloud promo code without turning it into a QR."""
    text = str(code).strip() or "КОД НЕ ГОТОВ"
    max_width = max(1, buffer.shape[1] - 4)
    full_font = load_font("cyrillic")
    full_width, _ = full_font.measure_text(text)
    if full_width * 2 <= max_width and full_font.char_height * 2 <= buffer.shape[0]:
        y = (buffer.shape[0] - full_font.char_height * 2) // 2
        draw_centered_text(buffer, text, y, color, scale=2, font=full_font)
        return
    if full_width <= max_width:
        y = (buffer.shape[0] - full_font.char_height) // 2
        draw_centered_text(buffer, text, y, color, scale=1, font=full_font)
        return

    split_candidates: list[tuple[int, int, int, str, str]] = []
    for split_at in range(1, len(text)):
        first, second = text[:split_at], text[split_at:]
        first_width, _ = full_font.measure_text(first)
        second_width, _ = full_font.measure_text(second)
        if first_width <= max_width and second_width <= max_width:
            separator_penalty = 0 if text[split_at - 1] == "-" else 1
            split_candidates.append(
                (separator_penalty, abs(first_width - second_width), split_at, first, second)
            )
    if split_candidates:
        _penalty, _imbalance, _split_at, first, second = min(split_candidates)
        gap = 3
        total_height = full_font.char_height * 2 + gap
        y = max(0, (buffer.shape[0] - total_height) // 2)
        draw_centered_text(buffer, first, y, color, scale=1, font=full_font)
        draw_centered_text(
            buffer,
            second,
            y + full_font.char_height + gap,
            color,
            scale=1,
            font=full_font,
        )
        return

    # Codes longer than one 5x7 line use the compact Latin 3x5 alphabet. This
    # preserves every character across up to three clearly separated rows.
    base_font = load_font("default")
    compact_font = PixelFont(
        name=f"{base_font.name}_ticket_code",
        char_height=base_font.char_height,
        char_width=base_font.char_width,
        spacing=0,
        glyphs=base_font.glyphs,
    )
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        if current and compact_font.measure_text(candidate)[0] > max_width:
            lines.append(current)
            current = char
        else:
            current = candidate
    if current:
        lines.append(current)

    # Backend codes are short, but keep an impossible payload visibly
    # diagnosable instead of silently clipping its beginning.
    if len(lines) > 3:
        lines = lines[:2] + ["..."]
    gap = 2
    total_height = len(lines) * compact_font.char_height + max(0, len(lines) - 1) * gap
    y = max(0, (buffer.shape[0] - total_height) // 2)
    for line in lines:
        draw_centered_text(buffer, line, y, color, scale=1, font=compact_font)
        y += compact_font.char_height + gap


def make_qr_array(
    payload: str,
    *,
    max_size: int,
    telegram_brand: bool,
    min_module_scale: int = 1,
    error_correction: str = "H",
) -> NDArray[np.uint8] | None:
    """Create an integer-scaled QR with a physical module-size floor."""
    if not payload:
        return None
    if min_module_scale < 1:
        return None
    try:
        import qrcode

        correction_levels = {
            "L": qrcode.constants.ERROR_CORRECT_L,
            "M": qrcode.constants.ERROR_CORRECT_M,
            "Q": qrcode.constants.ERROR_CORRECT_Q,
            "H": qrcode.constants.ERROR_CORRECT_H,
        }
        correction = correction_levels.get(str(error_correction).strip().upper())
        if correction is None:
            return None
        qr = qrcode.QRCode(
            version=None,
            error_correction=correction,
            box_size=1,
            border=4,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        base = np.asarray(qr.make_image(fill_color="black", back_color="white").convert("RGB"))
    except Exception:
        logger.exception("Prize-drum QR generation failed")
        return None
    if base.shape[0] > max_size:
        return None
    scale = max(1, max_size // base.shape[0])
    if scale < min_module_scale:
        return None
    image = np.repeat(np.repeat(base, scale, axis=0), scale, axis=1)
    if telegram_brand and image.shape[0] >= 45:
        _draw_telegram_mark(image)
    return image


def _draw_telegram_mark(image: NDArray[np.uint8]) -> None:
    size = image.shape[0]
    radius = max(4, min(6, size // 15))
    cx = cy = size // 2
    draw_circle(image, cx, cy, radius + 1, WHITE)
    draw_circle(image, cx, cy, radius, (39, 159, 217))
    # Tiny white paper-plane silhouette, kept well below 15% QR coverage.
    draw_line(image, cx - 4, cy, cx + 4, cy - 3, WHITE, thickness=2)
    draw_line(image, cx + 4, cy - 3, cx + 1, cy + 4, WHITE, thickness=2)
    draw_line(image, cx + 1, cy + 4, cx, cy + 1, WHITE, thickness=1)


def _normalize_label(label: str) -> str:
    return " ".join(str(label).upper().replace("₽", "Р").split())


def _short_prize_label(label: str) -> str:
    normalized = _normalize_label(label)
    replacements = {
        "БЕСПЛАТНЫЙ КОКТЕЙЛЬ": "КОКТЕЙЛЬ",
        "БЕСПЛАТНЫЙ МЕРЧ": "МЕРЧ",
        "БЕСПЛАТНЫЙ ШОТ": "ШОТ",
        "БЕСПЛАТНЫЙ СЕТ ШОТОВ": "СЕТ ШОТОВ",
        "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ": "СКИДКА 50%",
    }
    return replacements.get(normalized, normalized)


def _blit_centered(buffer: NDArray[np.uint8], image: NDArray[np.uint8], *, y: int) -> None:
    x = (buffer.shape[1] - image.shape[1]) // 2
    _blit_clipped(buffer, image, x, y, 0, buffer.shape[0])


def _blit_clipped(
    buffer: NDArray[np.uint8],
    image: NDArray[np.uint8],
    x: int,
    y: int,
    clip_top: int,
    clip_bottom: int,
) -> None:
    dst_x1 = max(0, x)
    dst_y1 = max(clip_top, y)
    dst_x2 = min(buffer.shape[1], x + image.shape[1])
    dst_y2 = min(clip_bottom, y + image.shape[0])
    if dst_x2 <= dst_x1 or dst_y2 <= dst_y1:
        return
    src_x1 = dst_x1 - x
    src_y1 = dst_y1 - y
    src_x2 = src_x1 + (dst_x2 - dst_x1)
    src_y2 = src_y1 + (dst_y2 - dst_y1)
    buffer[dst_y1:dst_y2, dst_x1:dst_x2] = image[src_y1:src_y2, src_x1:src_x2]

#!/usr/bin/env python3
"""Render reproducible ФОТОБУДКА ВИНОВНИЦЫ prize-drum QA previews."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from artifact.animation.engine import AnimationEngine
from artifact.core.events import EventBus
from artifact.core.state import StateMachine
from artifact.graphics.renderer import Renderer
from artifact.modes.base import ModeContext
from artifact.modes.prize_drum import (
    AUTH_QR_MAX_SIZE,
    PrizeDrumFlow,
    PrizeDrumMode,
    PrizeDrumScreen,
    SECTOR_STEP,
    SPIN_DURATION_MS,
    make_qr_array,
)
from artifact.printing.wheel_prize_roll import WheelPrizeRollReceiptGenerator
from artifact.services.vnvnc_kiosk import (
    KioskAuth,
    KioskAward,
    KioskCoupon,
    KioskPrize,
    KioskSession,
    KioskSpinResult,
    KioskUser,
    LocalKioskStub,
    SpinAllowance,
)


AUTH_URL = "https://api.vnvnc.ru/k/AbCdEfGhIjKlMnOpQrStUv"
WALKTHROUGH_TITLE = "ФОТОБУДКА ВИНОВНИЦЫ"


def _context() -> ModeContext:
    return ModeContext(
        state_machine=StateMachine(),
        event_bus=EventBus(),
        renderer=Renderer(),
        animation_engine=AnimationEngine(),
    )


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        (
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
            if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf"
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        ),
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _session(*, spins: int, boosts: int) -> KioskSession:
    return KioskSession(
        id="preview-session",
        status="READY",
        auth_mode="telegram",
        club_night="2026-08-28",
        authenticated=True,
        user=KioskUser(992001, "ЛЕНА", "lena"),
        allowance=SpinAllowance(
            base=1,
            bonus=min(boosts, 2),
            total=1 + min(boosts, 2),
            used=max(0, 1 + min(boosts, 2) - spins),
            left=spins,
            active_boosts=boosts,
        ),
    )


def _award() -> KioskAward:
    code = "VNVNC-KSK-8F2M9Q"
    return KioskAward(
        id="preview-award",
        prize=KioskPrize("SHOT1FREE", "БЕСПЛАТНЫЙ ШОТ", "До 07:00 текущей клубной ночи"),
        coupon=KioskCoupon(code, "2026-08-28T07:00:00+03:00", code),
        source_credit="boost",
        issued_at="2026-08-28T02:07:00+03:00",
    )


def _tix50_award() -> KioskAward:
    code = "260826-1234567890-50"
    return KioskAward(
        id="preview-tix50-award",
        prize=KioskPrize(
            "TIX50",
            "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ",
            (
                "Действует на две ближайшие опубликованные вечеринки, "
                "кроме «Все свои»."
            ),
        ),
        coupon=KioskCoupon(code, "2026-09-30T23:59:00+03:00", code),
        source_credit="base",
        issued_at="2026-08-30T03:20:00+03:00",
    )


def _render_mode(mode: PrizeDrumMode) -> tuple[Image.Image, Image.Image, str]:
    main = np.zeros((128, 128, 3), dtype=np.uint8)
    ticker = np.zeros((8, 48, 3), dtype=np.uint8)
    mode.render_main(main)
    mode.render_ticker(ticker)
    main_image = Image.fromarray(main).resize((512, 512), Image.Resampling.NEAREST)
    ticker_image = Image.fromarray(ticker).resize((480, 80), Image.Resampling.NEAREST)
    return main_image, ticker_image, mode.get_lcd_text().strip()


def _states() -> list[tuple[str, PrizeDrumMode]]:
    auth = PrizeDrumMode(_context(), client=LocalKioskStub())
    auth._accept_auth(KioskAuth("preview-pairing", AUTH_URL))

    ready = PrizeDrumMode(_context(), client=LocalKioskStub())
    ready.preferred_flow = PrizeDrumFlow.AUTH
    ready.screen = PrizeDrumScreen.READY
    ready._session = _session(spins=1, boosts=0)

    reveal = PrizeDrumMode(_context(), client=LocalKioskStub())
    reveal.preferred_flow = PrizeDrumFlow.AUTH
    reveal._session = _session(spins=1, boosts=1)
    reveal._accept_spin(KioskSpinResult(award=_award(), session=_session(spins=1, boosts=1)))
    assert reveal._motion is not None
    reveal._motion.elapsed_ms = SPIN_DURATION_MS
    reveal._reel_position = reveal._motion.target_position
    reveal._reveal_elapsed_ms = 270
    reveal.screen = PrizeDrumScreen.REVEAL

    result = PrizeDrumMode(_context(), client=LocalKioskStub())
    result.preferred_flow = PrizeDrumFlow.AUTH
    result._award = _award()
    result._session = _session(spins=0, boosts=0)
    result._redeem_qr = make_qr_array(result._award.coupon.code, max_size=76, telegram_brand=False)
    result._pending_print_issue_id = result._award.id
    result.screen = PrizeDrumScreen.RESULT

    return [
        ("QR", auth),
        ("READY", ready),
        ("REVEAL", reveal),
        ("RESULT", result),
    ]


def render_state_preview(path: Path) -> None:
    canvas = Image.new("RGB", (1160, 1400), "white")
    draw = ImageDraw.Draw(canvas)
    title_font = _font(24, bold=True)
    lcd_font = _font(20)
    positions = [(34, 58), (614, 58), (34, 758), (614, 758)]
    for (title, mode), (x, y) in zip(_states(), positions):
        draw.text((x, y - 42), title, fill=(20, 20, 20), font=title_font)
        main, ticker, lcd = _render_mode(mode)
        canvas.paste(main, (x, y))
        ticker_x = x + 32
        ticker_y = y + 530
        canvas.paste(ticker, (ticker_x, ticker_y))
        draw.text((x, ticker_y + 90), f"LCD:  {lcd}", fill=(70, 70, 70), font=lcd_font)
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def render_auth_frame(path: Path) -> None:
    mode = _states()[0][1]
    frame = np.zeros((128, 128, 3), dtype=np.uint8)
    mode.render_main(frame)
    output = Image.fromarray(frame).resize((1024, 1024), Image.Resampling.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    output.save(path)


def render_sector_catalog(path: Path) -> None:
    """Render every presentation sector without QA text inside the frames."""
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    cells: list[Image.Image] = []
    for prize_id, _label in mode._catalog:
        index = next(
            index
            for index, (candidate_id, _candidate_label) in enumerate(mode._reel_items)
            if candidate_id == prize_id
        )
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        mode._render_reel(frame, float(index * SECTOR_STEP))
        cells.append(Image.fromarray(frame).resize((384, 384), Image.Resampling.NEAREST))

    columns = 4
    rows = (len(cells) + columns - 1) // columns
    canvas = Image.new("RGB", (8 + columns * 388, 8 + rows * 388), (12, 9, 10))
    for index, cell in enumerate(cells):
        x = 8 + (index % columns) * 388
        y = 8 + (index // columns) * 388
        canvas.paste(cell, (x, y))
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(path)


def render_motion_preview(path: Path, *, fps: int = 30) -> None:
    """Encode a READY → committed spin → reveal → result pass as H.264."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to render the motion preview")

    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode._active = True
    mode.preferred_flow = PrizeDrumFlow.AUTH
    mode._session = _session(spins=2, boosts=1)
    mode.screen = PrizeDrumScreen.READY
    award = _award()
    spin_session = _session(spins=1, boosts=1)
    frame_ms = 1000.0 / fps

    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s:v",
            "768x768",
            "-r",
            str(fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
        ],
        stdin=subprocess.PIPE,
    )

    def emit_frame() -> None:
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        mode.render_main(frame)
        physical = np.repeat(np.repeat(frame, 6, axis=0), 6, axis=1)
        assert process.stdin is not None
        process.stdin.write(physical.tobytes())

    try:
        for _ in range(round(1.2 * fps)):
            emit_frame()
            mode.update(frame_ms)

        mode.screen = PrizeDrumScreen.ISSUING
        for _ in range(round(0.55 * fps)):
            emit_frame()
            mode.update(frame_ms)

        mode._accept_spin(KioskSpinResult(award=award, session=spin_session))
        while mode.screen != PrizeDrumScreen.RESULT:
            emit_frame()
            mode.update(frame_ms)
        for _ in range(round(2.2 * fps)):
            emit_frame()
            mode.update(frame_ms)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        return_code = process.wait()
    if return_code:
        raise RuntimeError(f"ffmpeg exited with status {return_code}")


def render_walkthrough_preview(
    path: Path,
    *,
    fps: int = 30,
    award: KioskAward | None = None,
    include_auth: bool = True,
    final_stage: str = "6 · QR ДЛЯ СОТРУДНИКА",
) -> None:
    """Record the real main/ticker/LCD flow in one reviewable video."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to render the walkthrough preview")

    video_width = 960
    video_height = 1200
    frame_ms = 1000.0 / fps
    mode = PrizeDrumMode(_context(), client=LocalKioskStub())
    mode._active = True
    if include_auth:
        mode._accept_auth(KioskAuth("preview-pairing", AUTH_URL))
    selected_award = award or _award()
    spin_session = _session(spins=1, boosts=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{video_width}x{video_height}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "17",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(path),
        ],
        stdin=subprocess.PIPE,
    )

    title_font = _font(31, bold=True)
    stage_font = _font(25, bold=True)
    label_font = _font(18, bold=True)
    lcd_font = _font(27, bold=True)

    def emit_frame(stage: str) -> None:
        main = np.zeros((128, 128, 3), dtype=np.uint8)
        ticker = np.zeros((8, 48, 3), dtype=np.uint8)
        mode.render_main(main)
        mode.render_ticker(ticker)

        canvas = Image.new("RGB", (video_width, video_height), (12, 9, 10))
        draw = ImageDraw.Draw(canvas)
        stage_box = draw.textbbox((0, 0), stage, font=stage_font)
        stage_width = stage_box[2] - stage_box[0]
        title_box = draw.textbbox((0, 0), WALKTHROUGH_TITLE, font=title_font)
        title_width = title_box[2] - title_box[0]
        stage_left = video_width - stage_width - 82
        if 48 + title_width + 24 > stage_left:
            raise RuntimeError("walkthrough brand header overlaps the stage badge")
        draw.text((48, 26), WALKTHROUGH_TITLE, fill=(255, 255, 255), font=title_font)
        draw.rounded_rectangle(
            (stage_left, 22, video_width - 38, 66),
            radius=14,
            fill=(204, 0, 24),
        )
        draw.text(
            (video_width - stage_width - 60, 29),
            stage,
            fill=(255, 255, 255),
            font=stage_font,
        )

        main_image = Image.fromarray(main).resize((768, 768), Image.Resampling.NEAREST)
        canvas.paste(main_image, (96, 92))
        draw.rectangle((94, 90, 865, 861), outline=(204, 0, 24), width=3)
        draw.text((96, 866), "MAIN · 128×128", fill=(235, 226, 222), font=label_font)

        ticker_image = Image.fromarray(ticker).resize((768, 128), Image.Resampling.NEAREST)
        canvas.paste(ticker_image, (96, 902))
        draw.rectangle((94, 900, 865, 1031), outline=(204, 0, 24), width=3)
        draw.text((96, 1037), "TICKER · 48×8", fill=(235, 226, 222), font=label_font)

        lcd_box = (96, 1070, 864, 1154)
        draw.rounded_rectangle(lcd_box, radius=12, fill=(0, 0, 0), outline=(204, 0, 24), width=3)
        lcd_text = mode.get_lcd_text().strip()
        if lcd_text:
            text_box = draw.textbbox((0, 0), lcd_text, font=lcd_font)
            text_width = text_box[2] - text_box[0]
            text_height = text_box[3] - text_box[1]
            draw.text(
                ((video_width - text_width) // 2, 1112 - text_height // 2),
                lcd_text,
                fill=(0, 255, 48),
                font=lcd_font,
            )
        draw.text((96, 1162), "LCD · 16×1", fill=(235, 226, 222), font=label_font)

        assert process.stdin is not None
        process.stdin.write(canvas.tobytes())

    def hold(seconds: float, stage: str, *, update: bool = True) -> None:
        for _ in range(round(seconds * fps)):
            emit_frame(stage)
            if update:
                mode.update(frame_ms)
            else:
                # Freeze network polling, not the machine's visual heartbeat.
                mode._time_in_mode += frame_ms

    try:
        if include_auth:
            # Auth polling is intentionally frozen in the deterministic capture;
            # the next scene is the simulated successful server response.
            hold(2.3, "1 · ВХОД ЧЕРЕЗ TELEGRAM", update=False)
            mode._session = spin_session
            mode._identity_cleared = False
            mode.screen = PrizeDrumScreen.READY
            hold(1.3, "2 · БАРАБАН ГОТОВ")
            issuing_stage = "3 · СЕРВЕР ФИКСИРУЕТ ПРИЗ"
            spin_stage = "4 · ВРАЩЕНИЕ"
            near_hit_prefix = "4 · ПОЧТИ…"
            reveal_stage = "5 · ВЫИГРЫШ"
        else:
            mode._session = spin_session
            mode._identity_cleared = False
            mode.screen = PrizeDrumScreen.READY
            hold(1.8, "1 · БАРАБАН ГОТОВ")
            issuing_stage = "2 · ПРИЗ ЗАФИКСИРОВАН"
            spin_stage = "3 · ДЛИННОЕ ВРАЩЕНИЕ"
            near_hit_prefix = "3 · ПОЧТИ…"
            reveal_stage = "4 · ВЫИГРЫШ"
        mode.screen = PrizeDrumScreen.ISSUING
        hold(0.6, issuing_stage)
        mode._accept_spin(KioskSpinResult(award=selected_award, session=spin_session))
        while mode.screen != PrizeDrumScreen.RESULT:
            if mode.screen == PrizeDrumScreen.SPINNING and mode._motion:
                near_hit = mode._motion.near_hit_stage
                stage = f"{near_hit_prefix} {near_hit}" if near_hit else spin_stage
            else:
                stage = reveal_stage
            emit_frame(stage)
            mode.update(frame_ms)
        hold(3.2 if not include_auth else 2.6, final_stage)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        return_code = process.wait()
    if return_code:
        raise RuntimeError(f"ffmpeg exited with status {return_code}")


def render_tix50_walkthrough_preview(path: Path, *, fps: int = 30) -> None:
    """Record READY → committed spin → TicketsCloud text-code result."""
    render_walkthrough_preview(
        path,
        fps=fps,
        award=_tix50_award(),
        include_auth=False,
        final_stage="TEXT CODE/TICKETSCLOUD",
    )


def _render_receipt(path: Path, data: dict[str, object]) -> None:
    receipt = WheelPrizeRollReceiptGenerator().generate_receipt(
        "prize_drum",
        data,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(receipt.preview_image)


def render_receipt_previews(output_dir: Path) -> None:
    _render_receipt(
        output_dir / "wheel-prize-roll-preview.png",
        {
            "issue_id": "KIOSK-20260826-0001",
            "prize_id": "COCKTL",
            "prize_title": "БЕСПЛАТНЫЙ КОКТЕЙЛЬ",
            "terms": "Действует до конца текущей клубной ночи.",
            "coupon_code": "VNVNC-KSK-8F2M9Q",
            "redeem_qr_payload": "VNVNC-KSK-8F2M9Q",
            "club_night": "2026-08-28",
            "issued_at": "2026-08-28T23:15:00+03:00",
            "expires_at": "2026-08-29T07:00:00+03:00",
            "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
        },
    )
    _render_receipt(
        output_dir / "wheel-prize-roll-merch-preview.png",
        {
            "issue_id": "KIOSK-20260829-0002",
            "prize_id": "MERCHFREE",
            "prize_title": "БЕСПЛАТНЫЙ МЕРЧ",
            "terms": "Один предмет из выделенного ассортимента мерча VNVNC.",
            "coupon_code": "VNVNC-KSK-MERCH1",
            "redeem_qr_payload": "VNVNC-KSK-MERCH1",
            "club_night": "2026-08-29",
            "issued_at": "2026-08-30T01:20:00+03:00",
            "expires_at": "2026-08-30T07:00:00+03:00",
            "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
        },
    )
    _render_receipt(
        output_dir / "wheel-prize-roll-shot-set-preview.png",
        {
            "issue_id": "KIOSK-20260829-0003",
            "prize_id": "SHOTFR",
            "prize_title": "СЕТ ШОТОВ",
            "terms": "Один сет фирменных шотов VNVNC.",
            "coupon_code": "VNVNC-KSK-SHOTSET1",
            "redeem_qr_payload": "VNVNC-KSK-SHOTSET1",
            "club_night": "2026-08-29",
            "issued_at": "2026-08-30T02:05:00+03:00",
            "expires_at": "2026-08-30T07:00:00+03:00",
            "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
        },
    )
    _render_receipt(
        output_dir / "wheel-prize-roll-single-shot-preview.png",
        {
            "issue_id": "KIOSK-20260828-0004",
            "prize_id": "SHOT1FREE",
            "prize_title": "БЕСПЛАТНЫЙ ШОТ",
            "terms": "Один бесплатный шот.",
            "coupon_code": "VNVNC-KSK-SHOTONE1",
            "redeem_qr_payload": "VNVNC-KSK-SHOTONE1",
            "club_night": "2026-08-28",
            "issued_at": "2026-08-29T02:40:00+03:00",
            "expires_at": "2026-08-29T07:00:00+03:00",
            "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
        },
    )
    _render_receipt(
        output_dir / "wheel-prize-roll-ticket-preview.png",
        {
            "issue_id": "KIOSK-20260829-0005",
            "prize_id": "TIX1FREE",
            "prize_title": "БИЛЕТ НА ОДНОГО",
            "terms": "Один человек, один проход.",
            "coupon_code": "VNVNC-KSK-TICKET01",
            "redeem_qr_payload": "VNVNC-KSK-TICKET01",
            "club_night": "2026-08-29",
            "issued_at": "2026-08-30T03:10:00+03:00",
            "expires_at": "2026-09-06T07:00:00+03:00",
            "validity_slots": [
                {"club_night": "2026-09-04", "label": "04.09.2026"},
                {"club_night": "2026-09-05", "label": "05.09.2026"},
            ],
            "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
        },
    )
    _render_receipt(
        output_dir / "wheel-prize-roll-tix50-preview.png",
        {
            "issue_id": "KIOSK-20260829-0006",
            "prize_id": "TIX50",
            "prize_title": "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ",
            "terms": (
                "Действует на две ближайшие опубликованные вечеринки, "
                "кроме «Все свои»."
            ),
            "coupon_code": "260826-1234567890-50",
            "redeem_qr_payload": "260826-1234567890-50",
            "club_night": "2026-08-29",
            "issued_at": "2026-08-30T03:20:00+03:00",
            "expires_at": "2026-09-30T23:59:00+03:00",
            "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
        },
    )
    _render_receipt(
        output_dir / "prize-drum-canary-receipt.png",
        {
            "issue_id": "canary-issue-000001",
            "prize_id": "COCKTL",
            "prize_title": "БЕСПЛАТНЫЙ КОКТЕЙЛЬ",
            "terms": "ТЕСТОВЫЙ ЧЕК — НЕ ДЕЙСТВИТЕЛЕН. НЕ ПРИНИМАТЬ КАК ПРИЗ.",
            "coupon_code": "TEST-VNVNC-000001",
            "redeem_qr_payload": "TEST-VNVNC-000001",
            "club_night": "2026-08-28",
            "issued_at": "2026-08-28T23:15:00+03:00",
            "expires_at": "2026-08-29T00:15:00+03:00",
            "regular_wheel_qr_payload": "https://t.me/vnvncbattlebot?start=wheel",
            "test_mode": True,
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--skip-motion", action="store_true")
    args = parser.parse_args()
    render_state_preview(args.output_dir / "prize-drum-state-preview.png")
    render_auth_frame(args.output_dir / "prize-drum-auth-oidc-frame.png")
    render_sector_catalog(args.output_dir / "prize-drum-ticket-catalog.png")
    render_receipt_previews(args.output_dir)
    if not args.skip_motion:
        render_motion_preview(args.output_dir / "prize-drum-motion-preview.mp4")
        render_walkthrough_preview(args.output_dir / "prize-drum-walkthrough.mp4")
        render_tix50_walkthrough_preview(
            args.output_dir / "prize-drum-tix50-walkthrough.mp4"
        )
    print(f"Rendered previews in {args.output_dir.resolve()} (auth QR max {AUTH_QR_MAX_SIZE}px)")


if __name__ == "__main__":
    main()

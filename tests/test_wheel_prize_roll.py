from __future__ import annotations

import asyncio
from io import BytesIO
import json
from pathlib import Path

import pytest
from PIL import Image

from artifact.core.events import EventBus, EventType
from artifact.hardware.printer.ip802 import MockLabelPrinter
from artifact.hardware.printer.rp80 import RP80ReceiptPrinter, create_rp80_printer
from artifact.printing.manager import PrintManager
from artifact.printing.wheel_prize_roll import (
    CLASSIC_LOGO_PATH,
    DRINK_PRIZE_IDS,
    MERCH_REDEEM_LOCATION_LINES,
    PAPER_WIDTH_PX,
    PUBLIC_DEVICE_NAME,
    REDEEM_LOCATION_LINES,
    REGULAR_WHEEL_HEADLINE,
    REGULAR_WHEEL_URL,
    TICKETSCLOUD_DISCOUNT_PRIZE_IDS,
    WHEEL_PRIZE_MODE_NAME,
    WheelPrizeRollReceiptGenerator,
)
from artifact.printing.wheel_qr import render_wheel_receipt_qr
from artifact.services.vnvnc_kiosk import LocalKioskStub


GOLDEN = json.loads(
    (Path(__file__).parent / "golden" / "wheel_prize_roll_contract.json").read_text()
)


def _sample_job(**overrides):
    job = {
        "type": WHEEL_PRIZE_MODE_NAME,
        "issue_id": "KIOSK-20260826-0001",
        "print_job_key": "KIOSK-20260826-0001",
        "prize_id": "COCKTL",
        "prize_title": "БЕСПЛАТНЫЙ КОКТЕЙЛЬ",
        "terms": (
            "Покажи этот чек сотруднику бара до окончания "
            "текущей клубной ночи."
        ),
        "coupon_code": GOLDEN["primary_payload"],
        "redeem_qr_payload": GOLDEN["primary_payload"],
        "club_night": "2026-08-28",
        "issued_at": "2026-08-28T23:15:00+03:00",
        "expires_at": "2026-08-29T07:00:00+03:00",
        "regular_wheel_qr_payload": GOLDEN["secondary_payload"],
    }
    job.update(overrides)
    return job


def _decode_qr(image_path: Path, box: tuple[int, int, int, int]) -> str:
    cv2 = pytest.importorskip("cv2")
    image = cv2.imread(str(image_path))
    assert image is not None
    left, top, right, bottom = box
    pad = 8
    crop = image[
        max(0, top - pad) : min(image.shape[0], bottom + pad),
        max(0, left - pad) : min(image.shape[1], right + pad),
    ]
    value, _points, _straight = cv2.QRCodeDetector().detectAndDecode(crop)
    return value


def test_wheel_prize_receipt_matches_golden_geometry_and_decodes(tmp_path) -> None:
    assert CLASSIC_LOGO_PATH.is_file()
    receipt = WheelPrizeRollReceiptGenerator().generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(),
    )
    preview_path = tmp_path / "wheel-prize.png"
    preview_path.write_bytes(receipt.preview_image)

    with Image.open(preview_path) as image:
        assert image.width == GOLDEN["paper_width_px"] == PAPER_WIDTH_PX
        assert GOLDEN["height_min_px"] <= image.height <= GOLDEN["height_max_px"]
        # Every edge remains paper-white: content cannot be silently clipped.
        pixels = image.convert("L")
        assert pixels.crop((0, 0, 20, pixels.height)).getextrema() == (255, 255)
        right_edge = pixels.crop((pixels.width - 20, 0, pixels.width, pixels.height))
        assert right_edge.getextrema() == (255, 255)

    assert _decode_qr(preview_path, receipt.qr_regions["redeem"]) == GOLDEN["primary_payload"]
    assert (
        _decode_qr(preview_path, receipt.qr_regions["regular_wheel"])
        == GOLDEN["secondary_payload"]
    )
    assert receipt.raw_commands.startswith(b"\x1b@\x1b3\x18\x1dv0\x00")
    assert receipt.raw_commands.endswith(b"\x1b2\x1bd\x04\x1dV\x01")


def _capture_receipt_text(generator, monkeypatch) -> list[str]:
    rendered_lines: list[str] = []
    original_draw_line = generator._draw_centered_line
    original_draw_box = generator._draw_centered_in_box

    def capture_drawn_line(draw, text, y, font, *, line_gap=9):
        rendered_lines.append(text)
        return original_draw_line(draw, text, y, font, line_gap=line_gap)

    def capture_drawn_box(draw, text, box, font, *, fill=0):
        rendered_lines.append(text)
        return original_draw_box(draw, text, box, font, fill=fill)

    monkeypatch.setattr(generator, "_draw_centered_line", capture_drawn_line)
    monkeypatch.setattr(generator, "_draw_centered_in_box", capture_drawn_box)
    return rendered_lines


def test_merch_receipt_prints_opposite_cloakroom_location_and_keeps_qrs(
    tmp_path,
    monkeypatch,
) -> None:
    generator = WheelPrizeRollReceiptGenerator()
    rendered_lines = _capture_receipt_text(generator, monkeypatch)
    receipt = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            prize_id="MERCHFREE",
            prize_title="БЕСПЛАТНЫЙ МЕРЧ",
            terms="Один предмет из выделенного ассортимента.",
        ),
    )
    preview_path = tmp_path / "redemption-location-receipt.png"
    preview_path.write_bytes(receipt.preview_image)

    assert REDEEM_LOCATION_LINES == MERCH_REDEEM_LOCATION_LINES == (
        "ПОКАЖИ ЭТОТ QR СОТРУДНИКУ",
        "НА СТОЙКЕ НАПРОТИВ ГАРДЕРОБА",
    )
    assert PUBLIC_DEVICE_NAME == "ФОТОБУДКА ВИНОВНИЦЫ"
    assert PUBLIC_DEVICE_NAME in rendered_lines
    assert REGULAR_WHEEL_HEADLINE == "ВИРТУАЛЬНОЕ КОЛЕСО ФОРТУНЫ VNVNC"
    assert REGULAR_WHEEL_HEADLINE in " ".join(rendered_lines)
    assert "ЖИВЁТ В TELEGRAM" in rendered_lines
    assert all("t.me/" not in line for line in rendered_lines)
    assert all("START WHEEL" not in line for line in rendered_lines)
    assert all(line in rendered_lines for line in MERCH_REDEEM_LOCATION_LINES)
    assert "QR ДЛЯ ПОЛУЧЕНИЯ МЕРЧА" in rendered_lines
    assert _decode_qr(preview_path, receipt.qr_regions["redeem"]) == GOLDEN["primary_payload"]
    assert (
        _decode_qr(preview_path, receipt.qr_regions["regular_wheel"])
        == REGULAR_WHEEL_URL
    )


@pytest.mark.parametrize(
    ("prize_id", "club_night", "expected_venue"),
    [
        ("COCKTL", "2026-08-28", "В МАЛУЮ ВИНОВНИЦУ"),
        ("COCKTL", "2026-08-29", "В АНГАР"),
        ("SHOTFR", "2026-08-28", "В МАЛУЮ ВИНОВНИЦУ"),
        ("SHOTFR", "2026-08-29", "В АНГАР"),
        ("SHOT1FREE", "2026-09-04", "В МАЛУЮ ВИНОВНИЦУ"),
    ],
)
def test_drink_receipt_routes_by_club_night_and_keeps_exact_qrs(
    prize_id,
    club_night,
    expected_venue,
    tmp_path,
    monkeypatch,
) -> None:
    assert prize_id in DRINK_PRIZE_IDS
    generator = WheelPrizeRollReceiptGenerator()
    rendered_lines = _capture_receipt_text(generator, monkeypatch)
    receipt = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            prize_id=prize_id,
            prize_title={
                "COCKTL": "БЕСПЛАТНЫЙ КОКТЕЙЛЬ",
                "SHOTFR": "СЕТ ШОТОВ",
                "SHOT1FREE": "БЕСПЛАТНЫЙ ШОТ",
            }[prize_id],
            club_night=club_night,
        ),
    )
    path = tmp_path / f"{prize_id.lower()}-receipt.png"
    path.write_bytes(receipt.preview_image)

    assert "СОХРАНИ ИМЕННО ЭТОТ ЧЕК" in rendered_lines
    assert "С НИМ — В БАР" in rendered_lines
    assert expected_venue in rendered_lines
    other_venue = "В АНГАР" if expected_venue != "В АНГАР" else "В МАЛУЮ ВИНОВНИЦУ"
    assert other_venue not in rendered_lines
    assert "QR ДЛЯ БАРА" in rendered_lines
    assert not any("ГАРДЕРОБ" in line for line in rendered_lines)
    assert _decode_qr(path, receipt.qr_regions["redeem"]) == GOLDEN["primary_payload"]
    assert _decode_qr(path, receipt.qr_regions["regular_wheel"]) == REGULAR_WHEEL_URL


@pytest.mark.parametrize(
    (
        "prize_id",
        "prize_title",
        "coupon_code",
        "club_night",
        "issued_at",
        "expires_at",
        "validity_slots",
        "expected_copy",
        "has_primary_qr",
    ),
    [
        (
            "SHOT1FREE",
            "БЕСПЛАТНЫЙ ШОТ",
            "VNVNC-KSK-SHOTONE1",
            "2026-08-28",
            "2026-08-29T02:40:00+03:00",
            "2026-08-29T07:00:00+03:00",
            [],
            ("СОХРАНИ ИМЕННО ЭТОТ ЧЕК", "В МАЛУЮ ВИНОВНИЦУ"),
            True,
        ),
        (
            "COCKTL",
            "БЕСПЛАТНЫЙ КОКТЕЙЛЬ",
            "VNVNC-KSK-COCKFRI",
            "2026-08-28",
            "2026-08-29T01:15:00+03:00",
            "2026-08-29T07:00:00+03:00",
            [],
            ("СОХРАНИ ИМЕННО ЭТОТ ЧЕК", "В МАЛУЮ ВИНОВНИЦУ"),
            True,
        ),
        (
            "COCKTL",
            "БЕСПЛАТНЫЙ КОКТЕЙЛЬ",
            "VNVNC-KSK-COCKSAT",
            "2026-08-29",
            "2026-08-30T01:15:00+03:00",
            "2026-08-30T07:00:00+03:00",
            [],
            ("СОХРАНИ ИМЕННО ЭТОТ ЧЕК", "В АНГАР"),
            True,
        ),
        (
            "SHOTFR",
            "СЕТ ШОТОВ",
            "VNVNC-KSK-SETFRI",
            "2026-08-28",
            "2026-08-29T01:45:00+03:00",
            "2026-08-29T07:00:00+03:00",
            [],
            ("СОХРАНИ ИМЕННО ЭТОТ ЧЕК", "В МАЛУЮ ВИНОВНИЦУ"),
            True,
        ),
        (
            "SHOTFR",
            "СЕТ ШОТОВ",
            "VNVNC-KSK-SETSAT",
            "2026-08-29",
            "2026-08-30T01:45:00+03:00",
            "2026-08-30T07:00:00+03:00",
            [],
            ("СОХРАНИ ИМЕННО ЭТОТ ЧЕК", "В АНГАР"),
            True,
        ),
        (
            "MERCHFREE",
            "БЕСПЛАТНЫЙ МЕРЧ",
            "VNVNC-KSK-MERCH1",
            "2026-08-29",
            "2026-08-30T01:20:00+03:00",
            "2026-08-30T07:00:00+03:00",
            [],
            MERCH_REDEEM_LOCATION_LINES,
            True,
        ),
        (
            "TIX1FREE",
            "БИЛЕТ НА ОДНОГО",
            "VNVNC-KSK-TICKET01",
            "2026-08-28",
            "2026-08-29T02:10:00+03:00",
            "2026-09-06T07:00:00+03:00",
            [
                {"club_night": "2026-09-04", "label": "04.09.2026"},
                {"club_night": "2026-09-05", "label": "05.09.2026"},
            ],
            (
                "1 ЧЕЛОВЕК · 1 ПРОХОД",
                "ПТ 04.09.2026 · 23:00–07:00",
                "СБ 05.09.2026 · 23:00–07:00",
            ),
            True,
        ),
        (
            "TIX50",
            "СКИДКА 50% НА ЛЮБОЙ БИЛЕТ",
            "260826-1234567890-50",
            "2026-08-29",
            "2026-08-30T03:20:00+03:00",
            "2026-09-30T23:59:00+03:00",
            [],
            (
                "2 БЛИЖАЙШИЕ ВЕЧЕРИНКИ",
                "КРОМЕ «ВСЕ СВОИ»",
                "ВВЕДИ КОД В TICKETSCLOUD",
            ),
            False,
        ),
    ],
)
def test_tomorrow_rp80_canary_receipt_matrix(
    prize_id,
    prize_title,
    coupon_code,
    club_night,
    issued_at,
    expires_at,
    validity_slots,
    expected_copy,
    has_primary_qr,
    tmp_path,
    monkeypatch,
) -> None:
    generator = WheelPrizeRollReceiptGenerator()
    rendered_lines = _capture_receipt_text(generator, monkeypatch)
    receipt = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            prize_id=prize_id,
            prize_title=prize_title,
            terms="Canary contract terms.",
            coupon_code=coupon_code,
            redeem_qr_payload=coupon_code,
            club_night=club_night,
            issued_at=issued_at,
            expires_at=expires_at,
            validity_slots=validity_slots,
        ),
    )
    path = tmp_path / f"canary-{prize_id}-{club_night}.png"
    path.write_bytes(receipt.preview_image)

    assert PUBLIC_DEVICE_NAME in rendered_lines
    assert all(text in rendered_lines for text in expected_copy)
    expected_regions = {"regular_wheel", "redeem"} if has_primary_qr else {"regular_wheel"}
    assert set(receipt.qr_regions) == expected_regions
    if has_primary_qr:
        assert _decode_qr(path, receipt.qr_regions["redeem"]) == coupon_code
    assert _decode_qr(path, receipt.qr_regions["regular_wheel"]) == REGULAR_WHEEL_URL

    with Image.open(path) as preview:
        mono = preview.convert("L")
        assert preview.width == PAPER_WIDTH_PX == 576
        assert preview.height <= GOLDEN["height_max_px"]
        assert mono.crop((0, 0, 20, preview.height)).getextrema() == (255, 255)
        assert mono.crop((preview.width - 20, 0, preview.width, preview.height)).getextrema() == (
            255,
            255,
        )
        assert mono.crop((0, 0, preview.width, 20)).getextrema() == (255, 255)
        assert mono.crop((0, preview.height - 3, preview.width, preview.height)).getextrema() == (
            255,
            255,
        )


@pytest.mark.parametrize(
    ("issued_at", "expires_at", "expected_destination"),
    [
        ("2026-08-29T02:15:00+03:00", "2026-08-29T07:00:00+03:00", "В МАЛУЮ ВИНОВНИЦУ"),
        ("2026-08-30T02:15:00+03:00", "2026-08-30T07:00:00+03:00", "В АНГАР"),
        ("2026-09-02T02:15:00+03:00", "2026-09-02T07:00:00+03:00", None),
    ],
)
def test_drink_receipt_uses_issued_at_business_date_and_safe_fallback(
    issued_at,
    expires_at,
    expected_destination,
    monkeypatch,
) -> None:
    generator = WheelPrizeRollReceiptGenerator()
    rendered_lines = _capture_receipt_text(generator, monkeypatch)
    generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            club_night=None,
            issued_at=issued_at,
            expires_at=expires_at,
        ),
    )
    if expected_destination:
        assert expected_destination in rendered_lines
        assert "ПОКАЖИ ЕГО В БАРЕ" not in rendered_lines
    else:
        assert "ПОКАЖИ ЕГО В БАРЕ" in rendered_lines
        assert "В МАЛУЮ ВИНОВНИЦУ" not in rendered_lines
        assert "В АНГАР" not in rendered_lines


def test_qr_contract_has_integer_modules_and_four_module_quiet_zone() -> None:
    primary = render_wheel_receipt_qr(
        GOLDEN["primary_payload"],
        max_size_px=304,
        error_correction="Q",
    )
    secondary = render_wheel_receipt_qr(
        REGULAR_WHEEL_URL,
        max_size_px=252,
        error_correction="H",
        telegram_icon=True,
    )

    for rendered in (primary, secondary):
        assert rendered.quiet_zone_modules == GOLDEN["quiet_zone_modules"]
        expected_modules = rendered.module_count + 2 * rendered.quiet_zone_modules
        assert rendered.image.width == expected_modules * rendered.pixels_per_module
        assert rendered.image.height == rendered.image.width
        quiet_px = rendered.quiet_zone_modules * rendered.pixels_per_module
        top_quiet_zone = rendered.image.crop((0, 0, rendered.image.width, quiet_px))
        left_quiet_zone = rendered.image.crop((0, 0, quiet_px, rendered.image.height))
        assert top_quiet_zone.getextrema() == (255, 255)
        assert left_quiet_zone.getextrema() == (255, 255)

    assert primary.has_telegram_icon is False
    assert secondary.has_telegram_icon is True
    assert secondary.error_correction == GOLDEN["secondary_error_correction"]


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"coupon_code": "lowercase", "redeem_qr_payload": "lowercase"}, "uppercase"),
        ({"coupon_code": " VNVNC-KSK-8F2M9Q", "redeem_qr_payload": " VNVNC-KSK-8F2M9Q"}, "trimmed"),
        ({"redeem_qr_payload": "OTHER-CODE"}, "match exactly"),
        ({"regular_wheel_qr_payload": "https://example.com"}, "canonical URL"),
        ({"expires_at": "2026-08-26T22:00:00+03:00"}, "later"),
        ({"terms": ""}, "terms"),
    ],
)
def test_wheel_prize_receipt_rejects_unsafe_or_incomplete_contract(overrides, message) -> None:
    with pytest.raises(ValueError, match=message):
        WheelPrizeRollReceiptGenerator().generate_receipt(
            WHEEL_PRIZE_MODE_NAME,
            _sample_job(**overrides),
        )


def test_ticket_receipt_prints_exact_next_entry_windows_and_no_bar_or_counter(
    tmp_path,
    monkeypatch,
) -> None:
    generator = WheelPrizeRollReceiptGenerator()
    slots = [
        {"club_night": "2026-09-04", "label": "04.09.2026"},
        {"club_night": "2026-09-05", "label": "05.09.2026"},
    ]

    ordinary_without_slots = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(validity_slots=[]),
    )
    ordinary_with_slots = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(validity_slots=slots),
    )
    assert ordinary_with_slots.preview_image == ordinary_without_slots.preview_image

    rendered_lines = _capture_receipt_text(generator, monkeypatch)
    pass_with_slots = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            prize_id="TIX1FREE",
            prize_title="БИЛЕТ НА ОДНОГО",
            terms="Один человек, один проход.",
            issued_at="2026-08-29T02:15:00+03:00",
            expires_at="2026-09-06T07:00:00+03:00",
            validity_slots=slots,
        ),
    )
    path = tmp_path / "ticket-receipt.png"
    path.write_bytes(pass_with_slots.preview_image)

    assert "СОХРАНИ ИМЕННО ЭТОТ ЧЕК" in rendered_lines
    assert "1 ЧЕЛОВЕК · 1 ПРОХОД" in rendered_lines
    assert "ИСПОЛЬЗУЙ ПРИ СЛЕДУЮЩЕМ ВХОДЕ" in rendered_lines
    assert "ПТ 04.09.2026 · 23:00–07:00" in rendered_lines
    assert "СБ 05.09.2026 · 23:00–07:00" in rendered_lines
    assert "QR ДЛЯ ПРОХОДА" in rendered_lines
    assert not any("ГАРДЕРОБ" in line or "В БАР" in line for line in rendered_lines)
    assert _decode_qr(path, pass_with_slots.qr_regions["redeem"]) == GOLDEN["primary_payload"]
    assert _decode_qr(path, pass_with_slots.qr_regions["regular_wheel"]) == REGULAR_WHEEL_URL


def test_ticket_uses_explicit_slot_timestamps_without_rewriting_them(monkeypatch) -> None:
    generator = WheelPrizeRollReceiptGenerator()
    rendered_lines = _capture_receipt_text(generator, monkeypatch)
    generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            prize_id="TIX1FREE",
            prize_title="БИЛЕТ НА ОДНОГО",
            terms="Один человек, один проход.",
            expires_at="2026-09-06T07:00:00+03:00",
            validity_slots=[
                {
                    "starts_at": "2026-09-04T22:30:00+03:00",
                    "ends_at": "2026-09-05T06:30:00+03:00",
                }
            ],
        ),
    )
    assert "ПТ 04.09.2026 · 22:30–06:30" in rendered_lines


def test_tix50_has_large_ticket_and_text_code_but_no_primary_qr(
    tmp_path,
    monkeypatch,
) -> None:
    assert TICKETSCLOUD_DISCOUNT_PRIZE_IDS == frozenset({"TIX50"})
    generator = WheelPrizeRollReceiptGenerator()
    rendered_lines: list[str] = []
    rendered_boxes: list[tuple[str, tuple[int, int, int, int], int]] = []
    original_draw_line = generator._draw_centered_line
    original_draw_box = generator._draw_centered_in_box

    def capture_drawn_line(draw, text, y, font, *, line_gap=9):
        rendered_lines.append(text)
        return original_draw_line(draw, text, y, font, line_gap=line_gap)

    def capture_drawn_box(draw, text, box, font, *, fill=0):
        rendered_boxes.append((text, box, int(getattr(font, "size", 0))))
        return original_draw_box(draw, text, box, font, fill=fill)

    monkeypatch.setattr(generator, "_draw_centered_line", capture_drawn_line)
    monkeypatch.setattr(generator, "_draw_centered_in_box", capture_drawn_box)
    provider_code = "260826-1234567890-50"
    receipt = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            prize_id="TIX50",
            prize_title="СКИДКА 50% НА ЛЮБОЙ БИЛЕТ",
            terms=(
                "Действует на две ближайшие опубликованные вечеринки, "
                "кроме «Все свои»."
            ),
            coupon_code=provider_code,
            redeem_qr_payload=provider_code,
        ),
    )
    path = tmp_path / "tix50-receipt.png"
    path.write_bytes(receipt.preview_image)

    assert set(receipt.qr_regions) == {"regular_wheel"}
    assert _decode_qr(path, receipt.qr_regions["regular_wheel"]) == REGULAR_WHEEL_URL
    cv2 = pytest.importorskip("cv2")
    image = cv2.imread(str(path))
    ok, values, _points, _straight = cv2.QRCodeDetector().detectAndDecodeMulti(image)
    assert ok is True
    assert [value for value in values if value] == [REGULAR_WHEEL_URL]

    visible_text = rendered_lines + [entry[0] for entry in rendered_boxes]
    assert "2 БЛИЖАЙШИЕ ВЕЧЕРИНКИ" in visible_text
    assert "КРОМЕ «ВСЕ СВОИ»" in visible_text
    assert "ВВЕДИ КОД В TICKETSCLOUD" in visible_text
    assert "АКТИВИРУЕТСЯ АВТОМАТИЧЕСКИ" in visible_text
    assert "ПОСЛЕ ПУБЛИКАЦИИ ВЕЧЕРИНОК" in visible_text
    assert provider_code in visible_text
    assert all("QR ДЛЯ" not in text for text in visible_text)
    assert all(not text.startswith("ДО ·") for text in visible_text)
    assert "1 ПРИЗ · 1 ПОГАШЕНИЕ" not in visible_text

    discount_box = next(entry for entry in rendered_boxes if entry[0] == "−50%")
    provider_code_box = next(entry for entry in rendered_boxes if entry[0] == provider_code)
    assert discount_box[2] >= 82
    assert provider_code_box[2] >= 30
    with Image.open(path) as preview:
        assert preview.width == PAPER_WIDTH_PX
        assert preview.height < 1800
        assert preview.crop((0, 0, 20, preview.height)).getextrema() == (255, 255)
        assert preview.crop((preview.width - 20, 0, preview.width, preview.height)).getextrema() == (
            255,
            255,
        )


def test_canary_receipt_has_prominent_test_banner_and_keeps_exact_qrs(tmp_path) -> None:
    generator = WheelPrizeRollReceiptGenerator()
    normal = generator.generate_receipt(WHEEL_PRIZE_MODE_NAME, _sample_job())
    canary = generator.generate_receipt(
        WHEEL_PRIZE_MODE_NAME,
        _sample_job(
            test_mode=True,
            terms="ТЕСТОВЫЙ ЧЕК — НЕ ДЕЙСТВИТЕЛЕН. НЕ ПРИНИМАТЬ КАК ПРИЗ.",
            coupon_code="TEST-VNVNC-000001",
            redeem_qr_payload="TEST-VNVNC-000001",
        ),
    )
    normal_image = Image.open(BytesIO(normal.preview_image))
    canary_image = Image.open(BytesIO(canary.preview_image))
    assert canary_image.height > normal_image.height
    # The banner is a full-width black region before the logo.
    assert canary_image.crop((24, 24, 552, 76)).getextrema() == (0, 255)
    path = tmp_path / "canary-receipt.png"
    path.write_bytes(canary.preview_image)
    assert _decode_qr(path, canary.qr_regions["redeem"]) == "TEST-VNVNC-000001"
    assert _decode_qr(path, canary.qr_regions["regular_wheel"]) == REGULAR_WHEEL_URL


class _CountingRP80(RP80ReceiptPrinter):
    def __init__(self, *, accept: bool = True) -> None:
        super().__init__(mock=True)
        self.accept = accept
        self.print_count = 0

    async def print_raw(self, data: bytes) -> bool:
        self.print_count += 1
        return self.accept


async def _silence_broadcast(_mode_name, _data) -> None:
    return None


def test_print_manager_routes_prize_to_rp80_once_for_duplicate_issue() -> None:
    async def scenario() -> None:
        bus = EventBus()
        printer = _CountingRP80()
        manager = PrintManager(bus, printer=printer, mock=True)
        manager._broadcast_to_telegram = _silence_broadcast
        await manager.start()
        try:
            await manager.queue_print(_sample_job())
            await manager.queue_print(_sample_job())
            await manager._queue.join()
        finally:
            await manager.stop()

        assert printer.print_count == 1
        completed = bus.get_history(EventType.PRINT_COMPLETE)
        assert len(completed) == 1
        assert completed[0].data["print_job_key"] == _sample_job()["print_job_key"]
        assert not bus.get_history(EventType.PRINT_ERROR)

    asyncio.run(scenario())


def test_print_manager_allows_explicit_kp8_reprint_with_same_prize_issue() -> None:
    async def scenario() -> None:
        bus = EventBus()
        printer = _CountingRP80()
        manager = PrintManager(bus, printer=printer, mock=True)
        manager._broadcast_to_telegram = _silence_broadcast
        initial = _sample_job()
        reprint = _sample_job(
            manual_reprint=True,
            reprint_number=1,
            print_job_key=f"{initial['issue_id']}:manual-reprint:1",
        )
        await manager.start()
        try:
            await manager.queue_print(initial)
            await manager._queue.join()
            await manager.queue_print(reprint)
            await manager._queue.join()
        finally:
            await manager.stop()

        assert printer.print_count == 2
        completed = bus.get_history(EventType.PRINT_COMPLETE)
        assert [event.data["issue_id"] for event in completed] == [
            initial["issue_id"],
            initial["issue_id"],
        ]
        assert [event.data["print_job_key"] for event in completed] == [
            initial["print_job_key"],
            reprint["print_job_key"],
        ]
        assert not bus.get_history(EventType.PRINT_ERROR)

    asyncio.run(scenario())


def test_print_manager_emits_error_when_rp80_rejects_job() -> None:
    async def scenario() -> None:
        bus = EventBus()
        printer = _CountingRP80(accept=False)
        manager = PrintManager(bus, printer=printer, mock=False)
        manager._broadcast_to_telegram = _silence_broadcast
        await manager.start()
        try:
            await manager.queue_print(_sample_job())
            await manager._queue.join()
        finally:
            await manager.stop()

        assert printer.print_count == 1
        errors = bus.get_history(EventType.PRINT_ERROR)
        assert len(errors) == 1
        assert errors[0].data["issue_id"] == _sample_job()["issue_id"]
        assert "rejected" in errors[0].data["error"]
        assert not bus.get_history(EventType.PRINT_COMPLETE)

    asyncio.run(scenario())


def test_print_manager_emits_error_instead_of_label_mock_success(monkeypatch) -> None:
    async def scenario() -> None:
        bus = EventBus()
        manager = PrintManager(bus, printer=MockLabelPrinter(), mock=False)
        monkeypatch.setattr(
            "artifact.printing.manager.auto_detect_rp80_printer",
            lambda: None,
        )
        await manager.start()
        try:
            await manager.queue_print(_sample_job())
            await manager._queue.join()
        finally:
            await manager.stop()

        errors = bus.get_history(EventType.PRINT_ERROR)
        assert len(errors) == 1
        assert "RP80" in errors[0].data["error"]
        assert not bus.get_history(EventType.PRINT_COMPLETE)

    asyncio.run(scenario())


def test_rp80_factory_never_implicitly_returns_mock(monkeypatch) -> None:
    monkeypatch.setattr(
        "artifact.hardware.printer.rp80.auto_detect_rp80_printer",
        lambda: None,
    )
    printer = create_rp80_printer(mock=False)
    assert type(printer) is RP80ReceiptPrinter
    assert asyncio.run(printer.connect()) is False


def test_sixty_spin_issue_retry_and_rp80_print_soak() -> None:
    """Preflight 20 authenticated 3-spin sessions and 60 unique receipts.

    This is deliberately local/stub-only.  It proves the client/receipt/queue
    invariants before the separately required supervised physical soak.
    """

    async def scenario() -> None:
        stub = LocalKioskStub(active_boosts=2, auto_auth_after_polls=1)
        bus = EventBus()
        printer = _CountingRP80()
        manager = PrintManager(bus, printer=printer, mock=True)
        manager._broadcast_to_telegram = _silence_broadcast
        issue_ids: set[str] = set()
        coupon_codes: set[str] = set()
        await manager.start()
        try:
            for session_number in range(20):
                session = await stub.create_session(
                    request_id=f"SOAK-SESSION-{session_number:03d}",
                    auth_mode="telegram",
                )
                session = await stub.get_session(session.id)
                assert session.authenticated
                assert session.allowance.total == 3

                for spin_number in range(3):
                    request_id = f"SOAK-SPIN-{session_number:03d}-{spin_number}"
                    result = await stub.spin(session.id, request_id=request_id)
                    retry = await stub.spin(session.id, request_id=request_id)
                    assert retry.idempotent
                    assert retry.award.id == result.award.id
                    assert retry.award.coupon.code == result.award.coupon.code

                    award = result.award
                    assert award.id not in issue_ids
                    assert award.coupon.code not in coupon_codes
                    issue_ids.add(award.id)
                    coupon_codes.add(award.coupon.code)
                    validity_slots = (
                        [
                            {"label": "ПЯТНИЦА 28.08.2026"},
                            {"label": "СУББОТА 29.08.2026"},
                        ]
                        if award.prize.id == "TIX1FREE"
                        else []
                    )
                    await manager.queue_print(
                        _sample_job(
                            issue_id=award.id,
                            print_job_key=award.id,
                            prize_id=award.prize.id,
                            prize_title=award.prize.label,
                            terms=award.prize.description or "Покажи QR сотруднику.",
                            coupon_code=award.coupon.code,
                            redeem_qr_payload=award.coupon.redeem_qr_payload,
                            issued_at=award.issued_at,
                            expires_at=award.coupon.expires_at,
                            validity_slots=validity_slots,
                        )
                    )

                exhausted = await stub.get_session(session.id)
                assert exhausted.allowance.left == 0
                await stub.finish_session(session.id)

            await manager._queue.join()
        finally:
            await manager.stop()

        assert len(issue_ids) == 60
        assert len(coupon_codes) == 60
        assert printer.print_count == 60
        completed = bus.get_history(EventType.PRINT_COMPLETE, limit=100)
        assert len(completed) == 60
        assert len({event.data["issue_id"] for event in completed}) == 60
        assert not bus.get_history(EventType.PRINT_ERROR, limit=100)

    asyncio.run(scenario())

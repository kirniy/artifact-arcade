"""Dedicated 80mm RP80 receipt for the physical VNVNC prize drum."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont, ImageOps

from artifact.printing.wheel_qr import WheelReceiptQR, render_wheel_receipt_qr


PAPER_WIDTH_PX = 576
PRINT_MARGIN_PX = 24
MAX_RECEIPT_HEIGHT_PX = 4096
REGULAR_WHEEL_URL = "https://t.me/vnvncbattlebot?start=wheel"
REGULAR_WHEEL_HEADLINE = "ВИРТУАЛЬНОЕ КОЛЕСО ФОРТУНЫ VNVNC"
PUBLIC_DEVICE_NAME = "ФОТОБУДКА ВИНОВНИЦЫ"
MERCH_REDEEM_LOCATION_LINES = (
    "ПОКАЖИ ЭТОТ QR СОТРУДНИКУ",
    "НА СТОЙКЕ НАПРОТИВ ГАРДЕРОБА",
)
# Compatibility alias retained for integrations that imported the old constant.
REDEEM_LOCATION_LINES = MERCH_REDEEM_LOCATION_LINES
DRINK_PRIZE_IDS = frozenset({"COCKTL", "SHOTFR", "SHOT1FREE"})
MERCH_PRIZE_IDS = frozenset({"MERCHFREE"})
TICKET_PRIZE_IDS = frozenset({"TIX1FREE"})
TICKETSCLOUD_DISCOUNT_PRIZE_IDS = frozenset({"TIX50"})
CLUB_NIGHT_START = time(23, 0)
CLUB_NIGHT_END = time(7, 0)
PROJECT_ROOT = Path(__file__).resolve().parents[3]
CLASSIC_LOGO_PATH = (
    PROJECT_ROOT / "assets" / "logos" / "vnvnc-logo-classic-border-letters-black.png"
)
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
WHEEL_PRIZE_MODE_NAME = "prize_drum"

_SAFE_COUPON_RE = re.compile(r"^[A-Z0-9_-]{6,64}$")


@dataclass(frozen=True, slots=True)
class WheelPrizeRollReceipt:
    """Rendered prize receipt, print bytes, and verification geometry."""

    raw_commands: bytes
    preview_image: bytes
    issued_at: datetime
    expires_at: datetime
    coupon_code: str
    issue_id: str
    print_job_key: str
    qr_regions: dict[str, tuple[int, int, int, int]]


@dataclass(frozen=True, slots=True)
class _ReceiptData:
    issue_id: str
    print_job_key: str
    prize_id: str
    prize_title: str
    terms: str
    coupon_code: str
    issued_at: datetime
    expires_at: datetime
    club_night: date
    validity_lines: tuple[str, ...]
    test_mode: bool


class WheelPrizeRollReceiptGenerator:
    """Create the monochrome VNVNC Classic prize receipt for RP80."""

    def __init__(
        self,
        *,
        paper_width_px: int = PAPER_WIDTH_PX,
        logo_path: Path = CLASSIC_LOGO_PATH,
    ) -> None:
        if paper_width_px != PAPER_WIDTH_PX:
            raise ValueError("wheel prize receipt is calibrated for the 576px RP80")
        self.paper_width_px = paper_width_px
        self.logo_path = Path(logo_path)

    def generate_receipt(
        self,
        mode_name: str,
        data: dict[str, Any],
    ) -> WheelPrizeRollReceipt:
        """Validate server output and render one idempotent prize print job."""
        if str(mode_name).strip() != WHEEL_PRIZE_MODE_NAME:
            raise ValueError(f"unsupported wheel receipt mode: {mode_name}")

        receipt_data = self._parse_data(data)
        image, qr_regions = self._render_image(receipt_data)
        raw_commands = self.image_to_escpos(image)

        preview = BytesIO()
        image.save(preview, format="PNG", optimize=False)
        return WheelPrizeRollReceipt(
            raw_commands=raw_commands,
            preview_image=preview.getvalue(),
            issued_at=receipt_data.issued_at,
            expires_at=receipt_data.expires_at,
            coupon_code=receipt_data.coupon_code,
            issue_id=receipt_data.issue_id,
            print_job_key=receipt_data.print_job_key,
            qr_regions=qr_regions,
        )

    def render_image(self, data: dict[str, Any]) -> Image.Image:
        """Render a final PNG-friendly image without producing printer bytes."""
        image, _regions = self._render_image(self._parse_data(data))
        return image

    def _parse_data(self, data: dict[str, Any]) -> _ReceiptData:
        issue_id = self._required_text(data, "issue_id")
        print_job_key = str(data.get("print_job_key") or issue_id).strip()
        if not print_job_key:
            raise ValueError("wheel prize receipt requires print_job_key or issue_id")

        prize_id = self._required_text(data, "prize_id").upper()
        prize_title = str(data.get("prize_title") or data.get("prize_label") or "").strip()
        if not prize_title:
            raise ValueError("wheel prize receipt requires prize_title")

        terms = str(data.get("terms") or data.get("prize_description") or "").strip()
        if not terms:
            raise ValueError("wheel prize receipt requires prize terms")

        raw_coupon_code = str(
            data.get("redeem_qr_payload") or data.get("coupon_code") or ""
        )
        raw_alternate_code = str(data.get("coupon_code") or raw_coupon_code)
        coupon_has_whitespace = raw_coupon_code != raw_coupon_code.strip()
        alternate_has_whitespace = raw_alternate_code != raw_alternate_code.strip()
        if coupon_has_whitespace or alternate_has_whitespace:
            raise ValueError("coupon QR payload must not be normalized or trimmed")
        coupon_code = raw_coupon_code
        if not coupon_code or coupon_code != raw_alternate_code:
            raise ValueError("coupon_code and redeem_qr_payload must match exactly")
        if coupon_code != coupon_code.upper() or not _SAFE_COUPON_RE.fullmatch(coupon_code):
            raise ValueError("coupon code must be raw uppercase A-Z/0-9 with '-' or '_'")

        supplied_wheel_url = str(
            data.get("regular_wheel_qr_payload") or REGULAR_WHEEL_URL
        )
        if supplied_wheel_url != REGULAR_WHEEL_URL:
            raise ValueError("regular wheel QR payload does not match the canonical URL")

        issued_at = self._required_datetime(data, "issued_at", aliases=("timestamp",))
        expires_at = self._required_datetime(data, "expires_at")
        if expires_at <= issued_at:
            raise ValueError("expires_at must be later than issued_at")

        club_night = self._club_night_date(data.get("club_night"), issued_at)
        validity_lines: list[str] = []
        raw_slots = data.get("validity_slots")
        if prize_id == "TIX1FREE" and isinstance(raw_slots, (list, tuple)):
            for slot in raw_slots:
                if isinstance(slot, dict):
                    label = self._format_validity_slot(slot)
                else:
                    label = self._format_validity_slot({"label": slot})
                if label:
                    validity_lines.append(label)

        return _ReceiptData(
            issue_id=issue_id,
            print_job_key=print_job_key,
            prize_id=prize_id,
            prize_title=prize_title,
            terms=terms,
            coupon_code=coupon_code,
            issued_at=issued_at,
            expires_at=expires_at,
            club_night=club_night,
            validity_lines=tuple(validity_lines),
            test_mode=bool(data.get("test_mode", False)),
        )

    def _render_image(
        self,
        data: _ReceiptData,
    ) -> tuple[Image.Image, dict[str, tuple[int, int, int, int]]]:
        canvas = Image.new("L", (self.paper_width_px, MAX_RECEIPT_HEIGHT_PX), 255)
        draw = ImageDraw.Draw(canvas)
        left = PRINT_MARGIN_PX
        right = self.paper_width_px - PRINT_MARGIN_PX
        content_width = right - left
        qr_regions: dict[str, tuple[int, int, int, int]] = {}
        y = 24

        if data.test_mode:
            draw.rectangle((left, y, right - 1, y + 52), fill=0)
            self._draw_centered_in_box(
                draw,
                "ТЕСТ · НЕ ДЕЙСТВИТЕЛЕН",
                (left, y, right, y + 52),
                self._font(27, bold=True),
                fill=255,
            )
            y += 70

        logo = self._load_classic_logo(132)
        canvas.paste(logo, ((self.paper_width_px - logo.width) // 2, y))
        y += logo.height + 12

        y = self._draw_centered_line(
            draw,
            PUBLIC_DEVICE_NAME,
            y,
            self._font(23, bold=True),
        )
        y += 12
        draw.rectangle((left, y, right - 1, y + 58), fill=0)
        self._draw_centered_in_box(
            draw,
            "ТВОЙ ПРИЗ",
            (left, y, right, y + 58),
            self._font(34, bold=True),
            fill=255,
        )
        y += 78

        prize_font = self._fit_multiline_font(
            draw,
            data.prize_title,
            max_width=content_width,
            max_size=48,
            min_size=30,
            bold=True,
            max_lines=3,
        )
        prize_lines = self._wrap_text(draw, data.prize_title, prize_font, content_width)
        for line in prize_lines:
            y = self._draw_centered_line(draw, line, y, prize_font)
        y += 14

        draw.line((left + 48, y, right - 48, y), fill=0, width=3)
        y += 18
        y = self._draw_prize_instruction(
            draw,
            data,
            y,
            left=left,
            right=right,
        )
        y += 18

        if data.prize_id in TICKETSCLOUD_DISCOUNT_PRIZE_IDS:
            # TIX50 is a provider text code, never a staff-redemption QR.
            y = self._draw_tix50_ticket(
                draw,
                data,
                y,
                left=left,
                right=right,
            )
            y += 18
        else:
            # Primary scanner QR: raw coupon code only and deliberately no logo.
            draw.rounded_rectangle((left, y, right - 1, y + 52), radius=14, fill=0)
            self._draw_centered_in_box(
                draw,
                self._primary_qr_heading(data.prize_id),
                (left, y, right, y + 52),
                self._font(27, bold=True),
                fill=255,
            )
            y += 65
            primary_qr = render_wheel_receipt_qr(
                data.coupon_code,
                max_size_px=304,
                error_correction="Q",
                telegram_icon=False,
            )
            primary_x = (self.paper_width_px - primary_qr.image.width) // 2
            canvas.paste(primary_qr.image, (primary_x, y))
            qr_regions["redeem"] = (
                primary_x,
                y,
                primary_x + primary_qr.image.width,
                y + primary_qr.image.height,
            )
            y += primary_qr.image.height + 12

            code_font = self._fit_font(
                draw,
                data.coupon_code,
                max_width=content_width - 20,
                max_size=36,
                min_size=23,
                bold=True,
            )
            y = self._draw_centered_line(draw, data.coupon_code, y, code_font)
            y += 7

            info_font = self._font(22, bold=True)
            y = self._draw_centered_line(
                draw,
                f"ВЫДАН · {self._format_datetime(data.issued_at)}",
                y,
                info_font,
                line_gap=7,
            )
            y = self._draw_centered_line(
                draw,
                f"ДО · {self._format_datetime(data.expires_at)}",
                y,
                info_font,
                line_gap=7,
            )

            y += 12
            draw.rectangle((left, y, right - 1, y + 46), outline=0, width=3)
            self._draw_centered_in_box(
                draw,
                "1 ПРИЗ · 1 ПОГАШЕНИЕ",
                (left, y, right, y + 46),
                self._font(24, bold=True),
            )
            y += 70

        self._draw_cut_line(draw, y, left=left, right=right)
        y += 30
        y = self._draw_centered_line(
            draw,
            "ХОЧЕШЬ ЕЩЁ?",
            y,
            self._font(36, bold=True),
        )
        y += 5
        secondary_font = self._font(22, bold=True)
        for line in self._wrap_text(
            draw,
            REGULAR_WHEEL_HEADLINE,
            secondary_font,
            content_width - 16,
        ):
            y = self._draw_centered_line(draw, line, y, secondary_font, line_gap=5)
        y = self._draw_centered_line(
            draw,
            "ЖИВЁТ В TELEGRAM",
            y,
            secondary_font,
            line_gap=5,
        )
        y += 10

        secondary_qr = render_wheel_receipt_qr(
            REGULAR_WHEEL_URL,
            max_size_px=252,
            error_correction="H",
            telegram_icon=True,
        )
        secondary_x = (self.paper_width_px - secondary_qr.image.width) // 2
        canvas.paste(secondary_qr.image, (secondary_x, y))
        qr_regions["regular_wheel"] = (
            secondary_x,
            y,
            secondary_x + secondary_qr.image.width,
            y + secondary_qr.image.height,
        )
        y += secondary_qr.image.height + 8
        y += 10

        self._draw_finish_bar(draw, y, left=left, right=right)
        y += 16

        if y > MAX_RECEIPT_HEIGHT_PX:
            raise ValueError("wheel prize receipt content exceeds maximum roll height")
        return canvas.crop((0, 0, self.paper_width_px, y)), qr_regions

    def _draw_prize_instruction(
        self,
        draw: ImageDraw.ImageDraw,
        data: _ReceiptData,
        y: int,
        *,
        left: int,
        right: int,
    ) -> int:
        """Draw the prize-specific handoff instruction in large Russian type."""
        content_width = right - left
        if data.prize_id in MERCH_PRIZE_IDS:
            return self._draw_instruction_box(
                draw,
                MERCH_REDEEM_LOCATION_LINES,
                y,
                left=left,
                right=right,
            )

        if data.prize_id in DRINK_PRIZE_IDS:
            venue = self._drink_venue(data.club_night)
            if venue:
                lines = (
                    "СОХРАНИ ИМЕННО ЭТОТ ЧЕК",
                    "С НИМ — В БАР",
                    venue,
                )
            else:
                lines = (
                    "СОХРАНИ ИМЕННО ЭТОТ ЧЕК",
                    "ПОКАЖИ ЕГО В БАРЕ",
                )
            return self._draw_instruction_box(
                draw,
                lines,
                y,
                left=left,
                right=right,
                inverted_first=True,
            )

        if data.prize_id in TICKET_PRIZE_IDS:
            lines = (
                "СОХРАНИ ИМЕННО ЭТОТ ЧЕК",
                "1 ЧЕЛОВЕК · 1 ПРОХОД",
                "ИСПОЛЬЗУЙ ПРИ СЛЕДУЮЩЕМ ВХОДЕ",
            )
            y = self._draw_instruction_box(
                draw,
                lines,
                y,
                left=left,
                right=right,
                inverted_first=True,
            )
            y += 14
            y = self._draw_centered_line(
                draw,
                "ДЕЙСТВУЕТ ТОЛЬКО",
                y,
                self._font(25, bold=True),
                line_gap=7,
            )
            slot_font = self._font(24, bold=True)
            if data.validity_lines:
                for validity_line in data.validity_lines:
                    for line in self._wrap_text(
                        draw,
                        validity_line,
                        slot_font,
                        content_width - 24,
                    ):
                        y = self._draw_centered_line(
                            draw,
                            line,
                            y,
                            slot_font,
                            line_gap=6,
                        )
            else:
                # The backend normally supplies both Fri/Sat slots.  This
                # explicit fallback never invents dates when the contract is
                # incomplete and still prints the authoritative expiry.
                y = self._draw_centered_line(
                    draw,
                    f"ДО {self._format_datetime(data.expires_at)}",
                    y,
                    self._font(21, bold=True),
                    line_gap=6,
                )
            return y

        if data.prize_id in TICKETSCLOUD_DISCOUNT_PRIZE_IDS:
            return self._draw_instruction_box(
                draw,
                (
                    "2 БЛИЖАЙШИЕ ВЕЧЕРИНКИ",
                    "КРОМЕ «ВСЕ СВОИ»",
                ),
                y,
                left=left,
                right=right,
            )

        # Historical or test-only prizes keep their server-authored terms.
        terms_font = self._font(23)
        for line in self._wrap_text(draw, data.terms, terms_font, content_width - 36):
            y = self._draw_centered_line(draw, line, y, terms_font, line_gap=7)
        return y

    def _draw_tix50_ticket(
        self,
        draw: ImageDraw.ImageDraw,
        data: _ReceiptData,
        y: int,
        *,
        left: int,
        right: int,
    ) -> int:
        """Draw the non-QR TicketsCloud promo ticket and its text code."""
        ticket_height = 226
        ticket_box = (left, y, right - 1, y + ticket_height)
        draw.rounded_rectangle(ticket_box, radius=22, outline=0, width=5)
        draw.rounded_rectangle(
            (left + 15, y + 15, right - 16, y + ticket_height - 15),
            radius=15,
            outline=0,
            width=2,
        )

        # White side notches create a recognizable physical-ticket silhouette.
        notch_radius = 22
        for center_x in (left, right - 1):
            draw.ellipse(
                (
                    center_x - notch_radius,
                    y + ticket_height // 2 - notch_radius,
                    center_x + notch_radius,
                    y + ticket_height // 2 + notch_radius,
                ),
                fill=255,
            )

        self._draw_centered_in_box(
            draw,
            "СКИДКА НА БИЛЕТЫ",
            (left + 20, y + 22, right - 20, y + 62),
            self._font(24, bold=True),
        )
        discount_text = "−50%"
        discount_font = self._fit_font(
            draw,
            discount_text,
            max_width=(right - left) - 76,
            max_size=112,
            min_size=82,
            bold=True,
        )
        self._draw_centered_in_box(
            draw,
            discount_text,
            (left + 24, y + 58, right - 24, y + ticket_height - 20),
            discount_font,
        )
        y += ticket_height + 20

        y = self._draw_centered_line(
            draw,
            "КОД ДЛЯ TICKETSCLOUD",
            y,
            self._font(25, bold=True),
            line_gap=9,
        )
        code_font = self._fit_font(
            draw,
            data.coupon_code,
            max_width=(right - left) - 40,
            max_size=48,
            min_size=20,
            bold=True,
        )
        code_bbox = draw.textbbox((0, 0), data.coupon_code, font=code_font)
        code_height = code_bbox[3] - code_bbox[1]
        code_box_height = max(72, code_height + 30)
        draw.rounded_rectangle(
            (left, y, right - 1, y + code_box_height),
            radius=12,
            fill=0,
        )
        self._draw_centered_in_box(
            draw,
            data.coupon_code,
            (left, y, right, y + code_box_height),
            code_font,
            fill=255,
        )
        y += code_box_height + 18

        instruction_font = self._font(23, bold=True)
        for line in (
            "ВВЕДИ КОД В TICKETSCLOUD",
            "АКТИВИРУЕТСЯ АВТОМАТИЧЕСКИ",
            "ПОСЛЕ ПУБЛИКАЦИИ ВЕЧЕРИНОК",
        ):
            y = self._draw_centered_line(
                draw,
                line,
                y,
                instruction_font,
                line_gap=6,
            )
        y += 6
        return self._draw_centered_line(
            draw,
            f"ВЫДАН · {self._format_datetime(data.issued_at)}",
            y,
            self._font(19, bold=True),
            line_gap=6,
        )

    def _draw_instruction_box(
        self,
        draw: ImageDraw.ImageDraw,
        lines: tuple[str, ...],
        y: int,
        *,
        left: int,
        right: int,
        inverted_first: bool = False,
    ) -> int:
        line_font = self._font(25, bold=True)
        first_font = self._font(27, bold=True)
        line_heights: list[int] = []
        for index, line in enumerate(lines):
            font = first_font if index == 0 else line_font
            bbox = draw.textbbox((0, 0), line, font=font)
            line_heights.append(bbox[3] - bbox[1])
        inner_gap = 10
        top_padding = 15
        bottom_padding = 15
        first_bar_extra = 14 if inverted_first else 0
        box_height = (
            top_padding
            + sum(line_heights)
            + inner_gap * max(0, len(lines) - 1)
            + bottom_padding
            + first_bar_extra
        )
        draw.rounded_rectangle(
            (left, y, right - 1, y + box_height),
            radius=14,
            outline=0,
            width=4,
        )
        current_y = y + top_padding
        for index, line in enumerate(lines):
            font = first_font if index == 0 else line_font
            if index == 0 and inverted_first:
                bar_height = line_heights[index] + 20
                draw.rounded_rectangle(
                    (left + 4, current_y - 10, right - 5, current_y - 10 + bar_height),
                    radius=9,
                    fill=0,
                )
                self._draw_centered_in_box(
                    draw,
                    line,
                    (left, current_y - 10, right, current_y - 10 + bar_height),
                    font,
                    fill=255,
                )
                current_y += bar_height + inner_gap
            else:
                current_y = self._draw_centered_line(
                    draw,
                    line,
                    current_y,
                    font,
                    line_gap=inner_gap,
                )
        return y + box_height

    def _primary_qr_heading(self, prize_id: str) -> str:
        if prize_id in MERCH_PRIZE_IDS:
            return "QR ДЛЯ ПОЛУЧЕНИЯ МЕРЧА"
        if prize_id in DRINK_PRIZE_IDS:
            return "QR ДЛЯ БАРА"
        if prize_id in TICKET_PRIZE_IDS:
            return "QR ДЛЯ ПРОХОДА"
        return "QR ДЛЯ ПОЛУЧЕНИЯ ПРИЗА"

    def _drink_venue(self, club_night: date) -> str | None:
        if club_night.weekday() == 4:
            return "В МАЛУЮ ВИНОВНИЦУ"
        if club_night.weekday() == 5:
            return "В АНГАР"
        return None

    def _club_night_date(self, raw_value: Any, issued_at: datetime) -> date:
        if isinstance(raw_value, datetime):
            return raw_value.astimezone(MOSCOW_TZ).date()
        if isinstance(raw_value, date):
            return raw_value
        if isinstance(raw_value, str) and raw_value.strip():
            try:
                return date.fromisoformat(raw_value.strip()[:10])
            except ValueError:
                pass
        local = issued_at.astimezone(MOSCOW_TZ)
        if local.timetz().replace(tzinfo=None) < CLUB_NIGHT_END:
            return local.date() - timedelta(days=1)
        return local.date()

    def _format_validity_slot(self, slot: dict[str, Any]) -> str:
        starts_at = self._optional_datetime(slot.get("starts_at") or slot.get("start"))
        ends_at = self._optional_datetime(slot.get("ends_at") or slot.get("end"))
        if starts_at and ends_at:
            return self._format_slot_interval(starts_at, ends_at)

        raw_night = slot.get("club_night")
        raw_label = str(slot.get("label") or "").strip()
        slot_date: date | None = None
        for candidate in (raw_night, raw_label):
            if isinstance(candidate, date):
                slot_date = candidate
                break
            if not isinstance(candidate, str) or not candidate.strip():
                continue
            clean = candidate.strip()
            for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
                try:
                    slot_date = datetime.strptime(clean[:10], date_format).date()
                    break
                except ValueError:
                    continue
            if slot_date:
                break
        if slot_date:
            start = datetime.combine(slot_date, CLUB_NIGHT_START, tzinfo=MOSCOW_TZ)
            end = datetime.combine(slot_date + timedelta(days=1), CLUB_NIGHT_END, tzinfo=MOSCOW_TZ)
            return self._format_slot_interval(start, end)
        return raw_label

    def _optional_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError:
                return None
        else:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=MOSCOW_TZ)
        return parsed.astimezone(MOSCOW_TZ)

    def _format_slot_interval(self, start: datetime, end: datetime) -> str:
        weekday = ("ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС")[start.weekday()]
        return (
            f"{weekday} {start.strftime('%d.%m.%Y')} · "
            f"{start.strftime('%H:%M')}–{end.strftime('%H:%M')}"
        )

    def image_to_escpos(self, image: Image.Image) -> bytes:
        """Convert the final 576px receipt into RP80 ESC/POS raster bytes."""
        if image.width != self.paper_width_px:
            raise ValueError("wheel prize receipt must be exactly 576px wide")

        mono = ImageOps.autocontrast(image.convert("L"))
        mono = mono.convert("1", dither=Image.Dither.FLOYDSTEINBERG)
        width, height = mono.size
        bytes_per_line = width // 8
        pixels = mono.load()
        raster = bytearray()
        for row in range(height):
            for x_byte in range(bytes_per_line):
                value = 0
                for bit in range(8):
                    if pixels[x_byte * 8 + bit, row] == 0:
                        value |= 0x80 >> bit
                raster.append(value)

        commands = bytearray(b"\x1b@\x1b3\x18\x1dv0\x00")
        commands += bytes([bytes_per_line & 0xFF, (bytes_per_line >> 8) & 0xFF])
        commands += bytes([height & 0xFF, (height >> 8) & 0xFF])
        commands += raster
        commands += b"\x1b2\x1bd\x04\x1dV\x01"
        return bytes(commands)

    def _load_classic_logo(self, max_size: int) -> Image.Image:
        if not self.logo_path.is_file():
            raise FileNotFoundError(f"canonical VNVNC logo not found: {self.logo_path}")
        with Image.open(self.logo_path) as source:
            rgba = source.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        logo = background.convert("L")
        logo = ImageOps.autocontrast(logo)
        logo.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        return logo.point(lambda value: 0 if value < 210 else 255, mode="1").convert("L")

    def _required_text(self, data: dict[str, Any], key: str) -> str:
        value = str(data.get(key) or "").strip()
        if not value:
            raise ValueError(f"wheel prize receipt requires {key}")
        return value

    def _required_datetime(
        self,
        data: dict[str, Any],
        key: str,
        *,
        aliases: tuple[str, ...] = (),
    ) -> datetime:
        value: Any = data.get(key)
        if value is None:
            for alias in aliases:
                value = data.get(alias)
                if value is not None:
                    break
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            try:
                parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"invalid {key} timestamp") from exc
        else:
            raise ValueError(f"wheel prize receipt requires {key}")
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=MOSCOW_TZ)
        return parsed.astimezone(MOSCOW_TZ)

    def _font(self, size: int, *, bold: bool = False) -> ImageFont.ImageFont:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
            if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
            if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for candidate in candidates:
            try:
                return ImageFont.truetype(candidate, size)
            except OSError:
                continue
        return ImageFont.load_default()

    def _fit_font(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        *,
        max_width: int,
        max_size: int,
        min_size: int,
        bold: bool,
    ) -> ImageFont.ImageFont:
        for size in range(max_size, min_size - 1, -1):
            font = self._font(size, bold=bold)
            if self._text_width(draw, text, font) <= max_width:
                return font
        return self._font(min_size, bold=bold)

    def _fit_multiline_font(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        *,
        max_width: int,
        max_size: int,
        min_size: int,
        bold: bool,
        max_lines: int,
    ) -> ImageFont.ImageFont:
        for size in range(max_size, min_size - 1, -1):
            font = self._font(size, bold=bold)
            if len(self._wrap_text(draw, text, font, max_width)) <= max_lines:
                return font
        return self._font(min_size, bold=bold)

    def _wrap_text(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
        max_width: int,
    ) -> list[str]:
        words = " ".join(str(text).split()).split()
        lines: list[str] = []
        current = ""
        for word in words:
            if self._text_width(draw, word, font) > max_width:
                if current:
                    lines.append(current)
                    current = ""
                pieces = self._split_long_word(draw, word, font, max_width)
                lines.extend(pieces[:-1])
                current = pieces[-1]
                continue
            candidate = word if not current else f"{current} {word}"
            if self._text_width(draw, candidate, font) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    def _split_long_word(
        self,
        draw: ImageDraw.ImageDraw,
        word: str,
        font: ImageFont.ImageFont,
        max_width: int,
    ) -> list[str]:
        pieces: list[str] = []
        current = ""
        for character in word:
            candidate = current + character
            if current and self._text_width(draw, candidate, font) > max_width:
                pieces.append(current)
                current = character
            else:
                current = candidate
        if current:
            pieces.append(current)
        return pieces or [word]

    def _draw_centered_line(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        y: int,
        font: ImageFont.ImageFont,
        *,
        line_gap: int = 9,
    ) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        x = (self.paper_width_px - width) // 2
        draw.text((x, y - bbox[1]), text, fill=0, font=font)
        return y + height + line_gap

    def _draw_centered_in_box(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        box: tuple[int, int, int, int],
        font: ImageFont.ImageFont,
        *,
        fill: int = 0,
    ) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        x = box[0] + ((box[2] - box[0]) - width) // 2
        y = box[1] + ((box[3] - box[1]) - height) // 2 - bbox[1]
        draw.text((x, y), text, fill=fill, font=font)

    def _draw_cut_line(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        *,
        left: int,
        right: int,
    ) -> None:
        dash_width = 18
        gap = 10
        x = left
        while x < right:
            draw.line((x, y, min(x + dash_width, right), y), fill=0, width=3)
            x += dash_width + gap
        draw.polygon([(left, y), (left + 12, y - 7), (left + 12, y + 7)], fill=0)
        draw.polygon([(right - 1, y), (right - 13, y - 7), (right - 13, y + 7)], fill=0)

    def _draw_finish_bar(
        self,
        draw: ImageDraw.ImageDraw,
        y: int,
        *,
        left: int,
        right: int,
    ) -> None:
        cell = 12
        for index, x in enumerate(range(left, right, cell)):
            if index % 2 == 0:
                draw.rectangle((x, y, min(x + cell - 1, right - 1), y + 9), fill=0)
        draw.line((left, y + 12, right - 1, y + 12), fill=0, width=3)

    def _format_datetime(self, value: datetime) -> str:
        return value.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y · %H:%M МСК")

    def _text_width(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.ImageFont,
    ) -> int:
        bbox = draw.textbbox((0, 0), text, font=font)
        return bbox[2] - bbox[0]

"""QR rendering helpers for the physical VNVNC prize-drum receipt.

The helpers deliberately keep QR modules on an integer pixel grid and retain
the ISO-recommended four-module quiet zone.  Do not use bilinear/Lanczos
resampling here: a thermal printer needs hard module edges.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw
import qrcode


@dataclass(frozen=True, slots=True)
class WheelReceiptQR:
    """A QR image plus geometry used by receipt verification tests."""

    image: Image.Image
    payload: str
    module_count: int
    quiet_zone_modules: int
    pixels_per_module: int
    error_correction: str
    has_telegram_icon: bool


_ERROR_CORRECTION = {
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}


def render_wheel_receipt_qr(
    payload: str,
    *,
    max_size_px: int,
    error_correction: str,
    telegram_icon: bool = False,
    quiet_zone_modules: int = 4,
) -> WheelReceiptQR:
    """Render a monochrome QR without fractional module scaling.

    Args:
        payload: Exact data encoded in the QR.
        max_size_px: Maximum square size available in the receipt.
        error_correction: One of ``M``, ``Q`` or ``H``.
        telegram_icon: Draw the monochrome Telegram mark in the center.  This
            is allowed only with EC-H because the mark replaces data modules.
        quiet_zone_modules: White modules surrounding the QR; fixed at four
            for the receipt contract.
    """
    clean_payload = str(payload).strip()
    if not clean_payload:
        raise ValueError("QR payload must not be empty")
    if quiet_zone_modules != 4:
        raise ValueError("wheel receipt QRs require a four-module quiet zone")

    level = str(error_correction).upper()
    if level not in _ERROR_CORRECTION:
        raise ValueError("error_correction must be M, Q, or H")
    if telegram_icon and level != "H":
        raise ValueError("Telegram icon requires EC-H")

    qr = qrcode.QRCode(
        version=None,
        error_correction=_ERROR_CORRECTION[level],
        box_size=1,
        border=quiet_zone_modules,
    )
    qr.add_data(clean_payload)
    qr.make(fit=True)

    module_count = int(qr.modules_count)
    total_modules = module_count + quiet_zone_modules * 2
    pixels_per_module = int(max_size_px) // total_modules
    if pixels_per_module < 3:
        raise ValueError("QR allocation is too small for reliable thermal printing")

    base = qr.make_image(fill_color="black", back_color="white").convert("L")
    exact_size = total_modules * pixels_per_module
    image = base.resize((exact_size, exact_size), Image.Resampling.NEAREST)

    if telegram_icon:
        _draw_telegram_icon(
            image,
            module_count=module_count,
            quiet_zone_modules=quiet_zone_modules,
            pixels_per_module=pixels_per_module,
        )

    return WheelReceiptQR(
        image=image,
        payload=clean_payload,
        module_count=module_count,
        quiet_zone_modules=quiet_zone_modules,
        pixels_per_module=pixels_per_module,
        error_correction=level,
        has_telegram_icon=telegram_icon,
    )


def _draw_telegram_icon(
    image: Image.Image,
    *,
    module_count: int,
    quiet_zone_modules: int,
    pixels_per_module: int,
) -> None:
    """Draw a small thermal-friendly Telegram paper-plane badge.

    The badge footprint is aligned to whole modules.  EC-H recovers the
    covered center modules, while the four-module outer quiet zone is never
    touched.
    """
    icon_modules = min(9, max(7, module_count // 5))
    if icon_modules % 2 == 0:
        icon_modules -= 1

    total_modules = module_count + quiet_zone_modules * 2
    top_module = (total_modules - icon_modules) // 2
    left = top_module * pixels_per_module
    top = top_module * pixels_per_module
    size = icon_modules * pixels_per_module
    right = left + size - 1
    bottom = top + size - 1
    unit = pixels_per_module

    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (left - unit, top - unit, right + unit, bottom + unit),
        radius=2 * unit,
        fill=255,
    )
    draw.ellipse((left, top, right, bottom), fill=0)

    # The familiar Telegram paper plane, reduced to a high-contrast polygon
    # that survives 203dpi thermal dithering.
    def point(x: float, y: float) -> tuple[int, int]:
        return (left + round(size * x), top + round(size * y))

    draw.polygon(
        [
            point(0.18, 0.48),
            point(0.79, 0.21),
            point(0.66, 0.76),
            point(0.46, 0.60),
            point(0.34, 0.72),
            point(0.36, 0.55),
        ],
        fill=255,
    )
    draw.line(
        [point(0.36, 0.55), point(0.66, 0.34), point(0.46, 0.60)],
        fill=0,
        width=max(1, unit // 2),
    )

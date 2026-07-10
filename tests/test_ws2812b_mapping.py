import numpy as np

from artifact.graphics.fonts.pixel_font import draw_text_bitmap, get_ticker_font
from artifact.hardware.display.ws2812b import WS2812BDisplay
import artifact.hardware.display.ws2812b as ws2812b_module
from artifact.hardware.runner import HardwareConfig


class _FakePixelStrip:
    def __init__(self, *args, **kwargs) -> None:
        self.args = args
        self.kwargs = kwargs

    def begin(self) -> None:
        pass

    def setPixelColor(self, index: int, color: int) -> None:
        pass

    def show(self) -> None:
        pass


class _FakeWS281x:
    WS2811_STRIP_RGB = 0x100800
    WS2811_STRIP_GRB = 0x081000

    def __init__(self) -> None:
        self.created = None

    def PixelStrip(self, *args, **kwargs):
        self.created = _FakePixelStrip(*args, **kwargs)
        return self.created


def build_display() -> WS2812BDisplay:
    return WS2812BDisplay(width=48, height=8)


def test_hardware_runner_uses_physically_verified_ticker_brightness() -> None:
    assert HardwareConfig().ws2812b_brightness == 32


def test_driver_explicitly_configures_grb_strip_order(monkeypatch) -> None:
    fake = _FakeWS281x()
    monkeypatch.setattr(ws2812b_module, "_get_rpi_ws281x", lambda: fake)

    display = build_display()

    assert display.init()
    assert fake.created.kwargs["strip_type"] == fake.WS2811_STRIP_GRB


def test_mapping_is_complete_and_unique() -> None:
    display = build_display()
    indexes = {display._xy_to_index(x, y) for x in range(48) for y in range(8)}

    assert indexes == set(range(48 * 8))


def test_right_matrix_matches_december_baseline() -> None:
    display = build_display()

    assert display._xy_to_index(47, 7) == 0
    assert display._xy_to_index(47, 0) == 7
    assert display._xy_to_index(46, 0) == 8
    assert display._xy_to_index(46, 7) == 15
    assert display._xy_to_index(40, 0) == 56
    assert display._xy_to_index(40, 7) == 63


def test_middle_matrix_matches_december_baseline() -> None:
    display = build_display()

    assert display._xy_to_index(39, 7) == 64
    assert display._xy_to_index(39, 0) == 71
    assert display._xy_to_index(38, 0) == 72
    assert display._xy_to_index(38, 7) == 79
    assert display._xy_to_index(8, 0) == 312
    assert display._xy_to_index(8, 7) == 319


def test_left_matrix_matches_december_baseline() -> None:
    display = build_display()

    assert display._xy_to_index(7, 7) == 320
    assert display._xy_to_index(7, 0) == 327
    assert display._xy_to_index(6, 0) == 328
    assert display._xy_to_index(6, 7) == 335
    assert display._xy_to_index(0, 0) == 376
    assert display._xy_to_index(0, 7) == 383


def test_boiling_text_snapshot_matches_december_baseline() -> None:
    display = build_display()
    buffer = np.zeros((8, 48, 3), dtype=np.uint8)

    draw_text_bitmap(buffer, "BOILING", 0, 0, (255, 0, 0), get_ticker_font(), 1)

    lit_indexes = [
        display._xy_to_index(x, y)
        for y in range(8)
        for x in range(48)
        if buffer[y, x].any()
    ]

    assert lit_indexes == [
        376, 375, 360, 359, 327, 312, 311, 280, 279, 264, 263, 248, 232, 184,
        183, 168, 167, 152, 136, 104, 87, 72, 71, 377, 345, 329, 297, 265, 233,
        169, 137, 134, 105, 89, 57, 378, 346, 330, 298, 266, 234, 170, 138, 122,
        106, 90, 379, 372, 363, 356, 331, 299, 267, 235, 171, 139, 123, 107, 91,
        380, 348, 332, 300, 268, 236, 172, 140, 115, 108, 92, 76, 67, 60, 381,
        349, 333, 301, 269, 237, 173, 141, 109, 93, 61, 382, 350, 334, 302, 270,
        238, 174, 142, 110, 94, 62, 383, 368, 367, 352, 320, 319, 304, 287, 272,
        271, 256, 255, 239, 224, 223, 208, 207, 191, 176, 175, 160, 159, 143,
        111, 80, 79, 64,
    ]

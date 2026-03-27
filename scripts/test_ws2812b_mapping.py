#!/usr/bin/env python3
"""
Display a deterministic ticker wiring diagnostic on the 48x8 WS2812B strip.

This is meant to verify the December 31, 2025 cabinet mapping on real hardware.

Usage:
    sudo PYTHONPATH=src python scripts/test_ws2812b_mapping.py
    sudo PYTHONPATH=src python scripts/test_ws2812b_mapping.py --mock
"""

import sys
import time

import numpy as np

sys.path.insert(0, "src")

from artifact.hardware.display import WS2812BDisplay, WS2812BDisplayMock
from artifact.graphics.fonts.pixel_font import draw_text_bitmap, get_ticker_font


WIDTH = 48
HEIGHT = 8
FRAME_DELAY = 1.5


def make_display(mock: bool):
    if mock:
        return WS2812BDisplayMock(width=WIDTH, height=HEIGHT)
    return WS2812BDisplay(width=WIDTH, height=HEIGHT, brightness=128, gpio_pin=21)


def matrix_blocks() -> np.ndarray:
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    frame[:, 0:8] = (0, 0, 255)
    frame[:, 8:40] = (0, 255, 0)
    frame[:, 40:48] = (255, 0, 0)
    frame[:, 7:9] = (255, 255, 255)
    frame[:, 39:41] = (255, 255, 255)
    return frame


def parity_stripes() -> np.ndarray:
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for x in range(WIDTH):
        if x % 2 == 0:
            frame[0:4, x] = (255, 160, 0)
        else:
            frame[4:8, x] = (0, 180, 255)
    return frame


def corner_markers() -> np.ndarray:
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    markers = {
        (0, 0): (255, 255, 255),
        (0, 7): (255, 0, 255),
        (7, 0): (255, 255, 0),
        (7, 7): (255, 128, 0),
        (8, 0): (0, 255, 255),
        (8, 7): (0, 128, 255),
        (39, 0): (0, 255, 0),
        (39, 7): (0, 128, 0),
        (40, 0): (255, 0, 0),
        (40, 7): (160, 0, 0),
        (47, 0): (180, 180, 180),
        (47, 7): (255, 255, 255),
    }
    for (x, y), color in markers.items():
        frame[y, x] = color
    return frame


def first_pixel_trace() -> np.ndarray:
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    trace = [
        (47, 7), (47, 0),
        (46, 0), (46, 7),
        (39, 7), (39, 0),
        (38, 0), (38, 7),
        (7, 7), (7, 0),
        (6, 0), (6, 7),
    ]
    for i, (x, y) in enumerate(trace):
        color = (255, 255, 255) if i % 2 == 0 else (255, 64, 0)
        frame[y, x] = color
    return frame


def text_sample() -> np.ndarray:
    frame = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    draw_text_bitmap(frame, "BOILING", 0, 0, (255, 0, 0), get_ticker_font(), 1)
    return frame


def show_frame(display, label: str, frame: np.ndarray) -> None:
    print(label)
    display.set_buffer(frame)
    display.show()
    time.sleep(FRAME_DELAY)


def main() -> int:
    mock = "--mock" in sys.argv or "-m" in sys.argv
    once = "--once" in sys.argv

    display = make_display(mock)
    if not display.init():
        print("WARNING: display init returned False")

    frames = [
        ("matrix blocks: left=blue middle=green right=red", matrix_blocks()),
        ("parity stripes: even cols top, odd cols bottom", parity_stripes()),
        ("corner markers: matrix edges and boundaries", corner_markers()),
        ("first-pixel trace: verifies serpentine start points", first_pixel_trace()),
        ("text sample: BOILING should read cleanly with no flipped letters", text_sample()),
    ]

    try:
        while True:
            for label, frame in frames:
                show_frame(display, label, frame)
            if once:
                break
    finally:
        display.clear(0, 0, 0)
        display.show()
        if hasattr(display, "cleanup"):
            display.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

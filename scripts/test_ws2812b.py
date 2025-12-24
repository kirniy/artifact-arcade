#!/usr/bin/env python3
"""
Test WS2812B LED ticker display.

Tests the 48x8 LED matrix (384 LEDs total) on GPIO 21.

Usage:
    sudo PYTHONPATH=src python scripts/test_ws2812b.py
"""

import sys
import time
import numpy as np

sys.path.insert(0, "src")

from artifact.hardware.display import WS2812BDisplay, WS2812BDisplayMock


def test_solid_colors(display, delay=0.5):
    """Display solid colors."""
    colors = [
        ((255, 0, 0), "RED"),
        ((0, 255, 0), "GREEN"),
        ((0, 0, 255), "BLUE"),
        ((255, 255, 0), "YELLOW"),
        ((255, 0, 255), "MAGENTA"),
        ((0, 255, 255), "CYAN"),
        ((255, 255, 255), "WHITE"),
    ]

    for (r, g, b), name in colors:
        print(f"  {name}...")
        display.clear(r, g, b)
        display.show()
        time.sleep(delay)

    display.clear(0, 0, 0)
    display.show()


def test_column_sweep(display, delay=0.02):
    """Sweep a column across the display."""
    print("  Column sweep...")

    for x in range(48):
        display.clear(0, 0, 0)
        for y in range(8):
            display.set_pixel(x, y, 0, 255, 0)
        display.show()
        time.sleep(delay)

    display.clear(0, 0, 0)
    display.show()


def test_row_sweep(display, delay=0.1):
    """Sweep a row across the display."""
    print("  Row sweep...")

    for y in range(8):
        display.clear(0, 0, 0)
        for x in range(48):
            display.set_pixel(x, y, 255, 0, 0)
        display.show()
        time.sleep(delay)

    display.clear(0, 0, 0)
    display.show()


def test_rainbow(display, duration=3.0):
    """Display rainbow pattern."""
    print("  Rainbow (3 sec)...")
    buffer = np.zeros((8, 48, 3), dtype=np.uint8)
    start = time.time()

    while time.time() - start < duration:
        offset = int((time.time() - start) * 20)

        for x in range(48):
            hue = ((x + offset) % 48) / 48.0
            # HSV to RGB (simplified)
            if hue < 1/6:
                r, g, b = 255, int(hue * 6 * 255), 0
            elif hue < 2/6:
                r, g, b = int((2/6 - hue) * 6 * 255), 255, 0
            elif hue < 3/6:
                r, g, b = 0, 255, int((hue - 2/6) * 6 * 255)
            elif hue < 4/6:
                r, g, b = 0, int((4/6 - hue) * 6 * 255), 255
            elif hue < 5/6:
                r, g, b = int((hue - 4/6) * 6 * 255), 0, 255
            else:
                r, g, b = 255, 0, int((1 - hue) * 6 * 255)

            for y in range(8):
                buffer[y, x] = [r, g, b]

        display.set_buffer(buffer)
        display.show()
        time.sleep(1 / 60)

    display.clear(0, 0, 0)
    display.show()


def test_brightness_levels(display, delay=0.5):
    """Test different brightness levels."""
    print("  Brightness levels...")

    for brightness in [16, 32, 64, 128, 255]:
        print(f"    Brightness: {brightness}")
        display.set_brightness(brightness)
        display.clear(255, 255, 255)
        display.show()
        time.sleep(delay)

    # Reset to default
    display.set_brightness(128)
    display.clear(0, 0, 0)
    display.show()


def test_scrolling_text_simulation(display, delay=0.05):
    """Simulate scrolling text (pattern only, not actual text)."""
    print("  Scrolling pattern...")
    buffer = np.zeros((8, 48, 3), dtype=np.uint8)

    # Create a simple pattern that looks like scrolling
    for frame in range(96):
        buffer.fill(0)

        # Create vertical bars pattern
        for x in range(48):
            if (x + frame) % 8 < 4:
                for y in range(8):
                    buffer[y, x] = [255, 128, 0]  # Orange

        display.set_buffer(buffer)
        display.show()
        time.sleep(delay)

    display.clear(0, 0, 0)
    display.show()


def main():
    print("=" * 50)
    print("WS2812B Ticker Display Test")
    print("GPIO 21 - 48x8 = 384 LEDs")
    print("=" * 50)

    # Check for mock mode
    use_mock = "--mock" in sys.argv or "-m" in sys.argv

    if use_mock:
        print("\nUsing mock display (no hardware)")
        display = WS2812BDisplayMock(width=48, height=8)
    else:
        print("\nUsing real WS2812B display on GPIO 21")
        display = WS2812BDisplay(width=48, height=8, brightness=128, gpio_pin=21)

    print("\nInitializing display...")
    if not display.init():
        print("WARNING: Display init returned False (may be mock)")

    print("Display ready!")
    print("\nPress Ctrl+C to exit at any time.\n")

    try:
        while True:
            print("Testing solid colors...")
            test_solid_colors(display)

            print("Testing column sweep...")
            test_column_sweep(display)

            print("Testing row sweep...")
            test_row_sweep(display)

            print("Testing rainbow...")
            test_rainbow(display)

            if not use_mock:
                print("Testing brightness levels...")
                test_brightness_levels(display)

            print("Testing scrolling pattern...")
            test_scrolling_text_simulation(display)

            print("\n--- Loop complete, repeating ---\n")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")

    finally:
        print("Cleaning up...")
        display.clear(0, 0, 0)
        display.show()
        if hasattr(display, 'cleanup'):
            display.cleanup()
        print("Done!")


if __name__ == "__main__":
    main()

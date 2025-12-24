#!/usr/bin/env python3
"""
Test HDMI display output for NovaStar T50.

Outputs test patterns to the 128x128 HDMI display.
The T50 receives this signal and forwards it to the DH418/panels.

Usage:
    sudo PYTHONPATH=src python scripts/test_hdmi.py
"""

import sys
import time
import numpy as np

sys.path.insert(0, "src")

from artifact.hardware.display import HDMIDisplay, HDMIDisplayScaled


def test_solid_colors(display, delay=1.0):
    """Display solid colors."""
    colors = [
        ((255, 0, 0), "RED"),
        ((0, 255, 0), "GREEN"),
        ((0, 0, 255), "BLUE"),
        ((255, 255, 0), "YELLOW"),
        ((255, 0, 255), "MAGENTA"),
        ((0, 255, 255), "CYAN"),
        ((255, 255, 255), "WHITE"),
        ((0, 0, 0), "BLACK"),
    ]

    for (r, g, b), name in colors:
        print(f"  {name}...")
        display.clear(r, g, b)
        display.show()
        time.sleep(delay)


def test_gradient(display, delay=2.0):
    """Display color gradient."""
    print("  Gradient...")
    buffer = np.zeros((128, 128, 3), dtype=np.uint8)

    for y in range(128):
        for x in range(128):
            buffer[y, x] = [
                int(x * 2),      # Red: left to right
                int(y * 2),      # Green: top to bottom
                128,             # Blue: constant
            ]

    display.set_buffer(buffer)
    display.show()
    time.sleep(delay)


def test_grid(display, delay=2.0):
    """Display grid pattern."""
    print("  Grid pattern...")
    buffer = np.zeros((128, 128, 3), dtype=np.uint8)

    for y in range(128):
        for x in range(128):
            if (x // 8 + y // 8) % 2 == 0:
                buffer[y, x] = [255, 255, 255]
            else:
                buffer[y, x] = [0, 0, 0]

    display.set_buffer(buffer)
    display.show()
    time.sleep(delay)


def test_corners(display, delay=2.0):
    """Display corner markers."""
    print("  Corner markers...")
    display.clear(0, 0, 0)

    # Red top-left
    for y in range(16):
        for x in range(16):
            display.set_pixel(x, y, 255, 0, 0)

    # Green top-right
    for y in range(16):
        for x in range(112, 128):
            display.set_pixel(x, y, 0, 255, 0)

    # Blue bottom-left
    for y in range(112, 128):
        for x in range(16):
            display.set_pixel(x, y, 0, 0, 255)

    # Yellow bottom-right
    for y in range(112, 128):
        for x in range(112, 128):
            display.set_pixel(x, y, 255, 255, 0)

    display.show()
    time.sleep(delay)


def test_animation(display, frames=120):
    """Display simple animation."""
    print("  Animation (2 sec)...")
    buffer = np.zeros((128, 128, 3), dtype=np.uint8)

    for frame in range(frames):
        buffer.fill(0)

        # Moving circle
        cx = 64 + int(40 * np.sin(frame * 0.1))
        cy = 64 + int(40 * np.cos(frame * 0.1))

        for y in range(128):
            for x in range(128):
                dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                if dist < 20:
                    buffer[y, x] = [255, 128, 0]  # Orange

        display.set_buffer(buffer)
        display.show()
        time.sleep(1 / 60)  # 60 FPS


def main():
    print("=" * 50)
    print("HDMI Display Test for NovaStar T50")
    print("=" * 50)

    # Check for scale argument
    use_scaled = "--scaled" in sys.argv or "-s" in sys.argv

    if use_scaled:
        print("\nUsing scaled display (4x upscale to 512x512)")
        display = HDMIDisplayScaled(width=128, height=128, scale=4)
    else:
        print("\nUsing native 128x128 display")
        display = HDMIDisplay(width=128, height=128)

    print("\nInitializing display...")
    if not display.init():
        print("ERROR: Failed to initialize display!")
        sys.exit(1)

    print("Display initialized successfully!")
    print("\nPress Ctrl+C to exit at any time.\n")

    try:
        while True:
            print("Testing solid colors...")
            test_solid_colors(display, delay=0.5)

            print("Testing gradient...")
            test_gradient(display)

            print("Testing grid pattern...")
            test_grid(display)

            print("Testing corner markers...")
            test_corners(display)

            print("Testing animation...")
            test_animation(display)

            print("\n--- Loop complete, repeating ---\n")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")

    finally:
        print("Cleaning up...")
        display.cleanup()
        print("Done!")


if __name__ == "__main__":
    main()

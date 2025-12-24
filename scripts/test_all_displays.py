#!/usr/bin/env python3
"""
Test all ARTIFACT displays simultaneously.

Tests:
- HDMI output (128x128) via NovaStar T50
- WS2812B ticker (48x8) on GPIO 21
- I2C LCD (16x2) on I2C bus

Usage:
    sudo PYTHONPATH=src python scripts/test_all_displays.py

Options:
    --mock    Use mock displays (no hardware)
    --scaled  Use 4x scaled HDMI output
"""

import sys
import time
import numpy as np

sys.path.insert(0, "src")


def init_displays(use_mock=False, use_scaled=False):
    """Initialize all displays."""
    displays = {}

    # HDMI Display
    try:
        if use_mock or use_scaled:
            from artifact.hardware.display import HDMIDisplayScaled
            displays['main'] = HDMIDisplayScaled(128, 128, scale=4)
        else:
            from artifact.hardware.display import HDMIDisplay
            displays['main'] = HDMIDisplay(128, 128)

        if displays['main'].init():
            print("  HDMI: OK")
        else:
            print("  HDMI: FAILED")
            displays['main'] = None
    except Exception as e:
        print(f"  HDMI: ERROR - {e}")
        displays['main'] = None

    # WS2812B Ticker
    try:
        if use_mock:
            from artifact.hardware.display import WS2812BDisplayMock
            displays['ticker'] = WS2812BDisplayMock(48, 8)
        else:
            from artifact.hardware.display import WS2812BDisplay
            displays['ticker'] = WS2812BDisplay(48, 8, brightness=128, gpio_pin=21)

        if hasattr(displays['ticker'], 'init'):
            displays['ticker'].init()
        print("  Ticker: OK")
    except Exception as e:
        print(f"  Ticker: ERROR - {e}")
        displays['ticker'] = None

    # I2C LCD
    try:
        if use_mock:
            from artifact.hardware.display import I2CLCDDisplayMock
            displays['lcd'] = I2CLCDDisplayMock(16, 2)
        else:
            from artifact.hardware.display import I2CLCDDisplay
            displays['lcd'] = I2CLCDDisplay(16, 2)

        if hasattr(displays['lcd'], 'init'):
            displays['lcd'].init()
        print("  LCD: OK")
    except Exception as e:
        print(f"  LCD: ERROR - {e}")
        displays['lcd'] = None

    return displays


def test_all_red(displays):
    """Fill all displays with red."""
    if displays.get('main'):
        displays['main'].clear(255, 0, 0)
        displays['main'].show()

    if displays.get('ticker'):
        displays['ticker'].clear(255, 0, 0)
        displays['ticker'].show()

    if displays.get('lcd'):
        displays['lcd'].clear()
        displays['lcd'].write("=== RED ===", row=0, col=2)


def test_all_green(displays):
    """Fill all displays with green."""
    if displays.get('main'):
        displays['main'].clear(0, 255, 0)
        displays['main'].show()

    if displays.get('ticker'):
        displays['ticker'].clear(0, 255, 0)
        displays['ticker'].show()

    if displays.get('lcd'):
        displays['lcd'].clear()
        displays['lcd'].write("=== GREEN ===", row=0, col=1)


def test_all_blue(displays):
    """Fill all displays with blue."""
    if displays.get('main'):
        displays['main'].clear(0, 0, 255)
        displays['main'].show()

    if displays.get('ticker'):
        displays['ticker'].clear(0, 0, 255)
        displays['ticker'].show()

    if displays.get('lcd'):
        displays['lcd'].clear()
        displays['lcd'].write("=== BLUE ===", row=0, col=2)


def test_synchronized_animation(displays, duration=5.0):
    """Run synchronized animation on all displays."""
    start = time.time()
    frame = 0

    main_buffer = np.zeros((128, 128, 3), dtype=np.uint8)
    ticker_buffer = np.zeros((8, 48, 3), dtype=np.uint8)

    while time.time() - start < duration:
        t = time.time() - start

        # Main display: pulsing circle
        if displays.get('main'):
            main_buffer.fill(0)
            cx, cy = 64, 64
            radius = 30 + int(20 * np.sin(t * 3))

            for y in range(128):
                for x in range(128):
                    dist = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
                    if dist < radius:
                        # Gradient from center
                        intensity = int(255 * (1 - dist / radius))
                        main_buffer[y, x] = [intensity, 0, intensity]

            displays['main'].set_buffer(main_buffer)
            displays['main'].show()

        # Ticker: scrolling wave
        if displays.get('ticker'):
            ticker_buffer.fill(0)
            for x in range(48):
                wave_y = int(3.5 + 3.5 * np.sin((x + frame * 0.3) * 0.3))
                if 0 <= wave_y < 8:
                    # Color based on position
                    hue = (x / 48.0 + t * 0.1) % 1.0
                    if hue < 0.33:
                        color = [255, int(hue * 3 * 255), 0]
                    elif hue < 0.66:
                        color = [int((0.66 - hue) * 3 * 255), 255, 0]
                    else:
                        color = [0, int((1 - hue) * 3 * 255), 255]
                    ticker_buffer[wave_y, x] = color

            displays['ticker'].set_buffer(ticker_buffer)
            displays['ticker'].show()

        # LCD: frame counter
        if displays.get('lcd'):
            if frame % 6 == 0:  # Update less frequently
                displays['lcd'].write(f"Frame: {frame:>6}", row=0, col=0)
                displays['lcd'].write(f"Time: {t:>6.1f}s", row=1, col=0)

        frame += 1
        time.sleep(1 / 60)  # 60 FPS


def test_startup_sequence(displays):
    """Simulate startup sequence."""
    # LCD shows loading
    if displays.get('lcd'):
        displays['lcd'].clear()
        displays['lcd'].write("ARTIFACT", row=0, col=4)
        displays['lcd'].write("Loading...", row=1, col=3)

    # Main display: fade in
    if displays.get('main'):
        for i in range(32):
            brightness = i * 8
            displays['main'].clear(brightness, 0, brightness // 2)
            displays['main'].show()
            time.sleep(0.03)

    # Ticker: sweep
    if displays.get('ticker'):
        for x in range(48):
            displays['ticker'].clear(0, 0, 0)
            for y in range(8):
                displays['ticker'].set_pixel(x, y, 0, 255, 128)
            displays['ticker'].show()
            time.sleep(0.02)

    # All displays: ready state
    if displays.get('main'):
        displays['main'].clear(0, 32, 64)
        displays['main'].show()

    if displays.get('ticker'):
        displays['ticker'].clear(0, 64, 32)
        displays['ticker'].show()

    if displays.get('lcd'):
        displays['lcd'].clear()
        displays['lcd'].write("Ready!", row=0, col=5)
        displays['lcd'].write("Press START", row=1, col=2)


def main():
    print("=" * 50)
    print("ARTIFACT All Displays Test")
    print("=" * 50)

    use_mock = "--mock" in sys.argv or "-m" in sys.argv
    use_scaled = "--scaled" in sys.argv or "-s" in sys.argv

    if use_mock:
        print("\nMode: MOCK (no hardware)")
    elif use_scaled:
        print("\nMode: SCALED (4x HDMI upscale)")
    else:
        print("\nMode: HARDWARE")

    print("\nInitializing displays...")
    displays = init_displays(use_mock, use_scaled)

    active = sum(1 for d in displays.values() if d is not None)
    print(f"\n{active}/3 displays active")

    if active == 0:
        print("ERROR: No displays available!")
        sys.exit(1)

    print("\nPress Ctrl+C to exit at any time.\n")

    try:
        while True:
            print("Testing startup sequence...")
            test_startup_sequence(displays)
            time.sleep(2)

            print("Testing RED...")
            test_all_red(displays)
            time.sleep(1)

            print("Testing GREEN...")
            test_all_green(displays)
            time.sleep(1)

            print("Testing BLUE...")
            test_all_blue(displays)
            time.sleep(1)

            print("Testing synchronized animation...")
            test_synchronized_animation(displays, duration=5.0)

            print("\n--- Loop complete, repeating ---\n")

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")

    finally:
        print("Cleaning up...")

        for name, display in displays.items():
            if display:
                if hasattr(display, 'clear'):
                    display.clear(0, 0, 0)
                    if hasattr(display, 'show'):
                        display.show()
                if hasattr(display, 'cleanup'):
                    display.cleanup()

        print("Done!")


if __name__ == "__main__":
    main()

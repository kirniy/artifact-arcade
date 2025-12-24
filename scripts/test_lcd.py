#!/usr/bin/env python3
"""
Test I2C LCD display (16x2).

Tests the character LCD connected via I2C on GPIO 2/3.

Usage:
    sudo PYTHONPATH=src python scripts/test_lcd.py
"""

import sys
import time

sys.path.insert(0, "src")

from artifact.hardware.display import I2CLCDDisplay, I2CLCDDisplayMock


def test_basic_text(display):
    """Test basic text display."""
    print("  Basic text...")
    display.clear()
    display.write("Hello World!", row=0, col=0)
    display.write("ARTIFACT v1.0", row=1, col=0)
    time.sleep(2)


def test_centering(display):
    """Test centered text."""
    print("  Centered text...")
    display.clear()

    # Center "ARTIFACT" on 16-char display
    text = "ARTIFACT"
    col = (16 - len(text)) // 2
    display.write(text, row=0, col=col)

    text = "Ready!"
    col = (16 - len(text)) // 2
    display.write(text, row=1, col=col)
    time.sleep(2)


def test_scrolling_text(display, text="*** Welcome to ARTIFACT! *** ", delay=0.2):
    """Test scrolling text effect."""
    print("  Scrolling text...")
    display.clear()
    display.write("Scrolling:", row=0, col=0)

    # Double the text for seamless scroll
    full_text = text * 2

    for i in range(len(text)):
        display.write(full_text[i:i+16], row=1, col=0)
        time.sleep(delay)


def test_counter(display, count=10):
    """Test counter display."""
    print("  Counter...")
    display.clear()
    display.write("Counter:", row=0, col=0)

    for i in range(count):
        display.write(f"{i:>8}", row=1, col=4)
        time.sleep(0.3)


def test_progress_bar(display, steps=16):
    """Test progress bar."""
    print("  Progress bar...")
    display.clear()
    display.write("Loading...", row=0, col=0)

    for i in range(steps + 1):
        bar = "=" * i + " " * (steps - i)
        display.write(bar, row=1, col=0)
        time.sleep(0.1)


def test_backlight(display):
    """Test backlight control."""
    print("  Backlight toggle...")
    if hasattr(display, 'set_backlight'):
        display.clear()
        display.write("Backlight OFF", row=0, col=0)
        display.set_backlight(False)
        time.sleep(1)

        display.set_backlight(True)
        display.clear()
        display.write("Backlight ON", row=0, col=0)
        time.sleep(1)
    else:
        print("    (backlight control not available)")


def test_cyrillic(display):
    """Test Cyrillic characters (may not work on all LCDs)."""
    print("  Cyrillic test...")
    display.clear()
    # Note: Most HD44780 LCDs don't support Cyrillic natively
    # This will likely show garbage characters
    display.write("Test:", row=0, col=0)
    display.write("ПРИВЕТ", row=1, col=0)  # "Hello" in Russian
    time.sleep(2)


def main():
    print("=" * 50)
    print("I2C LCD Display Test (16x2)")
    print("I2C Address: 0x27 (or 0x3F)")
    print("=" * 50)

    # Check for mock mode
    use_mock = "--mock" in sys.argv or "-m" in sys.argv
    address = 0x27

    # Check for alternate address
    if "--addr" in sys.argv:
        idx = sys.argv.index("--addr")
        if idx + 1 < len(sys.argv):
            address = int(sys.argv[idx + 1], 16)

    if use_mock:
        print("\nUsing mock display (no hardware)")
        display = I2CLCDDisplayMock(cols=16, rows=2)
    else:
        print(f"\nUsing real I2C LCD at address 0x{address:02X}")
        display = I2CLCDDisplay(cols=16, rows=2, i2c_address=address)

    print("\nInitializing display...")
    if not display.init():
        print("WARNING: Display init returned False")
        if not use_mock:
            print("Try: --addr 0x3F (alternate address)")

    print("Display ready!")
    print("\nPress Ctrl+C to exit at any time.\n")

    try:
        while True:
            test_basic_text(display)
            test_centering(display)
            test_scrolling_text(display)
            test_counter(display)
            test_progress_bar(display)

            if not use_mock:
                test_backlight(display)

            # Skip Cyrillic test by default (usually doesn't work)
            if "--cyrillic" in sys.argv:
                test_cyrillic(display)

            print("\n--- Loop complete, repeating ---\n")
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")

    finally:
        print("Cleaning up...")
        display.clear()
        if hasattr(display, 'cleanup'):
            display.cleanup()
        print("Done!")


if __name__ == "__main__":
    main()

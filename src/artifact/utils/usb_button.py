"""USB Button LED control utility.

Controls the LED on the giant red USB button (LinTx Keyboard 8088:0015).
The button registers as a keyboard with LED support, so we can control
its LED via the standard Linux LED subsystem.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# The button shows up as input7 with LED support
# LED paths: /sys/class/leds/input7::{numlock,capslock,scrolllock,compose,kana}
LED_BASE_PATH = Path("/sys/class/leds")
BUTTON_LED_PATTERNS = ["input7::numlock", "input7::scrolllock"]  # Try these first


def _find_button_led() -> Optional[Path]:
    """Find the USB button LED path dynamically.

    The input number can change on reboot, so we search for LinTx device.
    """
    if not LED_BASE_PATH.exists():
        return None

    # Try known patterns first
    for pattern in BUTTON_LED_PATTERNS:
        led_path = LED_BASE_PATH / pattern / "brightness"
        if led_path.exists():
            return led_path

    # Search for any numlock LED on high input numbers (USB devices)
    for led_dir in LED_BASE_PATH.iterdir():
        if led_dir.name.startswith("input") and "numlock" in led_dir.name:
            # Check if it's a USB device (input number > 4 usually)
            try:
                input_num = int(led_dir.name.split("::")[0].replace("input", ""))
                if input_num >= 4:  # USB devices are usually higher numbers
                    brightness_path = led_dir / "brightness"
                    if brightness_path.exists():
                        return brightness_path
            except ValueError:
                pass

    return None


def set_button_led(on: bool) -> bool:
    """Set the USB button LED state.

    Args:
        on: True to turn LED on, False to turn off

    Returns:
        True if successful, False otherwise
    """
    led_path = _find_button_led()
    if not led_path:
        logger.debug("USB button LED not found")
        return False

    try:
        with open(led_path, "w") as f:
            f.write("1" if on else "0")
        logger.debug(f"USB button LED set to {'on' if on else 'off'}")
        return True
    except PermissionError:
        logger.warning(f"Permission denied writing to {led_path}. Run as root.")
        return False
    except Exception as e:
        logger.warning(f"Failed to set USB button LED: {e}")
        return False


def get_button_led_state() -> Optional[bool]:
    """Get the current USB button LED state.

    Returns:
        True if on, False if off, None if unable to read
    """
    led_path = _find_button_led()
    if not led_path:
        return None

    try:
        with open(led_path, "r") as f:
            return f.read().strip() == "1"
    except Exception:
        return None


def turn_on_button_led() -> bool:
    """Convenience function to turn on the button LED."""
    return set_button_led(True)


def turn_off_button_led() -> bool:
    """Convenience function to turn off the button LED."""
    return set_button_led(False)


# Test if run directly
if __name__ == "__main__":
    import sys
    import time

    logging.basicConfig(level=logging.DEBUG)

    print("Testing USB button LED control...")

    led_path = _find_button_led()
    if led_path:
        print(f"Found LED at: {led_path}")

        if len(sys.argv) > 1 and sys.argv[1] == "on":
            print("Turning LED ON...")
            turn_on_button_led()
        elif len(sys.argv) > 1 and sys.argv[1] == "off":
            print("Turning LED OFF...")
            turn_off_button_led()
        else:
            print("Blinking LED 3 times...")
            for _ in range(3):
                turn_on_button_led()
                time.sleep(0.5)
                turn_off_button_led()
                time.sleep(0.5)

            print("Leaving LED ON")
            turn_on_button_led()
    else:
        print("USB button LED not found!")

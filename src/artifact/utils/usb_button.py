"""USB Button LED control utility.

Controls the LED on the giant red USB button (LinTx Keyboard 8088:0015).
Uses evdev to send LED commands directly to the device, which is more
reliable than the sysfs LED subsystem.
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# USB button vendor/product ID
BUTTON_VENDOR_ID = 0x8088
BUTTON_PRODUCT_ID = 0x0015

# Fallback: sysfs LED paths
LED_BASE_PATH = Path("/sys/class/leds")


def _find_button_device() -> Optional[str]:
    """Find the USB button's evdev device path.

    Returns:
        Path like '/dev/input/event7' or None if not found
    """
    try:
        import evdev

        for path in evdev.list_devices():
            try:
                device = evdev.InputDevice(path)
                info = device.info
                if info.vendor == BUTTON_VENDOR_ID and info.product == BUTTON_PRODUCT_ID:
                    logger.debug(f"Found USB button at {path}: {device.name}")
                    return path
            except Exception:
                continue
    except ImportError:
        logger.debug("evdev not available")
    except Exception as e:
        logger.debug(f"Error searching for button device: {e}")

    return None


def _find_button_led_sysfs() -> Optional[Path]:
    """Find the USB button LED path via sysfs (fallback)."""
    if not LED_BASE_PATH.exists():
        return None

    # Search for any numlock LED on high input numbers (USB devices)
    for led_dir in LED_BASE_PATH.iterdir():
        if led_dir.name.startswith("input") and "numlock" in led_dir.name:
            try:
                input_num = int(led_dir.name.split("::")[0].replace("input", ""))
                if input_num >= 4:  # USB devices are usually higher numbers
                    brightness_path = led_dir / "brightness"
                    if brightness_path.exists():
                        return brightness_path
            except ValueError:
                pass

    return None


def _find_hidraw_device() -> Optional[str]:
    """Find the USB button's hidraw device path.

    Returns:
        Path like '/dev/hidraw0' or None if not found
    """
    import os
    import struct

    HIDIOCGRAWINFO = 0x80084803  # ioctl to get device info

    for i in range(10):
        hidraw_path = f"/dev/hidraw{i}"
        if not os.path.exists(hidraw_path):
            continue

        try:
            import fcntl

            with open(hidraw_path, "rb") as f:
                # Get device info via ioctl
                buf = bytearray(8)
                fcntl.ioctl(f.fileno(), HIDIOCGRAWINFO, buf)
                bustype, vendor, product = struct.unpack("Ihh", buf)

                if vendor == BUTTON_VENDOR_ID and product == BUTTON_PRODUCT_ID:
                    logger.debug(f"Found USB button hidraw at {hidraw_path}")
                    return hidraw_path
        except Exception:
            continue

    return None


def set_button_led(on: bool) -> bool:
    """Set the USB button LED state.

    Tries multiple methods:
    1. hidraw - send HID output report directly
    2. evdev - use LED event interface
    3. sysfs - write to LED brightness file

    Args:
        on: True to turn LED on, False to turn off

    Returns:
        True if successful, False otherwise
    """
    # Method 1: Send HID output report via hidraw (most reliable)
    hidraw_path = _find_hidraw_device()
    if hidraw_path:
        try:
            # HID LED report: byte 0 = report ID (0), byte 1 = LED state
            # Bit 0 = NumLock, Bit 1 = CapsLock, Bit 2 = ScrollLock
            # Try all LEDs on (0x07) or all off (0x00)
            led_byte = 0x07 if on else 0x00
            with open(hidraw_path, "wb") as f:
                # Some devices want report ID 0, some don't
                # Try without report ID first (just LED byte)
                try:
                    f.write(bytes([led_byte]))
                    f.flush()
                except Exception:
                    pass
                # Try with report ID 0
                try:
                    f.write(bytes([0x00, led_byte]))
                    f.flush()
                except Exception:
                    pass
            logger.debug(f"USB button LED set via hidraw: {'on' if on else 'off'}")
            return True
        except PermissionError:
            logger.debug(f"Permission denied for {hidraw_path}")
        except Exception as e:
            logger.debug(f"hidraw LED control failed: {e}")

    # Method 2: Use evdev to set LED directly
    try:
        import evdev
        from evdev import ecodes

        device_path = _find_button_device()
        if device_path:
            device = evdev.InputDevice(device_path)
            # Try setting multiple LED types - the button might respond to any
            for led in [ecodes.LED_NUML, ecodes.LED_CAPSL, ecodes.LED_SCROLLL]:
                try:
                    device.set_led(led, 1 if on else 0)
                except Exception:
                    pass
            logger.debug(f"USB button LED set via evdev: {'on' if on else 'off'}")
            return True
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"evdev LED control failed: {e}")

    # Method 3: Try sysfs (fallback)
    led_path = _find_button_led_sysfs()
    if led_path:
        try:
            with open(led_path, "w") as f:
                f.write("1" if on else "0")
            logger.debug(f"USB button LED set via sysfs: {'on' if on else 'off'}")
            return True
        except PermissionError:
            logger.warning(f"Permission denied writing to {led_path}")
        except Exception as e:
            logger.warning(f"sysfs LED control failed: {e}")

    logger.debug("USB button LED control not available")
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

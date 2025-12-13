"""
Hardware pin mappings and configuration.

This module defines the GPIO pin assignments for all hardware components.
"""

from dataclasses import dataclass
from typing import NamedTuple


class GPIOPin(NamedTuple):
    """GPIO pin definition."""
    number: int
    name: str
    mode: str = "input"  # input, output, pwm, i2c, uart


@dataclass
class KeypadPins:
    """3x4 matrix keypad pin assignments."""
    rows: tuple[int, ...] = (5, 6, 13, 19)  # GPIO pins for rows
    cols: tuple[int, ...] = (12, 16, 20)     # GPIO pins for columns

    # Key layout
    layout: tuple[tuple[str, ...], ...] = (
        ("1", "2", "3"),
        ("4", "5", "6"),
        ("7", "8", "9"),
        ("*", "0", "#"),
    )


@dataclass
class ArcadeButtonPins:
    """Arcade button pin assignments."""
    left: int = 23   # GPIO for left button
    right: int = 24  # GPIO for right button

    # Pull-up resistor mode
    pull_up: bool = True

    # Debounce time in milliseconds
    debounce_ms: int = 50


@dataclass
class TickerPins:
    """WS2812B LED ticker pin assignments."""
    data: int = 18   # GPIO for data (PWM channel 0)

    # LED configuration
    led_count: int = 384  # 48x8 = 384 LEDs

    # Strip configuration
    led_freq_hz: int = 800000
    led_dma: int = 10
    led_brightness: int = 255
    led_invert: bool = False
    led_channel: int = 0


@dataclass
class LCDPins:
    """LCD1601 I2C pin assignments."""
    sda: int = 2   # I2C SDA
    scl: int = 3   # I2C SCL

    # I2C configuration
    i2c_address: int = 0x27
    i2c_bus: int = 1


@dataclass
class PrinterPins:
    """EM5820 thermal printer UART assignments."""
    tx: int = 14   # UART TX
    rx: int = 15   # UART RX

    # UART configuration
    port: str = "/dev/serial0"
    baudrate: int = 9600


@dataclass
class HardwareConfig:
    """Complete hardware configuration."""
    keypad: KeypadPins
    arcade: ArcadeButtonPins
    ticker: TickerPins
    lcd: LCDPins
    printer: PrinterPins


# Default hardware configuration
DEFAULT_CONFIG = HardwareConfig(
    keypad=KeypadPins(),
    arcade=ArcadeButtonPins(),
    ticker=TickerPins(),
    lcd=LCDPins(),
    printer=PrinterPins(),
)


def get_hardware_config() -> HardwareConfig:
    """Get the hardware configuration."""
    return DEFAULT_CONFIG

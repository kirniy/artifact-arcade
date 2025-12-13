# Hardware Documentation

## Overview

ARTIFACT uses a Raspberry Pi 4 (8GB) as the main controller, connected to multiple display and input devices.

## Component List

### Computing
- **Raspberry Pi 4 8GB** - Main controller

### Displays
- **P3 LED Matrix (4x 64x64)** - Main display, 128x128 pixels via 2x2 configuration
- **WS2812B LED Matrix** - Ticker display (32x8 center + 2x 8x8 sides = 48x8)
- **LCD1601 I2C** - Status display, 16 characters

### Input
- **USB Big Button 62mm** - Main interaction button (red, LED backlit)
- **3x4 Keypad** - Number input
- **Arcade Buttons 30mm (x2)** - Left/right selection

### Output
- **Pi Camera NoIR 12MP** - Photo capture for AI mode
- **EM5820 Thermal Printer** - Receipt printing
- **USB Speakers SVEN 150** - Audio output

### Power
- **Mean Well LRS-200-5** - 5V 40A power supply
- **RGB Matrix HAT** - HUB75 interface for LED matrix

## See Also

- [Component Specs](component-specs.md)
- [Wiring Diagram](wiring-diagram.md)
- [Assembly Order](assembly-order.md)
- [Troubleshooting](troubleshooting.md)

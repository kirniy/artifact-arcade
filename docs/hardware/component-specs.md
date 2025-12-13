# Component Specifications

## Displays

### P3 LED Matrix Modules (x4)
- **Resolution**: 64x64 pixels per module
- **Pixel Pitch**: 3mm
- **Interface**: HUB75E
- **Configuration**: 2x2 grid = 128x128 pixels total
- **Physical Size**: 192x192mm per module (384x384mm total)
- **Scan Rate**: 1/32

### WS2812B LED Ticker
- **Configuration**: 32x8 center + 8x8 left + 8x8 right
- **Total LEDs**: 384 (48x8)
- **Interface**: PWM (GPIO 18)
- **Voltage**: 5V
- **Protocol**: WS2812B (800kHz)

### LCD1601 I2C
- **Characters**: 16 columns, 1 row
- **Interface**: I2C (address 0x27)
- **Backlight**: Green on black
- **Controller**: HD44780 compatible

## Input Devices

### USB Big Button
- **Diameter**: 62mm
- **Type**: USB HID (emulates Enter key)
- **LED**: Red backlight
- **Response**: Tactile click

### 3x4 Matrix Keypad
- **Keys**: 0-9, *, #
- **Interface**: 7 GPIO pins (4 rows, 3 cols)
- **Layout**: Phone-style

### Arcade Buttons (x2)
- **Diameter**: 30mm
- **Color**: Red
- **Interface**: GPIO with pull-up
- **Function**: Left/Right selection

## Camera

### Raspberry Pi Camera Module 3 NoIR
- **Resolution**: 12MP
- **Sensor**: Sony IMX708
- **Features**: Autofocus, HDR
- **No IR filter**: Works in low light
- **Interface**: CSI (15-pin ribbon cable)

## Printer

### EM5820 Thermal Printer
- **Paper Width**: 58mm
- **Interface**: TTL UART (9600 baud)
- **Encoding**: CP866 for Cyrillic
- **Voltage**: 5-9V
- **Resolution**: 384 dots/line

## Audio

### SVEN 150 USB Speakers
- **Power**: 5W
- **Interface**: USB + 3.5mm jack
- **Frequency**: 100Hz-20kHz

## Power Supply

### Mean Well LRS-200-5
- **Output**: 5V DC, 40A
- **Input**: 85-264V AC
- **Power**: 200W
- **Protection**: Short circuit, overload, over voltage

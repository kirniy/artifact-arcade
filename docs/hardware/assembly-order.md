# Assembly Order

## Prerequisites

1. Raspberry Pi OS (64-bit Bookworm) installed on microSD card
2. SSH enabled for remote access
3. All components and cables ready
4. Tools: screwdriver, soldering iron (for some connections), wire strippers

## Assembly Steps

### Step 1: Prepare Raspberry Pi

1. Install RGB Matrix HAT onto GPIO header
2. Connect power supply to HAT (not Pi directly)
3. Boot Pi and configure:
   ```bash
   sudo raspi-config
   # Enable: I2C, SPI
   # Disable: Serial console (keep hardware serial)
   # Set hostname, timezone, WiFi
   ```
4. Add to `/boot/config.txt`:
   ```
   dtparam=audio=off
   dtparam=i2c_arm=on
   dtparam=spi=on
   enable_uart=1
   dtoverlay=disable-bt
   ```
5. Reboot

### Step 2: Connect P3 LED Matrix

1. Chain 4 panels in 2x2 configuration:
   - HAT Port 1 → Panel 1 (top-left)
   - Panel 1 OUT → Panel 2 IN (top-right)
   - HAT Port 2 → Panel 3 (bottom-left)
   - Panel 3 OUT → Panel 4 IN (bottom-right)
2. Connect power cables to all panels from 5V supply
3. Test with sample pattern

### Step 3: Connect WS2812B Ticker

1. Connect data wire to GPIO 18
2. Connect 5V power from external supply (not Pi)
3. Connect ground (shared with Pi ground)
4. Test LEDs light up

### Step 4: Connect LCD Display

1. Connect I2C wires:
   - SDA → GPIO 2
   - SCL → GPIO 3
   - VCC → 3V3
   - GND → GND
2. Test I2C detection:
   ```bash
   i2cdetect -y 1
   # Should show device at 0x27
   ```

### Step 5: Connect Input Devices

1. **Keypad Matrix**:
   - Wire rows to GPIO 5, 6, 13, 19
   - Wire columns to GPIO 12, 16, 20
   - Test each key responds

2. **Arcade Buttons**:
   - Left button: GPIO 23 + GND
   - Right button: GPIO 24 + GND
   - Enable internal pull-up resistors in software

3. **USB Big Button**:
   - Plug into USB port
   - Test it sends Enter key

### Step 6: Connect Camera

1. Attach 15-pin ribbon cable to CSI port
2. Secure camera module
3. Test capture:
   ```bash
   libcamera-hello
   ```

### Step 7: Connect Thermal Printer

1. Connect UART:
   - TX (GPIO 14) → Printer RX
   - RX (GPIO 15) → Printer TX (optional)
   - GND → Printer GND
2. Connect 9V power supply to printer
3. Test printing:
   ```bash
   echo "Test" | lp -d thermal
   ```

### Step 8: Connect Audio

1. Plug USB speakers into USB port
2. Configure audio output:
   ```bash
   # May need to set USB audio as default
   aplay -l  # List devices
   ```

### Step 9: Power Management

1. Connect Mean Well LRS-200-5:
   - 5V output to RGB Matrix HAT
   - 5V output to WS2812B ticker
2. Connect 9V supply to thermal printer
3. Test full system power draw

### Step 10: Final Integration Testing

1. Run test script:
   ```bash
   python scripts/test_hardware.py
   ```
2. Verify all components respond
3. Check power stability under load
4. Test thermal management

## Troubleshooting

See [troubleshooting.md](troubleshooting.md) for common issues.

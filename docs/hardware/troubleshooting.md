# Troubleshooting Guide

## Display Issues

### P3 LED Matrix Not Working

**Symptom**: No display or garbled output

**Solutions**:
1. Check HAT is properly seated on GPIO header
2. Verify power connections to all panels
3. Check chain configuration:
   ```bash
   sudo ./demo -D0 --led-rows=64 --led-cols=64 --led-chain=2 --led-parallel=2
   ```
4. Ensure no other processes using GPIO

### WS2812B Ticker Flickers

**Symptom**: LEDs flicker or show wrong colors

**Solutions**:
1. Determine whether flicker happens only in a photobooth state such as photo-ready. Check that all states use `render_idle_style_ticker_text()` once on a black-cleared buffer.
2. If short static `QR` is crystal clear, do not change the driver, GPIO, mapping, or wiring. The failure is in a different renderer.
3. Remove scrolling copy, vertical slide/fade transitions, flips, and post-render ticker particles. Render short static words through `render_idle_style_ticker_text()` on black using the theme accent color. Timed alternation must use hard cuts between complete frames.
4. If white remains clean but colored text is wrong, run static `R`, `G`, `B` labels. On July 11 the cabinet showed green `R`, red `G`, and blue `B`, proving physical GRB order. Keep `PixelStrip(..., strip_type=WS2811_STRIP_GRB)` explicit; white masks a red/green swap.
5. Match diagnostic and production brightness. Red noise improved at `64` versus the old `128` but did not disappear during full labels. Brightness `32` plus Summer Camp ticker color `(0,255,48)` eliminated the noise onsite. Test with full `SUMMER`, not only two-letter `QR`.
6. Run `PYTHONPATH=src python -m pytest -q tests/test_photobooth_ticker_states.py tests/test_ws2812b_mapping.py`.
7. Verify audio is disabled: `dtparam=audio=off` in `/boot/config.txt`.
8. Check the shared ground connection and power supply only if the brightness-64 full-width diagnostic also fails.

The July 11, 2026 Summer Camp failure affected animated ticker states while `QR` remained crystal clear. Driver timing experiments did not solve it and were reverted. All photobooth themes now use compact static labels in `theme_chrome`; processing hard-cuts between `ЖДИ` and `НЕ УХОДИ`. Cross-display ticker particles are disabled globally.

### LCD Shows Garbage

**Symptom**: Random characters or no display

**Solutions**:
1. Check I2C address: `i2cdetect -y 1`
2. Verify contrast potentiometer setting on back of LCD
3. Check wiring: SDA to GPIO 2, SCL to GPIO 3
4. Ensure I2C is enabled in raspi-config

## Input Issues

### USB Button Not Responding

**Symptom**: Button press not detected

**Solutions**:
1. Check USB connection: `lsusb`
2. Test as keyboard: `cat /dev/input/event*`
3. Verify evdev permissions
4. Check if mapped correctly (should send Enter key)

### Keypad Keys Not Working

**Symptom**: Some or all keys not responding

**Solutions**:
1. Check GPIO pin assignments match wiring
2. Verify no other process using those GPIO pins
3. Test individual pins: `gpio read <pin>`
4. Check for short circuits in matrix

### Arcade Buttons Stuck

**Symptom**: Button always reads as pressed

**Solutions**:
1. Check pull-up resistor enabled in software
2. Verify button is normally-open type
3. Test continuity with multimeter
4. Check for bent pins or shorts

## Camera Issues

### Camera Not Detected

**Symptom**: `libcamera-hello` fails

**Solutions**:
1. Check ribbon cable connection (metal contacts face HDMI port)
2. Verify camera interface enabled: `vcgencmd get_camera`
3. Check cable for damage
4. Try reseating connection

### Poor Image Quality in Low Light

**Symptom**: Dark or noisy images

**Solutions**:
1. Ensure using NoIR (no IR filter) camera model
2. Add IR illumination
3. Increase exposure time in software
4. Use flash effect from LEDs

## Printer Issues

### Printer Not Printing

**Symptom**: No output from printer

**Solutions**:
1. Check power supply (needs 9V, not 5V)
2. Verify UART enabled and console disabled
3. Test connection:
   ```bash
   stty -F /dev/serial0 9600
   echo "Test" > /dev/serial0
   ```
4. Check paper loaded correctly

### Cyrillic Characters Not Printing

**Symptom**: Russian text shows as garbage

**Solutions**:
1. Ensure printer supports CP866 codepage
2. Send codepage command before text
3. Use python-escpos library with correct encoding

## Audio Issues

### No Sound Output

**Symptom**: Speakers silent

**Solutions**:
1. Check USB speakers connected
2. Set correct audio device:
   ```bash
   aplay -l  # List devices
   pactl set-default-sink <usb_sink_name>
   ```
3. Test with:
   ```bash
   aplay /usr/share/sounds/alsa/Front_Center.wav
   ```
4. Check volume level

## Power Issues

### System Unstable Under Load

**Symptom**: Pi reboots or LEDs dim when all displays active

**Solutions**:
1. Verify power supply capacity (need 5V 40A for full brightness)
2. Check for voltage drop on cables (use thick gauge)
3. Add capacitors near LED strips
4. Reduce LED brightness in software

### Overheating

**Symptom**: Pi throttles or shuts down

**Solutions**:
1. Add heatsinks to Pi
2. Ensure ventilation in enclosure
3. Add fan if needed
4. Monitor temperature: `vcgencmd measure_temp`

## Software Issues

### GPIO Permission Denied

**Solutions**:
1. Add user to gpio group: `sudo usermod -aG gpio $USER`
2. Use `sudo` for initial testing
3. Check udev rules for GPIO access

### I2C Device Not Found

**Solutions**:
1. Enable I2C: `sudo raspi-config`
2. Check `/boot/config.txt` for `dtparam=i2c_arm=on`
3. Install tools: `sudo apt install i2c-tools`
4. Scan bus: `i2cdetect -y 1`

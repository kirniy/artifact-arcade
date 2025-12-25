# Wiring Diagram

## GPIO Pin Assignments

```
Raspberry Pi 4 GPIO Header
===========================

                    3V3 [01] [02] 5V
          I2C SDA - GPIO2 [03] [04] 5V
          I2C SCL - GPIO3 [05] [06] GND
                    GPIO4 [07] [08] GPIO14 - UART TX (Printer)
                      GND [09] [10] GPIO15 - UART RX (Printer)
                   GPIO17 [11] [12] GPIO18 - (Audio PWM)
                   GPIO27 [13] [14] GND
                   GPIO22 [15] [16] GPIO23 - Arcade Left
                      3V3 [17] [18] GPIO24 - Arcade Right
                   GPIO10 [19] [20] GND
                    GPIO9 [21] [22] GPIO25
                   GPIO11 [23] [24] GPIO8
                      GND [25] [26] GPIO7
                    GPIO0 [27] [28] GPIO1
          Keypad R1 - GPIO5 [29] [30] GND
          Keypad R2 - GPIO6 [31] [32] GPIO12 - Keypad C1
          Keypad R3 - GPIO13 [33] [34] GND
          Keypad R4 - GPIO19 [35] [36] GPIO16 - Keypad C2
                   GPIO26 [37] [38] GPIO20 - Keypad C3
                      GND [39] [40] GPIO21 - WS2812B Data
```

## Connection Details

### P3 LED Matrix (via NovaStar T50 + DH418)

**NOT using GPIO** - uses HDMI output to professional LED controller.

```
Signal Path:
  Pi HDMI → T50 HDMI In → T50 Ethernet Out → DH418 Ethernet In → HUB75E to Panels

DH418 HUB Outputs → Panel Inputs (8 cables total, NO daisy-chain!):
  HUB1 → Panel 1 (bottom-left) Input A (top half)
  HUB2 → Panel 1 (bottom-left) Input B (bottom half)
  HUB3 → Panel 2 (top-left) Input A
  HUB4 → Panel 2 (top-left) Input B
  HUB5 → Panel 3 (top-right) Input A
  HUB6 → Panel 3 (top-right) Input B
  HUB7 → Panel 4 (bottom-right) Input A
  HUB8 → Panel 4 (bottom-right) Input B

Panel Layout (from front):
  ┌─────────┬─────────┐
  │ Panel 2 │ Panel 3 │
  ├─────────┼─────────┤
  │ Panel 1 │ Panel 4 │
  └─────────┴─────────┘
```

See `novastar-setup.md` for complete configuration guide.

### WS2812B Ticker (GPIO 21)
```
Raspberry Pi          WS2812B Strip
-----------          --------------
GPIO 21 (PWM) -----> DIN (Data In)
5V (external) -----> VCC
GND          -----> GND

Note: Using GPIO 21 (not 18) to avoid conflict with 3.5mm audio.
Power WS2812B from external 5V supply, not Pi.
Connect grounds together.
```

### LCD1601 I2C
```
Raspberry Pi          LCD1601
-----------          --------
GPIO 2 (SDA) -----> SDA
GPIO 3 (SCL) -----> SCL
3V3          -----> VCC
GND          -----> GND
```

### 3x4 Keypad Matrix
```
Keypad Pin    GPIO    Function
----------    ----    --------
Row 1         GPIO 5  First row
Row 2         GPIO 6  Second row
Row 3         GPIO 13 Third row
Row 4         GPIO 19 Fourth row
Col 1         GPIO 12 First column
Col 2         GPIO 16 Second column
Col 3         GPIO 20 Third column
```

### Arcade Buttons
```
Button        GPIO    Notes
------        ----    -----
Left          GPIO 23 With pull-up
Right         GPIO 24 With pull-up
Ground        GND     Common ground
```

### EM5820 Thermal Printer
```
Raspberry Pi          Printer
-----------          --------
GPIO 14 (TX) -----> RX
GPIO 15 (RX) -----> TX
GND          -----> GND
(9V external) ----> VCC
```

### USB Devices
```
USB Port 1: USB Big Button
USB Port 2: USB Speakers
USB Port 3: (Available)
USB Port 4: (Available)
```

### Camera
```
CSI Port: Pi Camera NoIR (15-pin ribbon cable)
```

## Power Distribution

```
Mean Well LRS-200-5 (5V 40A)
├── Raspberry Pi (via USB-C, 5V 3A)
├── P3 LED Panels (via HAT, 5V ~20A max)
├── WS2812B Ticker (5V ~8A max)
└── Thermal Printer (needs 9V separate supply)
```

## Important Notes

1. **WS2812B PWM Conflict**: Disable onboard audio in `/boot/config.txt`:
   ```
   dtparam=audio=off
   ```

2. **UART for Printer**: Disable serial console:
   ```
   sudo raspi-config → Interface Options → Serial → No (console), Yes (hardware)
   ```

3. **I2C Enable**:
   ```
   sudo raspi-config → Interface Options → I2C → Enable
   ```

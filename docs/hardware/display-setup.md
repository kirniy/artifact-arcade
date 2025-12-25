# LED Display Setup - Complete Reference

This document contains all information about the LED display output system for ARTIFACT arcade machine. Use this reference when troubleshooting display issues or configuring a new setup.

---

## System Overview

```
┌─────────────────┐    HDMI      ┌─────────────┐   Ethernet   ┌─────────────┐   HUB75E    ┌────────────────┐
│  Raspberry Pi 4 │ ──────────▶  │  NovaStar   │ ───────────▶ │  NovaStar   │ ──────────▶│ 4× P3 64×64    │
│  720×480 HDMI   │              │  T50        │              │  DH418      │            │ LED Panels     │
│  pygame/SDL2    │              │  (sender)   │              │ (receiver)  │   8 cables │ 128×128 total  │
└─────────────────┘              └─────────────┘              └─────────────┘            └────────────────┘
```

---

## Hardware Components

### 1. LED Panels

| Parameter | Value |
|-----------|-------|
| Model | P3-2121-64x64-32S-v3 |
| Quantity | 4 panels |
| Per-Panel Resolution | 64×64 pixels |
| Total Resolution | 128×128 pixels (2×2 grid) |
| Pixel Pitch | 3mm (P3) |
| Scan Rate | 1/32 (32S) |
| Driver Chip | CHIPONE ICN2153 (ICND2153AP) |
| Row Decoder | ICN2013 |
| Interface | HUB75E |
| HUB Connectors | 2 per panel (BOTH ARE INPUTS, no daisy-chain!) |
| Power | 5V DC from Mean Well LRS-200-5 (40A) |

### 2. NovaStar T50 (Taurus Multimedia Player)

| Parameter | Value |
|-----------|-------|
| Role | HDMI-to-Ethernet sender |
| Model ID | 38428 |
| Max Pixel Load | 650,000 pixels/port |
| Input | HDMI (accepts 720×480, 1080p, etc.) |
| Output | Ethernet to DH418 receiver |
| WiFi AP | SSID: `AP00006151`, Password: `12345678` |
| Network IP | 192.168.0.10 (on WiFi AP) |
| Firmware | Internal (configurable via NovaLCT) |

### 3. NovaStar DH418 (Receiving Card)

| Parameter | Value |
|-----------|-------|
| Role | Ethernet-to-HUB75E receiver |
| Firmware | DH418_V4.5.1.0 |
| Max Pixel Load | 256×256 pixels |
| HUB Outputs | 8× HUB75E connectors |
| Configuration | Stored in flash, set via NovaLCT through T50 |

### 4. Raspberry Pi 4

| Parameter | Value |
|-----------|-------|
| Model | Raspberry Pi 4 Model B Rev 1.5 |
| RAM | 8GB |
| OS | Debian 13 (Trixie) 64-bit |
| Kernel | 6.12.47+rpt-rpi-v8 |
| Hostname | artifact |
| User/Pass | kirniy / qaz123 |
| Graphics Driver | vc4-kms-v3d (KMS) |
| Desktop | labwc (Wayland compositor) |

---

## Current Configuration (Dec 2024)

### HDMI Output: 720×480 @ 60Hz

The Pi outputs 720×480 HDMI. T50 crops the top-left 128×128 pixels for the LED panels.

#### /boot/firmware/config.txt
```ini
# KMS driver for graphics
dtoverlay=vc4-kms-v3d
max_framebuffers=2

# Disable firmware video= setting (we control it in cmdline.txt)
disable_fw_kms_setup=1

# Force HDMI output
hdmi_force_hotplug=1

# HDMI mode: CEA mode 3 = 720×480 @ 60Hz
hdmi_group=1
hdmi_mode=3

# Framebuffer dimensions
framebuffer_width=720
framebuffer_height=480

# Legacy settings (commented out):
# hdmi_cvt=128 128 60  # Custom mode - DOESN'T WORK with T50!
# hdmi_mode=87         # Custom mode trigger
```

#### /boot/firmware/cmdline.txt
```
... video=HDMI-A-1:720x480@60 quiet splash ...
```
The `video=` parameter is critical for KMS driver to use correct resolution.

### Framebuffer Status
```bash
$ fbset
mode "720x480"
    geometry 720 480 720 480 16
    timings 0 0 0 0 0 0 0
    rgba 5/11,6/5,5/0,0/0
endmode
```

### DRM Devices
```
/dev/dri/card0  - vc4 (main HDMI output) - status: connected
/dev/dri/card1  - v3d (GPU compute) - status: disconnected
/dev/dri/renderD128 - render node
```

---

## NovaStar Configuration

### Working Config File
**File**: `FINAL_4hub_128x128.rcfgx` (424KB)

This file configures:
- 128×128 total resolution
- 8 data groups (2 per panel)
- ICN2153 driver chip settings
- Panel arrangement in 2×2 grid

### Panel Wiring (4 Direct Cables)

Each panel connects directly to DH418 with its own cable (NO daisy-chain):

```
DH418 HUB Outputs → Panels (4 direct connections):
  HUB1 → Panel 1 (bottom-left)
  HUB2 → Panel 2 (top-left)
  HUB3 → Panel 3 (top-right)
  HUB4 → Panel 4 (bottom-right)
```

### Panel Physical Layout (from front)
```
┌─────────┬─────────┐
│ Panel 2 │ Panel 3 │
│  HUB2   │  HUB3   │
├─────────┼─────────┤
│ Panel 1 │ Panel 4 │
│  HUB1   │  HUB4   │
└─────────┴─────────┘
```

### T50 HDMI Cropping

T50 takes 720×480 HDMI input and displays a 128×128 window on the LED panels.

**Default**: Top-left corner (X=0, Y=0) - shows pixels 0-127 on both axes.

**To show center of HDMI** (optional):
- In T50 settings → Video Source → Output Position:
  - X = 296  (calculated: (720-128)/2)
  - Y = 176  (calculated: (480-128)/2)

**Test which area is shown**: Draw squares in all 4 corners of 720×480. Only the visible corner appears on LED.

---

## Software Stack

### Display Libraries (on Pi)

| Library | Version | Purpose |
|---------|---------|---------|
| pygame | 2.6.1 | Game rendering |
| SDL | 2.32.4 | Graphics backend |
| Python | 3.13.5 | Runtime |

### SDL Video Driver Status

| Driver | Status | Notes |
|--------|--------|-------|
| **offscreen** | WORKS | Default fallback, renders to nowhere |
| kmsdrm | FAILS | Blocked by labwc compositor holding DRM |
| wayland | FAILS | SDL2 not compiled with wayland support |
| x11 | FAILS | No X server running |
| fbdev | FAILS | Legacy framebuffer not available |
| directfb | FAILS | Not available |

### Desktop Environment

The Pi runs **labwc** (Wayland compositor) by default:
```
/usr/bin/labwc -C /etc/xdg/labwc-greeter/
```

This compositor holds exclusive access to `/dev/dri/card0`, preventing pygame from using kmsdrm directly.

---

## KNOWN ISSUE: Pygame Can't Render to Display

### SOLUTION: kmsdrm + sudo (WORKING!)

**Tested and confirmed working on Dec 25, 2024.**

The key requirements:
1. **Stop lightdm/labwc** - compositor must not hold DRM device
2. **Use kmsdrm driver** - SDL_VIDEODRIVER=kmsdrm
3. **Run with sudo** - kmsdrm needs root access to /dev/dri/card1
4. **card1 is HDMI** - NOT card0 (card0 is v3d GPU only)

### Working Command
```bash
# 1. Stop desktop compositor
sudo systemctl stop lightdm

# 2. Run pygame with kmsdrm
sudo SDL_VIDEODRIVER=kmsdrm SDL_AUDIODRIVER=dummy python3 your_app.py
```

### Working Test Script
```python
#!/usr/bin/env python3
import os
os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'
os.environ['SDL_AUDIODRIVER'] = 'dummy'

import pygame
import time

pygame.init()
print(f"Driver: {pygame.display.get_driver()}")  # Should print "KMSDRM"

screen = pygame.display.set_mode((720, 480))

# Colors test
for color, name in [((255,0,0),'RED'), ((0,255,0),'GREEN'), ((0,0,255),'BLUE')]:
    screen.fill(color)
    pygame.display.flip()
    print(name)
    time.sleep(1.5)

pygame.quit()
```

### Alternative: Direct Framebuffer (also works)
```python
import mmap, struct, time

fb = open('/dev/fb0', 'r+b')
mm = mmap.mmap(fb.fileno(), 720*480*2, mmap.MAP_SHARED, mmap.PROT_WRITE|mmap.PROT_READ)

def fill(r, g, b):
    color = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)  # RGB565
    mm.seek(0)
    mm.write(struct.pack('<H', color) * (720*480))
    mm.flush()

fill(255, 0, 0)  # Red
time.sleep(2)
fill(0, 255, 0)  # Green
```

### DRM Device Mapping (Raspberry Pi 4)
| Device | Driver | Purpose |
|--------|--------|---------|
| /dev/dri/card0 | v3d | 3D GPU only, NO display |
| /dev/dri/card1 | vc4-drm | **HDMI output** |

---

## pygame Code Requirements

### Basic Setup
```python
import os
import pygame

# MUST set before pygame.init()
os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'

pygame.init()

# Use full HDMI resolution, T50 will crop
screen = pygame.display.set_mode((720, 480), pygame.FULLSCREEN)

# Draw in top-left 128×128 - this is what appears on LED panels
game_surface = pygame.Surface((128, 128))
# ... render game content to game_surface ...

# Blit to screen's top-left corner
screen.fill((0, 0, 0))  # Black background
screen.blit(game_surface, (0, 0))
pygame.display.flip()
```

### Test Script
```python
# /tmp/test_display.py
import pygame
import time
import os

os.environ['SDL_VIDEODRIVER'] = 'kmsdrm'

pygame.init()
screen = pygame.display.set_mode((720, 480), pygame.FULLSCREEN)

# RGB test
for color, name in [((255,0,0), 'RED'), ((0,255,0), 'GREEN'), ((0,0,255), 'BLUE')]:
    print(f"Showing {name}...")
    screen.fill(color)
    pygame.display.flip()
    time.sleep(2)

# White square test (128×128 in top-left)
screen.fill((0, 0, 0))
pygame.draw.rect(screen, (255, 255, 255), (0, 0, 128, 128))
pygame.display.flip()
time.sleep(3)

pygame.quit()
```

---

## systemd Service Configuration

### /etc/systemd/system/artifact.service
```ini
[Unit]
Description=ARTIFACT Arcade Machine
After=network.target
# Don't start until labwc is stopped
Conflicts=labwc.service lightdm.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/home/kirniy/modular-arcade
Environment=PYTHONPATH=/home/kirniy/modular-arcade/src
Environment=SDL_VIDEODRIVER=kmsdrm
Environment=ARTIFACT_ENV=hardware
ExecStart=/home/kirniy/modular-arcade/.venv/bin/python -m artifact.main
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### To enable headless operation (no desktop):
```bash
# Disable desktop
sudo systemctl disable lightdm
sudo systemctl stop lightdm

# Enable artifact service
sudo systemctl enable artifact
sudo systemctl start artifact
```

---

## Troubleshooting

### Display shows boot splash then goes black
- Normal behavior when desktop starts
- labwc takes over DRM, terminal/splash disappears
- Solution: Stop labwc or disable lightdm

### pygame.error: kmsdrm not available
- Cause: Another process holds DRM device
- Check: `fuser -v /dev/dri/card0`
- Solution: Kill the process or stop labwc.service

### T50 shows "DVI Signal Exception"
- Cause: Pi not outputting HDMI or wrong resolution
- Check: `fbset` should show 720×480
- Solution: Verify config.txt and cmdline.txt settings

### Only offscreen driver works
- This is the current state
- labwc blocks kmsdrm access
- Stop labwc to use kmsdrm

### LED panels show content, pygame shows black
- Pi HDMI works (boot splash visible)
- pygame can't render
- Use kmsdrm with sudo after stopping labwc

---

## Configuration Files Summary

| File | Location | Purpose |
|------|----------|---------|
| config.txt | /boot/firmware/ on Pi | HDMI resolution settings |
| cmdline.txt | /boot/firmware/ on Pi | Kernel video= parameter |
| FINAL_4hub_128x128.rcfgx | ~/modular-arcade/ | NovaStar panel config |
| artifact.service | /etc/systemd/system/ | Autostart service |

---

## Quick Commands Reference

```bash
# SSH to Pi
ssh kirniy@artifact.local  # password: qaz123

# Check HDMI resolution
fbset

# Check what's using DRM
fuser -v /dev/dri/card0

# Stop desktop
sudo systemctl stop labwc.service
sudo killall -9 labwc wf-panel-pi

# Run pygame test
export SDL_VIDEODRIVER=kmsdrm
sudo python3 /tmp/test_display.py

# Restart desktop
sudo systemctl start labwc.service

# Service management
sudo systemctl status artifact
sudo systemctl restart artifact
journalctl -u artifact -f
```

---

## Version History

- **Dec 25, 2024**: Documented kmsdrm vs labwc conflict, 720×480 working setup
- **Dec 24, 2024**: Discovered panel wiring (no daisy-chain), created FINAL_4hub_128x128.rcfgx

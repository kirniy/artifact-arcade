# ARTIFACT - AI-Powered Arcade Fortune Machine

## Project Overview

ARTIFACT is an AI-powered arcade fortune-telling machine built on Raspberry Pi 4 with a multi-display system, camera, thermal printer, and Gemini AI integration.

---

## Raspberry Pi Setup

### Hardware Specs
- **Model**: Raspberry Pi 4 Model B Rev 1.5 (8GB RAM)
- **OS**: Debian 13 (Trixie) 64-bit
- **Hostname**: `artifact`
- **User**: `kirniy` / Password: `qaz123`

### Network Access

| Method | Address | Notes |
|--------|---------|-------|
| SSH | `ssh kirniy@artifact.local` | Or use IP address |
| VNC | `vnc://artifact.local:5900` | Remote desktop |
| Dashboard | `http://artifact.local:8080` | Logs, images, status |

### Finding the Pi on Any Network

```bash
# Method 1: mDNS (if on same network)
ping artifact.local

# Method 2: Network scan (from Mac)
arp -a | grep -i "raspberry\|artifact"

# Method 3: Router admin page
# Look for device named "artifact"

# Method 4: Use Raspberry Pi Connect (works from anywhere)
# https://connect.raspberrypi.com
```

### Configured WiFi Networks
| Network | Location | Priority |
|---------|----------|----------|
| Renaissance | Home | Default |
| office_64 | Club | Auto-connect |

### Pre-configured Services

| Service | Status | Description |
|---------|--------|-------------|
| `artifact.service` | Enabled | Main arcade application (autostart) |
| `artifact-dashboard.service` | Enabled | Web dashboard on port 8080 |
| `artifact-update.timer` | Enabled | Auto-pulls from GitHub every 2 min |
| `sing-box.service` | Enabled | VPN (Frankfurt server) |
| `wayvnc` | Enabled | Remote desktop |

### Quick Commands (on Pi)

```bash
# Check all services
systemctl status artifact artifact-dashboard artifact-update.timer sing-box

# View live logs
journalctl -u artifact -f

# Manual update from GitHub
~/modular-arcade/scripts/auto-update.sh

# Restart application
sudo systemctl restart artifact

# Run in hardware mode
cd ~/modular-arcade
sudo ARTIFACT_ENV=hardware PYTHONPATH=src .venv/bin/python -m artifact.main
```

### LED Demo (32 Visual Effects with Chiptune Music)

A standalone demo showcasing the 128×128 LED panel with 32 visual effects, videos, images, and Balatro-style chiptune music.

**Run the Demo:**
```bash
# SSH into Pi
ssh kirniy@artifact.local

# Load audio driver for 3.5mm jack
sudo modprobe snd-bcm2835

# Kill any running python processes (optional)
sudo pkill -9 python

# Kill desktop compositor (grabs display)
sudo killall -9 labwc wf-panel-pi 2>/dev/null

# Run demo - let pygame auto-detect kmsdrm (do NOT set SDL_VIDEODRIVER explicitly!)
sudo SDL_AUDIODRIVER=alsa AUDIODEV=hw:2,0 python3 ~/modular-arcade/scripts/led_demo.py
```

**Controls:**
| Key | Action |
|-----|--------|
| ENTER / SPACE / → | Next effect |
| ← | Previous effect |
| ESC | Exit demo |
| Big Red USB Button | Sends ENTER (switches effects) |

**Effects Include:**

*Iconic/Recognizable:*
- 🧽 SpongeBob Christmas (pixel art underwater scene)
- 🍄 Mario Runner (NES-style infinite runner)
- 🏛️ St. Petersburg (St. Isaac's Cathedral with snowfall)
- 👻 Pac-Man Chase (classic arcade)
- 🌈 Nyan Cat (rainbow trail in space)
- 🧱 Tetris (falling blocks)

*Video & Branding:*
- 🎬 Winter Saga (video with audio)
- 🎄 Polar Express (animated image)
- 🎮 VNVNC 3D Rotating logo
- 🌊 VNVNC Wave animation

*Visual Effects:*
- 🌀 Plasma Vortex, 📡 Neon Grid, ⚡ Electric Storm
- ⚛️ Quantum Field, 🔮 Hypercube 4D, 🧬 DNA Helix
- 🌳 Four Seasons Tree (cherry blossoms, fireflies, falling leaves, snow)
- 🕳️ Black Hole, 🌌 Aurora Borealis, 🎆 Fireworks
- 🫧 Lava Lamp, 🧬 Game of Life, 📡 Radar Sweep
- 🌀 Spiral Galaxy, 🔮 Kaleidoscope
- ❄️ Snowfall, 🔥 Fireplace, 💜 Plasma, 💚 Matrix, ✨ Starfield, 🕳️ Tunnel

**Audio:**
- Each effect has unique Balatro-style chiptune music
- Arcade "blip" sound on effect switch
- Video plays with its native audio track
- All audio goes through 3.5mm jack (hw:2,0)

**Big Red Button:**
The USB button (LinTx Keyboard, VendorID 0x8088) sends ENTER keycode when pressed.

```bash
# Verify button is detected
cat /proc/bus/input/devices | grep -A5 LinTx
```

### Hardware Connections

#### Fan Connection (GPIO)
```
Pin 4 (5V)  → Red wire
Pin 6 (GND) → Black wire
```

#### Display Interfaces
| Interface | Device | GPIO/Connection |
|-----------|--------|-----------------|
| HDMI | Main RGB Matrix (via T50) | HDMI port → NovaStar T50 |
| GPIO 21 | WS2812B Ticker LEDs | PWM (384 LEDs) |
| I2C | LCD 16x2 | /dev/i2c-1 (GPIO 2,3) |
| UART | Thermal Printer | /dev/ttyAMA0 (GPIO 14,15) |

#### Camera
| Component | Specification |
|-----------|---------------|
| **Model** | Raspberry Pi Camera Module 3 NoIR |
| **Sensor** | Sony IMX708 (no IR filter) |
| **Resolution** | 4608×2592 (12MP) |
| **Interface** | CSI (Camera Serial Interface) |
| **Library** | picamera2, rpicam-apps |

```bash
# List cameras
rpicam-hello --list-cameras

# Take a photo
rpicam-still -o photo.jpg

# Stream to network (view with: ffplay tcp://artifact.local:8888)
rpicam-vid -t 0 --width 640 --height 480 --inline --listen -o tcp://0.0.0.0:8888
```

#### Audio Output
| Component | Specification |
|-----------|---------------|
| **Output** | 3.5mm headphone jack |
| **Driver** | snd_bcm2835 |
| **Card** | card 2: Headphones |

**Note**: Audio uses PWM on GPIO 18, which conflicts with WS2812B. Solution: WS2812B moved to GPIO 21.

```bash
# Test audio
speaker-test -D hw:2,0 -t sine -f 440 -l 1

# Audio module auto-loads via /etc/modules-load.d/audio.conf
# Default output set in /etc/asound.conf
```

### Installed Libraries
- RPi.GPIO, gpiozero - GPIO control
- rpi_ws281x, neopixel - LED strips (ticker)
- RPLCD - LCD display
- python-escpos - Thermal printer
- picamera2 - Camera
- pygame - Display rendering (outputs to HDMI)

---

## RGB LED Matrix Hardware (Main Display)

### Hardware Overview

The main 128×128 display uses NovaStar professional LED control equipment, providing reliable HDMI-to-HUB75E conversion with native support for ICN2153 driver chips.

### Panel Configuration

| Component | Specification |
|-----------|---------------|
| **Panel Model** | P3-2121-64x64-32S-v3 |
| **Panels** | 4× P3 64×64 LED panels (HUB75E interface) |
| **Total Resolution** | 128×128 pixels (2×2 grid) |
| **Pixel Pitch** | 3mm (P3) |
| **Scan Rate** | 1/32 (32S) |
| **Driver Chip** | CHIPONE ICN2153 (ICND2153AP) |
| **Panel Power** | Mean Well LRS-200-5 (5V 40A) |

### Control System

| Component | Specification |
|-----------|---------------|
| **Sender** | **NovaStar T50** Multimedia Player |
| **Receiver** | **NovaStar DH418** Receiving Card |
| **Connection** | Pi HDMI → T50 HDMI In → Ethernet → DH418 → HUB75E |
| **Max Capacity** | T50: 650,000 pixels/port, DH418: 256×256 pixels |

### Signal Flow

```
┌─────────────┐    HDMI     ┌─────────────┐   Ethernet   ┌─────────────┐   HUB75E   ┌────────────┐
│ Raspberry   │ ─────────▶  │  NovaStar   │ ───────────▶ │  NovaStar   │ ─────────▶ │ 4× P3 64×64│
│ Pi 4        │             │  T50        │              │  DH418      │            │ Panels     │
│ (pygame)    │             │  (sender)   │              │  (receiver) │            │ (128×128)  │
└─────────────┘             └─────────────┘              └─────────────┘            └────────────┘
```

### Physical Wiring (4 Cables)

Each panel connects to DH418 with ONE HUB75E cable:

```
Panel Layout (as seen from FRONT):

  ┌───────────────┬───────────────┐
  │   Panel 2     │   Panel 3     │
  │  (top-left)   │  (top-right)  │
  │   ← HUB2      │   ← HUB3      │
  ├───────────────┼───────────────┤
  │   Panel 1     │   Panel 4     │
  │ (bottom-left) │(bottom-right) │
  │   ← HUB1      │   ← HUB4      │
  └───────────────┴───────────────┘

DH418 HUB1-4 → 4 panels (1 cable per panel)
```

**Configuration Files**: `configs/novastar/` contains backup configs.
See `docs/hardware/novastar-setup.md` for complete setup guide.

### Power Connections

```
Mean Well LRS-200-5:
  V+ (+5V) → All panel VCC (red wires)
  V- (GND) → All panel GND + DH418 GND (common ground!)

IMPORTANT:
- V- is GROUND (0V), not negative voltage
- Use thick gauge wires (at least 18 AWG) for power
```

### T50 Configuration

The T50 + DH418 require configuration via NovaLCT software (Windows only):

1. Connect to T50 via WiFi (`AP00006151` / `12345678`) or Ethernet
2. Launch NovaLCT V5.8.1
3. Use **Smart Settings Guide** to configure module:
   - Chip: ICND2153
   - Decoder: ICN2013
   - Data Type: Parallel drive
   - Module Type: Irregular Module
   - Size: 64×64
4. Use **Construct Irregular-Cabinet** to set up 128×128 layout:
   - 8 data groups (2 per panel, 4 panels)
   - Irregular cabinet type
5. Send configuration to DH418

**Note**: After initial configuration, the T50 operates standalone. NovaLCT is not needed for daily use.

See `docs/hardware/novastar-setup.md` for detailed configuration guide.

### Accessing NovaLCT

Options for Mac users:
- **Local QEMU VM** (recommended) - see `docs/hardware/novastar-setup.md`
  ```bash
  cd ~/win11-qemu && ./run.sh
  ```
- Parallels/VMware with Windows
- Borrow a Windows laptop

### Software Integration

**HDMI Configuration**: Pi outputs 720×480 @ 60Hz HDMI. T50 crops the top-left 128×128 pixels for display.

**IMPORTANT**: Raspberry Pi OS runs labwc (Wayland compositor) by default, which blocks pygame from accessing DRM. To run pygame on the LED display:

```bash
# 1. Stop artifact.service if running (it grabs DRM)
sudo systemctl stop artifact

# 2. Stop desktop compositor
sudo killall -9 labwc wf-panel-pi 2>/dev/null

# 3. Run pygame - let it auto-detect kmsdrm (do NOT set SDL_VIDEODRIVER!)
sudo python3 your_app.py
```

**⚠️ CRITICAL**: On Debian Trixie, do NOT set `SDL_VIDEODRIVER=kmsdrm` explicitly!
Let pygame auto-detect the driver. Explicit setting breaks initialization.

The display code uses pygame:

```python
import pygame

pygame.init()

# Initialize display FIRST - required for kmsdrm
screen = pygame.display.set_mode((720, 480), pygame.FULLSCREEN)
pygame.mouse.set_visible(False)  # Must be AFTER set_mode()

print(f"Video driver: {pygame.display.get_driver()}")  # Should show "KMSDRM"

# Draw in top-left 128×128 corner - this is what appears on LED panels
game_surface = pygame.Surface((128, 128))
game_surface.fill((255, 0, 0))  # Red
screen.blit(game_surface, (0, 0))
pygame.display.flip()
```

**Complete display documentation**: See `docs/hardware/display-setup.md` for full troubleshooting guide, SDL driver issues, and systemd configuration.

### Why NovaStar Instead of GPIO HAT?

The P3-2121-64x64-32S panels use **ICN2153 smart driver chips** with internal PWM/memory. These chips require a proprietary protocol (config latches + OE PWM clocking) that is NOT compatible with standard HUB75 libraries like `rpi-rgb-led-matrix`.

NovaStar receiving cards (DH418) have native firmware support for ICN2153 panels, making them plug-and-play.

---

## WS2812B Ticker LED Strip

### Configuration

| Component | Specification |
|-----------|---------------|
| **LED Type** | WS2812B (Neopixel-compatible) |
| **Layout** | 1× 32×8 matrix + 2× 8×8 matrices = 48×8 total |
| **Total LEDs** | 384 (256 + 64 + 64) |
| **GPIO Pin** | GPIO 21 (PWM) |
| **Data Protocol** | Single-wire 800kHz serial |

**Note**: Using GPIO 21 instead of GPIO 18 to avoid conflict with 3.5mm audio (which uses GPIO 18 for PWM).

### Wiring

```
Raspberry Pi GPIO 21 ──────▶ DIN (first matrix)
                             ↓
                      32×8 Matrix (256 LEDs)
                             ↓ DOUT → DIN
                      8×8 Matrix L (64 LEDs)
                             ↓ DOUT → DIN
                      8×8 Matrix R (64 LEDs)
                             ↓ DOUT
                           (end)

Power:
  5V PSU → VCC on all matrices
  GND → GND on all matrices + Pi GND (common ground!)
```

### Software

Using `rpi_ws281x` / `adafruit-circuitpython-neopixel`:

```python
import board
import neopixel

# 384 LEDs on GPIO 21 (not GPIO 18 - that conflicts with audio)
pixels = neopixel.NeoPixel(board.D21, 384, brightness=0.5, auto_write=False)

# Set pixel colors
pixels[0] = (255, 0, 0)  # Red
pixels.show()
```

### Important Notes

1. **GPIO 21 for WS2812B**: Using GPIO 21 instead of GPIO 18 to allow 3.5mm audio (which uses GPIO 18 for PWM). Both GPIO 18 and 21 support PWM for WS2812B.

2. **Level Shifting**: WS2812B expects 5V logic but Pi outputs 3.3V. Most WS2812B LEDs work reliably with 3.3V signals, but for long runs or reliability, add a 74AHCT125 level shifter.

3. **Power**: 384 LEDs at full white = ~23A (60mA/LED). Use a beefy 5V supply and inject power at multiple points for even brightness.

---

## Quick Start (Simulator on Mac)

```bash
# Run simulator
cd ~/dev/modular-arcade
PYTHONPATH=src:$PYTHONPATH .venv/bin/python -m artifact.simulator.main
```

## Simulator Controls

| Key | Action |
|-----|--------|
| SPACE / ENTER | Start / Confirm |
| LEFT / RIGHT | Navigate / Answer |
| B / BACKSPACE | Go back |
| R | Reboot to idle |
| 0-9 | Keypad input |
| * / # | Keypad special |
| F1 | Toggle debug panel |
| ESC | Exit |

## Current Status

### Working Features
- Core state machine and event system
- Pygame simulator with all virtual displays
- 5 game modes: Fortune, Zodiac, Roulette, Quiz, AI Prophet
- Russian UI with Cyrillic bitmap fonts
- Animated mystical eye in crystal ball
- Navigation (back/reboot)

### Known Issues & TODOs

#### HIGH PRIORITY - Text Display Issues
- [ ] **Fix ALL text overlapping/cropping/cutoff across all modes and screens**
  - Every text element must be fully visible
  - No text should be cut off at display edges
  - Adjust scale, position, or word wrapping as needed
  - Test all modes in all phases (intro, active, processing, result)
  - Test all three displays: main (128x128), ticker (48x8), LCD (16 chars)

#### Camera Features
- [ ] **Live camera preview on main display**
  - Show real-time camera feed as dithered silhouette on 128x128 display
  - Use 1-bit or limited color palette for retro look
  - Should work during photo capture countdown in AI Prophet mode

#### Printer Features
- [ ] **Print preview visualization in simulator**
  - When printing, show a visual preview of what would be printed
  - Display thermal receipt layout with:
    - Caricature image (dithered)
    - Prediction text
    - Date/time
    - ARTIFACT logo
  - Animate the "printing" process

#### Caricature Generation
- [ ] Caricature must be of the ACTUAL PERSON from their photo
  - NOT a generic "fortune teller" character
  - Black and white sketch style
  - Thick outlines, pure white background
  - Capture likeness and distinctive features

## Architecture

```
src/artifact/
├── core/           # State machine, events
├── modes/          # Game modes (fortune, zodiac, quiz, etc.)
├── animation/      # Particle system, idle animations
├── graphics/       # Fonts, primitives, renderer
├── simulator/      # Pygame desktop simulator
├── hardware/       # Hardware abstraction (for Pi)
├── ai/             # Gemini integration
├── printing/       # Thermal printer
└── utils/          # Shared utilities (S3 upload, camera service)
```

## Key Files

- `src/artifact/simulator/main.py` - Simulator entry point
- `src/artifact/modes/manager.py` - Mode lifecycle and UI
- `src/artifact/animation/idle.py` - Idle screen animations
- `src/artifact/graphics/fonts.py` - Cyrillic bitmap fonts
- `src/artifact/ai/caricature.py` - Gemini image generation
- `src/artifact/utils/s3_upload.py` - Selectel S3 upload + QR code generation

## QR Code Sharing

All modes that generate images or audio use Selectel S3 Object Storage for sharing via QR codes.

### Storage Configuration
| Setting | Value |
|---------|-------|
| Endpoint | `https://s3.ru-7.storage.selcloud.ru` |
| Bucket | `vnvnc` |
| Prefix | `artifact/{type}/` |
| Public URL | `https://e6aaa51f-863a-439e-9b6e-69991ff0ad6e.selstorage.ru` |
| AWS Profile | `selectel` (configured in ~/.aws/credentials) |

### Modes with QR Sharing
- **photobooth**: Photo uploads → QR on display
- **ai_prophet**: Caricature uploads → QR on display + receipt
- **roast**: Roast caricature → QR on display + receipt
- **fortune**: Fortune caricature → QR on display + receipt
- **zodiac**: Constellation portrait → QR on display + receipt
- **rapgod**: Audio track → QR on display + receipt

### Usage Pattern
```python
from artifact.utils.s3_upload import AsyncUploader, UploadResult

# In mode __init__:
self._uploader = AsyncUploader()
self._qr_url: Optional[str] = None
self._qr_image: Optional[np.ndarray] = None

# After generating content:
self._uploader.upload_bytes(
    image_data,
    prefix="fortune",  # or "photo", "roast", "zodiac", "track"
    extension="png",
    content_type="image/png",
    callback=self._on_upload_complete
)

# Callback handles result:
def _on_upload_complete(self, result: UploadResult) -> None:
    if result.success:
        self._qr_url = result.url
        self._qr_image = result.qr_image  # 60x60 RGB numpy array
```

## Display Specifications

| Display | Size | Notes |
|---------|------|-------|
| Main | 128x128 px | Primary content, animations |
| Ticker | 48x8 px | Scrolling text, status |
| LCD | 16 chars | Mode name, short prompts |

## Text Rendering Guidelines

- Main display: Use `scale=1` for text longer than 10 chars, `scale=2` for short text
- Always calculate centering: `x = (128 - text_width * scale) // 2`
- Word wrap long text to ~12 chars per line at scale=2
- Test Cyrillic characters - they may be wider than Latin

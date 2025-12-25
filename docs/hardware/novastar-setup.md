# NovaStar T50 + DH418 Setup Guide

Complete setup guide for the NovaStar LED control system with P3 64x64 panels.

---

## Table of Contents

1. [Hardware Overview](#hardware-overview)
2. [Panel Specifications](#panel-specifications)
3. [Critical Discovery: No Daisy-Chaining](#critical-discovery-no-daisy-chaining)
4. [Wiring Diagram](#wiring-diagram)
5. [NovaLCT Configuration](#novalct-configuration)
6. [Raspberry Pi HDMI Setup](#raspberry-pi-hdmi-setup)
7. [Windows VM Setup for NovaLCT](#windows-vm-setup-for-novalct)
8. [Troubleshooting](#troubleshooting)
9. [Session Log: Dec 24-25, 2024](#session-log-dec-24-25-2024)

---

## Hardware Overview

### Components

| Component | Model | Role |
|-----------|-------|------|
| **Sender** | NovaStar T50 (Taurus) | Receives HDMI, sends to receiver via Ethernet |
| **Receiver** | NovaStar DH418 | Receives data, drives panels via HUB75E |
| **Panels** | P3-2121-64x64-32S-v3 (x4) | 64x64 LED modules, 2x2 grid = 128x128 total |
| **Power** | Mean Well LRS-200-5 | 5V 40A for panels |

### Signal Flow

```
┌─────────────┐    HDMI     ┌─────────────┐   Ethernet   ┌─────────────┐   HUB75E    ┌────────────┐
│ Raspberry   │ ─────────►  │  NovaStar   │ ───────────► │  NovaStar   │ ──────────► │ 4× P3 64×64│
│ Pi 4        │             │  T50        │              │  DH418      │  (8 cables) │ Panels     │
│ (pygame)    │             │  (sender)   │              │  (receiver) │             │ (128×128)  │
└─────────────┘             └─────────────┘              └─────────────┘             └────────────┘
```

### T50 Taurus Multimedia Player

| Specification | Value |
|---------------|-------|
| Model ID | 38428 |
| Max Load | 650,000 pixels per port |
| Outputs | 1× Ethernet to receiver |
| Inputs | HDMI, USB |
| WiFi AP | `AP00006151` / Password: `12345678` |
| Network IP | Usually `192.168.0.10` (can vary) |

### DH418 Receiving Card

| Specification | Value |
|---------------|-------|
| Firmware | DH418_V4.5.1.0 |
| Max Load | 256×256 pixels |
| HUB Outputs | 8× HUB75E connectors |
| Control | Via T50 over Ethernet |

---

## Panel Specifications

### P3-2121-64x64-32S-v3

| Parameter | Value |
|-----------|-------|
| Resolution | 64×64 pixels |
| Pixel Pitch | 3mm (P3) |
| Physical Size | 192×192mm |
| Driver Chip | **ICND2153** (CHIPONE ICN2153) |
| Row Decoder | **ICN2013** |
| Scan Rate | 1/32 (32S) |
| Data Groups | **2 per panel** |
| HUB Connectors | **2 per panel (both are INPUTS)** |
| Interface | HUB75E |

### Why These Panels Need NovaStar

The ICND2153 driver chips are "smart" chips with internal PWM and memory. They require a proprietary initialization protocol that standard HUB75 libraries (like `rpi-rgb-led-matrix`) cannot provide.

NovaStar receiving cards have native firmware support for ICND2153, making configuration straightforward once properly set up.

---

## Critical Discovery: No Daisy-Chaining

### The Problem

These panels have **2 HUB connectors each**, but **BOTH ARE INPUTS** - there is no output for daisy-chaining.

```
Each P3 64×64 Panel (viewed from back):
┌─────────────────────────────┐
│                             │
│   [HUB-A]       [HUB-B]     │  ← BOTH ARE INPUTS!
│   (Input)       (Input)     │
│                             │
│      TOP HALF    BOT HALF   │
│      (32 rows)   (32 rows)  │
│                             │
└─────────────────────────────┘

HUB-A → Drives top 32 rows (data groups 0-1 of that panel)
HUB-B → Drives bottom 32 rows (data groups 2-3 of that panel)
```

### What This Means

- **NO daisy-chaining** is possible
- Each panel needs **2 separate HUB cables** from DH418
- 4 panels × 2 inputs = **8 HUB connections total**
- DH418 has exactly 8 HUB outputs - perfect match

### Previous Incorrect Wiring (Did NOT Work)

```
WRONG - Daisy-chain attempt:
DH418 HUB1 → Panel1 → Panel2 → Panel3 → Panel4

Result: Only Panel 4 showed content (cyan color), others dark
```

---

## Wiring Diagram

### Correct Wiring: 8 Separate Cables

Each DH418 HUB output connects directly to one panel input:

```
DH418 Receiving Card (8 HUB outputs):
┌──────────────────────────────────────────┐
│                                          │
│  [HUB1] [HUB2] [HUB3] [HUB4]            │
│  [HUB5] [HUB6] [HUB7] [HUB8]            │
│                                          │
└──────────────────────────────────────────┘
     │      │      │      │
     │      │      │      └─────► Panel 2 - BOTTOM half
     │      │      └────────────► Panel 2 - TOP half
     │      └───────────────────► Panel 1 - BOTTOM half
     └──────────────────────────► Panel 1 - TOP half

     (Same pattern for HUB5-8 → Panels 3-4)
```

### Panel Physical Layout (viewed from FRONT)

```
Screen Layout (128×128 total):
┌───────────────┬───────────────┐
│               │               │
│   Panel 2     │   Panel 3     │   Row 0-63
│  (top-left)   │  (top-right)  │
│               │               │
├───────────────┼───────────────┤
│               │               │
│   Panel 1     │   Panel 4     │   Row 64-127
│ (bottom-left) │(bottom-right) │
│               │               │
└───────────────┴───────────────┘
   Col 0-63       Col 64-127
```

### Recommended HUB Mapping

Based on NovaLCT Construct Cabinet configuration (8 data groups):

| DH418 Output | Panel | Half | Data Groups | Screen Position |
|--------------|-------|------|-------------|-----------------|
| HUB1 | Panel 1 | TOP | 1 | Bottom-left, rows 64-95 |
| HUB2 | Panel 1 | BOTTOM | 2 | Bottom-left, rows 96-127 |
| HUB3 | Panel 2 | TOP | 3 | Top-left, rows 0-31 |
| HUB4 | Panel 2 | BOTTOM | 4 | Top-left, rows 32-63 |
| HUB5 | Panel 3 | TOP | 5 | Top-right, rows 0-31 |
| HUB6 | Panel 3 | BOTTOM | 6 | Top-right, rows 32-63 |
| HUB7 | Panel 4 | TOP | 7 | Bottom-right, rows 64-95 |
| HUB8 | Panel 4 | BOTTOM | 8 | Bottom-right, rows 96-127 |

**Note**: The exact mapping may need adjustment based on how NovaLCT assigned data groups. If panels display wrong content, swap cables between HUB outputs.

### Power Wiring

```
Mean Well LRS-200-5:
┌─────────────────────────────────┐
│  L  N  ⏚   -V   -V   +V   +V   │
│  AC IN     GND       +5V       │
└─────────────────────────────────┘
              │         │
              │         └──► All panel VCC (red wires)
              └────────────► All panel GND + DH418 GND

CRITICAL:
- V- is GROUND (0V), not negative voltage
- Use thick wires (18 AWG minimum) for power
- Common ground between panels and DH418
```

---

## NovaLCT Configuration

### Module Settings (Smart Settings Guide)

| Parameter | Value |
|-----------|-------|
| Driver Chip | ICND2153 |
| Driver Version | 1.0.0 |
| Data Type | **Parallel drive** |
| Module Type | **Irregular Module** |
| Row Decoder | ICN2013 |
| Pixels | 64 × 64 |
| Data Groups per module | 2 |

### Cabinet Configuration

| Parameter | Value |
|-----------|-------|
| Cabinet Type | **Irregular** |
| Width | 128 |
| Height | 128 |
| Data Groups of Cabinet | **8** |

### Construct Cabinet Layout

In NovaLCT's "Construct Irregular-Cabinet" dialog:
- Set 8 data groups
- Arrange modules in 2×4 grid (representing 4 panels × 2 halves each)
- Each module represents one half of a panel (64×32 effective area mapped to 64×64 group)

### Performance Settings

| Parameter | Value |
|-----------|-------|
| Refresh Rate | 3840 |
| DCLK Frequency | 12.5 |
| Data Phase | 2 |
| GCLK Frequency | 20.8 MHz |
| GCLK Phase | 5 |
| GCLK Duty Cycle | 50% |
| Line Change | 3 |
| Row Blanking | 27 (1.30us) |
| Ghost Control | 24 |
| Brightness | ~76% |

---

## Raspberry Pi HDMI Setup

### Required Configuration

The Pi must output exactly 128×128 resolution over HDMI.

#### /boot/firmware/config.txt

Add these lines:

```ini
# Force HDMI output even without monitor detection
hdmi_force_hotplug=1

# Custom resolution mode
hdmi_group=2
hdmi_cvt=128 128 60
hdmi_mode=87

# Framebuffer size
framebuffer_width=128
framebuffer_height=128
```

#### /boot/firmware/cmdline.txt

Add to the end of the single line (space-separated):

```
video=HDMI-A-1:128x128@60
```

### Verification

After reboot, verify with:

```bash
# Check current resolution
xrandr

# Should show:
# HDMI-1 connected 128x128+0+0
#    128x128       60.00*+
```

### VPN Note

If Pi has VPN enabled (sing-box), you may need to disable it for local network access:

```bash
# Stop VPN temporarily
sudo systemctl stop sing-box

# Re-enable when done
sudo systemctl start sing-box
```

---

## Windows VM Setup for NovaLCT

NovaLCT only runs on Windows. Options for Mac users:

### Option 1: Azure Windows VM (Recommended)

1. Create Windows 11 VM on Azure
2. Install Tailscale on both Mac and VM for networking
3. Connect to VM via Microsoft Remote Desktop
4. Install NovaLCT V5.8.1 from NovaStar website

**Tailscale Setup**:
```
Mac IP: (your Tailscale IP)
VM IP: (VM's Tailscale IP)

Both must be on same Tailscale network for USB/IP forwarding
```

### Option 2: Local VM

- Parallels Desktop or VMware Fusion
- Windows 10/11 VM
- USB passthrough for direct T50 connection

### Option 3: Borrow Windows Laptop

- Temporary solution for one-time configuration

### Connecting NovaLCT to T50

1. **WiFi Method**:
   - Connect to T50's WiFi AP: `AP00006151` / `12345678`
   - T50 IP is usually `192.168.0.10`

2. **Ethernet Method**:
   - Direct Ethernet from PC to T50
   - Configure PC to same subnet (e.g., `192.168.0.100`)

3. **USB Method** (if available):
   - Direct USB connection
   - May require USB/IP forwarding for VMs

---

## Troubleshooting

### Problem: Only one panel shows content

**Cause**: Daisy-chain wiring with panels that don't support it.

**Solution**: Use 8 separate HUB cables, one per panel input.

### Problem: T50 shows "DVI Signal Exception"

**Cause**: Pi not outputting video or wrong resolution.

**Solution**:
1. Check Pi HDMI config (see above)
2. Verify `xrandr` shows 128×128
3. Restart Pi after config changes

### Problem: NovaLCT can't find T50

**Solutions**:
1. Check T50 WiFi connection (AP00006151)
2. Try Ethernet instead of WiFi
3. Ensure PC/VM is on same subnet
4. Disable VPN if using Tailscale between networks

### Problem: Panels show wrong colors/positions

**Cause**: HUB cable mapping doesn't match NovaLCT data group configuration.

**Solution**:
1. Note which panel shows what
2. Swap HUB cables to correct positions
3. Or reconfigure data groups in NovaLCT

### Problem: Panels flicker or show artifacts

**Causes & Solutions**:
- Power insufficient → Check 5V supply, use thicker wires
- Bad HUB cable → Try different cable
- Timing issues → Adjust DCLK/GCLK in NovaLCT

---

## Session Log: Dec 24-25, 2024

### Timeline

**~22:00** - Started troubleshooting display not working
- Only Panel 4 (bottom-right) showing cyan color
- Other 3 panels dark

**~23:00** - Discovered Pi outputting 1920×1080 instead of 128×128
- Modified `/boot/firmware/config.txt`
- Added `hdmi_cvt=128 128 60`, `hdmi_mode=87`
- Added `video=HDMI-A-1:128x128@60` to cmdline.txt
- After reboot: Pi correctly outputs 128×128

**~00:00** - Display still not working after Pi fix
- Tried multiple .rcfgx config files
- All showed same result: only Panel 4 lit

**~02:00** - Attempted protocol-based configuration
- Found sarakusha/novastar library on GitHub
- Created configure-2x2.mjs and configure-dh418.mjs scripts
- T50 Taurus returns "UnknownCommand" for most protocol addresses
- Protocol approach abandoned

**~05:00** - Used NovaLCT Construct Cabinet wizard
- Configured 8 data groups
- Set ICND2153 chip, ICN2013 decoder
- Sent configuration to DH418

**~07:00** - Key realization
- Each panel has 2 HUB connectors
- Both are INPUTS, not input+output
- **No daisy-chaining possible**
- Need 8 separate cables from DH418

**~08:00** - Session ended, wiring to be completed next day

### Key Learnings

1. **Panel architecture**: Each 64×64 panel uses 2 HUB inputs for top/bottom halves
2. **No daisy-chain**: These panels cannot be daisy-chained
3. **8 cables required**: DH418's 8 outputs match the 8 panel inputs perfectly
4. **T50 protocol**: T50 Taurus uses different protocol than older NovaStar devices
5. **NovaLCT required**: GUI configuration through NovaLCT is the supported method

### Files Created During Session

| File | Purpose |
|------|---------|
| `/tmp/novastar/configure-2x2.mjs` | Protocol config attempt (failed) |
| `/tmp/novastar/configure-dh418.mjs` | Direct RC config attempt (failed) |
| `/tmp/novastar/packages/` | Cloned sarakusha/novastar library |

### Configuration Files

The working NovaLCT configuration was sent directly to DH418. Export using:
- NovaLCT → Export Screen Module → saves .rcfgx file
- NovaLCT → Save System Configuration → saves to hardware

---

## Quick Reference

### Connections Checklist

- [ ] Pi HDMI → T50 HDMI In
- [ ] T50 Ethernet Out → DH418 Ethernet In
- [ ] DH418 HUB1 → Panel 1 Input A
- [ ] DH418 HUB2 → Panel 1 Input B
- [ ] DH418 HUB3 → Panel 2 Input A
- [ ] DH418 HUB4 → Panel 2 Input B
- [ ] DH418 HUB5 → Panel 3 Input A
- [ ] DH418 HUB6 → Panel 3 Input B
- [ ] DH418 HUB7 → Panel 4 Input A
- [ ] DH418 HUB8 → Panel 4 Input B
- [ ] 5V power to all panels
- [ ] Common ground (panels + DH418)

### T50 WiFi Quick Connect

```
SSID: AP00006151
Password: 12345678
T50 IP: 192.168.0.10
```

### Pi SSH Access

```bash
ssh kirniy@artifact.local
# Password: qaz123
```

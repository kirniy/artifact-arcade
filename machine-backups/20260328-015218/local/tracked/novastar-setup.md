# NovaStar T50 + DH418 Setup Guide

Complete setup guide for the NovaStar LED control system with P3 64x64 panels.

**Last Updated**: December 26, 2024

---

## Table of Contents

1. [Hardware Overview](#hardware-overview)
2. [Physical Wiring](#physical-wiring)
3. [NovaLCT Software Setup](#novalct-software-setup)
4. [Configuration Procedure](#configuration-procedure)
5. [Backup and Restore](#backup-and-restore)
6. [Windows VM Setup (QEMU on Mac)](#windows-vm-setup-qemu-on-mac)
7. [Troubleshooting](#troubleshooting)
8. [Configuration Files](#configuration-files)

---

## Hardware Overview

### Components

| Component | Model | Role |
|-----------|-------|------|
| **Sender** | NovaStar T50 (Taurus) | Receives HDMI, sends to receiver via Ethernet |
| **Receiver** | NovaStar DH418 | Receives data, drives panels via HUB75E |
| **Panels** | P3-2121-64x64-32S-v3 (x4) | 64x64 LED modules, 2x2 grid = 128x128 total |
| **Power** | Mean Well LRS-200-5 | 5V 40A for panels |

### Panel Specifications

| Parameter | Value |
|-----------|-------|
| Resolution | 64×64 pixels |
| Pixel Pitch | 3mm (P3) |
| Driver Chip | **ICND2153** (CHIPONE) |
| Row Decoder | **ICN2013** |
| Scan Rate | **1/32** (32S) |
| Data Groups | 2 per panel (software concept) |
| HUB Connector | 1 per panel |

### Signal Flow

```
┌─────────────┐    HDMI     ┌─────────────┐   Ethernet   ┌─────────────┐   HUB75E   ┌────────────┐
│ Raspberry   │ ─────────►  │  NovaStar   │ ───────────► │  NovaStar   │ ─────────► │ 4× P3 64×64│
│ Pi 4        │             │  T50        │              │  DH418      │            │ Panels     │
│ (pygame)    │             │  (sender)   │              │  (receiver) │            │ (128×128)  │
└─────────────┘             └─────────────┘              └─────────────┘            └────────────┘
```

---

## Physical Wiring

### Panel Connections: 4 Cables Total

Each panel connects to the DH418 with **ONE HUB75E cable**. The 8 data groups in the software configuration are a logical concept - physically there are only 4 cables.

```
Panel Layout (viewed from FRONT):

  ┌───────────────┬───────────────┐
  │   Panel 2     │   Panel 3     │
  │  (top-left)   │  (top-right)  │
  │   ← HUB2      │   ← HUB3      │
  ├───────────────┼───────────────┤
  │   Panel 1     │   Panel 4     │
  │ (bottom-left) │(bottom-right) │
  │   ← HUB1      │   ← HUB4      │
  └───────────────┴───────────────┘
```

### DH418 to Panel Mapping

| DH418 Port | Panel | Screen Position |
|------------|-------|-----------------|
| HUB1 | Panel 1 | Bottom-left (rows 64-127, cols 0-63) |
| HUB2 | Panel 2 | Top-left (rows 0-63, cols 0-63) |
| HUB3 | Panel 3 | Top-right (rows 0-63, cols 64-127) |
| HUB4 | Panel 4 | Bottom-right (rows 64-127, cols 64-127) |

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
- Use thick wires (18 AWG minimum)
- Common ground between panels and DH418
```

---

## NovaLCT Software Setup

### Requirements

- **NovaLCT Version**: V5.8.1 (MUST match config file version)
- **Platform**: Windows only (use VM on Mac - see below)
- **Connection**: WiFi or Ethernet to T50

### T50 Connection

| Method | Details |
|--------|---------|
| **WiFi** | SSID: `AP00006151` / Password: `12345678` |
| **T50 IP** | `192.168.0.10` (default) |
| **Port** | 5200 |

### Opening NovaLCT Screen Configuration

1. Launch NovaLCT
2. Menu: **User** → **Advanced User Login** (password: `admin`)
3. Menu: **Screen Configuration** → **Screen Configuration**
4. Enter T50 IP: `192.168.0.10`
5. Click **Connect**

---

## Configuration Procedure

### Loading Saved Configuration

If you have backup config files (`.rcfgx` and `.oscfg`):

1. **Receiving Card tab**:
   - Click **"Load from..."** → select `working_receiver.rcfgx`
   - Verify Module Information shows:
     - Chip: **ICND2153**
     - Size: **64W×64H**
     - Scanning Type: **1/32 scan**
     - Data Groups: **2**

2. **Screen Connection tab**:
   - Click **"Open Mapping"** ← **THIS IS CRITICAL!**
   - This loads and activates the screen mapping configuration

3. **Send to Hardware**:
   - Click **"Send"** (sends to DH418 RAM)
   - Click **"Save"** (writes to DH418 flash - persists after power cycle)

### Creating New Configuration (Smart Settings)

If no backup exists:

1. **Receiving Card tab** → Click **"Smart Set..."**
2. Select chip type: **ICND2153**
3. Set module size: **64×64**
4. Set scan: **1/32**
5. Set data groups: **2**
6. Click **"Construct Ca..."** to set up cabinet:
   - Data Groups of Cabinet: **8**
   - Cabinet Type: **Irregular**
   - Width: **128**, Height: **128**
7. Map the 8 data groups to their positions
8. Click **OK** → **Send** → **Save**

### The Critical "Open Mapping" Step

**If panels show garbled content or one panel is black after loading config:**

Go to **Screen Connection** tab → Click **"Open Mapping"**

This step activates the screen topology mapping. Without it, the receiver config is loaded but the sender doesn't know how to map video to the panels.

---

## Backup and Restore

### Export Configuration Files

From Screen Configuration window:

| Button | File Type | Purpose |
|--------|-----------|---------|
| **Receiving Card** → **Export** | `.rcfgx` | Module/chip settings |
| **Export Screen M...** | `.oscfg` | Screen mapping topology |
| **Bottom** → **Save** | N/A | Saves to hardware flash |

### Required Files for Full Restore

Keep these files backed up:

```
configs/novastar/
├── working_receiver.rcfgx    # Receiving card configuration
├── screenmapping.oscfg       # Screen mapping (CRITICAL!)
└── screen.scr                # Screen connection
```

### Restore Procedure

1. **Load** `working_receiver.rcfgx` in Receiving Card tab
2. Go to **Screen Connection** tab
3. Click **"Open Mapping"** or load `.oscfg` file
4. Click **Send**
5. Click **Save**
6. **Verify** all 4 panels display correctly

---

## Windows VM Setup (QEMU on Mac)

NovaLCT requires Windows. On Apple Silicon Macs, use QEMU with Windows 11 ARM64.

### Prerequisites

```bash
# Install QEMU
brew install qemu

# Create VM directory
mkdir -p ~/win11-qemu
cd ~/win11-qemu
```

### Download Required Files

1. **Windows 11 ARM64 ISO**: Download from Microsoft (Insider or retail)
2. **UEFI Firmware**: Get `QEMU_EFI.fd` for aarch64

### Setup Script

Create `~/win11-qemu/setup.sh`:

```bash
#!/bin/bash
cd ~/win11-qemu

# Create UEFI firmware copies
cp /opt/homebrew/share/qemu/edk2-aarch64-code.fd efi.img
truncate -s 64M efi.img
truncate -s 64M vars.img

# Create virtual disk (64GB)
qemu-img create -f qcow2 disk.qcow2 64G

# Create transfer disk for file sharing (500MB FAT32)
dd if=/dev/zero of=transfer.img bs=1M count=500
mkfs.fat -F 32 transfer.img
```

### Run VM Script

Create `~/win11-qemu/run.sh`:

```bash
#!/bin/bash
cd ~/win11-qemu
qemu-system-aarch64 \
  -m 4G \
  -smp 4 \
  -cpu host \
  -M virt \
  -accel hvf \
  -drive if=pflash,format=raw,file=efi.img,readonly=on \
  -drive if=pflash,format=raw,file=vars.img \
  -device ramfb \
  -device qemu-xhci \
  -device usb-kbd \
  -device usb-tablet \
  -nic user,model=virtio-net-pci \
  -device virtio-blk-pci,drive=system \
  -drive if=none,id=system,format=qcow2,file=disk.qcow2 \
  -device usb-storage,drive=transfer \
  -drive if=none,id=transfer,format=raw,file=transfer.img
```

### First-Time Installation

```bash
# Add ISO for installation
qemu-system-aarch64 \
  ... (same as run.sh) \
  -cdrom /path/to/Windows11_ARM64.iso
```

### Transferring Files to VM

```bash
# Mount transfer disk on Mac
hdiutil attach ~/win11-qemu/transfer.img

# Copy files
cp ~/dev/modular-arcade/configs/novastar/* /Volumes/TRANSFER/

# Unmount
hdiutil detach /Volumes/TRANSFER
```

In Windows VM, the transfer disk appears as `D:` drive.

### Network Configuration

The VM uses NAT networking. To reach T50 at `192.168.0.10`:

1. Connect Mac to T50's WiFi (`AP00006151`)
2. In QEMU, use `-nic user` (default) - it shares Mac's network
3. VM can reach T50 via Mac's WiFi connection

### Installing NovaLCT in VM

1. Download NovaLCT V5.8.1 from NovaStar website
2. Copy installer to transfer disk
3. In VM, run installer from D: drive
4. Launch NovaLCT

**Note**: VM resolution is limited to 800×600 with ramfb driver. It's cramped but usable.

---

## Troubleshooting

### Problem: Panels show garbled content after loading config

**Solution**: Go to **Screen Connection** tab → Click **"Open Mapping"**

This is the most common issue. The screen mapping must be explicitly activated.

### Problem: One panel is completely black

**Causes & Solutions**:
1. **Screen mapping not loaded**: Click "Open Mapping" in Screen Connection tab
2. **Wrong config file**: Ensure you're using the correct `.rcfgx` that matches your panel layout
3. **HUB cable issue**: Try swapping cables between working and non-working panel

### Problem: NovaLCT shows wrong chip type (LS9930, 1/60 scan)

**Cause**: Wrong config file loaded or readback from corrupted hardware state

**Solution**:
1. Click **"Load from..."** and load the correct `.rcfgx` file
2. Verify Module Information shows: ICND2153, 64×64, 1/32 scan, 2 data groups
3. Send and Save

### Problem: Config doesn't persist after power cycle

**Solution**: After clicking **Send**, you MUST also click **Save** to write to flash memory.

- **Send** = writes to RAM (temporary)
- **Save** = writes to FLASH (persistent)

### Problem: NovaLCT can't connect to T50

**Solutions**:
1. Connect to T50 WiFi: `AP00006151` / `12345678`
2. Verify T50 IP is `192.168.0.10`
3. If using VM, ensure Mac is connected to T50's WiFi (VM uses Mac's network)
4. Try disabling any VPN on Mac

### Problem: Config file won't load ("Failed to load configuration file!")

**Cause**: NovaLCT version mismatch

**Solution**: Config files are version-specific. Use NovaLCT V5.8.1 for the provided config files.

---

## Configuration Files

### Location

```
~/dev/modular-arcade/configs/novastar/
```

### Files

| File | Size | Purpose |
|------|------|---------|
| `working_receiver.rcfgx` | 426 KB | Receiving card config (ICND2153, 64×64, 1/32, 2 groups) |
| `screenmapping.oscfg` | 711 KB | Screen mapping topology (8 data groups, 128×128) |
| `screen.scr` | 587 B | Screen connection settings |
| `FINAL_4hub_128x128.rcfgx` | 424 KB | Original/backup receiver config |

### Module Settings in Config

| Parameter | Value |
|-----------|-------|
| Chip | ICND2153 |
| Decoder | ICN2013 (ICN2012WEA in file) |
| Module Size | 64×64 |
| Scan Type | 1/32 (Scan_32) |
| Data Groups per Module | 2 |
| Total Data Groups | 8 |
| Cabinet | Irregular, 128×128 |

---

## Quick Reference

### Restore Steps (TL;DR)

```
1. Launch NovaLCT V5.8.1
2. Screen Configuration → connect to 192.168.0.10
3. Receiving Card tab → Load from... → working_receiver.rcfgx
4. Screen Connection tab → Open Mapping    ← DON'T FORGET THIS!
5. Click Send
6. Click Save
7. Done - all 4 panels should work
```

### T50 WiFi Quick Connect

```
SSID: AP00006151
Password: 12345678
T50 IP: 192.168.0.10
```

### Launch Windows VM

```bash
cd ~/win11-qemu && ./run.sh
```

### Transfer Files to VM

```bash
hdiutil attach ~/win11-qemu/transfer.img
cp files/* /Volumes/TRANSFER/
hdiutil detach /Volumes/TRANSFER
```

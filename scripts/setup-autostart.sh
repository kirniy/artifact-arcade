#!/bin/bash
# Setup ARTIFACT and arcade-bot to auto-start on boot
# Run this on the Raspberry Pi: sudo ./setup-autostart.sh

set -e

echo "=== ARTIFACT Auto-Start Setup ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root: sudo ./setup-autostart.sh"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARTIFACT_SERVICE="$SCRIPT_DIR/artifact.service"
AUDIO_SERVICE="$SCRIPT_DIR/artifact-audio.service"
AUDIO_SETUP="$SCRIPT_DIR/setup-audio.sh"
BOT_SERVICE="$SCRIPT_DIR/arcade-bot.service"

if [ ! -f "$ARTIFACT_SERVICE" ]; then
    echo "Error: artifact.service not found in $SCRIPT_DIR"
    exit 1
fi

# Stop existing services if running
echo "Stopping existing services..."
systemctl stop artifact 2>/dev/null || true
systemctl stop artifact-audio 2>/dev/null || true
systemctl stop arcade-bot 2>/dev/null || true

# Make audio setup script executable
if [ -f "$AUDIO_SETUP" ]; then
    chmod +x "$AUDIO_SETUP"
fi

# Install audio service and setup script
if [ -f "$AUDIO_SERVICE" ] && [ -f "$AUDIO_SETUP" ]; then
    echo "Installing artifact-audio.service..."
    cp "$AUDIO_SERVICE" /etc/systemd/system/artifact-audio.service
    echo "Running audio setup for maximum volume..."
    "$AUDIO_SETUP" || echo "Warning: Audio setup had some issues, continuing..."
fi

# Install artifact service file
echo "Installing artifact.service..."
cp "$ARTIFACT_SERVICE" /etc/systemd/system/artifact.service

# Install arcade-bot service if it exists
if [ -f "$BOT_SERVICE" ]; then
    echo "Installing arcade-bot.service..."
    cp "$BOT_SERVICE" /etc/systemd/system/arcade-bot.service
fi

# Create data directory for control files
DATA_DIR="/home/kirniy/modular-arcade/data"
echo "Creating data directory..."
mkdir -p "$DATA_DIR"
chown kirniy:kirniy "$DATA_DIR"

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable audio service first (artifact depends on it)
if [ -f /etc/systemd/system/artifact-audio.service ]; then
    echo "Enabling audio auto-setup on boot..."
    systemctl enable artifact-audio
fi

# Enable auto-start for artifact
echo "Enabling artifact auto-start on boot..."
systemctl enable artifact

# Enable arcade-bot if service was installed
if [ -f /etc/systemd/system/arcade-bot.service ]; then
    echo "Enabling arcade-bot auto-start on boot..."
    systemctl enable arcade-bot
fi

# Disable desktop compositor (labwc) to free DRM for pygame
echo "Disabling desktop compositor for kmsdrm..."
systemctl disable labwc 2>/dev/null || true

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Services configured:"
echo "  artifact-audio  - Audio setup (runs before artifact)"
echo "  artifact        - Main arcade application"
if [ -f /etc/systemd/system/arcade-bot.service ]; then
echo "  arcade-bot      - Telegram bot for remote control"
fi
echo ""
echo "Audio configured:"
echo "  - Driver: snd-bcm2835 (auto-loads at boot)"
echo "  - Device: hw:2,0 (3.5mm headphones)"
echo "  - Volume: +4dB (maximum nightclub volume!)"
echo ""
echo "Data stored in: /home/kirniy/modular-arcade/data/"
echo "  (coupons.json, stats.json, control.json - not touched by git)"
echo ""
echo "Commands:"
echo "  Start:       sudo systemctl start artifact-audio artifact arcade-bot"
echo "  Stop:        sudo systemctl stop artifact arcade-bot"
echo "  Logs:        journalctl -u artifact -u arcade-bot -f"
echo "  Status:      systemctl status artifact-audio artifact arcade-bot"
echo "  Max Volume:  sudo ~/modular-arcade/scripts/setup-audio.sh"
echo ""
echo "Note: Hold Backspace for 3 seconds to shutdown."
echo "      Plug in power to boot and auto-start."

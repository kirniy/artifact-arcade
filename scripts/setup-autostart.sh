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
BOT_SERVICE="$SCRIPT_DIR/arcade-bot.service"

if [ ! -f "$ARTIFACT_SERVICE" ]; then
    echo "Error: artifact.service not found in $SCRIPT_DIR"
    exit 1
fi

# Stop existing services if running
echo "Stopping existing services..."
systemctl stop artifact 2>/dev/null || true
systemctl stop arcade-bot 2>/dev/null || true

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

# Load audio module on boot
echo "Configuring audio module..."
echo "snd-bcm2835" > /etc/modules-load.d/audio.conf

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Services configured:"
echo "  artifact     - Main arcade application"
if [ -f /etc/systemd/system/arcade-bot.service ]; then
echo "  arcade-bot   - Telegram bot for remote control"
fi
echo ""
echo "Data stored in: /home/kirniy/modular-arcade/data/"
echo "  (coupons.json, stats.json, control.json - not touched by git)"
echo ""
echo "Commands:"
echo "  Start:       sudo systemctl start artifact arcade-bot"
echo "  Stop:        sudo systemctl stop artifact arcade-bot"
echo "  Logs:        journalctl -u artifact -u arcade-bot -f"
echo "  Status:      systemctl status artifact arcade-bot"
echo ""
echo "Note: Hold Backspace for 3 seconds to shutdown."
echo "      Plug in power to boot and auto-start."

#!/bin/bash
# Setup ARTIFACT to auto-start on boot
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
SERVICE_FILE="$SCRIPT_DIR/artifact.service"

if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: artifact.service not found in $SCRIPT_DIR"
    exit 1
fi

# Stop existing service if running
echo "Stopping existing service..."
systemctl stop artifact 2>/dev/null || true

# Install service file
echo "Installing service file..."
cp "$SERVICE_FILE" /etc/systemd/system/artifact.service

# Reload systemd
echo "Reloading systemd..."
systemctl daemon-reload

# Enable auto-start
echo "Enabling auto-start on boot..."
systemctl enable artifact

# Disable desktop compositor (labwc) to free DRM for pygame
echo "Disabling desktop compositor for kmsdrm..."
systemctl disable labwc 2>/dev/null || true

# Load audio module on boot
echo "Configuring audio module..."
echo "snd-bcm2835" > /etc/modules-load.d/audio.conf

echo ""
echo "=== Setup Complete ==="
echo ""
echo "ARTIFACT will now auto-start on boot."
echo ""
echo "Commands:"
echo "  Start now:     sudo systemctl start artifact"
echo "  Stop:          sudo systemctl stop artifact"
echo "  View logs:     journalctl -u artifact -f"
echo "  Disable:       sudo systemctl disable artifact"
echo ""
echo "Note: Hold Backspace for 3 seconds to shutdown."
echo "      Plug in power to boot and auto-start."

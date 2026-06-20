#!/bin/bash
# Install the VNVNC CRT video-wall service without enabling or starting it.

set -euo pipefail

if [ "$EUID" -ne 0 ]; then
    echo "Run as root: sudo ./scripts/install-vnvnc-video-wall.sh"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICE_SRC="$SCRIPT_DIR/vnvnc-video-wall.service"
SERVICE_DST="/etc/systemd/system/vnvnc-video-wall.service"

if [ ! -f "$SERVICE_SRC" ]; then
    echo "Missing service file: $SERVICE_SRC"
    exit 1
fi

mkdir -p /home/kirniy/modular-arcade/data/video_wall
chown -R kirniy:kirniy /home/kirniy/modular-arcade/data/video_wall

cp "$SERVICE_SRC" "$SERVICE_DST"
systemctl daemon-reload

echo "Installed $SERVICE_DST"
echo "Service is intentionally disabled. Normal TV-wall mode now runs inside artifact."
echo "Use ./scripts/set-vnvnc-tv-wall-mode.sh 640x480 --restart for live operation."
echo "Start this standalone service only as an isolated diagnostic with artifact stopped."

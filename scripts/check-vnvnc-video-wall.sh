#!/bin/bash
# Quick diagnostics for HDMI capture-card and video-wall rendering.

set -euo pipefail

cd /home/kirniy/modular-arcade 2>/dev/null || cd "$(dirname "$0")/.."

echo "=== Video devices ==="
if command -v v4l2-ctl >/dev/null 2>&1; then
    v4l2-ctl --list-devices || true
    echo
    DEVICE="${VNVNC_VIDEO_WALL_DEVICE:-/dev/video0}"
    if [ -e "$DEVICE" ]; then
        echo "=== Formats for $DEVICE ==="
        v4l2-ctl --device="$DEVICE" --list-formats-ext || true
    else
        echo "$DEVICE not found"
    fi
else
    ls -l /dev/video* 2>/dev/null || echo "No /dev/video* devices found"
fi

echo
echo "=== Headless render test ==="
PYTHONPATH="${PYTHONPATH:-$(pwd)/src}" \
    "${VNVNC_PYTHON:-.venv/bin/python}" -m artifact.video_wall.renderer --headless-test
echo "Wrote ${VNVNC_VIDEO_WALL_HEADLESS_OUTPUT:-/tmp/vnvnc-video-wall-frame.jpg}"

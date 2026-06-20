#!/bin/bash
# Quick diagnostics for HDMI capture-card and video-wall rendering.

set -euo pipefail

cd /home/kirniy/modular-arcade 2>/dev/null || cd "$(dirname "$0")/.."

echo "=== Confirmed-good live setup ==="
echo "Expected during guest operation:"
echo "  artifact: active"
echo "  vnvnc-video-wall: inactive"
echo "  DRM owner: only python -m artifact.main on /dev/dri/card1"
echo "  HDMI-A-1: 720x480 photobooth/NovaStar"
echo "  HDMI-A-2: 640x480 TV wall"
echo

echo "=== Services ==="
systemctl is-active artifact || true
systemctl is-active vnvnc-video-wall || true
echo

echo "=== TV-wall env ==="
grep -E '^(VNVNC_INPROCESS_TV_WALL_ENABLED|VNVNC_VIDEO_WALL_(OUTPUT_WIDTH|OUTPUT_HEIGHT|DRM_CONNECTOR|SWITCH_INTERVAL|PRIMARY_WINDOW|DISPLAY_YEAR)|VNVNC_MAIN_DRM_CONNECTOR)=' .env 2>/dev/null || true
echo

echo "=== Display ownership ==="
if command -v fuser >/dev/null 2>&1; then
    sudo -n fuser -v /dev/dri/card1 /dev/fb0 2>&1 || true
else
    echo "fuser not installed"
fi
echo

echo "=== KMS connectors ==="
if command -v kmsprint >/dev/null 2>&1; then
    kmsprint | sed -n '1,80p'
elif command -v modetest >/dev/null 2>&1; then
    modetest -M vc4 -c | sed -n '1,180p'
else
    echo "kmsprint/modetest not installed"
fi
echo

echo "=== Shared capture heartbeat ==="
PYTHON_BIN="${VNVNC_PYTHON:-}"
if [ -z "${PYTHON_BIN}" ]; then
    if [ -x ".venv/bin/python" ]; then
        PYTHON_BIN=".venv/bin/python"
    else
        PYTHON_BIN="python3"
    fi
fi
"${PYTHON_BIN}" - <<'PY'
from pathlib import Path
import time

try:
    from PIL import Image
except Exception:
    Image = None

for path in [Path("data/video_wall/heartbeat"), Path("data/video_wall/hdmi_capture_latest.jpg")]:
    if not path.exists():
        print(f"{path}: missing")
        continue
    stat = path.stat()
    extra = ""
    if Image is not None and path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        try:
            extra = f" size={Image.open(path).size}"
        except Exception:
            pass
    print(f"{path}: age={time.time() - stat.st_mtime:.2f}s bytes={stat.st_size}{extra}")
PY
echo

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
PYCACHE_DIR="${ARTIFACT_PYCACHE_DIR:-/tmp/artifact-video-wall-check-pycache}"
rm -rf "$PYCACHE_DIR"
mkdir -p "$PYCACHE_DIR"
PYTHONPATH="${PYTHONPATH:-$(pwd)/src}" \
    PYTHONPYCACHEPREFIX="$PYCACHE_DIR" \
    "${VNVNC_PYTHON:-.venv/bin/python}" -m artifact.video_wall.renderer --headless-test
rm -rf "$PYCACHE_DIR"
echo "Wrote ${VNVNC_VIDEO_WALL_HEADLESS_OUTPUT:-/tmp/vnvnc-video-wall-frame.jpg}"

#!/bin/bash
# Configure the in-process VNVNC TV-wall HDMI output mode.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
ENV_FILE="${ARTIFACT_ENV_FILE:-${REPO_DIR}/.env}"
MODE="${1:-}"
RESTART=0

usage() {
    cat <<'EOF'
Usage: set-vnvnc-tv-wall-mode.sh <640x480|720x480|1280x720> [--restart]

Updates .env for the in-process TV wall. The standalone vnvnc-video-wall
service is kept disabled so artifact remains the only DRM/KMS owner.

Examples:
  ./scripts/set-vnvnc-tv-wall-mode.sh 640x480 --restart
  ./scripts/set-vnvnc-tv-wall-mode.sh 1280x720 --restart
EOF
}

if [ -z "${MODE}" ] || [ "${MODE}" = "-h" ] || [ "${MODE}" = "--help" ]; then
    usage
    exit 0
fi

shift || true
for arg in "$@"; do
    case "$arg" in
        --restart)
            RESTART=1
            ;;
        *)
            echo "Unknown option: ${arg}" >&2
            usage >&2
            exit 2
            ;;
    esac
done

case "${MODE}" in
    640x480)
        WIDTH=640
        HEIGHT=480
        ;;
    720x480)
        WIDTH=720
        HEIGHT=480
        ;;
    1280x720)
        WIDTH=1280
        HEIGHT=720
        ;;
    *)
        echo "Unsupported TV-wall mode: ${MODE}" >&2
        usage >&2
        exit 2
        ;;
esac

set_env() {
    local key="$1"
    local value="$2"
    ENV_FILE="${ENV_FILE}" ENV_KEY="${key}" ENV_VALUE="${value}" python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_FILE"])
key = os.environ["ENV_KEY"]
value = os.environ["ENV_VALUE"]

lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
needle = f"{key}="
written = False
out = []
for line in lines:
    stripped = line.strip()
    if stripped.startswith("#") or not stripped.startswith(needle):
        out.append(line)
        continue
    out.append(f"{key}={value}")
    written = True
if not written:
    out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

cd "${REPO_DIR}"
touch "${ENV_FILE}"

set_env VNVNC_INPROCESS_TV_WALL_ENABLED true
set_env VNVNC_VIDEO_WALL_OUTPUT_WIDTH "${WIDTH}"
set_env VNVNC_VIDEO_WALL_OUTPUT_HEIGHT "${HEIGHT}"
set_env VNVNC_VIDEO_WALL_DRM_CONNECTOR HDMI-A-2
set_env VNVNC_MAIN_DRM_CONNECTOR HDMI-A-1
set_env VNVNC_VIDEO_WALL_SWITCH_INTERVAL 0
set_env VNVNC_VIDEO_WALL_PRIMARY_WINDOW 0
set_env VNVNC_VIDEO_WALL_DISPLAY_YEAR 2017

if systemctl list-unit-files vnvnc-video-wall.service >/dev/null 2>&1; then
    sudo -n systemctl disable --now vnvnc-video-wall.service >/dev/null 2>&1 || true
fi

echo "TV-wall mode set to ${WIDTH}x${HEIGHT} in ${ENV_FILE}"
echo "Standalone vnvnc-video-wall service is disabled; artifact owns both HDMI outputs."

if [ "${RESTART}" = "1" ]; then
    ARTIFACT_RESTART_SERVICES=artifact ARTIFACT_MARK_RESTART_PENDING=1 \
        "${REPO_DIR}/scripts/restart-artifact-if-idle.sh" || true
fi

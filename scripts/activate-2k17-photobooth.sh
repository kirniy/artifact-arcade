#!/bin/bash
# Activate the 2K17 photobooth configuration without starting experimental wall output.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
ENV_FILE="${ARTIFACT_ENV_FILE:-${REPO_DIR}/.env}"
RESTART=0

for arg in "$@"; do
    case "$arg" in
        --restart)
            RESTART=1
            ;;
        -h|--help)
            echo "Usage: $0 [--restart]"
            echo "Sets .env to the 2K17 photobooth theme. Video wall remains installed/started separately."
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

cd "${REPO_DIR}"
mkdir -p "$(dirname "${ENV_FILE}")" data/video_wall
touch "${ENV_FILE}"

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

set_env PHOTOBOOTH_THEME 2k17
set_env PHOTOBOOTH_MENU_MODES 2k17
set_env PHOTOBOOTH_CAMERA_SELECTOR_ENABLED auto
set_env PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED false
set_env VNVNC_PRIMARY_CAMERA_SHARED_FRAME_ENABLED true
set_env VNVNC_VIDEO_WALL_DISPLAY_YEAR 2017

PYTHON_BIN="${VNVNC_PYTHON:-}"
if [ -z "${PYTHON_BIN}" ]; then
    if [ -x ".venv/bin/python" ]; then
        PYTHON_BIN=".venv/bin/python"
    else
        PYTHON_BIN="python3"
    fi
fi

PYCACHE_DIR="${ARTIFACT_PYCACHE_DIR:-/tmp/artifact-activate-pycache}"
rm -rf "${PYCACHE_DIR}"
mkdir -p "${PYCACHE_DIR}"

PYTHONPATH=src PYTHONPYCACHEPREFIX="${PYCACHE_DIR}" "${PYTHON_BIN}" -m py_compile \
    src/artifact/ai/caricature.py \
    src/artifact/animation/idle_scenes.py \
    src/artifact/modes/photobooth.py \
    src/artifact/modes/photobooth_themes.py \
    src/artifact/utils/camera_service.py \
    src/artifact/utils/hdmi_capture.py \
    src/artifact/utils/s3_upload.py \
    src/artifact/video_wall/renderer.py \
    scripts/upload_spool_daemon.py

rm -rf "${PYCACHE_DIR}"

echo "2K17 photobooth env is active in ${ENV_FILE}"
echo "Video-wall service is not enabled or started by this script."

if [ "${RESTART}" = "1" ]; then
    ARTIFACT_MARK_RESTART_PENDING=1 "${REPO_DIR}/scripts/restart-artifact-if-idle.sh" || true
fi

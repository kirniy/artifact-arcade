#!/bin/bash
# Включить воскресную тему «Чемпионат мира 2026: Испания × Аргентина».

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
            echo "Включает в .env тему фотобудки «Чемпионат мира 2026: Испания × Аргентина»."
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            exit 2
            ;;
    esac
done

cd "${REPO_DIR}"
mkdir -p "$(dirname "${ENV_FILE}")"
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
    if line.strip().startswith("#") or not line.startswith(needle):
        out.append(line)
        continue
    out.append(f"{key}={value}")
    written = True
if not written:
    out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY
}

set_env PHOTOBOOTH_THEME world-cup-final
set_env PHOTOBOOTH_MENU_MODES world_cup_final
set_env PHOTOBOOTH_AI_ENABLED true
set_env PHOTOBOOTH_CAMERA_SELECTOR_ENABLED auto
set_env PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED true
set_env PHOTOBOOTH_PRINT_FORTUNES false
set_env ARTIFACT_IMAGE_PROVIDER vertex
set_env ARTIFACT_GEMINI_PROVIDER vertex
set_env GOOGLE_GENAI_USE_VERTEXAI true
set_env GOOGLE_CLOUD_PROJECT project-8b5b3334-3456-4605-b2c
set_env GOOGLE_CLOUD_LOCATION global
set_env GEMINI_IMAGE_MODEL gemini-3.1-flash-lite-image
set_env VNVNC_INPROCESS_TV_WALL_ENABLED false

PYTHON_BIN="${VNVNC_PYTHON:-}"
if [ -z "${PYTHON_BIN}" ]; then
    if [ -x ".venv/bin/python" ]; then
        PYTHON_BIN=".venv/bin/python"
    else
        PYTHON_BIN="python3"
    fi
fi

PYCACHE_DIR="${ARTIFACT_PYCACHE_DIR:-/tmp/artifact-activate-world-cup-final-pycache}"
rm -rf "${PYCACHE_DIR}"
mkdir -p "${PYCACHE_DIR}"

PYTHONPATH=src PYTHONPYCACHEPREFIX="${PYCACHE_DIR}" "${PYTHON_BIN}" -m py_compile \
    src/artifact/ai/client.py \
    src/artifact/ai/caricature.py \
    src/artifact/animation/idle_scenes.py \
    src/artifact/modes/manager.py \
    src/artifact/modes/photobooth.py \
    src/artifact/modes/photobooth_themes.py \
    src/artifact/printing/photobooth_roll.py

rm -rf "${PYCACHE_DIR}"

echo "Тема фотобудки «Чемпионат мира 2026» включена в ${ENV_FILE}"

if [ "${RESTART}" = "1" ]; then
    ARTIFACT_MARK_RESTART_PENDING=1 "${REPO_DIR}/scripts/restart-artifact-if-idle.sh" || true
fi

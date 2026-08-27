#!/bin/bash
# Stage or enable the signed VNVNC prize-drum client without exposing its HMAC secret.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
ENV_FILE="${ARTIFACT_ENV_FILE:-${REPO_DIR}/.env}"
ENABLE=false
RESTART=0

for arg in "$@"; do
    case "$arg" in
        --enable) ENABLE=true ;;
        --disable) ENABLE=false ;;
        --restart) RESTART=1 ;;
        -h|--help)
            echo "Usage: ARTIFACT_KIOSK_DEVICE_SECRET=... $0 [--enable|--disable] [--restart]"
            exit 0
            ;;
        *) echo "Unknown option: $arg" >&2; exit 2 ;;
    esac
done

DEVICE_ID="${ARTIFACT_KIOSK_DEVICE_ID:-artifact}"
DEVICE_SECRET="${ARTIFACT_KIOSK_DEVICE_SECRET:-}"
API_BASE_URL="${VNVNC_KIOSK_API_BASE_URL:-https://api.vnvnc.ru}"

case "${DEVICE_ID}" in
    *[!A-Za-z0-9._-]*|'') echo "Invalid ARTIFACT_KIOSK_DEVICE_ID" >&2; exit 2 ;;
esac
if [ "${#DEVICE_SECRET}" -lt 24 ]; then
    echo "ARTIFACT_KIOSK_DEVICE_SECRET is absent or too short" >&2
    exit 2
fi
case "${API_BASE_URL}" in
    https://*) ;;
    *) echo "VNVNC_KIOSK_API_BASE_URL must use HTTPS" >&2; exit 2 ;;
esac

mkdir -p "$(dirname "${ENV_FILE}")"
touch "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

ENV_FILE="${ENV_FILE}" \
DEVICE_ID="${DEVICE_ID}" \
DEVICE_SECRET="${DEVICE_SECRET}" \
API_BASE_URL="${API_BASE_URL%/}" \
PRIZE_DRUM_ENABLED="${ENABLE}" \
python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["ENV_FILE"])
updates = {
    "ARTIFACT_PRIZE_DRUM_ENABLED": os.environ["PRIZE_DRUM_ENABLED"],
    "ARTIFACT_KIOSK_STUB": "false",
    "ARTIFACT_KIOSK_DEVICE_ID": os.environ["DEVICE_ID"],
    "ARTIFACT_KIOSK_DEVICE_SECRET": os.environ["DEVICE_SECRET"],
    "VNVNC_KIOSK_API_BASE_URL": os.environ["API_BASE_URL"],
    "ARTIFACT_MOCK_PRINTER": "false",
    "ARTIFACT_MOCK_HARDWARE": "false",
}
lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
seen: set[str] = set()
out: list[str] = []
for line in lines:
    if line.lstrip().startswith("#") or "=" not in line:
        out.append(line)
        continue
    key = line.split("=", 1)[0]
    if key not in updates:
        out.append(line)
        continue
    if key not in seen:
        out.append(f"{key}={updates[key]}")
        seen.add(key)
for key, value in updates.items():
    if key not in seen:
        out.append(f"{key}={value}")
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
PY

echo "Prize drum configuration staged (enabled=${ENABLE}); secret stored without display."
if [ "${RESTART}" = "1" ]; then
    ARTIFACT_MARK_RESTART_PENDING=1 "${REPO_DIR}/scripts/restart-artifact-if-idle.sh" || true
fi

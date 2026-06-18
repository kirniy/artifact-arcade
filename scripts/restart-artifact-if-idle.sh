#!/bin/bash
# Restart arcade services only when the booth is idle.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
STATUS_FILE="${ARCADE_STATUS_FILE:-${REPO_DIR}/data/status.json}"
PENDING_FILE="${ARTIFACT_RESTART_PENDING_FILE:-${REPO_DIR}/.deploy/restart-pending}"
MAX_AGE="${ARTIFACT_IDLE_STATUS_MAX_AGE:-20}"
FORCE="${ARTIFACT_FORCE_RESTART:-0}"
MARK_PENDING="${ARTIFACT_MARK_RESTART_PENDING:-0}"
SERVICES="${ARTIFACT_RESTART_SERVICES:-artifact arcade-bot artifact-upload-spool}"

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

status_state() {
    if [ "${FORCE}" = "1" ]; then
        echo "forced"
        return 0
    fi

    PYTHON_BIN="${VNVNC_PYTHON:-}"
    if [ -z "${PYTHON_BIN}" ]; then
        if [ -x "${REPO_DIR}/.venv/bin/python" ]; then
            PYTHON_BIN="${REPO_DIR}/.venv/bin/python"
        else
            PYTHON_BIN="python3"
        fi
    fi

    STATUS_FILE="${STATUS_FILE}" MAX_AGE="${MAX_AGE}" "${PYTHON_BIN}" - <<'PY'
import json
import os
import sys
import time

path = os.environ["STATUS_FILE"]
max_age = float(os.environ.get("MAX_AGE", "20"))

try:
    with open(path, encoding="utf-8") as handle:
        status = json.load(handle)
except FileNotFoundError:
    print("missing status")
    sys.exit(0)
except Exception as exc:
    print(f"unreadable status: {exc}")
    sys.exit(0)

timestamp = status.get("timestamp")
try:
    age = time.time() - float(timestamp)
except Exception:
    print("status has no valid timestamp")
    sys.exit(0)

mode = str(status.get("mode", "")).strip().lower()
if age > max_age:
    print(f"stale status ({age:.0f}s, mode={mode or '?'})")
    sys.exit(0)

if mode in {"", "idle", "none"}:
    print(f"idle ({age:.0f}s)")
    sys.exit(0)

print(f"busy ({mode}, {age:.0f}s)")
sys.exit(1)
PY
}

mkdir -p "$(dirname "${PENDING_FILE}")"

set +e
state="$(status_state 2>&1)"
state_code=$?
set -e

if [ "${state_code}" -ne 0 ]; then
    log "Restart deferred: ${state}"
    if [ "${MARK_PENDING}" = "1" ]; then
        printf '%s\n' "$(date '+%Y-%m-%d %H:%M:%S') ${state}" > "${PENDING_FILE}"
    fi
    exit 75
fi

log "Restart allowed: ${state}"

for service in ${SERVICES}; do
    if systemctl list-unit-files "${service}.service" >/dev/null 2>&1 || systemctl status "${service}" >/dev/null 2>&1; then
        if sudo -n systemctl restart "${service}"; then
            log "Restarted ${service}"
        else
            log "Warning: failed to restart ${service}"
        fi
    else
        log "Skipping missing service ${service}"
    fi
done

rm -f "${PENDING_FILE}"
log "Restart complete"

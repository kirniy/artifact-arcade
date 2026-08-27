#!/bin/bash
# Install/start/stop the supervised, non-redeemable RP80 canary without editing .env.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
SYSTEMD_DIR="${ARTIFACT_SYSTEMD_DIR:-/etc/systemd/system}"
BACKEND_UNIT="artifact-prize-drum-canary-backend.service"
UI_UNIT="artifact-prize-drum-canary-ui.service"
ACTION="${1:-status}"

fail() {
    echo "FAIL: $*" >&2
    exit 1
}

require_root() {
    [ "${EUID}" -eq 0 ] || fail "run with sudo"
}

units_are_current() {
    cmp -s "${REPO_DIR}/scripts/${BACKEND_UNIT}" "${SYSTEMD_DIR}/${BACKEND_UNIT}" &&
        cmp -s "${REPO_DIR}/scripts/${UI_UNIT}" "${SYSTEMD_DIR}/${UI_UNIT}"
}

wait_active() {
    local unit="$1"
    local attempts="${2:-20}"
    local index
    for ((index = 0; index < attempts; index++)); do
        systemctl is-active --quiet "${unit}" && return 0
        sleep 1
    done
    return 1
}

case "${ACTION}" in
    install)
        require_root
        install -m 0644 "${REPO_DIR}/scripts/${BACKEND_UNIT}" "${SYSTEMD_DIR}/${BACKEND_UNIT}"
        install -m 0644 "${REPO_DIR}/scripts/${UI_UNIT}" "${SYSTEMD_DIR}/${UI_UNIT}"
        systemctl daemon-reload
        # They have no [Install] section, but remove stale enablement left by any old unit.
        systemctl disable "${BACKEND_UNIT}" "${UI_UNIT}" >/dev/null 2>&1 || true
        echo "Installed supervised canary units; neither is enabled at boot."
        ;;
    start)
        require_root
        [ "$(uname -s)" = "Linux" ] || fail "physical canary runs only on the cabinet"
        units_are_current || fail "run '$0 install' after updating the repository"
        lsusb -d 0fe6:811e >/dev/null || fail "exact RP80 0fe6:811e is not connected"
        "${REPO_DIR}/scripts/preflight-prize-drum-deployment.sh" --hardware-only

        canary_start_complete=false
        cleanup_incomplete_start() {
            if [ "${canary_start_complete}" != true ]; then
                systemctl stop "${UI_UNIT}" >/dev/null 2>&1 || true
                systemctl stop "${BACKEND_UNIT}" >/dev/null 2>&1 || true
                systemctl start artifact.service >/dev/null 2>&1 || true
            fi
        }
        trap cleanup_incomplete_start EXIT

        systemctl start "${BACKEND_UNIT}"
        wait_active "${BACKEND_UNIT}" || fail "canary backend did not become active"
        backend_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
            --connect-timeout 2 --max-time 4 http://127.0.0.1:8765/)"
        [ "${backend_status}" = "401" ] || fail "signed canary backend guard did not return 401"

        systemctl start "${UI_UNIT}"
        wait_active "${UI_UNIT}" || fail "canary UI did not become active"
        systemctl is-active --quiet artifact.service && fail "production UI still owns the display"

        UI_UNIT="${UI_UNIT}" python3 - <<'PY'
import os
from pathlib import Path
import subprocess

unit = os.environ["UI_UNIT"]
pid = int(subprocess.check_output(
    ["systemctl", "show", unit, "-p", "MainPID", "--value"], text=True
).strip())
if pid <= 0:
    raise SystemExit("canary UI has no main process")
values = {}
for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
    if b"=" in item:
        key, value = item.split(b"=", 1)
        values[key.decode(errors="replace")] = value.decode(errors="replace")
expected = {
    "ARTIFACT_PRIZE_DRUM_ENABLED": "true",
    "ARTIFACT_KIOSK_STUB": "false",
    "ARTIFACT_MOCK_PRINTER": "false",
    "ARTIFACT_MOCK_HARDWARE": "false",
    "VNVNC_KIOSK_API_BASE_URL": "http://127.0.0.1:8765",
}
if any(values.get(key) != value for key, value in expected.items()):
    raise SystemExit("canary UI environment is not fail-closed")
if len(values.get("ARTIFACT_KIOSK_DEVICE_SECRET", "")) < 24:
    raise SystemExit("canary UI has no signed device secret")
PY
        canary_start_complete=true
        trap - EXIT
        echo "Physical canary active; all coupons are TEST-only and non-redeemable."
        ;;
    stop)
        require_root
        systemctl stop "${UI_UNIT}" >/dev/null 2>&1 || true
        systemctl stop "${BACKEND_UNIT}" >/dev/null 2>&1 || true
        systemctl start artifact.service
        wait_active artifact.service || fail "production artifact.service did not recover"
        echo "Physical canary stopped; fail-closed production service restored."
        ;;
    status)
        printf '%-44s %s\n' "RP80 0fe6:811e" \
            "$(if command -v lsusb >/dev/null && lsusb -d 0fe6:811e >/dev/null 2>&1; then echo present; else echo absent; fi)"
        for unit in artifact.service "${BACKEND_UNIT}" "${UI_UNIT}"; do
            printf '%-44s %s\n' "${unit}" "$(systemctl is-active "${unit}" 2>/dev/null || true)"
        done
        ;;
    *)
        echo "Usage: sudo $0 {install|start|stop|status}" >&2
        exit 2
        ;;
esac

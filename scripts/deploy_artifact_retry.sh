#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE_DIR="${ROOT_DIR}/.deploy/retry-artifact"
LOG_FILE="${STATE_DIR}/deploy.log"
SUCCESS_FILE="${STATE_DIR}/success"
LOCK_DIR="${STATE_DIR}/lock"
REMOTE_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
REMOTE_TMP="/tmp/modular-arcade-printer-theme-deploy.tgz"

HOSTS=()
if [[ -n "${ARTIFACT_HOST:-}" ]]; then
  HOSTS+=("${ARTIFACT_HOST}")
fi
HOSTS+=(
  "kirniy@100.115.122.91"
  "kirniy@artifact.tailb30214.ts.net"
  "kirniy@artifact.local"
)

FILES=(
  "pyproject.toml"
  "requirements.txt"
  "requirements-hardware.txt"
  "assets/images/2k17.png"
  "assets/images/2k17-black-label-reference.jpg"
  "assets/images/candy-shop.png"
  "assets/idle/2k17/video/2k17-fans.mp4"
  "assets/idle/candy_shop"
  "assets/video_wall/flame-logo.png"
  "data/fortunes/vnvnc_fortunes.json"
  "scripts/activate-2k17-photobooth.sh"
  "scripts/autopull.sh"
  "scripts/check-vnvnc-video-wall.sh"
  "scripts/install-vnvnc-video-wall.sh"
  "scripts/restart-artifact-if-idle.sh"
  "scripts/setup-autostart.sh"
  "scripts/test_rp80_photobooth.py"
  "scripts/upload_spool_daemon.py"
  "scripts/vnvnc-video-wall.service"
  "src/artifact/ai/caricature.py"
  "src/artifact/ai/client.py"
  "src/artifact/animation/idle_scenes.py"
  "src/artifact/hardware/printer/__init__.py"
  "src/artifact/hardware/printer/rp80.py"
  "src/artifact/main.py"
  "src/artifact/modes/photobooth.py"
  "src/artifact/modes/photobooth_themes.py"
  "src/artifact/printing/__init__.py"
  "src/artifact/printing/fortune_quotes.py"
  "src/artifact/printing/manager.py"
  "src/artifact/printing/photobooth_roll.py"
  "src/artifact/utils/camera_service.py"
  "src/artifact/utils/hdmi_capture.py"
  "src/artifact/utils/s3_upload.py"
  "src/artifact/video_wall/__init__.py"
  "src/artifact/video_wall/renderer.py"
)

mkdir -p "${STATE_DIR}"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "${LOG_FILE}" >&2
}

if [[ -f "${SUCCESS_FILE}" && "${ARTIFACT_FORCE_DEPLOY:-0}" != "1" ]]; then
  log "Deploy already succeeded at $(cat "${SUCCESS_FILE}"). Set ARTIFACT_FORCE_DEPLOY=1 to run again."
  exit 0
fi

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  log "Another deploy attempt is already running."
  exit 0
fi
trap 'rm -rf "${LOCK_DIR}"' EXIT

ssh_base=(
  ssh
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=5
  -o ServerAliveCountMax=1
  -o StrictHostKeyChecking=accept-new
)

scp_base=(
  scp
  -o BatchMode=yes
  -o ConnectTimeout=10
  -o ServerAliveInterval=5
  -o ServerAliveCountMax=1
  -o StrictHostKeyChecking=accept-new
)

run_with_timeout() {
  local seconds="$1"
  shift
  if command -v timeout >/dev/null 2>&1; then
    timeout "${seconds}" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "${seconds}" "$@"
  else
    perl -e 'alarm shift @ARGV; exec @ARGV' "${seconds}" "$@"
  fi
}

pick_host() {
  local host output status auth_url
  for host in "${HOSTS[@]}"; do
    log "Checking ${host}..."
    set +e
    output="$(run_with_timeout 25 "${ssh_base[@]}" "${host}" "printf 'ok:%s\n' \"\$(hostname)\"" 2>&1)"
    status=$?
    set -e
    printf '%s\n' "${output}" | tee -a "${LOG_FILE}" >&2
    if [[ ${status} -eq 0 && "${output}" == ok:* ]]; then
      printf '%s' "${host}"
      return 0
    fi
    auth_url="$(grep -Eo 'https://login\.tailscale\.com/a/[A-Za-z0-9]+' <<<"${output}" | tail -1 || true)"
    if [[ -n "${auth_url}" ]]; then
      printf '%s\n' "${auth_url}" > "${STATE_DIR}/tailscale-auth-url"
      log "Tailscale authorization URL: ${auth_url}"
    fi
  done
  return 1
}

archive_path="${STATE_DIR}/payload.tgz"
log "Building deploy payload..."
(
  cd "${ROOT_DIR}"
  tar -czf "${archive_path}" "${FILES[@]}"
)

if ! host="$(pick_host)"; then
  log "No reachable artifact host yet. Will try again on the next scheduled run."
  exit 75
fi

log "Deploying to ${host}..."
"${scp_base[@]}" "${archive_path}" "${host}:${REMOTE_TMP}"

remote_script=$(cat <<'REMOTE'
set -euo pipefail
REMOTE_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
REMOTE_TMP="/tmp/modular-arcade-printer-theme-deploy.tgz"
mkdir -p "${REMOTE_DIR}"
tar -xzf "${REMOTE_TMP}" -C "${REMOTE_DIR}"
cd "${REMOTE_DIR}"

if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python 'qrcode[pil]>=7.4.0' 'pyusb>=1.3.0' 'opencv-python-headless>=4.8.0' 'aiohttp-socks>=0.10.0'
elif [[ -x .venv/bin/python ]] && .venv/bin/python -m pip --version >/dev/null 2>&1; then
  .venv/bin/python -m pip install 'qrcode[pil]>=7.4.0' 'pyusb>=1.3.0' 'opencv-python-headless>=4.8.0' 'aiohttp-socks>=0.10.0'
else
  echo "Warning: no uv/pip installer available; skipped Python dependency install"
fi

if [[ -x .venv/bin/python ]]; then
  rm -rf /tmp/artifact-pycache
  mkdir -p /tmp/artifact-pycache
  PYTHONPATH=src PYTHONPYCACHEPREFIX=/tmp/artifact-pycache .venv/bin/python -m compileall -q \
    src/artifact/ai/caricature.py \
    src/artifact/ai/client.py \
    src/artifact/animation/idle_scenes.py \
    src/artifact/hardware/printer/rp80.py \
    src/artifact/modes/photobooth.py \
    src/artifact/modes/photobooth_themes.py \
    src/artifact/utils/camera_service.py \
    src/artifact/utils/hdmi_capture.py \
    src/artifact/utils/s3_upload.py \
    src/artifact/video_wall/renderer.py \
    scripts/upload_spool_daemon.py \
    src/artifact/printing/manager.py \
    src/artifact/printing/photobooth_roll.py \
    scripts/test_rp80_photobooth.py
fi

if command -v systemctl >/dev/null 2>&1; then
  ./scripts/activate-2k17-photobooth.sh || true
  ARTIFACT_MARK_RESTART_PENDING=1 ./scripts/restart-artifact-if-idle.sh || true
fi

rm -f "${REMOTE_TMP}"
printf 'remote deploy complete on %s\n' "$(hostname)"
REMOTE
)

"${ssh_base[@]}" "${host}" "ARTIFACT_REMOTE_DIR='${REMOTE_DIR}' bash -s" <<<"${remote_script}"
date '+%Y-%m-%d %H:%M:%S' > "${SUCCESS_FILE}"
log "Deploy succeeded to ${host}."

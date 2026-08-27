#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +"%Y%m%d-%H%M%S")"
HOST="${ARTIFACT_HOST:-kirniy@100.115.122.91}"
OUT_DIR="${ROOT_DIR}/machine-backups/${STAMP}"
LOCAL_DIR="${OUT_DIR}/local"
REMOTE_DIR="${OUT_DIR}/remote"

mkdir -p "${LOCAL_DIR}" "${REMOTE_DIR}"

echo "Creating ARTIFACT machine snapshot"
echo "Host: ${HOST}"
echo "Output: ${OUT_DIR}"

git -C "${ROOT_DIR}" rev-parse HEAD > "${LOCAL_DIR}/git-head.txt"
git -C "${ROOT_DIR}" status --short > "${LOCAL_DIR}/git-status.txt"
git -C "${ROOT_DIR}" diff > "${LOCAL_DIR}/git-diff.patch"
git -C "${ROOT_DIR}" diff --cached > "${LOCAL_DIR}/git-diff-staged.patch"
git -C "${ROOT_DIR}" ls-files --others --exclude-standard > "${LOCAL_DIR}/git-untracked.txt"

mkdir -p "${LOCAL_DIR}/tracked"
cp -R "${ROOT_DIR}/configs/novastar" "${LOCAL_DIR}/tracked/"
cp "${ROOT_DIR}/scripts/artifact.service" "${LOCAL_DIR}/tracked/"
cp "${ROOT_DIR}/pi-config/cmdline.txt" "${LOCAL_DIR}/tracked/" 2>/dev/null || true
cp "${ROOT_DIR}/docs/hardware/display-setup.md" "${LOCAL_DIR}/tracked/"
cp "${ROOT_DIR}/docs/hardware/novastar-setup.md" "${LOCAL_DIR}/tracked/"
cp "${ROOT_DIR}/docs/hardware/machine-restore.md" "${LOCAL_DIR}/tracked/"

ssh -o BatchMode=yes "${HOST}" "
  set -e
  echo HOSTNAME=\$(hostname)
  echo '---'
  uname -a
  echo '---'
  systemctl show artifact --property=ActiveState,SubState,StatusText,ExecStart,FragmentPath --no-pager || sudo systemctl show artifact --property=ActiveState,SubState,StatusText,ExecStart,FragmentPath --no-pager
  echo '---'
  ip -4 addr
  echo '---'
  ip route
  echo '---'
  ip link show eth0 || true
  echo '---'
  nmcli -t -f NAME,UUID,TYPE,DEVICE con show --active || true
  echo '---'
  nmcli con show VNVNC || true
  echo '---'
  systemctl is-enabled artifact artifact-dashboard artifact-update.timer tailscaled 2>/dev/null || true
  echo '---'
  journalctl -u artifact -b -n 300 --no-pager || true
" > "${REMOTE_DIR}/diagnostics.txt"

ssh -o BatchMode=yes "${HOST}" "
  sudo tar --ignore-failed-read -czf - \
    /etc/systemd/system/artifact.service \
    /boot/firmware/config.txt \
    /boot/firmware/cmdline.txt \
    /etc/NetworkManager/system-connections \
    /home/kirniy/modular-arcade/.env \
    /home/kirniy/.aws \
    /root/.aws
" > "${REMOTE_DIR}/system-state.tgz"

cat > "${OUT_DIR}/README.txt" <<EOF
ARTIFACT machine snapshot

Timestamp: ${STAMP}
Host: ${HOST}

Contents:
- local/git-head.txt
- local/git-status.txt
- local/git-diff.patch
- local/git-diff-staged.patch
- local/git-untracked.txt
- local/tracked/
- remote/diagnostics.txt
- remote/system-state.tgz
EOF

echo "Snapshot complete: ${OUT_DIR}"

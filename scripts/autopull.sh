#!/bin/bash
# Auto-pull from git and restart services when the booth is idle.
# This script is run by arcade-autopull.service or a cron job/timer

set -euo pipefail

REPO_DIR="/home/kirniy/modular-arcade"
LOG_FILE="/home/kirniy/modular-arcade/logs/autopull.log"
PENDING_FILE="/home/kirniy/modular-arcade/.deploy/restart-pending"
AUTO_ACTIVATE_2K17="${ARTIFACT_AUTO_ACTIVATE_2K17:-1}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
    echo "$1"
}

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PENDING_FILE")"
cd "$REPO_DIR"

env_has_2k17() {
    [ -f "$REPO_DIR/.env" ] &&
        grep -Eq '^PHOTOBOOTH_THEME=2k17$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_MENU_MODES=2k17$' "$REPO_DIR/.env"
}

ensure_2k17_activation() {
    if [ "$AUTO_ACTIVATE_2K17" != "1" ]; then
        return 1
    fi
    if env_has_2k17; then
        return 1
    fi
    if [ ! -x "$REPO_DIR/scripts/activate-2k17-photobooth.sh" ]; then
        log "2K17 activation script is not present yet."
        return 1
    fi

    log "Activating 2K17 photobooth env..."
    ARTIFACT_REMOTE_DIR="$REPO_DIR" "$REPO_DIR/scripts/activate-2k17-photobooth.sh"
    return 0
}

# Check for updates
log "Checking for updates..."
git fetch origin main

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date."
    activation_changed=0
    if ensure_2k17_activation; then
        activation_changed=1
    fi
    if [ -f "$PENDING_FILE" ] || [ "$activation_changed" = "1" ]; then
        log "Restart needed; trying idle-gated restart..."
        ARTIFACT_RESTART_PENDING_FILE="$PENDING_FILE" \
            ARTIFACT_MARK_RESTART_PENDING=1 \
            "$REPO_DIR/scripts/restart-artifact-if-idle.sh" || true
    fi
    exit 0
fi

log "Updates found, pulling..."
git pull --ff-only origin main

ensure_2k17_activation || true

log "Trying idle-gated restart..."
ARTIFACT_RESTART_PENDING_FILE="$PENDING_FILE" \
    ARTIFACT_MARK_RESTART_PENDING=1 \
    "$REPO_DIR/scripts/restart-artifact-if-idle.sh" || true

log "Auto-pull complete!"

#!/bin/bash
# Auto-pull from git and restart services when the booth is idle.
# This script is run by arcade-autopull.service or a cron job/timer

set -euo pipefail

REPO_DIR="/home/kirniy/modular-arcade"
LOG_FILE="/home/kirniy/modular-arcade/logs/autopull.log"
PENDING_FILE="/home/kirniy/modular-arcade/.deploy/restart-pending"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
    echo "$1"
}

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PENDING_FILE")"
cd "$REPO_DIR"

# Check for updates
log "Checking for updates..."
git fetch origin main

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date."
    if [ -f "$PENDING_FILE" ]; then
        log "Pending restart exists; trying idle-gated restart..."
        ARTIFACT_RESTART_PENDING_FILE="$PENDING_FILE" \
            ARTIFACT_MARK_RESTART_PENDING=1 \
            "$REPO_DIR/scripts/restart-artifact-if-idle.sh" || true
    fi
    exit 0
fi

log "Updates found, pulling..."
git pull --ff-only origin main

log "Trying idle-gated restart..."
ARTIFACT_RESTART_PENDING_FILE="$PENDING_FILE" \
    ARTIFACT_MARK_RESTART_PENDING=1 \
    "$REPO_DIR/scripts/restart-artifact-if-idle.sh" || true

log "Auto-pull complete!"

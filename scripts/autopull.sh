#!/bin/bash
# Auto-pull from git and restart services
# This script is run by arcade-autopull.service or a cron job/timer

set -e

REPO_DIR="/home/kirniy/modular-arcade"
LOG_FILE="/home/kirniy/modular-arcade/logs/autopull.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
    echo "$1"
}

cd "$REPO_DIR"

# Check for updates
log "Checking for updates..."
git fetch origin main

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u})

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date."
    exit 0
fi

log "Updates found, pulling..."
git pull origin main

log "Restarting services..."
sudo systemctl restart artifact || log "Warning: Failed to restart artifact"
sudo systemctl restart arcade-bot || log "Warning: Failed to restart arcade-bot"

log "Auto-pull complete!"

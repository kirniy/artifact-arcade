#!/bin/bash
# Auto-pull from git and restart services
# This script is run by arcade-autopull.service or a cron job/timer

set -e

REPO_DIR="/home/kirniy/modular-arcade"
LOG_FILE="/home/kirniy/modular-arcade/logs/autopull.log"
SINGBOX_CONFIG="/etc/sing-box/config.json"
VPN_PORT_FILE="$REPO_DIR/configs/vpn/port"

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

# Update sing-box VPN config if a new config exists in repo
REPO_VPN_CONFIG="$REPO_DIR/configs/vpn/sing-box-active.json"
SINGBOX_BACKUP_DIR="$REPO_DIR/configs/vpn/backups"

if [ -f "$REPO_VPN_CONFIG" ]; then
    # Check if config actually changed
    if ! diff -q "$REPO_VPN_CONFIG" "$SINGBOX_CONFIG" &>/dev/null 2>&1; then
        log "New VPN config detected, updating sing-box..."
        # Backup current config
        mkdir -p "$SINGBOX_BACKUP_DIR"
        BACKUP_NAME="sing-box-backup-$(date '+%Y%m%d-%H%M%S').json"
        sudo cp "$SINGBOX_CONFIG" "$SINGBOX_BACKUP_DIR/$BACKUP_NAME" 2>/dev/null || true
        log "Backed up old config to $SINGBOX_BACKUP_DIR/$BACKUP_NAME"
        # Install new config
        sudo cp "$REPO_VPN_CONFIG" "$SINGBOX_CONFIG"
        log "VPN config replaced, restarting sing-box..."
        sudo systemctl restart sing-box || log "Warning: Failed to restart sing-box"
    fi
elif [ -f "$VPN_PORT_FILE" ] && [ -f "$SINGBOX_CONFIG" ]; then
    # Legacy: update port only
    NEW_PORT=$(cat "$VPN_PORT_FILE" | tr -d '[:space:]')
    if [ -n "$NEW_PORT" ]; then
        log "Updating sing-box port to $NEW_PORT..."
        if command -v jq &> /dev/null; then
            sudo jq --argjson port "$NEW_PORT" \
                '(.outbounds[] | select(.type == "vless" or .server != null) | .server_port) = $port' \
                "$SINGBOX_CONFIG" > /tmp/singbox_new.json && \
                sudo mv /tmp/singbox_new.json "$SINGBOX_CONFIG"
            log "VPN port updated, restarting sing-box..."
            sudo systemctl restart sing-box || log "Warning: Failed to restart sing-box"
        else
            log "Warning: jq not installed, cannot update VPN port"
        fi
    fi
fi

log "Restarting services..."
sudo systemctl restart artifact || log "Warning: Failed to restart artifact"
sudo systemctl restart arcade-bot || log "Warning: Failed to restart arcade-bot"

log "Auto-pull complete!"

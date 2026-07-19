#!/bin/bash
# Auto-pull from git and restart services when the booth is idle.
# This script is run by arcade-autopull.service or a cron job/timer

set -euo pipefail

REPO_DIR="/home/kirniy/modular-arcade"
LOG_FILE="/home/kirniy/modular-arcade/logs/autopull.log"
PENDING_FILE="/home/kirniy/modular-arcade/.deploy/restart-pending"
AUTO_ACTIVATE_JARA="${ARTIFACT_AUTO_ACTIVATE_JARA:-1}"
AUTO_ACTIVATE_WORLD_CUP_FINAL="${ARTIFACT_AUTO_ACTIVATE_WORLD_CUP_FINAL:-1}"
RECOVERY_TUNNEL_ENABLED="${ARTIFACT_RECOVERY_TUNNEL_ENABLED:-1}"
RECOVERY_TUNNEL_HOST="${ARTIFACT_RECOVERY_TUNNEL_HOST:-root@82.38.148.239}"
RECOVERY_TUNNEL_PORT="${ARTIFACT_RECOVERY_TUNNEL_PORT:-22091}"
RECOVERY_TUNNEL_KEY="${ARTIFACT_RECOVERY_TUNNEL_KEY:-/home/kirniy/.ssh/frankfurt2_macmini}"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG_FILE"
    echo "$1"
}

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$PENDING_FILE")"
cd "$REPO_DIR"

ensure_recovery_tunnel() {
    if [ "$RECOVERY_TUNNEL_ENABLED" != "1" ] || [ ! -f "$RECOVERY_TUNNEL_KEY" ]; then
        return 0
    fi

    tunnel_spec="127.0.0.1:${RECOVERY_TUNNEL_PORT}:127.0.0.1:22"
    if pgrep -u "$(id -u)" -f -- "$tunnel_spec" >/dev/null 2>&1; then
        return 0
    fi

    log "Opening localhost-only recovery SSH tunnel on Frankfurt2 port ${RECOVERY_TUNNEL_PORT}..."
    ssh \
        -i "$RECOVERY_TUNNEL_KEY" \
        -o BatchMode=yes \
        -o IdentitiesOnly=yes \
        -o StrictHostKeyChecking=accept-new \
        -o ExitOnForwardFailure=yes \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -fNT \
        -R "$tunnel_spec" \
        "$RECOVERY_TUNNEL_HOST" || log "Recovery SSH tunnel could not be opened yet."
}

# Tailscale is not the only route into a powered-on booth. Keep a loopback-only
# reverse SSH forward on Frankfurt2 so operators can repair overlay networking.
ensure_recovery_tunnel

env_has_jara() {
    [ -f "$REPO_DIR/.env" ] &&
        grep -Eq '^PHOTOBOOTH_THEME=jara$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_MENU_MODES=jara$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_AI_ENABLED=true$' "$REPO_DIR/.env" &&
        grep -Eq '^GEMINI_IMAGE_MODEL=gemini-3\.1-flash-lite-image$' "$REPO_DIR/.env"
}

env_has_world_cup_final() {
    [ -f "$REPO_DIR/.env" ] &&
        grep -Eq '^PHOTOBOOTH_THEME=world-cup-final$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_MENU_MODES=world_cup_final$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_AI_ENABLED=true$' "$REPO_DIR/.env" &&
        grep -Eq '^GEMINI_IMAGE_MODEL=gemini-3\.1-flash-lite-image$' "$REPO_DIR/.env"
}

world_cup_final_window_active() {
    # Sunday club night continues until noon Monday, matching the booth's
    # party-date rollover convention.
    moscow_stamp="$(TZ=Europe/Moscow date '+%Y%m%d%H%M')"
    [ "$moscow_stamp" -ge 202607190000 ] && [ "$moscow_stamp" -lt 202607201200 ]
}

ensure_world_cup_final_activation() {
    if [ "$AUTO_ACTIVATE_WORLD_CUP_FINAL" != "1" ] || ! world_cup_final_window_active; then
        return 1
    fi
    if env_has_world_cup_final; then
        return 1
    fi
    if [ ! -x "$REPO_DIR/scripts/activate-world-cup-final-photobooth.sh" ]; then
        log "World Cup final activation script is not present yet."
        return 1
    fi

    log "Включаем тему фотобудки «Чемпионат мира 2026» на воскресную ночь..."
    ARTIFACT_REMOTE_DIR="$REPO_DIR" "$REPO_DIR/scripts/activate-world-cup-final-photobooth.sh"
    return 0
}

ensure_jara_activation() {
    if [ "$AUTO_ACTIVATE_JARA" != "1" ]; then
        return 1
    fi
    if env_has_jara; then
        return 1
    fi
    if [ ! -x "$REPO_DIR/scripts/activate-jara-photobooth.sh" ]; then
        log "ЖАРА activation script is not present yet."
        return 1
    fi

    log "Activating ЖАРА photobooth env..."
    ARTIFACT_REMOTE_DIR="$REPO_DIR" "$REPO_DIR/scripts/activate-jara-photobooth.sh"
    return 0
}

ensure_event_activation() {
    if world_cup_final_window_active; then
        ensure_world_cup_final_activation
        return $?
    fi
    ensure_jara_activation
}

# Check for updates
log "Checking for updates..."
git fetch origin main

LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    log "Already up to date."
    activation_changed=0
    if ensure_event_activation; then
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

ensure_event_activation || true

log "Trying idle-gated restart..."
ARTIFACT_RESTART_PENDING_FILE="$PENDING_FILE" \
    ARTIFACT_MARK_RESTART_PENDING=1 \
    "$REPO_DIR/scripts/restart-artifact-if-idle.sh" || true

log "Auto-pull complete!"

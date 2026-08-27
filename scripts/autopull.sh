#!/bin/bash
# Auto-pull from git and restart services when the booth is idle.
# This script is run by arcade-autopull.service or a cron job/timer

set -euo pipefail

REPO_DIR="/home/kirniy/modular-arcade"
LOG_FILE="/home/kirniy/modular-arcade/logs/autopull.log"
PENDING_FILE="/home/kirniy/modular-arcade/.deploy/restart-pending"
AUTO_ACTIVATE_BOILINGROOM="${ARTIFACT_AUTO_ACTIVATE_BOILINGROOM:-1}"
# Theme activation is explicit. A historical event must never silently replace
# the currently selected weekend theme on a routine auto-pull.
AUTO_ACTIVATE_SUNSET_PALMS="${ARTIFACT_AUTO_ACTIVATE_SUNSET_PALMS:-0}"
AUTO_ACTIVATE_JARA="${ARTIFACT_AUTO_ACTIVATE_JARA:-0}"
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

env_has_boilingroom() {
    [ -f "$REPO_DIR/.env" ] &&
        grep -Eq '^PHOTOBOOTH_THEME=boilingroom$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_MENU_MODES=boilingroom$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_AI_ENABLED=true$' "$REPO_DIR/.env" &&
        grep -Eq '^GEMINI_IMAGE_MODEL=gemini-3\.1-flash-lite-image$' "$REPO_DIR/.env"
}

env_has_sunset_palms() {
    [ -f "$REPO_DIR/.env" ] &&
        grep -Eq '^PHOTOBOOTH_THEME=sunset-palms$' "$REPO_DIR/.env" &&
        grep -Eq '^PHOTOBOOTH_MENU_MODES=sunset-palms$' "$REPO_DIR/.env" &&
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

boilingroom_weekend_window_active() {
    # Friday setup through Monday noon, Moscow time. Outside this one event
    # window the auto-updater never forces Boiling Room.
    moscow_stamp="$(TZ=Europe/Moscow date '+%Y%m%d%H%M')"
    [ "$moscow_stamp" -ge 202607311200 ] && [ "$moscow_stamp" -lt 202608031200 ]
}

ensure_boilingroom_activation() {
    if [ "$AUTO_ACTIVATE_BOILINGROOM" != "1" ] || ! boilingroom_weekend_window_active; then
        return 1
    fi
    if env_has_boilingroom; then
        return 1
    fi
    if [ ! -x "$REPO_DIR/scripts/activate-boilingroom-photobooth.sh" ]; then
        log "Boiling Room activation script is not present yet."
        return 1
    fi

    log "Activating Boiling Room for the current weekend..."
    ARTIFACT_REMOTE_DIR="$REPO_DIR" "$REPO_DIR/scripts/activate-boilingroom-photobooth.sh"
    return 0
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

ensure_sunset_palms_activation() {
    if [ "$AUTO_ACTIVATE_SUNSET_PALMS" != "1" ]; then
        return 1
    fi
    if env_has_sunset_palms; then
        return 1
    fi
    if [ ! -x "$REPO_DIR/scripts/activate-sunset-palms-photobooth.sh" ]; then
        log "Sunset Palms activation script is not present yet."
        return 1
    fi

    log "Activating Sunset Palms photobooth env..."
    ARTIFACT_REMOTE_DIR="$REPO_DIR" "$REPO_DIR/scripts/activate-sunset-palms-photobooth.sh"
    return 0
}

ensure_event_activation() {
    weekly_output="$(ARTIFACT_REMOTE_DIR="$REPO_DIR" \
        "$REPO_DIR/scripts/sync-weekly-photobooth-theme.sh")"
    while IFS= read -r line; do
        [ -n "$line" ] && log "Weekly theme schedule: $line"
    done <<<"$weekly_output"
    if grep -q '^THEME_CHANGED=1$' <<<"$weekly_output"; then
        return 0
    fi
    if grep -q '^THEME_SCHEDULE=disabled$' <<<"$weekly_output"; then
        # A deliberate manual override owns theme selection while disabled.
        return 1
    fi

    if world_cup_final_window_active; then
        ensure_world_cup_final_activation
        return $?
    fi
    if boilingroom_weekend_window_active; then
        ensure_boilingroom_activation
        return $?
    fi
    if ensure_sunset_palms_activation; then
        return 0
    fi
    ensure_jara_activation
}

# The booth runs on a machine-local branch. Its intentional asset-footprint
# commit may differ from GitHub, but deployed code must remain clean and
# canonical. Refuse to trample an unexpected on-site edit or an untracked path
# that a release is about to add; an operator can then reconcile it explicitly.
runtime_tree_is_safe_to_merge() {
    local remote_ref="$1"
    local collision=0
    local path

    if ! git diff --quiet --ignore-submodules -- ||
        ! git diff --cached --quiet --ignore-submodules --; then
        log "Update deferred: tracked on-site changes are not in the runtime branch."
        return 1
    fi

    while IFS= read -r -d '' path; do
        if git cat-file -e "${remote_ref}:${path}" 2>/dev/null; then
            log "Update deferred: upstream path collides with local untracked file: $path"
            collision=1
        fi
    done < <(git ls-files --others --exclude-standard -z)

    [ "$collision" = "0" ]
}

merge_remote_release() {
    local remote_ref="$1"
    local before_merge

    if git merge-base --is-ancestor "$remote_ref" HEAD; then
        return 1
    fi

    runtime_tree_is_safe_to_merge "$remote_ref"
    before_merge="$(git rev-parse HEAD)"
    log "Merging release $(git rev-parse --short "$remote_ref") into runtime branch..."
    if ! git \
        -c user.name="VNVNC PHOTOBOOTH Autopuller" \
        -c user.email="photobooth-autopull@localhost" \
        merge --no-edit --no-ff -X ours "$remote_ref"; then
        log "Release merge failed; restoring the clean runtime checkpoint."
        git merge --abort >/dev/null 2>&1 || true
        # merge --abort restores the exact pre-merge index and worktree. Keep
        # the explicit revision in the log for a deterministic recovery audit.
        log "Runtime checkpoint remains at $(git rev-parse --short "$before_merge")."
        return 1
    fi
    return 0
}

# Check for updates
log "Checking for updates..."
git fetch origin main

REMOTE=$(git rev-parse origin/main)

if git merge-base --is-ancestor "$REMOTE" HEAD; then
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

log "Updates found."
merge_remote_release origin/main

ensure_event_activation || true

log "Trying idle-gated restart..."
ARTIFACT_RESTART_PENDING_FILE="$PENDING_FILE" \
    ARTIFACT_MARK_RESTART_PENDING=1 \
    "$REPO_DIR/scripts/restart-artifact-if-idle.sh" || true

log "Auto-pull complete!"

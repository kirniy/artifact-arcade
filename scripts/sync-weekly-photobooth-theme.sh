#!/bin/bash
# Keep the recurring Moscow club-week theme schedule in sync.
#
# One-off VNVNC B'DAY window: Thursday 2026-08-27 23:00 through Sunday
# 2026-08-30 06:59, covering today's ВСЕ СВОИ plus Friday and Saturday.
# Historical 2K17 window: Friday 2026-08-14 23:00 through Sunday
# 2026-08-16 06:59.
# Recurring ВСЕ СВОИ enforcement: every Thursday and Sunday outside event windows.
# Other weekdays retain the current theme so one-off events can be selected.
#
# Set ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED=0 in .env to pause automatic
# switching for a one-off manual theme.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
ENV_FILE="${ARTIFACT_ENV_FILE:-${REPO_DIR}/.env}"
DRY_RUN=0
AT=""

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) DRY_RUN=1 ;;
        --at)
            shift
            [ "$#" -gt 0 ] || { echo "--at requires YYYYMMDDHHMM" >&2; exit 2; }
            AT="$1"
            ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--at YYYYMMDDHHMM]"
            exit 0
            ;;
        *) echo "Unknown option: $1" >&2; exit 2 ;;
    esac
    shift
done

read_env_value() {
    local key="$1"
    [ -f "${ENV_FILE}" ] || return 0
    sed -n "s/^${key}=//p" "${ENV_FILE}" | tail -1
}

enabled="${ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED:-}"
if [ -z "${enabled}" ]; then
    enabled="$(read_env_value ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED)"
fi
enabled="${enabled:-1}"
if [ "${enabled}" != "1" ] && [ "${enabled}" != "true" ]; then
    echo "THEME_CHANGED=0"
    echo "THEME_SCHEDULE=disabled"
    exit 0
fi

if [ -n "${AT}" ]; then
    case "${AT}" in
        20[0-9][0-9][01][0-9][0-3][0-9][0-2][0-9][0-5][0-9]) ;;
        *) echo "Invalid --at value: ${AT}" >&2; exit 2 ;;
    esac
    stamp="${AT}"
    dow="$(TZ=Europe/Moscow date -j -f '%Y%m%d%H%M' "${AT}" +%u 2>/dev/null || \
        TZ=Europe/Moscow date -d "${AT:0:4}-${AT:4:2}-${AT:6:2} ${AT:8:2}:${AT:10:2}" +%u)"
else
    stamp="$(TZ=Europe/Moscow date +%Y%m%d%H%M)"
    dow="$(TZ=Europe/Moscow date +%u)"
fi

target_theme=""
target_menu=""
activation_script=""
if [ "${stamp}" -ge 202608272300 ] && [ "${stamp}" -lt 202608300700 ]; then
    target_theme="vnvnc-bday"
    target_menu="classic"
    activation_script="activate-vnvnc-bday-photobooth.sh"
elif [ "${stamp}" -ge 202608142300 ] && [ "${stamp}" -lt 202608160700 ]; then
    target_theme="2k17"
    target_menu="2k17"
    activation_script="activate-2k17-photobooth.sh"
elif [ "${dow}" -eq 4 ] || [ "${dow}" -eq 7 ]; then
    target_theme="vse-svoi"
    target_menu="vse_svoi"
    activation_script="activate-vse-svoi-photobooth.sh"
else
    echo "THEME_TARGET=unchanged"
    echo "THEME_CHANGED=0"
    exit 0
fi

current_theme="$(read_env_value PHOTOBOOTH_THEME)"
current_menu="$(read_env_value PHOTOBOOTH_MENU_MODES)"
echo "THEME_TARGET=${target_theme}"

if [ "${current_theme}" = "${target_theme}" ] && [ "${current_menu}" = "${target_menu}" ]; then
    echo "THEME_CHANGED=0"
    exit 0
fi

if [ "${DRY_RUN}" = "1" ]; then
    echo "THEME_CHANGED=1"
    exit 0
fi

script_path="${REPO_DIR}/scripts/${activation_script}"
[ -x "${script_path}" ] || { echo "Missing activation script: ${script_path}" >&2; exit 1; }
ARTIFACT_REMOTE_DIR="${REPO_DIR}" ARTIFACT_ENV_FILE="${ENV_FILE}" "${script_path}"
echo "THEME_CHANGED=1"

#!/bin/bash
# Keep the recurring Moscow club-week theme schedule in sync.
#
# ВСЕ СВОИ: Sunday 07:00 through Thursday 22:59.
# 2K17:     Thursday 23:00 through Sunday 06:59.
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
            [ "$#" -gt 0 ] || { echo "--at requires DOW:HHMM" >&2; exit 2; }
            AT="$1"
            ;;
        -h|--help)
            echo "Usage: $0 [--dry-run] [--at DOW:HHMM]"
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
        [1-7]:[0-2][0-9][0-5][0-9]) ;;
        *) echo "Invalid --at value: ${AT}" >&2; exit 2 ;;
    esac
    dow="${AT%%:*}"
    hhmm="${AT#*:}"
else
    dow="$(TZ=Europe/Moscow date +%u)"
    hhmm="$(TZ=Europe/Moscow date +%H%M)"
fi

target_theme="vse-svoi"
target_menu="vse_svoi"
activation_script="activate-vse-svoi-photobooth.sh"
if { [ "${dow}" -eq 4 ] && [ "${hhmm}" -ge 2300 ]; } || \
   [ "${dow}" -eq 5 ] || \
   [ "${dow}" -eq 6 ] || \
   { [ "${dow}" -eq 7 ] && [ "${hhmm}" -lt 0700 ]; }; then
    target_theme="2k17"
    target_menu="2k17"
    activation_script="activate-2k17-photobooth.sh"
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

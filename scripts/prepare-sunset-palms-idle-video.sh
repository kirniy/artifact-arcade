#!/bin/bash
# Adapt the QA-approved Sunset Palms fan master to the ARTIFACT 128x128 idle contract.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT_PATH="${SUNSET_PALMS_IDLE_VIDEO_PATH:-${REPO_DIR}/assets/idle/sunset_palms/video/sunset-palms-fans.mp4}"

validate_video() {
    local target="$1"
    if [ ! -s "${target}" ]; then
        echo "Missing required Sunset Palms idle video: ${target}" >&2
        return 1
    fi

    local video_data audio_count codec width height pix_fmt fps
    video_data="$(ffprobe -v error -select_streams v:0 \
        -show_entries stream=codec_name,width,height,pix_fmt,avg_frame_rate \
        -of default=noprint_wrappers=1:nokey=1 "${target}")"
    codec="$(printf '%s\n' "${video_data}" | sed -n '1p')"
    width="$(printf '%s\n' "${video_data}" | sed -n '2p')"
    height="$(printf '%s\n' "${video_data}" | sed -n '3p')"
    pix_fmt="$(printf '%s\n' "${video_data}" | sed -n '4p')"
    fps="$(printf '%s\n' "${video_data}" | sed -n '5p')"
    audio_count="$(ffprobe -v error -select_streams a -show_entries stream=index \
        -of csv=p=0 "${target}" | sed '/^$/d' | wc -l | tr -d ' ')"

    if [ "${codec}" != "h264" ] || [ "${width}" != "128" ] || \
       [ "${height}" != "128" ] || [ "${pix_fmt}" != "yuv420p" ] || \
       [ "${fps}" != "24/1" ] || [ "${audio_count}" != "0" ]; then
        echo "Invalid Sunset Palms idle video contract: codec=${codec} size=${width}x${height} pix_fmt=${pix_fmt} fps=${fps} audio_streams=${audio_count}" >&2
        return 1
    fi

    echo "Sunset Palms idle video valid: ${target} (H.264 128x128 yuv420p 24fps silent)"
}

if [ "${1:-}" = "--check" ]; then
    validate_video "${OUTPUT_PATH}"
    exit 0
fi

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 /absolute/path/to/qa-approved-sunset-palms-fan-master.mp4" >&2
    echo "       $0 --check" >&2
    exit 2
fi

SOURCE_PATH="$1"
if [ ! -s "${SOURCE_PATH}" ]; then
    echo "Accepted fan master not found: ${SOURCE_PATH}" >&2
    exit 1
fi

SOURCE_DURATION="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "${SOURCE_PATH}")"
FADE_START="$(awk -v duration="${SOURCE_DURATION}" 'BEGIN {
    start = duration - 0.6
    if (start < 0) start = 0
    printf "%.3f", start
}')"

mkdir -p "$(dirname "${OUTPUT_PATH}")"
TEMP_PATH="${OUTPUT_PATH}.tmp.mp4"
trap 'rm -f "${TEMP_PATH}"' EXIT

ffmpeg -hide_banner -loglevel warning -y -i "${SOURCE_PATH}" \
    -vf "scale=128:128:force_original_aspect_ratio=increase,crop=128:128,setsar=1,fps=24,fade=t=out:st=${FADE_START}:d=0.6,format=yuv420p" \
    -an -c:v libx264 -profile:v high -level 3.1 -preset slow -crf 17 \
    -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart \
    "${TEMP_PATH}"

validate_video "${TEMP_PATH}"
mv -f "${TEMP_PATH}" "${OUTPUT_PATH}"
trap - EXIT
echo "Installed accepted Sunset Palms idle video: ${OUTPUT_PATH}"

#!/bin/bash
# Adapt the approved dance clip to the 128x128 silent idle-video contract.

set -euo pipefail

REPO_DIR="${ARTIFACT_REMOTE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT_PATH="${SPIDERVERSE_IDLE_VIDEO_PATH:-${REPO_DIR}/assets/idle/spiderverse/video/spiderverse-emo-dance.mp4}"

validate_video() {
    local target="$1"
    if [ ! -s "${target}" ]; then
        echo "Missing required SPIDERVERSE idle video: ${target}" >&2
        return 1
    fi
    local video_data audio_count codec width height pix_fmt fps
    video_data="$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,pix_fmt,avg_frame_rate -of default=noprint_wrappers=1:nokey=1 "${target}")"
    codec="$(printf '%s\n' "${video_data}" | sed -n '1p')"
    width="$(printf '%s\n' "${video_data}" | sed -n '2p')"
    height="$(printf '%s\n' "${video_data}" | sed -n '3p')"
    pix_fmt="$(printf '%s\n' "${video_data}" | sed -n '4p')"
    fps="$(printf '%s\n' "${video_data}" | sed -n '5p')"
    audio_count="$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "${target}" | sed '/^$/d' | wc -l | tr -d ' ')"
    if [ "${codec}" != "h264" ] || [ "${width}" != "128" ] || [ "${height}" != "128" ] || [ "${pix_fmt}" != "yuv420p" ] || [ "${fps}" != "24/1" ] || [ "${audio_count}" != "0" ]; then
        echo "Invalid SPIDERVERSE idle video: codec=${codec} size=${width}x${height} pix_fmt=${pix_fmt} fps=${fps} audio=${audio_count}" >&2
        return 1
    fi
    echo "SPIDERVERSE idle video valid: ${target} (H.264 128x128 yuv420p 24fps silent)"
}

if [ "${1:-}" = "--check" ]; then
    validate_video "${OUTPUT_PATH}"
    exit 0
fi
if [ "$#" -ne 1 ] || [ ! -s "$1" ]; then
    echo "Usage: $0 /absolute/path/to/dance-master.mp4" >&2
    echo "       $0 --check" >&2
    exit 2
fi

mkdir -p "$(dirname "${OUTPUT_PATH}")"
TEMP_PATH="${OUTPUT_PATH}.tmp.mp4"
trap 'rm -f "${TEMP_PATH}"' EXIT

# The source action is centered throughout. Crop the 16:9 master to its center
# square before downsampling, keep the original duration, and omit audio so idle
# playback starts quickly and cannot contend with the GPIO ticker PWM.
ffmpeg -hide_banner -loglevel warning -y -i "$1" -map 0:v:0 \
    -vf "crop=ih:ih:(iw-ih)/2:0,scale=128:128:flags=lanczos,setsar=1,fps=24,format=yuv420p" \
    -an -c:v libx264 -profile:v high -level 3.1 -preset slow -crf 17 \
    -g 48 -keyint_min 48 -sc_threshold 0 -movflags +faststart "${TEMP_PATH}"

validate_video "${TEMP_PATH}"
mv -f "${TEMP_PATH}" "${OUTPUT_PATH}"
trap - EXIT
echo "Installed SPIDERVERSE idle video: ${OUTPUT_PATH}"

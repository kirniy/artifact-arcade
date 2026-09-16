#!/bin/bash
# Ten complete repeats of the user-approved fan export; no added artwork or fades.
set -euo pipefail
REPO_DIR="${ARTIFACT_REMOTE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
OUTPUT="${TROPICAL_THAI_IDLE_VIDEO_PATH:-${REPO_DIR}/assets/idle/tropical_thai/video/tropical-thai-fans-10x.mp4}"
check() {
  python3 - "$1" <<'PY'
import json, subprocess, sys
p=sys.argv[1]
d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',p]))
v=d['streams'][0]
assert len(d['streams']) == 1, 'Idle video must be silent'
assert (v['codec_name'],v['width'],v['height'],v['pix_fmt'],v['avg_frame_rate']) == ('h264',128,128,'yuv420p','24/1'), 'Invalid idle video format'
assert abs(float(d['format']['duration']) - 150.56708) < 0.1, 'Expected ten complete approved fan repeats'
subprocess.run(['ffmpeg','-v','error','-xerror','-i',p,'-f','null','-'],check=True)
print('Tropical Thai idle video validated: ten repeats, H.264 128x128, 24 fps, silent')
PY
}
if [[ "${1:-}" == --check ]]; then check "$OUTPUT"; exit; fi
[[ $# == 1 && -s "$1" ]] || { echo "Usage: $0 APPROVED_FAN.mp4 | --check" >&2; exit 2; }
# Do not silently use an older delivery with a similar filename.
python3 - "$1" <<'PY'
import hashlib,sys
from pathlib import Path
expected='5d1747dd9d0a87210d7dd164965532734d7c22be783acbb70c845a8339e68e30'
assert hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest()==expected, 'Source is not the approved final fan export'
PY
mkdir -p "$(dirname "$OUTPUT")"
TEMP="${OUTPUT}.tmp.mp4"
trap 'rm -f "$TEMP"' EXIT
ffmpeg -v error -y -stream_loop 9 -i "$1" \
  -vf 'scale=128:128:force_original_aspect_ratio=increase,crop=128:128,setsar=1,fps=24,format=yuv420p' \
  -an -c:v libx264 -preset slow -crf 17 -g 48 -movflags +faststart "$TEMP"
check "$TEMP"
mv "$TEMP" "$OUTPUT"

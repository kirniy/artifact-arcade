#!/bin/bash
# Validate the new NIGHT RIDERS theme before changing the booth's environment.
set -euo pipefail
REPO_DIR="${ARTIFACT_REMOTE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
ENV_FILE="${ARTIFACT_ENV_FILE:-${REPO_DIR}/.env}"
[[ $# == 0 || ( $# == 1 && "$1" == --restart ) ]] || { echo 'Usage: activate-night-riders-photobooth.sh [--restart]' >&2; exit 2; }
cd "$REPO_DIR"
PYTHON_BIN="${VNVNC_PYTHON:-${REPO_DIR}/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN=python3
PYTHONPATH=src "$PYTHON_BIN" - "$ENV_FILE" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import py_compile
import subprocess
import sys
import tempfile

from artifact.ai.caricature import CaricatureStyle
from artifact.modes.photobooth import PHOTOBOOTH_MENU_REGISTRY
from artifact.modes.photobooth_themes import THEMES

root = Path.cwd()
theme = THEMES['night-riders']
emblem = root / 'assets/images' / theme.logo_filename
assert hashlib.sha256(emblem.read_bytes()).hexdigest() == theme.required_reference_sha256, 'Wrong NIGHT RIDERS emblem'
assert PHOTOBOOTH_MENU_REGISTRY['night_riders'] == 'night-riders'
assert CaricatureStyle.PHOTOBOOTH_NIGHT_RIDERS.value == 'photobooth_night_riders'
video = root / 'assets/idle/night_riders/video' / theme.idle_video_filename
probe = json.loads(subprocess.check_output([
    'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)
]))
streams = probe['streams']
assert len(streams) == 1 and streams[0]['codec_name'] == 'h264', 'Idle must be silent H.264'
assert (streams[0]['width'], streams[0]['height'], streams[0]['pix_fmt']) == (128, 128, 'yuv420p')
assert streams[0]['avg_frame_rate'] == '24/1'
assert float(probe['format']['duration']) > 119, 'Idle fan video was truncated'
subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(video), '-f', 'null', '-'], check=True)
with tempfile.TemporaryDirectory(prefix='night_riders-compile-') as cache:
    for index, name in enumerate(['ai/night_riders.py', 'ai/caricature.py', 'modes/photobooth.py', 'modes/photobooth_themes.py', 'animation/idle_scenes.py']):
        py_compile.compile(str(root / 'src/artifact' / name), cfile=str(Path(cache) / f'{index}.pyc'), doraise=True)

env = Path(sys.argv[1])
lines = env.read_text().splitlines()
updates = {
    'PHOTOBOOTH_THEME': 'night-riders',
    'PHOTOBOOTH_MENU_MODES': 'night-riders',
    'PHOTOBOOTH_AI_ENABLED': 'true',
    'PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED': 'true',
    'PHOTOBOOTH_CAMERA_SELECTOR_ENABLED': 'auto',
    'PHOTOBOOTH_PRINT_FORTUNES': 'false',
    'ARTIFACT_CLUB_THEME_SCHEDULE': 'ticketscloud',
    'PHOTOBOOTH_DEFAULT_THEME': 'night-riders',
    'ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED': '1',
}
new_lines = [line for line in lines if line.partition('=')[0].strip() not in updates]
new_lines.extend(f'{key}={value}' for key, value in updates.items())
new_text = '\n'.join(new_lines) + '\n'
if env.read_text() == new_text:
    print('NIGHT RIDERS configuration already current')
else:
    backup = env.with_name(env.name + '.before-night_riders')
    if not backup.exists():
        backup.write_bytes(env.read_bytes())
        os.chmod(backup, env.stat().st_mode & 0o777)
    fd, tmp = tempfile.mkstemp(prefix='.env-night_riders-', dir=env.parent)
    try:
        os.fchmod(fd, env.stat().st_mode & 0o777)
        with os.fdopen(fd, 'w') as out:
            out.write(new_text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, env)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    print(f'NIGHT RIDERS configured; backup: {backup}')
PY
if [[ "${1:-}" == --restart ]]; then
  ARTIFACT_RESTART_SERVICES=artifact ARTIFACT_MARK_RESTART_PENDING=1 "$REPO_DIR/scripts/restart-artifact-if-idle.sh"
fi

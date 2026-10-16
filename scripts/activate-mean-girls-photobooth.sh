#!/bin/bash
# Preserve camera/provider settings; switch branding and retire the hidden quest.
set -euo pipefail
REPO_DIR="${ARTIFACT_REMOTE_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
ENV_FILE="${ARTIFACT_ENV_FILE:-${REPO_DIR}/.env}"
[[ $# == 0 || ( $# == 1 && "$1" == --restart ) ]] || { echo 'Usage: activate-mean-girls-photobooth.sh [--restart]' >&2; exit 2; }
cd "$REPO_DIR"
PYTHON_BIN="${VNVNC_PYTHON:-${REPO_DIR}/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN=python3
PYTHONPATH=src "$PYTHON_BIN" - "$ENV_FILE" <<'PY'
import hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from PIL import ImageFont
from artifact.modes.photobooth import PHOTOBOOTH_MENU_REGISTRY
from artifact.modes.photobooth_themes import THEMES
root = Path.cwd()
theme = THEMES['mean-girls']
manifest=json.loads((root/'assets/idle/mean_girls/manifest.json').read_text())
for filename,digest in manifest['files'].items():
    assert hashlib.sha256((root/filename).read_bytes()).hexdigest()==digest, f'MEAN GIRLS asset changed: {filename}'
assert PHOTOBOOTH_MENU_REGISTRY['mean_girls'] == theme.id
emblem = root / 'assets/images' / theme.logo_filename
assert hashlib.sha256(emblem.read_bytes()).hexdigest() == theme.required_reference_sha256
video = root / 'assets/idle/mean_girls/video' / theme.idle_video_filename
probe = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
assert len(probe['streams']) == 1
s=probe['streams'][0]
assert (s['width'],s['height'],s['codec_name'],s['pix_fmt'],s['avg_frame_rate']) == (128,128,'h264','yuv420p','24000/1001')
assert abs(float(probe['format']['duration']) - 15.056708) < .1
subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(video),'-f','null','-'],check=True)
for name in ('Anton.ttf','Unbounded.ttf'):
    ImageFont.truetype(str(root/'assets/fonts/mean-girls'/name),24)
env=Path(sys.argv[1])
text=env.read_text()
updates={
    'PHOTOBOOTH_THEME':'mean-girls',
    'PHOTOBOOTH_MENU_MODES':'mean_girls',
    'PHOTOBOOTH_DEFAULT_THEME':'mean-girls',
    'PHOTOBOOTH_PRINT_FORTUNES':'false',
    'ARTIFACT_SPIDERVERSE_QUEST_ENABLED':'false',
    'ARTIFACT_LEGACY_QUEST_PRINT_ENABLED':'false',
    'ARTIFACT_CLUB_THEME_SCHEDULE':'ticketscloud',
    'ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED':'1',
}
lines=[line for line in text.splitlines() if line.partition('=')[0].strip() not in updates]
lines.extend(f'{k}={v}' for k,v in updates.items())
new='\n'.join(lines)+'\n'
if new==text:
    print('MEAN GIRLS already configured; no changes')
    sys.exit(0)
backup=env.with_name(env.name+'.before-mean-girls-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
# Never log environment content: backups retain the original private permissions.
with backup.open('xb') as out:
    os.chmod(backup,env.stat().st_mode & 0o777)
    out.write(text.encode())
fd,tmp=tempfile.mkstemp(prefix='.env-mean-girls-',dir=env.parent)
try:
    os.fchmod(fd,env.stat().st_mode & 0o777)
    with os.fdopen(fd,'w') as out:
        out.write(new);out.flush();os.fsync(out.fileno())
    os.replace(tmp,env)
finally:
    if os.path.exists(tmp):os.unlink(tmp)
print(f'MEAN GIRLS configured; backup: {backup}')
PY
if [[ "${1:-}" == --restart ]]; then
  ARTIFACT_RESTART_SERVICES=artifact ARTIFACT_MARK_RESTART_PENDING=1 "$REPO_DIR/scripts/restart-artifact-if-idle.sh"
fi

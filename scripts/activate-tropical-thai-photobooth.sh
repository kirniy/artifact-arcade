#!/bin/bash
# Validate the complete theme before atomically changing booth configuration.
set -euo pipefail
REPO_DIR="${ARTIFACT_REMOTE_DIR:-/home/kirniy/modular-arcade}"
ENV_FILE="${ARTIFACT_ENV_FILE:-${REPO_DIR}/.env}"
[[ $# == 0 || ( $# == 1 && "$1" == --restart ) ]] || { echo 'Usage: activate-tropical-thai-photobooth.sh [--restart]' >&2; exit 2; }
cd "$REPO_DIR"
"$REPO_DIR/scripts/prepare-tropical-thai-idle-video.sh" --check
PYTHON_BIN="${VNVNC_PYTHON:-${REPO_DIR}/.venv/bin/python}"
[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN=python3
PYTHONPATH=src "$PYTHON_BIN" - "$ENV_FILE" <<'PY'
import hashlib, os, pathlib, py_compile, sys, tempfile
from artifact.modes.photobooth_themes import THEMES
from artifact.ai.caricature import CaricatureStyle
from artifact.modes.photobooth import PHOTOBOOTH_MENU_REGISTRY
from artifact.ai.tropical_thai import build_prompt
root=pathlib.Path.cwd()
theme=THEMES['tropical-thai']
assert hashlib.sha256((root/'assets/images'/theme.logo_filename).read_bytes()).hexdigest()==theme.required_reference_sha256
assert CaricatureStyle.PHOTOBOOTH_TROPICAL_THAI.value == 'photobooth_tropical_thai'
assert 'tropical_thai' in PHOTOBOOTH_MENU_REGISTRY
# The running hardware service owns its existing pycache as root. Preflight must
# not write there when an operator activates the theme as kirniy.
with tempfile.TemporaryDirectory(prefix='tropical-thai-compile-') as cache:
 for index,name in enumerate(['ai/caricature.py','ai/tropical_thai.py','modes/photobooth.py','modes/photobooth_themes.py','animation/idle_scenes.py']):
  py_compile.compile(str(root/'src/artifact'/name),cfile=str(pathlib.Path(cache)/f'{index}.pyc'),doraise=True)
p=pathlib.Path(sys.argv[1])
updates={
 'PHOTOBOOTH_THEME':'tropical-thai','PHOTOBOOTH_MENU_MODES':'tropical-thai',
 'PHOTOBOOTH_AI_ENABLED':'true','PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED':'true',
 'PHOTOBOOTH_CAMERA_SELECTOR_ENABLED':'auto','PHOTOBOOTH_PRINT_FORTUNES':'false',
 'ARTIFACT_SPIDERVERSE_QUEST_ENABLED':'false','ARTIFACT_WEEKLY_THEME_SCHEDULE_ENABLED':'0',
}
# Keep provider credentials, upload recovery and unrelated runtime settings unchanged.
lines=p.read_text().splitlines()
result=[line for line in lines if line.partition('=')[0].strip() not in updates]
result += [f'{k}={v}' for k,v in updates.items()]
fd,tmp=tempfile.mkstemp(prefix='.env-tropical-',dir=p.parent)
try:
 os.fchmod(fd,p.stat().st_mode & 0o777)
 with os.fdopen(fd,'w') as f:
  f.write('\n'.join(result)+'\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,p)
finally:
 if os.path.exists(tmp):os.unlink(tmp)
print('TROPICAL THAI configured; quest disabled; weekly theme switching paused')
PY
if [[ "${1:-}" == --restart ]]; then
  ARTIFACT_RESTART_SERVICES=artifact ARTIFACT_MARK_RESTART_PENDING=1 "$REPO_DIR/scripts/restart-artifact-if-idle.sh"
fi

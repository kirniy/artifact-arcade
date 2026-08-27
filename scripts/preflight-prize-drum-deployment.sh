#!/usr/bin/env bash
# Fail-closed ФОТОБУДКА ВИНОВНИЦЫ prize-drum deployment gate.
#
# This script never enables the feature, changes credentials, or touches the
# printer.  Run once before activation and once with --post-activation after
# the supervised switch.  Real paper/scanner/OIDC/boost and 60-spin checks
# remain mandatory in docs/software/artifact-prize-drum-physical-canary.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFLIGHT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PREFLIGHT_DOTENV="$PREFLIGHT_ROOT/.env"
PREFLIGHT_HARDWARE=false
PREFLIGHT_POST_ACTIVATION=false
PREFLIGHT_FOCUSED=false

for preflight_arg in "$@"; do
  case "$preflight_arg" in
    --hardware) PREFLIGHT_HARDWARE=true ;;
    --post-activation)
      PREFLIGHT_HARDWARE=true
      PREFLIGHT_POST_ACTIVATION=true
      ;;
    --focused) PREFLIGHT_FOCUSED=true ;;
    -h|--help)
      echo "usage: $0 [--focused] [--hardware|--post-activation]"
      exit 0
      ;;
    *)
      echo "FAIL: unknown argument: $preflight_arg" >&2
      exit 2
      ;;
  esac
done

preflight_fail() {
  echo "FAIL: $*" >&2
  exit 1
}

preflight_pass() {
  echo "PASS: $*"
}

if [[ -x "$PREFLIGHT_ROOT/.venv/bin/python" ]]; then
  PREFLIGHT_PYTHON="$PREFLIGHT_ROOT/.venv/bin/python"
elif [[ -x /opt/homebrew/opt/python@3.13/bin/python3.13 ]]; then
  PREFLIGHT_PYTHON=/opt/homebrew/opt/python@3.13/bin/python3.13
else
  PREFLIGHT_PYTHON="$(command -v python3 || true)"
fi
[[ -n "$PREFLIGHT_PYTHON" ]] || preflight_fail "Python 3 is unavailable"

cd "$PREFLIGHT_ROOT"

"$PREFLIGHT_PYTHON" -m py_compile \
  src/artifact/modes/prize_drum.py \
  src/artifact/services/vnvnc_kiosk.py \
  src/artifact/printing/wheel_prize_roll.py \
  src/artifact/hardware/printer/rp80.py \
  scripts/render_prize_drum_previews.py \
  scripts/run_prize_drum_canary_backend.py
preflight_pass "critical Python modules compile"

if [[ "$PREFLIGHT_FOCUSED" == true ]]; then
  PREFLIGHT_TEST_TARGETS=(
    tests/test_prize_drum.py
    tests/test_prize_drum_canary_backend.py
    tests/test_wheel_prize_roll.py
    tests/test_printer_device_detection.py
    tests/test_photobooth_menu_modes.py
  )
else
  PREFLIGHT_TEST_TARGETS=(tests)
fi
PYTHONPATH=src "$PREFLIGHT_PYTHON" -m pytest -q "${PREFLIGHT_TEST_TARGETS[@]}"
preflight_pass "automated regression suite"

command -v ffmpeg >/dev/null || preflight_fail "ffmpeg is unavailable"
command -v ffprobe >/dev/null || preflight_fail "ffprobe is unavailable"
PREFLIGHT_TMP="$(mktemp -d "${TMPDIR:-/tmp}/vnvnc-prize-drum-preflight.XXXXXX")"
trap 'rm -rf -- "$PREFLIGHT_TMP"' EXIT

PYTHONPATH=src "$PREFLIGHT_PYTHON" scripts/render_prize_drum_previews.py \
  --output-dir "$PREFLIGHT_TMP"

for preflight_video in \
  "$PREFLIGHT_TMP/prize-drum-motion-preview.mp4" \
  "$PREFLIGHT_TMP/prize-drum-walkthrough.mp4"; do
  [[ -s "$preflight_video" ]] || preflight_fail "preview video was not produced"
  preflight_codec="$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,pix_fmt -of csv=p=0 "$preflight_video")"
  [[ "$preflight_codec" == h264,yuv420p ]] || \
    preflight_fail "unexpected video contract: $preflight_codec"
  preflight_audio_count="$(ffprobe -v error -select_streams a \
    -show_entries stream=index -of csv=p=0 "$preflight_video" | wc -l | tr -d ' ')"
  [[ "$preflight_audio_count" == 0 ]] || preflight_fail "preview unexpectedly contains audio"
  preflight_black_log="$(ffmpeg -hide_banner -nostats -i "$preflight_video" \
    -vf 'blackdetect=d=0.08:pix_th=0.02' -an -f null - 2>&1)"
  if grep -q 'black_start:' <<<"$preflight_black_log"; then
    preflight_fail "black interval detected in $(basename "$preflight_video")"
  fi
done
preflight_pass "H.264 previews are silent, yuv420p, and contain no black interval"

PREFLIGHT_WALKTHROUGH="$PREFLIGHT_TMP/prize-drum-walkthrough.mp4" \
PYTHONPATH=src "$PREFLIGHT_PYTHON" - <<'PY'
import os
import sys

import cv2

sys.path.insert(0, "scripts")
import render_prize_drum_previews as preview

expected = {
    preview.AUTH_URL,
    preview._award().coupon.redeem_qr_payload,
}
found: set[str] = set()
capture = cv2.VideoCapture(os.environ["PREFLIGHT_WALKTHROUGH"])
frame_index = 0
detector = cv2.QRCodeDetector()
while True:
    ok, frame = capture.read()
    if not ok:
        break
    if frame_index % 5 == 0:
        main = frame[92:860, 96:864]
        value, points, _straight = detector.detectAndDecode(main)
        if points is not None and value:
            found.add(value)
    frame_index += 1
capture.release()
missing = expected - found
if missing:
    raise SystemExit(f"compressed walkthrough QR decode failed for {len(missing)} payload(s)")
PY
preflight_pass "both compressed-video QR payloads decode exactly"

if [[ "$PREFLIGHT_HARDWARE" != true ]]; then
  preflight_pass "local gate complete; cabinet checks were not requested"
  exit 0
fi

[[ "$(uname -s)" == Linux ]] || preflight_fail "--hardware must run on ФОТОБУДКА ВИНОВНИЦЫ"
for preflight_command in systemctl journalctl lsusb rpicam-hello curl; do
  command -v "$preflight_command" >/dev/null || \
    preflight_fail "$preflight_command is unavailable on the cabinet"
done

for preflight_service in artifact artifact-dashboard tailscaled; do
  systemctl is-active --quiet "$preflight_service" || \
    preflight_fail "$preflight_service is not active"
done
preflight_pass "cabinet services are active"

lsusb -d 0fe6:811e >/dev/null || preflight_fail "RP80 0fe6:811e is not connected"
preflight_pass "exact RP80 USB identity is present"

preflight_camera_list="$(rpicam-hello --list-cameras 2>&1)"
grep -qi 'imx708' <<<"$preflight_camera_list" || preflight_fail "IMX708 camera is unavailable"
preflight_pass "IMX708 camera is available"

PREFLIGHT_SERVICE_ENV="$(systemctl show artifact --property=Environment --value)"
PREFLIGHT_POST_ACTIVATION="$PREFLIGHT_POST_ACTIVATION" \
PREFLIGHT_SERVICE_ENV="$PREFLIGHT_SERVICE_ENV" \
PREFLIGHT_DOTENV="$PREFLIGHT_DOTENV" \
"$PREFLIGHT_PYTHON" - <<'PY'
import os
import shlex
from pathlib import Path
from urllib.parse import urlparse

raw = os.environ.get("PREFLIGHT_SERVICE_ENV", "")
values = {}
dotenv_path = Path(os.environ["PREFLIGHT_DOTENV"])
if dotenv_path.is_file():
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
for token in shlex.split(raw):
    if "=" in token:
        key, value = token.split("=", 1)
        values[key] = value

truthy = {"1", "true", "yes", "on"}
errors = []
if values.get("ARTIFACT_ENV", "").lower() != "hardware":
    errors.append("ARTIFACT_ENV is not hardware")
for key in ("ARTIFACT_KIOSK_STUB", "ARTIFACT_MOCK_PRINTER", "ARTIFACT_MOCK_HARDWARE"):
    if values.get(key, "").strip().lower() in truthy:
        errors.append(f"{key} is enabled")
if not values.get("ARTIFACT_KIOSK_DEVICE_ID", "").strip():
    errors.append("device ID is absent")
if len(values.get("ARTIFACT_KIOSK_DEVICE_SECRET", "").strip()) < 24:
    errors.append("device secret is absent or too short")
base_url = values.get("VNVNC_KIOSK_API_BASE_URL", "")
parsed = urlparse(base_url)
if parsed.scheme != "https" or not parsed.hostname:
    errors.append("VNVNC kiosk API is not an explicit HTTPS URL")
enabled = values.get("ARTIFACT_PRIZE_DRUM_ENABLED", "").strip().lower() in truthy
post = os.environ.get("PREFLIGHT_POST_ACTIVATION", "false") == "true"
if enabled != post:
    expected = "enabled" if post else "disabled before activation"
    errors.append(f"prize drum is not {expected}")
if errors:
    raise SystemExit("unsafe service configuration: " + "; ".join(errors))
PY
PREFLIGHT_API_URL="$(PREFLIGHT_POST_ACTIVATION="$PREFLIGHT_POST_ACTIVATION" \
  PREFLIGHT_SERVICE_ENV="$PREFLIGHT_SERVICE_ENV" \
  PREFLIGHT_DOTENV="$PREFLIGHT_DOTENV" \
  "$PREFLIGHT_PYTHON" - <<'PY'
import os
import shlex
from pathlib import Path
values = {}
dotenv_path = Path(os.environ["PREFLIGHT_DOTENV"])
if dotenv_path.is_file():
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
for token in shlex.split(os.environ["PREFLIGHT_SERVICE_ENV"]):
    if "=" in token:
        key, value = token.split("=", 1)
        values[key] = value
print(values.get("VNVNC_KIOSK_API_BASE_URL", "").rstrip("/"))
PY
)"
[[ -n "$PREFLIGHT_API_URL" ]] || preflight_fail "kiosk API URL was not resolved"
preflight_http_code="$(curl --silent --show-error --output /dev/null \
  --connect-timeout 5 --max-time 10 --write-out '%{http_code}' "$PREFLIGHT_API_URL/")"
[[ "$preflight_http_code" != 000 && "$preflight_http_code" != 5* ]] || \
  preflight_fail "VNVNC API TLS/reachability check failed"
preflight_pass "production configuration is fail-closed and API is reachable"

preflight_recent_logs="$(journalctl -u artifact --since '15 minutes ago' --no-pager)"
if grep -Eiq 'Traceback|CRITICAL|segmentation fault|watchdog.*(timeout|failed)|mock RP80|black frame' \
  <<<"$preflight_recent_logs"; then
  preflight_fail "critical pattern found in recent artifact.service logs"
fi
preflight_pass "recent artifact.service logs contain no critical pattern"

if [[ "$PREFLIGHT_POST_ACTIVATION" == true ]]; then
  preflight_pass "post-activation software/hardware gate complete"
else
  preflight_pass "pre-activation software/hardware gate complete"
fi
echo "MANUAL GATE REMAINS: supervised real LED/RP80/scanner/OIDC/boost and 60-spin soak."

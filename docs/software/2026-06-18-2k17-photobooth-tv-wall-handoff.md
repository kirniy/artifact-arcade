# 2026-06-18 2K17 Photobooth And Optional TV Wall Handoff

This note captures the current 2K17 photobooth setup and the optional CRT/TV-wall mode. The stable live setup is one process owning both HDMI outputs: `artifact` drives the photobooth screen on HDMI-A-1 and the TV wall on HDMI-A-2. Do not run a second fullscreen wall process during guest operation.

## User-Facing Behavior

When guests enter the 2K17 photobooth mode, the machine first shows a camera selection screen:

- `CAM1: СПЕРЕДИ` uses the regular front Raspberry Pi camera.
- `CAM2: СЗАДИ` uses the HDMI capture card feed from the rear/secondary camera.

The selected camera preview is shown live on the 128x128 screen and crop-fills the square display. After the guest confirms, the normal countdown starts.

The idle screen for this theme uses the 2K17 fan video at `assets/idle/2k17/video/2k17-fans.mp4`, processed to 128x128 for cheap Pi playback. The idle overlay shows `2K17` while real upload/session metadata still uses real current dates.

Camera 1 follows the normal AI photobooth flow: capture, 2K17 themed generation, waiting screen, final image, QR, upload, bot event, and print.

Camera 2 is configured as the low-risk path by default: it captures the HDMI feed and uploads/prints that image directly without AI. This avoids extra latency and avoids fighting the video-wall process for the capture card. AI for Camera 2 can be enabled later with `PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED=true`, but the safe event default is `false`.

Visible 2K17 artwork can show `2017` for the party concept. Upload filenames, S3 metadata, gallery grouping, bot stats, and club-night logic still use real current Moscow timestamps.

## Optional TV Wall Behavior

When the TV wall is off, the photobooth still works normally. Camera 1 always works. Camera 2 only works if the USB HDMI capture card is connected and readable.

When the TV wall is on, it runs inside `artifact` through `HDMIDisplayKMSDual`:

- reads the USB HDMI capture card
- writes a shared latest-frame JPEG under `data/video_wall/`
- touches a heartbeat file so photobooth knows the wall owns the card
- renders a VHS/CRT-style live image with the flame emblem, `REC`, Moscow time, and a visible `2017` date

Photobooth Camera 2 should read the shared frame while the wall is active. This is the intended no-conflict path for the capture device: one process owns the USB capture device, and the photobooth consumes a JPEG snapshot.

### 2026-06-21 Live Display Findings

The current Pi/display stack cannot safely run the photobooth screen and the TV wall as two independent fullscreen DRM/KMS owners. The working architecture is:

- `artifact` is active.
- `vnvnc-video-wall` is inactive and disabled.
- `artifact.main` is the only process owning `/dev/dri/card1`.
- `HDMI-A-1` is the NovaStar/photobooth screen.
- `HDMI-A-2` is the TV-wall splitter output.
- `VNVNC_INPROCESS_TV_WALL_ENABLED=true` enables the dual KMS backend.
- `VNVNC_VIDEO_WALL_SWITCH_INTERVAL=0` keeps the wall on the HDMI capture card only; it does not switch to the photobooth camera.
- `assets/idle/2k17/video/2k17-fans.mp4` is present and loaded for idle mode.

Confirmed good live state on 2026-06-21 at 02:23 MSK:

- Booth screen recovered and stayed normal after startup.
- TVs showed the intended live wall feed.
- HDMI-A-2 was changed to `640x480`, which is the remembered working CRT/VGA-style output mode for this splitter/converter chain.
- User confirmed: "Ok all good."

Verified live command state:

```bash
systemctl is-active artifact            # active
systemctl is-active vnvnc-video-wall    # inactive
sudo fuser -v /dev/dri/card1            # only python -m artifact.main
kmsprint                                # HDMI-A-1 and HDMI-A-2 both connected
```

The 2026-06-21 confirmed-good init log is:

```text
Pygame initialized (driver: KMSDRM)
Opened HDMI capture card /dev/video0 at 640x480@25 fourcc=MJPG
KMS dual HDMI initialized: main=720x480 wall=640x480
```

After the CRTs looked too small/squished at `1280x720`, the confirmed live mode is `640x480` on HDMI-A-2. This is a normal 4:3 VGA mode advertised by the splitter/converter chain and makes the logo/time overlays larger on the TVs.

Switch TV-wall resolution with:

```bash
cd /home/kirniy/modular-arcade
./scripts/set-vnvnc-tv-wall-mode.sh 640x480 --restart
```

Revert immediately with:

```bash
cd /home/kirniy/modular-arcade
./scripts/set-vnvnc-tv-wall-mode.sh 1280x720 --restart
```

The script only changes `.env`, disables the standalone wall service, and idle-gates the `artifact` restart. The key env values are:

```text
VNVNC_INPROCESS_TV_WALL_ENABLED=true
VNVNC_VIDEO_WALL_OUTPUT_WIDTH=640
VNVNC_VIDEO_WALL_OUTPUT_HEIGHT=480
VNVNC_VIDEO_WALL_DRM_CONNECTOR=HDMI-A-2
VNVNC_MAIN_DRM_CONNECTOR=HDMI-A-1
VNVNC_VIDEO_WALL_SWITCH_INTERVAL=0
VNVNC_VIDEO_WALL_PRIMARY_WINDOW=0
VNVNC_VIDEO_WALL_DISPLAY_YEAR=2017
```

Do not leave both `artifact` and standalone `vnvnc-video-wall` running. If `vnvnc-video-wall` owns `/dev/dri/card1`, the photobooth app can start but its main screen can render offscreen or become corrupted. If `artifact` owns `/dev/dri/card1` first, standalone `vnvnc-video-wall` fails with `Failed to set DRM plane ... -13`.

Rejected paths from live testing:

- `VNVNC_VIDEO_WALL_OUTPUT=fbdev` writes `/dev/fb0` and can corrupt the photobooth main display.
- `VNVNC_VIDEO_WALL_OUTPUT=pygame` can run and update `data/video_wall/heartbeat`, but on this Pi it does not drive the physical TV HDMI output.
- Forcing `SDL_VIDEODRIVER=kmsdrm` in the wall service fails with `pygame.error: kmsdrm not available`.

Headless previews from a dev Mac use synthetic placeholder frames because there is no USB capture card there. They verify overlay rendering only; they do not prove live camera video.

The standalone video-wall service is intentionally not enabled or started by default. It is only an isolated diagnostic tool with `artifact` stopped.

## Hardware Wiring For TV Wall Night

Keep the existing arcade wiring untouched.

Connect the secondary camera path:

1. Camera / GoPro-like camera HDMI out.
2. HDMI cable into the USB HDMI capture card.
3. USB HDMI capture card into the Raspberry Pi spare USB port.

Connect the TV wall output:

1. Use the Raspberry Pi spare micro-HDMI output for the TV wall.
2. Micro-HDMI to HDMI cable into the HDMI splitter input.
3. Splitter HDMI outputs to the six HDMI cables.
4. Each HDMI cable goes into its HDMI-to-VGA converter.
5. VGA converters feed the CRT/TV inputs.
6. Power the splitter and converters before starting the wall service.

The Raspberry Pi does not need to know there are six TVs. It only outputs one HDMI signal to the splitter.

## Safe Deploy Path

The current safe deploy path is built around two scripts:

```bash
cd /home/kirniy/modular-arcade
git pull --ff-only origin main
./scripts/activate-2k17-photobooth.sh --restart
```

`activate-2k17-photobooth.sh` sets:

- `PHOTOBOOTH_THEME=2k17`
- `PHOTOBOOTH_MENU_MODES=2k17`
- `PHOTOBOOTH_CAMERA_SELECTOR_ENABLED=auto`
- `PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED=false`
- `VNVNC_PRIMARY_CAMERA_SHARED_FRAME_ENABLED=true`
- `VNVNC_VIDEO_WALL_DISPLAY_YEAR=2017`

The restart is idle-gated through `scripts/restart-artifact-if-idle.sh`. If guests are using the booth, the script writes a pending marker and does not restart `artifact`.

`scripts/autopull.sh` also auto-activates the 2K17 env by default after pulling the new code, then tries the same idle-gated restart. Set `ARTIFACT_AUTO_ACTIVATE_2K17=0` if a future event should not auto-switch to this theme.

## TV Wall Mode And Test

Normal live mode is in-process:

```bash
cd /home/kirniy/modular-arcade
./scripts/set-vnvnc-tv-wall-mode.sh 640x480 --restart
```

Use `1280x720` only if the TV chain clearly handles it better:

```bash
cd /home/kirniy/modular-arcade
./scripts/set-vnvnc-tv-wall-mode.sh 1280x720 --restart
```

After a power cycle, run this if the TVs are wrong or show a stale boot/fallback frame:

```bash
cd /home/kirniy/modular-arcade
./scripts/set-vnvnc-tv-wall-mode.sh 640x480 --restart
./scripts/check-vnvnc-video-wall.sh
```

Run diagnostics without changing live output:

```bash
./scripts/check-vnvnc-video-wall.sh
```

Expected live checks:

```text
artifact active
vnvnc-video-wall inactive
KMS dual HDMI initialized: main=720x480 wall=640x480
data/video_wall/heartbeat age under 2 seconds
data/video_wall/hdmi_capture_latest.jpg changing
```

If the booth screen is ever wrong, return to photobooth-only safe mode:

```bash
sudo systemctl stop vnvnc-video-wall
cd /home/kirniy/modular-arcade
python3 - <<'PY'
from pathlib import Path
path = Path(".env")
lines = path.read_text().splitlines()
out = []
for line in lines:
    if line.startswith("VNVNC_INPROCESS_TV_WALL_ENABLED="):
        out.append("VNVNC_INPROCESS_TV_WALL_ENABLED=false")
    else:
        out.append(line)
path.write_text("\n".join(out).rstrip() + "\n")
PY
./scripts/restart-artifact-if-idle.sh
```

If the standalone diagnostic service must be installed, install it without enabling it:

```bash
cd /home/kirniy/modular-arcade
sudo ./scripts/install-vnvnc-video-wall.sh
```

Do not enable it permanently.

## Verification Checklist

Before opening to guests:

- `artifact` is running and the main 128x128 display is live.
- `.env` has `PHOTOBOOTH_THEME=2k17` and `PHOTOBOOTH_MENU_MODES=2k17`.
- Entering photobooth shows `CAM1: СПЕРЕДИ` and `CAM2: СЗАДИ`.
- Camera 1 preview is live and can complete a full AI photo.
- If the capture card is connected, Camera 2 preview is live and crop-filled square.
- Camera 2 can complete the raw no-AI capture path.
- Uploads land in Selectel and gallery dates use real current dates.
- Bot receives the result/source photo event.
- `vnvnc-video-wall` is inactive/disabled and `artifact` owns `/dev/dri/card1`.
- If the wall is enabled, TVs show the VHS feed and `data/video_wall/heartbeat` updates.
- If testing 640x480, artifact logs `KMS dual HDMI initialized: main=720x480 wall=640x480`.

## Key Files

- `src/artifact/modes/photobooth.py`
- `src/artifact/modes/photobooth_themes.py`
- `src/artifact/ai/caricature.py`
- `src/artifact/animation/idle_scenes.py`
- `src/artifact/utils/hdmi_capture.py`
- `src/artifact/utils/camera_service.py`
- `src/artifact/video_wall/renderer.py`
- `scripts/activate-2k17-photobooth.sh`
- `scripts/restart-artifact-if-idle.sh`
- `scripts/install-vnvnc-video-wall.sh`
- `scripts/check-vnvnc-video-wall.sh`
- `scripts/set-vnvnc-tv-wall-mode.sh`
- `scripts/vnvnc-video-wall.service`
- `assets/idle/2k17/video/2k17-fans.mp4`

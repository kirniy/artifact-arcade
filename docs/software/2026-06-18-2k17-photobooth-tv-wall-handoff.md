# 2026-06-18 2K17 Photobooth And Optional TV Wall Handoff

This note captures the current 2K17 photobooth setup and the optional CRT/TV-wall mode. The TV wall is not part of the normal boot path: most nights it can stay off, and for specific events it can be installed, tested, and started separately.

## User-Facing Behavior

When guests enter the 2K17 photobooth mode, the machine first shows a camera selection screen:

- `CAM1: СПЕРЕДИ` uses the regular front Raspberry Pi camera.
- `CAM2: СЗАДИ` uses the HDMI capture card feed from the rear/secondary camera.

The selected camera preview is shown live on the 128x128 screen and crop-fills the square display. After the guest confirms, the normal countdown starts.

Camera 1 follows the normal AI photobooth flow: capture, 2K17 themed generation, waiting screen, final image, QR, upload, bot event, and print.

Camera 2 is configured as the low-risk path by default: it captures the HDMI feed and uploads/prints that image directly without AI. This avoids extra latency and avoids fighting the video-wall process for the capture card. AI for Camera 2 can be enabled later with `PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED=true`, but the safe event default is `false`.

Visible 2K17 artwork can show `2017` for the party concept. Upload filenames, S3 metadata, gallery grouping, bot stats, and club-night logic still use real current Moscow timestamps.

## Optional TV Wall Behavior

When the TV wall is off, the photobooth still works normally. Camera 1 always works. Camera 2 only works if the USB HDMI capture card is connected and readable.

When the TV wall is on, it runs as a separate service:

- reads the USB HDMI capture card
- writes a shared latest-frame JPEG under `data/video_wall/`
- touches a heartbeat file so photobooth knows the wall owns the card
- renders a VHS/CRT-style live image with the flame emblem, `REC`, Moscow time, and a visible `2017` date
- can occasionally switch to the shared regular camera preview without opening the Pi camera directly

Photobooth Camera 2 should read the shared frame while the wall is active. This is the intended no-conflict path: one process owns the USB capture device, and the photobooth consumes a JPEG snapshot.

The video-wall service is intentionally not enabled or started by default. Install and test it manually only when the HDMI splitter/capture hardware is present.

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

## TV Wall Install And Test

Install the service without starting it:

```bash
cd /home/kirniy/modular-arcade
sudo ./scripts/install-vnvnc-video-wall.sh
```

Run diagnostics:

```bash
./scripts/check-vnvnc-video-wall.sh
```

Only after the capture card and spare HDMI output are confirmed, start the wall:

```bash
sudo systemctl start vnvnc-video-wall
journalctl -u vnvnc-video-wall -f
```

Stop it with:

```bash
sudo systemctl stop vnvnc-video-wall
```

Do not enable it permanently until the wall has been tested on the actual Pi/display stack. The main arcade service and the wall service both use display output, so the wall should be treated as an event-specific process.

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
- If the wall is on, TVs show the VHS feed and `data/video_wall/heartbeat` updates.
- If the wall is off, photobooth still works normally.

## Key Files

- `src/artifact/modes/photobooth.py`
- `src/artifact/modes/photobooth_themes.py`
- `src/artifact/ai/caricature.py`
- `src/artifact/utils/hdmi_capture.py`
- `src/artifact/utils/camera_service.py`
- `src/artifact/video_wall/renderer.py`
- `scripts/activate-2k17-photobooth.sh`
- `scripts/restart-artifact-if-idle.sh`
- `scripts/install-vnvnc-video-wall.sh`
- `scripts/check-vnvnc-video-wall.sh`
- `scripts/vnvnc-video-wall.service`

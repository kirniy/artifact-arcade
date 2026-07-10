# Summer Camp Photobooth Handoff

Last production verification: July 11, 2026, Moscow time.

## Active Configuration

```dotenv
PHOTOBOOTH_THEME=summer-camp
PHOTOBOOTH_MENU_MODES=summer_camp
VNVNC_INPROCESS_TV_WALL_ENABLED=false
VNVNC_PRIMARY_CAMERA_SHARED_FRAME_ENABLED=false
PHOTOBOOTH_HDMI_CAPTURE_AI_ENABLED=false
```

`summer-camp` is the theme ID. `summer_camp` is the menu registry key. Using the hyphenated value in `PHOTOBOOTH_MENU_MODES` is invalid and falls back to the default multi-mode menu.

The event has no hard-coded dates. `event_date=""`, `footer_date_mode="weekday_ru"`, and `party_date_rollover_hour=12` produce the real Moscow club-night weekday: Friday night through Saturday morning remains Friday; Saturday night through Sunday morning remains Saturday. Upload metadata and gallery grouping always use real timestamps.

## Assets

- Logo: `assets/images/summer-camp.png`
- Idle video: `assets/idle/summer_camp/video/summer-camp-fans.mp4`
- Idle video format: H.264, 128x128, 12 FPS, YUV420p

## Ticker Contract

All photobooth states call `render_idle_style_ticker_text()` through one path after clearing the 48x8 buffer to black:

- idle: `SUMMER`
- camera selector: `СПЕРЕДИ` / `СЗАДИ`
- countdown: current digit
- processing: `НЕ УХОДИ`
- completed photo: `ГОТОВО`
- QR view: `QR`

The physical WS2812 driver uses bounded recovery refresh. Changed animation frames are capped at 15 FPS; unchanged frames are resent every 250 ms so a corrupted physical latch cannot remain indefinitely. Do not restore unconditional 60 FPS transmission and do not change this to a permanent write-once hold.

Regression tests:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_photobooth_ticker_states.py \
  tests/test_ws2812b_mapping.py
```

The mapping test protects the verified December 31, 2025 physical matrix order and serpentine parity. The ticker-state test protects the complete user journey and exact result renderer path.

## Safe Deployment

The Pi at `/home/kirniy/modular-arcade` may be a release directory without `.git`. Inspect it before choosing a deployment method. When it has no repository metadata:

1. Compare local and remote hashes.
2. Back up every changed remote file under `data/deploy_backups/` with a timestamp.
3. Copy only required files with `scp`.
4. Compile with a temporary bytecode cache if the existing `__pycache__` is root-owned:

```bash
PYTHONPYCACHEPREFIX=/tmp/artifact-pycache PYTHONPATH=src \
  .venv/bin/python -m py_compile <changed-python-files>
```

5. Restart only through the idle gate:

```bash
ARTIFACT_MARK_RESTART_PENDING=1 ./scripts/restart-artifact-if-idle.sh
```

6. Require `artifact`, `arcade-bot`, and `artifact-upload-spool` to be active, `vnvnc-video-wall` to be inactive, exactly one mode to be registered, the Summer Camp idle video to load, and the camera plus WS2812 ticker to initialize without exceptions.

## Relevant Commits

- `39b5e34` unifies all photobooth ticker states behind one renderer.
- `15d992e` introduced change-driven WS2812 output.
- `8215a85` supersedes the permanent static hold with a 15 FPS cap and 250 ms recovery refresh after physical validation.

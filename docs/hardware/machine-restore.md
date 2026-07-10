# ARTIFACT Machine Restore

This document describes the current known-good restore state for the full machine, not just the NovaStar sender.

Last verified:
- July 11, 2026

## What "Working" Means

- Main screen:
  Pi `pygame` / `KMSDRM` output at `720x480` over HDMI to the NovaStar T50, cropped to the top-left `128x128`, then forwarded to the DH418 and panels.
- Ticker:
  WS2812B mapping uses the December 31, 2025 baseline, explicit physical GRB order, and brightness `32`. This eliminated the red noise onsite on July 11, 2026.
- Photobooth:
  Camera capture works, AI generation works, Selectel S3 upload works.
- Current event mode:
  `PHOTOBOOTH_THEME=summer-camp`, `PHOTOBOOTH_MENU_MODES=summer_camp`

## Ticker Production Baseline

- `HardwareConfig.ws2812b_brightness=32`
- `PixelStrip(..., strip_type=WS2811_STRIP_GRB)`
- photobooth theme labels measure at most 48 pixels
- idle and selector labels are static in each theme's ticker color
- processing hard-cuts between `ЖДИ` and `НЕ УХОДИ`
- completed-photo state hard-cuts between `ФОТО` and `НА ЧЕКЕ`
- ticker cross-display particles are disabled
- the main-screen processing countdown and bottom progress bar remain animated

These rules apply to every registered photobooth theme. Summer Camp additionally uses `ticker_color=(0,255,48)` while keeping its original main-screen palette.

Validate with:

```bash
PYTHONPATH=src python -m pytest -q \
  tests/test_photobooth_ticker_states.py \
  tests/test_ws2812b_mapping.py
```

## Tracked Recovery Assets

- NovaStar config set:
  `configs/novastar/`
- Service definition:
  `scripts/artifact.service`
- Pi boot args snapshot kept in repo:
  `pi-config/cmdline.txt`
- Hardware docs:
  `docs/hardware/display-setup.md`
  `docs/hardware/novastar-setup.md`

## Critical Failure Mode

The T50 is not a dumb HDMI bridge.

If the screen shows an old uploaded photo, do not assume the receiver mapping is lost.

That symptom can mean:
- panel mapping is still correct
- DH418 is still driving the panels correctly
- T50 is showing internal stored media instead of HDMI

On March 28, 2026, the machine recovered after the T50 front-panel switch had been pressed accidentally.

## Pi State That Must Be Preserved

- `/etc/systemd/system/artifact.service`
- `/boot/firmware/config.txt`
- `/boot/firmware/cmdline.txt`
- NetworkManager connection profiles
- `/home/kirniy/modular-arcade/.env`
- AWS credentials used for Selectel S3
- current repo worktree state, including uncommitted diffs

## Snapshot Workflow

Run:

```bash
scripts/snapshot_artifact_machine.sh
```

This creates an ignored local backup under `machine-backups/<timestamp>/` containing:
- local repo git status and diff
- local tracked recovery files
- remote Pi diagnostics
- remote root-owned config tarball

Use this after any meaningful machine-side fix.

## First Recovery Order

1. Ensure the Pi app is actually running.
2. Check the T50 source/switch before touching NovaStar mapping.
3. Only reload `rcfgx` / mapping if live HDMI is back but the panel image is garbled, split, or black.
4. If the machine must be rebuilt, restore from the latest `machine-backups/` snapshot plus the tracked repo files listed above.

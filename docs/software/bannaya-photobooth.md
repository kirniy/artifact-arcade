# БАННАЯ photobooth theme

The new `bannaya` theme is separate from the April `banya_chic` / «БАННЫЙ ШИК» menu entry. It uses the September «БАННАЯ» wooden plaque and the approved LED fan video, with pale timber and steam so the portrait remains readable on monochrome thermal labels. Guest portraits use expressive painted 2D romance visual-novel illustration, in the spirit of «Клуб Романтики». All guests wear closed belted bathrobes; faces are illustrated too, with original facial geometry, ethnic features, expressions, group layout and poses preserved. Scene variations change only background and edge props. The old photoreal bathhouse and Octane 3D directions are excluded.

## Source assets

- Plaque: `/Users/kirniy/dev/PRINT/bannaya/masters/02-emblem.png` (source SHA-256 `82377c32868efe171afe29762084cba4e27d7076dd9f7d7765b63baa63453e28`). The 2048-pixel lossless PNG at `assets/images/bannaya-emblem.png` is pinned by the theme hash. The master is unchanged.
- Video: `/Users/kirniy/dev/VIDEOS/bannaya/regular/02-LED-FAN-SOUND-H264.mp4` (source SHA-256 `1e37ee2dbb2312ea4cbd8ff456ed92c59dca797209cc87eef96860c5213e2f0a`). `assets/idle/bannaya/video/bannaya-fans.mp4` is the complete 132-second picture scaled to 128×128, 24 fps H.264, silent. The player loops it without multiplying file size or playing the source audio over the booth.
- Scene inspiration: the approved wooden photo-zone master and the banya show's birch/steam/samovar/furako boards. The old ornate gold «БАННЫЙ ШИК» emblem is intentionally absent.

## Activation on the actual Pi

Do not replace the Pi's runtime branch wholesale. Check `git status`, the active guest state, camera and printer health, and `arcade-autopull.timer` behavior first. Bring this branch's new code and two assets into the installed `artifact-runtime` branch while preserving unrelated machine changes. Then, while idle:

```bash
cd /home/kirniy/modular-arcade
VNVNC_PYTHON=.venv/bin/python bash scripts/activate-bannaya-photobooth.sh --restart
```

Activation validates the emblem hash, new enum/menu wiring, full video decode and Python syntax before changing `.env`. It saves the original `.env.before-bannaya` once and writes atomically. It selects only `bannaya`, enables AI and camera selection, turns off the expired dated Project X schedule and weekly theme switching, and does **not** disable the independent PARTY EXAM keypad gate. `--restart` delegates to the existing restart-if-idle script. Provider credentials and unrelated settings are preserved.

Verify the live logo, 132-second loop, first generated portrait, grayscale receipt and printer paper in person. A local AI mock and `ffmpeg` decode do not prove image quality, camera exposure or paper appearance. If the printer remains disconnected, record that separately rather than calling printing verified.

## Local verification

`PYTHONPATH=src python -m pytest -q tests/test_photobooth_bannaya.py tests/test_photobooth_project_x.py tests/test_project_x_idle.py tests/test_photobooth_tropical_thai.py tests/test_project_x_schedule.py tests/test_project_x_idle_schedule.py`

The activation script was run twice against a temporary `.env` with the old Project X schedule and PARTY EXAM key: it switched to `bannaya`, retained PARTY EXAM and an unrelated custom key, made a backup, and was idempotent. This is not a physical Pi test.
